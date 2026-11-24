"""V150: actual color yield, one-off Tapsi price and read-only tailor audit."""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from core import material_report_ui_v131 as production_ui
from core.models import (
    AppSetting, Brand, BusinessPayment, Color, ExcelManualRow,
    MaterialReportBlock, MaterialReportOutputApplied, ProductCode,
    ProductComposition, ProductSize, SaleDay, Size, StockBalance,
    StockLocation, TapsiOrder, TapsiPriceRule
)
from core.tapsi_shop_v138 import create_tapsi_order, current_catalog, order_metrics
from core.tailor_statement_v150 import build_tailor_statement


class ColorHistoricalYieldV150(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="v150-yield", password="v150")
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="دارما")
        Brand.objects.create(name="Novani")
        Size.objects.create(name="M")
        AppSetting.objects.create(key="pedram_dozen_wage", label="مزد", value="110000")

    def sheet(self, days_ago, color, kg, cut, entered, applied=None, brand=None):
        block = MaterialReportBlock.objects.create(
            date=date.today() - timedelta(days=days_ago),
            brand=brand or self.brand,
            input_data={"_meta": {"active_material_keys": [color]},
                        color: {"fabric_code": color, "weight": str(kg), "cut": str(cut)}},
            output_data={color: {"m": str(entered)}},
        )
        if applied is not None:
            MaterialReportOutputApplied.objects.create(
                block=block, model_key=color, size_key="m", quantity=applied,
            )
        return block

    def test_weighted_actual_yield_per_color_excludes_incomplete_future_and_other_brand(self):
        self.sheet(7, "pink", "20", 750, 750, 750)
        self.sheet(5, "pink", "19.2", 720, 720, 720)
        self.sheet(4, "pink", "20", 750, 100, 100)  # unfinished; exclude full weight
        self.sheet(3, "pink", "20", 750, 750, 0)  # unposted; exclude
        self.sheet(2, "white", "20", 1000, 1000, 1000)
        novani = Brand.objects.get(name="Novani")
        self.sheet(2, "pink", "20", 1000, 1000, 1000, brand=novani)
        target = self.sheet(0, "pink", "19.2", 700, 0)
        future = self.sheet(-1, "pink", "25", 1100, 1100, 1100)
        all_blocks = list(MaterialReportBlock.objects.select_related("brand").prefetch_related(
            "output_applications", "stock_consumptions"))
        history = production_ui._completed_color_history(all_blocks)
        rate, rolls = production_ui._historical_color_yield(history, target, "صورتی")
        self.assertEqual(rolls, 2)
        self.assertEqual(rate, Decimal("37.5"))  # (750 + 720) / (20 + 19.2)
        self.assertEqual(production_ui._estimate_from_yield("19.2", rate), 720)
        self.assertIsNone(production_ui._estimate_from_yield("", rate))
        row = production_ui._editor(target, history)["rows"][0]
        self.assertEqual(row["mean_cut"], 720)
        self.assertEqual(row["cut"], 700)  # forecast never modifies the entered cut
        self.assertEqual(row["mean_history_rolls"], 2)
        self.assertEqual(future.input_data["pink"]["cut"], "1100")
        rendered = self.client.get(reverse("material_report"))
        self.assertEqual(rendered.status_code, 200)
        self.assertContains(rendered, "میانگین برش")
        self.assertContains(rendered, "data-mean-rate=")

    def test_empty_history_never_invents_a_number(self):
        new = self.sheet(0, "pink", "19.2", 710, 0)
        row = production_ui._editor(new, {})["rows"][0]
        self.assertIsNone(row["mean_cut"])
        self.assertEqual(row["mean_history_rolls"], 0)


