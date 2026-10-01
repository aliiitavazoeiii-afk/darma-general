"""Read-only regression for V97 material navigation and Finance & Tools center."""
from decimal import Decimal
from hashlib import sha256
from inspect import getsource
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template
from django.test import RequestFactory, override_settings
from django.urls import resolve

from core import business_tools_v91, calculator_v37, finance_center_v97, inventory_center_v97, report_v10
from core.models import (
    AppSetting,
    ExcelManualRow,
    ExcelManualSetting,
    InventoryMovement,
    MaterialReportConsumption,
    RawMaterialStock,
    SaleLine,
    SaleSnapshot,
    StockBalance,
)
from core.report_v5 import _raw_material_context


def _digest_model(model):
    fields = [field.attname for field in model._meta.concrete_fields]
    digest = sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        digest.update(repr(tuple(row)).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _state():
    return {
        "raw": _digest_model(RawMaterialStock),
        "material_consumption": _digest_model(MaterialReportConsumption),
        "stock": _digest_model(StockBalance),
        "movements": _digest_model(InventoryMovement),
        "sales": _digest_model(SaleLine),
        "snapshots": _digest_model(SaleSnapshot),
        "settings": _digest_model(AppSetting),
        "manual_settings": _digest_model(ExcelManualSetting),
        "manual_rows": _digest_model(ExcelManualRow),
    }


def _render(view, path):
    factory = RequestFactory()
    req = factory.get(path)
    req.user = SimpleNamespace(is_authenticated=True)
    response = view(req)
    if response.status_code != 200:
        raise RuntimeError(f"Render failed for {path}: HTTP {response.status_code}")
    return response.content.decode("utf-8", errors="replace")


class Command(BaseCommand):
    help = "Read-only: validate V97 material cards/tables and Finance & Tools routing."

    def handle(self, *args, **kwargs):
        before = _state()

        if resolve("/inventory/").func is not inventory_center_v97.inventory_home:
            raise RuntimeError("/inventory/ is not V97 inventory center")
        if resolve("/inventory/materials/").func is not inventory_center_v97.raw_materials:
            raise RuntimeError("/inventory/materials/ is not V97 material view")
        if resolve("/finance/").func is not finance_center_v97.finance_home:
            raise RuntimeError("/finance/ is not V97 Finance & Tools hub")
        if resolve("/finance/accounts/").func is not finance_center_v97.accounts:
            raise RuntimeError("Finance accounts route missing")
        if resolve("/payments/").func is not business_tools_v91.payments:
            raise RuntimeError("Existing payments/receipts route changed")
        if resolve("/calculator/").func is not calculator_v37.calculator:
            raise RuntimeError("Existing calculator route changed")

        for name in (
            "core/raw_material_inventory_v97.html",
            "core/finance_center_v97.html",
            "core/finance_accounts_v97.html",
            "core/report_excel_v97.html",
        ):
            get_template(name)

        static_override = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with override_settings(STORAGES=static_override):
            text = _render(inventory_center_v97.raw_materials, "/inventory/materials/")
            for marker in ("پارچه", "کش", "rm97-card-grid"):
                if marker not in text:
                    raise RuntimeError(f"Material root card missing: {marker}")

            text = _render(inventory_center_v97.raw_materials, "/inventory/materials/?kind=fabric")
            for marker in ("انبار", "نزد خیاط", "دپو", "rm97-location-grid"):
                if marker not in text:
                    raise RuntimeError(f"Fabric location card missing: {marker}")

            text = _render(inventory_center_v97.raw_materials, "/inventory/materials/?kind=fabric&location=tailor")
            if "انتقال پارچه از انبار به خیاط" not in text or "rm97-table" not in text:
                raise RuntimeError("Tailor fabric page lost transfer/table UI")
            if "ردیف داخلی" in text:
                raise RuntimeError("Legacy internal-row UI is still visible")

            text = _render(inventory_center_v97.raw_materials, "/inventory/materials/?kind=elastic&location=tailor")
            if "انتقال کش از انبار به خیاط" not in text or "rm97-table" not in text:
                raise RuntimeError("Tailor elastic page lost transfer/table UI")

            text = _render(finance_center_v97.finance_home, "/finance/")
            for marker in ("دریافتی‌ها و پرداختی‌ها", "حساب‌ها", "محاسبه‌گر"):
                if marker not in text:
                    raise RuntimeError(f"Finance card missing: {marker}")

            text = _render(finance_center_v97.accounts, "/finance/accounts/")
            for marker in ("ریز حساب‌ها", "حساب اشخاص", "طلب دیجی‌کالا", "بدهی تکوین", "Dia Gallery"):
                if marker not in text:
                    raise RuntimeError(f"Finance accounts marker missing: {marker}")

        raw = _raw_material_context()
        for key in ("fabric_warehouse", "fabric_tailor", "fabric_depot"):
            source_rows = raw[key]
            groups = inventory_center_v97._fabric_location_groups(source_rows)
            source_qty = sum((Decimal(row.quantity or 0) for row in source_rows), Decimal("0"))
            group_qty = sum((Decimal(row["quantity"] or 0) for row in groups), Decimal("0"))
            source_value = sum(int(row.total_value or 0) for row in source_rows)
            group_value = sum(int(row["total_value"] or 0) for row in groups)
            if source_qty != group_qty or source_value != group_value:
                raise RuntimeError(f"V97 fabric display aggregation changed quantity/value for {key}")

        report_source = getsource(report_v10.report)
        for marker in (
            'raw = _raw_material_context()',
            'inventory_total = finished_inventory_total + raw["materials_total"]',
            'current_capital_total = accounts_total + inventory_total + digikala_receivable - takvin_debt + assets_total',
            '"core/report_excel_v97.html"',
        ):
            if marker not in report_source:
                raise RuntimeError(f"Report formula/template marker missing: {marker}")

        report_template = (Path(settings.BASE_DIR) / "templates/core/report_excel_v97.html").read_text(encoding="utf-8")
        if "title==='حساب‌ها'" not in report_template:
            raise RuntimeError("Report account-management domain is not removed in V97")

        nav_js = (Path(settings.BASE_DIR) / "static/core/number_format.js").read_text(encoding="utf-8")
        if "financeLink.href = '/finance/'" not in nav_js or "Finance & Tools is one direct destination" not in nav_js:
            raise RuntimeError("Finance navigation is not a direct single entry")

        after = _state()
        if before != after:
            raise RuntimeError("V97 read-only regression changed business state")

        self.stdout.write("MATERIAL ROOT CARDS = OK")
        self.stdout.write("FABRIC LOCATION CARDS = OK")
        self.stdout.write("FABRIC TABLE ALIGNMENT STRUCTURE = OK")
        self.stdout.write("TAILOR FABRIC TRANSFER UI = OK")
        self.stdout.write("TAILOR ELASTIC TRANSFER UI = OK")
        self.stdout.write("LEGACY INTERNAL-ROW TABLE UI = REMOVED")
        self.stdout.write("FABRIC QUANTITY/VALUE AGGREGATION = NEUTRAL")
        self.stdout.write("FINANCE HUB 3 CARDS = OK")
        self.stdout.write("PAYMENTS/RECEIPTS FLOW = UNCHANGED")
        self.stdout.write("CALCULATOR ROUTE = UNCHANGED")
        self.stdout.write("REPORT ACCOUNT MANAGEMENT UI = MOVED")
        self.stdout.write("REPORT CAPITAL FORMULA = UNCHANGED")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: MATERIAL + FINANCE CENTER V97 CHECK PASSED"))
