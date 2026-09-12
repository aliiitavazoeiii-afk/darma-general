from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import RequestFactory
from django.template.loader import get_template
from django.urls import resolve

from core.dateutils import format_jalali
from core.models import AccountEntry, BusinessPayment, InventoryMovement, SaleLine, StockBalance
from core.payment_source_v63 import SOURCE_MELAT, source_balance

from expense_tracker.models import DailyExpense, ExpenseCategory, ReceivableEntry, ReceivablePerson
from expense_tracker import views as expense_views
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

        dashboard_source = get_template("expense_tracker/dashboard.html").template.source
        if 'data-ajax-expense="1"' not in dashboard_source or 'jalali-picker' not in dashboard_source:
            raise CommandError("dashboard is missing AJAX expense entry or Jalali picker marker")
        if "میانگین خرج روزانه" not in dashboard_source or "کل طلب‌های باز" in dashboard_source:
            raise CommandError("dashboard daily-average KPI replacement is missing")

        manifest_match = resolve("/manifest.webmanifest")
        manifest_request = RequestFactory().get("/manifest.webmanifest")
        manifest_response = manifest_match.func(manifest_request)
        if manifest_response.status_code != 200 or b'"display": "standalone"' not in manifest_response.content:
            raise CommandError("expense PWA manifest is not valid/standalone")

        worker_match = resolve("/sw.js")
        worker_request = RequestFactory().get("/sw.js")
        worker_response = worker_match.func(worker_request)
        if worker_response.status_code != 200 or worker_response.get("Service-Worker-Allowed") != "/":
            raise CommandError("expense service worker route/scope is invalid")

        sample_groups = expense_views._group_expenses_by_day(
            [
                type("ExpenseStub", (), {"date": today, "amount": 1000})(),
                type("ExpenseStub", (), {"date": today, "amount": 2000})(),
                type("ExpenseStub", (), {"date": today - timedelta(days=1), "amount": 4000})(),
            ],
            today=today,
        )
        if len(sample_groups) != 2:
            raise CommandError("expense daily grouping did not produce two day groups")
        if sample_groups[0]["label"] != "امروز" or sample_groups[0]["total"] != 3000:
            raise CommandError("today transaction grouping/total is wrong")
        if sample_groups[1]["label"] != "دیروز" or sample_groups[1]["total"] != 4000:
            raise CommandError("yesterday transaction grouping/total is wrong")

        calendar_match = resolve("/calendar/picker/")
        calendar_request = RequestFactory().get("/calendar/picker/")
        calendar_request.user = type("AuthUser", (), {"is_authenticated": True})()
        calendar_response = calendar_match.func(calendar_request)
        if calendar_response.status_code != 200:
            raise CommandError("expense Jalali calendar route did not return HTTP 200")

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

                delete_expense(expense)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("pre-AJAX cleanup did not restore Mellat")

                ajax_request = RequestFactory().post(
                    "/expenses/add/",
                    {
                        "date": format_jalali(today),
                        "amount": "12000",
                        "category": str(category.id),
                        "title": "ajax test",
                        "note": "",
                    },
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                    HTTP_ACCEPT="application/json",
                )
                ajax_request.user = type("AuthUser", (), {"is_authenticated": True})()
                ajax_response = expense_views.expense_add(ajax_request)
                if ajax_response.status_code != 200:
                    raise CommandError("AJAX expense endpoint did not return HTTP 200")
                if b'"ok": true' not in ajax_response.content.lower():
                    raise CommandError("AJAX expense endpoint did not return success JSON")
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 12_000:
                    raise CommandError("AJAX expense did not debit Mellat exactly")
                ajax_expense = DailyExpense.objects.get(title="ajax test", category=category)
                delete_expense(ajax_expense)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("AJAX expense cleanup did not restore Mellat")

                expense = create_expense(
                    expense_date=today,
                    amount=10_000,
                    category=category,
                    title="test for edit",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 10_000:
                    raise CommandError("expense recreate before edit did not debit Mellat")

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

                legacy_claim = ReceivableEntry.objects.create(
                    person=person,
                    date=today,
                    kind=ReceivableEntry.CLAIM,
                    amount=5_000,
                    note="legacy claim",
                    mellat_applied=False,
                )
                delete_receivable_entry(legacy_claim)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("legacy claim delete unexpectedly changed Mellat")

                claim = create_claim(person=person, entry_date=today, amount=40_000, note="test claim")
                if not claim.mellat_applied:
                    raise CommandError("new claim was not marked as Mellat-applied")
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 40_000:
                    raise CommandError("new claim did not debit Mellat exactly")

                repayment = record_repayment(
                    person=person,
                    entry_date=today,
                    amount=15_000,
                    note="test repayment",
                )
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 25_000:
                    raise CommandError("claim repayment did not credit Mellat exactly")

                delete_receivable_entry(repayment)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"] - 40_000:
                    raise CommandError("repayment delete did not reverse Mellat exactly")

                delete_receivable_entry(claim)
                if int(source_balance(SOURCE_MELAT) or 0) != before["mellat"]:
                    raise CommandError("claim delete did not restore Mellat exactly")

                transaction.set_rollback(True)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"V1 rollback regression failed: {exc}") from exc

        after = self._snapshot()
        if before != after:
            raise CommandError(f"rollback regression leaked persistent data: before={before} after={after}")

        self.stdout.write("EXPENSE DASHBOARD V5: elapsed-month daily-average KPI present")
        self.stdout.write("EXPENSE PWA V3: manifest + service worker routes passed")
        self.stdout.write("EXPENSE PWA V3: daily transaction grouping passed")
        self.stdout.write("EXPENSE UI V2: Jalali calendar route rendered HTTP 200")
        self.stdout.write("EXPENSE UI V2: AJAX save returned JSON and debited Mellat exactly")
        self.stdout.write("EXPENSE V1: create 10000 -> Mellat -10000")
        self.stdout.write("EXPENSE V1: edit to 25000 -> Mellat total delta -25000")
        self.stdout.write("EXPENSE V1: delete -> Mellat fully restored")
        self.stdout.write("RECEIVABLE V5: legacy claim delete -> Mellat unchanged")
        self.stdout.write("RECEIVABLE V5: new claim 40000 -> Mellat -40000")
        self.stdout.write("RECEIVABLE V5: repayment 15000 -> Mellat +15000; delete -> reversed")
        self.stdout.write("RECEIVABLE V5: claim delete -> Mellat fully restored")
        self.stdout.write("NO BUSINESS DATA CHANGED")
        self.stdout.write(self.style.SUCCESS("SUCCESS: EXPENSE TRACKER CASHFLOW V5 REGRESSION PASSED"))
