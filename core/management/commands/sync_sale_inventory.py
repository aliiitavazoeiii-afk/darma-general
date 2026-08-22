from django.core.management.base import BaseCommand
from django.db import models

from core.models import SaleLine
from core.services import sync_sale_line_inventory


class Command(BaseCommand):
    help = "Apply any sale quantities that have not yet been reflected in inventory."

    def handle(self, *args, **options):
        pending = SaleLine.objects.exclude(quantity=models.F("inventory_applied_quantity"))
        applied = 0
        skipped = 0
        for line in pending.iterator():
            result = sync_sale_line_inventory(line)
            if result.get("applied"):
                applied += 1
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SaleLine {line.id} skipped: {result.get('message', 'unknown reason')}"))
        self.stdout.write(self.style.SUCCESS(f"Sale inventory synced: {applied}; skipped: {skipped}"))
