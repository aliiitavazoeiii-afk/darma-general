from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from .dateutils import format_jalali, parse_jalali_date
from .models import Color, Size, TakvinPurchase

PREFIX = "[excel-web]"
SIZE_DEFAULTS = [("M", 120000), ("L", 140000), ("XL", 155000), ("XXL", 170000)]
COLOR_NAMES = [
    "طوسی راه راه",
    "زرد",
    "بنفش",
    "طوسی",
    "سرمه‌ای",
    "سفید",
    "چرک روشن",
    "مشکی",
    "راه راه بنفش",
    "راه راه سفید مشکی",
    "راه راه زرد",
]


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


def _masters():
    sizes = []
    for name, default_price in SIZE_DEFAULTS:
        size, _ = Size.objects.get_or_create(name=name)
        sizes.append({"obj": size, "name": name, "default_price": default_price})
    colors = []
    for name in COLOR_NAMES:
        color, _ = Color.objects.get_or_create(name=name)
        colors.append(color)
    return sizes, colors


def _clean_note(note):
    raw = note or ""
    if raw.startswith(PREFIX):
        raw = raw[len(PREFIX):].strip()
    return raw


@login_required
@transaction.atomic
def takvin_excel(request):
    sizes, colors = _masters()
    selected_text = request.GET.get("date") or format_jalali(__import__("datetime").date.today())
    try:
        selected_date = parse_jalali_date(selected_text)
    except ValueError:
        selected_date = __import__("datetime").date.today()
        selected_text = format_jalali(selected_date)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            post_date_text = request.POST.get("date") or selected_text
            post_date = parse_jalali_date(post_date_text)
            if action == "delete_day":
                TakvinPurchase.objects.filter(date=post_date, note__startswith=PREFIX).delete()
                messages.success(request, "خرید تکوین این روز حذف شد.")
                return redirect("takvin")

            discount = _decimal(request.POST.get("discount_percent"), "10")
            if discount < 0 or discount > 100:
                raise ValueError("درصد تخفیف باید بین صفر تا ۱۰۰ باشد.")
            user_note = (request.POST.get("note") or "").strip()
            prices = {
                item["obj"].id: max(0, _int(request.POST.get(f"price_{item['obj'].id}"), item["default_price"]))
                for item in sizes
            }

            TakvinPurchase.objects.filter(date=post_date, note__startswith=PREFIX).delete()
            created = 0
            for color in colors:
                for item in sizes:
                    size = item["obj"]
                    qty = max(0, _int(request.POST.get(f"qty_{color.id}_{size.id}")))
                    if not qty:
                        continue
                    list_price = prices[size.id]
                    net_price = int(
                        (Decimal(list_price) * (Decimal("1") - discount / Decimal("100"))).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    )
                    TakvinPurchase.objects.create(
                        date=post_date,
                        size=size,
                        color=color,
                        qty=qty,
                        list_unit_price=list_price,
                        discount_percent=discount,
                        net_unit_price=net_price,
                        total_cost=qty * net_price,
                        note=f"{PREFIX} {user_note}".strip(),
                        applied=True,
                    )
                    created += 1
            if not created:
                raise ValueError("حداقل یک تعداد خرید وارد کن.")
            messages.success(request, "خرید تکوین ذخیره شد. این ثبت فقط گزارش خرید است و حساب‌ها/موجودی را خودکار تغییر نمی‌دهد.")
            return redirect(f"/takvin/?date={format_jalali(post_date)}")
        except Exception as exc:
            messages.error(request, str(exc))
            selected_text = request.POST.get("date") or selected_text
            try:
                selected_date = parse_jalali_date(selected_text)
            except ValueError:
                pass

    existing = list(
        TakvinPurchase.objects.filter(date=selected_date, note__startswith=PREFIX)
        .select_related("size", "color")
        .order_by("color__name", "size__sort_order")
    )
    qty_map = {(row.color_id, row.size_id): row.qty for row in existing}
    saved_prices = {}
    for row in existing:
        saved_prices.setdefault(row.size_id, row.list_unit_price)
    discount_value = existing[0].discount_percent if existing else Decimal("10")
    note_value = _clean_note(existing[0].note) if existing else ""

    grid_rows = []
    for color in colors:
        grid_rows.append(
            {
                "color": color,
                "cells": [
                    {
                        "size": item["obj"],
                        "name": f"qty_{color.id}_{item['obj'].id}",
                        "value": qty_map.get((color.id, item["obj"].id), 0),
                    }
                    for item in sizes
                ],
            }
        )

    size_rows = []
    for item in sizes:
        size = item["obj"]
        qty_total = sum(row.qty for row in existing if row.size_id == size.id)
        list_price = saved_prices.get(size.id, item["default_price"])
        before_discount = qty_total * list_price
        net_total = sum(row.total_cost for row in existing if row.size_id == size.id)
        size_rows.append(
            {
                "obj": size,
                "name": item["name"],
                "price": list_price,
                "qty": qty_total,
                "before": before_discount,
                "net": net_total,
            }
        )

    day_total_qty = sum(row.qty for row in existing)
    day_before = sum(row.qty * row.list_unit_price for row in existing)
    day_net = sum(row.total_cost for row in existing)

    history_rows = []
    grouped = defaultdict(lambda: {"qty": 0, "before": 0, "net": 0})
    history_qs = (
        TakvinPurchase.objects.filter(note__startswith=PREFIX)
        .order_by("-date", "-id")[:600]
    )
    for row in history_qs:
        data = grouped[row.date]
        data["qty"] += row.qty
        data["before"] += row.qty * row.list_unit_price
        data["net"] += row.total_cost
    for day, data in sorted(grouped.items(), reverse=True)[:30]:
        history_rows.append({"date": day, "jalali": format_jalali(day), **data})

    return render(
        request,
        "core/takvin_excel.html",
        {
            "selected_date": selected_text,
            "sizes": sizes,
            "grid_rows": grid_rows,
            "size_rows": size_rows,
            "discount_value": discount_value,
            "note_value": note_value,
            "day_total_qty": day_total_qty,
            "day_before": day_before,
            "day_net": day_net,
            "history_rows": history_rows,
        },
    )
