from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from core.inventory_v19 import _sizes_for_brand
from core.material_report_v19 import NOVANI_OUTPUT_SIZES, _output_sizes_for_brand
from core.models import Brand, Size, StockBalance, StockLocation


EXPECTED_NOVANI = ["S", "M", "L", "XL", "XXL", "3XL"]
EXPECTED_DARMA = ["M", "L", "XL", "XXL", "3XL", "4XL"]
EXPECTED_TAKVIN = ["M", "L", "XL", "XXL"]


class Command(BaseCommand):
    help = "Verify Novani material-report sizes and inventory isolation. Read only."

    def handle(self, *args, **options):
        names = list(Size.objects.order_by("sort_order", "id").values_list("name", flat=True))
        if "S" not in names:
            raise CommandError("Size S is missing; migration was not applied")

        novani = Brand.objects.get(name="Novani")
        darma = Brand.objects.get(name="دارما")
        takvin = Brand.objects.get(name="تکوین")

        if [x.name for x in _sizes_for_brand(novani)] != EXPECTED_NOVANI:
            raise CommandError("Novani inventory sizes mismatch")
        if [x.name for x in _sizes_for_brand(darma)] != EXPECTED_DARMA:
            raise CommandError("Darma inventory sizes changed unexpectedly")
        if [x.name for x in _sizes_for_brand(takvin)] != EXPECTED_TAKVIN:
            raise CommandError("Takvin inventory sizes changed unexpectedly")

        if [label for _key, label in _output_sizes_for_brand(novani)] != EXPECTED_NOVANI:
            raise CommandError("Novani material-report sizes mismatch")
        if [label for _key, label in _output_sizes_for_brand(darma)] != EXPECTED_DARMA:
            raise CommandError("Darma material-report sizes changed unexpectedly")
        if list(NOVANI_OUTPUT_SIZES) != [
            ("s", "S"), ("m", "M"), ("l", "L"), ("xl", "XL"), ("xxl", "XXL"), ("3xl", "3XL")
        ]:
            raise CommandError("Novani size constants mismatch")

        home = StockLocation.objects.get(key=StockLocation.HOME)
        s = Size.objects.get(name="S")
        novani_s_rows = StockBalance.objects.filter(brand=novani, size=s, location=home).count()
        darma_s_qty = int(StockBalance.objects.filter(brand=darma, size=s).aggregate(v=Sum("qty"))["v"] or 0)
        takvin_s_qty = int(StockBalance.objects.filter(brand=takvin, size=s).aggregate(v=Sum("qty"))["v"] or 0)

        if novani_s_rows <= 0:
            raise CommandError("Novani S stock rows were not seeded")
        if darma_s_qty != 0 or takvin_s_qty != 0:
            raise CommandError(f"S stock leaked to another brand: Darma={darma_s_qty}, Takvin={takvin_s_qty}")

        self.stdout.write(f"Novani sizes: {EXPECTED_NOVANI}")
        self.stdout.write(f"Darma sizes unchanged: {EXPECTED_DARMA}")
        self.stdout.write(f"Takvin sizes unchanged: {EXPECTED_TAKVIN}")
        self.stdout.write(f"Novani S rows: {novani_s_rows}")
        self.stdout.write("NOVANI MATERIAL V33 CHECK OK")
