"""V138 independent Tapsi Shop regression: pricing, multi-line fee, inventory, deletion."""
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.darma_cost_v55 import darma_cost_for
from core.daily_report_actions_v21 import delete_sale_day
from core.models import (
    Brand, Color, InventoryMovement, ProductCode, ProductComposition, ProductSize,
    SaleDay, SaleLine, Size, StockBalance, StockLocation, TapsiOrder, TapsiOrderItem,
    TapsiPriceRule, TapsiStockAllocation,
)
from core.sale_price_v60 import sale_price_for
from core.tapsi_shop_v138 import (
    SHIPPING_PER_ORDER, COMMISSION_PERCENT, create_tapsi_order,
    current_catalog, order_metrics, reverse_tapsi_order,
    save_tapsi_bulk_darma, save_tapsi_product_prices, tapsi_price_for,
    tapsi_day_summary,
)


class TapsiShopV138Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="tapsi-test", password="temporary-test")
        cls.brand = Brand.objects.create(name="دارما")
        cls.size_m = Size.objects.create(name="M", sort_order=1)
        cls.size_l = Size.objects.create(name="L", sort_order=2)
        cls.black = Color.objects.create(name="مشکی")
        cls.pink = Color.objects.create(name="صورتی")
        cls.home = StockLocation.objects.create(key="home", title="خانه")
        cls.khorshid = StockLocation.objects.create(key="khorshid", title="خورشید")
        cls.product = ProductCode.objects.create(
            brand=cls.brand, code="330", title="شورت زنانه 330 مجموعه سعدعلی", pack_qty=3
        )
        ProductComposition.objects.create(product=cls.product, color=cls.black, qty=1)
        ProductComposition.objects.create(product=cls.product, color=cls.pink, qty=2)
        cls.ps_m = ProductSize.objects.create(
            product=cls.product, size=cls.size_m, active=True, default_sale_price=500000, unit_cost=65000,
        )
        cls.ps_l = ProductSize.objects.create(
            product=cls.product, size=cls.size_l, active=True, default_sale_price=550000, unit_cost=65000,
        )
        cls.day = SaleDay.objects.create(date=date.today())
        for size in (cls.size_m, cls.size_l):
            for color in (cls.black, cls.pink):
                StockBalance.objects.create(brand=cls.brand, size=size, color=color, location=cls.home, qty=100)
                StockBalance.objects.create(brand=cls.brand, size=size, color=color, location=cls.khorshid, qty=80)

    def setUp(self):
        self.client.force_login(self.user)
        TapsiPriceRule.objects.update_or_create(
            product_size=self.ps_m, effective_from=self.day.date, defaults={"price": 900000}
        )
        TapsiPriceRule.objects.update_or_create(
            product_size=self.ps_l, effective_from=self.day.date, defaults={"price": 1000000}
        )

    def _balance(self, size, color, loc=None):
        return StockBalance.objects.get(
            brand=self.brand, size=size, color=color, location=loc or self.home
        ).qty

    def test_tapsi_prices_independent_from_digikala_and_title_shared(self):
        dg_price = sale_price_for(self.ps_m, self.day.date)
        self.assertEqual(dg_price, 500000)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 900000)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date.replace(year=self.day.date.year - 1)), 0)
        catalog = current_catalog(self.day.date)
        p = next(x for x in catalog if x["code"] == "330")
        self.assertEqual(p["title"], "شورت زنانه 330 مجموعه سعدعلی")
        self.assertEqual({x["name"] for x in p["sizes"]}, {"M", "L"})
        self.assertEqual(next(x["price"] for x in p["sizes"] if x["name"] == "M"), 900000)
        self.assertEqual(sale_price_for(self.ps_m, self.day.date), dg_price)

    def test_two_products_one_order_exactly_one_shipping_plus_manual_discount(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 1), (self.ps_l.pk, 2)], discount_cost=25000)
        metrics = order_metrics(order)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(metrics["gross"], 2900000)
        self.assertEqual(metrics["commission"], 435000)
        self.assertEqual(metrics["shipping"], 140000)
        self.assertEqual(metrics["discount"], 25000)
        self.assertEqual(metrics["fee"], 600000)
        self.assertEqual(metrics["packs"], 3)
        self.assertEqual(metrics["shorts"], 9)
        self.assertEqual(metrics["cogs"], 9 * int(darma_cost_for(self.day.date)))
        self.assertEqual(metrics["profit"], 2900000 - 600000 - metrics["cogs"])
        self.assertEqual(COMMISSION_PERCENT, Decimal("15.00"))
        self.assertEqual(SHIPPING_PER_ORDER, 140000)
        # No extra 10% VAT: 15% includes it.
        self.assertEqual(metrics["commission"], metrics["gross"] * 15 // 100)
        self.assertFalse(SaleLine.objects.exists())

    def test_two_separate_orders_each_have_one_shipping(self):
        a = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        b = create_tapsi_order(self.day, [(self.ps_l.id, 1)])
        summary = tapsi_day_summary(self.day)["total"]
        self.assertEqual(summary["orders"], 2)
        self.assertEqual(summary["shipping"], 280000)
        self.assertEqual(summary["commission"], 285000)
        self.assertEqual(summary["gross"], 1900000)
        self.assertEqual(summary["discount"], 0)
        self.assertNotEqual(a.id, b.id)

    def test_stock_deductions_are_color_exact_home_only_and_reversible(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 2), (self.ps_l.pk, 1)])
        self.assertEqual(self._balance(self.size_m, self.black), 98)
        self.assertEqual(self._balance(self.size_m, self.pink), 96)
        self.assertEqual(self._balance(self.size_l, self.black), 99)
        self.assertEqual(self._balance(self.size_l, self.pink), 98)
        self.assertEqual(self._balance(self.size_m, self.pink, self.khorshid), 80)
        self.assertEqual(self._balance(self.size_l, self.black, self.khorshid), 80)
        self.assertEqual(TapsiStockAllocation.objects.filter(item__order=order).count(), 4)
        self.assertEqual(
            sum(x.quantity for x in TapsiStockAllocation.objects.filter(item__order=order)), 9
        )
        reverse_tapsi_order(order)
        self.assertFalse(TapsiOrder.objects.filter(pk=order.id).exists())
        for size in (self.size_m, self.size_l):
            for color in (self.black, self.pink):
                self.assertEqual(self._balance(size, color), 100)
                self.assertEqual(self._balance(size, color, self.khorshid), 80)
        self.assertEqual(
            sum(x.delta for x in InventoryMovement.objects.filter(reference__startswith="tapsi-item:")), 0
        )

    def test_changing_catalog_composition_after_order_does_not_change_reversal(self):
        order = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        ProductComposition.objects.filter(product=self.product).update(qty=1)
        ProductComposition.objects.filter(product=self.product, color=self.black).update(qty=3)
        reverse_tapsi_order(order)
        self.assertEqual(self._balance(self.size_m, self.black), 100)
        self.assertEqual(self._balance(self.size_m, self.pink), 100)

    def test_price_snapshot_never_repriced_when_tapsi_rule_changes(self):
        order = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        TapsiPriceRule.objects.filter(product_size=self.ps_m).update(price=1200000)
        item = order.items.get()
        self.assertEqual(item.unit_price, 900000)
        self.assertEqual(order_metrics(order)["gross"], 900000)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 1200000)
        self.assertEqual(sale_price_for(self.ps_m, self.day.date), 500000)

    def test_invalid_price_or_composition_rolls_back_without_stock_or_order(self):
        TapsiPriceRule.objects.filter(product_size=self.ps_l).delete()
        with self.assertRaisesMessage(ValueError, "ابتدا قیمت تپسی‌شاپ"):
            create_tapsi_order(self.day, [(self.ps_m.id, 1), (self.ps_l.id, 1)])
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(self._balance(self.size_m, self.black), 100)
        ProductComposition.objects.filter(product=self.product, color=self.pink).delete()
        with self.assertRaisesMessage(ValueError, "ترکیب رنگ"):
            create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(self._balance(self.size_m, self.pink), 100)

    def test_bulk_and_individual_prices_update_only_tapsi(self):
        before = sale_price_for(self.ps_m, self.day.date)
        count = save_tapsi_product_prices(
            self.product, self.day.date, {f"price_{self.ps_m.id}": "990000"}
        )
        self.assertEqual(count, 1)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 990000)
        self.assertEqual(tapsi_price_for(self.ps_l, self.day.date), 1000000)
        grouped = save_tapsi_bulk_darma(3, self.day.date, {"price_M": "780000", "price_L": "800000"})
        self.assertEqual(grouped["products"], 1)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 780000)
        self.assertEqual(tapsi_price_for(self.ps_l, self.day.date), 800000)
        self.assertEqual(sale_price_for(self.ps_m, self.day.date), before)

    def test_daily_web_box_search_and_order_create_and_delete(self):
        page = self.client.get(reverse("daily_report", args=[self.day.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "فروش تپسی‌شاپ")
        self.assertContains(page, 'id="tapsi-shop-catalog"')
        self.assertTrue(any(row["title"] == "شورت زنانه 330 مجموعه سعدعلی" for row in page.context["tapsi_catalog"]))
        self.assertContains(page, 'name="discount_cost"')
        submit = self.client.post(reverse("tapsi_order_create", args=[self.day.id]), {
            "product_size_id": [str(self.ps_m.pk), str(self.ps_l.pk)],
            "quantity": ["1", "1"], "discount_cost": "75000", "note": "ref 0123",
        })
        self.assertEqual(submit.status_code, 302)
        self.assertEqual(TapsiOrder.objects.count(), 1)
        order = TapsiOrder.objects.get()
        self.assertEqual(order.discount_cost, 75000)
        self.assertEqual(order.items.count(), 2)
        report = self.client.get(reverse("daily_report", args=[self.day.id]))
        self.assertEqual(report.context["tapsi_summary"]["total"]["orders"], 1)
        self.assertEqual(report.context["total"]["gross"], 1900000)
        self.assertEqual(report.context["total"]["digikala_fee"], 0)
        self.assertEqual(report.context["total"]["profit"], order_metrics(order)["profit"])
        deleted = self.client.post(reverse("tapsi_order_delete", args=[self.day.id, order.id]))
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(self._balance(self.size_m, self.black), 100)

    def test_sale_day_delete_undoes_tapsi_before_cascading_day(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 1), (self.ps_l.pk, 1)])
        deleted = delete_sale_day(self.day.id)
        self.assertEqual(deleted["tapsi_orders"], 1)
        self.assertFalse(SaleDay.objects.filter(pk=self.day.pk).exists())
        self.assertFalse(TapsiOrder.objects.filter(pk=order.id).exists())
        self.assertEqual(self._balance(self.size_m, self.black), 100)
        self.assertEqual(self._balance(self.size_l, self.pink), 100)

    def test_catalog_price_route_and_static_ui_contract(self):
        page = self.client.get(reverse("settings_products"), {"section":"pricing", "brand":"darma"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "ویرایش گروهی قیمت فروش دارما · تپسی‌شاپ")
        self.assertContains(page, "قیمت مستقل هر کد · تپسی‌شاپ")
        self.assertContains(page, 'name="action" value="tapsi_bulk_darma_prices"')
        self.assertContains(page, 'name="action" value="tapsi_product_prices"')
        changed = self.client.post(reverse("settings_products"), {
            "action": "tapsi_product_prices", "product_id": self.product.pk,
            "effective_from": __import__("core.dateutils", fromlist=["format_jalali"]).format_jalali(self.day.date),
            f"price_{self.ps_m.pk}": "850000",
        })
        self.assertEqual(changed.status_code, 302)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 850000)
        for path in (
            "templates/core/_tapsi_shop_daily_v138.html",
            "core/static/core/tapsi_shop_v138.js",
            "core/static/core/tapsi_shop_v138.css",
        ):
            self.assertTrue((Path(settings.BASE_DIR) / path).is_file())
