from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import *


def _to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


@login_required
def dashboard(request):
    today = date.today()
    current = SaleDay.objects.filter(date=today).first()
    sales = 0
    shorts = 0
    if current:
        for line in current.lines.select_related("product_size__product"):
            sales += line.gross_sales
            shorts += line.shorts_count
    alerts = []
    for t in StockThreshold.objects.select_related("brand", "size", "color")[:200]:
        qs = StockBalance.objects.filter(brand=t.brand, size=t.size, color=t.color)
        home = qs.filter(location__key="home").aggregate(v=Sum("qty"))["v"] or 0
        total = qs.aggregate(v=Sum("qty"))["v"] or 0
        kh = qs.filter(location__key="khorshid").aggregate(v=Sum("qty"))["v"] or 0
        if home <= t.home_min:
            alerts.append(("انتقال", f"{t.brand.name} / {t.color.name} / {t.size.name}", home, kh))
        if total <= t.total_min:
            alerts.append(("تولید", f"{t.brand.name} / {t.color.name} / {t.size.name}", total, t.total_min))
    setup_counts = {
        "products": ProductCode.objects.filter(active=True).count(),
        "colors": Color.objects.filter(active=True).count(),
        "stock_rows": StockBalance.objects.exclude(qty=0).count(),
    }
    return render(request, "core/dashboard.html", {"sales": sales, "shorts": shorts, "alerts": alerts[:10], "setup_counts": setup_counts})


@login_required
def sale_start(request):
    if request.method == "POST":
        d = request.POST.get("date") or str(date.today())
        day, _ = SaleDay.objects.get_or_create(date=d)
        return redirect("sale_brand", day_id=day.id)
    return render(request, "core/sale_start.html", {"today": date.today()})


@login_required
def sale_brand(request, day_id):
    day = get_object_or_404(SaleDay, id=day_id)
    brands = Brand.objects.filter(active=True)
    cards = []
    for brand in brands:
        first_ps = ProductSize.objects.filter(product__brand=brand, active=True, product__active=True).select_related("size").order_by("size__sort_order").first()
        cards.append((brand, first_ps))
    return render(request, "core/sale_brand.html", {"day": day, "cards": cards})


@login_required
def sale_size(request, day_id, brand_id, size_id):
    day = get_object_or_404(SaleDay, id=day_id)
    brand = get_object_or_404(Brand, id=brand_id)
    size = get_object_or_404(Size, id=size_id)
    product_sizes = ProductSize.objects.filter(product__brand=brand, size=size, active=True, product__active=True).select_related("product", "size").order_by("product__code")
    rows = []
    for ps in product_sizes:
        line = SaleLine.objects.filter(day=day, product_size=ps).first()
        rows.append((ps, line))
    sizes = list(Size.objects.filter(productsize__product__brand=brand, productsize__active=True, productsize__product__active=True).distinct().order_by("sort_order"))
    ids = [s.id for s in sizes]
    idx = ids.index(size.id) if size.id in ids else 0
    prev_size = sizes[idx - 1] if idx > 0 else None
    next_size = sizes[idx + 1] if idx < len(sizes) - 1 else None
    return render(request, "core/sale_size.html", {"day": day, "brand": brand, "size": size, "rows": rows, "sizes": sizes, "prev_size": prev_size, "next_size": next_size})


@login_required
@require_POST
def sale_line_save(request):
    day = get_object_or_404(SaleDay, id=request.POST["day_id"])
    ps = get_object_or_404(ProductSize, id=request.POST["product_size_id"])
    qty = max(0, _to_int(request.POST.get("quantity")))
    price = max(0, _to_int(request.POST.get("sale_price"), ps.default_sale_price))
    line, _ = SaleLine.objects.update_or_create(day=day, product_size=ps, defaults={"quantity": qty, "sale_price": price})
    return render(request, "core/_saved.html", {"line": line})


