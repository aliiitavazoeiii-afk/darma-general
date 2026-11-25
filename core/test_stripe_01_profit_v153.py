"""V153: date-scoped 162,500 price and 76,000 COGS, only Darma stripe01 Azar 5–10."""
from datetime import date

from django.test import TestCase

from core.cost_accounting_v14 import snapshot_sale_line
from core.daily_order_import_v23 import apply_delivery_preview
from core.finance import digikala_fee_for_unit, sale_line_metrics
from core.models import (
    Brand, Color, ProductCode, ProductSize, SaleDay, SaleLine,
    Size, StockBalance, StockLocation,
)
from core.sale_price_v60 import sale_price_for
from core.stripe_01_v151 import (
    PRODUCT_CODE, PROFIT_START, PROFIT_END,
    PROFIT_SALE_PRICE, PROFIT_UNIT_COST, UNIT_COST, SALE_PRICE,
    profit_rule_applies,
)


class Stripe01ProfitWindowV153Tests(TestCase):
    def setUp(self):
        self.darma = Brand.objects.create(name="دارما")
        self.takvin = Brand.objects.create(name="تکوین")
        self.size = Size.objects.create(name="XL", sort_order=1)
        self.product = ProductCode.objects.create(
            brand=self.darma, code=PRODUCT_CODE, title="راه راه 01",
            pack_qty=1, active=True,
        )
        self.ps = ProductSize.objects.create(
            product=self.product, size=self.size, active=True,
            default_sale_price=SALE_PRICE, unit_cost=UNIT_COST,
        )

    def _line(self, when, price=None):
        day = SaleDay.objects.create(date=when)
        price = sale_price_for(self.ps, when) if price is None else price
        line = SaleLine.objects.create(
            day=day, product_size=self.ps, quantity=1, sale_price=price,
        )
        return line, snapshot_sale_line(line, self.ps, price)

    def test_boundaries_exact_and_non_target_product_untouched(self):
        self.assertEqual(PROFIT_START, date(2026, 11, 26))
        self.assertEqual(PROFIT_END, date(2026, 12, 1))
        for when, expected in [
            (date(2026, 11, 25), SALE_PRICE),
            (PROFIT_START, PROFIT_SALE_PRICE),
            (date(2026, 11, 30), PROFIT_SALE_PRICE),
            (PROFIT_END, PROFIT_SALE_PRICE),
            (date(2026, 12, 2), SALE_PRICE),
        ]:
            with self.subTest(when=when):
                self.assertEqual(sale_price_for(self.ps, when), expected)
                self.assertEqual(
                    profit_rule_applies(when, "دارما", PRODUCT_CODE),
                    PROFIT_START <= when <= PROFIT_END,
                )
        for brand_name, code in [
            ("تکوین", PRODUCT_CODE), ("دارما", "striped"),
            ("انبارش", PRODUCT_CODE),
        ]:
            self.assertFalse(profit_rule_applies(PROFIT_START, brand_name, code))
        self.assertFalse(profit_rule_applies(None, "دارما", PRODUCT_CODE))

        other = ProductCode.objects.create(
            brand=self.takvin, code=PRODUCT_CODE, title="unrelated",
            pack_qty=1, active=True,
        )
        other_ps = ProductSize.objects.create(
            product=other, size=self.size, active=True,
            default_sale_price=123456, unit_cost=90000,
        )
        self.assertEqual(sale_price_for(other_ps, PROFIT_START), 123456)

    def test_fee_cogs_profit_exact_on_both_boundaries_and_outside(self):
        cases = [
            (date(2026, 11, 25), 139000, 67000, 57677, 14323),
            (PROFIT_START, 162500, 76000, 61038, 25462),
            (PROFIT_END, 162500, 76000, 61038, 25462),
            (date(2026, 12, 2), 139000, 67000, 74496, -2496),
        ]
        for when, price, cost, fee, profit in cases:
            with self.subTest(when=when):
                line, snap = self._line(when)
                metrics = sale_line_metrics(line)
                self.assertEqual(line.sale_price, price)
                self.assertEqual(snap.unit_cost, cost)
                self.assertEqual(snap.digikala_fee_unit, fee)
                self.assertEqual(metrics["gross"], price)
                self.assertEqual(metrics["cogs"], cost)
                self.assertEqual(metrics["digikala_fee"], fee)
                self.assertEqual(metrics["profit"], profit)
                self.assertEqual(
                    digikala_fee_for_unit(
                        price, when, product_code=PRODUCT_CODE, brand_name="دارما"
                    ), fee,
                )
        self.assertEqual(self.ps.default_sale_price, SALE_PRICE)
        self.assertEqual(self.ps.unit_cost, UNIT_COST)

    def test_existing_manual_sale_price_remains_authoritative(self):
        line, snap = self._line(PROFIT_START, price=170000)
        self.assertEqual(line.sale_price, 170000)
        self.assertEqual(snap.unit_cost, PROFIT_UNIT_COST)
        self.assertEqual(snap.digikala_fee_unit, digikala_fee_for_unit(
            170000, PROFIT_START, product_code=PRODUCT_CODE, brand_name="دارما",
        ))

    def test_digikala_import_new_lines_pick_162500_and_preserve_inventory_idempotence(self):
        color = Color.objects.create(name="راه راه مشکی", active=True)
        home = StockLocation.objects.create(key="home", title="خانه")
        StockLocation.objects.create(key="khorshid", title="خورشید")
        StockBalance.objects.create(
            brand=self.darma, size=self.size, color=color, location=home, qty=100,
        )
        day = SaleDay.objects.create(date=PROFIT_START)
        preview = {
            "errors": [], "rows": [{
                "brand": "دارما", "code": PRODUCT_CODE,
                "size": "XL", "color": "راه راه مشکی", "quantity": 2,
            }],
            "source_rows": 1, "ignored_rows": 0, "raw_quantity": 2,
        }
        first = apply_delivery_preview(day, preview)
        self.assertEqual(first["total_quantity"] if "total_quantity" in first else first["raw_quantity"], 2)
        line = SaleLine.objects.get(day=day, product_size=self.ps)
        self.assertEqual(line.sale_price, PROFIT_SALE_PRICE)
        self.assertEqual(line.snapshot.unit_cost, PROFIT_UNIT_COST)
        self.assertEqual(line.snapshot.digikala_fee_unit, 61038)
        self.assertEqual(sale_line_metrics(line)["profit"], 2 * 25462)
        self.assertEqual(StockBalance.objects.get(brand=self.darma, color=color).qty, 98)
        apply_delivery_preview(day, preview)
        self.assertEqual(SaleLine.objects.get(pk=line.pk).sale_price, PROFIT_SALE_PRICE)
        self.assertEqual(StockBalance.objects.get(brand=self.darma, color=color).qty, 98)
