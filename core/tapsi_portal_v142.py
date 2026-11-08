"""V142 standalone Tapsi workspace. No changes to original inventory/accounting services."""
from datetime import date, timedelta

import jdatetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .dateutils import format_jalali, parse_jalali_date, normalize_digits
from .models import SaleDay, TapsiOrder, ProductSize
from .tapsi_shop_v138 import (
    create_tapsi_order, current_catalog, reverse_tapsi_order,
    tapsi_day_summary, tapsi_receivable_total, tapsi_period_metrics, product_unit_cost,
)


def _date(raw, *, default_today=False):
    if not raw and default_today:
        return timezone.localdate()
    value = normalize_digits(raw)
    try:
        selected = parse_jalali_date(value) if "/" in value else date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("تاریخ سفارش معتبر نیست.")
    if not 2000 <= selected.year <= 2100:
        raise ValueError("تاریخ سفارش خارج از محدوده مجاز است.")
    return selected


def _hub_url(on_date):
    return f"{reverse('tapsi_home')}?date={on_date.isoformat()}"


def _empty_summary():
    return {
        "rows": [],
        "total": {
            "orders": 0, "packs": 0, "shorts": 0, "gross": 0,
            "commission": 0, "vat": 0, "insurance": 0, "infrastructure": 0,
            "shipping": 0, "discount": 0,
            "fee": 0, "cogs": 0, "profit": 0,
        },
    }


def _month(raw, default_day):
    """Valid Persian year/month; invalid user input fails closed."""
    if not raw:
        selected = jdatetime.date.fromgregorian(date=default_day)
        return selected.year, selected.month
    value = normalize_digits(raw).replace("-", "/")
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError("ماه گزارش باید به صورت ۱۴۰۵/۰۸ باشد.")
    try:
        jy, jm = map(int, parts)
        if not 1300 <= jy <= 1500 or not 1 <= jm <= 12:
            raise ValueError
        jdatetime.date(jy, jm, 1)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("ماه گزارش شمسی معتبر نیست.")
    return jy, jm


def _month_report(raw_month, on_date):
    jy, jm = _month(raw_month, on_date)
    first_j = jdatetime.date(jy, jm, 1)
    next_j = jdatetime.date(jy + 1, 1, 1) if jm == 12 else jdatetime.date(jy, jm + 1, 1)
    first, last = first_j.togregorian(), next_j.togregorian() - timedelta(days=1)
    summary = tapsi_period_metrics(first, last)
    daily = [
        {
            "date": day,
            "date_iso": day.isoformat(),
            "jalali": format_jalali(day),
            **values,
        }
        for day, values in sorted(summary["by_date"].items(), reverse=True)
    ]
    prev_j = jdatetime.date(jy - 1, 12, 1) if jm == 1 else jdatetime.date(jy, jm - 1, 1)
    next_month = next_j
    from .jalali_calendar import PERSIAN_MONTHS
    return {
        "month_key": f"{jy:04d}/{jm:02d}",
        "month_title": f"{PERSIAN_MONTHS[jm - 1]} {jy}",
        "month_prev": f"{prev_j.year:04d}/{prev_j.month:02d}",
        "month_next": f"{next_month.year:04d}/{next_month.month:02d}",
        "month_start": first,
        "month_end": last,
        "total": summary["total"],
        "days": daily,
    }


def _calculator_catalog(on_date, catalog):
    """Read-only matching stock cost/pack for each selectable SKU/size."""
    ids = [int(size["id"]) for product in catalog for size in product["sizes"]]
    cost_by_id = {
        ps.pk: int(product_unit_cost(ps, on_date))
        for ps in ProductSize.objects.filter(pk__in=ids)
            .select_related("product__brand", "size")
    }
    return [{
        **product,
        "sizes": [
            {**size, "unit_cost": cost_by_id.get(int(size["id"]), 0)}
            for size in product["sizes"]
        ],
    } for product in catalog]


@login_required
def home(request):
    """Only daily orders, inventory and receivable; no heavy monthly UI."""
    try:
        on_date = _date(request.GET.get("date"), default_today=True)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    day = SaleDay.objects.filter(date=on_date).first()
    catalog = current_catalog(on_date)
    return render(request, "core/tapsi_shop_v142.html", {
        "on_date": on_date, "iso_date": on_date.isoformat(),
        "jalali_date": format_jalali(on_date),
        "is_today": on_date == timezone.localdate(),
        "prev_date": (on_date - timedelta(days=1)).isoformat(),
        "next_date": (on_date + timedelta(days=1)).isoformat(),
        "calc_catalog": _calculator_catalog(on_date, catalog),
        "tapsi_catalog": catalog,
        "tapsi_summary": tapsi_day_summary(day) if day else _empty_summary(),
        "tapsi_receivable": tapsi_receivable_total(),
    })


@login_required
def calculator(request):
    """Independent one-pack price quotation: no SKU search or database access."""
    return render(request, "core/tapsi_calculator_v144.html")


@login_required
def monthly(request):
    try:
        report = _month_report(request.GET.get("month"), timezone.localdate())
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    return render(request, "core/tapsi_monthly_v144.html", {"monthly": report})


@login_required
@require_POST
def create(request):
    try:
        on_date = _date(request.POST.get("order_date"))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("tapsi_home")
    ids = request.POST.getlist("product_size_id")
    quantities = request.POST.getlist("quantity")
    if not ids or len(ids) != len(quantities):
        messages.error(request, "حداقل یک کالا و تعداد معتبر برای سفارش انتخاب کن.")
        return redirect(_hub_url(on_date))
    try:
        # The date row is created ONLY with a successful order. Roll back the
        # new SaleDay as well when validation, stock posting or snapshots fail.
        with transaction.atomic():
            day, _ = SaleDay.objects.get_or_create(date=on_date)
            order = create_tapsi_order(
                day, list(zip(ids, quantities)),
                discount_cost=request.POST.get("discount_cost"),
                note=request.POST.get("note"),
            )
        messages.success(request, f"سفارش تپسی‌شاپ #{order.pk} ثبت شد؛ موجودی و سرمایه بر اساس منطق فعلی به‌روزرسانی شدند.")
    except (ValueError, RuntimeError) as exc:
        messages.error(request, f"سفارش ثبت نشد؛ هیچ تغییری در سفارش یا موجودی ذخیره نشد: {exc}")
    return redirect(_hub_url(on_date))


@login_required
@require_POST
def delete(request, order_id):
    order = get_object_or_404(TapsiOrder.objects.select_related("day"), pk=order_id)
    on_date = order.day.date
    try:
        reverse_tapsi_order(order)
        messages.success(request, f"سفارش #{order_id} حذف شد؛ موجودی دقیق و اثر سرمایه آن برگشت.")
    except (ValueError, RuntimeError) as exc:
        messages.error(request, f"حذف انجام نشد: {exc}")
    return redirect(_hub_url(on_date))
