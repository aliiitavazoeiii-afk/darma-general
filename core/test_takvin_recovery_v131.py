"""V131 disposable-Postgres tests; never touch production finance."""
from datetime import date, datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import (
    AppSetting, BusinessPayment, Color, ExcelManualRow,
    ExcelManualSetting, Size, TakvinPurchase
)
from core.management.commands import recover_takvin_deleted_50m_v131 as rec


class RecoverTakvinDeleted50MV131Tests(TestCase):
    def setUp(self):
        self.setting = ExcelManualSetting.objects.create(
            key="takvin_debt", label="بدهی تکوین", value=50_000_000
        )
        self.setting.updated_at = datetime.fromisoformat(rec.ORIGINAL_BALANCE_UPDATE)
        ExcelManualSetting.objects.filter(pk=self.setting.pk).update(
            updated_at=self.setting.updated_at
        )
        self.melat = ExcelManualRow.objects.create(
            section=ExcelManualRow.ACCOUNTS, title="حساب ملت",
            amount=100_000_000, active=True,
        )
        self.mofid = ExcelManualRow.objects.create(
            section=ExcelManualRow.ACCOUNTS, title="مانده مفید",
            amount=80_000_000, active=True,
        )
        for pk, amount in rec.PRIOR_PAYMENT_IDS.items():
            BusinessPayment.objects.create(
                id=pk, date=date(2026, 9, 20), payee="takvin",
                source_account="melat", amount=amount
            )
        size = Size.objects.create(name="XL")
        color = Color.objects.create(name="مشکی")
        for idx in range(rec.PRIOR_PURCHASE_COUNT):
            TakvinPurchase.objects.create(
                date=date(2026, 10, 5), size=size, color=color, qty=1,
                list_unit_price=7_087_500, discount_percent=0,
                net_unit_price=7_087_500, total_cost=7_087_500
            )

    def cmd(self, bank="melat", apply=False, expected=None, approval="", **opts):
        args = dict(bank=bank, paid_on="2026-10-29", stdout=StringIO())
        if expected is not None:
            args["expected_bank_balance"] = expected
        if apply:
            args["apply"] = True
        if approval:
            args["approval"] = approval
        args.update(opts)
        call_command("recover_takvin_deleted_50m_v131", **args)
        return args["stdout"].getvalue()

    def balances(self):
        self.setting.refresh_from_db()
        self.melat.refresh_from_db()
        self.mofid.refresh_from_db()
        return self.setting.value, self.melat.amount, self.mofid.amount

    def test_preview_read_only_even_when_bank_is_selected(self):
        for bank in ("melat", "mofid"):
            s = self.cmd(bank=bank)
            self.assertIn("DRY_RUN_OK: ZERO DATABASE WRITES", s)
            self.assertIn("TAKVIN_EXPECTED_AFTER=-2480000", s)
            self.assertEqual(self.balances(), (50_000_000, 100_000_000, 80_000_000))
            self.assertEqual(BusinessPayment.objects.count(), 3)
            self.assertFalse(AppSetting.objects.filter(key=rec.MARKER).exists())

    def test_recovered_melat_payment_is_once_atomic_and_exact(self):
        s = self.cmd(apply=True, expected=100_000_000, approval=rec.TOKEN)
        self.assertIn("SUCCESS: V131 EXACT TAKVIN PAYMENT RECOVERED ONCE", s)
        self.assertEqual(self.balances(), (-2_480_000, 50_000_000, 80_000_000))
        self.assertEqual(BusinessPayment.objects.filter(payee="takvin").count(), 4)
        p = BusinessPayment.objects.get(payee="takvin", amount=50_000_000)
        self.assertEqual((p.date, p.source_account), (date(2026, 10, 29), "melat"))
        self.assertTrue(AppSetting.objects.filter(key=rec.MARKER).exists())
        with self.assertRaises(CommandError):
            self.cmd(apply=True, expected=50_000_000, approval=rec.TOKEN)
        self.assertEqual(self.balances(), (-2_480_000, 50_000_000, 80_000_000))

    def test_recovered_mofid_payment_debits_only_mofid(self):
        self.cmd(bank="mofid", apply=True, expected=80_000_000, approval=rec.TOKEN)
        self.assertEqual(self.balances(), (-2_480_000, 100_000_000, 30_000_000))
        p = BusinessPayment.objects.get(payee="takvin", amount=50_000_000)
        self.assertEqual(p.source_account, "mofid")

    def test_no_authorization_no_written_financial_entries(self):
        for kw in (
            {"apply": True, "expected": 100_000_000},
            {"apply": True, "approval": rec.TOKEN},
            {"apply": True, "expected": 1, "approval": rec.TOKEN},
        ):
            with self.assertRaises(CommandError):
                self.cmd(**kw)
        self.assertEqual(self.balances(), (50_000_000, 100_000_000, 80_000_000))
        self.assertEqual(BusinessPayment.objects.count(), 3)

    def test_changed_debt_setting_or_purchase_history_aborts(self):
        self.setting.value = 47_520_000
        self.setting.save(update_fields=["value"])
        with self.assertRaises(CommandError):
            self.cmd(apply=True, expected=100_000_000, approval=rec.TOKEN)
        self.assertEqual(BusinessPayment.objects.count(), 3)

    def test_core_payment_raises_mid_transaction_and_everything_rolls_back(self):
        with patch.object(rec, "_apply_full", side_effect=RuntimeError("simulated bank outage")):
            with self.assertRaises(RuntimeError):
                self.cmd(apply=True, expected=100_000_000, approval=rec.TOKEN)
        self.assertEqual(self.balances(), (50_000_000, 100_000_000, 80_000_000))
        self.assertEqual(BusinessPayment.objects.count(), 3)
        self.assertFalse(AppSetting.objects.filter(key=rec.MARKER).exists())
