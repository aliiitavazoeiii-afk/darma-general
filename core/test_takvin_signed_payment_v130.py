"""V130: real payment HTTP flow preserves signed Takvin receivable and exact reversals.

Run only against isolated disposable test database.  Never POST production
money transactions in CI, the read-only audit, or release preflight.
"""
from datetime import date
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import business_tools_v21 as v21
from core.models import BusinessPayment, ExcelManualSetting


class TakvinSignedPaymentV130Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="takvin-v130-ci", password="test-only-not-production"
        )
        self.client.force_login(self.user)
        self.debt = ExcelManualSetting.objects.create(
            key="takvin_debt", label="بدهی تکوین", value=47_600_000
        )
        self.bank = v21._mellat_row(create=True)
        self.bank.amount = 100_000_000
        self.bank.save(update_fields=["amount"])
        self.date = date(2026, 10, 31)

    def _post(self, amount):
        return self.client.post(
            reverse("payment_add"),
            {
                "date": "1405/08/09",
                "payee": "takvin",
                "source_account": "melat",
                "amount": str(amount),
                "note": "V130 isolated reversible Takvin payment",
            },
        )

    def _assert_state(self, debt, bank):
        self.debt.refresh_from_db()
        self.bank.refresh_from_db()
        self.assertEqual(self.debt.value, debt)
        self.assertEqual(self.bank.amount, bank)
        # Supplier debt positive is a liability; negative is a receivable.
        self.assertEqual(self.bank.amount - self.debt.value, 52_400_000)

    def test_overpayment_creates_credit_and_deleted_payment_restores_exact_old_debt(self):
        response = self._post(50_000_000)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessPayment.objects.filter(payee="takvin").count(), 1)
        self._assert_state(-2_400_000, 50_000_000)
        payment = BusinessPayment.objects.get(payee="takvin")
        response = self.client.post(reverse("payment_delete", args=[payment.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BusinessPayment.objects.filter(pk=payment.id).exists())
        self._assert_state(47_600_000, 100_000_000)

    def test_editing_overpaid_amount_reverses_first_and_reapplies_once(self):
        self._post(50_000_000)
        payment = BusinessPayment.objects.get(payee="takvin")
        response = self.client.post(
            reverse("payment_update", args=[payment.id]),
            {
                "date": "1405/08/09",
                "payee": "takvin",
                "source_account": "melat",
                "amount": "49000000",
                "note": "V130 edited overpayment",
            },
        )
        self.assertEqual(response.status_code, 302)
        self._assert_state(-1_400_000, 51_000_000)
        self.assertEqual(BusinessPayment.objects.get(pk=payment.id).amount, 49_000_000)

    def test_existing_supplier_credit_can_increase_in_magnitude(self):
        self.debt.value = -2_400_000
        self.debt.save(update_fields=["value"])
        self._post(500_000)
        self.debt.refresh_from_db()
        self.bank.refresh_from_db()
        self.assertEqual(self.debt.value, -2_900_000)
        self.assertEqual(self.bank.amount, 99_500_000)

    def test_finance_kpi_and_accounts_label_negative_as_credit(self):
        for path in (
            "templates/core/_finance_kpis_v104.html",
            "templates/core/finance_accounts_v97.html",
        ):
            text = (Path(settings.BASE_DIR) / path).read_text("utf-8")
            self.assertIn("takvin_debt < 0", text)
            self.assertIn("طلب از تکوین", text)
            self.assertIn("بدهی تکوین", text)
    def test_read_only_audit_does_not_modify_current_financial_rows(self):
        before = (
            self.debt.value,
            self.bank.amount,
            BusinessPayment.objects.count(),
        )
        output = StringIO()
        call_command("check_takvin_signed_v130", stdout=output)
        text = output.getvalue()
        self.assertIn("TAKVIN_SIGNED_BALANCE_TOMAN=47600000", text)
        self.assertIn("SUCCESS: TAKVIN READ-ONLY AUDIT", text)
        self.debt.refresh_from_db()
        self.bank.refresh_from_db()
        after = (
            self.debt.value,
            self.bank.amount,
            BusinessPayment.objects.count(),
        )
        self.assertEqual(before, after)

