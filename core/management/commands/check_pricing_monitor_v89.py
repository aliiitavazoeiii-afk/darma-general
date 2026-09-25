"""Read-only regression for V89 working-day pricing/dashboard changes."""
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings
from django.template.loader import get_template
from django.urls import resolve

from core import excel_dashboard_v89
from core.dateutils import format_jalali
from core.models import AppSetting, SaleLine
from core.pricing_export_v89 import pricing_monitor_xlsx
from core.pricing_monitor_v89 import pricing_monitor, pricing_monitor_data
from core.working_days_v89 import month_bounds, working_dates


class Command(BaseCommand):
    help = "Read-only: validate V89 working-day comparisons, layout routes and XLSX."

    def handle(self, *args, **kwargs):
        before_sales = SaleLine.objects.count()
        before_settings = AppSetting.objects.count()

        if resolve("/").func is not excel_dashboard_v89.dashboard:
            raise RuntimeError("Dashboard route is not V89")
        if resolve("/pricing-monitor/").func is not pricing_monitor:
            raise RuntimeError("Pricing monitor route is not V89")
        if resolve("/pricing-monitor/export/xlsx/").func is not pricing_monitor_xlsx:
            raise RuntimeError("Pricing XLSX route is not V89")

        get_template("core/dashboard_excel_v89.html")
        get_template("core/_pricing_monitor_dashboard_v89.html")
        get_template("core/pricing_monitor_v89.html")

        dashboard_source = Path(settings.BASE_DIR, "templates/core/dashboard_excel_v89.html").read_text(encoding="utf-8")
        pricing_source = Path(settings.BASE_DIR, "templates/core/pricing_monitor_v89.html").read_text(encoding="utf-8")
        if "هشدارها" in dashboard_source:
            raise RuntimeError("Legacy dashboard alerts block still exists")
        if "تا ۳۰ روز" not in dashboard_source:
            raise RuntimeError("30-day dashboard marker missing")
        if "pm-table" not in pricing_source or "white-space:nowrap" not in pricing_source:
            raise RuntimeError("Pricing table alignment guard missing")
        if "نشانه مثبت؛ نرخ تبدیل نامشخص" not in pricing_source:
            raise RuntimeError("Positive evaluation badge text is stale")

        latest_working = (
            SaleLine.objects.filter(
                quantity__gt=0,
                product_size__product__brand__name="دارما",
            )
            .order_by("-day__date")
            .values_list("day__date", flat=True)
            .first()
        )
        probe = latest_working or date.today()
        data = pricing_monitor_data(probe)
        start, _end = month_bounds(probe)
        working = working_dates(start, probe)
        expected_working = probe in working
        if data["is_working_day"] != expected_working:
            raise RuntimeError("Working-day detection mismatch")
        if expected_working:
            expected_number = working.index(probe) + 1
            if data["workday_number"] != expected_number:
                raise RuntimeError("Working-day ordinal mismatch")
        elif data["day_rows"]:
            raise RuntimeError("Holiday/no-sale date produced daily comparison rows")

        user = SimpleNamespace(is_authenticated=True)
        factory = RequestFactory()
        request = factory.get("/pricing-monitor/", {"date": format_jalali(probe)})
        request.user = user
        with override_settings(STORAGES={
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }):
            response = pricing_monitor(request)
        if response.status_code != 200:
            raise RuntimeError(f"V89 pricing render HTTP {response.status_code}")

        request = factory.get("/pricing-monitor/export/xlsx/", {"date": format_jalali(probe)})
        request.user = user
        response = pricing_monitor_xlsx(request)
        if response.status_code != 200 or not response.content.startswith(b"PK"):
            raise RuntimeError("V89 pricing XLSX failed")
        with ZipFile(BytesIO(response.content)) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("V89 XLSX ZIP integrity failed")
            main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            names = [node.attrib["name"] for node in workbook.find(f"{main}sheets")]
            if "مقایسه روز کاری" not in names or "ارزیابی ۱۰ روز کاری" not in names:
                raise RuntimeError("V89 working-day XLSX sheets missing")

        if SaleLine.objects.count() != before_sales or AppSetting.objects.count() != before_settings:
            raise RuntimeError("V89 read-only check changed database row counts")

        self.stdout.write(f"PROBE DATE = {format_jalali(probe)}")
        self.stdout.write(f"WORKING DAY = {data['is_working_day']}")
        self.stdout.write(f"WORKING DAY NUMBER = {data['workday_number']}")
        self.stdout.write(f"PREVIOUS MATCH = {data['previous_day_j']}")
        self.stdout.write("DASHBOARD ALERTS REMOVED = OK")
        self.stdout.write("DASHBOARD 30 SALE DAYS = OK")
        self.stdout.write("PRICING TABLE ALIGNMENT GUARD = OK")
        self.stdout.write("WORKING-DAY XLSX = OK")
        self.stdout.write("NO ROW-COUNT WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: PRICING WORKDAYS + DASHBOARD V89 CHECK PASSED"))
