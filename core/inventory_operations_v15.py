from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .brand_colors import colors_for_brand
from .dateutils import format_jalali, parse_jalali_date
from .final_services import sync_inventory_adjustment, sync_stock_transfer
from .models import (
    Brand, Color, InventoryAdjustment, InventoryMovement, Size,
    StockBalance, StockLocation, StockTransfer,
)


INVENTORY_BRANDS = ("دارما", "تکوین", "Novani")


def _int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(str(value).replace(" ", "").replace(",", "").replace("٬", ""))
    except Exception:
        return default


def _date(value=None):
    return parse_jalali_date(value) if value else date.today()


@transaction.atomic
def _set_inventory_target(*, adjustment_date, brand, size, color, location, target_qty, note=""):
    """Set one stock cell to an absolute counted quantity using the existing adjustment ledger.

    InventoryAdjustment remains delta-based for audit/history. The UI/business input is
    absolute: delta is calculated as target_qty - current_qty under a row lock.
    """
    balance, _ = StockBalance.objects.get_or_create(
        brand=brand,
        size=size,
        color=color,
        location=location,
        defaults={"qty": 0},
    )
    balance = StockBalance.objects.select_for_update().get(pk=balance.pk)
    current_qty = int(balance.qty or 0)
    delta = int(target_qty) - current_qty
    if delta == 0:
        return {
            "adjustment": None,
            "before": current_qty,
            "after": current_qty,
            "delta": 0,
        }

    obj = InventoryAdjustment.objects.create(
        date=adjustment_date,
        brand=brand,
        size=size,
        color=color,
        location=location,
        delta=delta,
        note=note or "",
    )
    sync_inventory_adjustment(obj)
    return {
        "adjustment": obj,
        "before": current_qty,
        "after": int(target_qty),
        "delta": delta,
    }


@transaction.atomic
def _bulk_transfer_khorshid_to_home(*, transfer_date, brand, size, color_quantities):
    """Apply one form submission as multiple explicit KHORSHID -> HOME transfers.

    The existing StockTransfer model/service remains authoritative. Every non-zero
    color becomes its own StockTransfer row, while the full batch is atomic.
    """
    if brand.name != "دارما":
        raise ValueError("انتقال خانه/خورشید فقط برای دارما فعال است.")

    home = StockLocation.objects.get(key=StockLocation.HOME)
    khorshid = StockLocation.objects.get(key=StockLocation.KHORSHID)
    prepared = []

    for color, qty in color_quantities:
        qty = int(qty or 0)
        if qty <= 0:
            continue
        src, _ = StockBalance.objects.get_or_create(
            brand=brand,
            size=size,
            color=color,
            location=khorshid,
            defaults={"qty": 0},
        )
        src = StockBalance.objects.select_for_update().get(pk=src.pk)
        available = int(src.qty or 0)
        if available < qty:
            raise ValueError(
                f"{color.name}: موجودی خورشید کافی نیست. موجودی فعلی {available} عدد است، "
                f"ولی {qty} عدد برای انتقال وارد شده."
            )
        prepared.append((color, qty))

    if not prepared:
        raise ValueError("حداقل برای یک رنگ تعداد انتقال را وارد کن.")

    created = []
    total_qty = 0
    for color, qty in prepared:
        obj = StockTransfer.objects.create(
            date=transfer_date,
            brand=brand,
            size=size,
            color=color,
            qty=qty,
            from_location=khorshid,
            to_location=home,
            note="",
        )
        sync_stock_transfer(obj)
        created.append(obj)
        total_qty += qty

    return {"transfers": created, "total_qty": total_qty}


@login_required
def inventory_operations(request):
    brands = Brand.objects.filter(active=True, name__in=INVENTORY_BRANDS).order_by("id")
    transfer_brands = brands.filter(name="دارما")
    sizes = Size.objects.all()
    colors = Color.objects.filter(active=True)
    locations = StockLocation.objects.all()
    darma = transfer_brands.first()
    transfer_colors = colors_for_brand(darma) if darma else Color.objects.none()

    if request.method == "POST":
        try:
            action = request.POST.get("action")
            brand = Brand.objects.filter(
                id=request.POST.get("brand"),
                active=True,
                name__in=INVENTORY_BRANDS,
            ).first()
            if not brand:
                raise ValueError("برند موجودی معتبر نیست.")

            size = Size.objects.filter(id=request.POST.get("size")).first()
            if not size:
                raise ValueError("سایز معتبر نیست.")

            if action == "transfer":
                if brand.name != "دارما":
                    raise ValueError("انتقال خانه/خورشید فقط برای دارما فعال است.")
                brand_colors = list(colors_for_brand(brand))
                color_quantities = [
                    (color, max(0, _int(request.POST.get(f"qty_{color.id}"))))
                    for color in brand_colors
                ]
                result = _bulk_transfer_khorshid_to_home(
                    transfer_date=_date(request.POST.get("date")),
                    brand=brand,
                    size=size,
                    color_quantities=color_quantities,
                )
                messages.success(
                    request,
                    f"انتقال خورشید به خانه ثبت شد؛ {result['total_qty']} عدد در "
                    f"{len(result['transfers'])} رنگ منتقل شد.",
                )

            elif action == "adjust":
                color = Color.objects.filter(id=request.POST.get("color"), active=True).first()
                if not color:
                    raise ValueError("رنگ معتبر نیست.")

                location_id = request.POST.get("location")
                if brand.name == "Novani":
                    location = StockLocation.objects.get(key=StockLocation.HOME)
                else:
                    location = StockLocation.objects.filter(id=location_id).first()
                    if not location:
                        raise ValueError("محل موجودی معتبر نیست.")

                raw_target = request.POST.get("target_qty")
                if raw_target in (None, ""):
                    raise ValueError("موجودی اصلی را وارد کن.")
                target_qty = _int(raw_target, -1)
                if target_qty < 0:
                    raise ValueError("موجودی اصلی نمی‌تواند منفی باشد.")

                result = _set_inventory_target(
                    adjustment_date=_date(request.POST.get("date")),
                    brand=brand,
                    size=size,
                    color=color,
                    location=location,
                    target_qty=target_qty,
                    note=request.POST.get("note", ""),
                )
                if result["delta"] == 0:
                    messages.info(request, "موجودی همین مقدار است؛ تغییری ثبت نشد.")
                else:
                    messages.success(
                        request,
                        f"موجودی اصلی ثبت شد: {result['before']} ← {result['after']} عدد.",
                    )
            else:
                raise ValueError("نوع عملیات موجودی معتبر نیست.")

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
            "transfer_brands": transfer_brands,
            "transfer_colors": transfer_colors,
            "sizes": sizes,
            "colors": colors,
            "locations": locations,
            "recent": recent,
            "today_j": format_jalali(date.today()),
        },
    )
