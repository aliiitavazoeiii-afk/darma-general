"""One-time, idempotent price copy from today's Digikala catalog to Tapsi.

No Digikala prices or historical Tapsi orders are touched.
Existing Tapsi prices ALWAYS win, including rules effective before today.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ProductSize, TapsiPriceRule
from core.sale_price_v60 import sale_price_for
from core.tapsi_shop_v138 import effective_prices


class Command(BaseCommand):
    help = "Seed currently-unpriced active Tapsi SKUs from today's Digikala prices without overwriting Tapsi overrides"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Audit only; do not write")

    def handle(self, *args, **options):
        today = date.today()
        product_sizes = list(
            ProductSize.objects.filter(active=True, product__active=True, product__brand__active=True)
            .select_related("product__brand", "size")
            .order_by("product__brand__name", "product__code", "size__sort_order", "id")
        )
        existing = effective_prices([ps.pk for ps in product_sizes], today)
        to_seed = []
        already = 0
        skipped_without_dg = 0
        for ps in product_sizes:
            if int(existing.get(ps.pk, 0)) > 0:
                already += 1
                continue
            price = int(sale_price_for(ps, today) or 0)
            if price <= 0:
                skipped_without_dg += 1
                continue
            to_seed.append(TapsiPriceRule(
                product_size=ps, effective_from=today, price=price
            ))

        if not options["dry_run"]:
            with transaction.atomic():
                # Creation at the exact date is safe and repeatable.
                for rule in to_seed:
                    TapsiPriceRule.objects.get_or_create(
                        product_size=rule.product_size,
                        effective_from=rule.effective_from,
                        defaults={"price": rule.price},
                    )
        self.stdout.write(
            f"TAPSI_SEED_V140 mode={'DRY_RUN' if options['dry_run'] else 'APPLIED'} "
            f"date={today.isoformat()} active_sizes={len(product_sizes)} "
            f"copied={len(to_seed)} existing_tapsi_unchanged={already} "
            f"without_digikala_price={skipped_without_dg}"
        )
