"""V150 regression: one-off Tapsi order prices and transparent full tailor audit/export."""
from datetime import date
from io import BytesIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from core.models import (
    Account, AccountEntry, Brand, BusinessPayment, Color, ExcelManualRow,
    MaterialReportBlock, MaterialReportOutputApplied, MoneyMovement,
    ProductCode, ProductComposition, ProductSize, SaleDay, Size,
    StockBalance, StockLocation, TailorBalanceEntry, TapsiOrder,
    TapsiPriceRule, WholesaleCustomer, WholesaleInvoice,
)
from core.tapsi_shop_v138 import create_tapsi_order, order_metrics, tapsi_price_for
from core.tailor_ledger_v150 import build_tailor_ledger, live_tailor_balance


class TapsiOneOffSalePriceV150Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="v150-tapsi", password="test")
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="دارما")
        self.size = Size.objects.create(name="XXL")
        self.color = Color.objects.create(name="مشکی")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        self.product = ProductCode.objects.create(
            brand=self.brand, code="P4", title="پک چهار عددی", pack_qty=4
        )
        ProductComposition.objects.create(product=self.product, color=self.color, qty=4)
        self.ps = ProductSize.objects.create(
            product=self.product, size=self.size, active=True, default_sale_price=500000
        )
        self.today = date(2026, 11, 17)
        self.day = SaleDay.objects.create(date=self.today)
        StockBalance.objects.create(
            brand=self.brand, size=self.size, color=self.color, location=self.home, qty=30
        )
        self.rule = TapsiPriceRule.objects.create(
            product_size=self.ps, effective_from=self.today, price=816000
        )

    def test_order_screen_has_editable_current_price_and_default_remains(self):
        page = self.client.get(reverse("tapsi_home"), {"date": self.today.isoformat()})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="t150-price"')
        self.assertContains(page, 'id="t150-price-default"')
        self.assertContains(page, "قیمت فروش هر پک")
        self.assertEqual(page.context["tapsi_catalog"][0]["sizes"][0]["price"],816000)
        with open("core/static/core/tapsi_portal_v142.js", encoding="utf-8") as handle:
            js = handle.read()
        self.assertIn('chosenPrice.name="unit_price"', js)

    def test_post_custom_price_updates_snapshot_only_not_rule_or_future_orders(self):
        response=self.client.post(reverse("tapsi_hub_create"),{
            "order_date":self.today.isoformat(),
            "product_size_id":[str(self.ps.id)],
            "quantity":["2"],
            "unit_price":["910000"],
            "discount_cost":"0",
        })
        self.assertEqual(response.status_code,302)
        order=TapsiOrder.objects.get()
        item=order.items.get()
        self.assertEqual(item.unit_price,910000)
        self.assertEqual(item.quantity,2)
        self.assertEqual(order_metrics(order)["gross"],1820000)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.price,816000)
        self.assertEqual(tapsi_price_for(self.ps,self.today),816000)
        self.assertEqual(StockBalance.objects.get(brand=self.brand,size=self.size,color=self.color).qty,22)
        second=create_tapsi_order(self.day,[(self.ps.id,1)])
        self.assertEqual(second.items.get().unit_price,816000)
        self.assertEqual(StockBalance.objects.get(brand=self.brand,size=self.size,color=self.color).qty,18)

    def test_invalid_price_and_bad_multiplicity_never_change_stock_or_save_order(self):
        stock=StockBalance.objects.get(brand=self.brand)
        for value in ["0","-1","این قیمت","10000000001"]:
            page=self.client.post(reverse("tapsi_hub_create"),{
                "order_date":self.today.isoformat(),
                "product_size_id":[str(self.ps.pk)],
                "quantity":["1"],
                "unit_price":[value],
            })
            self.assertEqual(page.status_code,302)
            self.assertFalse(TapsiOrder.objects.exists())
            stock.refresh_from_db()
            self.assertEqual(stock.qty,30)
        self.client.post(reverse("tapsi_hub_create"),{
            "order_date":self.today.isoformat(),
            "product_size_id":[str(self.ps.pk)],
            "quantity":["1"],
            "unit_price":["900000","950000"],
        })
        self.assertFalse(TapsiOrder.objects.exists())
        stock.refresh_from_db()
        self.assertEqual(stock.qty,30)
        # Old V149 cached forms omit unit_price and must still use the
        # canonical catalog default, not silently fail.
        self.client.post(reverse("tapsi_hub_create"),{
            "order_date":self.today.isoformat(),
            "product_size_id":[str(self.ps.pk)],
            "quantity":["1"],
        })
        self.assertEqual(TapsiOrder.objects.count(),1)
        self.assertEqual(TapsiOrder.objects.get().items.get().unit_price,816000)

    def test_tapsi_existing_service_call_without_override_unchanged(self):
        order=create_tapsi_order(self.day,[(self.ps.id,1)], discount_cost=0)
        self.assertEqual(order.items.get().unit_price,816000)

    def test_custom_zero_default_can_be_sold_without_creating_wrong_rule(self):
        self.rule.delete()
        self.ps.default_sale_price=0
        self.ps.save(update_fields=["default_sale_price"])
        order=create_tapsi_order(
            self.day,[(self.ps.pk,1)],unit_prices={str(self.ps.pk):"990000"}
        )
        self.assertEqual(order.items.get().unit_price,990000)
        self.assertEqual(TapsiPriceRule.objects.count(),0)


