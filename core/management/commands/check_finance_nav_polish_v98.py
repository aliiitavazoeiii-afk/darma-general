"""Read-only regression for V98/V99 finance navigation + presentation polish."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings
from django.urls import resolve

from core import business_tools_v91, calculator_v37, finance_center_v97
from core.models import (
    AppSetting,
    ExcelManualRow,
    ExcelManualSetting,
    InventoryMovement,
    RawMaterialStock,
    SaleLine,
    StockBalance,
)
from core.ui_polish_v98 import V98PresentationMiddleware


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
    help = "Read-only: validate final server-rendered finance nav and UI polish."

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
        for marker in (
            "normalizeFinanceNav",
            "financeLink.href = '/finance/'",
            "oldFinanceGroup.remove()",
            "text-decoration:none!important",
            ".rm97-kpi strong",
            "font-size:1.35rem!important",
        ):
            if marker not in js:
                raise RuntimeError(f"Presentation marker missing: {marker}")

        middleware_path = "core.ui_polish_v98.V98PresentationMiddleware"
        if middleware_path not in settings.MIDDLEWARE:
            raise RuntimeError("Presentation middleware is not enabled")

        request = RequestFactory().get("/finance/")
        request.user = SimpleNamespace(is_authenticated=True)
        static_override = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with override_settings(STORAGES=static_override):
            response = V98PresentationMiddleware(finance_center_v97.finance_home)(request)

        if response.status_code != 200:
            raise RuntimeError(f"Finance hub render HTTP {response.status_code}")
        rendered = response.content.decode("utf-8", errors="replace")

        if response.get("X-Darma-Finance-Nav-V99") != "server":
            raise RuntimeError("Server-side finance submenu replacement did not run")
        if 'data-finance-root-nav="server-v99"' not in rendered:
            raise RuntimeError("Direct server-rendered finance link missing")
        if 'erp-nav-group-title">مالی و ابزار' in rendered:
            raise RuntimeError("Legacy Finance & Tools submenu still exists in final HTML")
        if 'href="/finance/"' not in rendered:
            raise RuntimeError("Direct /finance/ href missing from final HTML")
        for marker in ("دریافتی‌ها و پرداختی‌ها", "حساب‌ها", "محاسبه‌گر"):
            if marker not in rendered:
                raise RuntimeError(f"Finance hub card missing: {marker}")
        if '/static/core/number_format.js?v=99' not in rendered:
            raise RuntimeError("V99 cache-busted UI helper missing")

        after = _state()
        if before != after:
            raise RuntimeError("Read-only finance-nav regression changed business state")

        self.stdout.write("SERVER-SIDE FINANCE NAV REPLACEMENT = OK")
        self.stdout.write("LEGACY FINANCE SUBMENU ABSENT = OK")
        self.stdout.write("FINANCE HUB 3 CARDS = OK")
        self.stdout.write("GLOBAL LINK UNDERLINES REMOVED = OK")
        self.stdout.write("RAW MATERIAL KPI NUMBER SIZE = OK")
        self.stdout.write("V99 CACHE-BUSTED UI HELPER = OK")
        self.stdout.write("PAYMENTS / CALCULATOR ROUTES = UNCHANGED")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: FINANCE NAV + UI POLISH V98/V99 CHECK PASSED"))