class TapsiManualSalePriceV150(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="v150-price", password="v150")
        cls.brand = Brand.objects.create(name="دارما")
        cls.size = Size.objects.create(name="XXL")
        cls.color = Color.objects.create(name="مشکی")
        cls.home = StockLocation.objects.create(key="home", title="خانه")
        cls.product = ProductCode.objects.create(brand=cls.brand, code="99", pack_qty=3, title="آزمایشی")
        ProductComposition.objects.create(product=cls.product, color=cls.color, qty=3)
        cls.ps = ProductSize.objects.create(
            product=cls.product, size=cls.size, active=True, default_sale_price=700000
        )
        cls.day = SaleDay.objects.create(date=date.today())
        StockBalance.objects.create(brand=cls.brand, color=cls.color, size=cls.size, location=cls.home, qty=50)

    def setUp(self):
        self.client.force_login(self.user)
        TapsiPriceRule.objects.create(product_size=self.ps, effective_from=self.day.date, price=816000)

    def test_one_off_sale_price_snapshotted_and_default_unchanged(self):
        order = create_tapsi_order(self.day, [(self.ps.pk, 2)], unit_prices={self.ps.pk: "780000"})
        self.assertEqual(order.items.get().unit_price, 780000)
        self.assertEqual(order_metrics(order)["gross"], 1560000)
        catalog = current_catalog(self.day.date)
        self.assertEqual(catalog[0]["sizes"][0]["price"], 816000)
        self.assertEqual(TapsiPriceRule.objects.get().price, 816000)
        self.assertEqual(StockBalance.objects.get().qty, 44)

    def test_web_form_accepts_persian_digits_but_rejects_invalid_price_atomically(self):
        page = self.client.get(reverse("tapsi_home"))
        self.assertContains(page, 'id="t150-unit-price"')
        self.assertContains(page, 'فی فروش این سایز')
        req = {
            "order_date": self.day.date.isoformat(),
            "product_size_id": [str(self.ps.pk)],
            "quantity": ["1"], "unit_price": ["۷۹۰٬۰۰۰"],
        }
        resp = self.client.post(reverse("tapsi_hub_create"), req)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(TapsiOrder.objects.get().items.get().unit_price, 790000)
        self.assertEqual(TapsiPriceRule.objects.get().price, 816000)
        before = StockBalance.objects.get().qty
        bad = dict(req, unit_price=["0"])
        self.client.post(reverse("tapsi_hub_create"), bad)
        self.assertEqual(TapsiOrder.objects.count(), 1)
        self.assertEqual(StockBalance.objects.get().qty, before)


class TailorStatementV150(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="v150-tailor", password="v150")
        self.client.force_login(user)
        self.brand = Brand.objects.create(name="دارما")
        self.account = ExcelManualRow.objects.create(
            section=ExcelManualRow.PERSONS, title="خیاط", amount=1000000, active=True,
        )
        self.pay = BusinessPayment.objects.create(
            date=date(2026, 10, 7), payee="tailor", amount=300000,
            source_account="melat", note="واریز تست"
        )
        self.block = MaterialReportBlock.objects.create(
            date=date(2026, 10, 8), brand=self.brand,
            input_data={}, output_data={}, delivery_wage=110000,
        )
        MaterialReportOutputApplied.objects.create(
            block=self.block, model_key="pink", size_key="m", quantity=12,
        )

    def test_signed_ledger_uses_own_live_balance_and_all_known_events(self):
        statement = build_tailor_statement()
        self.assertEqual(statement["opening"], 810000)
        self.assertEqual(statement["payments"], 300000)
        self.assertEqual(statement["wages"], 110000)
        self.assertEqual(statement["closing"], 1000000)
        self.assertEqual(statement["count"], 2)
        self.assertEqual(statement["rows"][0]["balance"], 1110000)
        self.assertEqual(statement["rows"][1]["balance"], 1000000)
        before = (self.account.amount, MaterialReportBlock.objects.count(), BusinessPayment.objects.count())
        resp = self.client.get(reverse("tailor_statement"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "مانده ابتدای سوابق (بازسازی‌شده)")
        self.assertEqual(
            before, (ExcelManualRow.objects.get(pk=self.account.pk).amount,
                     MaterialReportBlock.objects.count(), BusinessPayment.objects.count())
        )

    def test_excel_has_full_history_and_numeric_running_balance(self):
        response = self.client.get(reverse("tailor_statement_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        ws = load_workbook(BytesIO(response.content), read_only=True).active
        rows = list(ws.values)
        self.assertTrue(any(row[1] == "مانده اولیه بازسازی‌شده" for row in rows if len(row)>1))
        self.assertTrue(any(row[2] == f"پرداخت #{self.pay.pk}" and row[4] == 300000
                            for row in rows if len(row)>4))
        self.assertTrue(any(row[2] == f"صورت #{self.block.pk}" and row[5] == 110000
                            for row in rows if len(row)>5))
        self.assertEqual(rows[-1][6], 1000000)
