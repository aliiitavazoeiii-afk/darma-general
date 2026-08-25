from collections import defaultdict

from django.db import transaction
from django.db.models import Sum

from .brand_colors import norm
from .darma_pricing import SIZE_NAMES, get_group_prices
from .models import (
    AppSetting, Brand, Color, InventoryMovement, ProductCode, ProductSize,
    SaleAllocation, SaleLine, SaleShortage, Size, StockBalance, StockLocation,
)

VARIANT_PRODUCT_CODE = "s3"

# Exact Digikala seller-code semantics from the user's daily-order workflow.
# These are intentionally case-sensitive: s3=black, S3=pink.
SELLER_COLOR_CODES = {
    "s2": "کرم",
    "s3": "مشکی",
    "S3": "صورتی",
    "s5": "سرمه ای",
}

TITLE_COLORS = ["مشکی", "کرم", "صورتی", "سرمه ای"]


def _color_for_name(name):
    wanted = norm(name)
    for color in Color.objects.filter(active=True).order_by("id"):
        if norm(color.name) == wanted:
            return color
    raise ValueError(f"رنگ دارما «{name}» در موجودی تعریف نشده است.")


def resolve_variant_color(title, seller_code=""):
    text = str(title or "")
    # Title is authoritative because model s3 is a customer-selectable color item.
    # Match pipe-delimited color tokens to avoid accidental words elsewhere in title.
    parts = [part.strip() for part in text.split("|")]
    for part in parts:
        for color_name in TITLE_COLORS:
            if norm(part) == norm(color_name):
                return color_name
    # Fallback to seller code only when the title export omitted color.
    raw_code = str(seller_code or "").strip()
    return SELLER_COLOR_CODES.get(raw_code)


@transaction.atomic
def ensure_variant_product():
    brand = Brand.objects.get(name="دارما")
    product, _ = ProductCode.objects.get_or_create(
        brand=brand,
        code=VARIANT_PRODUCT_CODE,
        defaults={"pack_qty": 1, "active": True, "note": "[variant-color]"},
    )
    product.pack_qty = 1
    product.active = True
    product.note = "[variant-color] رنگ هر فروش از عنوان فایل دیجی‌کالا"
    product.save(update_fields=["pack_qty", "active", "note"])
    # Fixed composition must stay empty for this product.
    product.composition.all().delete()

    prices = get_group_prices(1)
    sizes = {s.name: s for s in Size.objects.filter(name__in=SIZE_NAMES)}
    for size_name in SIZE_NAMES:
        size = sizes.get(size_name)
        if not size:
            continue
        ProductSize.objects.update_or_create(
            product=product,
            size=size,
            defaults={
                "default_sale_price": int(prices.get(size_name, 0) or 0),
                "unit_cost": 61000,
                "active": True,
            },
        )
    return product


def _stock_total_by_brand():
    return {
        row["brand_id"]: int(row["qty"] or 0)
        for row in StockBalance.objects.values("brand_id").annotate(qty=Sum("qty"))
    }


def sold_units_by_brand(lines):
    result = defaultdict(int)
    for line in lines:
        result[line.product_size.product.brand_id] += int(line.quantity or 0) * int(line.product_size.product.pack_qty or 0)
    return dict(result)


def assert_stock_invariant(before_stock, after_stock, old_sold, new_sold):
    brand_ids = set(before_stock) | set(after_stock) | set(old_sold) | set(new_sold)
    errors = []
    for brand_id in brand_ids:
        actual_decrease = int(before_stock.get(brand_id, 0)) - int(after_stock.get(brand_id, 0))
        expected_decrease = int(new_sold.get(brand_id, 0)) - int(old_sold.get(brand_id, 0))
        if actual_decrease != expected_decrease:
            brand_name = Brand.objects.filter(id=brand_id).values_list("name", flat=True).first() or str(brand_id)
            errors.append(
                f"{brand_name}: تغییر واقعی موجودی {actual_decrease:+d} ولی تغییر مورد انتظار فروش {expected_decrease:+d}"
            )
    if errors:
        raise ValueError("کنترل موجودی فروش ناموفق بود؛ کل Import برگشت داده شد. " + " | ".join(errors))


