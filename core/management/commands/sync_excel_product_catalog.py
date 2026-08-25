from django.core.management.base import BaseCommand
from django.db import transaction

from core.product_catalog import sync_catalog


class Command(BaseCommand):
    help = "Create/update Darma and Takvin product codes and fixed color compositions from the legacy Excel catalog."

    @transaction.atomic
    def handle(self, *args, **options):
        summary = sync_catalog()
        for brand_name, data in summary.items():
            self.stdout.write(
                f"{brand_name}: total={data['total']} created={data['created']} updated={data['updated']}"
            )
        self.stdout.write(self.style.SUCCESS("Excel product catalog synced"))
