from datetime import date

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import Resolver404, resolve

from .dateutils import month_calendar
from .models import Account, Color, Product, ProductVariant, SaleDay, SaleLine, Size, StockBalance
from .services import digikala_fee_for_unit, main_location, sync_sale_inventory


class DiaIsolationTests(TestCase):
    def setUp(self):
        call_command("seed_base", verbosity=0)

    def test_legacy_core_is_not_installed(self):
        self.assertNotIn("core", settings.INSTALLED_APPS)
        self.assertTrue(any("dia_core" in item for item in settings.INSTALLED_APPS))

    def test_fresh_seed_has_no_business_data(self):
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SaleDay.objects.count(), 0)
        self.assertEqual(StockBalance.objects.count(), 0)
        self.assertEqual(Account.objects.count(), 0)

    def test_digikala_api_routes_do_not_exist(self):
        with self.assertRaises(Resolver404):
            resolve("/digikala/")
        with self.assertRaises(Resolver404):
            resolve("/digikala/orders/")

    def test_reference_commission_formula_is_kept_local(self):
        self.assertEqual(digikala_fee_for_unit(100_000), 64_200)

    def test_jalali_calendar_handles_esfand(self):
        for year in (1404, 1405, 1406):
            cal = month_calendar(year, 12)
            days = [day for week in cal["weeks"] for day in week if day]
            self.assertEqual(days[0], 1)
            self.assertIn(days[-1], (29, 30))
            self.assertEqual(len(days), days[-1])


class DiaStockSyncTests(TestCase):
    def setUp(self):
        call_command("seed_base", verbosity=0)
        size = Size.objects.create(name="TEST", sort_order=1)
        color = Color.objects.create(name="TEST COLOR", code="T")
        product = Product.objects.create(code="TEST-P")
        self.variant = ProductVariant.objects.create(
            product=product,
            size=size,
            color=color,
            default_sale_price=100_000,
            unit_cost=20_000,
        )
        self.balance = StockBalance.objects.create(variant=self.variant, location=main_location(), qty=10)
        self.day = SaleDay.objects.create(date=date(2026, 9, 14))

    def test_sale_edit_roundtrip_changes_only_delta(self):
        line = SaleLine.objects.create(
            day=self.day,
            variant=self.variant,
            quantity=3,
            sale_price=100_000,
            unit_cost_snapshot=20_000,
            digikala_fee_unit=digikala_fee_for_unit(100_000),
        )
        sync_sale_inventory(line)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.qty, 7)

        line.quantity = 5
        line.save(update_fields=["quantity"])
        sync_sale_inventory(line)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.qty, 5)

        line.quantity = 1
        line.save(update_fields=["quantity"])
        sync_sale_inventory(line)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.qty, 9)
