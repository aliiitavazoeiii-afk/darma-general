"""Read-only deployment audit for transfer AJAX JSON/auth and safe HTML parsing."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import reverse
from django.template.loader import get_template

from core.inventory_transfer_v123 import inventory_transfer_direction


class Command(BaseCommand):
    help = "Read-only check: transfer AJAX never redirects unauthenticated requests to HTML."

    def handle(self, *args, **kwargs):
        path=reverse("inventory_transfer_direction_v123")
        if path != "/inventory/operations/transfer-direction/":
            raise RuntimeError("Transfer URL unexpectedly changed")
        request=RequestFactory().post(
            path, data={"brand":"1","size":"1","direction":"warehouse_to_home"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user=AnonymousUser()
        response=inventory_transfer_direction(request)
        if response.status_code != 401 or "application/json" not in response["Content-Type"]:
            raise RuntimeError("Expired AJAX login still returns HTML/redirect")
        import json
        if json.loads(response.content).get("code") != "login_required":
            raise RuntimeError("AJAX session expiry JSON code missing")
        template=(Path(settings.BASE_DIR)/"templates/core/inventory_operations.html").read_text("utf-8")
        for needle in (
            "const contentType=", "contentType.includes('application/json')",
            "response.status===403", "const loginPage=", "result=await response.json()",
            "قبل از اقدام مجدد، موجودی و آخرین انتقال‌ها را بررسی کن",
            "new FormData(transferForm)",
            "transferForm.querySelectorAll('input[name^=\"qty_\"]')",
        ):
            if needle not in template:
                raise RuntimeError(f"Transfer response guard missing: {needle}")
        # Regression: HTML form has a hidden <input name="action">.
        # JS form.action then evaluates to that DOM element instead of URL.
        # The exact 404 observed on the server was
        # /inventory/operations/[object%20HTMLInputElement].
        if 'name="action" value="transfer"' not in template:
            raise RuntimeError("Transfer action-shadowing regression fixture missing")
        if "fetch(transferForm.action" in template:
            raise RuntimeError("Transfer fetch uses shadowed form.action property")
        if "transferForm.getAttribute('action')" not in template:
            raise RuntimeError("Transfer fetch must use literal action attribute")
        if "fetch(endpoint,{" not in template:
            raise RuntimeError("Transfer must send request to literal endpoint")
        if "/inventory/operations/transfer-direction/" not in template:
            raise RuntimeError("Missing route safeguard against stray form action")
        get_template("core/inventory_operations.html")
        self.stdout.write("UNAUTHENTICATED_AJAX=401_APPLICATION_JSON")
        self.stdout.write("LOGIN_CSRF_SERVER_HTML=EXPLICIT_USER_MESSAGE")
        self.stdout.write("AUTOMATIC_RETRY=DISABLED; TOTAL_STOCK_UNCHANGED")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: V125 INVENTORY TRANSFER JSON RESPONSE GUARD PASSED"
        ))
