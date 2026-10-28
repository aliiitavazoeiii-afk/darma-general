"""No-write production guard for HTMLFormElement.action shadowing regression."""
from pathlib import Path
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse


class Command(BaseCommand):
    help = "Verify JS fetch reads form action ATTRIBUTE, never shadowed input."

    def handle(self, *args, **options):
        route = reverse("inventory_operations")
        if route != "/inventory/operations/":
            raise RuntimeError("Operations route drift")
        text = (
            Path(settings.BASE_DIR) / "templates/core/inventory_operations.html"
        ).read_text(encoding="utf-8")
        if 'name="action" value="transfer"' not in text:
            raise RuntimeError("Expected hidden transfer action marker is missing")
        if 'action="{% url \'inventory_operations\' %}"' not in text:
            raise RuntimeError("Expected canonical form route is missing")
        if not re.search(
            r"fetch\(\s*transferForm\.getAttribute\(\s*['\"]action['\"]\s*\)",
            text
        ):
            raise RuntimeError("Transfer JS must POST to explicit action attribute")
        if re.search(r"fetch\(\s*transferForm\.action\b", text):
            raise RuntimeError("Name-shadowed form.action would POST to invalid URL")
        if "body:new FormData(transferForm)" not in text:
            raise RuntimeError("Transfer payload changed unexpectedly")
        self.stdout.write(f"TRANSFER_FORM_ACTION_URL={route}")
        self.stdout.write("FORM_INPUT_NAME_ACTION=SHADOWING_PREVENTED")
        self.stdout.write("DATA_WRITES=ZERO")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: V129 TRANSFER FORM ACTION SHADOWING GUARD PASSED"
        ))