@transaction.atomic
def sync_variant_inventory(line, color_quantities):
    line = (
        SaleLine.objects.select_for_update()
        .select_related("product_size__product__brand", "product_size__size")
        .get(pk=line.pk)
    )
    product = line.product_size.product
    if product.brand.name != "دارما" or product.code != VARIANT_PRODUCT_CODE:
        raise ValueError("این تابع فقط برای محصول رنگ‌انتخابی s3 است.")

    brand = product.brand
    size = line.product_size.size
    home = StockLocation.objects.get(key=StockLocation.HOME)
    khorshid = StockLocation.objects.get(key=StockLocation.KHORSHID)
    ref = f"sale:{line.id}"

    # Return the previous allocation first; this makes re-upload idempotent.
    for alloc in list(line.allocations.select_related("color", "location").all()):
        bal, _ = StockBalance.objects.get_or_create(
            brand=brand, size=size, color=alloc.color, location=alloc.location, defaults={"qty": 0}
        )
        bal = StockBalance.objects.select_for_update().get(pk=bal.pk)
        bal.qty += int(alloc.qty)
        bal.save(update_fields=["qty"])
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.ADJUST,
            brand=brand, size=size, color=alloc.color, location=alloc.location,
            delta=int(alloc.qty), reference=f"{ref}:variant-recalc",
        )
    line.allocations.all().delete()
    line.shortages.all().delete()

    desired_total = sum(int(qty or 0) for qty in color_quantities.values())
    if desired_total != int(line.quantity or 0):
        raise ValueError(
            f"جمع رنگ‌های s3 ({desired_total}) با تعداد فروش ({int(line.quantity or 0)}) برابر نیست."
        )
    if line.quantity <= 0:
        line.inventory_applied_quantity = 0
        line.save(update_fields=["inventory_applied_quantity"])
        return {"shortages": [], "transferred": 0}

    transferred = 0
    shortages = []
    for color_name, qty in color_quantities.items():
        needed = int(qty or 0)
        if needed <= 0:
            continue
        color = _color_for_name(color_name)
        home_row, _ = StockBalance.objects.get_or_create(
            brand=brand, size=size, color=color, location=home, defaults={"qty": 0}
        )
        home_row = StockBalance.objects.select_for_update().get(pk=home_row.pk)

        if home_row.qty < needed:
            kh_row, _ = StockBalance.objects.get_or_create(
                brand=brand, size=size, color=color, location=khorshid, defaults={"qty": 0}
            )
            kh_row = StockBalance.objects.select_for_update().get(pk=kh_row.pk)
            move = min(max(0, needed - max(home_row.qty, 0)), max(kh_row.qty, 0))
            if move:
                kh_row.qty -= move
                home_row.qty += move
                kh_row.save(update_fields=["qty"])
                home_row.save(update_fields=["qty"])
                transferred += move
                InventoryMovement.objects.create(
                    movement_type=InventoryMovement.TRANSFER,
                    brand=brand, size=size, color=color, location=khorshid,
                    delta=-move, reference=f"{ref}:variant-auto-transfer",
                )
                InventoryMovement.objects.create(
                    movement_type=InventoryMovement.TRANSFER,
                    brand=brand, size=size, color=color, location=home,
                    delta=move, reference=f"{ref}:variant-auto-transfer",
                )

        available = max(0, int(home_row.qty or 0))
        home_row.qty -= needed
        home_row.save(update_fields=["qty"])
        SaleAllocation.objects.create(
            sale_line=line, color=color, location=home, qty=needed, is_replacement=False
        )
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.SALE,
            brand=brand, size=size, color=color, location=home,
            delta=-needed, reference=f"{ref}:variant",
        )
        if available < needed:
            shortage = SaleShortage.objects.create(
                sale_line=line, source_color=color, qty=needed - available, resolved=False
            )
            shortages.append(shortage)

    line.inventory_applied_quantity = line.quantity
    line.save(update_fields=["inventory_applied_quantity"])
    return {"shortages": shortages, "transferred": transferred}
