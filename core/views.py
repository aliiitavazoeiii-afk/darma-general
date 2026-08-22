from collections import defaultdict
from datetime import date
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import *

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
    return render(request, "core/dashboard.html", {"sales": sales, "shorts": shorts, "alerts": alerts[:10]})

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
    qty = max(0, int(request.POST.get("quantity") or 0))
    price = max(0, int(request.POST.get("sale_price") or ps.default_sale_price))
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
def settings_products(request):
    return render(request, "core/settings_products.html", {"products": ProductCode.objects.select_related("brand").all()[:200]})

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
