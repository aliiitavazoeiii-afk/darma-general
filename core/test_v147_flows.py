"""V147 financial receipts and exactly-once new production-sheet fabric transfers."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core import business_receipts_v64 as receipts
from core.dateutils import format_jalali
from core.material_flow import FABRIC, ELASTIC, WAREHOUSE, TAILOR
from core.models import (
    Account, AccountEntry, Brand, Color, DigikalaSettlement,
    MaterialReportBlock, MaterialReportFabricTransfer, ProductCode,
    ProductComposition, ProductSize, RawMaterialStock, SaleDay, Size,
    StockBalance, StockLocation, TapsiOrder,
)
from core.production_fabric_auto_v147 import (
    sync_sheet_auto_fabric, reverse_sheet_auto_fabric,
)
from core.tapsi_shop_v138 import create_tapsi_order, tapsi_receivable_total
from core.business_tools_v14 import mellat_balance
from core.capital_history_v87 import current_capital_breakdown


class TapsiReceiptsV147Tests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(username="v147-receipt", password="test")
        self.client.force_login(u)
        self.brand = Brand.objects.create(name="دارما")
        m = Size.objects.create(name="M")
        black = Color.objects.create(name="مشکی")
        home = StockLocation.objects.create(key=StockLocation.HOME, title="خانه")
        StockLocation.objects.create(key=StockLocation.KHORSHID, title="خورشید")
        product = ProductCode.objects.create(brand=self.brand, code="ABC", pack_qty=3)
        ProductComposition.objects.create(product=product, color=black, qty=3)
        size = ProductSize.objects.create(product=product, size=m, default_sale_price=900000)
        StockBalance.objects.create(brand=self.brand, size=m, color=black, location=home, qty=60)
        self.day = SaleDay.objects.create(date=date(2026, 11, 9))
        self.order = create_tapsi_order(self.day, [(size.id, 1)])

    def test_receipt_add_edit_delete_and_capital_transfer(self):
        earned = tapsi_receivable_total()
        bank0 = mellat_balance()
        capital0 = current_capital_breakdown()["capital_total"]
        self.assertGreater(earned, 300000)
        self.assertEqual(receipts.SOURCE_TAPSI, "tapsi")
        self.assertIn(("tapsi", "تپسی‌شاپ"), receipts.SOURCE_CHOICES)
        p = {"source": "tapsi", "date": format_jalali(self.day.date), "amount": "100000", "note": "تسویه آزمایشی"}
        a = self.client.post(reverse("receipt_add"), p)
        self.assertEqual(a.status_code, 302)
        receipt = DigikalaSettlement.objects.get(source="tapsi")
        self.assertEqual(tapsi_receivable_total(), earned - 100000)
        self.assertEqual(mellat_balance(), bank0 + 100000)
        self.assertEqual(current_capital_breakdown()["capital_total"], capital0)
        self.assertEqual(AccountEntry.objects.filter(
            account__key=Account.TAPSI, reference=f"receipt:{receipt.pk}:tapsi-shop", delta=-100000
        ).count(), 1)
        self.assertContains(self.client.get(reverse("payments"), {"section": "receipts"}), "تپسی‌شاپ")
        self.assertContains(self.client.get(reverse("finance")), 'data-finance-kpi="tapsi"')
        self.assertNotContains(self.client.get(reverse("finance")), 'data-finance-tapsi-receivable="v144"')

        p["amount"] = "150000"
        self.client.post(reverse("receipt_update", args=[receipt.id]), p)
        receipt.refresh_from_db()
        self.assertEqual(receipt.amount, 150000)
        self.assertEqual(tapsi_receivable_total(), earned - 150000)
        self.assertEqual(mellat_balance(), bank0 + 150000)
        self.assertEqual(current_capital_breakdown()["capital_total"], capital0)

        self.client.post(reverse("receipt_delete", args=[receipt.id]))
        self.assertFalse(DigikalaSettlement.objects.filter(source="tapsi").exists())
        self.assertEqual(tapsi_receivable_total(), earned)
        self.assertEqual(mellat_balance(), bank0)
        self.assertEqual(current_capital_breakdown()["capital_total"], capital0)

    def test_receipt_more_than_unpaid_claim_rolls_back_everything(self):
        earned = tapsi_receivable_total()
        before = current_capital_breakdown()["capital_total"]
        bank = mellat_balance()
        result = self.client.post(reverse("receipt_add"), {
            "source": "tapsi", "date": format_jalali(self.day.date),
            "amount": str(earned + 1),
        })
        self.assertEqual(result.status_code, 302)
        self.assertFalse(DigikalaSettlement.objects.filter(source="tapsi").exists())
        self.assertEqual(tapsi_receivable_total(), earned)
        self.assertEqual(mellat_balance(), bank)
        self.assertEqual(current_capital_breakdown()["capital_total"], before)


class ProductionFabricAutoV147Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="v147-production", password="test")
        self.client.force_login(self.user)
        self.brand = Brand.objects.create(name="دارما")
        self.stock = RawMaterialStock.objects.create(
            kind=FABRIC, location=WAREHOUSE, material_key="black",
            title="مشکی", unit_price=1900000, quantity=Decimal("10.000"), unit="کیلو",
        )
        self.elastic = RawMaterialStock.objects.create(
            kind=ELASTIC, location=WAREHOUSE, material_key="black",
            title="کش مشکی", variant="16", unit_price=2400000, quantity=Decimal("4.000"), unit="کیلو",
        )
        self.block = MaterialReportBlock.objects.create(
            date=date(2026, 11, 9), title="تولید مشکی", brand=self.brand,
            input_data={
                "_meta": {"active_material_keys": ["black"], "auto_fabric_transfer_v147": True},
                "black": {"fabric_code": "FAB-1", "weight": "3", "elastic16": "2"},
            },
            output_data={},
        )

    def _qty(self, location, kind=FABRIC):
        return sum(
            (row.quantity for row in RawMaterialStock.objects.filter(
                active=True, material_key="black", location=location, kind=kind
            )), Decimal(0)
        )

    def test_new_sheet_transfer_repeated_save_delta_and_safe_reverse(self):
        self.assertEqual(self._qty(WAREHOUSE), Decimal("10"))
        sync_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("7"))
        self.assertEqual(self._qty(TAILOR), Decimal("3"))
        self.assertEqual(self._qty(WAREHOUSE, ELASTIC), Decimal("4"))
        self.assertEqual(self._qty(TAILOR, ELASTIC), Decimal("0"))
        self.assertEqual(MaterialReportFabricTransfer.objects.count(), 1)
        sync_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("7"))
        self.block.input_data["black"]["weight"] = "5"
        sync_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("5"))
        self.assertEqual(self._qty(TAILOR), Decimal("5"))
        self.block.input_data["black"]["weight"] = "2"
        sync_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("8"))
        self.assertEqual(self._qty(TAILOR), Decimal("2"))
        reverse_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("10"))
        self.assertEqual(self._qty(TAILOR), Decimal("0"))
        self.assertFalse(MaterialReportFabricTransfer.objects.exists())
        self.assertEqual(self._qty(WAREHOUSE, ELASTIC), Decimal("4"))

    def test_legacy_sheet_never_double_transfers(self):
        self.block.input_data["_meta"].pop("auto_fabric_transfer_v147")
        sync_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("10"))
        self.assertEqual(self._qty(TAILOR), Decimal("0"))
        self.assertFalse(MaterialReportFabricTransfer.objects.exists())

    def test_insufficient_warehouse_does_not_mutate_stock_or_sheet(self):
        self.block.input_data["black"]["weight"] = "11"
        response = self.client.post(reverse("material_block_save", args=[self.block.id]), {
            "brand": str(self.brand.id),
            "date": format_jalali(self.block.date),
            "title": self.block.title,
            "active_material_keys": "black",
            "in_black_weight": "11",
            "in_black_fabric_code": "FAB-1",
        })
        self.assertEqual(response.status_code, 302)
        self.block.refresh_from_db()
        self.assertEqual(self.block.input_data["black"]["weight"], "3")
        self.assertEqual(self._qty(WAREHOUSE), Decimal("10"))
        self.assertFalse(MaterialReportFabricTransfer.objects.exists())

    def test_saving_via_real_route_transfers_once_and_delete_returns(self):
        payload = {
            "brand": str(self.brand.id), "date": format_jalali(self.block.date),
            "title": self.block.title, "active_material_keys": "black",
            "in_black_weight": "3", "in_black_fabric_code": "FAB-1",
            "in_black_elastic16": "2",
        }
        self.client.post(reverse("material_block_save", args=[self.block.id]), payload)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("7"))
        self.assertEqual(self._qty(TAILOR), Decimal("3"))
        self.client.post(reverse("material_block_save", args=[self.block.id]), payload)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("7"))
        self.assertEqual(MaterialReportFabricTransfer.objects.count(), 1)
        deleted = self.client.post(reverse("material_block_delete", args=[self.block.id]))
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(MaterialReportBlock.objects.filter(pk=self.block.pk).exists())
        self.assertEqual(self._qty(WAREHOUSE), Decimal("10"))
        self.assertEqual(self._qty(TAILOR), Decimal("0"))

    def test_consumed_fabric_cannot_be_reversed_without_available_tailor_stock(self):
        sync_sheet_auto_fabric(self.block)
        row = RawMaterialStock.objects.get(kind=FABRIC, material_key="black", location=TAILOR)
        row.quantity = Decimal("1")
        row.save(update_fields=["quantity"])
        with self.assertRaisesMessage(ValueError, "مصرف شده"):
            reverse_sheet_auto_fabric(self.block)
        self.assertEqual(self._qty(WAREHOUSE), Decimal("7"))
        self.assertEqual(self._qty(TAILOR), Decimal("1"))
        self.assertEqual(MaterialReportFabricTransfer.objects.count(), 1)
