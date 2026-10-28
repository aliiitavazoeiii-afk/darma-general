"""V127 production-safe transport audit. No business-data mutations."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import resolve, reverse

from core import inventory_transfer_v123 as transfer


class Command(BaseCommand):
    help = "Read-only audit of AJAX stock transfer route, authentication, CSRF and browser guard."

    def handle(self, *args, **kwargs):
        route = reverse("inventory_transfer_direction_v123")
        if route != "/inventory/operations/transfer-direction/":
            raise RuntimeError("Stock transfer URL changed")
        func = resolve(route).func
        if func is not transfer.inventory_transfer_direction:
            raise RuntimeError("Transfer URL is not wired to the approved V127 view")
        req = RequestFactory().post(
            route, {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        req.user = AnonymousUser()
        response = func(req)
        if response.status_code != 401 or json.loads(response.content)["code"] != "authentication_required":
            raise RuntimeError("Unauthenticated AJAX must receive JSON 401, never HTML redirect")
        csrf_response = transfer.csrf_failure(req, "read-only synthetic check")
        if (csrf_response.status_code != 403
                or json.loads(csrf_response.content)["code"] != "csrf_failed"):
            raise RuntimeError("CSRF failure must return JSON 403 on AJAX transfer")
        if settings.CSRF_FAILURE_VIEW != "core.inventory_transfer_v123.csrf_failure":
            raise RuntimeError("Django CSRF failure view not configured")
        source = (Path(settings.BASE_DIR) / "templates/core/inventory_operations.html").read_text("utf-8")
        for marker in (
            "'Accept':'application/json'",
            "response.headers.get('Content-Type')",
            "response.redirected",
            "response.status===401",
            "response.status===403",
            "قبل از ثبت مجدد",
            "new FormData(transferForm)",
        ):
            if marker not in source:
                raise RuntimeError(f"Missing AJAX safety check: {marker}")
        self.stdout.write("TRANSFER_AUTH_JSON=401 TRANSFER_CSRF_JSON=403")
        self.stdout.write("TRANSFER_HTML_DETECTION=OK; AUTOMATIC_RETRY=OFF; DB_WRITES=ZERO")
        self.stdout.write(self.style.SUCCESS("SUCCESS: V127 TRANSFER JSON TRANSPORT AUDIT PASSED"))
