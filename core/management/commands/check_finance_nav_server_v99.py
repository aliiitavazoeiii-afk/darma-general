"""Read-only V99 regression: validate final server-rendered Finance & Tools nav."""
from hashlib import sha256
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.test import RequestFactory

from core import finance_center_v97
from core.models import ExcelManualRow, ExcelManualSetting, RawMaterialStock, SaleLine, StockBalance
from core.ui_polish_v98 import V98PresentationMiddleware


def _digest(model):
    fields = [f.attname for f in model._meta.concrete_fields]
    h = sha256()
    for row in model.objects.order_by(model._meta.pk.attname).values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8")); h.update(b"\n")
    return h.hexdigest()


def _state():
    return {
        "raw": _digest(RawMaterialStock),
        "stock": _digest(StockBalance),
        "sales": _digest(SaleLine),
        "manual_settings": _digest(ExcelManualSetting),
        "manual_rows": _digest(ExcelManualRow),
    }


class Command(BaseCommand):
    help = "Read-only: verify final HTML has one direct Finance & Tools link and no submenu."

    def handle(self, *args, **kwargs):
        before = _state()

        req = RequestFactory().get("/finance/")
        req.user = SimpleNamespace(is_authenticated=True)
        middleware = V98PresentationMiddleware(finance_center_v97.finance_home)
        response = middleware(req)
        if response.status_code != 200:
            raise RuntimeError(f"Finance hub render HTTP {response.status_code}")

        html = response.content.decode("utf-8", errors="replace")
        if 'data-finance-root-nav="server-v99"' not in html:
            raise RuntimeError("V99 direct finance nav was not rendered server-side")
        if 'href="/finance/"' not in html:
            raise RuntimeError("V99 direct finance href missing")
        if 'erp-nav-group-title">مالی و ابزار' in html:
            raise RuntimeError("Legacy Finance & Tools submenu still exists in final HTML")
        if response.get("X-Darma-Finance-Nav-V99") != "server":
            raise RuntimeError("V99 middleware did not report successful server-side replacement")

        for marker in ("دریافتی‌ها و پرداختی‌ها", "حساب‌ها", "محاسبه‌گر"):
            if marker not in html:
                raise RuntimeError(f"Finance hub card missing after middleware: {marker}")

        if b'/static/core/number_format.js?v=99' not in response.content:
            raise RuntimeError("V99 cache-busted presentation helper missing")

        after = _state()
        if before != after:
            raise RuntimeError("V99 read-only regression changed business state")

        self.stdout.write("SERVER-SIDE FINANCE NAV REPLACEMENT = OK")
        self.stdout.write("LEGACY FINANCE SUBMENU ABSENT FROM FINAL HTML = OK")
        self.stdout.write("FINANCE HUB 3 CARDS = OK")
        self.stdout.write("V99 CACHE-BUSTED UI HELPER = OK")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: SERVER FINANCE NAV V99 CHECK PASSED"))
