from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .excel_views import DISPLAY_SIZES, _add_metrics, _decimal, _empty_metrics, _finish_metrics, _int, _period_range
from .finance import sale_line_metrics
from .models import (
    ExcelManualRow,
    ExcelManualSetting,
    InventoryModelCost,
    RawMaterialStock,
    SaleLine,
    StockBalance,
)
from .dateutils import format_jalali


def _finished_inventory_value():
    cost_map = {
        (row.brand_id, row.color_id, row.size_id): int(row.unit_cost or 0)
        for row in InventoryModelCost.objects.all()
    }
    total = 0
    grouped = StockBalance.objects.values("brand_id", "color_id", "size_id").annotate(qty=Sum("qty"))
    for row in grouped:
        unit_cost = cost_map.get((row["brand_id"], row["color_id"], row["size_id"]), 0)
        total += int(row["qty"] or 0) * unit_cost
    return total


def _raw_material_context():
    rows = list(RawMaterialStock.objects.filter(active=True).order_by("kind", "location", "id"))
    grouped = {
        RawMaterialStock.FABRIC: {RawMaterialStock.WAREHOUSE: [], RawMaterialStock.TAILOR: []},
        RawMaterialStock.ELASTIC: {RawMaterialStock.WAREHOUSE: [], RawMaterialStock.TAILOR: []},
    }
    totals = {
        RawMaterialStock.FABRIC: {RawMaterialStock.WAREHOUSE: 0, RawMaterialStock.TAILOR: 0},
        RawMaterialStock.ELASTIC: {RawMaterialStock.WAREHOUSE: 0, RawMaterialStock.TAILOR: 0},
    }
    for row in rows:
        grouped[row.kind][row.location].append(row)
        totals[row.kind][row.location] += row.total_value

    fabric_total = totals[RawMaterialStock.FABRIC][RawMaterialStock.WAREHOUSE] + totals[RawMaterialStock.FABRIC][RawMaterialStock.TAILOR]
    elastic_total = totals[RawMaterialStock.ELASTIC][RawMaterialStock.WAREHOUSE] + totals[RawMaterialStock.ELASTIC][RawMaterialStock.TAILOR]
    return grouped, totals, fabric_total, elastic_total, fabric_total + elastic_total


@login_required
def report(request):
    period, start, end = _period_range(request)
    lines = list(
        SaleLine.objects.filter(day__date__gte=start, day__date__lte=end, quantity__gt=0)
        .select_related("day", "product_size__product__brand", "product_size__product", "product_size__size")
        .prefetch_related("product_size__product__composition__color")
    )

    brand_totals = defaultdict(_empty_metrics)
    brand_sizes = defaultdict(lambda: defaultdict(_empty_metrics))
    product_profit = defaultdict(lambda: defaultdict(int))
    color_sales = defaultdict(lambda: defaultdict(int))
    overall = _empty_metrics()

    for line in lines:
        metrics = sale_line_metrics(line)
        brand = line.product_size.product.brand.name
        size = line.product_size.size.name
        _add_metrics(brand_totals[brand], metrics)
        _add_metrics(brand_sizes[brand][size], metrics)
        _add_metrics(overall, metrics)
        if brand == "دارما":
            product_profit[line.product_size.product.code][size] += metrics["profit"]
            for comp in line.product_size.product.composition.all():
                color_sales[comp.color.name][size] += int(line.quantity) * int(comp.qty)

    for values in brand_totals.values():
        _finish_metrics(values)
    for size_map in brand_sizes.values():
        for values in size_map.values():
            _finish_metrics(values)
    _finish_metrics(overall)

    brands_view = []
    for brand_name in ["تکوین", "دارما"]:
        sizes = ["M", "L", "XL", "XXL"] if brand_name == "تکوین" else DISPLAY_SIZES
        brands_view.append({
            "name": brand_name,
            "total": brand_totals[brand_name],
            "sizes": [(size, brand_sizes[brand_name][size]) for size in sizes],
        })

    product_rows = []
    for code, values in sorted(product_profit.items()):
        cells = [values.get(size, 0) for size in DISPLAY_SIZES]
        product_rows.append({"code": code, "cells": cells, "total": sum(cells)})
    product_rows.sort(key=lambda row: row["total"], reverse=True)

    color_rows = []
    for color, values in color_sales.items():
        cells = [values.get(size, 0) for size in DISPLAY_SIZES]
        color_rows.append({"color": color, "cells": cells, "total": sum(cells)})
    color_rows.sort(key=lambda row: row["total"], reverse=True)

    manual_rows = ExcelManualRow.objects.filter(active=True)
    accounts_rows = list(manual_rows.filter(section=ExcelManualRow.ACCOUNTS).order_by("sort_order", "id"))
    person_rows = list(manual_rows.filter(section=ExcelManualRow.PERSONS).order_by("sort_order", "id"))
    asset_rows = list(manual_rows.filter(section=ExcelManualRow.ASSETS).order_by("sort_order", "id"))

    settings = {obj.key: obj for obj in ExcelManualSetting.objects.all()}
    takvin_debt = settings.get("takvin_debt").value if settings.get("takvin_debt") else 0
    digikala_receivable = settings.get("digikala_receivable").value if settings.get("digikala_receivable") else 0

    accounts_total = sum(row.amount for row in accounts_rows) + sum(row.amount for row in person_rows)
    assets_total = sum(row.amount for row in asset_rows)
    finished_inventory_total = _finished_inventory_value()
    raw_groups, raw_totals, fabric_total, elastic_total, materials_total = _raw_material_context()
    inventory_total = finished_inventory_total + materials_total
    capital_total = accounts_total + inventory_total + digikala_receivable - takvin_debt

    return render(request, "core/report_excel_v2.html", {
        "period": period,
        "start": format_jalali(start),
        "end": format_jalali(end),
        "overall": overall,
        "brands": brands_view,
        "display_sizes": DISPLAY_SIZES,
        "product_rows": product_rows,
        "color_rows": color_rows,
        "accounts_rows": accounts_rows,
        "person_rows": person_rows,
        "asset_rows": asset_rows,
        "accounts_total": accounts_total,
        "assets_total": assets_total,
        "finished_inventory_total": finished_inventory_total,
        "materials_total": materials_total,
        "fabric_total": fabric_total,
        "elastic_total": elastic_total,
        "inventory_total": inventory_total,
        "capital_total": capital_total,
        "takvin_debt": takvin_debt,
        "digikala_receivable": digikala_receivable,
        "fabric_warehouse": raw_groups[RawMaterialStock.FABRIC][RawMaterialStock.WAREHOUSE],
        "fabric_tailor": raw_groups[RawMaterialStock.FABRIC][RawMaterialStock.TAILOR],
        "elastic_warehouse": raw_groups[RawMaterialStock.ELASTIC][RawMaterialStock.WAREHOUSE],
        "elastic_tailor": raw_groups[RawMaterialStock.ELASTIC][RawMaterialStock.TAILOR],
        "fabric_warehouse_total": raw_totals[RawMaterialStock.FABRIC][RawMaterialStock.WAREHOUSE],
        "fabric_tailor_total": raw_totals[RawMaterialStock.FABRIC][RawMaterialStock.TAILOR],
        "elastic_warehouse_total": raw_totals[RawMaterialStock.ELASTIC][RawMaterialStock.WAREHOUSE],
        "elastic_tailor_total": raw_totals[RawMaterialStock.ELASTIC][RawMaterialStock.TAILOR],
    })


