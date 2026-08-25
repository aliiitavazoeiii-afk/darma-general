from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .dateutils import format_jalali, parse_jalali_date
from .final_services import sync_inventory_adjustment, sync_stock_transfer
from .models import (
    Brand, Color, InventoryAdjustment, InventoryMovement, Size,
    StockBalance, StockLocation, StockTransfer,
)


def _int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(str(value).replace(" ", "").replace(",", "").replace("٬", ""))
    except Exception:
        return default


def _date(value=None):
    return parse_jalali_date(value) if value else date.today()


@login_required
def inventory_operations(request):
    brands = Brand.objects.filter(active=True)
    sizes = Size.objects.all()
    colors = Color.objects.filter(active=True)
    locations = StockLocation.objects.all()

    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "transfer":
                brand_id = request.POST.get("brand")
                size_id = request.POST.get("size")
                color_id = request.POST.get("color")
                from_id = request.POST.get("from_location")
                to_id = request.POST.get("to_location")
                qty = max(1, _int(request.POST.get("qty"), 1))

                if from_id == to_id:
                    raise ValueError("مبدا و مقصد نمی‌تواند یکی باشد.")

                with transaction.atomic():
                    src, _ = StockBalance.objects.get_or_create(
                        brand_id=brand_id,
                        size_id=size_id,
                        color_id=color_id,
                        location_id=from_id,
                        defaults={"qty": 0},
                    )
                    src = StockBalance.objects.select_for_update().get(pk=src.pk)
                    available = int(src.qty or 0)
                    if available < qty:
                        raise ValueError(
                            f"موجودی مبدا کافی نیست. موجودی فعلی: {available} عدد، درخواست انتقال: {qty} عدد."
                        )

                    obj = StockTransfer.objects.create(
                        date=_date(request.POST.get("date")),
                        brand_id=brand_id,
                        size_id=size_id,
                        color_id=color_id,
                        qty=qty,
                        from_location_id=from_id,
                        to_location_id=to_id,
                        note=request.POST.get("note", ""),
                    )
                    sync_stock_transfer(obj)
                messages.success(request, "انتقال موجودی ثبت شد.")
            else:
                obj = InventoryAdjustment.objects.create(
                    date=_date(request.POST.get("date")),
                    brand_id=request.POST.get("brand"),
                    size_id=request.POST.get("size"),
                    color_id=request.POST.get("color"),
                    location_id=request.POST.get("location"),
                    delta=_int(request.POST.get("delta")),
                    note=request.POST.get("note", ""),
                )
                if obj.delta == 0:
                    obj.delete()
                    raise ValueError("مقدار اصلاح نمی‌تواند صفر باشد.")
                sync_inventory_adjustment(obj)
                messages.success(request, "اصلاح موجودی ثبت شد.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("inventory_operations")

    recent = InventoryMovement.objects.select_related(
        "brand", "size", "color", "location"
    ).order_by("-id")[:50]
    return render(
        request,
        "core/inventory_operations.html",
        {
            "brands": brands,
            "sizes": sizes,
            "colors": colors,
            "locations": locations,
            "recent": recent,
            "today_j": format_jalali(date.today()),
        },
    )
