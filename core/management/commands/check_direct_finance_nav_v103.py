"""Read-only V103 regression: Finance & Tools must be one direct hub link."""
from hashlib import sha256
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings
from django.urls import resolve

from core import finance_center_v97
from core.models import (
    BusinessPayment,
    ExcelManualRow,
    InventoryMovement,
    MaterialReportBlock,
    MaterialReportOutputApplied,
    RawMaterialStock,
    StockBalance,
)
from core.ui_polish_v98 import V98PresentationMiddleware


def _digest(model):
    fields = [field.attname for field in model._meta.concrete_fields]
    h = sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _state():
    return {
        "payments": _digest(BusinessPayment),
        "manual": _digest(ExcelManualRow),
        "raw": _digest(RawMaterialStock),
        "blocks": _digest(MaterialReportBlock),
        "output": _digest(MaterialReportOutputApplied),
        "stock": _digest(StockBalance),
        "moves": _digest(InventoryMovement),
    }


class Command(BaseCommand):
    help = "Read-only: verify V103 direct Finance & Tools navigation and 3-card finance hub."

    def handle(self, *args, **kwargs):
        before = _state()

        if resolve("/finance/").func is not finance_center_v97.finance_home:
            raise RuntimeError("/finance/ does not resolve to finance_home")
        if resolve("/finance/accounts/").func is not finance_center_v97.accounts:
            raise RuntimeError("/finance/accounts/ route changed")

        req = RequestFactory().get("/finance/")
        req.user = SimpleNamespace(is_authenticated=True)
        static_override = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with override_settings(STORAGES=static_override):
            response = V98PresentationMiddleware(finance_center_v97.finance_home)(req)

        if response.status_code != 200:
            raise RuntimeError(f"Finance hub render HTTP {response.status_code}")
        html = response.content.decode("utf-8", errors="replace")

        if html.count('data-finance-root-nav="v103"') != 1:
            raise RuntimeError("Finance direct sidebar link missing or duplicated")
        if 'erp-nav-group-title">مالی و ابزار' in html:
            raise RuntimeError("Legacy expandable Finance & Tools group still rendered")
        if 'href="/finance/"' not in html:
            raise RuntimeError("Direct /finance/ href missing")

        for marker in (
            "دریافتی‌ها و پرداختی‌ها",
            "حساب‌ها",
            "محاسبه‌گر",
            'href="/finance/accounts/"',
        ):
            if marker not in html:
                raise RuntimeError(f"Finance hub marker missing: {marker}")

        if response.get("X-Darma-Finance-Nav-V103") != "direct":
            raise RuntimeError("V103 presentation middleware marker missing")

        after = _state()
        if before != after:
            raise RuntimeError("V103 read-only regression changed business state")

        self.stdout.write("FINANCE & TOOLS SIDEBAR = DIRECT LINK")
        self.stdout.write("LEGACY FINANCE SUBMENU = ABSENT")
        self.stdout.write("FINANCE HUB 3 CARDS = OK")
        self.stdout.write("ACCOUNTS PAGE ROUTE = OK")
        self.stdout.write("V103 PRESENTATION MIDDLEWARE = NON-REWRITING")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: DIRECT FINANCE NAV V103 CHECK PASSED"))
