from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template.loader import get_template

from core.models import AccountEntry, BusinessPayment, InventoryMovement, SaleLine, StockBalance
from core.payment_source_v63 import SOURCE_MELAT, source_balance

from expense_tracker.models import DailyExpense, ExpenseCategory, ReceivableEntry, ReceivablePerson
from expense_tracker.services import (
    create_claim,
    create_expense,
    delete_expense,
    delete_receivable_entry,
    record_repayment,
    update_expense,
)


class Command(BaseCommand):
    help = "Rollback-only regression for the isolated expense tracker V1."

    def _snapshot(self):
        return {
            "mellat": int(source_balance(SOURCE_MELAT) or 0),
            "business_payments": BusinessPayment.objects.count(),
            "sales": SaleLine.objects.count(),
            "account_entries": AccountEntry.objects.count(),
            "inventory_movements": InventoryMovement.objects.count(),
            "stock_qty": sum(int(q or 0) for q in StockBalance.objects.values_list("qty", flat=True)),
            "expenses": DailyExpense.objects.count(),
            "categories": ExpenseCategory.objects.count(),
            "receivable_people": ReceivablePerson.objects.count(),
            "receivable_entries": ReceivableEntry.objects.count(),
        }

    def handle(self, *args, **options):
        for template in (
            "expense_tracker/base.html",
            "expense_tracker/login.html",
            "expense_tracker/dashboard.html",
            "expense_tracker/expenses.html",
            "expense_tracker/expense_edit.html",
            "expense_tracker/receivables.html",
            "expense_tracker/categories.html",
            "expense_tracker/reports.html",
        ):
            get_template(template)

        before = self._snapshot()
        today = date.today()

        try:
            with transaction.atomic():
                category = ExpenseCategory.objects.create(
                    name="__EXPENSE_V1_TEST__",
                    slug="expense-v1-test",
                    accent="green",
                    sort_order=99999,
                )

                expense = create_expense(
                    expense_date=today,
                    amount=10_000,
                    category=category,
                    title="test",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 10_000:
                    raise CommandError("expense create did not debit Mellat exactly")

                expense = update_expense(
                    expense,
                    expense_date=today,
                    amount=25_000,
                    category=category,
                    title="test updated",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 25_000:
                    raise CommandError("expense update did not apply only the amount difference")

                delete_expense(expense)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("expense delete did not restore Mellat exactly")

                person = ReceivablePerson.objects.create(name="__EXPENSE_V1_PERSON__")
                create_claim(person=person, entry_date=today, amount=40_000, note="test claim")
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("claim creation unexpectedly changed Mellat")

                repayment = record_repayment(
                    person=person,
                    entry_date=today,
                    amount=15_000,
                    note="test repayment",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] + 15_000:
                    raise CommandError("claim repayment did not credit Mellat exactly")

                delete_receivable_entry(repayment)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("repayment delete did not reverse Mellat exactly")

                transaction.set_rollback(True)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"V1 rollback regression failed: {exc}") from exc

        after = self._snapshot()
        if before != after:
            raise CommandError(f"rollback regression leaked persistent data: before={before} after={after}")

        self.stdout.write("EXPENSE V1: create 10000 -> Mellat -10000")
        self.stdout.write("EXPENSE V1: edit to 25000 -> Mellat total delta -25000")
        self.stdout.write("EXPENSE V1: delete -> Mellat fully restored")
        self.stdout.write("RECEIVABLE V1: claim -> Mellat unchanged")
        self.stdout.write("RECEIVABLE V1: repayment 15000 -> Mellat +15000; delete -> restored")
        self.stdout.write("NO BUSINESS DATA CHANGED")
        self.stdout.write(self.style.SUCCESS("SUCCESS: EXPENSE TRACKER V1 REGRESSION PASSED"))
