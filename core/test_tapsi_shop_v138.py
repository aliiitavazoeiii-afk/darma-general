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

    def test_anbaresh_mirrored_products_are_excluded_from_tapsi(self):
        mirror_brand = Brand.objects.create(name="انبارش")
        mirror = ProductCode.objects.create(
            brand=mirror_brand, code="330", title="آینه فروش دارما", pack_qty=3
        )
        mirror_ps = ProductSize.objects.create(product=mirror, size=self.size_m, active=True)
        ProductComposition.objects.create(product=mirror, color=self.black, qty=1)
        ProductComposition.objects.create(product=mirror, color=self.pink, qty=2)
        TapsiPriceRule.objects.create(
            product_size=mirror_ps, effective_from=self.day.date, price=500000
        )
        catalog = current_catalog(self.day.date)
        self.assertEqual(len([r for r in catalog if r["code"] == "330"]), 1)
        with self.assertRaisesMessage(ValueError, "غیرفعال یا نامعتبر"):
            create_tapsi_order(self.day, [(mirror_ps.id, 1)])
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertFalse(StockBalance.objects.filter(brand=mirror_brand).exists())

    def test_two_products_one_order_exactly_one_shipping_plus_manual_discount(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 1), (self.ps_l.pk, 2)], discount_cost=25000)
        metrics = order_metrics(order)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(metrics["gross"], 2900000)
        self.assertEqual(metrics["commission"], 435000)
        self.assertEqual(metrics["shipping"], 140000)
        self.assertEqual(metrics["discount"], 25000)
        self.assertEqual(metrics["vat"], 43500)
        self.assertEqual(metrics["insurance"], 43500)
        self.assertEqual(metrics["infrastructure"], 550000)
        self.assertEqual(metrics["fee"], 1237000)
        self.assertEqual(metrics["packs"], 3)
        self.assertEqual(metrics["shorts"], 9)
        self.assertEqual(metrics["cogs"], 9 * int(darma_cost_for(self.day.date)))
        self.assertEqual(metrics["profit"], 2900000 - 1237000 - metrics["cogs"])
        self.assertEqual(COMMISSION_PERCENT, Decimal("15.00"))
        self.assertEqual(SHIPPING_PER_ORDER, 140000)
        # V143 snapshots the 10% VAT on the 15% sales commission.
        self.assertEqual(metrics["commission"], metrics["gross"] * 15 // 100)
        self.assertEqual(order.vat_percent, Decimal("10.00"))
        self.assertFalse(SaleLine.objects.exists())

    def test_two_separate_orders_each_have_one_shipping(self):
        a = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        b = create_tapsi_order(self.day, [(self.ps_l.id, 1)])
        summary = tapsi_day_summary(self.day)["total"]
        self.assertEqual(summary["orders"], 2)
        self.assertEqual(summary["shipping"], 280000)
        self.assertEqual(summary["commission"], 285000)
        self.assertEqual(summary["vat"], 28500)
        self.assertEqual(summary["insurance"], 28500)
        self.assertEqual(summary["infrastructure"], 550000)
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
        # Even a later product-brand edit cannot redirect historical stock reversal.
        self.product.brand = Brand.objects.create(name="Novani")
        self.product.save(update_fields=["brand"])
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
        # Neither an independent Tapsi price nor the canonical Digikala
        # baseline exists: the request must still be rejected atomically.
        self.ps_l.default_sale_price = 0
        self.ps_l.save(update_fields=["default_sale_price"])
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
        date_string = self.day.date.isoformat()
        page = self.client.get(reverse("daily_report", args=[self.day.id]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'id="t142-entry"')
        self.assertNotContains(page, reverse("tapsi_order_report", args=[self.day.id]))
        entry = self.client.get(reverse("tapsi_home"), {"date": date_string})
        self.assertContains(entry, 'id="t142-catalog"')
        self.assertTrue(any(row["title"] == "شورت زنانه 330 مجموعه سعدعلی" for row in entry.context["tapsi_catalog"]))
        self.assertContains(entry, 'name="discount_cost"')
        submit = self.client.post(reverse("tapsi_hub_create"), {
            "order_date": date_string,
            "product_size_id": [str(self.ps_m.pk), str(self.ps_l.pk)],
            "quantity": ["1", "1"], "discount_cost": "75000", "note": "ref 0123",
        })
        self.assertEqual(submit.status_code, 302)
        self.assertEqual(TapsiOrder.objects.count(), 1)
        order = TapsiOrder.objects.get()
        self.assertEqual(order.discount_cost, 75000)
        self.assertEqual(order.items.count(), 2)
        standalone = self.client.get(reverse("tapsi_home"), {"date": date_string})
        self.assertEqual(standalone.context["tapsi_summary"]["total"]["orders"], 1)
        daily = self.client.get(reverse("daily_report", args=[self.day.id]))
        self.assertNotIn("tapsi_summary", daily.context)
        self.assertEqual(daily.context["total"]["gross"], 0)
        self.assertEqual(daily.context["total"]["profit"], 0)
        deleted = self.client.post(reverse("tapsi_hub_delete", args=[order.id]))
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(self._balance(self.size_m, self.black), 100)
    def test_sale_day_delete_preserves_standalone_tapsi(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 1), (self.ps_l.pk, 1)])
        before_black = self._balance(self.size_m, self.black)
        before_pink = self._balance(self.size_l, self.pink)
        result = delete_sale_day(self.day.id)
        self.assertTrue(result["day_retained_for_tapsi"])
        self.assertTrue(SaleDay.objects.filter(pk=self.day.pk).exists())
        self.assertTrue(TapsiOrder.objects.filter(pk=order.id).exists())
        self.assertEqual(self._balance(self.size_m, self.black), before_black)
        self.assertEqual(self._balance(self.size_l, self.pink), before_pink)
        self.client.post(reverse("tapsi_hub_delete", args=[order.id]))
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

    def test_v142_tapsi_is_not_in_daily_sales_navigation(self):
        daily = self.client.get(reverse("daily_report", args=[self.day.id]))
        self.assertEqual(daily.status_code, 200)
        self.assertNotContains(daily, reverse("tapsi_order_report", args=[self.day.id]))
        self.assertNotContains(daily, 'id="t142-entry"')
        self.assertNotContains(daily, 'id="t142-query"')
        self.assertNotContains(daily, 'name="discount_cost"')
        chooser = self.client.get(reverse("sale_brand", args=[self.day.id]))
        self.assertNotContains(chooser, reverse("tapsi_order_entry", args=[self.day.id]))
        redirected = self.client.get(reverse("tapsi_order_entry", args=[self.day.id]))
        self.assertEqual(redirected.status_code, 302)
        self.assertTrue(redirected.url.startswith(reverse("tapsi_home")))
        report_redirect = self.client.get(reverse("tapsi_order_report", args=[self.day.id]))
        self.assertEqual(report_redirect.status_code, 302)
        entry = self.client.get(reverse("tapsi_home"), {"date": self.day.date.isoformat()})
        self.assertContains(entry, 'id="t142-order-form"')
        self.assertContains(entry, 'id="t142-query"')
        self.assertContains(entry, 'name="discount_cost"')
        self.assertContains(entry, 'href="' + reverse("tapsi_home") + '"')
        self.assertTrue(any(x["title"] == "شورت زنانه 330 مجموعه سعدعلی" for x in entry.context["tapsi_catalog"]))
    def test_v140_seed_current_digikala_prices_only_where_tapsi_missing(self):
        from django.core.management import call_command
        from io import StringIO
        before = sale_price_for(self.ps_m, self.day.date)
        # M already independent, L unpriced to test one-time import.
        TapsiPriceRule.objects.filter(product_size=self.ps_l).delete()
        dry = StringIO()
        call_command("seed_tapsi_prices_v140", dry_run=True, stdout=dry)
        self.assertEqual(tapsi_price_for(self.ps_l, self.day.date), 0)
        output = StringIO()
        call_command("seed_tapsi_prices_v140", stdout=output)
        self.assertEqual(tapsi_price_for(self.ps_m, self.day.date), 900000)
        self.assertEqual(tapsi_price_for(self.ps_l, self.day.date), 550000)
        self.assertEqual(sale_price_for(self.ps_m, self.day.date), before)
        self.assertIn("TAPSI_SEED_V140", output.getvalue())
        rows_before = list(TapsiPriceRule.objects.values_list("pk", "price"))
        call_command("seed_tapsi_prices_v140", stdout=StringIO())
        self.assertEqual(rows_before, list(TapsiPriceRule.objects.values_list("pk", "price")))

    def test_v140_capital_recognizes_net_receivable_not_profit_twice(self):
        from core.capital_history_v87 import current_capital_breakdown, capital_as_of
        from core.tapsi_shop_v138 import tapsi_receivable_total
        from datetime import timedelta
        before = current_capital_breakdown()
        order = create_tapsi_order(self.day, [(self.ps_m.id, 1), (self.ps_l.id, 2)], discount_cost=25000)
        m = order_metrics(order)
        after = current_capital_breakdown()
        self.assertEqual(tapsi_receivable_total(), m["gross"] - m["fee"])
        self.assertEqual(after["tapsi_receivable"], m["gross"] - m["fee"])
        # Home inventory value decreases by exact accounting cost at today's date.
        self.assertEqual(
            before["finished_inventory_total"] - after["finished_inventory_total"],
            m["cogs"],
        )
        self.assertEqual(after["capital_total"] - before["capital_total"], m["profit"])
        historical = capital_as_of(self.day.date - timedelta(days=1))
        self.assertEqual(historical["delta_parts"]["tapsi_profit"], m["profit"])
        self.assertEqual(historical["capital_total"], before["capital_total"])
        reverse_tapsi_order(order)
        self.assertEqual(tapsi_receivable_total(), 0)
        self.assertEqual(current_capital_breakdown()["capital_total"], before["capital_total"])

    def test_v140_comprehensive_tapsi_code_size_ledger_reconciles_fees_and_profit(self):
        from core.tapsi_shop_v138 import tapsi_period_metrics
        create_tapsi_order(self.day, [(self.ps_m.id, 1), (self.ps_l.id, 2)], discount_cost=25000)
        ledger = tapsi_period_metrics(self.day.date, self.day.date)
        total = ledger["total"]
        rows = ledger["rows"]
        self.assertEqual(total["orders"], 1)
        self.assertEqual(total["fee"], 1237000)
        self.assertEqual(total["infrastructure"], 550000)
        self.assertEqual(total["insurance"], 43500)
        self.assertEqual(total["vat"], 43500)
        self.assertEqual(sum(row["vat"] for row in rows), 43500)
        self.assertEqual(sum(row["fee"] for row in rows), total["fee"])
        self.assertEqual(sum(row["commission"] for row in rows), 435000)
        self.assertEqual(sum(row["shipping"] for row in rows), 140000)
        self.assertEqual(sum(row["discount"] for row in rows), 25000)
        self.assertEqual(sum(row["profit"] for row in rows), total["profit"])
        self.assertEqual(sum(row["packs"] for row in ledger["by_size"]), 3)
        self.assertEqual(total["receivable"], total["gross"] - total["fee"])
        page = self.client.get(reverse("report"), {"period": "today"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="comprehensive-tapsi-shop"')
        self.assertContains(page, 'class="v76-fold tapsi-comprehensive-fold"')
        self.assertContains(page, "گزارش تپسی‌شاپ")
        self.assertContains(page, "سود هر کد و سایز در تپسی‌شاپ")
        self.assertEqual(page.context["tapsi_period"]["total"]["profit"], total["profit"])
        self.assertEqual(page.context["overall"]["gross"], total["gross"])
        self.assertEqual(page.context["overall"]["profit"], total["profit"])
        self.assertEqual(page.context["overall"]["digikala_fee"], 0)

    def test_v142_orders_only_managed_inside_standalone_workspace(self):
        order = create_tapsi_order(self.day, [(self.ps_m.pk, 1)])
        daily = self.client.get(reverse("daily_report", args=[self.day.pk]))
        self.assertNotContains(daily, f"سفارش #{order.pk}")
        self.assertNotContains(daily, 'id="t142-history"')
        report_legacy = self.client.get(reverse("tapsi_order_report", args=[self.day.pk]))
        self.assertRedirects(report_legacy, reverse("tapsi_home") + "?date=" + self.day.date.isoformat(), fetch_redirect_response=False)
        workspace = self.client.get(reverse("tapsi_home"), {"date": self.day.date.isoformat()})
        self.assertContains(workspace, f"سفارش #{order.pk}")
        self.assertContains(workspace, reverse("tapsi_hub_delete", args=[order.pk]))
    def test_v141_brand_new_10_white_pack_sizes_selectable_and_price_snapshotted(self):
        from core.tapsi_shop_v138 import initial_catalog_prices
        product = ProductCode.objects.create(
            brand=self.brand, code="03", title="پک ۰۳ ده تایی سفید",
            pack_qty=10, active=True,
        )
        white = Color.objects.create(name="سفید")
        ProductComposition.objects.create(product=product, color=white, qty=10)
        ps_m = ProductSize.objects.create(
            product=product, size=self.size_m, active=True,
            default_sale_price=1600000,
        )
        ps_l = ProductSize.objects.create(
            product=product, size=self.size_l, active=True,
            default_sale_price=1750000,
        )
        self.assertFalse(TapsiPriceRule.objects.filter(product_size__in=[ps_m, ps_l]).exists())
        catalog = current_catalog(self.day.date)
        row = next(x for x in catalog if x["id"] == product.id)
        self.assertEqual(
            {x["name"]: x["price"] for x in row["sizes"]},
            {"M": 1600000, "L": 1750000},
        )
        page = self.client.get(reverse("tapsi_home"), {"date": self.day.date.isoformat()})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(row["title"], "پک ۰۳ ده تایی سفید")
        # Django json_script escapes non-ASCII JSON values by design;
        # verify the loaded catalog, not the escaped HTML representation.
        self.assertContains(page, 'id="t142-size"')
        self.assertContains(page, "خلاصه روز انتخاب‌شده")
        self.assertContains(page, "سفارش‌های ثبت‌شده")
        self.assertContains(page, 'id="t142-order-form"')
        response = self.client.post(reverse("tapsi_hub_create"), {
            "order_date": self.day.date.isoformat(),
            "product_size_id": [str(ps_m.pk)],
            "quantity": ["1"],
            "discount_cost": "0",
        })
        self.assertEqual(response.status_code, 302)
        item = TapsiOrderItem.objects.get(product_size=ps_m)
        self.assertEqual(item.unit_price, 1600000)
        self.assertEqual(item.pack_qty, 10)
        self.assertEqual(TapsiPriceRule.objects.get(product_size=ps_m).price, 1600000)
        self.assertEqual(
            StockBalance.objects.get(
                brand=self.brand, size=self.size_m, color=white, location=self.home
            ).qty, -10,
        )
        ps_m.default_sale_price = 2200000
        ps_m.save(update_fields=["default_sale_price"])
        self.assertEqual(item.unit_price, 1600000)
        self.assertEqual(initial_catalog_prices([ps_m], self.day.date)[ps_m.pk], 1600000)
        self.assertEqual(sale_price_for(ps_m, self.day.date), 2200000)
        self.assertEqual(
            next(x for x in current_catalog(self.day.date) if x["id"] == product.id)["sizes"][0]["price"],
            1600000,
        )

    def test_v142_table_free_cards_and_comprehensive_fold(self):
        create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        page = self.client.get(reverse("tapsi_home"), {"date": self.day.date.isoformat()})
        self.assertContains(page, 'class="t142-kpis"')
        self.assertContains(page, 'id="t142-entry"')
        self.assertContains(page, 'id="t142-history"')
        self.assertContains(page, 'class="t142-history-item"')
        self.assertContains(page, "فروش کالا")
        self.assertContains(page, "هزینه‌های تپسی")
        self.assertContains(page, "بهای تمام‌شده")
        self.assertContains(page, "سود فروش")
        self.assertNotContains(page, "سود تخمینی تپسی")
        self.assertNotContains(page, "tapsi-orders-table")
        body = page.content.decode("utf-8")
        self.assertLess(body.index('class="t142-kpis"'), body.index('id="t142-entry"'))
        self.assertLess(body.index('id="t142-entry"'), body.index('id="t142-history"'))
        script = (Path(settings.BASE_DIR) / "core/static/core/tapsi_portal_v142.js").read_text("utf-8")
        self.assertIn("t142-save", script)
        self.assertIn("basket", script)
        report = self.client.get(reverse("report"), {"period": "today"})
        self.assertContains(report, 'id="comprehensive-tapsi-shop"')
        self.assertContains(report, 'class="v76-fold tapsi-comprehensive-fold"')

    def test_v142_readonly_visit_does_not_create_day(self):
        from datetime import timedelta
        selected = self.day.date + timedelta(days=4)
        self.assertFalse(SaleDay.objects.filter(date=selected).exists())
        page = self.client.get(reverse("tapsi_home"), {"date": selected.isoformat()})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(SaleDay.objects.filter(date=selected).exists())
        self.assertEqual(page.context["tapsi_summary"]["total"]["orders"], 0)

    def test_v143_historical_vat_zero_does_not_reprice_orders(self):
        from core.tapsi_shop_v138 import tapsi_receivable_total
        order = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        self.assertEqual(order.vat_percent, Decimal("10.00"))
        new_metrics = order_metrics(order)
        order.vat_percent = Decimal("0.00")
        order.save(update_fields=["vat_percent"])
        legacy = order_metrics(order)
        self.assertEqual(legacy["vat"], 0)
        self.assertEqual(legacy["fee"], new_metrics["fee"] - new_metrics["vat"])
        self.assertEqual(legacy["profit"], new_metrics["profit"] + new_metrics["vat"])
        self.assertEqual(tapsi_receivable_total(), legacy["gross"] - legacy["fee"])

    def test_v143_shamsi_picker_round_trip_and_calculator_contract(self):
        from core.dateutils import format_jalali
        selected = format_jalali(self.day.date)
        page = self.client.get(reverse("tapsi_home"), {"date": selected})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["iso_date"], self.day.date.isoformat())
        self.assertContains(page, 'class="form-control jalali-date"')
        self.assertContains(page, 'value="' + selected + '"')
        self.assertContains(page, 'data-jalali-date')
        self.assertNotContains(page, 'id="t143-calculator"')
        self.assertNotContains(page, 'id="t143-monthly"')
        self.assertContains(page, reverse("tapsi_calculator"))
        self.assertContains(page, reverse("tapsi_monthly"))
        calculator_page = self.client.get(reverse("tapsi_calculator"))
        self.assertContains(calculator_page, 'id="t145-calc-target"')
        self.assertContains(calculator_page, 'id="t145-calc-cost"')
        self.assertContains(calculator_page, 'id="t145-calc-price"')
        self.assertContains(calculator_page, 'id="t145-calc-target"')
        self.assertNotContains(calculator_page, 'id="t144-calc-monthly"')
        self.assertNotContains(calculator_page, 'id="t143-calc-product"')
        self.assertNotContains(calculator_page, 'id="t143-calc-size"')
        self.assertNotContains(calculator_page, 'id="t143-calc-qty"')
        self.assertNotContains(calculator_page, 'id="t143-calc-pack"')
        self.assertNotContains(calculator_page, 'id="t142-entry"')
        monthly_page = self.client.get(reverse("tapsi_monthly"))
        self.assertContains(monthly_page, 'id="t143-monthly"')
        self.assertNotContains(monthly_page, 'id="t142-entry"')
        self.assertEqual(self.client.get(reverse("tapsi_home"), {"date": "1405/13/01"}).status_code, 400)
        calculator = (Path(settings.BASE_DIR) / "core/static/core/tapsi_calculator_v143.js").read_text("utf-8")
        self.assertIn("function targetPrice", calculator)
        self.assertIn("Math.round(commission * .10)", calculator)
        self.assertIn("const shipping = 140000", calculator)
        self.assertIn("Math.round(sale * .015)", calculator)
        self.assertIn("Math.round(sale * .003)", calculator)
        self.assertNotIn("550000", calculator)
        self.assertNotIn("2200000", calculator)
        self.assertNotIn("monthlyBill", calculator)
        self.assertIn("function targetPrice", calculator)

    def test_v143_jalali_month_boundary_financial_summary(self):
        import jdatetime
        from core.tapsi_portal_v142 import _month_report
        j = jdatetime.date.fromgregorian(date=self.day.date)
        month = f"{j.year:04d}/{j.month:02d}"
        following_j = jdatetime.date(j.year + 1, 1, 1) if j.month == 12 else jdatetime.date(j.year, j.month + 1, 1)
        following = SaleDay.objects.create(date=following_j.togregorian())
        current_order = create_tapsi_order(self.day, [(self.ps_m.id, 1)], discount_cost=30000)
        following_order = create_tapsi_order(following, [(self.ps_l.id, 1)])
        current = order_metrics(current_order)
        next_metrics = order_metrics(following_order)
        monthly = _month_report(month, self.day.date)
        self.assertEqual(monthly["total"]["orders"], 1)
        self.assertEqual(monthly["total"]["gross"], current["gross"])
        self.assertEqual(monthly["total"]["vat"], current["vat"])
        self.assertEqual(monthly["total"]["profit"], current["profit"])
        self.assertEqual(monthly["total"]["receivable"], current["gross"] - current["fee"])
        self.assertEqual(len(monthly["days"]), 1)
        later = self.client.get(reverse("tapsi_monthly"), {
            "month": f"{following_j.year:04d}/{following_j.month:02d}"
        })
        self.assertEqual(later.status_code, 200)
        self.assertEqual(later.context["monthly"]["total"]["gross"], next_metrics["gross"])
        self.assertEqual(later.context["monthly"]["total"]["profit"], next_metrics["profit"])
        self.assertContains(later, "سود خالص ماه")
        self.assertContains(later, "فروش به تفکیک روز")

    def test_v144_infrastructure_monthly_floor_once_and_separate_months(self):
        from datetime import timedelta
        from core.tapsi_infrastructure_v144 import infrastructure_allocations
        from core.tapsi_shop_v138 import tapsi_period_metrics, tapsi_receivable_total
        import jdatetime
        first = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        second = create_tapsi_order(self.day, [(self.ps_l.id, 1)])
        amounts = infrastructure_allocations([first, second])
        self.assertEqual(sum(amounts.values()), 550000)
        self.assertEqual(tapsi_day_summary(self.day)["total"]["infrastructure"], 550000)
        self.assertEqual(tapsi_receivable_total(),
                         1900000 - tapsi_day_summary(self.day)["total"]["fee"])
        # Filtering one day in a month must not charge the 550k floor twice.
        other_date = self.day.date + timedelta(days=1)
        j1 = jdatetime.date.fromgregorian(date=self.day.date)
        j2 = jdatetime.date.fromgregorian(date=other_date)
        if (j1.year, j1.month) == (j2.year, j2.month):
            another_day = SaleDay.objects.create(date=other_date)
            third = create_tapsi_order(another_day, [(self.ps_m.id, 2)])
            monthly = tapsi_period_metrics(self.day.date, other_date)
            self.assertEqual(monthly["total"]["infrastructure"], 550000)
            self.assertEqual(
                tapsi_period_metrics(self.day.date, self.day.date)["total"]["infrastructure"]
                + tapsi_period_metrics(other_date, other_date)["total"]["infrastructure"],
                550000,
            )
            self.assertEqual(tapsi_day_summary(another_day)["total"]["orders"], 1)

    def test_v144_infrastructure_cap_and_order_deletion_reallocation(self):
        from core.tapsi_shop_v138 import tapsi_period_metrics
        a = create_tapsi_order(self.day, [(self.ps_m.id, 1000)])
        b = create_tapsi_order(self.day, [(self.ps_l.id, 1000)])
        totals = tapsi_period_metrics(self.day.date, self.day.date)["total"]
        self.assertEqual(totals["gross"], 1900000000)
        self.assertEqual(totals["infrastructure"], 2200000)
        self.assertEqual(totals["insurance"], 28500000)
        reverse_tapsi_order(b)
        after = tapsi_period_metrics(self.day.date, self.day.date)["total"]
        self.assertEqual(after["infrastructure"], 2200000)
        reverse_tapsi_order(a)
        empty = tapsi_period_metrics(self.day.date, self.day.date)["total"]
        self.assertEqual(empty["infrastructure"], 0)

    def test_v144_legacy_zero_fees_and_finance_claim(self):
        from core.capital_history_v87 import current_capital_breakdown
        from core.tapsi_shop_v138 import tapsi_receivable_total
        order = create_tapsi_order(self.day, [(self.ps_m.id, 1)])
        before = order_metrics(order)
        self.assertEqual(before["insurance"], 13500)
        self.assertEqual(before["infrastructure"], 550000)
        self.assertEqual(order.insurance_percent, Decimal("1.50"))
        self.assertEqual(order.infrastructure_percent, Decimal("0.30"))
        order.insurance_percent = Decimal("0")
        order.infrastructure_percent = Decimal("0")
        order.save(update_fields=["insurance_percent", "infrastructure_percent"])
        historic = order_metrics(order)
        self.assertEqual(historic["insurance"], 0)
        self.assertEqual(historic["infrastructure"], 0)
        self.assertEqual(historic["profit"], before["profit"] + before["insurance"] + before["infrastructure"])
        self.assertEqual(current_capital_breakdown()["tapsi_receivable"], tapsi_receivable_total())
        accounts = self.client.get(reverse("finance_accounts"))
        self.assertContains(accounts, 'data-account-summary="tapsi"')
        hub = self.client.get(reverse("finance"))
        self.assertContains(hub, 'data-finance-tapsi-receivable="v144"')

    def test_v144_separate_pages_do_not_mutate_sales(self):
        stock = self._balance(self.size_m, self.black)
        rules = list(TapsiPriceRule.objects.values_list("id", "price"))
        for name in ("tapsi_home", "tapsi_calculator", "tapsi_monthly"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(stock, self._balance(self.size_m, self.black))
        self.assertEqual(rules, list(TapsiPriceRule.objects.values_list("id", "price")))

    def test_v145_simple_calculator_only_does_not_query_catalog_or_change_data(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        before = list(TapsiPriceRule.objects.values_list("id", "price"))
        with CaptureQueriesContext(connection) as sql:
            page = self.client.get(reverse("tapsi_calculator"))
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("calc_catalog", page.context)
        self.assertContains(page, "بهای تمام‌شده کل محصول")
        self.assertContains(page, "زیرساخت (۰٫۳٪ فروش)")
        self.assertContains(page, "ارسال ثابت سفارش")
        self.assertContains(page, "هزینه تخفیف دستی")
        self.assertNotContains(page, "پیش‌بینی مبلغ فروش کل ماه")
        self.assertNotContains(page, "کف ماهانه")
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(before, list(TapsiPriceRule.objects.values_list("id", "price")))

    def test_v142_failed_new_day_order_rolls_back_day_and_stock(self):
        from datetime import timedelta
        selected = self.day.date + timedelta(days=5)
        bad = self.client.post(reverse("tapsi_hub_create"), {
            "order_date": selected.isoformat(), "product_size_id": ["99999999"],
            "quantity": ["1"], "discount_cost": "0",
        })
        self.assertEqual(bad.status_code, 302)
        self.assertFalse(SaleDay.objects.filter(date=selected).exists())
        self.assertFalse(TapsiOrder.objects.exists())
        self.assertEqual(self._balance(self.size_m, self.black), 100)
