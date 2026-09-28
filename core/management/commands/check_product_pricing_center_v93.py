"""Read-only regression for V93 unified product/pricing center."""
from datetime import date, timedelta
from hashlib import sha256
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import RequestFactory, override_settings
from django.template.loader import get_template
from django.urls import resolve

from core import product_center_v93
from core.models import (
    AppSetting,
    ProductCode,
    ProductComposition,
    ProductSize,
    SaleDay,
    SaleLine,
    TakvinCostRule,
)
from core.sale_price_v60 import sale_price_for, set_sale_price_rule


def _digest(qs, fields):
    h = sha256()
    for row in qs.order_by("id").values_list(*fields):
        h.update(repr(tuple(row)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _state():
    return {
        "app_settings": _digest(AppSetting.objects.all(), ("id", "key", "value", "label")),
        "takvin_cost_rules": _digest(
            TakvinCostRule.objects.all(),
            ("id", "size_id", "effective_from", "unit_cost"),
        ),
        "products": _digest(
            ProductCode.objects.all(),
            ("id", "brand_id", "code", "pack_qty", "active", "note"),
        ),
        "product_sizes": _digest(
            ProductSize.objects.all(),
            ("id", "product_id", "size_id", "default_sale_price", "unit_cost", "active"),
        ),
        "composition": _digest(
            ProductComposition.objects.all(),
            ("id", "product_id", "color_id", "qty"),
        ),
        "sale_days": SaleDay.objects.count(),
        "sale_lines": SaleLine.objects.count(),
    }


def _generated_ps_ids(rows):
    return {
        int(cell["ps_id"])
        for row in rows
        for cell in row["cells"]
        if cell.get("active") and cell.get("ps_id")
    }


def _first_active_ps(brand_name):
    return (
        ProductSize.objects.filter(
            product__brand__name=brand_name,
            product__active=True,
            active=True,
        )
        .select_related("product__brand", "product", "size")
        .order_by("id")
        .first()
    )


def _check_v60_sale_price_semantics():
    darma_ps = _first_active_ps("دارما")
    takvin_ps = _first_active_ps("تکوین")
    if not darma_ps or not takvin_ps:
        raise RuntimeError("V93 regression needs active Darma and Takvin ProductSize rows")

    with transaction.atomic():
        try:
            future = date.today() + timedelta(days=3650)
            darma_today = int(sale_price_for(darma_ps, date.today()))
            takvin_today = int(sale_price_for(takvin_ps, date.today()))
            darma_new = max(1, darma_today + 12_345)
            takvin_new = max(1, takvin_today + 23_456)

            set_sale_price_rule(darma_ps, future, darma_new)
            set_sale_price_rule(takvin_ps, future, takvin_new)

            if int(sale_price_for(darma_ps, date.today())) != darma_today:
                raise RuntimeError("V93/V60 future Darma price leaked into today")
            if int(sale_price_for(takvin_ps, date.today())) != takvin_today:
                raise RuntimeError("V93/V60 future Takvin price leaked into today")
            if int(sale_price_for(darma_ps, future)) != darma_new:
                raise RuntimeError("V93/V60 Darma effective-date price did not activate")
            if int(sale_price_for(takvin_ps, future)) != takvin_new:
                raise RuntimeError("V93/V60 Takvin effective-date price did not activate")

            sale_day_date = future + timedelta(days=31)
            while SaleDay.objects.filter(date=sale_day_date).exists():
                sale_day_date += timedelta(days=1)
            sale_day = SaleDay.objects.create(date=sale_day_date)
            frozen_price = 777_777
            line = SaleLine.objects.create(
                day=sale_day,
                product_size=darma_ps,
                quantity=1,
                sale_price=frozen_price,
            )
            set_sale_price_rule(darma_ps, sale_day_date, frozen_price + 111_111)
            line.refresh_from_db()
            if int(line.sale_price or 0) != frozen_price:
                raise RuntimeError("V93/V60 rule rewrote historical SaleLine.sale_price")
        finally:
            transaction.set_rollback(True)


class Command(BaseCommand):
    help = "Read-only: validate V93 product center routes, pricing semantics, coverage, templates, and no-write behavior."

    def handle(self, *args, **kwargs):
        before = _state()

        match = resolve("/settings/products/")
        if match.func is not product_center_v93.settings_products:
            raise RuntimeError("Active /settings/products/ route is not V93")
        old_rules = resolve("/settings/rules/")
        if old_rules.func is not product_center_v93.settings_rules_compat:
            raise RuntimeError("Old /settings/rules/ compatibility route is not V93")

        for template_name in (
            "core/settings_products_v93.html",
            "core/_product_center_rules_v93.html",
            "core/_product_center_pricing_v93.html",
            "core/_product_center_colors_v93.html",
        ):
            get_template(template_name)

        darma_rows = product_center_v93._product_pricing_rows(
            "دارما", product_center_v93.DARMA_PRICE_SIZES
        )
        takvin_rows = product_center_v93._product_pricing_rows(
            "تکوین", product_center_v93.TAKVIN_PRICE_SIZES
        )
        expected_darma = set(
            ProductSize.objects.filter(
                product__brand__name="دارما",
                product__active=True,
                active=True,
                size__name__in=product_center_v93.DARMA_PRICE_SIZES,
            ).values_list("id", flat=True)
        )
        expected_takvin = set(
            ProductSize.objects.filter(
                product__brand__name="تکوین",
                product__active=True,
                active=True,
                size__name__in=product_center_v93.TAKVIN_PRICE_SIZES,
            ).values_list("id", flat=True)
        )
        if _generated_ps_ids(darma_rows) != expected_darma:
            raise RuntimeError("V93 Darma per-code pricing coverage mismatch")
        if _generated_ps_ids(takvin_rows) != expected_takvin:
            raise RuntimeError("V93 Takvin per-code pricing coverage mismatch")

        _check_v60_sale_price_semantics()

        factory = RequestFactory()
        static_override = {
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            },
        }
        cases = [
            ({}, ("قوانین و قیمت‌های پایه", "قیمت‌گذاری‌ها", "رنگ‌بندی‌ها")),
            ({"section": "rules"}, ("بهای تمام‌شده هر شورت دارما", "قیمت تمام‌شده تکوین", "سایر تنظیمات محاسباتی")),
            ({"section": "pricing", "brand": "darma"}, ("ویرایش گروهی قیمت فروش دارما", "قیمت مستقل هر کد دارما")),
            ({"section": "pricing", "brand": "takvin"}, ("ویرایش گروهی قیمت فروش تکوین", "قیمت مستقل هر کد تکوین")),
            ({"section": "colors"}, ("ترکیب رنگ", "سایزهای فعال", "ویرایش")),
        ]
        with override_settings(STORAGES=static_override):
            for params, markers in cases:
                request = factory.get("/settings/products/", params)
                request.user = SimpleNamespace(is_authenticated=True)
                response = product_center_v93.settings_products(request)
                if response.status_code != 200:
                    raise RuntimeError(f"V93 render failed for {params}: HTTP {response.status_code}")
                text = response.content.decode("utf-8", errors="replace")
                for marker in markers:
                    if marker not in text:
                        raise RuntimeError(f"V93 UI marker missing for {params}: {marker}")

        compat_request = factory.get("/settings/rules/")
        compat_request.user = SimpleNamespace(is_authenticated=True)
        compat_response = product_center_v93.settings_rules_compat(compat_request)
        if compat_response.status_code not in {301, 302}:
            raise RuntimeError("V93 old rules compatibility URL did not redirect")
        if "section=rules" not in compat_response.url:
            raise RuntimeError("V93 old rules compatibility URL redirects to wrong target")

        after = _state()
        if after != before:
            raise RuntimeError("V93 read-only regression changed pricing/product/cost/sale state")

        self.stdout.write("PRODUCT CENTER V93 ROUTES = OK")
        self.stdout.write("DARMA PER-CODE PRICE COVERAGE = OK")
        self.stdout.write("TAKVIN PER-CODE PRICE COVERAGE = OK")
        self.stdout.write("V60 DATE-EFFECTIVE SALE PRICE SEMANTICS = OK")
        self.stdout.write("HISTORICAL SALELINE PRICE FREEZE = OK")
        self.stdout.write("RULES / PRICING / COLORS TEMPLATES = OK")
        self.stdout.write("OLD RULES URL COMPATIBILITY = OK")
        self.stdout.write("NO PRODUCT / PRICE / COST / SALE WRITE = OK")
        self.stdout.write(self.style.SUCCESS("SUCCESS: PRODUCT PRICING CENTER V93 CHECK PASSED"))
