from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .digikala_client_v40 import DigikalaAPIError, get_summary


@login_required
def digikala_home(request):
    force = request.GET.get("refresh") == "1"
    try:
        summary = get_summary(force=force)
        page_error = ""
    except DigikalaAPIError as exc:
        summary = {"connected": False, "errors": {"api": str(exc)}}
        page_error = str(exc)
    return render(
        request,
        "core/digikala_v40.html",
        {
            "digikala": summary,
            "digikala_error": page_error,
        },
    )


@login_required
def digikala_summary(request):
    try:
        summary = get_summary(force=request.GET.get("refresh") == "1")
        return JsonResponse({"ok": True, "data": summary})
    except DigikalaAPIError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
