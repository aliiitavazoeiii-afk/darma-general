"""Read-only regression for V98 finance navigation + presentation polish."""
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import resolve

from core import business_tools_v91, calculator_v37, finance_center_v97
from core.models import AppSetting, ExcelManualRow, ExcelManualSetting, InventoryMovement, RawMaterialStock, SaleLine, StockBalance


def _digest(model):
    fields = [field.attname for field in model._meta.concrete_fields]
    h = sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8")); h.update(b"\n")
    return h.hexdigest()


def _state():
    return {
        "raw": _digest(RawMaterialStock),
        "stock": _digest(StockBalance),
        "movement": _digest(InventoryMovement),
        "sales": _digest(SaleLine),
        "settings": _digest(AppSetting),
        "manual_settings": _digest(ExcelManualSetting),
        "manual_rows": _digest(ExcelManualRow),
    }


class Command(BaseCommand):
    help = "Read-only: validate V98 direct finance nav, no underline, and material KPI polish."

    def handle(self, *args, **kwargs):
        before = _state()

        if resolve("/finance/").func is not finance_center_v97.finance_home:
            raise RuntimeError("Finance hub route changed")
        if resolve("/finance/accounts/").func is not finance_center_v97.accounts:
            raise RuntimeError("Finance accounts route changed")
        if resolve("/payments/").func is not business_tools_v91.payments:
            raise RuntimeError("Payments/receipts route changed")
        if resolve("/calculator/").func is not calculator_v37.calculator:
            raise RuntimeError("Calculator route changed")

        js = (Path(settings.BASE_DIR) / "static/core/number_format.js").read_text(encoding="utf-8")
        markers = (
            "normalizeFinanceNav",
            "financeLink.href = '/finance/'",
            "oldFinanceGroup.remove()",
            "text-decoration:none!important",
            ".rm97-kpi strong",
            "font-size:1.35rem!important",
        )
        for marker in markers:
            if marker not in js:
                raise RuntimeError(f"V98 presentation marker missing: {marker}")

        after = _state()
        if before != after:
            raise RuntimeError("V98 read-only regression changed business state")

        self.stdout.write("FINANCE NAV SINGLE DIRECT LINK = OK")
        self.stdout.write("FINANCE HUB / ACCOUNTS ROUTES = OK")
        self.stdout.write("GLOBAL LINK UNDERLINES REMOVED = OK")
        self.stdout.write("RAW MATERIAL KPI NUMBER SIZE = OK")
        self.stdout.write("PAYMENTS / CALCULATOR ROUTES = UNCHANGED")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: FINANCE NAV + UI POLISH V98 CHECK PASSED"))
