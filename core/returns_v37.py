from datetime import date
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .dateutils import format_jalali, parse_jalali_date
from .final_services import sync_inventory_adjustment
from .inventory_valuation_v17 import finished_inventory_value_v17
from .models import Brand, Color, InventoryAdjustment, ProductComposition, ProductSize, Size, StockLocation

RETURN_BRANDS = ("دارما", "تکوین")
SIZE_MAP = {
    "دارما": ("M", "L", "XL", "XXL", "3XL", "4XL"),
    "تکوین": ("M", "L", "XL", "XXL"),
}
NOTE_PREFIX = "[standalone-return-v37]"


def _int(value):
    try:
        return max(0, int(str(value or "0").replace(",", "").replace("٬", "").strip()))
    except (TypeError, ValueError):
        return 0


def _selected_brand(brand_name):
    if brand_name not in RETURN_BRANDS:
        return None
    return Brand.objects.filter(name=brand_name, active=True).first()


def _sizes_for_brand(brand):
    if not brand:
        return []
    return list(Size.objects.filter(name__in=SIZE_MAP[brand.name]).order_by("sort_order", "id"))


def _colors_for_brand(brand):
    if not brand:
        return []
    color_ids = set(
        ProductComposition.objects.filter(
            product__brand=brand,
            product__active=True,
        ).values_list("color_id", flat=True)
    )
    return list(Color.objects.filter(id__in=color_ids, active=True).order_by("id"))


def _products_for(brand, size):
    if not brand or not size:
        return []
    rows = []
    qs = (
        ProductSize.objects.filter(
            product__brand=brand,
            product__active=True,
            active=True,
            size=size,
        )
        .select_related("product", "size")
        .prefetch_related("product__composition__color")
        .order_by("product__code", "id")
    )
    for ps in qs:
        comps = list(ps.product.composition.all())
        comp_total = sum(int(c.qty or 0) for c in comps)
        fixed = bool(comps) and comp_total == int(ps.product.pack_qty or 0)
        rows.append({
            "ps": ps,
            "code": ps.product.code,
            "pack_qty": int(ps.product.pack_qty or 0),
            "fixed": fixed,
        })
    return rows


def _create_adjustment(*, when, brand, size, color, qty, group, source):
    home = StockLocation.objects.get(key=StockLocation.HOME)
    obj = InventoryAdjustment.objects.create(
        date=when,
        brand=brand,
        size=size,
        color=color,
        location=home,
        delta=int(qty),
        note=f"{NOTE_PREFIX} group={group} {source}",
    )
    sync_inventory_adjustment(obj)
    return obj


def _apply_color_batch(*, when, brand, size, entries):
    allowed = {c.id: c for c in _colors_for_brand(brand)}
    group = uuid4().hex[:12]
    shorts_total = 0
    for color, qty in entries:
        qty = _int(qty)
        if not qty:
            continue
        if color.id not in allowed:
            raise ValueError("این رنگ برای برند انتخاب‌شده معتبر نیست.")
        _create_adjustment(
            when=when, brand=brand, size=size, color=color, qty=qty,
            group=group, source=f"color={color.id}",
        )
        shorts_total += qty
    if shorts_total <= 0:
        raise ValueError("حداقل یک تعداد وارد کن.")
    return {"shorts": shorts_total, "group": group}


def _apply_code_batch(*, when, brand, size, entries):
    allowed = {row["ps"].id: row for row in _products_for(brand, size)}
    group = uuid4().hex[:12]
    shorts_total = 0
    for product_size, packs in entries:
        packs = _int(packs)
        if not packs:
            continue
        row = allowed.get(product_size.id)
        if not row:
            raise ValueError("این کد برای برند/سایز انتخاب‌شده معتبر نیست.")
        if not row["fixed"]:
            raise ValueError(f"کد {row['code']} ترکیب رنگ ثابت ندارد؛ آن را از مسیر «بر اساس رنگ» ثبت کن.")
        components = list(product_size.product.composition.select_related("color").all())
        component_total = 0
        for comp in components:
            units = packs * int(comp.qty or 0)
            if not units:
                continue
            _create_adjustment(
                when=when, brand=brand, size=size, color=comp.color, qty=units,
                group=group, source=f"code={row['code']} ps={product_size.id} packs={packs}",
            )
            component_total += units
        expected = packs * int(row["pack_qty"])
        if component_total != expected:
            raise ValueError(f"ترکیب کد {row['code']} با تعداد پک همخوان نیست؛ عملیات کامل برگشت.")
        shorts_total += component_total
    if shorts_total <= 0:
        raise ValueError("حداقل یک تعداد وارد کن.")
    return {"shorts": shorts_total, "group": group}


