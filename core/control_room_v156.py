"""V156 Control Room — isolated, GET-only executive analytics over existing ERP data.

Zero model changes, zero migrations, zero writes. PostgreSQL additionally
enforces READ ONLY at transaction level on every control-room request.
Never call helpers that auto-create baseline rows (e.g. digikala_receivable_total).
All estimates are labelled, all quantities use saved operational records.
"""
from collections import defaultdict
from datetime import timedelta

import jdatetime
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .dateutils import format_jalali
from .dia_gallery_v45 import dia_gallery_period_metrics, dia_gallery_receivable_total
from .finance import sale_line_metrics
from .inventory_valuation_v17 import finished_inventory_value_v17
from .material_report_overall_v137 import build_overall_report
from .report_v5 import _raw_material_context
from .self_spend_v62 import capital_accounts_queryset
from .tapsi_shop_v138 import tapsi_period_metrics, tapsi_receivable_total
from .models import (
    Account, AccountEntry, BusinessPayment, DigikalaSettlement, DiaGallerySale, Expense, Brand,
    ExcelManualRow, ExcelManualSetting, InventoryMovement, MaterialReportBlock,
    SaleAllocation, SaleLine, StockBalance, StockThreshold, TapsiStockAllocation,
    
)

SECTIONS = ("overview", "audit", "inventory", "profit", "cash", "production", "integrity")
NAV = (
    ("overview", "نمای مدیریتی", "◈"),
    ("audit", "حسابرسی مالی", "◎"),
    ("inventory", "موجودی و پیش‌بینی", "▦"),
    ("profit", "سودآوری محصولات", "▥"),
    ("cash", "نقدینگی و سرمایه", "◉"),
    ("production", "تولید و تامین", "⌁"),
    ("integrity", "ردیابی و اطمینان", "◇"),
)


def _amount(qs, field="amount"):
    return int(qs.aggregate(v=Sum(field))["v"] or 0)


def _period(today):
    jd = jdatetime.date.fromgregorian(date=today)
    return jd.replace(day=1).togregorian(), today


def _claim_digikala():
    # Direct read-only equivalent of finance_excel_v9's canonical components.
    baseline = ExcelManualSetting.objects.filter(
        key="digikala_receivable"
    ).values_list("value", flat=True).first() or 0
    entries = AccountEntry.objects.filter(
        account__key=Account.DIGIKALA, entry_type__in=("sale", "receipt")
    )
    return int(baseline) + _amount(entries, "delta")


def _capital():
    manual = ExcelManualRow.objects.filter(active=True)
    account_rows = capital_accounts_queryset(
        manual.filter(section=ExcelManualRow.ACCOUNTS)
    )
    account_total = _amount(account_rows)
    persons = _amount(manual.filter(section=ExcelManualRow.PERSONS))
    assets = _amount(manual.filter(section=ExcelManualRow.ASSETS))
    dia = int(dia_gallery_receivable_total())
    dk = _claim_digikala()
    tapsi = int(tapsi_receivable_total())
    finished = int(finished_inventory_value_v17())
    materials = int(_raw_material_context()["materials_total"] or 0)
    debt = int(ExcelManualSetting.objects.filter(
        key="takvin_debt"
    ).values_list("value", flat=True).first() or 0)
    value = account_total + persons + dia + dk + tapsi + finished + materials + assets - debt
    return {
        "capital_total": value, "cash_and_accounts": account_total,
        "persons": persons, "assets": assets, "finished": finished,
        "materials": materials, "digikala": dk, "tapsi": tapsi,
        "dia": dia, "takvin_debt": debt,
        "breakdown": (
            ("حساب‌های ثبت‌شده", account_total),
            ("حساب اشخاص", persons),
            ("موجودی کالای آماده", finished),
            ("مواد اولیه", materials),
            ("طلب دیجی‌کالا", dk),
            ("طلب تپسی‌شاپ", tapsi),
            ("طلب دیا گالری", dia),
            ("دارایی‌های ثبت‌شده", assets),
            ("بدهی تکوین (کسر)", -debt),
        ),
    }


