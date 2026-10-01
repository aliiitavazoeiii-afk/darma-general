"""Read-only regression for V101 Finance & Tools submenu + Accounts page."""
from hashlib import sha256
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.test import RequestFactory, override_settings
from django.conf import settings

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
    help = "Read-only: verify Finance & Tools submenu has Accounts and Accounts page covers DB rows."

    def handle(self, *args, **kwargs):
        before = _state()

        req = RequestFactory().get("/finance/accounts/")
        req.user = SimpleNamespace(is_authenticated=True)
        static_override = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        with override_settings(STORAGES=static_override):
            response = V98PresentationMiddleware(finance_center_v97.accounts)(req)

        if response.status_code != 200:
            raise RuntimeError(f"Finance accounts render HTTP {response.status_code}")
        html = response.content.decode("utf-8", errors="replace")

        for marker in ("پرداخت‌ها", "حساب‌ها", "محاسبه‌گر"):
            if marker not in html:
                raise RuntimeError(f"Finance submenu marker missing: {marker}")
        if 'href="/finance/accounts/"' not in html:
            raise RuntimeError("Accounts submenu href missing")
        if html.count('data-finance-accounts-nav="v101"') != 1:
            raise RuntimeError("Accounts submenu entry is missing or duplicated")
        if response.get("X-Darma-Finance-Accounts-V101") != "present":
            raise RuntimeError("V101 middleware did not find Finance & Tools submenu")

        accounts = list(ExcelManualRow.objects.filter(active=True, section=ExcelManualRow.ACCOUNTS).order_by("sort_order", "id"))
        persons = list(ExcelManualRow.objects.filter(active=True, section=ExcelManualRow.PERSONS).order_by("sort_order", "id"))
        for row in accounts + persons:
            if f'finance-row-{row.id}' not in html:
                raise RuntimeError(f"Account/person row missing from HTML: id={row.id} title={row.title}")

        after = _state()
        if before != after:
            raise RuntimeError("V101 read-only regression changed business state")

        self.stdout.write("FINANCE TOOLS SUBMENU = PRESERVED")
        self.stdout.write("ACCOUNTS SUBMENU ENTRY = OK")
        self.stdout.write(f"ACCOUNT ROW COVERAGE = OK ({len(accounts)})")
        self.stdout.write(f"PERSON ROW COVERAGE = OK ({len(persons)})")
        self.stdout.write("PAYMENTS + ACCOUNTS + CALCULATOR = OK")
        self.stdout.write("NO BUSINESS STATE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: FINANCE ACCOUNTS SUBMENU V101 CHECK PASSED"))