@login_required
def returns_home(request):
    mode = (request.GET.get("mode") or "").strip().lower()
    if mode not in {"color", "code"}:
        mode = ""

    brand_name = (request.GET.get("brand") or "").strip()
    brand = _selected_brand(brand_name)
    sizes = _sizes_for_brand(brand)

    size = None
    size_name = (request.GET.get("size") or "").strip()
    if brand and size_name in SIZE_MAP[brand.name]:
        size = Size.objects.filter(name=size_name).first()

    colors = _colors_for_brand(brand) if mode == "color" and brand and size else []
    products = _products_for(brand, size) if mode == "code" and brand and size else []

    return render(request, "core/returns_v37.html", {
        "mode": mode,
        "brand": brand,
        "brands": [b for name in RETURN_BRANDS if (b := _selected_brand(name))],
        "sizes": sizes,
        "size": size,
        "colors": colors,
        "products": products,
        "today_j": format_jalali(date.today()),
    })


@login_required
@require_POST
def return_apply(request):
    mode = (request.POST.get("mode") or "").strip().lower()
    brand = _selected_brand((request.POST.get("brand") or "").strip())
    size_name = (request.POST.get("size") or "").strip()
    if mode not in {"color", "code"} or not brand or size_name not in SIZE_MAP[brand.name]:
        messages.error(request, "مسیر مرجوعی معتبر نیست.")
        return redirect("returns")

    size = Size.objects.filter(name=size_name).first()
    if not size:
        messages.error(request, "سایز معتبر نیست.")
        return redirect("returns")

    try:
        when = parse_jalali_date(request.POST.get("date") or format_jalali(date.today()))
        before_value = int(finished_inventory_value_v17())
        with transaction.atomic():
            if mode == "color":
                allowed = {c.id: c for c in _colors_for_brand(brand)}
                entries = []
                for key, value in request.POST.items():
                    if not key.startswith("qty_color_") or not _int(value):
                        continue
                    try:
                        color_id = int(key.removeprefix("qty_color_"))
                    except ValueError:
                        raise ValueError("شناسه رنگ نامعتبر است.")
                    color = allowed.get(color_id)
                    if not color:
                        raise ValueError("این رنگ برای برند انتخاب‌شده معتبر نیست.")
                    entries.append((color, value))
                result = _apply_color_batch(when=when, brand=brand, size=size, entries=entries)
            else:
                allowed = {row["ps"].id: row for row in _products_for(brand, size)}
                entries = []
                for key, value in request.POST.items():
                    if not key.startswith("qty_code_") or not _int(value):
                        continue
                    try:
                        ps_id = int(key.removeprefix("qty_code_"))
                    except ValueError:
                        raise ValueError("شناسه کد نامعتبر است.")
                    row = allowed.get(ps_id)
                    if not row:
                        raise ValueError("این کد برای برند/سایز انتخاب‌شده معتبر نیست.")
                    entries.append((row["ps"], value))
                result = _apply_code_batch(when=when, brand=brand, size=size, entries=entries)

            after_value = int(finished_inventory_value_v17())
            value_delta = after_value - before_value
            if value_delta <= 0:
                raise ValueError("ارزش موجودی با مرجوعی افزایش پیدا نکرد؛ برای جلوگیری از ثبت ناقص عملیات برگشت خورد.")

        messages.success(
            request,
            f"مرجوعی ثبت شد: {result['shorts']:,} شورت فقط به موجودی خانه {brand.name} اضافه شد؛ "
            f"ارزش موجودی/سرمایه {value_delta:,} تومان افزایش یافت. فروش، سود، دیجی، طلب دیجی و حساب‌ها تغییر نکردند.",
        )
    except Exception as exc:
        messages.error(request, f"مرجوعی اعمال نشد و کل عملیات برگشت: {exc}")

    return redirect(f"/returns/?mode={mode}&brand={brand.name}&size={size.name}")