def _sales(start, end):
    groups = {}
    channels = {
        "digikala": {"title": "دیجی‌کالا / فروش روزانه", "gross": 0, "profit": 0, "fee": 0, "packs": 0},
        "tapsi": {"title": "تپسی‌شاپ", "gross": 0, "profit": 0, "fee": 0, "packs": 0},
        "dia": {"title": "دیا گالری", "gross": 0, "profit": 0, "fee": 0, "packs": 0},
    }
    for line in SaleLine.objects.filter(
        day__date__gte=start, day__date__lte=end, quantity__gt=0,
    ).select_related("day", "product_size__product__brand", "product_size__size", "snapshot"):
        m = sale_line_metrics(line)
        p = line.product_size.product
        key = ("digikala", p.brand.name, p.code, line.product_size.size.name)
        row = groups.setdefault(key, {
            "channel": "دیجی‌کالا", "brand": p.brand.name, "code": p.code,
            "size": line.product_size.size.name, "title": p.title or p.code,
            "gross": 0, "profit": 0, "cogs": 0, "fee": 0, "packs": 0,
        })
        for k in ("gross", "profit", "cogs", "packs"):
            row[k] += int(m[k])
        row["fee"] += int(m["digikala_fee"])
        for k, source in (("gross", "gross"), ("profit", "profit"), ("packs", "packs")):
            channels["digikala"][k] += int(m[source])
        channels["digikala"]["fee"] += int(m["digikala_fee"])
    tapsi = tapsi_period_metrics(start, end)
    for item in tapsi["rows"]:
        key = ("tapsi", item["brand"], item["code"], item["size"])
        row = groups.setdefault(key, {
            "channel": "تپسی‌شاپ", "brand": item["brand"],
            "code": item["code"], "size": item["size"],
            "title": item["title"], "gross": 0, "profit": 0,
            "cogs": 0, "fee": 0, "packs": 0,
        })
        for k in ("gross", "profit", "cogs", "fee", "packs"):
            row[k] += int(item[k])
    for k in ("gross", "profit", "fee", "packs"):
        channels["tapsi"][k] = int(tapsi["total"][k])
    dia = dia_gallery_period_metrics(start, end)
    for k, key in (("gross", "gross"), ("profit", "profit"), ("fee", "digikala_fee"), ("packs", "packs")):
        channels["dia"][k] = int(dia["total"][key])
    # Dia is color-specific and not associated with a ProductCode. Keep it at
    # channel level instead of fabricating SKU profitability.
    ranked = sorted(groups.values(), key=lambda row: (-row["profit"], -row["gross"], row["code"]))
    for row in ranked:
        row["margin"] = round(100 * row["profit"] / row["gross"], 1) if row["gross"] else None
        row["return_on_cogs"] = round(100 * row["profit"] / row["cogs"], 1) if row["cogs"] else None
    maximum_gross = max((item["gross"] for item in channels.values()), default=0)
    for item in channels.values():
        item["bar"] = max(3, round(item["gross"] / maximum_gross * 100)) if maximum_gross > 0 else 0
    gross = sum(item["gross"] for item in channels.values())
    profit = sum(item["profit"] for item in channels.values())
    fee = sum(item["fee"] for item in channels.values())
    return {
        "channels": list(channels.values()), "products": ranked,
        "top": ranked[:8], "bottom": sorted(ranked, key=lambda row: (row["profit"], row["gross"]))[:8],
        "gross": gross, "profit": profit, "fee": fee,
        "margin": round(100 * profit / gross, 1) if gross else None,
        "packs": sum(item["packs"] for item in channels.values()),
        "start": format_jalali(start), "end": format_jalali(end),
    }


