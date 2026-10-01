from datetime import date

import jdatetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template.loader import get_template
from django.test import RequestFactory

from core.payment_source_v63 import SOURCE_MELAT, SOURCE_MOFID, source_balance

from expense_tracker.expense_v7 import build_transaction_context
from expense_tracker.models import DailyExpense, ExpenseCategory
from expense_tracker.services import create_expense, delete_expense, update_expense


class Command(BaseCommand):
    help = "Rollback-only V7 regression for dual payment sources and Jalali month grouping."

    def handle(self, *args, **options):
        dashboard_source = get_template("expense_tracker/dashboard.html").template.source
        expenses_source = get_template("expense_tracker/expenses.html").template.source
        edit_source = get_template("expense_tracker/expense_edit.html").template.source

        if 'name="payment_source"' not in dashboard_source or 'value="mofid"' not in dashboard_source:
            raise CommandError("quick expense form is missing Melat/Mofid payment source controls")
        if 'name="payment_source"' not in edit_source:
            raise CommandError("expense edit form is missing payment source control")
        if "ماه‌های گذشته" not in expenses_source or "جمع نتایج" not in expenses_source:
            raise CommandError("transaction month archive UI is missing")

        before_melat = int(source_balance(SOURCE_MELAT) or 0)
        before_mofid = int(source_balance(SOURCE_MOFID) or 0)
        before_expenses = DailyExpense.objects.count()
        before_categories = ExpenseCategory.objects.count()
        today = date.today()

        try:
            with transaction.atomic():
                category = ExpenseCategory.objects.create(
                    name="__EXPENSE_V7_TEST__",
                    slug="expense-v7-test",
                    accent="cyan",
                    sort_order=99998,
                )

                expense = create_expense(
                    expense_date=today,
                    amount=11_000,
                    category=category,
                    payment_source=SOURCE_MOFID,
                    title="v7 mofid",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before_melat:
                    raise CommandError("Mofid expense unexpectedly changed Melat")
                if int(source_balance(SOURCE_MOFID) or 0) != before_mofid - 11_000:
                    raise CommandError("Mofid expense did not debit Mofid exactly")

                expense = update_expense(
                    expense,
                    expense_date=today,
                    amount=17_000,
                    category=category,
                    payment_source=SOURCE_MOFID,
                    title="v7 mofid edited",
                )
                if int(source_balance(SOURCE_MOFID) or 0) != before_mofid - 17_000:
                    raise CommandError("Mofid expense edit did not apply only the amount difference")
                if int(source_balance(SOURCE_MELAT) or 0) != before_melat:
                    raise CommandError("Mofid expense edit unexpectedly changed Melat")

                expense = update_expense(
                    expense,
                    expense_date=today,
                    amount=13_000,
                    category=category,
                    payment_source=SOURCE_MELAT,
                    title="v7 moved to melat",
                )
                if int(source_balance(SOURCE_MOFID) or 0) != before_mofid:
                    raise CommandError("moving expense to Melat did not restore Mofid")
                if int(source_balance(SOURCE_MELAT) or 0) != before_melat - 13_000:
                    raise CommandError("moving expense to Melat did not debit Melat exactly")

                delete_expense(expense)
                if int(source_balance(SOURCE_MELAT) or 0) != before_melat:
                    raise CommandError("expense delete did not restore Melat")
                if int(source_balance(SOURCE_MOFID) or 0) != before_mofid:
                    raise CommandError("expense delete changed Mofid after source move")

                current_j = jdatetime.date.fromgregorian(date=today)
                if current_j.month == 1:
                    prev_j = jdatetime.date(current_j.year - 1, 12, 1)
                else:
                    prev_j = jdatetime.date(current_j.year, current_j.month - 1, 1)
                previous_month_date = prev_j.togregorian()

                marker = "__EXPENSE_V7_MONTH_SEARCH__"
                DailyExpense.objects.create(
                    date=today,
                    amount=11_111,
                    category=category,
                    payment_source=SOURCE_MELAT,
                    title=marker,
                )
                DailyExpense.objects.create(
                    date=previous_month_date,
                    amount=22_222,
                    category=category,
                    payment_source=SOURCE_MELAT,
                    title=marker,
                )

                request = RequestFactory().get("/expenses/", {"q": marker})
                context = build_transaction_context(request, today=today)
                if int(context["current_total"]) != 11_111:
                    raise CommandError(
                        f"current-month search total is wrong: {context['current_total']}"
                    )
                if len(context["historical_months"]) != 1:
                    raise CommandError("previous-month search result was not grouped into one archive month")
                historical = context["historical_months"][0]
                if int(historical["total"]) != 22_222:
                    raise CommandError("historical month total is wrong")
                if int(historical["count"]) != 1:
                    raise CommandError("historical month count is wrong")

                transaction.set_rollback(True)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"V7 rollback regression failed: {exc}") from exc

        if int(source_balance(SOURCE_MELAT) or 0) != before_melat:
            raise CommandError("V7 regression leaked a Melat balance change")
        if int(source_balance(SOURCE_MOFID) or 0) != before_mofid:
            raise CommandError("V7 regression leaked a Mofid balance change")
        if DailyExpense.objects.count() != before_expenses:
            raise CommandError("V7 regression leaked expense rows")
        if ExpenseCategory.objects.count() != before_categories:
            raise CommandError("V7 regression leaked category rows")

        self.stdout.write("EXPENSE V7: Mofid create/edit debits Mofid only")
        self.stdout.write("EXPENSE V7: source switch Mofid -> Melat restores/debits exactly")
        self.stdout.write("EXPENSE V7: delete restores the selected source exactly")
        self.stdout.write("EXPENSE V7: current search total excludes previous Jalali months")
        self.stdout.write("EXPENSE V7: previous month remains available as grouped archive")
        self.stdout.write(self.style.SUCCESS("SUCCESS: EXPENSE TRACKER DUAL ACCOUNT V7 REGRESSION PASSED"))
