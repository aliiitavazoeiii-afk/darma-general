from datetime import date
from decimal import Decimal, InvalidOperation

import jdatetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import material_report_v23 as v23
from .models import MaterialReportBlock


JALALI_MONTH_NAMES = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}


def _decimal(value):
    raw = str(value or "").strip().replace("٬", "").replace(",", ".")
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _jalali_month_context(today=None):
    today = today or date.today()
    current = jdatetime.date.fromgregorian(date=today)
    start_j = jdatetime.date(current.year, current.month, 1)
    if current.month == 12:
        next_j = jdatetime.date(current.year + 1, 1, 1)
    else:
        next_j = jdatetime.date(current.year, current.month + 1, 1)
    return {
        "year": int(current.year),
        "month": int(current.month),
        "key": f"{current.year:04d}/{current.month:02d}",
        "label": f"{JALALI_MONTH_NAMES[current.month]} {current.year}",
        "start": start_j.togregorian(),
        "next": next_j.togregorian(),
    }


def _format_weight(value):
    value = Decimal(value or 0).quantize(Decimal("0.001"))
    text = format(value, "f").rstrip("0").rstrip(".")
    return text or "0"


BASE_COLOR_PROGRESS = tuple(v23.BASE_MODELS)


def _summarize_open_base_colors(blocks):
    """Outstanding Darma work for the five main colors.

    Completed sheets are intentionally excluded so old production does not inflate
    the operational numbers. For each color we show only blocks where cut >
    actually-applied finished output.
    """
    rows = []
    for key, label in BASE_COLOR_PROGRESS:
        expected = 0
        delivered = 0
        pending = 0
        open_blocks = 0
        for block in blocks:
            if block.brand.name != "دارما":
                continue
            cut = max(0, v23.v20._int(((block.input_data or {}).get(key) or {}).get("cut")))
            applied = sum(
                max(0, int(item.quantity or 0))
                for item in block.output_applications.all()
                if item.model_key == key
            )
            if cut <= applied:
                continue
            expected += cut
            delivered += applied
            pending += cut - applied
            open_blocks += 1
        rows.append({
            "key": key,
            "label": label,
            "expected": int(expected),
            "delivered": int(delivered),
            "pending": int(pending),
            "open_blocks": int(open_blocks),
        })
    return rows


def _summarize_month_blocks(blocks):
    fabric_codes = set()
    uncoded_rolls = 0
    total_weight = Decimal("0")
    total_cut = 0
    total_delivered = 0
    total_pending = 0

    for block in blocks:
        active_keys = v23._active_model_keys(block)
        block_cut = 0

        for key in active_keys:
            values = (block.input_data or {}).get(key, {}) or {}
            code = str(values.get("fabric_code") or "").strip()
            weight = max(_decimal(values.get("weight")), Decimal("0"))
            cut = max(0, v23.v20._int(values.get("cut")))

            if code:
                fabric_codes.add(code)
            elif weight > 0:
                # A positive-weight row without a fabric code still represents
                # one delivered roll for the monthly operational summary.
                uncoded_rolls += 1

            total_weight += weight
            block_cut += cut

        block_delivered = sum(
            max(0, int(row.quantity or 0))
            for row in block.output_applications.all()
        )
        total_cut += block_cut
        total_delivered += block_delivered
        total_pending += max(0, block_cut - block_delivered)

    return {
        "roll_count": len(fabric_codes) + uncoded_rolls,
        "weight": total_weight,
        "weight_display": _format_weight(total_weight),
        "minimum_delivery": int(total_cut),
        "delivered": int(total_delivered),
        "pending": int(total_pending),
        "block_count": len(blocks),
    }


def _decorate_block_month(row):
    parts = str(row.get("jalali_date") or "").split("/")
    if len(parts) >= 2:
        try:
            year = int(parts[0])
            month = int(parts[1])
        except (TypeError, ValueError):
            return row
        row["month_key"] = f"{year:04d}/{month:02d}"
        row["month_label"] = f"{JALALI_MONTH_NAMES.get(month, month)} {year}"
    return row


@login_required
def material_report(request):
    """V92: V23 material report with current-month KPIs and previous-month UI archive."""
    if request.method == "POST":
        # Creation semantics stay exactly on V23.
        return v23.material_report(request)

    v23._reset_request_caches()
    brands = v23.v20._material_brands()
    month = _jalali_month_context()

    queryset = MaterialReportBlock.objects.select_related("brand").prefetch_related(
        "output_applications", "stock_consumptions"
    )
    objects = list(queryset.all())
    blocks = [_decorate_block_month(v23._view_block(obj)) for obj in objects]

    current_month_objects = [
        obj for obj in objects
        if month["start"] <= obj.date < month["next"]
    ]
    summary = _summarize_month_blocks(current_month_objects)
    summary["month_label"] = month["label"]
    base_color_progress = _summarize_open_base_colors(objects)

    return render(
        request,
        "core/material_report_v92.html",
        {
            "blocks": blocks,
            "brands": brands,
            "today_j": v23.v20._today_jalali(),
            "sewing_wage_rate": v23.v20._dozen_wage(),
            "material_month_summary": summary,
            "material_current_month_key": month["key"],
            "material_current_month_label": month["label"],
            "material_base_color_progress": base_color_progress,
        },
    )
