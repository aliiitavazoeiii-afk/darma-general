"""V131 presentation-only production workspace.

POST remains delegated to V23. The original material, inventory, cost and wage
endpoints are unchanged; every editor posts the COMPLETE original block payload.
"""
from collections import defaultdict
from decimal import Decimal

import jdatetime
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from . import material_report_v23 as v23
from . import material_report_v92 as v92
from .material_flow import ELASTIC, FABRIC, TAILOR, q
from .models import MaterialReportBlock, RawMaterialStock


def _month_key(dt):
    jalali = jdatetime.date.fromgregorian(date=dt)
    return f"{jalali.year:04d}/{jalali.month:02d}"


def _month_title(key):
    year, month = (int(part) for part in key.split("/"))
    return f"{v92.JALALI_MONTH_NAMES[month]} {year}"


def _roll_entries(block):
    """Raw read-only per-color roll rows, with no stock or wage mutation."""
    entries = []
    applied = defaultdict(int)
    for record in block.output_applications.all():
        applied[record.model_key] += max(0, int(record.quantity or 0))
    for key in v23._active_model_keys(block):
        raw = (block.input_data or {}).get(key) or {}
        out = (block.output_data or {}).get(key) or {}
        used = (
            v23._values_have_input(raw)
            or v23._values_have_output(out)
            or applied.get(key, 0) > 0
            or any(row.material_key == key for row in block.stock_consumptions.all())
        )
        if not used:
            continue
        cut = max(0, v23.v20._int(raw.get("cut")))
        entered = sum(
            max(0, v23.v20._int(out.get(size)))
            for size, _ in v23._output_sizes_for_block(block)
        )
        entries.append({
            "key": key,
            "color": v23._material_label(key),
            "code": str(raw.get("fabric_code") or "").strip(),
            "weight": max(Decimal("0"), q(raw.get("weight"))),
            "cut": cut,
            "entered": entered,
            "applied": applied.get(key, 0),
            "remaining": max(0, cut - entered),
        })
    return entries


def _totals(blocks):
    total = {"rolls": 0, "weight": Decimal("0"), "cut": 0,
             "entered": 0, "applied": 0, "remaining": 0, "open_rolls": 0,
             "average_cut": 0}
    for block in blocks:
        for roll in _roll_entries(block):
            total["rolls"] += 1
            total["weight"] += roll["weight"]
            total["cut"] += roll["cut"]
            total["entered"] += roll["entered"]
            total["applied"] += roll["applied"]
            total["remaining"] += roll["remaining"]
            total["open_rolls"] += int(roll["cut"] > roll["entered"])
    if total["rolls"]:
        total["average_cut"] = round(total["cut"] / total["rolls"])
    return total


