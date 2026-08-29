from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.template.loader import get_template
from django.urls import Resolver404, resolve

from core.calculator_v37 import _solve_sale_price
from core.finance import digikala_fee_for_unit
from core.finance_excel_v9 import digikala_receivable_total
from core.inventory_valuation_v17 import finished_inventory_value_v17
from core.models import AccountEntry, Brand, InventoryAdjustment, ProductComposition, ProductSize, SaleLine, StockBalance, StockLocation
from core.returns_v37 import _create_adjustment


class Command(BaseCommand):
    help = "Regression check for standalone returns and current-margin calculator v37."

    def _home_qty(self, brand, size, color):
        return int(StockBalance.objects.filter(
            brand=brand, size=size, color=color, location__key=StockLocation.HOME
        ).aggregate(v=Sum("qty"))["v"] or 0)

    def handle(self, *args, **options):
        if resolve("/returns/").func.__module__ != "core.returns_v37":
            raise CommandError("/returns/ is not routed to returns_v37")
        if resolve("/returns/apply/").func.__module__ != "core.returns_v37":
            raise CommandError("/returns/apply/ is not routed to returns_v37")
        if resolve("/calculator/").func.__module__ != "core.calculator_v37":
            raise CommandError("calculator route is not v37")
        if resolve("/calculator/target-quote/").func.__module__ != "core.calculator_v37":
            raise CommandError("target calculator route is not v37")
        try:
            resolve("/sales/1/return/")
            raise CommandError("old daily-report return route still exists")
        except Resolver404:
            pass

        for name in (
            "core/daily_report_v21.html",
            "core/returns_v37.html",
            "core/calculator_v37.html",
            "core/_calculator_target_result_v37.html",
            "core/report_excel_v36.html",
        ):
            try:
                get_template(name)
            except Exception as exc:
                raise CommandError(f"template load failed: {name}: {exc}") from exc

        # Exact fee-engine solver check: returned price must meet target and one toman less must not.
        cost = 100000
        target = 50.0
        price = _solve_sale_price(cost, target)
        achieved = price - int(digikala_fee_for_unit(price)) - cost
        target_profit = cost * target / 100
        if achieved < target_profit:
            raise CommandError("target calculator undershot requested profit ratio")
        if price > 0:
            previous = price - 1
            previous_profit = previous - int(digikala_fee_for_unit(previous)) - cost
            if previous_profit >= target_profit:
                raise CommandError("target calculator did not return minimum valid sale price")

        darma = Brand.objects.get(name="دارما")
        ps = (
            ProductSize.objects.filter(
                product__brand=darma,
                product__active=True,
                active=True,
                product__composition__isnull=False,
            )
            .select_related("product", "size")
            .prefetch_related("product__composition__color")
            .distinct()
            .first()
        )
        if not ps:
            raise CommandError("no Darma product-size available for return rollback test")
        comp = list(ProductComposition.objects.filter(product=ps.product).select_related("color")).pop(0)
        before_qty = self._home_qty(darma, ps.size, comp.color)
        before_finished = int(finished_inventory_value_v17())
        before_digi = int(digikala_receivable_total())
        before_entries = AccountEntry.objects.count()
        before_sales = SaleLine.objects.count()
        before_adjustments = InventoryAdjustment.objects.count()

        with transaction.atomic():
            _create_adjustment(
                when=date.today(), brand=darma, size=ps.size, color=comp.color,
                qty=2, group="v37check", source="rollback-test",
            )
            if self._home_qty(darma, ps.size, comp.color) != before_qty + 2:
                raise CommandError("standalone return did not add exact HOME quantity")
            if int(digikala_receivable_total()) != before_digi:
                raise CommandError("standalone return changed Digikala receivable")
            if AccountEntry.objects.count() != before_entries:
                raise CommandError("standalone return created finance entry")
            if SaleLine.objects.count() != before_sales:
                raise CommandError("standalone return changed sales")
            if int(finished_inventory_value_v17()) <= before_finished:
                raise CommandError("standalone return did not increase inventory value")
            transaction.set_rollback(True)

        if self._home_qty(darma, ps.size, comp.color) != before_qty:
            raise CommandError("return rollback left HOME stock changed")
        if int(finished_inventory_value_v17()) != before_finished:
            raise CommandError("return rollback left finished inventory value changed")
        if int(digikala_receivable_total()) != before_digi:
            raise CommandError("return rollback left Digikala changed")
        if AccountEntry.objects.count() != before_entries or SaleLine.objects.count() != before_sales:
            raise CommandError("return rollback left finance/sale data changed")
        if InventoryAdjustment.objects.count() != before_adjustments:
            raise CommandError("return rollback left adjustment rows changed")

        self.stdout.write("RETURNS + CALCULATOR V37 CHECK OK")
        self.stdout.write("Old return box/route removed from daily report")
        self.stdout.write("Standalone return adds HOME only; no SaleLine/AccountEntry/Digikala movement")
        self.stdout.write("Target calculator uses exact existing Digikala fee engine")
        self.stdout.write("Rollback test left business values unchanged")
