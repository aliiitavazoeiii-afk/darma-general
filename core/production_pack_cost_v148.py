"""V148 read-only color-weighted production costs and actual sellable pack composition.

This report deliberately DOES NOT change the standard accounting cost, sale
pricing, inventory or production records. Every color uses its newest Jalali
month <= today containing cut sheets, preferring the current month. Weight by
number cut, not a simple average of per-roll unit prices.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

import jdatetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .brand_colors import norm, title_for_material_key
from .material_cost_v23 import round_money
from .material_report_ui_v131 import _roll_entries
from .material_report_v92 import JALALI_MONTH_NAMES
from . import material_report_v23 as v23
from .models import MaterialReportBlock, ProductCode


def _jalali_period(day):
    j = jdatetime.date.fromgregorian(date=day)
    return f"{j.year:04d}/{j.month:02d}"


def _period_title(key):
    year, month = map(int, key.split("/"))
    return f"{JALALI_MONTH_NAMES[month]} {year}"


def _selected_color_costs(as_of=None, blocks=None):
    """Return color-key costs for most recent cut month, no writes or zero fallback."""
    as_of = as_of or date.today()
    current = _jalali_period(as_of)
    if blocks is None:
        blocks = list(
            MaterialReportBlock.objects.filter(
                brand__name="دارما", date__lte=as_of
            ).select_related("brand").prefetch_related(
                "output_applications", "stock_consumptions"
            )
        )
    v23._reset_request_caches()
    grouped = {}
    for block in blocks:
        if block.date > as_of or block.brand.name != "دارما":
            continue
        month = _jalali_period(block.date)
        for roll in _roll_entries(block):
            cut = int(roll["cut"] or 0)
            if cut <= 0:
                continue
            key = norm(title_for_material_key(roll["key"]))
            if not key:
                continue
            item = grouped.setdefault((key, month), {
                "color": roll["color"],
                "month": month,
                "cut": 0,
                "rolls": 0,
                "total_cost": 0,
                "incomplete": False,
            })
            item["cut"] += cut
            item["rolls"] += 1
            item["total_cost"] += int(roll["cost_total"] or 0)
            # Missing fabric, unknown live ingredient price or a zero total
            # must NEVER yield a plausible-looking but underpriced pack.
            if (roll["cost_incomplete"]
                or roll["weight"] <= 0
                or int(roll["cost_total"] or 0) <= 0):
                item["incomplete"] = True

    selected = {}
    keys = {key for key, _month in grouped}
    for key in keys:
        months = [month for candidate, month in grouped if candidate == key and month <= current]
        if not months:
            continue
        month = max(months)  # Jalali YYYY/MM strings sort chronologically.
        aggregate = grouped[(key, month)]
        complete = not aggregate["incomplete"] and aggregate["cut"] > 0
        selected[key] = {
            **aggregate,
            "month_title": _period_title(month),
            "older": month != current,
            "available": complete,
            "unit_cost": (
                round_money(Decimal(aggregate["total_cost"]) / Decimal(aggregate["cut"]))
                if complete else None
            ),
        }
    return selected


def build_pack_cost_report(as_of=None):
    """One source-of-truth for product cards and per-color costs."""
    as_of = as_of or date.today()
    current = _jalali_period(as_of)
    sources = _selected_color_costs(as_of)
    products = list(
        ProductCode.objects.filter(
            brand__name="دارما", active=True, sizes__active=True
        ).distinct().prefetch_related(
            "composition__color", "sizes__size"
        ).order_by("code", "id")
    )
    product_rows = []
    colors_used = set()
    for product in products:
        composition = list(product.composition.all())
        contents = []
        missing = []
        sum_qty = 0
        pack_cost = 0
        for part in composition:
            qty = int(part.qty or 0)
            sum_qty += qty
            key = norm(part.color.name)
            colors_used.add(key)
            estimate = sources.get(key)
            price = estimate["unit_cost"] if estimate and estimate["available"] else None
            if price is None:
                missing.append(part.color.name)
            else:
                pack_cost += qty * price
            contents.append({
                "name": part.color.name,
                "qty": qty,
                "unit_cost": price,
                "subtotal": qty * price if price is not None else None,
                "month": estimate["month_title"] if estimate else "",
                "older": bool(estimate and estimate["older"]),
                "incomplete": bool(estimate and not estimate["available"]),
            })

        valid_composition = sum_qty == int(product.pack_qty or 0) and sum_qty > 0
        if not valid_composition:
            missing.append("ترکیب رنگ‌ها با تعداد پک مطابقت ندارد")
        ready = valid_composition and not missing
        sizes = sorted(
            {ps.size.name for ps in product.sizes.all() if ps.active},
            key=lambda k: ("M", "L", "XL", "XXL", "3XL", "4XL").index(k)
            if k in ("M", "L", "XL", "XXL", "3XL", "4XL") else 99
        )
        product_rows.append({
            "code": product.code,
            "title": product.title,
            "pack_qty": int(product.pack_qty or 0),
            "contents": contents,
            "sizes": sizes,
            "cost": pack_cost if ready else None,
            "missing": missing,
            "complete": ready,
            "count": sum_qty,
        })

    color_rows = [
        {
            **sources[key],
            "key": key,
        }
        for key in colors_used if key in sources
    ]
    color_rows.sort(key=lambda row: row["color"])
    return {
        "month": current,
        "month_title": _period_title(current),
        "products": product_rows,
        "colors": color_rows,
        "products_total": len(product_rows),
        "products_ready": sum(row["complete"] for row in product_rows),
        "products_missing": sum(not row["complete"] for row in product_rows),
    }


@login_required
def production_pack_costs(request):
    context = build_pack_cost_report()
    return render(request, "core/production_pack_costs_v148.html", context)
