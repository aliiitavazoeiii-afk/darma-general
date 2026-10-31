"""One-time, evidence-locked recovery of the deleted *real* 50M Takvin payment.

Defaults to READ ONLY. Requires source bank, actual payment date, an exact
expected bank balance and a distinctive approval token before any writes.
Run only after taking a fresh complete PostgreSQL backup. Based on the
user's independently examined 2026-10-26/28/31 SQL backup snapshots.
"""
from datetime import date, datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from core.business_tools_v62 import _apply_full
from core.models import (
    AppSetting, BusinessPayment, ExcelManualSetting, TakvinPurchase,
)
from core.payment_source_v63 import SOURCE_MELAT, SOURCE_MOFID, source_row


WRONG_BALANCE = 50_000_000
OLD_BALANCE = 47_520_000
REAL_PAYMENT = 50_000_000
CORRECT_BALANCE = OLD_BALANCE - REAL_PAYMENT  # -2,480,000 credit
PRIOR_PAYMENT_IDS = {11: 32_625_000, 43: 10_000_000, 47: 55_880_000}
PRIOR_PURCHASE_COUNT = 16
PRIOR_PURCHASE_TOTAL = 113_400_000
ORIGINAL_BALANCE_UPDATE = "2026-10-29T06:52:15.031509+00:00"
MARKER = "takvin-real-payment-recovery-v131"
TOKEN = "I_CONFIRM_REAL_50M_BANK_TRANSFER_AND_NO_DUPLICATE"


