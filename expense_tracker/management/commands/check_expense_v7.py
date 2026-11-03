from datetime import date

import jdatetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template.loader import get_template
from django.test import RequestFactory

from core.payment_source_v63 import SOURCE_MELAT, SOURCE_MOFID, source_balance

from expense_tracker.expense_v7 import _jalali_month_day_count, build_transaction_context
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
        if "month.category_totals" not in expenses_source or "month.daily_average" not in expenses_source:
            raise CommandError("archive month category totals or daily average are missing")
        if _jalali_month_day_count(1403, 12) != 30 or _jalali_month_day_count(1402, 12) != 29:
            raise CommandError("Jalali month calendar-day divisor is wrong for Esfand leap years")

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
                other_category = ExpenseCategory.objects.create(
                    name="__EXPENSE_V7_OTHER_CATEGORY__",
                    slug="expense-v7-other-category",
                    accent="blue",
                    sort_order=99997,
                )
                DailyExpense.objects.create(
                    date=previous_month_date,
                    amount=33_333,
                    category=other_category,
                    payment_source=SOURCE_MOFID,
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
                if int(historical["total"]) != 55_555:
                    raise CommandError("historical month total is wrong")
                if int(historical["count"]) != 2:
                    raise CommandError("historical month count is wrong")
                category_totals = [
                    (item["name"], item["total"]) for item in historical["category_totals"]
                ]
                if category_totals != [
                    ("__EXPENSE_V7_OTHER_CATEGORY__", 33_333),
                    ("__EXPENSE_V7_TEST__", 22_222),
                ]:
                    raise CommandError(f"historical category totals are wrong: {category_totals}")
                expected_days = _jalali_month_day_count(prev_j.year, prev_j.month)
                if historical["days_in_month"] != expected_days:
                    raise CommandError("historical month day count is wrong")
                if historical["daily_average"] != round(55_555 / expected_days):
                    raise CommandError("historical daily average is wrong")

                category_request = RequestFactory().get(
                    "/expenses/", {"q": marker, "category": str(category.id)}
                )
                filtered = build_transaction_context(category_request, today=today)
                filtered_month = filtered["historical_months"][0]
                if filtered_month["total"] != 22_222 or filtered_month["count"] != 1:
                    raise CommandError("category-filtered archive month totals are wrong")
                if filtered_month["category_totals"] != [
                    {"name": category.name, "total": 22_222}
                ]:
                    raise CommandError("category-filtered archive breakdown is wrong")
                if filtered_month["daily_average"] != round(22_222 / expected_days):
                    raise CommandError("category-filtered daily average is wrong")

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
        self.stdout.write("EXPENSE ARCHIVE: category subtotals, calendar-day average and filters passed")
        self.stdout.write(self.style.SUCCESS("SUCCESS: EXPENSE TRACKER DUAL ACCOUNT V7 REGRESSION PASSED"))