@login_required
def inventory(request):
    brand_id = request.GET.get("brand")
    brands = Brand.objects.filter(active=True)
    brand = brands.filter(id=brand_id).first() if brand_id else brands.first()
    sizes = Size.objects.all()
    colors = Color.objects.filter(active=True)
    table = []
    if brand:
        for color in colors:
            row = []
            for size in sizes:
                qs = StockBalance.objects.filter(brand=brand, color=color, size=size)
                home = qs.filter(location__key="home").aggregate(v=Sum("qty"))["v"] or 0
                kh = qs.filter(location__key="khorshid").aggregate(v=Sum("qty"))["v"] or 0
                row.append((size, home, kh, home + kh))
            table.append((color, row))
    return render(request, "core/inventory.html", {"brands": brands, "brand": brand, "sizes": sizes, "table": table})


@login_required
def settings_home(request):
    counts = {"brands": Brand.objects.filter(active=True).count(), "sizes": Size.objects.count(), "colors": Color.objects.filter(active=True).count(), "products": ProductCode.objects.filter(active=True).count(), "stock_rows": StockBalance.objects.exclude(qty=0).count()}
    accounts = Account.objects.all().order_by("id")
    return render(request, "core/settings_home.html", {"counts": counts, "accounts": accounts})


@login_required
def settings_catalog(request):
    if request.method == "POST":
        entity = request.POST.get("entity")
        obj_id = request.POST.get("id")
        if entity == "color":
            name = (request.POST.get("name") or "").strip()
            code = (request.POST.get("code") or "").strip()
            if not name:
                messages.error(request, "نام رنگ نمی‌تواند خالی باشد.")
            else:
                obj = Color.objects.filter(id=obj_id).first() if obj_id else None
                if obj:
                    obj.name, obj.code = name, code
                    obj.active = bool(request.POST.get("active"))
                    obj.save()
                    messages.success(request, "رنگ ویرایش شد.")
                else:
                    Color.objects.get_or_create(name=name, defaults={"code": code, "active": True})
                    messages.success(request, "رنگ اضافه شد.")
        elif entity == "brand":
            name = (request.POST.get("name") or "").strip()
            if name:
                obj = Brand.objects.filter(id=obj_id).first() if obj_id else None
                if obj:
                    obj.name = name
                    obj.active = bool(request.POST.get("active"))
                    obj.save()
                else:
                    Brand.objects.get_or_create(name=name, defaults={"active": True})
                messages.success(request, "برند ذخیره شد.")
        elif entity == "size":
            name = (request.POST.get("name") or "").strip()
            order = max(0, _to_int(request.POST.get("sort_order")))
            if name:
                obj = Size.objects.filter(id=obj_id).first() if obj_id else None
                if obj:
                    obj.name, obj.sort_order = name, order
                    obj.save()
                else:
                    Size.objects.get_or_create(name=name, defaults={"sort_order": order})
                messages.success(request, "سایز ذخیره شد.")
        return redirect("settings_catalog")
    return render(request, "core/settings_catalog.html", {"brands": Brand.objects.all().order_by("id"), "sizes": Size.objects.all(), "colors": Color.objects.all().order_by("id")})


@login_required
def settings_products(request):
    products = ProductCode.objects.select_related("brand").prefetch_related("composition__color", "sizes__size").all().order_by("brand__name", "code")
    return render(request, "core/settings_products.html", {"products": products})