class FullTailorLedgerV150Tests(TestCase):
    def setUp(self):
        u=get_user_model().objects.create_user(username="v150-ledger",password="test")
        self.client.force_login(u)
        self.person=ExcelManualRow.objects.create(
            section=ExcelManualRow.PERSONS,
            title="خیاط",amount=-265000,sort_order=10,
            note="مانده خیاط",
        )
        self.brand=Brand.objects.create(name="دارما")
        self.block=MaterialReportBlock.objects.create(
            brand=self.brand,date=date(2026,11,3),title="برش مشکی",
            input_data={},output_data={},delivery_wage=165000,
        )
        MaterialReportOutputApplied.objects.create(
            block=self.block,model_key="black",size_key="m",quantity=18
        )
        self.payment=BusinessPayment.objects.create(
            date=date(2026,11,6),payee="tailor",
            source_account="mofid",amount=100000,note="پرداخت مرحله اول"
        )
        self.customer=WholesaleCustomer.objects.create(name="پدرام",is_pedram=True)
        self.invoice=WholesaleInvoice.objects.create(
            date=date(2026,11,9),customer=self.customer,
            total_amount=200000,quantity_total=4,note="فاکتور عمده",
        )

    def test_current_balance_opens_reconstructed_and_all_streams_reconcile(self):
        report=build_tailor_ledger()
        self.assertEqual(live_tailor_balance(),-265000)
        self.assertEqual(report["debt"],265000)
        self.assertEqual(report["advance"],0)
        self.assertEqual(report["totals"],{
            "wage":165000,"payments":100000,"wholesale":200000
        })
        self.assertEqual(report["base_reconstructed"],-400000)
        self.assertEqual(report["entries"][-1]["balance"],-265000)
        self.assertEqual(len(report["entries"]),3)
        self.assertEqual({r["origin"] for r in report["entries"]},
                         {"production","payment","wholesale"})
        self.assertEqual(report["entries"][0]["charge"],165000)
        self.assertEqual(report["entries"][1]["payment"],100000)

    def test_unapplied_draft_wage_never_counted(self):
        MaterialReportBlock.objects.create(
            brand=self.brand,date=date(2026,11,10),title="پیش‌نویس",
            delivery_wage=500000,
        )
        report=build_tailor_ledger()
        self.assertEqual(len(report["entries"]),3)
        self.assertEqual(report["totals"]["wage"],165000)

    def test_old_pedram_account_is_separate_not_double_counted(self):
        pedram=Account.objects.create(
            key=Account.PEDRAM,title="پدرام قدیمی",opening_balance=75000
        )
        AccountEntry.objects.create(
            account=pedram,date=date(2026,11,1),
            delta=-110000,title="مزد قدیمی",reference="legacy:1"
        )
        bank=Account.objects.create(key=Account.MELAT,title="ملت",opening_balance=0)
        MoneyMovement.objects.create(
            date=date(2026,11,2),kind=MoneyMovement.TRANSFER,amount=30000,
            from_account=bank,to_account=pedram,title="واریزی قدیمی"
        )
        report=build_tailor_ledger()
        self.assertEqual(report["legacy_account_opening"],75000)
        self.assertEqual(report["legacy_account_current"],-5000)
        self.assertEqual(report["legacy_account_entries"][-1]["balance"],-5000)
        self.assertEqual(report["current"],-265000)
        self.assertEqual(report["base_reconstructed"],-400000)

    def test_legacy_balance_events_are_exported_without_double_counting(self):
        TailorBalanceEntry.objects.create(
            date=date(2026,11,2),delta=-5000,
            title="رویداد قدیمی",reference="tailor-old-1"
        )
        report=build_tailor_ledger()
        self.assertEqual(report["legacy_events"][0]["delta"],-5000)
        self.assertEqual(report["current"],-265000)
        self.assertEqual(len(report["entries"]),3)

    def test_full_excel_export_contains_all_rows_and_is_read_only(self):
        for i in range(105):
            BusinessPayment.objects.create(
                date=date(2026,11,12),payee="pedram",
                source_account="melat",amount=10,
                note=f"پرداخت قدیمی شماره {i}",
            )
        TailorBalanceEntry.objects.create(
            date=date(2026,11,2),delta=123,
            title="=HYPERLINK(\"x\",\"y\")",reference="old-log"
        )
        before={
            "person":self.person.amount,
            "payments":BusinessPayment.objects.count(),
            "blocks":MaterialReportBlock.objects.count(),
            "entries":TailorBalanceEntry.objects.count(),
            "invoices":WholesaleInvoice.objects.count(),
        }
        page=self.client.get(reverse("tailor_ledger"))
        self.assertEqual(page.status_code,200)
        self.assertContains(page,"بدهی خیاط")
        self.assertContains(page,'data-tailor-ledger="v150"')
        self.assertContains(page,"پرداخت مرحله اول")
        resp=self.client.get(reverse("tailor_ledger_xlsx"))
        self.assertEqual(resp.status_code,200)
        self.assertEqual(resp["Content-Type"],
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        wb=load_workbook(BytesIO(resp.content),read_only=True)
        self.assertEqual(wb.sheetnames,[
            "گردش حساب خیاط","حساب پدرام قدیمی",
            "سوابق مستقل خیاط","راهنما و تطبیق"
        ])
        ws=wb["گردش حساب خیاط"]
        self.assertEqual(ws.max_row,1+1+108)
        self.assertEqual(ws.cell(ws.max_row,6).value,-265000)
        self.assertTrue(wb["سوابق مستقل خیاط"].cell(2,3).value.startswith("'=HYPERLINK"))
        self.person.refresh_from_db()
        self.assertEqual(before,{
            "person":self.person.amount,
            "payments":BusinessPayment.objects.count(),
            "blocks":MaterialReportBlock.objects.count(),
            "entries":TailorBalanceEntry.objects.count(),
            "invoices":WholesaleInvoice.objects.count(),
        })

    def test_requires_authentication(self):
        self.client.logout()
        for name in ["tailor_ledger","tailor_ledger_xlsx"]:
            resp=self.client.get(reverse(name))
            self.assertEqual(resp.status_code,302)
