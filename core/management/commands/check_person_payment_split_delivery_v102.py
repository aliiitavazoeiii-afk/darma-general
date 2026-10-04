"""Read-only V102 regression for person payments + 3-part deliveries + five-color open-work KPIs."""
from hashlib import sha256
from inspect import getsource
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.http import QueryDict
from django.template.loader import get_template

from core import business_tools_v62 as payments_v62
from core import business_tools_v91 as payments_v91
from core import finance_center_v97
from core import material_report_v23 as material_v23
from core import material_report_v92 as material_v92
from core.models import (
    AccountEntry,
    BusinessPayment,
    ExcelManualRow,
    ExcelManualSetting,
    InventoryMovement,
    MaterialReportBlock,
    MaterialReportOutputApplied,
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
        "manual_rows": _digest(ExcelManualRow),
        "manual_settings": _digest(ExcelManualSetting),
        "payments": _digest(BusinessPayment),
        "blocks": _digest(MaterialReportBlock),
        "output_applied": _digest(MaterialReportOutputApplied),
        "stock": _digest(StockBalance),
        "movements": _digest(InventoryMovement),
        "account_entries": _digest(AccountEntry),
    }


class Command(BaseCommand):
    help = "Read-only: verify V102 person-payment linkage, split deliveries and base-color open work."

    def handle(self, *args, **kwargs):
        before = _state()

        # 1) Every active PERSONS row is selectable as a stable id-based payment target.
        persons = list(
            ExcelManualRow.objects.filter(section=ExcelManualRow.PERSONS, active=True)
            .order_by("sort_order", "id")
        )
        payees = dict(payments_v62.payment_payee_choices())
        for row in persons:
            key = payments_v62._person_payee_key(row.id)
            if key not in payees:
                raise RuntimeError(f"Person account missing from payment choices: {row.id} / {row.title}")
            if row.title not in payees[key]:
                raise RuntimeError(f"Person payment label mismatch: {row.id} / {row.title}")
            if len(key) > BusinessPayment._meta.get_field("payee").max_length:
                raise RuntimeError(f"Person payment key exceeds BusinessPayment.payee max_length: {key}")
            resolved = payments_v62._person_row_for_payee(key, active_only=True)
            if not resolved or resolved.id != row.id:
                raise RuntimeError(f"Person payment key does not resolve back to row: {key}")

        if "payment_payee_choices()" not in getsource(payments_v91.payments):
            raise RuntimeError("V91 payments screen is not using dynamic person payment choices")

        apply_source = getsource(payments_v62._apply_full)
        reverse_source = getsource(payments_v62._reverse_full)
        if "_adjust_person_payment(payment.payee, -int(payment.amount or 0))" not in apply_source:
            raise RuntimeError("Person payment does not subtract from PERSONS account")
        if "_adjust_person_payment(payment.payee, int(payment.amount or 0))" not in reverse_source:
            raise RuntimeError("Person payment reverse does not restore PERSONS account")
        if 'BusinessPayment.objects.filter(payee=f"person:{row.id}").exists()' not in getsource(finance_center_v97.accounts_action):
            raise RuntimeError("Person account deletion guard is missing")

        # 2) Three internal delivery boxes sum into the single canonical target used by all old sync logic.
        darma = material_v23.Brand.objects.filter(name="دارما").first()
        if darma is None:
            raise RuntimeError("Darma brand not found")

        post = QueryDict("", mutable=True)
        post.update({
            "out_white_xl_1": "50",
            "out_white_xl_2": "70",
            "out_white_xl_3": "50",
        })
        split = material_v23._parse_output(SimpleNamespace(POST=post), darma, ["white"])
        if material_v23.v20._int(split["white"]["xl"]) != 170:
            raise RuntimeError("50 + 70 + 50 did not produce canonical target 170")
        if split["white"]["_delivery_parts"]["xl"] != ["50", "70", "50"]:
            raise RuntimeError("Three delivery installments were not preserved separately")
        if material_v23._target_qty(SimpleNamespace(output_data=split), "white", "xl") != 170:
            raise RuntimeError("Existing output sync target is not reading the three-part total")

        legacy_post = QueryDict("", mutable=True)
        legacy_post.update({"out_white_xl": "170"})
        legacy = material_v23._parse_output(SimpleNamespace(POST=legacy_post), darma, ["white"])
        if material_v23.v20._int(legacy["white"]["xl"]) != 170:
            raise RuntimeError("Legacy one-box delivery value no longer preserves total")
        if material_v23._delivery_parts_for_values(legacy["white"], "xl")[0] != "170":
            raise RuntimeError("Legacy delivery did not migrate presentation to first mini-box")

        get_template("core/material_report_v36.html")
        get_template("core/material_report_v92.html")
        material_template = (Path(settings.BASE_DIR) / "templates/core/material_report_v36.html").read_text(encoding="utf-8")
        if "delivery-split" not in material_template or "cell.parts" not in material_template:
            raise RuntimeError("Three-box delivery UI is missing from material report template")

        # 3) Five base-color cards represent only OPEN Darma work: cut > actually applied delivery.
        blocks = list(
            MaterialReportBlock.objects.select_related("brand")
            .prefetch_related("output_applications")
            .all()
        )
        progress = material_v92._summarize_open_base_colors(blocks)
        expected_keys = [key for key, _label in material_v23.BASE_MODELS]
        if [row["key"] for row in progress] != expected_keys:
            raise RuntimeError("Five base-color progress rows/order changed")

        for row in progress:
            expected = delivered = pending = open_blocks = 0
            for block in blocks:
                if block.brand.name != "دارما":
                    continue
                cut = max(
                    0,
                    material_v23.v20._int(
                        ((block.input_data or {}).get(row["key"]) or {}).get("cut")
                    ),
                )
                applied = sum(
                    max(0, int(item.quantity or 0))
                    for item in block.output_applications.all()
                    if item.model_key == row["key"]
                )
                if cut <= applied:
                    continue
                expected += cut
                delivered += applied
                pending += cut - applied
                open_blocks += 1
            actual = (row["expected"], row["delivered"], row["pending"], row["open_blocks"])
            manual = (expected, delivered, pending, open_blocks)
            if actual != manual:
                raise RuntimeError(f"Open-work KPI mismatch for {row['key']}: {actual} != {manual}")

        month_template = (Path(settings.BASE_DIR) / "templates/core/material_report_v92.html").read_text(encoding="utf-8")
        for marker in (
            "materialV102ColorProgress",
            "طبق برش باید تحویل شود",
            "تا الان تحویل شده",
            "مانده تحویل",
        ):
            if marker not in month_template:
                raise RuntimeError(f"Five-color KPI UI marker missing: {marker}")

        after = _state()
        if before != after:
            raise RuntimeError("V102 read-only regression changed business state")

        self.stdout.write(f"PERSON PAYMENT CHOICES = OK ({len(persons)})")
        self.stdout.write("PERSON PAYMENT APPLY/REVERSE = LINKED")
        self.stdout.write("PERSON ACCOUNT DELETE GUARD = ON")
        self.stdout.write("THREE DELIVERY BOXES = 50 + 70 + 50 -> 170")
        self.stdout.write("LEGACY DELIVERY TOTAL = PRESERVED")
        self.stdout.write("OUTPUT SYNC TARGET = SAME CANONICAL TOTAL")
        self.stdout.write("FIVE BASE COLORS = OPEN CUT VS APPLIED DELIVERY")
        self.stdout.write("COMPLETED OLD SHEETS = EXCLUDED FROM OPEN-WORK KPI")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS(
            "SUCCESS: PERSON PAYMENTS + SPLIT DELIVERY + COLOR PROGRESS V102 CHECK PASSED"
        ))
