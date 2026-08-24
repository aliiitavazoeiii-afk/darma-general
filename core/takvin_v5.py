from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from .brand_colors import TAKVIN_COLORS
from .dateutils import format_jalali, parse_jalali_date
from .models import Color, ExcelManualSetting, Size, TakvinPurchase

PREFIX = "[excel-web]"
SIZE_DEFAULTS = [("M", 120000), ("L", 140000), ("XL", 155000), ("XXL", 170000)]


def _int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(str(value).replace(" ", "").replace(",", "").replace("٬", "").strip())
    except (TypeError, ValueError):
        return default


def _decimal(value, default="10"):
    try:
        if value in (None, ""):
            return Decimal(default)
        return Decimal(str(value).replace("٫", ".").replace(",", ".").strip())
    except Exception:
        return Decimal(default)


def _debt_setting():
    obj, _ = ExcelManualSetting.objects.get_or_create(key="takvin_debt", defaults={"label": "بدهی تکوین", "value": 0})
    return obj


def _masters():
    sizes = []
    for order, (name, default_price) in enumerate(SIZE_DEFAULTS):
        size, _ = Size.objects.get_or_create(name=name, defaults={"sort_order": order})
        sizes.append({"obj": size, "name": name, "default_price": default_price})
    colors = []
    for name in TAKVIN_COLORS:
        color, _ = Color.objects.get_or_create(name=name, defaults={"active": True})
        colors.append(color)
    return sizes, colors


def _clean_note(note):
    raw = note or ""
    return raw[len(PREFIX):].strip() if raw.startswith(PREFIX) else raw


@login_required
def takvin_excel(request):
    sizes, colors = _masters()
    selected_text = request.GET.get("date") or format_jalali(date.today())
    try:
        selected_date = parse_jalali_date(selected_text)
    except ValueError:
        selected_date = date.today(); selected_text = format_jalali(selected_date)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            post_date = parse_jalali_date(request.POST.get("date") or selected_text)
            old_total = int(TakvinPurchase.objects.filter(date=post_date, note__startswith=PREFIX).aggregate(v=Sum("total_cost"))["v"] or 0)
            if action == "delete_day":
                with transaction.atomic():
                    TakvinPurchase.objects.filter(date=post_date, note__startswith=PREFIX).delete()
                    debt = _debt_setting(); debt.value = int(debt.value or 0) - old_total; debt.save(update_fields=["value", "updated_at"])
                messages.success(request, "خرید تکوین این روز حذف شد و بدهی تکوین هم اصلاح شد.")
                return redirect("takvin")

            discount = _decimal(request.POST.get("discount_percent"), "10")
            if discount < 0 or discount > 100:
                raise ValueError("درصد تخفیف باید بین صفر تا ۱۰۰ باشد.")
            user_note = (request.POST.get("note") or "").strip()
            prices = {item["obj"].id: max(0, _int(request.POST.get(f"price_{item['obj'].id}"), item["default_price"])) for item in sizes}
            pending = []
            new_total = 0
            for color in colors:
                for item in sizes:
                    size = item["obj"]
                    qty = max(0, _int(request.POST.get(f"qty_{color.id}_{size.id}")))
                    if not qty:
                        continue
                    list_price = prices[size.id]
                    net_price = int((Decimal(list_price) * (Decimal("1") - discount / Decimal("100"))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    pending.append((color, size, qty, list_price, net_price))
                    new_total += qty * net_price
            if not pending:
                raise ValueError("حداقل یک تعداد خرید وارد کن؛ برای پاک‌کردن روز از دکمه حذف استفاده کن.")

            with transaction.atomic():
                TakvinPurchase.objects.filter(date=post_date, note__startswith=PREFIX).delete()
                for color, size, qty, list_price, net_price in pending:
                    TakvinPurchase.objects.create(
                        date=post_date, size=size, color=color, qty=qty, list_unit_price=list_price,
                        discount_percent=discount, net_unit_price=net_price, total_cost=qty * net_price,
                        note=f"{PREFIX} {user_note}".strip(), applied=True,
                    )
                debt = _debt_setting(); debt.value = int(debt.value or 0) + (new_total - old_total); debt.save(update_fields=["value", "updated_at"])
            messages.success(request, "خرید تکوین ذخیره شد و مبلغ خالص به بدهی تکوین اضافه شد.")
            return redirect(f"/takvin/?date={format_jalali(post_date)}")
        except Exception as exc:
            messages.error(request, str(exc))
            selected_text = request.POST.get("date") or selected_text
            try:
                selected_date = parse_jalali_date(selected_text)
            except ValueError:
                selected_date = date.today(); selected_text = format_jalali(selected_date)

    existing = list(TakvinPurchase.objects.filter(date=selected_date, note__startswith=PREFIX).select_related("size", "color").order_by("color__name", "size__sort_order"))
    qty_map = {(r.color_id, r.size_id): r.qty for r in existing}
    saved_prices = {}
    for row in existing: saved_prices.setdefault(row.size_id, row.list_unit_price)
    discount_value = existing[0].discount_percent if existing else Decimal("10")
    note_value = _clean_note(existing[0].note) if existing else ""
    grid_rows = [{"color": color, "cells": [{"size": item["obj"], "name": f"qty_{color.id}_{item['obj'].id}", "value": qty_map.get((color.id, item["obj"].id), 0)} for item in sizes]} for color in colors]
    size_rows = []
    for item in sizes:
        size = item["obj"]
        qty_total = sum(r.qty for r in existing if r.size_id == size.id)
        list_price = saved_prices.get(size.id, item["default_price"])
        size_rows.append({"obj": size, "name": item["name"], "price": list_price, "qty": qty_total, "before": qty_total * list_price, "net": sum(r.total_cost for r in existing if r.size_id == size.id)})
    grouped = defaultdict(lambda: {"qty": 0, "before": 0, "net": 0})
    for row in TakvinPurchase.objects.filter(note__startswith=PREFIX).order_by("-date", "-id")[:600]:
        data = grouped[row.date]; data["qty"] += row.qty; data["before"] += row.qty * row.list_unit_price; data["net"] += row.total_cost
    history_rows = [{"date": d, "jalali": format_jalali(d), **data} for d, data in sorted(grouped.items(), reverse=True)[:30]]
    return render(request, "core/takvin_excel.html", {
        "selected_date": selected_text, "sizes": sizes, "grid_rows": grid_rows, "size_rows": size_rows,
        "discount_value": discount_value, "note_value": note_value,
        "day_total_qty": sum(r.qty for r in existing),
        "day_before": sum(r.qty * r.list_unit_price for r in existing),
        "day_net": sum(r.total_cost for r in existing), "history_rows": history_rows,
        "takvin_debt": int(_debt_setting().value or 0),
    })