def _audit(start, end, limit=30):
    """Cross-check saved fees and receivable ledger without calling sync functions."""
    issues = []
    inspected = 0
    missing_snapshot = 0
    wrong_fee = 0
    ledger_gap = 0
    from .digikala_five_pack_v155 import applies_to as is_campaign
    from .finance import digikala_fee_for_unit

    lines = SaleLine.objects.filter(
        day__date__gte=start, day__date__lte=end, quantity__gt=0,
        product_size__product__brand__name__in=("دارما", "تکوین"),
    ).select_related("day", "product_size__product__brand", "product_size__size", "snapshot")
    for line in lines.iterator(chunk_size=200):
        inspected += 1
        try:
            snap = line.snapshot
        except Exception:
            snap = None
        pack = int((snap.pack_qty if snap else 0) or line.product_size.product.pack_qty or 0)
        price = int(line.sale_price or 0)
        code = line.product_size.product.code
        brand = line.product_size.product.brand.name
        qty = int(line.quantity)
        if not snap:
            missing_snapshot += 1
            issues.append({"level": "warn", "title": "فروش فاقد Snapshot", "detail": f"{code} / {line.product_size.size.name} · {format_jalali(line.day.date)}", "amount": None})
        if price <= 0:
            issues.append({"level": "danger", "title": "قیمت فروش صفر", "detail": f"{code} · {format_jalali(line.day.date)}", "amount": None})
            continue
        if is_campaign(line.day.date, pack):
            effective_fee = digikala_fee_for_unit(price, line.day.date, product_code=code, brand_name=brand, pack_qty=pack)
            if snap and int(snap.digikala_fee_unit or 0) != effective_fee:
                wrong_fee += 1
                issues.append({"level": "warn", "title": "کارمزد Snapshot قدیمی", "detail": f"{code} · {format_jalali(line.day.date)}", "amount": (effective_fee - int(snap.digikala_fee_unit)) * qty})
        else:
            # Outside V155, the historical snapshot is authoritative; current
            # app settings are not safe to retroactively impose on prior sales.
            effective_fee = int(snap.digikala_fee_unit) if snap and snap.digikala_fee_unit else digikala_fee_for_unit(
                price, line.day.date, product_code=code, brand_name=brand,
                pack_qty=pack,
            )
        expected_claim = (price - effective_fee) * qty
        entries = list(AccountEntry.objects.filter(
            reference=f"sale:{line.pk}:digikala", account__key="digikala",
            entry_type="sale"
        ).values_list("delta", flat=True))
        if len(entries) != 1 or int(entries[0]) != expected_claim:
            ledger_gap += 1
            current = sum(int(val) for val in entries)
            issues.append({"level": "danger", "title": "اختلاف سند طلب دیجی‌کالا", "detail": f"{code} · {format_jalali(line.day.date)} · ثبت: {current:,}", "amount": expected_claim - current})
    negative = StockBalance.objects.filter(qty__lt=0).count()
    if negative:
        issues.append({"level": "warn", "title": "موجودی منفی", "detail": f"{negative} ردیف موجودی منفی؛ ممکن است برای فروش مجاز باشد", "amount": None})
    return {
        "inspected": inspected, "missing_snapshot": missing_snapshot,
        "wrong_fee": wrong_fee, "ledger_gap": ledger_gap, "negative_stock": negative,
        "count": len(issues), "issues": issues[:limit], "hidden": max(0, len(issues) - limit),
        "start": format_jalali(start), "end": format_jalali(end),
    }


