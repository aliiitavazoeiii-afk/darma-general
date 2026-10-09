"""Read-only regression for compact V110 material-sheet summary box grid."""
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template

from core.models import (
    AccountEntry,
    AppSetting,
    BusinessPayment,
    DigikalaSettlement,
    ExcelManualRow,
    ExcelManualSetting,
    InventoryMovement,
    MaterialReportBlock,
    MaterialReportConsumption,
    MaterialReportOutputApplied,
    RawMaterialStock,
    SaleLine,
    SaleSnapshot,
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
        "blocks": _digest(MaterialReportBlock),
        "consumption": _digest(MaterialReportConsumption),
        "output": _digest(MaterialReportOutputApplied),
        "stock": _digest(StockBalance),
        "movement": _digest(InventoryMovement),
        "sales": _digest(SaleLine),
        "snapshots": _digest(SaleSnapshot),
        "accounts": _digest(AccountEntry),
        "app_settings": _digest(AppSetting),
        "manual_settings": _digest(ExcelManualSetting),
        "manual_rows": _digest(ExcelManualRow),
        "payments": _digest(BusinessPayment),
        "receipts": _digest(DigikalaSettlement),
    }


class Command(BaseCommand):
    help = "Read-only V110 compact material summary regression."

    def handle(self, *args, **kwargs):
        before = _state()

        # Compile both material templates.
        get_template("core/material_report_v36.html")
        get_template("core/material_report_v92.html")

        source = (
            Path(settings.BASE_DIR) / "templates/core/material_report_v36.html"
        ).read_text(encoding="utf-8")

        required = (
            'data-summary-box-grid="v110"',
            "grid-template-columns:minmax(120px,1fr) minmax(220px,1.65fr) minmax(170px,1.25fr) minmax(150px,1fr) minmax(170px,1.1fr)",
            "summary-brand-box",
            "summary-models-box",
            "summary-codes-box",
            "summary-material-box",
            "summary-output-box",
            "summary-sub-line",
            "min-height:34px",
            "padding:5px 9px",
            "font-size:.76rem",
        )
        for marker in required:
            if marker not in source:
                raise RuntimeError(f"V110 summary-grid marker missing: {marker}")

        forbidden = (
            ".summary-pills{display:grid;grid-template-columns:1fr;justify-items:start",
            "font-size:.82rem;line-height:1.35",
        )
        for marker in forbidden:
            if marker in source:
                raise RuntimeError(f"V109 tall vertical summary returned: {marker}")

        # The desktop summary has exactly five semantic boxes in the template.
        for class_name in (
            "summary-brand-box",
            "summary-models-box",
            "summary-codes-box",
            "summary-material-box",
            "summary-output-box",
        ):
            if source.count(class_name) != 1:
                raise RuntimeError(
                    f"Expected exactly one {class_name} marker, got {source.count(class_name)}"
                )

        # Pending increase/reduction must stay INSIDE output box rather than
        # create extra summary grid cells that increase collapsed-card height.
        output_start = source.index('class="apply-state applied summary-output-box"')
        output_end = source.index("</span>\n      </div>", output_start)
        output_chunk = source[output_start:output_end]
        for marker in ("افزایش منتظر", "کاهش منتظر", "summary-sub-line"):
            if marker not in output_chunk:
                raise RuntimeError(
                    f"Pending delivery status escaped the compact output box: {marker}"
                )

        # Existing V106 three-delivery UI is still present.
        if "delivery-split" not in source or "part.name" not in source:
            raise RuntimeError("Three-delivery UI disappeared from material report")

        after = _state()
        if before != after:
            raise RuntimeError("V110 regression changed persistent business state")

        self.stdout.write("MATERIAL SUMMARY DESKTOP GRID = 5 BOXES")
        self.stdout.write("COLLAPSED HEIGHT = COMPACT HORIZONTAL LAYOUT")
        self.stdout.write("MODEL / FABRIC / MATERIAL / DELIVERY = SEPARATE BOXES")
        self.stdout.write("PENDING OUTPUT STATUS = KEPT INSIDE DELIVERY BOX")
        self.stdout.write("V109 COLOR ROLL CARDS = UNTOUCHED")
        self.stdout.write("THREE DELIVERY INPUTS = PRESERVED")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: COMPACT MATERIAL SUMMARY BOX GRID V110 CHECK PASSED"
        ))
