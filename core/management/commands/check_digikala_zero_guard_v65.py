from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from core.digikala_client_v40 import DigikalaAPIError
from core.digikala_zero_guard_v65 import (
    ZERO_STATE_PREFIX,
    _marker_key,
    _resolved_identity,
    affected_variants_for_cell,
    get_variant_rows,
    scan_zero_transitions,
    stock_cell_total,
)
from core.models import AppSetting, Brand, ProductSize, StockBalance


class Command(BaseCommand):
    help = "V65 safe regression for Darma zero-stock Telegram alerts and read-only Digikala mapping."

    def add_arguments(self, parser):
        parser.add_argument(
            "--live-map",
            action="store_true",
            help="GET current Digikala variants and print read-only mapping summary. No write endpoint is called.",
        )
        parser.add_argument(
            "--allow-network-failure",
            action="store_true",
            help="For safe deploy only: if Digikala GET times out, report deferred mapping and exit successfully. Writes remain absent.",
        )

    def _source_checks(self):
        base = Path(settings.BASE_DIR)
        required = {
            "core/digikala_zero_guard_v65.py": (
                '"/open-api/v1/variants"',
                "resolve_product_from_title",
                "_resolve_size",
                "write_enabled",
                "affected_variants_for_cell",
            ),
            "core/telegram_inventory_alerts_v20.py": (
                "dkz:preview:",
                "غیرفعال‌سازی فعلاً قفل است",
                "maybe_send_zero_guard_alerts",
                "scan_zero_transitions",
            ),
            "compose.telegram.yml": (
                "/opt/darma-secrets/digikala/runtime:/run/secrets/digikala",
            ),
        }
        for relative, markers in required.items():
            text = (base / relative).read_text(encoding="utf-8")
            for marker in markers:
                if marker not in text:
                    raise CommandError(f"V65 source marker missing: {relative}: {marker}")

        guard_source = (base / "core" / "digikala_zero_guard_v65.py").read_text(encoding="utf-8")
        for forbidden in (
            "/activation",
            "/seller-stock",
            '"PATCH"',
            "'PATCH'",
            '"PUT"',
            "'PUT'",
            '"POST"',
            "'POST'",
        ):
            if forbidden in guard_source:
                raise CommandError(
                    f"V65 SAFE MODE VIOLATION: write marker found in digikala_zero_guard_v65.py: {forbidden}"
                )

    def _synthetic_mapping_check(self):
        ps = (
            ProductSize.objects.filter(
                product__brand__name="دارما",
                product__active=True,
                active=True,
                product__composition__qty__gt=0,
            )
            .select_related("product", "size")
            .prefetch_related("product__composition__color")
            .order_by("product__code", "size__sort_order", "id")
            .distinct()
            .first()
        )
        if ps is None:
            raise CommandError("V65 mapping regression needs one active fixed-composition Darma ProductSize")

        comp = next((x for x in ps.product.composition.all() if int(x.qty or 0) > 0), None)
        if comp is None:
            raise CommandError("V65 mapping regression could not find a Darma composition color")

        fake = {
            "id": 987654321,
            "product_variant_id": 123456789,
            "supplier_code": "must-not-identify-product",
            "title": (
                f"شورت زنانه دارما مدل {ps.product.code} مجموعه {int(ps.product.pack_qty or 1)} عددی "
                f"| {ps.size.name} | {comp.color.name}"
            ),
            "product_title": "",
            "active": True,
            "marketplace_seller_stock": 7,
            "warehouse_stock": 2,
        }
        preview = affected_variants_for_cell(ps.size_id, comp.color_id, rows=[fake])
        affected = preview["affected"]
        if len(affected) != 1:
            raise CommandError(f"V65 synthetic title mapping failed: {affected}")
        row = affected[0]
        if row["product_code"] != ps.product.code or row["size"] != ps.size.name:
            raise CommandError("V65 synthetic mapping resolved to the wrong Darma product/size")
        if row["seller_variant_id"] != 987654321 or row["dkpc"] != 123456789:
            raise CommandError("V65 variant identifiers were not preserved")

        wrong_size = dict(fake)
        wrong_size["id"] = 987654322
        wrong_size["product_variant_id"] = 123456790
        wrong_size["title"] = fake["title"].replace(f"| {ps.size.name} |", "| __NO_SIZE__ |")
        wrong_preview = affected_variants_for_cell(ps.size_id, comp.color_id, rows=[wrong_size])
        if wrong_preview["affected"]:
            raise CommandError("V65 mapped a Digikala variant whose size could not be resolved")

        product, size_name, _title = _resolved_identity(fake)
        if product is None or product.id != ps.product_id or size_name != ps.size.name:
            raise CommandError("V65 identity resolver did not use current title-only Darma resolver")

        return ps, comp.color

    def _zero_transition_rollback_check(self):
        positive = (
            StockBalance.objects.filter(
                brand__name="دارما",
                qty__gt=0,
                size__name__in=["M", "L", "XL", "XXL", "3XL", "4XL"],
            )
            .select_related("size", "color")
            .order_by("-qty", "id")
            .first()
        )
        if positive is None:
            raise CommandError("V65 zero transition regression needs one positive Darma stock cell")

        before_total = int(
            StockBalance.objects.filter(
                brand=positive.brand,
                size=positive.size,
                color=positive.color,
            ).aggregate(v=Sum("qty"))["v"]
            or 0
        )
        marker_count_before = AppSetting.objects.filter(key__startswith=ZERO_STATE_PREFIX).count()

        with transaction.atomic():
            StockBalance.objects.filter(
                brand=positive.brand,
                size=positive.size,
                color=positive.color,
            ).update(qty=0)
            AppSetting.objects.update_or_create(
                key=_marker_key(positive.size_id, positive.color_id),
                defaults={"value": "positive", "label": "[v65 regression]"},
            )
            transitions = scan_zero_transitions(bootstrap=False)
            matches = [
                cell
                for cell in transitions
                if cell["size"].id == positive.size_id and cell["color"].id == positive.color_id
            ]
            if len(matches) != 1:
                raise CommandError("V65 did not emit exactly one positive->zero transition")
            if int(matches[0]["total"]) != 0:
                raise CommandError("V65 zero transition reported a non-zero total")
            transaction.set_rollback(True)

        after_total = int(
            StockBalance.objects.filter(
                brand=positive.brand,
                size=positive.size,
                color=positive.color,
            ).aggregate(v=Sum("qty"))["v"]
            or 0
        )
        if after_total != before_total:
            raise CommandError("V65 rollback test changed Darma stock persistently")
        if AppSetting.objects.filter(key__startswith=ZERO_STATE_PREFIX).count() != marker_count_before:
            raise CommandError("V65 rollback test left zero-guard state markers behind")

    def _live_map(self):
        rows = get_variant_rows(force=True)
        resolved = 0
        darma = 0
        unresolved_darma_like = 0
        by_code = {}

        for row in rows:
            product, size_name, _title = _resolved_identity(row)
            if product is not None and size_name:
                resolved += 1
                if product.brand.name == "دارما":
                    darma += 1
                    key = (product.code, size_name)
                    by_code[key] = by_code.get(key, 0) + 1
            elif "دارما" in " ".join(
                str(row.get(key) or "") for key in ("title", "product_title")
            ):
                unresolved_darma_like += 1

        self.stdout.write(f"LIVE DIGIKALA VARIANTS READ = {len(rows)}")
        self.stdout.write(f"TITLE/SIZE RESOLVED = {resolved}")
        self.stdout.write(f"DARMA VARIANTS RESOLVED = {darma}")
        self.stdout.write(f"UNRESOLVED DARMA-LIKE TITLES = {unresolved_darma_like}")

        for (code, size_name), count in sorted(by_code.items())[:80]:
            self.stdout.write(f"MAP {code} / {size_name} = {count} variant row(s)")

        zero_cells = []
        brand = Brand.objects.get(name="دارما")
        pairs = (
            StockBalance.objects.filter(
                brand=brand,
                size__name__in=["M", "L", "XL", "XXL", "3XL", "4XL"],
            )
            .values("size_id", "color_id", "size__name", "color__name")
            .annotate(total=Sum("qty"))
            .order_by("color__name", "size__sort_order", "size_id")
        )
        for pair in pairs:
            if int(pair["total"] or 0) <= 0:
                zero_cells.append(pair)

        self.stdout.write(f"CURRENT DARMA ZERO/NEGATIVE CELLS = {len(zero_cells)}")
        for pair in zero_cells[:25]:
            preview = affected_variants_for_cell(
                pair["size_id"],
                pair["color_id"],
                rows=rows,
            )
            self.stdout.write(
                f"ZERO {pair['color__name']} / {pair['size__name']} -> "
                f"matched={len(preview['affected'])} active={len(preview['active_affected'])} "
                f"unresolved_darma_like={preview['unresolved_darma_like']}"
            )
        if len(zero_cells) > 25:
            self.stdout.write(f"... {len(zero_cells) - 25} more zero cells omitted")

        self.stdout.write("DIGIKALA WRITE CALLS = 0")

    def handle(self, *args, **options):
        self._source_checks()
        ps, color = self._synthetic_mapping_check()
        self._zero_transition_rollback_check()

        self.stdout.write(
            f"SYNTHETIC TITLE-ONLY MAPPING OK = {ps.product.code} / {ps.size.name} / {color.name}"
        )
        self.stdout.write("ZERO TRANSITION ROLLBACK CHECK OK")
        self.stdout.write("TELEGRAM APPROVAL FLOW = PREVIEW ONLY")
        self.stdout.write("DIGIKALA WRITE MODE = ABSENT / LOCKED")

        if options["live_map"]:
            try:
                self._live_map()
            except DigikalaAPIError as exc:
                if not options["allow_network_failure"]:
                    raise
                self.stdout.write(
                    self.style.WARNING(
                        "LIVE DIGIKALA MAP DEFERRED: network/API read failed after safe retries. "
                        f"{exc}"
                    )
                )
                self.stdout.write("DIGIKALA WRITE CALLS = 0")
                self.stdout.write("BOT PREVIEW WILL RETRY LATER; NO LISTING WAS CHANGED")

        self.stdout.write("NO BUSINESS DATA CHANGED")
        self.stdout.write(self.style.SUCCESS("SUCCESS: DIGIKALA ZERO GUARD V65 CHECK PASSED"))
