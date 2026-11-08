"""V142 standalone Tapsi workspace. No changes to original inventory/accounting services."""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .dateutils import format_jalali
from .models import SaleDay, TapsiOrder
from .tapsi_shop_v138 import (
    create_tapsi_order, current_catalog, reverse_tapsi_order,
    tapsi_day_summary, tapsi_receivable_total,
)


def _date(raw, *, default_today=False):
    if not raw and default_today:
        return timezone.localdate()
    try:
        selected = date.fromisoformat(str(raw))
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
            "commission": 0, "shipping": 0, "discount": 0,
            "fee": 0, "cogs": 0, "profit": 0,
        },
    }


@login_required
def home(request):
    """Viewing a date must not create a SaleDay or mutate any economic ledger."""
    try:
        on_date = _date(request.GET.get("date"), default_today=True)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    day = SaleDay.objects.filter(date=on_date).first()
    return render(request, "core/tapsi_shop_v142.html", {
        "on_date": on_date,
        "iso_date": on_date.isoformat(),
        "jalali_date": format_jalali(on_date),
        "is_today": on_date == timezone.localdate(),
        "prev_date": (on_date - timedelta(days=1)).isoformat(),
        "next_date": (on_date + timedelta(days=1)).isoformat(),
        "tapsi_catalog": current_catalog(on_date),
        "tapsi_summary": tapsi_day_summary(day) if day else _empty_summary(),
        "tapsi_receivable": tapsi_receivable_total(),
    })


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