def _stock(today):
    from .models import TapsiStockAllocation
    since = today - timedelta(days=27)
    demand = defaultdict(int)
    # Physical units only, using recorded color/size stock allocations.
    darma_id = Brand.objects.filter(name="دارما").values_list("id", flat=True).first()
    anbaresh_id = Brand.objects.filter(name="انبارش").values_list("id", flat=True).first()
    for row in SaleAllocation.objects.filter(
        sale_line__day__date__gte=since, sale_line__day__date__lte=today,
    ).values("sale_line__product_size__product__brand_id", "sale_line__product_size__size_id", "color_id").annotate(total=Sum("qty")):
        brand_id = row["sale_line__product_size__product__brand_id"]
        # Anbaresh sales are physically deducted from Darma stock.
        if anbaresh_id and brand_id == anbaresh_id and darma_id:
            brand_id = darma_id
        key = (brand_id, row["sale_line__product_size__size_id"], row["color_id"])
        demand[key] += int(row["total"] or 0)
    # Dia physically consumes Darma stock. Count independently.
    if darma_id:
        for row in DiaGallerySale.objects.filter(
            day__date__gte=since, day__date__lte=today, quantity__gt=0
        ).values("size_id", "color_id").annotate(total=Sum("quantity")):
            demand[(darma_id, row["size_id"], row["color_id"])] += int(row["total"] or 0)
    for row in TapsiStockAllocation.objects.filter(
        item__order__day__date__gte=since, item__order__day__date__lte=today,
    ).values("brand_id", "size_id", "color_id").annotate(total=Sum("quantity")):
        demand[(row["brand_id"], row["size_id"], row["color_id"])] += int(row["total"] or 0)

    totals = defaultdict(lambda: {"home": 0, "khorshid": 0, "other": 0})
    labels = {}
    for row in StockBalance.objects.exclude(brand__name="انبارش").values(
        "brand_id", "size_id", "color_id", "brand__name",
        "size__name", "color__name", "location__key", "qty",
    ):
        key = (row["brand_id"], row["size_id"], row["color_id"])
        loc = row["location__key"]
        totals[key][loc if loc in ("home", "khorshid") else "other"] += int(row["qty"] or 0)
        labels[key] = f'{row["brand__name"]} · {row["color__name"]} · {row["size__name"]}'
    thresholds = {
        (r["brand_id"], r["size_id"], r["color_id"]): int(r["home_min"] or 0)
        for r in StockThreshold.objects.values("brand_id", "size_id", "color_id", "home_min")
    }
    risks = []
    for key, stock in totals.items():
        sold = demand.get(key, 0)
        daily = sold / 28
        cover = round(stock["home"] / daily, 1) if daily else None
        threshold = thresholds.get(key, 0)
        # Physical HOME, not KHORSHID: internal replenishment must be manual.
        urgent = stock["home"] < 0 or (sold > 0 and (cover is not None and cover < 14)) or (threshold > 0 and stock["home"] < threshold)
        if not urgent:
            continue
        risks.append({
            "label": labels[key], "home": stock["home"],
            "khorshid": stock["khorshid"], "sold": sold,
            "cover": cover, "threshold": threshold,
            "suggested": max(0, int(daily * 28 + 0.999) - max(0, stock["home"])),
            "level": "danger" if stock["home"] <= 0 else "warn",
        })
    risks.sort(key=lambda r: (r["home"] > 0, r["cover"] if r["cover"] is not None else -1, r["home"]))
    return {
        "risk_total": len(risks), "risk_rows": risks[:35],
        "risk_hidden": max(0, len(risks) - 35),
        "home_total": sum(x["home"] for x in totals.values()),
        "khorshid_total": sum(x["khorshid"] for x in totals.values()),
        "since": format_jalali(since), "until": format_jalali(today),
        "stock_rows": len(totals),
    }


def _cash(today):
    capital = _capital()
    since = today - timedelta(days=29)
    receipts = []
    for source, label in (
        (DigikalaSettlement.SOURCE_DIGIKALA, "دیجی‌کالا"),
        (DigikalaSettlement.SOURCE_TAPSI, "تپسی‌شاپ"),
        (DigikalaSettlement.SOURCE_DIA_GALLERY, "دیا گالری"),
    ):
        receipts.append({
            "label": label, "total": _amount(
                DigikalaSettlement.objects.filter(source=source, date__range=(since, today))
            ),
        })
    recent_outgoings = _amount(BusinessPayment.objects.filter(date__range=(since, today)))
    receipts_total = sum(row["total"] for row in receipts)
    recent_expenses = _amount(Expense.objects.filter(date__range=(since, today)))
    # Scenario, not a contractual due-date forecast; historical records don't
    # contain confirmed future settlement schedules.
    runrate_14 = round((receipts_total - recent_outgoings - recent_expenses) * 14 / 30)
    runrate_30 = receipts_total - recent_outgoings - recent_expenses
    return {
        "capital": capital, "receipts": receipts,
        "receipts_total": receipts_total,
        "outgoings": recent_outgoings, "expenses": recent_expenses,
        "scenario_14": runrate_14, "scenario_30": runrate_30,
        "since": format_jalali(since), "until": format_jalali(today),
    }


