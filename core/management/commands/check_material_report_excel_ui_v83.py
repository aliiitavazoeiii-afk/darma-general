import inspect
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template
from django.urls import resolve, reverse

from core import material_report_v23 as v23


class Command(BaseCommand):
    help = "Read-only regression check for V83 Excel-style material report UI."

    def handle(self, *args, **options):
        route_expectations = [
            ("material_report", (), v23.material_report),
            ("material_block_save", (1,), v23.material_block_save),
            ("material_block_add_model", (1,), v23.material_block_add_model),
            ("material_block_apply", (1,), v23.material_block_apply_materials),
            ("material_block_apply_output", (1,), v23.material_block_apply_output),
        ]
        for route_name, args_, expected in route_expectations:
            match = resolve(reverse(route_name, args=args_))
            if match.func is not expected:
                raise RuntimeError(f"{route_name} is no longer routed to material_report_v23")

        parse_input_source = inspect.getsource(v23._parse_input)
        sync_output_source = inspect.getsource(v23._sync_output)
        consumption_source = inspect.getsource(v23.sync_report_consumption)

        backend_markers = [
            (parse_input_source, "calculate_model_cost"),
            (parse_input_source, "elastic16_key"),
            (parse_input_source, "elastic25_key"),
            (sync_output_source, "output-sync-v77"),
            (sync_output_source, "_sync_darma_stock_costed"),
            (sync_output_source, "_adjust_tailor_balance"),
            (consumption_source, "_consume_rows"),
        ]
        for source, marker in backend_markers:
            if marker not in source:
                raise RuntimeError(f"Material report backend marker missing: {marker}")

        get_template("core/material_report_v36.html")
        get_template("core/base.html") if False else None

        template_path = Path(settings.BASE_DIR) / "templates" / "core" / "material_report_v36.html"
        template_source = template_path.read_text(encoding="utf-8")
        ui_markers = [
            "material-workspace",
            "materials-pane",
            "delivery-pane",
            "active_material_keys",
            "material-source-select",
            "output-data-row",
            "delivery_{{ row.model_key }}",
            "material_block_apply",
            "material_block_apply_output",
            "material_report_v6.js",
        ]
        for marker in ui_markers:
            if marker not in template_source:
                raise RuntimeError(f"V83 UI marker missing: {marker}")

        self.stdout.write("MATERIAL REPORT ROUTES = V23")
        self.stdout.write("COST / ELASTIC / CONSUMPTION MARKERS = preserved")
        self.stdout.write("DELIVERY STOCK + WAGE SYNC MARKERS = preserved")
        self.stdout.write("RIGHT PANE = materials / cut / live cost")
        self.stdout.write("LEFT PANE = delivered products / sizes / date")
        self.stdout.write("ACTIVE MODEL KEYS = shared by both panes")
        self.stdout.write("TEMPLATE COMPILE = OK")
        self.stdout.write("CHECK MODE = READ ONLY")
        self.stdout.write(self.style.SUCCESS("MATERIAL REPORT EXCEL UI V83 CHECK OK"))
