from django.core.management.base import BaseCommand, CommandError

from core import daily_order_import_v12 as v12
from core import daily_order_views_v8
from core.daily_order_import_v23 import _status_is_delivery
from core.models import ProductSize


class Command(BaseCommand):
    help = "Verify Digikala delivery status compatibility and strict title-only product resolution."

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

        by_key = v12._product_maps_v19()

        # Real regression from the user's export: seller code says rah220 while
        # title says D-220. Title must be the only product identity source.
        conflict_title = (
            "شورت زنانه دارما مدل D-220 مجموعه 3 عددی | 46-48 | چند رنگ | "
            "گارانتی اصالت و سلامت فیزیکی کالا"
        )
        product = v12._resolve_product_v12("rah220", conflict_title, by_key)
        size_name = v12._resolve_size(conflict_title)
        if not product or product.brand.name != "دارما" or product.code != "D 220":
            shown = None if not product else f"{product.brand.name}/{product.code}"
            errors.append(f"title-only regression failed: expected دارما/D 220, got {shown}")
        if size_name != "4XL":
            errors.append(f"46-48 size regression failed: expected 4XL, got {size_name}")
        if product and size_name:
            if not ProductSize.objects.filter(product=product, size__name=size_name, active=True).exists():
                errors.append("resolved target دارما/D 220/4XL is not active in ProductSize")

        reverse_conflict_title = (
            "شورت زنانه دارما مدل rah-220 مجموعه 3 عددی | 3XL | چند رنگ | "
            "گارانتی اصالت و سلامت فیزیکی کالا"
        )
        product = v12._resolve_product_v12("220", reverse_conflict_title, by_key)
        if not product or product.brand.name != "دارما" or product.code != "rah-220":
            shown = None if not product else f"{product.brand.name}/{product.code}"
            errors.append(f"reverse title-only regression failed: expected دارما/rah-220, got {shown}")

        # Seller code is never allowed to rescue a missing/unknown title model.
        no_model_title = "شورت زنانه دارما | 46-48 | چند رنگ | گارانتی اصالت و سلامت فیزیکی کالا"
        if v12._resolve_product_v12("rah220", no_model_title, by_key) is not None:
            errors.append("seller-code fallback is still active when title has no model")

        unknown_title = "شورت زنانه دارما مدل UNKNOWN-999 مجموعه 3 عددی | 46-48 | چند رنگ"
        if v12._resolve_product_v12("rah220", unknown_title, by_key) is not None:
            errors.append("seller-code fallback is still active for unknown title model")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("V23 DELIVERY IMPORT CHECK FAILED")

        self.stdout.write("accepted current Digikala status: اماده ارسال/تحویل")
        self.stdout.write("negative return/cancel statuses remain blocked")
        self.stdout.write("conflicting seller code rah220 + title D-220 resolves to D 220 / 4XL")
        self.stdout.write("resolved D 220 / 4XL target is active")
        self.stdout.write("seller-code column is ignored for product identity")
        self.stdout.write("missing/unknown title model fails instead of falling back to seller code")
        self.stdout.write(self.style.SUCCESS("V23 DELIVERY IMPORT CHECK OK"))