@login_required
@require_POST
def manual_report_action(request):
    action = request.POST.get("action")
    try:
        if action == "setting":
            key = request.POST.get("key")
            labels = {"takvin_debt": "بدهی تکوین", "digikala_receivable": "طلب دیجی‌کالا"}
            if key not in labels:
                raise ValueError("فیلد ناشناخته است.")
            obj, _ = ExcelManualSetting.objects.get_or_create(key=key, defaults={"label": labels[key]})
            obj.value = _int(request.POST.get("value"))
            obj.label = labels[key]
            obj.save(update_fields=["value", "label", "updated_at"])

        elif action in {"save_row", "add_row", "delete_row"}:
            allowed_sections = {ExcelManualRow.ACCOUNTS, ExcelManualRow.PERSONS, ExcelManualRow.ASSETS}
            if action == "save_row":
                row = get_object_or_404(ExcelManualRow, id=request.POST.get("id"), section__in=allowed_sections)
                row.title = (request.POST.get("title") or row.title).strip()
                row.amount = _int(request.POST.get("amount"))
                row.note = (request.POST.get("note") or "").strip()
                row.save()
            elif action == "add_row":
                section = request.POST.get("section")
                if section not in allowed_sections:
                    raise ValueError("این بخش دیگر ورود دستی ندارد.")
                title = (request.POST.get("title") or "ردیف جدید").strip()
                order = ExcelManualRow.objects.filter(section=section).aggregate(v=Sum("sort_order"))["v"] or 0
                ExcelManualRow.objects.create(section=section, title=title, sort_order=order + 1)
            else:
                ExcelManualRow.objects.filter(id=request.POST.get("id"), section__in=allowed_sections).delete()

        elif action in {"raw_add", "raw_save", "raw_delete"}:
            if action == "raw_delete":
                RawMaterialStock.objects.filter(id=request.POST.get("id")).delete()
            else:
                kind = request.POST.get("kind")
                location = request.POST.get("location")
                if kind not in {RawMaterialStock.FABRIC, RawMaterialStock.ELASTIC}:
                    raise ValueError("نوع ماده اولیه معتبر نیست.")
                if location not in {RawMaterialStock.WAREHOUSE, RawMaterialStock.TAILOR}:
                    raise ValueError("محل موجودی معتبر نیست.")
                title = (request.POST.get("title") or "").strip()
                if not title:
                    raise ValueError("نام/رنگ را وارد کن.")
                quantity = _decimal(request.POST.get("quantity"))
                unit_price = _int(request.POST.get("unit_price"))
                if quantity < 0 or unit_price < 0:
                    raise ValueError("مقدار و فی نمی‌توانند منفی باشند.")
                if action == "raw_add":
                    RawMaterialStock.objects.create(
                        kind=kind,
                        location=location,
                        title=title,
                        quantity=quantity,
                        unit_price=unit_price,
                        unit=(request.POST.get("unit") or "کیلو").strip(),
                        note=(request.POST.get("note") or "").strip(),
                    )
                else:
                    row = get_object_or_404(RawMaterialStock, id=request.POST.get("id"))
                    row.kind = kind
                    row.location = location
                    row.title = title
                    row.quantity = quantity
                    row.unit_price = unit_price
                    row.unit = (request.POST.get("unit") or "کیلو").strip()
                    row.note = (request.POST.get("note") or "").strip()
                    row.save()
        else:
            raise ValueError("عملیات نامعتبر است.")
        messages.success(request, "ذخیره شد.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("report")
