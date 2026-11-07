"""AJAX response adapter for the *existing* production POST actions.

The accounting, wage, inventory, and material operations still execute in the
original V23 handlers. This module only replaces their redirect with JSON when
an authenticated same-origin form chooses inline save, delivery or materials.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from . import material_report_v23 as posting
from . import material_report_ui_v131 as presentation
from .models import MaterialReportBlock


HANDLERS = {
    "save": posting.material_block_save,
    "apply-output": posting.material_block_apply_output,
    "apply-color": posting.material_block_apply_color,
}


def _row_state(row):
    return {
        "key": row["key"],
        "color": row["color"],
        "code": row["code"],
        "search": row["search"],
        "weight": str(row["weight"]),
        "cut": row["cut"],
        "entered": row["entered"],
        "applied": row["applied"],
        "remaining": row["remaining"],
        "surplus": row["surplus"],
        "unit_cost": row["unit_cost"],
        "cost_total": row["cost_total"],
        "material_applied": row["material_applied"],
        "material_meaningful": row["material_meaningful"],
        "production_meaningful": row["production_meaningful"],
        "dirty_stock": row["dirty_stock"],
    }


@login_required
@require_POST
def material_block_inline_action(request, block_id):
    action = str(request.POST.get("_inline_action") or "").strip()
    if action not in HANDLERS:
        return JsonResponse(
            {"ok": False, "message": "عملیات ناشناخته است؛ هیچ تغییری اعمال نشد."},
            status=400,
        )
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return JsonResponse(
            {"ok": False, "message": "برای ثبت بدون رفرش، درخواست معتبر لازم است."},
            status=400,
        )

    # Invoke the exact existing decorated business endpoint in the same
    # request/transaction context, and discard only its browser redirect.
    response = HANDLERS[action](request, block_id)
    if response.status_code not in (301, 302, 303):
        return JsonResponse(
            {"ok": False, "message": "پاسخ عملیات تولید نامعتبر است."},
            status=500,
        )
    notices = list(messages.get_messages(request))
    failures = [str(note) for note in notices if note.level >= messages.ERROR]
    if failures:
        return JsonResponse({
            "ok": False, "message": " ".join(failures),
        }, status=422)

    # No inventory write here. The snapshot is authoritative, from the
    # committed business transaction, so all affected sheet colors refresh
    # their badges/totals without replacing the user's editor or scroll.
    block = get_object_or_404(
        MaterialReportBlock.objects.select_related("brand").prefetch_related(
            "output_applications", "stock_consumptions"
        ),
        pk=block_id,
    )
    posting._reset_request_caches()
    editor = presentation._editor(block)
    return JsonResponse({
        "ok": True,
        "action": action,
        "block_id": block.pk,
        "message": " ".join(str(note) for note in notices) or "اطلاعات ذخیره شد.",
        "rows": [_row_state(row) for row in editor["rows"]],
        "deletable": editor["deletable"],
    })
