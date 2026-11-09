"""V131 presentation-only production workspace.

POST remains delegated to V23. The original material, inventory, cost and wage
endpoints are unchanged; every editor posts the COMPLETE original block payload.
"""
from collections import defaultdict
from decimal import Decimal

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from . import material_report_v23 as v23
from . import material_report_v92 as v92
from .material_flow import ELASTIC, FABRIC, TAILOR, q
from .material_cost_v23 import used_elastic
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
    dozen_wage = v23.v20._dozen_wage()
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
        wage = v23.v20._wage_for_pieces(cut, dozen_wage) if cut else 0
        breakdown = v23.calculate_model_cost(key, raw, wage) if cut else {}
        elastic16_used = used_elastic(raw, "elastic16", "remain16") if cut else Decimal("0")
        elastic25_used = used_elastic(raw, "elastic25", "remain25") if cut else Decimal("0")
        incomplete_cost = cut > 0 and (
            (q(raw.get("weight")) > 0 and not breakdown.get("fabric_price"))
            or (elastic16_used > 0 and not breakdown.get("elastic16_price"))
            or (elastic25_used > 0 and not breakdown.get("elastic25_price"))
        )
        entries.append({
            "fabric_cost": int(breakdown.get("fabric_cost") or 0),
            "elastic_cost": int(breakdown.get("elastic_cost") or 0),
            "labor_cost": int(breakdown.get("labor_cost") or 0),
            "elastic16_used": elastic16_used,
            "elastic25_used": elastic25_used,
            "cost_incomplete": incomplete_cost,
            "cost_total": int(breakdown.get("total_cost") or 0),
            "cost_per_piece": int(breakdown.get("unit_cost") or 0),
            "key": key,
            "color": v23._material_label(key),
            "code": str(raw.get("fabric_code") or "").strip(),
            "weight": max(Decimal("0"), q(raw.get("weight"))),
            "cut": cut,
            "entered": entered,
            "applied": applied.get(key, 0),
            "remaining": max(0, cut - entered),
            "surplus": max(0, entered - cut),
        })
    return entries


