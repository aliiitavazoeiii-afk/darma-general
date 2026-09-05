from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.template.loader import get_template

from core.cost_accounting_v14 import snapshot_sale_line
from core.darma_cost_v55 import darma_cost_for, set_darma_cost_rule
from core.dia_gallery_v45 import sync_dia_gallery_sale
from core.final_services import sync_inventory_adjustment
from core.inventory_valuation_v17 import finished_inventory_value_v17
from core.models import (
    AccountEntry,
    AppSetting,
    Brand,
    DiaGallerySale,
    InventoryAdjustment,
    InventoryMovement,
    ProductSize,
    SaleDay,
    SaleLine,
    SaleSnapshot,
    StockBalance,
    StockLocation,
)


class Command(BaseCommand):
    help = "Transactional regression for the centralized date-effective Darma cost source V55."

    def _darma_qty(self):
        darma = Brand.objects.get(name="دارما")
        return int(StockBalance.objects.filter(brand=darma).aggregate(v=Sum("qty"))["v"] or 0)

    def _state(self):
        return {
            "finished": int(finished_inventory_value_v17()),
            "darma_qty": self._darma_qty(),
            "sales": SaleLine.objects.count(),
            "snapshots": SaleSnapshot.objects.count(),
            "dia": DiaGallerySale.objects.count(),
            "entries": AccountEntry.objects.count(),
            "adjustments": InventoryAdjustment.objects.count(),
            "movements": InventoryMovement.objects.count(),
            "settings": AppSetting.objects.count(),
        }

    def _free_day(self, start):
        candidate = start
        for _ in range(30):
            if not SaleDay.objects.filter(date=candidate).exists():
                return candidate
            candidate += timedelta(days=1)
        raise CommandError("could not find free V55 regression SaleDay")

    def handle(self, *args, **options):
        try:
            get_template("core/settings_rules_v17.html")
        except Exception as exc:
            raise CommandError(f"V55 settings template failed to compile: {exc}") from exc

        template_source = (Path(settings.BASE_DIR) / "templates" / "core" / "settings_rules_v17.html").read_text(encoding="utf-8")
        for marker in ("darma_cost_rule", "بهای تمام‌شده هر شورت دارما", "darma_delete_rule"):
            if marker not in template_source:
                raise CommandError(f"V55 settings marker missing: {marker}")

        before = self._state()

        with transaction.atomic():
            try:
                # 1) Date-effective rule resolution.
                first_date = date(2098, 1, 1)
                second_date = date(2098, 2, 1)
                set_darma_cost_rule(first_date, 61_000)
                set_darma_cost_rule(second_date, 67_000)
                if darma_cost_for(date(2098, 1, 15)) != 61_000:
                    raise CommandError("V55 first date-effective Darma rule did not resolve")
                if darma_cost_for(date(2098, 2, 15)) != 67_000:
                    raise CommandError("V55 second date-effective Darma rule did not resolve")

                darma = Brand.objects.get(name="دارما")
                darma_ps = (
                    ProductSize.objects.filter(
                        product__brand=darma,
                        product__active=True,
                        active=True,
                    )
                    .select_related("product", "size")
                    .order_by("id")
                    .first()
                )
                if darma_ps is None:
                    raise CommandError("V55 regression needs one active Darma ProductSize")

                test_date = self._free_day(date(2098, 2, 15))
                day = SaleDay.objects.create(date=test_date)
                line = SaleLine.objects.create(
                    day=day,
                    product_size=darma_ps,
                    quantity=1,
                    sale_price=max(1, int(darma_ps.default_sale_price or 100_000)),
                )
                snap = snapshot_sale_line(line, darma_ps, line.sale_price)
                if int(snap.unit_cost or 0) != 67_000:
                    raise CommandError(f"V55 Darma SaleSnapshot cost mismatch: {snap.unit_cost}")

                # 2) Anbaresh is Darma-backed and must freeze the same rule.
                anbaresh_ps = (
                    ProductSize.objects.filter(
                        product__brand__name="انبارش",
                        product__active=True,
                        active=True,
                    )
                    .select_related("product", "size")
                    .order_by("id")
                    .first()
                )
                if anbaresh_ps is None:
                    raise CommandError("V55 regression needs one active Anbaresh ProductSize")
                anbaresh_line = SaleLine.objects.create(
                    day=day,
                    product_size=anbaresh_ps,
                    quantity=1,
                    sale_price=max(1, int(anbaresh_ps.default_sale_price or 100_000)),
                )
                anbaresh_snap = snapshot_sale_line(anbaresh_line, anbaresh_ps, anbaresh_line.sale_price)
                if int(anbaresh_snap.unit_cost or 0) != 67_000:
                    raise CommandError(f"V55 Anbaresh SaleSnapshot cost mismatch: {anbaresh_snap.unit_cost}")

                # 3) Dia Gallery freezes the rule effective on its SaleDay.
                home = StockLocation.objects.get(key=StockLocation.HOME)
                stock = (
                    StockBalance.objects.filter(brand=darma, location=home)
                    .select_related("size", "color")
                    .order_by("id")
                    .first()
                )
                if stock is None:
                    raise CommandError("V55 regression needs one Darma HOME StockBalance")
                dia = DiaGallerySale.objects.create(
                    day=day,
                    size=stock.size,
                    color=stock.color,
                    quantity=1,
                    unit_price=71_000,
                )
                sync_dia_gallery_sale(dia)
                dia.refresh_from_db()
                if int(dia.unit_cost or 0) != 67_000:
                    raise CommandError(f"V55 Dia frozen Darma cost mismatch: {dia.unit_cost}")

                # 4) Current finished inventory must be a single Darma rate, not
                # InventoryModelCost. Revalue at today's rule and verify exact delta.
                current_before = int(finished_inventory_value_v17())
                old_rate = int(darma_cost_for(date.today()))
                darma_qty = self._darma_qty()
                new_rate = old_rate + 1_234
                set_darma_cost_rule(date.today(), new_rate)
                current_after = int(finished_inventory_value_v17())
                expected_after = current_before + darma_qty * (new_rate - old_rate)
                if current_after != expected_after:
                    raise CommandError(
                        f"V55 current inventory revaluation mismatch: {current_after} != {expected_after}"
                    )

                # 5) A standalone physical Darma return/adjustment must increase
                # finished value by exactly qty * central current rate.
                stock = StockBalance.objects.select_for_update().get(pk=stock.pk)
                value_before_return = int(finished_inventory_value_v17())
                adjustment = InventoryAdjustment.objects.create(
                    date=date.today(),
                    brand=darma,
                    size=stock.size,
                    color=stock.color,
                    location=home,
                    delta=2,
                    note="[standalone-return-v37] v55-regression",
                )
                sync_inventory_adjustment(adjustment)
                value_after_return = int(finished_inventory_value_v17())
                if value_after_return - value_before_return != 2 * new_rate:
                    raise CommandError(
                        "V55 Darma return valuation did not equal returned shorts * central Darma rate"
                    )
            finally:
                transaction.set_rollback(True)

        after = self._state()
        if before != after:
            raise CommandError(f"V55 regression left persistent business data changed: {before} != {after}")

        self.stdout.write("DARMA COST RULE V55 CHECK OK")
        self.stdout.write("DATE RULES: 61,000 -> 67,000 resolved by effective sale date")
        self.stdout.write("DARMA + ANBARESH SNAPSHOTS: canonical date-effective cost")
        self.stdout.write("DIA: canonical cost frozen on Dia sale date")
        self.stdout.write("CURRENT INVENTORY: all Darma stock revalues at one effective current rate")
        self.stdout.write("RETURNS/ADJUSTMENTS: exact qty * canonical current Darma rate")
        self.stdout.write("NO TEST DATA CHANGED")
        self.stdout.write(self.style.SUCCESS("SUCCESS: DARMA COST RULE V55 CHECK PASSED"))
