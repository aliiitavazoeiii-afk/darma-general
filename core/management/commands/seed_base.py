from django.core.management.base import BaseCommand
from core.models import Account, AppSetting, Brand, Color, ProductSize, Size, StockLocation


class Command(BaseCommand):
    help = "Create base master data without fake inventory or sales."

    def handle(self, *args, **kwargs):
        Brand.objects.get_or_create(name="تکوین")
        Brand.objects.get_or_create(name="دارما")
        for i, name in enumerate(["M", "L", "XL", "XXL", "3XL", "4XL"]):
            Size.objects.get_or_create(name=name, defaults={"sort_order": i})
        for name, code in [("مشکی", "B"), ("سفید", "W"), ("سرمه‌ای", "S"), ("صورتی", "P"), ("کرم", "K"), ("قرمز", "R"), ("طوسی", "G"), ("راه راه", "STR")]:
            Color.objects.get_or_create(name=name, defaults={"code": code})
        StockLocation.objects.get_or_create(key="home", defaults={"title": "خانه"})
        StockLocation.objects.get_or_create(key="khorshid", defaults={"title": "انبار خورشید"})
        for key, title in [("melat", "ملت"), ("mofid", "مفید"), ("digikala", "طلب دیجی‌کالا"), ("pedram", "حساب پدرام"), ("takvin", "بدهی تکوین")]:
            Account.objects.get_or_create(key=key, defaults={"title": title})
        defaults = {
            "digikala_commission_percent": ("24", "کمیسیون دیجی‌کالا (%)"),
            "digikala_processing_percent": ("7", "پردازش و ارسال (%)"),
            "digikala_processing_floor": ("36000", "حداقل پردازش و ارسال"),
            "digikala_vat_percent": ("10", "مالیات ارزش افزوده (%)"),
            "digikala_floor_taxable_part": ("18000", "بخش مشمول مالیات در کف پردازش"),
            "pedram_dozen_wage": ("110000", "مزد هر جین پدرام"),
            "darma_accounting_unit_cost": ("61000", "بهای محاسباتی هر شورت دارما"),
        }
        for key, (value, label) in defaults.items():
            AppSetting.objects.get_or_create(key=key, defaults={"value": value, "label": label})
        ProductSize.objects.filter(product__brand__name="تکوین", size__name="4XL").update(active=False)
        self.stdout.write(self.style.SUCCESS("Base data ready"))
