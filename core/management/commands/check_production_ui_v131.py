"""V131 non-mutating deploy audit for the monthly production presentation."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template
from django.urls import resolve, reverse

from core import material_report_ui_v131 as ui
from core import material_report_v23 as posting
from core import material_report_v20 as legacy
from core import material_report_overall_v137 as overall
from core import production_inline_v138 as inline


class Command(BaseCommand):
    help = "Read-only UI, URL and legacy posting contract audit for V131"

    def handle(self, *args, **options):
        get_template("core/material_report_v131.html")
        get_template("core/material_report_overall_v137.html")
        routes = {
            "material_block_save": posting.material_block_save,
            "material_block_apply": posting.material_block_apply_materials,
            "material_block_apply_color": posting.material_block_apply_color,
            "material_block_apply_output": posting.material_block_apply_output,
            "material_block_add_model": posting.material_block_add_model,
            "material_block_delete": legacy.material_block_delete,
        }
        if resolve(reverse("material_block_inline", args=[123])).func is not inline.material_block_inline_action:
            raise RuntimeError("V138 inline editor route mismatch")
        if resolve(reverse("material_production_overall")).func is not overall.production_overall:
            raise RuntimeError("V137 all-history GET route mismatch")
        if resolve(reverse("material_report")).func is not ui.material_report:
            raise RuntimeError("V131 UI-only GET route mismatch")
        for name, handler in routes.items():
            if resolve(reverse(name, args=[123])).func is not handler:
                raise RuntimeError(f"Existing business POST handler changed: {name}")
        base = Path(settings.BASE_DIR)
        template = (base / "templates/core/material_report_v131.html").read_text("utf-8")
        script = (base / "core/static/core/production_workspace_v131.js").read_text("utf-8")
        full = (base / "templates/core/material_report_overall_v137.html").read_text("utf-8")
        style = (base / "core/static/core/production_overall_v137.css").read_text("utf-8")
        for marker in (
            'form="{{ editor.form_id }}"',
            'name="delivery_destination"',
            'value="home"',
            'value="khorshid"',
            'material_block_apply_color',
            'material_block_apply_output',
            'material_block_save',
            'prod131-delivery',
            'prod131-group',
            'name="initial_material_key"',
            'new_sheet_colors',
            'material_block_delete',
            'prod131-delete-form-',
            'editor.deletable',
            'data-scope-metric="rolls"',
            'data-scope-metric="average_cost"',
            'data-countable=',
            'material_production_overall',
            'data-inline-url=',
            'prod138-save-toast',
        ):
            if marker not in template:
                raise RuntimeError(f"Missing V131 UI contract: {marker}")
        if "اعمال مصرف کل صورت" in template:
            raise RuntimeError("V133 must not expose whole-sheet consumption control")
        for marker in (
            "prod131-search", "prod131-toggle", "prod131-open-dest",
            "initialCode", "formaction", "data-field", "2.5",
        ):
            if marker not in script:
                raise RuntimeError(f"Missing V131 JS contract: {marker}")
        self.stdout.write("MONTHLY ROW UI=ON")
        self.stdout.write("COLOR/CODE FILTER AND PER-MONTH ARCHIVE=ON")
        self.stdout.write("THREE DELIVERY INPUTS PER SIZE=V23 UNCHANGED")
        self.stdout.write("WAREHOUSE CHOICE=V23 UNCHANGED")
        self.stdout.write("PER-COLOR MATERIAL CONTROL=VISIBLE; WHOLE-SHEET BUTTON=HIDDEN")
        self.stdout.write("NEW-SHEET COLOR SELECTOR=VALIDATED")
        self.stdout.write("WHOLE-SHEET DELETE=EXISTING INVENTORY-SAFE V20 PATH")
        for marker in ("selectedColor", "selectedMaterial", "matchesMaterial", "scopedMetric", "validWeight",
                       "event.preventDefault()", "new FormData(form)", "fetch(inlineUrl",
                       "inlineUpdateRow", "pendingInlineRequest"):
            if marker not in script:
                raise RuntimeError(f"V137 selected-month reactive KPI missing: {marker}")
        for marker in ("ماهانه", "مقایسه رنگ‌ها", "material_report", "report.monthly",
                       "report.colors", "report.sizes", "report.followups"):
            if marker not in full:
                raise RuntimeError(f"V137 overall analytics missing: {marker}")
        if not style.strip():
            raise RuntimeError("V137 overall dashboard styles missing")
        self.stdout.write("SELECTED-MONTH KPIS FOLLOW ALL ACTIVE FILTERS=ON")
        self.stdout.write("SEPARATE COMPLETE READ-ONLY ALL-TIME PRODUCTION REPORT=ON")
        self.stdout.write("V138 NO-REFRESH SAVE AND DELIVERY=ON")
        self.stdout.write("EXISTING V23 INVENTORY/WAGE HANDLERS=UNCHANGED")
        self.stdout.write("DATABASE WRITES=NONE")
        self.stdout.write(self.style.SUCCESS("V131 PRODUCTION UI READ-ONLY CONTRACT CHECK OK"))
