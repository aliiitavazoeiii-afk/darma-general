from datetime import date
from pathlib import Path

import jdatetime
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.template.loader import get_template
from django.test import RequestFactory
from django.urls import resolve, reverse

from core.payment_source_v63 import SOURCE_MELAT, SOURCE_MOFID, source_balance
from expense_tracker.category_report_v8 import _category_report_context
from expense_tracker.models import DailyExpense, ExpenseCategory


class _RegressionUser:
    is_authenticated = True
    username = "expense-v8-regression"

    def get_short_name(self):
        return "expense-v8-regression"


class Command(BaseCommand):
    help = "Rollback-only regression for detailed category reports V8."

    def _snapshot(self):
        return {
            "mellat": int(source_balance(SOURCE_MELAT) or 0),
            "mofid": int(source_balance(SOURCE_MOFID) or 0),
            "expenses": DailyExpense.objects.count(),
            "categories": ExpenseCategory.objects.count(),
        }

    def handle(self, *args, **options):
        template = get_template("expense_tracker/category_report.html")
        template_source = template.template.source
        required_template_markers = (
            'class="largest-list"',
            'class="category-months"',
            "largest_expenses",
            "month_groups",
            "current_month_total",
            "all_total",
        )
        missing_markers = [
            marker for marker in required_template_markers if marker not in template_source
        ]
        if missing_markers:
            raise CommandError(
                f"category report template is missing V8 structural markers: {missing_markers}"
            )

        before = self._snapshot()
        today = date.today()
        current_j = jdatetime.date.fromgregorian(date=today)
        if current_j.month == 1:
            previous_j = jdatetime.date(current_j.year - 1, 12, 15)
        else:
            previous_j = jdatetime.date(current_j.year, current_j.month - 1, 15)
        previous_date = previous_j.togregorian()

        app_js = Path(settings.BASE_DIR, "static", "expense_tracker", "app.js").read_text(encoding="utf-8")
        if "bindCategoryReports" not in app_js or "/reports/category-name/" not in app_js:
            raise CommandError("dashboard/report category rows are not wired to detailed reports")

        # `docker compose run` executes before the long-lived expense container's
        # entrypoint runs collectstatic, so the WhiteNoise manifest may not exist yet.
        # In that pre-start phase we validate context, routes and template source.
        # The same regression runs again inside the live container after collectstatic;
        # only then do we require a full template render using the production manifest.
        static_manifest = Path(settings.STATIC_ROOT) / "staticfiles.json"
        production_static_ready = static_manifest.exists()

        try:
            with transaction.atomic():
                category = ExpenseCategory.objects.create(
                    name="__EXPENSE_V8_CATEGORY__",
                    slug="expense-v8-category",
                    accent="amber",
                    active=True,
                    sort_order=99999,
                )
                DailyExpense.objects.create(
                    date=today,
                    amount=10_000,
                    category=category,
                    payment_source=DailyExpense.SOURCE_MELAT,
                    title="small current",
                )
                DailyExpense.objects.create(
                    date=today,
                    amount=50_000,
                    category=category,
                    payment_source=DailyExpense.SOURCE_MOFID,
                    title="largest current",
                )
                DailyExpense.objects.create(
                    date=previous_date,
                    amount=30_000,
                    category=category,
                    payment_source=DailyExpense.SOURCE_MELAT,
                    title="previous month",
                )

                context = _category_report_context(category, today=today)
                if context["all_total"] != 90_000 or context["all_count"] != 3:
                    raise CommandError("category all-time totals are wrong")
                if context["current_month_total"] != 60_000 or context["current_month_count"] != 2:
                    raise CommandError("category current-month totals are wrong")

                largest = [int(row.amount or 0) for row in context["largest_expenses"]]
                if largest != [50_000, 30_000, 10_000]:
                    raise CommandError(f"largest expenses ordering is wrong: {largest}")
                if len(context["month_groups"]) != 2:
                    raise CommandError("category history did not split into two Jalali months")
                if not context["month_groups"][0]["is_current"]:
                    raise CommandError("current Jalali month is not the first/open category history group")

                by_id_path = reverse("expense_tracker:category_report", args=[category.id])
                by_name_path = reverse("expense_tracker:category_report_by_name", args=[category.name])
                if resolve(by_id_path).url_name != "category_report":
                    raise CommandError("category report by-id route does not resolve correctly")
                if resolve(by_name_path).url_name != "category_report_by_name":
                    raise CommandError("category report by-name route does not resolve correctly")

                if production_static_ready:
                    auth_user = _RegressionUser()
                    factory = RequestFactory()
                    from expense_tracker.category_report_v8 import category_report, category_report_by_name

                    by_id_request = factory.get(by_id_path)
                    by_id_request.user = auth_user
                    response = category_report(by_id_request, category.id)
                    if response.status_code != 200:
                        raise CommandError("category report by id did not render HTTP 200")
                    rendered = response.content.decode("utf-8")
                    if (
                        "بزرگ‌ترین خرج‌ها" not in rendered
                        or category.name not in rendered
                        or "largest-list" not in rendered
                        or "category-months" not in rendered
                    ):
                        raise CommandError("category report by id rendered without required V8 detail sections")

                    by_name_request = factory.get(by_name_path)
                    by_name_request.user = auth_user
                    response = category_report_by_name(by_name_request, category.name)
                    if response.status_code != 200:
                        raise CommandError("category report by name did not render HTTP 200")

                snapshot_now = self._snapshot()
                if snapshot_now["mellat"] != before["mellat"] or snapshot_now["mofid"] != before["mofid"]:
                    raise CommandError("read-only category report regression changed account balances")

                transaction.set_rollback(True)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"category report V8 regression failed: {exc}") from exc

        after = self._snapshot()
        if before != after:
            raise CommandError(f"category report regression leaked data: before={before} after={after}")

        self.stdout.write("CATEGORY REPORT V8: template structural markers passed")
        self.stdout.write("CATEGORY REPORT V8: current-month and all-time totals passed")
        self.stdout.write("CATEGORY REPORT V8: largest expenses sorted descending")
        self.stdout.write("CATEGORY REPORT V8: full history grouped by Jalali month")
        self.stdout.write("CATEGORY REPORT V8: dashboard/report category click wiring present")
        self.stdout.write("CATEGORY REPORT V8: by-id and by-name routes resolve")
        if production_static_ready:
            self.stdout.write("CATEGORY REPORT V8: live template render passed with production static manifest")
        else:
            self.stdout.write("CATEGORY REPORT V8: pre-start render deferred until collectstatic creates manifest")
        self.stdout.write("CATEGORY REPORT V8: Mellat/Mofid unchanged")
        self.stdout.write(self.style.SUCCESS("SUCCESS: EXPENSE CATEGORY REPORT V8 REGRESSION PASSED"))
