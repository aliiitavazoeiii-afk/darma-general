from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .digikala_client_v40 import DigikalaAPIError, get_summary
from .digikala_delivery_v41 import get_delivery_board


@login_required
@require_GET
def digikala_home(request):
    force = request.GET.get("refresh") == "1"
    try:
        summary = get_summary(force=force)
        delivery = get_delivery_board(force=force)
        page_error = ""
    except DigikalaAPIError as exc:
        summary = {"connected": False, "errors": {"api": str(exc)}}
        delivery = {"rows": [], "effective_total": 0, "total_commitments": 0}
        page_error = str(exc)
    return render(
        request,
        "core/digikala_v40.html",
        {
            "digikala": summary,
            "delivery": delivery,
            "digikala_error": page_error,
        },
    )


@login_required
@require_GET
def digikala_summary(request):
    try:
        force = request.GET.get("refresh") == "1"
        summary = get_summary(force=force)
        delivery = get_delivery_board(force=force)
        summary["delivery_effective_total"] = delivery.get("effective_total", 0)
        summary["delivery_total_commitments"] = delivery.get("total_commitments", 0)
        summary["delivery_delayed_total"] = delivery.get("delayed_total", 0)
        summary["delivery_variant_count"] = delivery.get("variant_count", 0)
        summary["delivery_counts_match"] = delivery.get("counts_match", True)
        return JsonResponse({"ok": True, "data": summary})
    except DigikalaAPIError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