def _editor(block):
    """Adapt V23's exact form field names for the new compact row editor."""
    view = v23._view_block(block)
    keys = view["active_keys"]
    field_map = {key: [] for key in keys}
    for field in view["input_rows"]:
        for index, key in enumerate(keys):
            cell = field["cells"][index]
            field_map[key].append({
                "name": cell["name"], "value": cell["value"],
                "label": field["label"], "type": cell["type"],
                "readonly": cell["readonly"],
                "choices": cell.get("choices", []),
                "field_key": field["field_key"],
            })
    out_by_key = {row["model_key"]: row for row in view["output_rows"]}
    applied_keys = {
        row.model_key for row in block.output_applications.all()
        if int(row.quantity or 0) > 0
    }
    consumed_keys = {row.material_key for row in block.stock_consumptions.all()}
    visible = []
    for key in keys:
        raw = (block.input_data or {}).get(key) or {}
        out = (block.output_data or {}).get(key) or {}
        if (v23._values_have_input(raw) or v23._values_have_output(out)
                or key in applied_keys or key in consumed_keys):
            visible.append(key)
    # An empty newly-created sheet needs one explicit color selection, not five
    # permanently visible columns. Unused base colors are still posted unchanged.
    if not visible:
        visible = [keys[0]] if keys else []

    hidden_fields = []
    rows = []
    for key in keys:
        out_row = out_by_key[key]
        if key not in visible:
            for field in field_map[key]:
                if not field["readonly"]:
                    hidden_fields.append({"name": field["name"], "value": field["value"]})
            for cell in out_row["cells"]:
                for part in cell["parts"]:
                    hidden_fields.append({"name": part["name"], "value": part["value"]})
            continue

        raw = (block.input_data or {}).get(key) or {}
        cut = max(0, v23.v20._int(raw.get("cut")))
        entered = int(out_row["total"])
        applied = int(out_row["applied_total"])
        fields = field_map[key]
        fields_by_key = {f["field_key"]: f for f in fields}
        rows.append({
            "key": key,
            "color": v23._material_label(key),
            "code": str(raw.get("fabric_code") or "").strip(),
            "weight": raw.get("weight") or "",
            "cut": cut, "entered": entered, "applied": applied,
            "remaining": max(0, cut - entered),
            "unit_cost": fields_by_key["cost"]["value"],
            "elastic16": raw.get("elastic16") or "",
            "elastic25": raw.get("elastic25") or "",
            "material_applied": key in consumed_keys,
            "dirty_stock": entered != applied,
            "fields": fields,
            "sizes": [
                {"label": name, "parts": cell["parts"]}
                for (size_key, name), cell in zip(view["output_sizes"], out_row["cells"])
            ],
            "delivery_date": str(((block.output_data or {}).get(key) or {}).get("delivery_date") or ""),
            "search": " ".join([str(block.title or ""), str(block.id), v23._material_label(key),
                                str(raw.get("fabric_code") or ""), v23.format_jalali(block.date)]),
        })

    # All active keys must have a delivery date field even if blank.
    delivery_fields = [
        {"name": f"delivery_{key}",
         "value": str(((block.output_data or {}).get(key) or {}).get("delivery_date") or "")}
        for key in keys
    ]
    return {
        "obj": block,
        "form_id": f"material-form-{block.pk}",
        "date_j": v23.format_jalali(block.date),
        "active_keys_csv": view["active_keys_csv"],
        "hidden_fields": hidden_fields,
        "delivery_fields": delivery_fields,
        "add_model_choices": view["add_model_choices"],
        "rows": rows,
        "visible_count": len(rows),
        "brand": block.brand.name,
        "material_applied": view["materials_applied"],
        "has_output": view["output_applied"] > 0,
        "output_applied": view["output_applied"],
        "output_pending": view["output_pending"],
        "output_reduction": view["output_reduction"],
        "average_cost": view["average_cost"],
    }


@login_required
def material_report(request):
    if request.method == "POST":
        # Preserve V23 creation, transaction and redirects verbatim.
        return v23.material_report(request)

    v23._reset_request_caches()
    blocks = list(
        MaterialReportBlock.objects.select_related("brand")
        .prefetch_related("output_applications", "stock_consumptions")
        .all()
    )
    current = v92._jalali_month_context()
    current_key = current["key"]
    available = sorted({current_key, *(_month_key(b.date) for b in blocks)}, reverse=True)
    requested = str(request.GET.get("report_month") or current_key)
    month = requested if requested in available and requested <= current_key else current_key
    mode = "open" if request.GET.get("mode") == "open" else "month"
    if mode == "open":
        active = [b for b in blocks if v92._block_operational_status(b)]
    else:
        active = [b for b in blocks if _month_key(b.date) == month]

    editors = [_editor(b) for b in active]
    # Keep row and its exact original block form associated; no data duplication.
    for editor in editors:
        for row in editor["rows"]:
            row["sheet"] = editor

    tailor = RawMaterialStock.objects.filter(active=True, location=TAILOR)
    stock = {
        "fabric_kg": tailor.filter(kind=FABRIC).aggregate(v=Sum("quantity"))["v"] or Decimal("0"),
        "elastic_kg": tailor.filter(kind=ELASTIC).aggregate(v=Sum("quantity"))["v"] or Decimal("0"),
    }
    return render(request, "core/material_report_v131.html", {
        "editors": editors,
        "month": month,
        "month_title": _month_title(month),
        "current_month": current_key,
        "months": [{"key": key, "label": _month_title(key)} for key in available],
        "mode": mode,
        "scope": _totals(active),
        "all_totals": _totals(blocks),
        "stock": stock,
        "brands": v23.v20._material_brands(),
        "today_j": v23.v20._today_jalali(),
        "open_count": sum(bool(v92._block_operational_status(b)) for b in blocks),
    })
