from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template
from django.urls import reverse

from core.models import ExcelManualRow, ExcelManualSetting, InventoryModelCost, MaterialReportBlock, TakvinPurchase


class Command(BaseCommand):
    help = "Compile Excel-Web templates and verify main routes/models before deployment."

    def handle(self, *args, **options):
        templates = [
            "base.html",
            "core/_mobile_shell.html",
            "core/dashboard_excel.html",
            "core/report_excel.html",
            "core/_manual_table.html",
            "core/material_report.html",
            "core/takvin_excel.html",
            "core/sale_calendar.html",
            "core/sale_brand_final.html",
            "core/sale_size.html",
            "core/_sale_saved_final.html",
            "core/daily_report.html",
            "core/inventory_final.html",
            "core/inventory_operations.html",
            "core/settings_home.html",
            "core/settings_catalog.html",
            "core/settings_products.html",
            "core/settings_product_form.html",
            "core/settings_stock.html",
            "core/settings_finance.html",
            "core/settings_rules.html",
        ]
        errors = []
        for template_name in templates:
            try:
                get_template(template_name)
                self.stdout.write(f"template OK: {template_name}")
            except Exception as exc:
                errors.append(f"template {template_name}: {exc}")

        simple_routes = [
            "dashboard",
            "sale_start",
            "sale_line_save",
            "report",
            "manual_report_action",
            "material_report",
            "takvin",
            "inventory",
            "inventory_add_color_model",
            "inventory_operations",
            "settings_home",
            "settings_catalog",
            "settings_products",
            "settings_product_new",
            "settings_stock",
            "settings_finance",
            "settings_rules",
        ]
        for route in simple_routes:
            try:
                reverse(route)
                self.stdout.write(f"route OK: {route}")
            except Exception as exc:
                errors.append(f"route {route}: {exc}")

        parameter_routes = [
            ("sale_brand", [1]),
            ("daily_report", [1]),
            ("sale_size", [1, 1, 1]),
            ("shortage_resolve", [1]),
            ("material_block_save", [1]),
            ("material_block_delete", [1]),
            ("settings_product_edit", [1]),
        ]
        for route, args in parameter_routes:
            try:
                reverse(route, args=args)
                self.stdout.write(f"route OK: {route}")
            except Exception as exc:
                errors.append(f"route {route}: {exc}")

        for static_name in ["core/jalali_picker.js", "core/ui-polish.css"]:
            if not finders.find(static_name):
                errors.append(f"static file {static_name} not found")
            else:
                self.stdout.write(f"static OK: {static_name}")

        try:
            ExcelManualSetting.objects.count()
            ExcelManualRow.objects.count()
            MaterialReportBlock.objects.count()
            TakvinPurchase.objects.filter(note__startswith="[excel-web]").count()
            InventoryModelCost.objects.count()
            self.stdout.write("Excel-Web models OK")
        except Exception as exc:
            errors.append(f"models/database: {exc}")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("Excel-Web preflight failed")

        self.stdout.write(self.style.SUCCESS("Excel-Web preflight passed"))
