"""Read-only, all-history production analytics.

Every number is derived from MaterialReportBlock and the exact V23 live costing
formula. No writes, reconciliation, or inventory movements occur on GET.
"""
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from . import material_report_ui_v131 as ui
from . import material_report_v23 as v23
from .material_flow import ELASTIC, FABRIC, TAILOR, WAREHOUSE, q
from .models import MaterialReportBlock, RawMaterialStock


def _empty(name=""):
    return {
        "name": name, "sheets": 0, "rolls": 0, "weight": Decimal("0"),
        "cut": 0, "entered": 0, "applied": 0, "remaining": 0, "surplus": 0,
        "fabric_cost": 0, "elastic_cost": 0, "labor_cost": 0, "cost_total": 0,
        "elastic16": Decimal("0"), "elastic25": Decimal("0"),
        "valid_yield_weight": Decimal("0"), "valid_yield_cut": 0,
        "unit_cost": 0, "yield20": 0, "progress": 0,
        "material_applied": 0, "material_pending": 0,
        "unsynced": 0, "reverse_due": 0, "incomplete_cost": 0,
        "missing_weight": 0, "open_codes": 0, "color_count": 0,
        "cost_share": 0, "bar": 0,
    }


def _accumulate(target, roll, *, material_applied, pending_sync, reverse_due):
    target["rolls"] += 1
    for key in ("cut", "entered", "applied", "remaining", "surplus",
                "fabric_cost", "elastic_cost", "labor_cost", "cost_total"):
        target[key] += roll[key]
    target["weight"] += roll["weight"]
    target["elastic16"] += roll["elastic16_used"]
    target["elastic25"] += roll["elastic25_used"]
    if roll["weight"] > 0 and roll["cut"] > 0:
        target["valid_yield_cut"] += roll["cut"]
        target["valid_yield_weight"] += roll["weight"]
    if roll["cut"] > 0 and roll["weight"] <= 0:
        target["missing_weight"] += 1
    target["incomplete_cost"] += int(roll["cost_incomplete"])
    target["material_applied" if material_applied else "material_pending"] += 1
    target["unsynced"] += pending_sync
    target["reverse_due"] += reverse_due
    target["open_codes"] += int(
        roll["remaining"] > 0 or pending_sync > 0
        or reverse_due > 0 or not material_applied
    )


def _finalize(stats):
    if stats["cut"] > 0:
        stats["unit_cost"] = v23.round_money(
            Decimal(stats["cost_total"]) / Decimal(stats["cut"])
        )
        stats["progress"] = min(100, v23.round_money(
            Decimal(stats["entered"]) * Decimal("100") / Decimal(stats["cut"])
        ))
    if stats["valid_yield_weight"] > 0:
        stats["yield20"] = v23.round_money(
            Decimal(stats["valid_yield_cut"]) * Decimal("20")
            / stats["valid_yield_weight"]
        )
    return stats


