"""Read-only V109 regression for base-color roll counts and stacked sheet summary."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings

from core import material_report_v92
from core.models import (
    BusinessPayment,
    ExcelManualRow,
    InventoryMovement,
    MaterialReportBlock,
    MaterialReportOutputApplied,
    RawMaterialStock,
    SaleLine,
    StockBalance,
)


def _digest(model):
    fields = [field.attname for field in model._meta.concrete_fields]
    h = sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _state():
    return {
        "raw": _digest(RawMaterialStock),
        "stock": _digest(StockBalance),
        "movement": _digest(InventoryMovement),
        "sales": _digest(SaleLine),
        "manual_rows": _digest(ExcelManualRow),
        "payments": _digest(BusinessPayment),
        "blocks": _digest(MaterialReportBlock),
        "output": _digest(MaterialReportOutputApplied),
    }


def _request(path):
    request = RequestFactory().get(path)
    request.user = SimpleNamespace(is_authenticated=True)
    return request


def _render():
    storage = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    with override_settings(STORAGES=storage):
        return material_report_v92.material_report(_request("/material-report/"))


class Command(BaseCommand):
    help = "Read-only: verify V109 per-color roll counts and stacked larger sheet summary badges."

    def handle(self, *args, **kwargs):
        before = _state()

        blocks = list(
            MaterialReportBlock.objects.select_related("brand")
            .prefetch_related("output_applications")
            .all()
        )
        progress = material_report_v92._summarize_open_base_colors(blocks)

        for row in progress:
            fabric_codes = set()
            uncoded_rolls = 0
            for block in blocks:
                if getattr(block.brand, "name", "") != "دارما":
                    continue
                values = ((block.input_data or {}).get(row["key"]) or {})
                cut = max(0, material_report_v92.v23.v20._int(values.get("cut")))
                applied = sum(
                    max(0, int(item.quantity or 0))
                    for item in block.output_applications.all()
                    if item.model_key == row["key"]
                )
                if cut <= applied:
                    continue
                code = str(values.get("fabric_code") or "").strip()
                weight = max(
                    material_report_v92._decimal(values.get("weight")),
                    material_report_v92.Decimal("0"),
                )
                if code:
                    fabric_codes.add(code)
                elif weight > 0:
                    uncoded_rolls += 1
            expected_rolls = len(fabric_codes) + uncoded_rolls
            if int(row["roll_count"]) != expected_rolls:
                raise RuntimeError(
                    f"Roll count mismatch for {row['key']}: "
                    f"{row['roll_count']} != {expected_rolls}"
                )

        response = _render()
        if response.status_code != 200:
            raise RuntimeError(f"Material report HTTP {response.status_code}")
        html = response.content.decode("utf-8", errors="replace")

        if html.count('data-base-color=') != 5:
            raise RuntimeError("Expected exactly five base-color cards")
        for row in progress:
            marker = (
                f'data-base-color="{row["key"]}" '
                f'data-roll-count="{int(row["roll_count"])}"'
            )
            if marker not in html:
                raise RuntimeError(f"Rendered roll-count marker missing: {marker}")

        for marker in (
            "تعداد طاقه تحویلی",
            "باید تحویل شود",
            "تحویل‌شده",
            "مانده",
        ):
            if marker not in html:
                raise RuntimeError(f"Color-card UI marker missing: {marker}")

        template = (
            Path(settings.BASE_DIR) / "templates/core/material_report_v36.html"
        ).read_text(encoding="utf-8")
        required_css = (
            ".summary-pills{display:grid;grid-template-columns:1fr;",
            "font-size:.84rem",
            "width:max-content",
        )
        for marker in required_css:
            if marker not in template:
                raise RuntimeError(f"Stacked summary CSS marker missing: {marker}")

        after = _state()
        if before != after:
            raise RuntimeError("V109 regression changed persistent business state")

        self.stdout.write("BASE-COLOR ROLL COUNTS = VERIFIED")
        self.stdout.write("ROLL COUNT SCOPE = SAME OPEN WORK AS DELIVERY/PENDING")
        self.stdout.write("FIVE COLOR CARDS = ROLL COUNT ABOVE 3 DELIVERY METRICS")
        self.stdout.write("MATERIAL SHEET SUMMARY BADGES = VERTICAL STACK")
        self.stdout.write("SUMMARY BADGE TEXT = LARGER WITHOUT WIDER/TALLER BAR RULE")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: MATERIAL ROLLS + STACKED SUMMARY V109 CHECK PASSED"
        ))
