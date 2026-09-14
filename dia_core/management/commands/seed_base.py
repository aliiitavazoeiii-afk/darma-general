from django.core.management.base import BaseCommand

from dia_core.models import AppSetting, StockLocation


class Command(BaseCommand):
    help = "Create only generic Dia Gallery base rows. No products, sales, stock, accounts or private business data."

    def handle(self, *args, **kwargs):
        StockLocation.objects.get_or_create(key="main", defaults={"title": "موجودی اصلی", "active": True})

        defaults = {
            "digikala_commission_percent": ("24", "کمیسیون دیجی‌کالا (%)"),
            "digikala_processing_percent": ("7", "پردازش و ارسال (%)"),
            "digikala_processing_floor": ("36000", "حداقل پردازش و ارسال"),
            "digikala_vat_percent": ("10", "مالیات ارزش افزوده (%)"),
            "digikala_floor_taxable_part": ("18000", "بخش مشمول مالیات در کف پردازش"),
            "low_stock_threshold": ("10", "حد هشدار موجودی"),
        }
        for key, (value, label) in defaults.items():
            AppSetting.objects.get_or_create(key=key, defaults={"value": value, "label": label})

        self.stdout.write(self.style.SUCCESS("Dia Gallery base ready: no business catalog/data seeded"))