def _totals(blocks, only_open=False):
    total = {"rolls": 0, "weight": Decimal("0"), "cut": 0,
             "entered": 0, "applied": 0, "remaining": 0, "surplus": 0,
             "open_rolls": 0, "average_cut": 0, "cost_total": 0,
             "cost_cut": 0, "average_unit_cost": 0,
             "yield_cut": 0, "yield_weight": Decimal("0"), "yield_per_20kg": 0}
    for block in blocks:
        raw_applied = {
            row.material_key for row in block.stock_consumptions.all()
            if row.kind == FABRIC and q(row.quantity) > 0
        }
        for roll in _roll_entries(block):
            if only_open and not (
                roll["cut"] > roll["entered"]
                or roll["entered"] != roll["applied"]
                or (roll["weight"] > 0 and roll["key"] not in raw_applied)
            ):
                continue
            total["rolls"] += 1
            total["weight"] += roll["weight"]
            total["cut"] += roll["cut"]
            total["entered"] += roll["entered"]
            total["applied"] += roll["applied"]
            total["remaining"] += roll["remaining"]
            total["surplus"] += roll["surplus"]
            total["cost_total"] += roll["cost_total"]
            if roll["weight"] > 0 and roll["cut"] > 0:
                total["yield_cut"] += roll["cut"]
                total["yield_weight"] += roll["weight"]
            if roll["cut"] > 0:
                total["cost_cut"] += roll["cut"]
            total["open_rolls"] += int(roll["cut"] > roll["entered"])
    if total["rolls"]:
        total["average_cut"] = round(total["cut"] / total["rolls"])
    if total["yield_weight"] > 0:
        total["yield_per_20kg"] = v23.round_money(
            Decimal(total["yield_cut"]) * Decimal("20") / total["yield_weight"]
        )
    if total["cost_cut"]:
        total["average_unit_cost"] = v23.round_money(
            Decimal(total["cost_total"]) / Decimal(total["cost_cut"])
        )
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
    consumed_keys = {
        row.material_key for row in block.stock_consumptions.all()
        if row.kind == FABRIC and q(row.quantity) > 0
    }
    visible = []
    for key in keys:
        raw = (block.input_data or {}).get(key) or {}
        out = (block.output_data or {}).get(key) or {}
        if (v23._values_have_input(raw) or v23._values_have_output(out)
                or key in applied_keys or key in consumed_keys):
            visible.append(key)
    # Newly-created empty sheets expose the five base colors once, so the
    # operator can choose pink/white/black without opening a different page.
    # After any row is filled, unused base colors disappear on the next load.
    if not visible:
        initial_key = str(((block.input_data or {}).get("_meta") or {}).get("initial_material_key") or "")
        visible = [initial_key] if initial_key in keys else [
            key for key in keys if key in v23.BASE_KEYS
        ]
    # An explicitly added extra model must remain editable even while blank.
    for key in v23._meta_keys(block.input_data):
        if key not in v23.BASE_KEYS and key in keys and key not in visible:
            visible.append(key)

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
        wage = v23.v20._wage_for_pieces(cut, v23.v20._dozen_wage()) if cut else 0
        batch_cost = v23.calculate_model_cost(key, raw, wage) if cut else {}
        rows.append({
            "key": key,
            "color": v23._material_label(key),
            "code": str(raw.get("fabric_code") or "").strip(),
            "weight": raw.get("weight") or "",
            "cut": cut, "entered": entered, "applied": applied,
            "remaining": max(0, cut - entered),
            "surplus": max(0, entered - cut),
            "cost_total": int(batch_cost.get("total_cost") or 0),
            "unit_cost": fields_by_key["cost"]["value"],
            "elastic16": raw.get("elastic16") or "",
            "elastic25": raw.get("elastic25") or "",
            "material_applied": key in consumed_keys,
            "production_meaningful": bool(
                v23._values_have_input(raw) or v23._values_have_output(out)
                or applied > 0 or key in consumed_keys
            ),
            "material_meaningful": bool(
                str(raw.get("fabric_code") or "").strip()
                or q(raw.get("weight")) > 0 or cut > 0 or entered > 0
                or key in consumed_keys
            ),
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
        "deletable": (
            not block.stock_consumptions.exists()
            and not block.output_applications.filter(quantity__gt=0).exists()
        ),
        "has_output": view["output_applied"] > 0,
        "output_applied": view["output_applied"],
        "output_pending": view["output_pending"],
        "output_reduction": view["output_reduction"],
        "average_cost": view["average_cost"],
    }


@login_required
def material_report(request):
    if request.method == "POST":
        # Older cached forms still follow the original V23 creation route.
        # New forms only add a presentation hint to V23's blank-sheet schema.
        v23._reset_request_caches()
        key = str(request.POST.get("initial_material_key") or "").strip()
        if not key:
            return v23.material_report(request)
        try:
            allowed = dict(v23._material_candidates(v23.BASE_KEYS))
            if key not in allowed:
                raise ValueError("رنگ انتخاب‌شده معتبر نیست؛ رنگی از فهرست انتخاب کن.")
            brand = v23._selected_brand(request)
            input_data = v23._blank_input_data()
            input_data["_meta"]["initial_material_key"] = key
            if brand.name == "دارما":
                input_data["_meta"]["auto_fabric_transfer_v147"] = True
            if key not in input_data["_meta"]["active_material_keys"]:
                input_data["_meta"]["active_material_keys"].append(key)
                input_data[key] = {}
            block = MaterialReportBlock.objects.create(
                date=v23.parse_jalali_date(request.POST.get("date") or v23.v20._today_jalali()),
                title=(request.POST.get("title") or "").strip(),
                brand=brand,
                input_data=input_data,
                output_data=v23._blank_output_data_for_brand(brand),
            )
            messages.success(
                request, f"صورت جدید با رنگ آغازین «{allowed[key]}» ساخته شد؛ وقتی وزن پارچه را ذخیره کنی از انبار به خیاط منتقل می‌شود. کش دستی است."
            )
            return redirect(f"/material-report/#block-{block.id}")
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("material_report")

    v23._reset_request_caches()
    blocks = list(
        MaterialReportBlock.objects.select_related("brand")
        .prefetch_related("output_applications", "stock_consumptions")
        .all()
    )
    current = v92._jalali_month_context()
    current_key = current["key"]
    available = sorted({current_key, *(_month_key(b.date) for b in blocks)}, reverse=True)
    previous_months = [key for key in available if key < current_key]
    mode = "archive" if request.GET.get("mode") in {"archive", "open"} else "month"
    requested = str(request.GET.get("report_month") or "")
    if mode == "archive":
        # Each archived month is strictly isolated; never combine old sheets.
        month = requested if requested in previous_months else (
            previous_months[0] if previous_months else current_key
        )
    else:
        month = current_key
    active = [b for b in blocks if _month_key(b.date) == month]

    editors = [_editor(b) for b in active]
    colors = {}
    for editor in editors:
        for row in editor["rows"]:
            # Do not offer empty legacy base-color placeholders as filters.
            if row["code"] or row["cut"] or row["entered"] or q(row["weight"]) > 0:
                colors[row["key"]] = row["color"]
    color_filters = [
        {"key": key, "label": label} for key, label in colors.items()
    ]
    tailor = RawMaterialStock.objects.filter(active=True, location=TAILOR)
    stock = {
        "fabric_kg": tailor.filter(kind=FABRIC).aggregate(v=Sum("quantity"))["v"] or Decimal("0"),
        "elastic_kg": tailor.filter(kind=ELASTIC).aggregate(v=Sum("quantity"))["v"] or Decimal("0"),
    }
    month_scope = _totals(active)
    return render(request, "core/material_report_v131.html", {
        "editors": editors,
        "month": month,
        "month_title": _month_title(month),
        "current_month": current_key,
        "months": [{"key": key, "label": _month_title(key)} for key in available],
        "previous_months": [{"key": key, "label": _month_title(key)} for key in previous_months],
        "color_filters": color_filters,
        "mode": mode,
        "scope": month_scope,
        "stock": stock,
        "brands": v23.v20._material_brands(),
        "new_sheet_colors": v23._material_candidates(v23.BASE_KEYS),
        "today_j": v23.v20._today_jalali(),
        "open_count": sum(bool(v92._block_operational_status(b)) for b in blocks),
    })
