from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import Brand, Color, Size, StockBalance, StockLocation


DARMA_STOCK = {
    "M": {
        "مشکی": 312, "سفید": 240, "سرمه ای": 146, "صورتی": 263, "کرم": 348,
        "قرمز": 153, "زرد": -4, "طوسی": 100, "راه راه": 218, "راه راه طوسی": 218,
        "برعکس مشکی": 47, "برعکس سفید": 45, "برعکس سرمه ای": 0,
    },
    "L": {
        "مشکی": 664, "سفید": 251, "سرمه ای": 656, "صورتی": 690, "کرم": 1009,
        "قرمز": -34, "زرد": 80, "طوسی": 101, "راه راه": 107, "راه راه طوسی": 313,
        "برعکس مشکی": 83, "برعکس سفید": 72, "برعکس سرمه ای": 71,
    },
    "XL": {
        "مشکی": 716, "سفید": 164, "سرمه ای": 1270, "صورتی": 94, "کرم": 616,
        "قرمز": -29, "زرد": 0, "طوسی": 32, "راه راه": 39, "راه راه طوسی": 444,
        "برعکس مشکی": 79, "برعکس سفید": 38, "برعکس سرمه ای": 67,
    },
    "XXL": {
        "مشکی": 791, "سفید": 351, "سرمه ای": 903, "صورتی": 547, "کرم": 702,
        "قرمز": -39, "زرد": 0, "طوسی": -3, "راه راه": 105, "راه راه طوسی": 439,
        "برعکس مشکی": 85, "برعکس سفید": 121, "برعکس سرمه ای": 72,
    },
    "3XL": {
        "مشکی": 95, "سفید": 152, "سرمه ای": 298, "صورتی": 53, "کرم": 124,
        "قرمز": 0, "زرد": 0, "طوسی": 10, "راه راه": 41, "راه راه طوسی": 100,
        "برعکس مشکی": 87, "برعکس سفید": 84, "برعکس سرمه ای": 76,
    },
}

EXPECTED_SIZE_TOTALS = {"M": 2086, "L": 4063, "XL": 3530, "XXL": 4074, "3XL": 1120}
EXPECTED_TOTAL = 14873


class Command(BaseCommand):
    help = "Delete all DARMA app data (not auth users), rebuild base masters, and load the supplied Darma stock into Home."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Required acknowledgement for destructive reset")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options.get("yes"):
            raise CommandError("This command deletes ALL business data. Run again with --yes.")

        # PostgreSQL production DB: wipe only this app's tables. Auth users/superuser,
        # Django migrations and sessions are untouched.
        tables = [t for t in connection.introspection.table_names() if t.startswith("core_")]
        if not tables:
            raise CommandError("No core_* tables were found; refusing to continue.")

        quoted = ", ".join(connection.ops.quote_name(t) for t in tables)
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")

        # Recreate only stable base data.
        call_command("seed_base", verbosity=0)

        darma = Brand.objects.get(name="دارما")
        home = StockLocation.objects.get(key=StockLocation.HOME)
        khorshid = StockLocation.objects.get(key=StockLocation.KHORSHID)

        loaded_total = 0
        for size_name, color_values in DARMA_STOCK.items():
            size = Size.objects.get(name=size_name)
            size_total = 0
            for color_name, qty in color_values.items():
                color = Color.objects.get(name=color_name)
                StockBalance.objects.update_or_create(
                    brand=darma, size=size, color=color, location=home,
                    defaults={"qty": qty},
                )
                # Explicit zero row for Khorshid so the current state is unambiguous.
                StockBalance.objects.update_or_create(
                    brand=darma, size=size, color=color, location=khorshid,
                    defaults={"qty": 0},
                )
                size_total += qty
                loaded_total += qty

            expected = EXPECTED_SIZE_TOTALS[size_name]
            if size_total != expected:
                raise CommandError(f"Inventory validation failed for {size_name}: {size_total} != {expected}")

        if loaded_total != EXPECTED_TOTAL:
            raise CommandError(f"Inventory validation failed: {loaded_total} != {EXPECTED_TOTAL}")

        self.stdout.write(self.style.SUCCESS("Business data reset complete."))
        self.stdout.write(self.style.SUCCESS("Correct Darma color/model catalog loaded."))
        for size_name in ["M", "L", "XL", "XXL", "3XL"]:
            self.stdout.write(f"  {size_name}: {EXPECTED_SIZE_TOTALS[size_name]}")
        self.stdout.write(self.style.SUCCESS(f"Darma Home total: {loaded_total}"))
        self.stdout.write(self.style.SUCCESS("Khorshid total: 0"))
        self.stdout.write(self.style.WARNING("Negative quantities from the workbook were preserved exactly."))
