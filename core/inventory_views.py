from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Brand, Color, ProductComposition, Size, StockBalance, StockLocation


def _sizes_for_brand(brand):
    qs = Size.objects.all().order_by("sort_order", "id")
    if brand and brand.name == "تکوین":
        qs = qs.exclude(name__in=["3XL", "4XL"])
    return list(qs)


@login_required
def inventory(request):
    brands = Brand.objects.filter(active=True)
    brand = brands.filter(id=request.GET.get("brand")).first() if request.GET.get("brand") else brands.filter(name="دارما").first() or brands.first()
    sizes = _sizes_for_brand(brand)
    rows = []

    if brand:
        color_ids = set(StockBalance.objects.filter(brand=brand).values_list("color_id", flat=True))
        color_ids.update(ProductComposition.objects.filter(product__brand=brand).values_list("color_id", flat=True))
        colors = Color.objects.filter(active=True, id__in=color_ids).order_by("id")

        for color in colors:
            cells = []
            for size in sizes:
                qs = StockBalance.objects.filter(brand=brand, size=size, color=color)
                home = qs.filter(location__key=StockLocation.HOME).aggregate(v=Sum("qty"))["v"] or 0
                kh = qs.filter(location__key=StockLocation.KHORSHID).aggregate(v=Sum("qty"))["v"] or 0
                cells.append({"size": size, "home": home, "kh": kh, "total": home + kh})
            rows.append({"color": color, "cells": cells})

    return render(request, "core/inventory_final.html", {"brands": brands, "brand": brand, "sizes": sizes, "rows": rows})


@login_required
@require_POST
def add_color_model(request):
    name = (request.POST.get("name") or "").strip()
    code = (request.POST.get("code") or "").strip()
    brand_id = (request.POST.get("brand") or "").strip()
    brand = Brand.objects.filter(id=brand_id).first()

    if not name:
        messages.error(request, "نام رنگ / مدل را وارد کن.")
    elif not brand:
        messages.error(request, "برند معتبر نیست.")
    else:
        color, created = Color.objects.get_or_create(name=name, defaults={"code": code, "active": True})
        changed = False
        if code and color.code != code:
            color.code = code
            changed = True
        if not color.active:
            color.active = True
            changed = True
        if changed:
            color.save(update_fields=["code", "active"])

        home = StockLocation.objects.get(key=StockLocation.HOME)
        khorshid = StockLocation.objects.get(key=StockLocation.KHORSHID)
        for size in _sizes_for_brand(brand):
            StockBalance.objects.get_or_create(brand=brand, size=size, color=color, location=home, defaults={"qty": 0})
            if brand.name == "دارما":
                StockBalance.objects.get_or_create(brand=brand, size=size, color=color, location=khorshid, defaults={"qty": 0})

        if created:
            messages.success(request, f"«{name}» اضافه شد و از همین حالا در موجودی {brand.name} نمایش داده می‌شود.")
        else:
            messages.info(request, f"«{name}» به موجودی {brand.name} متصل شد.")

    url = reverse("inventory")
    if brand_id:
        url += f"?brand={brand_id}"
    return redirect(url)