def build_overall_report(blocks):
    """Pure aggregation on prefetched ORM objects; no persisted side effects."""
    all_stats = _empty("تمام دوره‌ها")
    monthly = {}
    colors = {}
    followups = []
    size_totals = {}
    destinations = {"home": 0, "khorshid": 0, "other": 0, "legacy_unknown": 0}
    all_color_keys = set()

    for block in blocks:
        month_key = ui._month_key(block.date)
        month = monthly.setdefault(month_key, _empty(ui._month_title(month_key)))
        all_stats["sheets"] += 1
        month["sheets"] += 1

        fabric_keys = {
            row.material_key for row in block.stock_consumptions.all()
            if row.kind == FABRIC and q(row.quantity) > 0
        }
        output_applied = defaultdict(int)
        for application in block.output_applications.all():
            size_name = next(
                (label for key, label in v23._output_sizes_for_block(block)
                 if key == application.size_key), application.size_key.upper()
            )
            bucket = size_totals.setdefault(size_name, {
                "name": size_name, "entered": 0, "applied": 0, "pending": 0,
            })
            # Applied quantities can belong to an older sheet with no current
            # saved entry; they are counted in the applied column, not inferred.
            qty = max(0, int(application.quantity or 0))
            bucket["applied"] += qty
            output_applied[(application.model_key, application.size_key)] += qty
            allocated = 0
            for location_row in application.location_allocations.all():
                location_qty = max(0, int(location_row.quantity or 0))
                allocated += location_qty
                location_key = location_row.location.key
                if location_key in ("home", "khorshid"):
                    destinations[location_key] += location_qty
                else:
                    destinations["other"] += location_qty
            destinations["legacy_unknown"] += max(0, qty - allocated)

        saved_outputs = block.output_data or {}
        for material_key in v23._active_model_keys(block):
            saved = saved_outputs.get(material_key) or {}
            for size_key, label in v23._output_sizes_for_block(block):
                entered = max(0, v23.v20._int(saved.get(size_key)))
                bucket = size_totals.setdefault(label, {
                    "name": label, "entered": 0, "applied": 0, "pending": 0,
                })
                bucket["entered"] += entered
                bucket["pending"] += max(
                    0, entered - output_applied.get((material_key, size_key), 0)
                )

        for roll in ui._roll_entries(block):
            key = roll["key"]
            all_color_keys.add(key)
            color = colors.setdefault(key, _empty(roll["color"]))
            material_applied = key in fabric_keys
            saved = saved_outputs.get(key) or {}
            pending = 0
            reverse = 0
            for size_key, _ in v23._output_sizes_for_block(block):
                registered = max(0, v23.v20._int(saved.get(size_key)))
                applied = output_applied.get((key, size_key), 0)
                pending += max(0, registered - applied)
                reverse += max(0, applied - registered)
            for target in (all_stats, month, color):
                _accumulate(target, roll,
                    material_applied=material_applied,
                    pending_sync=pending, reverse_due=reverse)
            if roll["remaining"] or pending or reverse or not material_applied:
                followups.append({
                    "month": month["name"], "month_key": month_key,
                    "block_id": block.pk, "color": roll["color"],
                    "code": roll["code"] or "بدون کد",
                    "remaining": roll["remaining"],
                    "unsynced": pending, "reverse_due": reverse,
                    "material_applied": material_applied,
                    "priority": roll["remaining"] + pending + reverse,
                    "month_mode": "archive",
                })

    all_stats["color_count"] = len(all_color_keys)
    for target in [all_stats, *monthly.values(), *colors.values()]:
        _finalize(target)
        target["cost_share"] = (
            v23.round_money(Decimal(target["cost_total"]) * 100
            / Decimal(all_stats["cost_total"]))
            if all_stats["cost_total"] > 0 else 0
        )
    maximum_month_cut = max((item["cut"] for item in monthly.values()), default=0)
    for month in monthly.values():
        month["bar"] = round(month["cut"] * 100 / maximum_month_cut) if maximum_month_cut else 0
    followups.sort(key=lambda item: (-item["priority"], item["month_key"], item["block_id"]))
    return {
        "all": all_stats,
        "monthly": [
            dict({"key": key}, **row)
            for key, row in sorted(monthly.items(), reverse=True)
        ],
        "monthly_chart": [
            dict({"key": key}, **row)
            for key, row in sorted(monthly.items())
        ],
        "colors": sorted(colors.values(), key=lambda row: (-row["cut"], row["name"])),
        "followups": followups[:15],
        "followup_total": len(followups),
        "sizes": sorted(size_totals.values(), key=lambda row: (
            next((i for i, (key, label) in enumerate(
                v23.DARMA_OUTPUT_SIZES + v23.v20.NOVANI_OUTPUT_SIZES
            ) if label == row["name"]), 99)
        )),
        "destinations": destinations,
    }


@login_required
def production_overall(request):
    v23._reset_request_caches()
    blocks = list(
        MaterialReportBlock.objects.select_related("brand")
        .prefetch_related(
            "stock_consumptions",
            "output_applications__location_allocations__location",
        ).all()
    )
    report = build_overall_report(blocks)
    tailored = RawMaterialStock.objects.filter(active=True, location=TAILOR)
    warehouse = RawMaterialStock.objects.filter(active=True, location=WAREHOUSE)
    def _quantity(queryset, kind):
        return queryset.filter(kind=kind).aggregate(total=Sum("quantity"))["total"] or Decimal("0")
    stock = {
        "tailor_fabric": _quantity(tailored, FABRIC),
        "tailor_elastic": _quantity(tailored, ELASTIC),
        "warehouse_fabric": _quantity(warehouse, FABRIC),
        "warehouse_elastic": _quantity(warehouse, ELASTIC),
    }
    return render(request, "core/material_report_overall_v137.html", {
        "report": report,
        "stock": stock,
        "current_month": ui._month_key(blocks[0].date) if blocks else "",
    })
