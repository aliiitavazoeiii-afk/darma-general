from collections import defaultdict
from datetime import date, timedelta

import jdatetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .dateutils import format_jalali
from .finance import sale_line_metrics
from .models import Brand, ProductSize, SaleDay, SaleLine, Size


PERSIAN_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _brand_sizes(brand):
    qs = Size.objects.all().order_by("sort_order", "id")
    if brand.name == "تکوین":
        qs = qs.exclude(name__in=["3XL", "4XL"])
    return list(qs)


@login_required
def sale_calendar(request):
    today_j = jdatetime.date.fromgregorian(date=date.today())
    try:
        jy = int(request.GET.get("jy", today_j.year))
        jm = int(request.GET.get("jm", today_j.month))
        if not 1 <= jm <= 12:
            raise ValueError
    except ValueError:
        jy, jm = today_j.year, today_j.month

    first_j = jdatetime.date(jy, jm, 1)
    first_g = first_j.togregorian()
    if jm == 12:
        next_j = jdatetime.date(jy + 1, 1, 1)
    else:
        next_j = jdatetime.date(jy, jm + 1, 1)
    next_g = next_j.togregorian()
    days_count = (next_g - first_g).days
    leading = (first_g.weekday() + 2) % 7

    existing = {
        d.date: d
        for d in SaleDay.objects.filter(date__gte=first_g, date__lt=next_g).prefetch_related("lines")
    }
    cells = [None] * leading
    for day_num in range(1, days_count + 1):
        g = jdatetime.date(jy, jm, day_num).togregorian()
        sale_day = existing.get(g)
        has_sales = bool(sale_day and any(line.quantity > 0 for line in sale_day.lines.all()))
        cells.append({
            "day": day_num,
            "is_today": g == date.today(),
            "has_sales": has_sales,
            "sale_day": sale_day,
        })
    while len(cells) % 7:
        cells.append(None)
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]

    if jm == 1:
        prev_y, prev_m = jy - 1, 12
    else:
        prev_y, prev_m = jy, jm - 1
    if jm == 12:
        next_y, next_m = jy + 1, 1
    else:
        next_y, next_m = jy, jm + 1

    return render(request, "core/sale_calendar.html", {
        "jy": jy, "jm": jm, "month_name": PERSIAN_MONTHS[jm - 1],
        "weekdays": PERSIAN_WEEKDAYS, "weeks": weeks,
        "prev_y": prev_y, "prev_m": prev_m, "next_y": next_y, "next_m": next_m,
    })


@login_required
def select_sale_day(request, jy, jm, jd):
    g = jdatetime.date(jy, jm, jd).togregorian()
    day, _ = SaleDay.objects.get_or_create(date=g)
    if day.lines.filter(quantity__gt=0).exists():
        return redirect("daily_report", day_id=day.id)
    return redirect("sale_brand", day_id=day.id)


@login_required
def sale_size(request, day_id, brand_id, size_id):
    day = get_object_or_404(SaleDay, id=day_id)
    brand = get_object_or_404(Brand, id=brand_id)
    size = get_object_or_404(Size, id=size_id)
    sizes = _brand_sizes(brand)
    ids = [s.id for s in sizes]
    if size.id not in ids:
        return redirect("sale_brand", day_id=day.id)

    product_sizes = ProductSize.objects.filter(
        product__brand=brand, size=size, active=True, product__active=True
    ).select_related("product", "size").order_by("product__code")
    rows = []
    for ps in product_sizes:
        line = SaleLine.objects.filter(day=day, product_size=ps).first()
        rows.append((ps, line))

    idx = ids.index(size.id)
    prev_size = sizes[idx - 1] if idx > 0 else None
    next_size = sizes[idx + 1] if idx < len(sizes) - 1 else None
    return render(request, "core/sale_size.html", {
        "day": day, "brand": brand, "size": size, "rows": rows,
        "sizes": sizes, "prev_size": prev_size, "next_size": next_size,
    })


@login_required
def daily_report(request, day_id):
    day = get_object_or_404(SaleDay, id=day_id)
    lines = list(
        SaleLine.objects.filter(day=day, quantity__gt=0)
        .select_related("product_size__product__brand", "product_size__size")
        .order_by("product_size__product__brand__name", "product_size__size__sort_order", "product_size__product__code")
    )

    by_brand = defaultdict(lambda: {
        "gross": 0, "digikala_fee": 0, "cogs": 0, "profit": 0,
        "shorts": 0, "packs": 0, "margin": 0,
    })
    total = {"gross": 0, "digikala_fee": 0, "cogs": 0, "profit": 0, "shorts": 0, "packs": 0, "margin": 0}
    detail_rows = []

    for line in lines:
        m = sale_line_metrics(line)
        brand_name = line.product_size.product.brand.name
        for key in ["gross", "digikala_fee", "cogs", "profit", "shorts", "packs"]:
            by_brand[brand_name][key] += m[key]
            total[key] += m[key]
        detail_rows.append({"line": line, **m})

    for values in by_brand.values():
        values["margin"] = (values["profit"] / values["gross"] * 100) if values["gross"] else 0
    total["margin"] = (total["profit"] / total["gross"] * 100) if total["gross"] else 0

    ordered_brands = []
    for brand_name in ["تکوین", "دارما"]:
        if brand_name in by_brand:
            ordered_brands.append((brand_name, by_brand[brand_name]))
    for brand_name, values in by_brand.items():
        if brand_name not in ["تکوین", "دارما"]:
            ordered_brands.append((brand_name, values))

    return render(request, "core/daily_report.html", {
        "day": day,
        "jalali_date": format_jalali(day.date),
        "detail_rows": detail_rows,
        "by_brand": ordered_brands,
        "total": total,
    })
