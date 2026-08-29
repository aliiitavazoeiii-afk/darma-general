from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .dateutils import format_jalali
from .finance import sale_line_metrics
from .models import SaleDay, SaleLine
from .telegram_inventory_alerts_v20 import notify_after_daily_report


PRIMARY_REPORT_BRANDS = ("تکوین", "دارما")
FILTER_SIZES = {
    "تکوین": ("M", "L", "XL", "XXL"),
    "دارما": ("M", "L", "XL", "XXL", "3XL", "4XL"),
}


def _line_color_breakdown(line):
    """Return the physical colors represented by this sale line.

    SaleAllocation is authoritative because it records what was actually deducted
    from stock, including resolved replacement colors. For older lines that have
    no allocations, fall back to the configured ProductComposition and mark that
    source explicitly so the UI never presents an inferred composition as exact.
    """
    grouped = {}
    replacement_qty = defaultdict(int)

    allocations = list(line.allocations.all())
    if allocations:
        for alloc in allocations:
            name = alloc.color.name
            if name not in grouped:
                grouped[name] = 0
            qty = int(alloc.qty or 0)
            grouped[name] += qty
            if alloc.is_replacement:
                replacement_qty[name] += qty
        source = "allocation"
    else:
        for comp in line.product_size.product.composition.all():
            name = comp.color.name
            if name not in grouped:
                grouped[name] = 0
            grouped[name] += int(line.quantity or 0) * int(comp.qty or 0)
        source = "composition" if grouped else "unknown"

    colors = []
    for name, qty in grouped.items():
        colors.append({
            "name": name,
            "qty": int(qty),
            "replacement_qty": int(replacement_qty.get(name, 0)),
        })
    return colors, source


def _build_filter_brands(detail_rows):
    stats = {
        brand: {
            "name": brand,
            "packs": 0,
            "shorts": 0,
            "line_count": 0,
            "sizes": {size: {"name": size, "packs": 0, "shorts": 0, "line_count": 0}
                      for size in FILTER_SIZES[brand]},
        }
        for brand in PRIMARY_REPORT_BRANDS
    }

    for row in detail_rows:
        brand = row["brand_name"]
        if brand not in stats:
            continue
        values = stats[brand]
        values["packs"] += int(row["packs"])
        values["shorts"] += int(row["shorts"])
        values["line_count"] += 1
        size = row["size_name"]
        if size not in values["sizes"]:
            values["sizes"][size] = {"name": size, "packs": 0, "shorts": 0, "line_count": 0}
        values["sizes"][size]["packs"] += int(row["packs"])
        values["sizes"][size]["shorts"] += int(row["shorts"])
        values["sizes"][size]["line_count"] += 1

    result = []
    for brand in PRIMARY_REPORT_BRANDS:
        values = stats[brand]
        values["sizes"] = list(values["sizes"].values())
        result.append(values)
    return result


@login_required
def daily_report(request, day_id):
    day = get_object_or_404(SaleDay, id=day_id)
    lines = list(
        SaleLine.objects.filter(day=day, quantity__gt=0)
        .select_related("product_size__product__brand", "product_size__size")
        .prefetch_related(
            "allocations__color",
            "product_size__product__composition__color",
        )
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
        size_name = line.product_size.size.name
        colors, color_source = _line_color_breakdown(line)
        color_total = sum(int(item["qty"]) for item in colors)

        for key in ["gross", "digikala_fee", "cogs", "profit", "shorts", "packs"]:
            by_brand[brand_name][key] += metrics[key]
            total[key] += metrics[key]

        detail_rows.append({
            "line": line,
            "brand_name": brand_name,
            "size_name": size_name,
            "code": line.product_size.product.code,
            "colors": colors,
            "color_source": color_source,
            "color_total": color_total,
            "color_mismatch": bool(color_source == "allocation" and color_total != int(metrics["shorts"])),
            **metrics,
        })

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

    filter_brands = _build_filter_brands(detail_rows)
    primary_detail_rows = [row for row in detail_rows if row["brand_name"] in PRIMARY_REPORT_BRANDS]
    other_detail_rows = [row for row in detail_rows if row["brand_name"] not in PRIMARY_REPORT_BRANDS]

    default_brand = "دارما"
    if not any(row["brand_name"] == "دارما" for row in primary_detail_rows):
        default_brand = "تکوین"

    if lines:
        try:
            notify_after_daily_report(day)
        except Exception:
            pass

    return render(request, "core/daily_report_v21.html", {
        "day": day,
        "jalali_date": format_jalali(day.date),
        "detail_rows": detail_rows,
        "primary_detail_rows": primary_detail_rows,
        "other_detail_rows": other_detail_rows,
        "filter_brands": filter_brands,
        "default_brand": default_brand,
        "by_brand": ordered_brands,
        "total": total,
    })