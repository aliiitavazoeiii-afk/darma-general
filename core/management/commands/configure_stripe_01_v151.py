"""Safely register the new 1-piece Darma «راه راه 01» product.

Default invocation is READ-ONLY. Explicit --apply provisions catalog metadata
only (ProductCode/Color/ProductSize), never sales, stock or accounting.
Repeatable; refuses existing identity/price collisions when historical sales exist.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.brand_colors import norm
from core.daily_order_import_v8 import _compact_code
from core.models import Brand, Color, ProductCode, ProductSize, SaleLine, Size
from core.stripe_01_v151 import (
    BRAND_NAME, PACK_QTY, PRODUCT_CODE, PRODUCT_TITLE,
    SALE_PRICE, STOCK_COLOR_NAMES, UNIT_COST,
)
from core.title_product_resolver_v27 import resolve_product_from_title
from core.variant_sale_v12 import is_variable_color_product_code, resolve_variable_product_color

NEEDED_SIZES = ("M", "L", "XL", "XXL", "3XL", "4XL")


def _validate_identity(brand, existing):
    key = _compact_code(PRODUCT_TITLE)
    for other in ProductCode.objects.filter(brand=brand).exclude(code=PRODUCT_CODE):
        if _compact_code(other.code) == key or (
            other.title and _compact_code(other.title) == key
        ):
            raise CommandError(
                f"محصول دیگری با عنوان/کد «{PRODUCT_TITLE}» وجود دارد: "
                f"id={other.pk}, code={other.code!r}, active={other.active}. "
                "برای جلوگیری از برداشت موجودی اشتباه، ثبت خودکار متوقف شد."
            )
    if existing:
        if int(existing.pack_qty) != PACK_QTY:
            raise CommandError("کد موجود rahrah-01 پک یک‌عددی نیست؛ هیچ تغییری اعمال نشد.")
        if existing.title and _compact_code(existing.title) != key:
            raise CommandError(f"کد rahrah-01 قبلاً عنوان دیگری دارد: {existing.title!r}")
        if existing.composition.exists():
            raise CommandError("کد rahrah-01 دارای ترکیب رنگ ثابت است؛ نمی‌توان خودکار تغییرش داد.")
        if SaleLine.objects.filter(product_size__product=existing).exists():
            bad_sizes = list(
                ProductSize.objects.filter(product=existing)
                .exclude(default_sale_price=SALE_PRICE, unit_cost=UNIT_COST)
                .values_list("size__name", "default_sale_price", "unit_cost")
            )
            if bad_sizes:
                raise CommandError(
                    f"این کد قبلاً فروش دارد و قیمت/هزینه فعلی با مقدار تأییدشده سازگار نیست: {bad_sizes}"
                )


def _colors_state():
    found, missing = {}, []
    candidates = list(Color.objects.order_by("id"))
    for name in STOCK_COLOR_NAMES:
        matches = [c for c in candidates if norm(c.name) == norm(name)]
        active = [c for c in matches if c.active]
        if len(matches) > 1:
            raise CommandError(f"نام رنگ «{name}» در دیتابیس چند تطبیق دارد؛ نیاز به بررسی دستی دارد.")
        if matches and not active:
            raise CommandError(f"رنگ «{name}» غیرفعال است؛ از تعریف دوباره جلوگیری شد.")
        if active:
            found[name] = active[0]
        else:
            missing.append(name)
    return found, missing


def _preflight():
    try:
        brand = Brand.objects.get(name=BRAND_NAME, active=True)
    except Brand.DoesNotExist as exc:
        raise CommandError("برند فعال دارما یافت نشد؛ داده‌ای تغییر نمی‌کند.") from exc
    sizes = {s.name: s for s in Size.objects.filter(name__in=NEEDED_SIZES)}
    missing_sizes = set(NEEDED_SIZES) - set(sizes)
    if missing_sizes:
        raise CommandError(f"سایزبندی لازم در سیستم وجود ندارد: {sorted(missing_sizes)}")
    existing = ProductCode.objects.filter(brand=brand, code=PRODUCT_CODE).first()
    _validate_identity(brand, existing)
    found, missing = _colors_state()
    if not is_variable_color_product_code(PRODUCT_CODE):
        raise CommandError("کد محصول به‌عنوان محصول تک‌رنگ متغیر شناخته نمی‌شود؛ کد V151 نصب نشده.")
    return brand, sizes, existing, found, missing


class Command(BaseCommand):
    help = "V151: preview/create just «راه راه 01» one-piece SKU at 139,000 toman; no sale/stock changes."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Provision catalog after preflight.")
        parser.add_argument("--verify", action="store_true", help="Read-only verify registered SKU and title variants.")

    def handle(self, *args, **options):
        if options["apply"] and options["verify"]:
            raise CommandError("--apply و --verify را همزمان استفاده نکن.")
        if options["verify"]:
            self._verify()
            return
        brand, sizes, existing, found, missing = _preflight()
        if not options["apply"]:
            self.stdout.write(
                f"V151_PREFLIGHT=OK code={PRODUCT_CODE} "
                f"existing={bool(existing)} title={PRODUCT_TITLE} "
                f"price={SALE_PRICE:,} cost={UNIT_COST:,}"
            )
            self.stdout.write(
                "V151_COLORS_MISSING_WOULD_CREATE=" + (", ".join(missing) or "(none)")
            )
            self.stdout.write("V151_READ_ONLY=YES: call with --apply to register catalog metadata")
            return

        with transaction.atomic():
            # Revalidate with lock to avoid a concurrent partial definition.
            brand = Brand.objects.select_for_update().get(pk=brand.pk)
            existing = ProductCode.objects.select_for_update().filter(
                brand=brand, code=PRODUCT_CODE
            ).first()
            _validate_identity(brand, existing)
            found, missing = _colors_state()
            for name in missing:
                found[name] = Color.objects.create(name=name, active=True)
            product, created = ProductCode.objects.get_or_create(
                brand=brand, code=PRODUCT_CODE,
                defaults={
                    "title": PRODUCT_TITLE, "pack_qty": PACK_QTY,
                    "active": True,
                    "note": "[stripe01-v151] تکی، رنگ فروش از عنوان دیجی‌کالا",
                }
            )
            fields = []
            if product.title != PRODUCT_TITLE:
                product.title = PRODUCT_TITLE
                fields.append("title")
            if not product.active:
                product.active = True
                fields.append("active")
            if fields:
                product.save(update_fields=fields)
            for name in NEEDED_SIZES:
                ps, ps_created = ProductSize.objects.get_or_create(
                    product=product, size=sizes[name],
                    defaults={
                        "active": True,
                        "default_sale_price": SALE_PRICE,
                        "unit_cost": UNIT_COST,
                    },
                )
                if not ps_created:
                    changed = []
                    if not ps.active:
                        ps.active = True
                        changed.append("active")
                    if ps.default_sale_price != SALE_PRICE:
                        ps.default_sale_price = SALE_PRICE
                        changed.append("default_sale_price")
                    if ps.unit_cost != UNIT_COST:
                        ps.unit_cost = UNIT_COST
                        changed.append("unit_cost")
                    if changed:
                        ps.save(update_fields=changed)
            self.stdout.write(
                f"V151_CATALOG_REGISTERED=OK product_id={product.pk}, created={created}, "
                f"colors_created={missing}, price={SALE_PRICE}, cost={UNIT_COST}"
            )
        self._verify()

    def _verify(self):
        brand = Brand.objects.filter(name=BRAND_NAME, active=True).first()
        p = ProductCode.objects.filter(brand=brand, code=PRODUCT_CODE, active=True).first() if brand else None
        if not p or p.title != PRODUCT_TITLE or p.pack_qty != PACK_QTY or p.composition.exists():
            raise CommandError("V151_VERIFY_SKU=FAILED: canonical single-piece variable-color SKU not configured")
        for name in NEEDED_SIZES:
            ps = ProductSize.objects.filter(product=p, size__name=name, active=True).first()
            if not ps or ps.default_sale_price != SALE_PRICE or ps.unit_cost != UNIT_COST:
                raise CommandError(f"V151_VERIFY_SIZE=FAILED {name}")
        for title_color, stock_color in [
            ("مشکی", "راه راه مشکی"),
            ("قرمز", "راه راه قرمز"),
            ("طوسی", "راه راه طوسی"),
            ("سرمه ای", "راه راه"),
        ]:
            raw = f"شورت اسلیپ زنانه دارما مدل راه راه 01 | XL | {title_color} | گارانتی"
            resolved = resolve_product_from_title(raw)
            selected = resolve_variable_product_color(p.code, raw)
            matches = [
                c for c in Color.objects.filter(active=True) if norm(c.name) == norm(stock_color)
            ]
            if not resolved or resolved.pk != p.pk or selected != stock_color or len(matches) != 1:
                raise CommandError(f"V151_VERIFY_COLOR=FAILED title={title_color} stock={stock_color}")
        self.stdout.write(self.style.SUCCESS(
            "V151_VERIFY=OK: all 4 colors -> exact Darma stock and single-item 139,000 price; no sales written"
        ))
