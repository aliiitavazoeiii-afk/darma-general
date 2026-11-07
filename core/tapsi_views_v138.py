"""Django HTTP views for the Tapsi Shop daily-sale channel."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import SaleDay, TapsiOrder
from .tapsi_shop_v138 import create_tapsi_order, reverse_tapsi_order


@login_required
@require_POST
def order_create(request, day_id):
    day = get_object_or_404(SaleDay, pk=day_id)
    ids = request.POST.getlist("product_size_id")
    qtys = request.POST.getlist("quantity")
    if len(ids) != len(qtys) or not ids:
        messages.error(request, "محصول و تعداد هر قلم سفارش باید مشخص باشد.")
        return redirect(f"/sales/{day.pk}/report/#tapsi-shop")
    try:
        order = create_tapsi_order(
            day, list(zip(ids, qtys)),
            discount_cost=request.POST.get("discount_cost"),
            note=request.POST.get("note"),
        )
        messages.success(request, f"سفارش تپسی‌شاپ شماره {order.pk} ثبت شد؛ ارسال ۱۴۰٬۰۰۰ تومان فقط یک‌بار محاسبه شد.")
    except Exception as exc:
        messages.error(request, f"سفارش تپسی ثبت نشد و هیچ موجودی تغییر نکرد: {exc}")
    return redirect(f"/sales/{day.pk}/report/#tapsi-shop")


@login_required
@require_POST
def order_delete(request, day_id, order_id):
    day = get_object_or_404(SaleDay, pk=day_id)
    order = get_object_or_404(TapsiOrder, pk=order_id, day=day)
    try:
        reverse_tapsi_order(order)
        messages.success(request, "سفارش تپسی حذف شد؛ موجودی همان رنگ‌ها و سایزهای برداشت‌شده برگشت.")
    except Exception as exc:
        messages.error(request, f"حذف سفارش انجام نشد؛ هیچ موجودی به‌صورت ناقص تغییر نکرد: {exc}")
    return redirect(f"/sales/{day.pk}/report/#tapsi-shop")
