from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .dateutils import format_jalali
from .finance import sale_line_metrics
from .models import SaleDay, SaleLine
from .telegram_inventory_alerts_v20 import notify_after_daily_report


@login_required
def daily_report(request, day_id):
    day = get_object_or_404(SaleDay, id=day_id)
    lines = list(
        SaleLine.objects.filter(day=day, quantity__gt=0)
        .select_related("product_size__product__brand", "product_size__size")
        .order_by(
            "product_size__product__brand__name",
            "product_size__size__sort_order",
            "product_size__product__code",
        )
    )

    by_brand = defaultdict(lambda: {
        "gross": 0, "digikala_fee": 0, "cogs": 0, "profit": 0,
        "shorts": 0, "packs": 0, "margin": 0,
    })
    total = {"gross": 0, "digikala_fee": 0, "cogs": 0, "profit": 0, "shorts": 0, "packs": 0, "margin": 0}
    detail_rows = []

    for line in lines:
        metrics = sale_line_metrics(line)
        brand_name = line.product_size.product.brand.name
        for key in ["gross", "digikala_fee", "cogs", "profit", "shorts", "packs"]:
            by_brand[brand_name][key] += metrics[key]
            total[key] += metrics[key]
        detail_rows.append({"line": line, **metrics})

    for values in by_brand.values():
        values["margin"] = (values["profit"] / values["gross"] * 100) if values["gross"] else 0
    total["margin"] = (total["profit"] / total["gross"] * 100) if total["gross"] else 0

    preferred = ["تکوین", "دارما", "انبارش"]
    ordered_brands = []
    for brand_name in preferred:
        if brand_name in by_brand:
            ordered_brands.append((brand_name, by_brand[brand_name]))
    for brand_name, values in by_brand.items():
        if brand_name not in preferred:
            ordered_brands.append((brand_name, values))

    # At most one automatic stock alert is sent for this sale date. Telegram
    # failure must never prevent the business report from opening.
    if lines:
        try:
            notify_after_daily_report(day)
        except Exception:
            pass

    return render(request, "core/daily_report_v21.html", {
        "day": day,
        "jalali_date": format_jalali(day.date),
        "detail_rows": detail_rows,
        "by_brand": ordered_brands,
        "total": total,
    })