class Command(BaseCommand):
    help = "V131: DRY-RUN by default. Restore deleted 50M Takvin payment once with precise bank/date checks."

    def add_arguments(self, parser):
        parser.add_argument("--bank", required=True, choices=[SOURCE_MELAT, SOURCE_MOFID])
        parser.add_argument("--paid-on", required=True, help="Actual Gregorian bank transfer date YYYY-MM-DD")
        parser.add_argument("--expected-bank-balance", type=int)
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--approval", default="")

    def handle(self, *args, **options):
        try:
            paid_on = date.fromisoformat(options["paid_on"])
        except ValueError as exc:
            raise CommandError("Invalid Gregorian payment date: use YYYY-MM-DD") from exc
        if not date(2026, 10, 28) <= paid_on <= date(2026, 11, 2):
            raise CommandError("Payment date outside the incident window; review bank evidence first.")

        bank = options["bank"]
        do_apply = bool(options["apply"])
        if do_apply:
            if options["approval"] != TOKEN:
                raise CommandError("Explicit bank-transfer approval token missing; NO WRITES.")
            if options["expected_bank_balance"] is None:
                raise CommandError("Exact bank balance from recent DRY-RUN is required; NO WRITES.")

        with transaction.atomic():
            debt_row = ExcelManualSetting.objects.select_for_update().filter(key="takvin_debt").first()
            if debt_row is None:
                raise CommandError("Takvin balance setting absent; NO WRITES.")
            debt = int(debt_row.value or 0)
            updated = debt_row.updated_at.astimezone(dt_timezone.utc).isoformat()
            if debt != WRONG_BALANCE or updated != ORIGINAL_BALANCE_UPDATE:
                raise CommandError(
                    f"Unexpected Takvin account state debt={debt} updated={updated}. "
                    "This recovery applies ONLY to the audited incident; NO WRITES."
                )

            if AppSetting.objects.filter(key=MARKER).exists():
                raise CommandError("This recovery has already been recorded; refusing duplicate payment.")

            prior_payments = dict(
                BusinessPayment.objects.filter(payee="takvin").values_list("id", "amount")
            )
            if prior_payments != PRIOR_PAYMENT_IDS:
                raise CommandError(
                    f"Takvin payments changed since audit: {prior_payments}. NO WRITES."
                )
            purchase_qs = TakvinPurchase.objects.all()
            p_count = purchase_qs.count()
            p_total = int(purchase_qs.aggregate(v=Sum("total_cost"))["v"] or 0)
            if (p_count, p_total) != (PRIOR_PURCHASE_COUNT, PRIOR_PURCHASE_TOTAL):
                raise CommandError("Takvin purchase history changed since backups; NO WRITES.")
            if BusinessPayment.objects.filter(payee="takvin", amount=REAL_PAYMENT).exists():
                raise CommandError("Another 50M Takvin payment is already active; NO WRITES.")

            melat = source_row(SOURCE_MELAT, create=False, for_update=do_apply)
            mofid = source_row(SOURCE_MOFID, create=False, for_update=do_apply)
            if melat is None or mofid is None or melat.id == mofid.id:
                raise CommandError("Distinct existing Mellat and Mofid balances required; NO WRITES.")
            source = melat if bank == SOURCE_MELAT else mofid
            other = mofid if bank == SOURCE_MELAT else melat
            starting = int(source.amount or 0)
            other_before = int(other.amount or 0)
            if options["expected_bank_balance"] is not None and starting != options["expected_bank_balance"]:
                raise CommandError(
                    f"Bank balance changed since inspection: current={starting}, "
                    f"expected={options['expected_bank_balance']}; NO WRITES."
                )
            self.stdout.write("=== V131 TAKVIN DELETED-PAYMENT RECOVERY ===")
            self.stdout.write(f"MODE={'APPLY' if do_apply else 'DRY_RUN_READ_ONLY'}")
            self.stdout.write(f"ORIGINAL_DEBT_FROM_TWO_BACKUPS={OLD_BALANCE}")
            self.stdout.write(f"CORRUPTED_DEBT_CURRENT={debt}")
            self.stdout.write(f"REAL_DELETED_PAYMENT={REAL_PAYMENT}")
            self.stdout.write(f"PAYMENT_DATE_GREGORIAN={paid_on}")
            self.stdout.write(f"BANK_SOURCE={bank} id={source.id} balance_before={starting}")
            self.stdout.write(f"BANK_SOURCE_BALANCE_AFTER={starting - REAL_PAYMENT}")
            self.stdout.write(f"BANK_OTHER={other.id} balance_unchanged={other_before}")
            self.stdout.write(f"TAKVIN_EXPECTED_AFTER={CORRECT_BALANCE} (negative is supplier credit)")
            self.stdout.write(f"PAYMENTS_BEFORE={len(prior_payments)} PAYMENTS_AFTER=4")
            self.stdout.write(f"PURCHASES_UNCHANGED={p_count} total={p_total}")

            if not do_apply:
                self.stdout.write(self.style.SUCCESS("DRY_RUN_OK: ZERO DATABASE WRITES"))
                self.stdout.write(
                    "To apply, take a fresh SQL backup, confirm actual bank/date, "
                    "then supply --expected-bank-balance, --apply and --approval."
                )
                return

            # Crucial: restore the *pre*-clamp liability first, then call the
            # canonical V130 payment posting path exactly once. Both changes
            # commit together; failures roll everything back, including cash.
            debt_row.value = OLD_BALANCE
            debt_row.save(update_fields=["value", "updated_at"])
            payment = BusinessPayment.objects.create(
                date=paid_on,
                payee="takvin",
                source_account=bank,
                amount=REAL_PAYMENT,
                note="بازیابی پرداخت واقعی حذف‌شده تکوین؛ اصلاح خطای صفرشدن بستانکاری V131",
            )
            _apply_full(payment, {
                "purchase": None,
                "prepayment_title": None,
            })
            debt_row.refresh_from_db()
            source.refresh_from_db()
            other.refresh_from_db()
            if int(debt_row.value) != CORRECT_BALANCE:
                raise CommandError("Takvin after-balance assertion failed; transaction rolled back.")
            if int(source.amount) != starting - REAL_PAYMENT:
                raise CommandError("Bank effect assertion failed; transaction rolled back.")
            if int(other.amount) != other_before:
                raise CommandError("Unrelated bank changed; transaction rolled back.")
            if BusinessPayment.objects.filter(payee="takvin").count() != 4:
                raise CommandError("Supplier payment count assertion failed; transaction rolled back.")
            AppSetting.objects.create(
                key=MARKER,
                value=f"payment:{payment.id};bank:{bank};date:{paid_on};old:{OLD_BALANCE}",
                label="V131 one-time verified Takvin 50M real transfer recovery",
            )
            self.stdout.write(f"RECOVERED_BUSINESS_PAYMENT_ID={payment.id}")
            self.stdout.write(self.style.SUCCESS(
                "SUCCESS: V131 EXACT TAKVIN PAYMENT RECOVERED ONCE, ATOMICALLY"
            ))
