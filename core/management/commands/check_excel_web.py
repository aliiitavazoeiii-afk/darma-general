from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template
from django.urls import reverse

from core.models import ExcelManualRow, ExcelManualSetting, MaterialReportBlock


class Command(BaseCommand):
    help = "Compile Excel-Web templates and verify main routes/models before deployment."

    def handle(self, *args, **options):
        templates = [
            "base.html",
            "core/dashboard_excel.html",
            "core/report_excel.html",
            "core/_manual_table.html",
            "core/material_report.html",
            "core/sale_calendar.html",
            "core/sale_size.html",
            "core/daily_report.html",
        ]
        errors = []
        for template_name in templates:
            try:
                get_template(template_name)
                self.stdout.write(f"template OK: {template_name}")
            except Exception as exc:
                errors.append(f"template {template_name}: {exc}")

        routes = [
            "dashboard",
            "sale_start",
            "report",
            "manual_report_action",
            "material_report",
            "inventory",
            "settings_products",
        ]
        for route in routes:
            try:
                if route == "manual_report_action":
                    reverse(route)
                else:
                    reverse(route)
                self.stdout.write(f"route OK: {route}")
            except Exception as exc:
                errors.append(f"route {route}: {exc}")

        try:
            ExcelManualSetting.objects.count()
            ExcelManualRow.objects.count()
            MaterialReportBlock.objects.count()
            self.stdout.write("Excel-Web models OK")
        except Exception as exc:
            errors.append(f"models/database: {exc}")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("Excel-Web preflight failed")

        self.stdout.write(self.style.SUCCESS("Excel-Web preflight passed"))