@login_required
@transaction.atomic
def settings_product_form(request, product_id=None):
    product = get_object_or_404(ProductCode, id=product_id) if product_id else None
    brands = Brand.objects.filter(active=True)
    colors = list(Color.objects.filter(active=True).order_by("id"))
    sizes = list(Size.objects.all())
    existing_comp = {}
    existing_sizes = {}
    if product:
        existing_comp = {c.color_id: c.qty for c in product.composition.all()}
        existing_sizes = {ps.size_id: ps for ps in product.sizes.select_related("size").all()}
    form_brand_id = product.brand_id if product else (brands.first().id if brands.exists() else None)
    form_code = product.code if product else ""
    form_pack_qty = product.pack_qty if product else 1
    form_note = product.note if product else ""
    form_active = product.active if product else True
    if request.method == "POST":
        form_brand_id = _to_int(request.POST.get("brand"))
        form_code = (request.POST.get("code") or "").strip()
        form_pack_qty = max(1, _to_int(request.POST.get("pack_qty"), 1))
        form_note = (request.POST.get("note") or "").strip()
        form_active = bool(request.POST.get("active"))
        brand = get_object_or_404(Brand, id=form_brand_id)
        comp = {}
        comp_total = 0
        for color in colors:
            qty = max(0, _to_int(request.POST.get(f"color_{color.id}")))
            if qty:
                comp[color.id] = qty
                comp_total += qty
        enabled_sizes = [size for size in sizes if request.POST.get(f"size_{size.id}")]
        errors = []
        if not form_code:
            errors.append("کد محصول را وارد کن.")
        if comp_total != form_pack_qty:
            errors.append(f"جمع تعداد رنگ‌ها باید دقیقاً {form_pack_qty} باشد؛ الان {comp_total} است.")
        if not enabled_sizes:
            errors.append("حداقل یک سایز را برای این کد فعال کن.")
        duplicate = ProductCode.objects.filter(brand=brand, code=form_code)
        if product:
            duplicate = duplicate.exclude(id=product.id)
        if duplicate.exists():
            errors.append("این کد برای این برند قبلاً ثبت شده است.")
        if not errors:
            if not product:
                product = ProductCode()
            product.brand = brand
            product.code = form_code
            product.pack_qty = form_pack_qty
            product.note = form_note
            product.active = form_active
            product.save()
            ProductComposition.objects.filter(product=product).delete()
            for color_id, qty in comp.items():
                ProductComposition.objects.create(product=product, color_id=color_id, qty=qty)
            selected_ids = {sz.id for sz in enabled_sizes}
            ProductSize.objects.filter(product=product).exclude(size_id__in=selected_ids).update(active=False)
            for size in enabled_sizes:
                ProductSize.objects.update_or_create(product=product, size=size, defaults={"default_sale_price": max(0, _to_int(request.POST.get(f"sale_price_{size.id}"))), "unit_cost": max(0, _to_int(request.POST.get(f"unit_cost_{size.id}"))), "active": True})
            messages.success(request, f"کد {product.code} ذخیره شد.")
            return redirect("settings_products")
        for err in errors:
            messages.error(request, err)
    color_rows = []
    for color in colors:
        qty = max(0, _to_int(request.POST.get(f"color_{color.id}"))) if request.method == "POST" else existing_comp.get(color.id, 0)
        color_rows.append({"obj": color, "qty": qty})
    size_rows = []
    for size in sizes:
        ps = existing_sizes.get(size.id)
        if request.method == "POST":
            checked = bool(request.POST.get(f"size_{size.id}"))
            sale_price = max(0, _to_int(request.POST.get(f"sale_price_{size.id}")))
            unit_cost = max(0, _to_int(request.POST.get(f"unit_cost_{size.id}")))
        else:
            checked = bool(ps and ps.active)
            sale_price = ps.default_sale_price if ps else 0
            unit_cost = ps.unit_cost if ps else 0
        size_rows.append({"obj": size, "checked": checked, "sale_price": sale_price, "unit_cost": unit_cost})
    return render(request, "core/settings_product_form.html", {"product": product, "brands": brands, "color_rows": color_rows, "size_rows": size_rows, "form_brand_id": form_brand_id, "form_code": form_code, "form_pack_qty": form_pack_qty, "form_note": form_note, "form_active": form_active})


