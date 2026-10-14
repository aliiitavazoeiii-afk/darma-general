"""Isolated regression tests. Django's TEST database only, never live records."""
from uuid import uuid4

from django.http import QueryDict
from django.test import TestCase

from .models import (
    Brand, Color, ExcelManualRow, InventoryMovement, SaleLine,
    Size, StockBalance, StockLocation, WholesaleCustomer,
    WholesaleInvoice, WholesaleReceipt,
)
from .wholesale_logic_v119 import account, add_receipt, post_invoice


class NovaniWholesaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand, _ = Brand.objects.get_or_create(name="Novani", defaults={"active": True})
        cls.brand.active = True
        cls.brand.save(update_fields=["active"])
        cls.color, _ = Color.objects.get_or_create(name="مدل تست عمده", defaults={"active": True})
        cls.color.active = True
        cls.color.save(update_fields=["active"])
        cls.size, _ = Size.objects.get_or_create(name="S")
        cls.home, _ = StockLocation.objects.get_or_create(
            key=StockLocation.HOME, defaults={"title": "خانه"}
        )
        cls.stock, _ = StockBalance.objects.update_or_create(
            brand=cls.brand, color=cls.color, size=cls.size,
            location=cls.home, defaults={"qty": 10}
        )
        cls.person = ExcelManualRow.objects.create(
            section=ExcelManualRow.PERSONS, title="خریدار تست عمده",
            amount=0, active=True,
        )
        cls.buyer = WholesaleCustomer.objects.create(
            name="خریدار تست عمده", account_row=cls.person,
        )
        cls.tailor = ExcelManualRow.objects.create(
            section=ExcelManualRow.PERSONS, title="خیاط",
            amount=500000, active=True
        )
        cls.mellat = ExcelManualRow.objects.create(
            section=ExcelManualRow.ACCOUNTS, title="ملت",
            amount=100000, active=True
        )
        cls.pedram = WholesaleCustomer.objects.get(name="پدرام")

    def form(self, customer, qty="3", price="85000", token=None):
        form = QueryDict(mutable=True)
        form["customer_id"] = str(customer.pk)
        form["date"] = "۱۴۰۵/۰۷/۲۲"
        form["request_token"] = str(token or uuid4())
        form.setlist("color_id", [str(self.color.pk)])
        form.setlist("size_id", [str(self.size.pk)])
        form.setlist("quantity", [str(qty)])
        form.setlist("unit_price", [str(price)])
        return form

    def test_generic_invoice_deducts_stock_and_creates_real_receivable(self):
        form = self.form(self.buyer)
        inv = post_invoice(form)
        self.assertEqual(inv.total_amount, 255000)
        self.assertEqual(inv.quantity_total, 3)
        self.stock.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(self.stock.qty, 7)
        self.assertEqual(self.person.amount, 255000)
        self.assertEqual(InventoryMovement.objects.filter(
            reference__startswith=f"novani-wholesale:{inv.pk}:"
        ).count(), 1)
        self.assertEqual(SaleLine.objects.count(), 0)
        self.assertEqual(account(self.buyer)["balance"], 255000)

        with self.assertRaises(ValueError):
            post_invoice(form)  # the exact request can never debit again
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.qty, 7)

    def test_pedram_offsets_existing_tailor_and_never_credits_mellat(self):
        invoice = post_invoice(self.form(self.pedram, qty="2", price="90000"))
        self.tailor.refresh_from_db()
        self.mellat.refresh_from_db()
        self.assertEqual(self.tailor.amount, 320000)
        self.assertEqual(self.mellat.amount, 100000)
        self.assertEqual(invoice.tailor_deducted_amount, 180000)
        self.assertEqual(account(self.pedram)["gross"], 180000)
        self.assertEqual(account(self.pedram)["balance"], 0)

    def test_shortage_cannot_partially_debit_anything(self):
        with self.assertRaises(ValueError):
            post_invoice(self.form(self.buyer, qty="11"))
        self.stock.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(self.stock.qty, 10)
        self.assertEqual(self.person.amount, 0)
        self.assertEqual(WholesaleInvoice.objects.count(), 0)

    def test_receipt_transfers_receivable_to_mellat_once(self):
        post_invoice(self.form(self.buyer))
        receipt_form = QueryDict(mutable=True)
        receipt_form["customer_id"] = str(self.buyer.pk)
        receipt_form["date"] = "۱۴۰۵/۰۷/۲۲"
        receipt_form["amount"] = "100000"
        receipt_form["request_token"] = str(uuid4())
        receipt = add_receipt(receipt_form)
        self.assertEqual(receipt.amount, 100000)
        self.person.refresh_from_db()
        self.mellat.refresh_from_db()
        self.assertEqual(self.person.amount, 155000)
        self.assertEqual(self.mellat.amount, 200000)
        self.assertEqual(account(self.buyer)["balance"], 155000)
        with self.assertRaises(ValueError):
            add_receipt(receipt_form)
        self.assertEqual(WholesaleReceipt.objects.count(), 1)

    def test_pedram_cannot_receive_second_payment(self):
        form = QueryDict(mutable=True)
        form["customer_id"] = str(self.pedram.pk)
        form["date"] = "۱۴۰۵/۰۷/۲۲"
        form["amount"] = "5000"
        form["request_token"] = str(uuid4())
        with self.assertRaises(ValueError):
            add_receipt(form)
