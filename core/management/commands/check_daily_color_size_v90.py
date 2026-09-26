"""Read-only regression for V90 daily product/color/size sales matrix."""
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings
from django.template.loader import get_template

from core.daily_report_v8 import _build_color_size_matrix, daily_report
from core.models import SaleDay, SaleLine


class Command(BaseCommand):
    help = "Read-only: validate V90 daily product/color/size sales matrix and report render."

    def handle(self, *args, **kwargs):
        before_days = SaleDay.objects.count()
        before_lines = SaleLine.objects.count()

        synthetic = [
            {
                "brand_name": "دارما", "code": "pack6", "size_name": "M",
                "shorts": 3, "color_source": "allocation",
                "colors": [
                    {"name": "مشکی", "qty": 2, "replacement_qty": 1},
                    {"name": "سفید", "qty": 1, "replacement_qty": 0},
                ],
            },
            {
                "brand_name": "دارما", "code": "06", "size_name": "L",
                "shorts": 1, "color_source": "allocation",
                "colors": [
                    {"name": "مشکی", "qty": 1, "replacement_qty": 0},
                ],
            },
        ]
        matrix = _build_color_size_matrix(synthetic)
        if matrix["sizes"] != ["M", "L"]:
            raise RuntimeError(f"Unexpected V90 size columns: {matrix['sizes']}")
        if matrix["total"] != 4 or matrix["expected_shorts"] != 4 or matrix["has_mismatch"]:
            raise RuntimeError("V90 matrix total mismatch on synthetic data")
        if not matrix["has_replacement"]:
            raise RuntimeError("V90 replacement marker was lost")

        black = next((row for row in matrix["rows"] if row["code"] == "06" and row["color_name"] == "مشکی"), None)
        if black is None:
            raise RuntimeError("V90 did not canonicalize pack6/06")
        values = {cell["name"]: cell["qty"] for cell in black["size_values"]}
        if values.get("M") != 2 or values.get("L") != 1 or black["total"] != 3:
            raise RuntimeError("V90 product/color/size aggregation failed")

        get_template("core/daily_report_v45.html")

        latest_day = SaleDay.objects.order_by("-date", "-id").first()
        if latest_day is not None:
            request = RequestFactory().get(f"/sales/{latest_day.id}/report/")
            request.user = SimpleNamespace(is_authenticated=True)
            static_override = {
                **settings.STORAGES,
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            }
            with override_settings(STORAGES=static_override):
                response = daily_report(request, latest_day.id)
            if response.status_code != 200:
                raise RuntimeError(f"V90 daily report render HTTP {response.status_code}")
            text = response.content.decode("utf-8", errors="replace")
            if "فروش تعدادی به تفکیک محصول، رنگ و سایز" not in text and SaleLine.objects.filter(day=latest_day, quantity__gt=0).exists():
                raise RuntimeError("V90 matrix block missing from populated daily report")

        if SaleDay.objects.count() != before_days or SaleLine.objects.count() != before_lines:
            raise RuntimeError("V90 read-only regression changed SaleDay/SaleLine row counts")

        self.stdout.write("PACK6 / 06 MATRIX CANONICALIZATION = OK")
        self.stdout.write("PRODUCT + COLOR + SIZE AGGREGATION = OK")
        self.stdout.write("REPLACEMENT COLOR MARKER = OK")
        self.stdout.write("DAILY REPORT TEMPLATE / RENDER = OK")
        self.stdout.write("NO SALE ROW WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: DAILY COLOR-SIZE MATRIX V90 CHECK PASSED"))