def _production(today):
    from .material_report_v23 import _reset_request_caches
    _reset_request_caches()
    blocks = list(MaterialReportBlock.objects.select_related("brand").prefetch_related(
        "stock_consumptions", "output_applications__location_allocations__location",
    ).all())
    result = build_overall_report(blocks)
    raw = _raw_material_context()
    from .tailor_ledger_v150 import live_tailor_balance
    outstanding = live_tailor_balance()
    return {
        "all": result["all"], "followups": result["followups"][:12],
        "followup_total": result["followup_total"],
        "materials": int(raw["materials_total"] or 0),
        "fabric_warehouse": int(raw["fabric_warehouse_total"] or 0),
        "fabric_tailor": int(raw["fabric_tailor_total"] or 0),
        "tailor_ledger_net": outstanding,
        "note": "مانده فعلی خیاط از ردیف مبنای حسابداری موجود خوانده شده؛ برای تفسیر علامت مثبت و منفی به دفتر خیاط رجوع کنید.",
    }


def _integrity(today):
    latest = []
    for row in AccountEntry.objects.select_related("account").order_by("-created_at")[:8]:
        latest.append({"when": row.created_at, "kind": "سند مالی", "detail": row.title,
                       "amount": row.delta})
    for row in InventoryMovement.objects.select_related("color", "size").order_by("-created_at")[:8]:
        latest.append({"when": row.created_at, "kind": "حرکت انبار",
                       "detail": f"{row.color.name} · {row.size.name} · {row.movement_type}",
                       "amount": row.delta})
    latest.sort(key=lambda row: row["when"], reverse=True)
    updated_manual = ExcelManualRow.objects.filter(active=True).order_by("-updated_at")[:8]
    return {
        "events": latest[:14], "manual_updates": updated_manual,
        "last_sale_date": SaleLine.objects.order_by("-day__date").values_list("day__date", flat=True).first(),
        "missing_snapshots": SaleLine.objects.filter(quantity__gt=0, snapshot__isnull=True).count(),
        "orphan_entries": AccountEntry.objects.filter(
            account__key=Account.DIGIKALA, entry_type="sale"
        ).exclude(reference__startswith="sale:").count(),
        "warnings": [
            "نویسندهٔ تغییرات تاریخی در همهٔ رکوردها ثبت نشده؛ نام و زمان ویرایش‌های قدیمی قابل بازسازی نیست.",
            "وضعیت بکاپ، زمان‌بندی تسویه و تاریخ دقیق سررسید بدهی‌ها از این جداول قابل تأیید نیست.",
            "تاریخچه سرمایه برای دوره‌های قدیمی ممکن است به علت بازنویسی داده‌های دستی کامل نباشد.",
        ],
    }


@login_required
@require_GET
def control_room(request):
    selected = request.GET.get("tab", "overview")
    tab = selected if selected in SECTIONS else "overview"
    today = timezone.localdate()

    # PostgreSQL hard-denies INSERT/UPDATE/DELETE from this endpoint, even
    # when a legacy helper unexpectedly attempts a write.
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")

        first, _ = _period(today)
        context = {
            "tab": tab, "nav": NAV,
            "today": format_jalali(today),
            "month_start": format_jalali(first),
            "read_only": True,
        }
        if tab == "overview":
            context["sales"] = _sales(first, today)
            context["capital"] = _capital()
            context["stock"] = _stock(today)
            context["audit"] = _audit(today - timedelta(days=29), today, limit=5)
        elif tab == "audit":
            context["audit"] = _audit(today - timedelta(days=89), today, limit=100)
        elif tab == "inventory":
            context["stock"] = _stock(today)
        elif tab == "profit":
            context["sales"] = _sales(first, today)
        elif tab == "cash":
            context["cash"] = _cash(today)
        elif tab == "production":
            context["production"] = _production(today)
        elif tab == "integrity":
            context["integrity"] = _integrity(today)

        return render(request, "core/control_room_v156.html", context)
