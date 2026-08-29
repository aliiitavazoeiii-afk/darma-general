from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.urls import resolve

from core.daily_returns_v36 import _apply_return_batch
from core.finance_excel_v9 import digikala_receivable_total
from core.inventory_valuation_v17 import finished_inventory_value_v17
from core.models import AccountEntry, Brand, Color, InventoryAdjustment, ProductSize, SaleDay, SaleLine, StockBalance, StockLocation


class Command(BaseCommand):
    help = "Rollback regression check for v36 UI safety and isolated daily returns."

    def _qty(self, brand, size, color):
        return int(StockBalance.objects.filter(
            brand=brand, size=size, color=color, location__key=StockLocation.HOME
        ).aggregate(v=Sum("qty"))["v"] or 0)

    def handle(self, *args, **options):
        if resolve("/report/").func.__module__ != "core.report_v9":
            raise CommandError("report route changed away from report_v9")
        if resolve("/").func.__module__ != "core.excel_dashboard":
            raise CommandError("dashboard route changed away from excel_dashboard")
        if resolve("/sales/1/report/").func.__module__ != "core.daily_report_v8":
            raise CommandError("daily report route changed away from daily_report_v8")
        if resolve("/sales/1/return/").func.__module__ != "core.daily_returns_v36":
            raise CommandError("daily return route is not v36")

        darma = Brand.objects.get(name="دارما")
        ps = ProductSize.objects.filter(
            product__brand=darma, product__active=True, active=True,
            product__composition__isnull=False,
        ).select_related("product", "size").distinct().first()
        if not ps:
            raise CommandError("no fixed-composition Darma product-size found for test")
        comp = ps.product.composition.select_related("color").first()
        color = comp.color
        before_qty = self._qty(darma, ps.size, color)
        before_finished = int(finished_inventory_value_v17())
        before_digi = int(digikala_receivable_total())
        before_entries = AccountEntry.objects.count()
        before_sales = SaleLine.objects.count()
        before_adjustments = InventoryAdjustment.objects.count()

        with transaction.atomic():
            day, _ = SaleDay.objects.get_or_create(date=date(2099, 1, 1))
            loose_qty = 2
            result = _apply_return_batch(
                day=day,
                brand=darma,
                size=ps.size,
                loose_by_color=[(color, loose_qty)],
                pack_by_product_size=[],
            )
            if result["shorts"] != loose_qty:
                raise CommandError(f"loose return quantity mismatch: {result}")
            after_qty = self._qty(darma, ps.size, color)
            if after_qty != before_qty + loose_qty:
                raise CommandError(f"HOME stock did not increase exactly: {before_qty} -> {after_qty}")
            if int(digikala_receivable_total()) != before_digi:
                raise CommandError("daily return changed Digikala receivable")
            if AccountEntry.objects.count() != before_entries:
                raise CommandError("daily return created finance account entries")
            if SaleLine.objects.count() != before_sales:
                raise CommandError("daily return created/changed sales")
            if int(finished_inventory_value_v17()) <= before_finished:
                raise CommandError("daily return did not increase finished inventory value")
            transaction.set_rollback(True)

        if self._qty(darma, ps.size, color) != before_qty:
            raise CommandError("rollback test left stock changed")
        if int(finished_inventory_value_v17()) != before_finished:
            raise CommandError("rollback test left inventory value changed")
        if int(digikala_receivable_total()) != before_digi:
            raise CommandError("rollback test left Digikala changed")
        if AccountEntry.objects.count() != before_entries or SaleLine.objects.count() != before_sales:
            raise CommandError("rollback test left finance/sale data changed")
        if InventoryAdjustment.objects.count() != before_adjustments:
            raise CommandError("rollback test left adjustment rows changed")

        self.stdout.write("UI + DAILY RETURNS V36 CHECK OK")
        self.stdout.write("Dashboard/report formulas and active routes preserved")
        self.stdout.write("Return adds HOME stock only and creates no SaleLine/AccountEntry/Digikala movement")
        self.stdout.write("Rollback test left all business values unchanged")
