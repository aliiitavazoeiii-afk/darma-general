"""V128 read-only route validation, no stock POST or production mutations."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import resolve, reverse

from core import inventory_operations_v16, inventory_transfer_v123


class Command(BaseCommand):
    help = "Read-only check: inventory operations GET/POST share canonical route."

    def handle(self, *args, **kwargs):
        target = reverse("inventory_operations")
        old = reverse("inventory_transfer_direction_v123")
        assert target == "/inventory/operations/"
        assert old == "/inventory/operations/transfer-direction/"
        if resolve(target).func is not inventory_operations_v16.inventory_operations:
            raise RuntimeError("Canonical inventory operations route not resolved")
        if resolve(old).func is not inventory_transfer_v123.inventory_transfer_direction:
            raise RuntimeError("Legacy explicit transfer URL unexpectedly removed")
        request = RequestFactory().post(
            target, {"action": "transfer"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_ACCEPT="application/json",
        )
        request.user = AnonymousUser()
        response = resolve(target).func(request)
        if response.status_code != 401 or json.loads(response.content).get("code") != "authentication_required":
            raise RuntimeError("Canonical transfer AJAX missing typed auth 401")
        csrf = inventory_transfer_v123.csrf_failure(request, "synthetic read-only check")
        if csrf.status_code != 403 or json.loads(csrf.content).get("code") != "csrf_failed":
            raise RuntimeError("Canonical transfer AJAX missing typed CSRF 403")
        if settings.CSRF_FAILURE_VIEW != "core.inventory_transfer_v123.csrf_failure":
            raise RuntimeError("CSRF rejection handler changed")
        source = (Path(settings.BASE_DIR) / "templates/core/inventory_operations.html").read_text("utf-8")
        required = (
            "action=\"{% url 'inventory_operations' %}\"",
            "new FormData(transferForm)",
            "response.headers.get('Content-Type')",
            "transferForm.querySelectorAll('input[name^=\"qty_\"]')",
        )
        for marker in required:
            if marker not in source:
                raise RuntimeError(f"Canonical transfer HTML guard missing: {marker}")
        self.stdout.write("CANONICAL_TRANSFER_GET_POST=/inventory/operations/")
        self.stdout.write("LEGACY_TRANSFER_POST=/inventory/operations/transfer-direction/")
        self.stdout.write(self.style.SUCCESS("SUCCESS: V128 SAME-PAGE TRANSFER ROUTE READ-ONLY AUDIT PASSED"))
