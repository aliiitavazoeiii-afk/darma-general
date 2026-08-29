from django.core.management.base import BaseCommand, CommandError

from core import daily_order_views_v8
from core.daily_order_import_v23 import _status_is_delivery


class Command(BaseCommand):
    help = "Verify Digikala delivery status compatibility for v23."

    def handle(self, *args, **options):
        errors = []

        accepted = [
            "",
            "دریافت شده",
            "دریافت‌شده",
            "اماده ارسال/تحویل",
            "آماده ارسال/تحویل",
            "آماده ارسال / تحویل",
        ]
        rejected = [
            "مرجوع شده",
            "لغو ارسال/تحویل",
            "عدم تحویل",
            "عدم ارسال",
            "ارسال ناموفق",
            "رد شده",
        ]

        for value in accepted:
            if not _status_is_delivery(value):
                errors.append(f"should accept status: {value!r}")
        for value in rejected:
            if _status_is_delivery(value):
                errors.append(f"should reject status: {value!r}")

        module = getattr(daily_order_views_v8.apply_delivery_report, "__module__", "")
        if module != "core.daily_order_import_v23":
            errors.append(f"daily upload engine is {module}, expected core.daily_order_import_v23")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("V23 DELIVERY IMPORT CHECK FAILED")

        self.stdout.write("accepted current Digikala status: اماده ارسال/تحویل")
        self.stdout.write("negative return/cancel statuses remain blocked")
        self.stdout.write(self.style.SUCCESS("V23 DELIVERY IMPORT CHECK OK"))