@login_required
def settings_stock(request):
    brands = Brand.objects.filter(active=True)
    brand_id = request.GET.get("brand") or request.POST.get("brand")
    brand = brands.filter(id=brand_id).first() if brand_id else brands.first()
    sizes = list(Size.objects.all())
    colors = list(Color.objects.filter(active=True).order_by("id"))
    home = StockLocation.objects.get(key="home")
    khorshid = StockLocation.objects.get(key="khorshid")
    if request.method == "POST" and brand:
        with transaction.atomic():
            for color in colors:
                for size in sizes:
                    home_qty = _to_int(request.POST.get(f"home_{color.id}_{size.id}"))
                    kh_qty = _to_int(request.POST.get(f"kh_{color.id}_{size.id}"))
                    if brand.name == "تکوین":
                        kh_qty = 0
                    StockBalance.objects.update_or_create(brand=brand, size=size, color=color, location=home, defaults={"qty": home_qty})
                    StockBalance.objects.update_or_create(brand=brand, size=size, color=color, location=khorshid, defaults={"qty": kh_qty})
                    StockThreshold.objects.update_or_create(brand=brand, size=size, color=color, defaults={"home_min": max(0, _to_int(request.POST.get(f"home_min_{color.id}_{size.id}"))), "total_min": max(0, _to_int(request.POST.get(f"total_min_{color.id}_{size.id}")))})
        messages.success(request, f"موجودی و حداقل‌های {brand.name} ذخیره شد.")
        return redirect(f"{request.path}?brand={brand.id}")
    rows = []
    if brand:
        for color in colors:
            cells = []
            for size in sizes:
                balances = StockBalance.objects.filter(brand=brand, color=color, size=size)
                h = balances.filter(location=home).first()
                k = balances.filter(location=khorshid).first()
                t = StockThreshold.objects.filter(brand=brand, color=color, size=size).first()
                cells.append({"size": size, "home": h.qty if h else 0, "kh": k.qty if k else 0, "home_min": t.home_min if t else 0, "total_min": t.total_min if t else 0})
            rows.append({"color": color, "cells": cells})
    return render(request, "core/settings_stock.html", {"brands": brands, "brand": brand, "sizes": sizes, "rows": rows})


@login_required
def settings_finance(request):
    accounts = list(Account.objects.all().order_by("id"))
    if request.method == "POST":
        for account in accounts:
            account.opening_balance = _to_int(request.POST.get(f"account_{account.id}"), account.opening_balance)
            account.save(update_fields=["opening_balance"])
        messages.success(request, "مانده‌های اولیه حساب‌ها ذخیره شد.")
        return redirect("settings_finance")
    return render(request, "core/settings_finance.html", {"accounts": accounts})


@login_required
def settings_rules(request):
    settings = list(AppSetting.objects.all().order_by("id"))
    if request.method == "POST":
        for item in settings:
            if f"setting_{item.id}" in request.POST:
                item.value = (request.POST.get(f"setting_{item.id}") or "").strip()
                item.save(update_fields=["value", "updated_at"])
        messages.success(request, "تنظیمات محاسباتی ذخیره شد.")
        return redirect("settings_rules")
    return render(request, "core/settings_rules.html", {"settings": settings})


@login_required
def report(request):
    start = request.GET.get("start")
    end = request.GET.get("end")
    days = SaleDay.objects.all()
    if start: days = days.filter(date__gte=start)
    if end: days = days.filter(date__lte=end)
    total_sales = 0
    total_shorts = 0
    total_packs = 0
    by_brand = defaultdict(lambda: {"sales": 0, "shorts": 0, "packs": 0})
    for line in SaleLine.objects.filter(day__in=days).select_related("product_size__product__brand"):
        total_sales += line.gross_sales
        total_shorts += line.shorts_count
        total_packs += line.quantity
        b = line.product_size.product.brand.name
        by_brand[b]["sales"] += line.gross_sales
        by_brand[b]["shorts"] += line.shorts_count
        by_brand[b]["packs"] += line.quantity
    return render(request, "core/report.html", {"total_sales": total_sales, "total_shorts": total_shorts, "total_packs": total_packs, "by_brand": dict(by_brand), "start": start, "end": end})
