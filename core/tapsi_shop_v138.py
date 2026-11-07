"""Tapsi Shop — independent pricing and order ledger, without Digikala SaleLine side effects.

Currency: toman. Fee: 15% INCLUDING all VAT (never tax it again).
Delivery: 140,000 per order, irrespective of item count.
Discount cost: manual fixed amount, no automatic discount-percentage logic.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Prefetch

from .darma_cost_v55 import darma_cost_for
from .novani_cost_v59 import novani_cost_for
from .takvin_pricing_v17 import takvin_cost_for
from .models import (
    InventoryMovement, ProductCode, ProductComposition, ProductSize, SaleDay,
    StockBalance, StockLocation, TapsiOrder, TapsiOrderItem,
    TapsiPriceRule, TapsiStockAllocation,
)


COMMISSION_PERCENT = Decimal("15.00")
SHIPPING_PER_ORDER = 140_000
DARMA_PACK_SIZES = ("M", "L", "XL", "XXL", "3XL", "4XL")


def money(value):
    return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def positive_int(value, label):
    text = str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    try:
        n = int(text.replace(",", "").replace("٬", "").replace(" ", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{label} معتبر نیست.")
    if n <= 0:
        raise ValueError(f"{label} باید بیشتر از صفر باشد.")
    return n


def nonnegative_int(value, label):
    if value in (None, ""):
        return 0
    text = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    try:
        n = int(text.replace(",", "").replace("٬", "").replace(" ", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{label} معتبر نیست.")
    if n < 0:
        raise ValueError(f"{label} نمی‌تواند منفی باشد.")
    return n


def effective_prices(product_size_ids, on_date):
    """One bulk query, latest effective rule on or before date, no Digikala fallback."""
    ids = [int(x) for x in product_size_ids]
    result = {}
    if not ids:
        return result
    for row in TapsiPriceRule.objects.filter(
        product_size_id__in=ids, effective_from__lte=on_date
    ).order_by("-effective_from", "-id"):
        result.setdefault(row.product_size_id, int(row.price))
    return result


def tapsi_price_for(product_size, on_date):
    ps_id = product_size.pk if isinstance(product_size, ProductSize) else int(product_size)
    return effective_prices([ps_id], on_date).get(ps_id, 0)


def current_catalog(on_date):
    """Use exact shared product codes and titles; prices are Tapsi-exclusive."""
    products = list(
        ProductCode.objects.filter(active=True, brand__active=True)
        .select_related("brand")
        .prefetch_related(
            Prefetch("sizes", queryset=ProductSize.objects.filter(active=True).select_related("size").order_by("size__sort_order", "size__id"))
        ).order_by("brand__name", "code", "id")
    )
    ids = [ps.pk for product in products for ps in product.sizes.all()]
    prices = effective_prices(ids, on_date)
    catalog = []
    for product in products:
        sizes = [
            {"id": ps.pk, "name": ps.size.name, "price": prices.get(ps.pk, 0)}
            for ps in product.sizes.all()
        ]
        if not sizes:
            continue
        catalog.append({
            "id": product.pk, "code": product.code,
            "title": product.title or product.code,
            "brand": product.brand.name,
            "pack_qty": product.pack_qty,
            "sizes": sizes,
        })
    return catalog


def product_unit_cost(ps, on_date):
    name = ps.product.brand.name
    if name in {"دارما", "انبارش"}:
        return int(darma_cost_for(on_date))
    if name == "Novani":
        return int(novani_cost_for(on_date))
    if name == "تکوین":
        return int(takvin_cost_for(ps.size, on_date))
    return int(ps.unit_cost or 0)


def _locked_home_balance(brand, size, color, home):
    balance, _ = StockBalance.objects.select_for_update().get_or_create(
        brand=brand, size=size, color=color, location=home, defaults={"qty": 0}
    )
    return balance


def _deduct_item(item, compositions, home):
    """Record exact physical colors so subsequent deletion can reverse identically."""
    ps = item.product_size
    for comp in compositions:
        pieces = int(comp.qty) * int(item.quantity)
        if pieces <= 0:
            continue
        balance = _locked_home_balance(ps.product.brand, ps.size, comp.color, home)
        # Existing Digikala/manual sale convention permits negative HOME stock;
        # do not silently transfer from KHORSHID into HOME.
        balance.qty -= pieces
        balance.save(update_fields=["qty"])
        TapsiStockAllocation.objects.create(
            item=item, color=comp.color, quantity=pieces, location=home,
        )
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.SALE,
            brand=ps.product.brand, size=ps.size, color=comp.color,
            location=home, delta=-pieces, reference=f"tapsi-item:{item.pk}",
        )


@transaction.atomic
def create_tapsi_order(day, pairs, discount_cost=0, note=""):
    """One order may have multiple product/size lines, one shipping charge."""
    day = SaleDay.objects.select_for_update().get(pk=day.pk if hasattr(day, "pk") else day)
    amounts = defaultdict(int)
    for ps_id, quantity in pairs:
        ps_id = positive_int(ps_id, "کد سایز")
        quantity = positive_int(quantity, "تعداد")
        amounts[ps_id] += quantity
    if not amounts:
        raise ValueError("حداقل یک محصول باید به سفارش اضافه شود.")
    if len(amounts) > 50 or sum(amounts.values()) > 10000:
        raise ValueError("تعداد اقلام سفارش بیش از حد مجاز است.")

    discount_cost = nonnegative_int(discount_cost, "هزینه تخفیف")
    note = str(note or "").strip()[:300]
    product_sizes = {
        ps.pk: ps
        for ps in ProductSize.objects.filter(pk__in=amounts, active=True, product__active=True)
        .select_related("product__brand", "size")
    }
    if len(product_sizes) != len(amounts):
        raise ValueError("یکی از محصولات یا سایزهای سفارش غیرفعال یا نامعتبر است.")

    prices = effective_prices(amounts, day.date)
    compositions = {}
    for ps_id, ps in product_sizes.items():
        if prices.get(ps_id, 0) <= 0:
            raise ValueError(f"ابتدا قیمت تپسی‌شاپ {ps.product.code} / {ps.size.name} را در قیمت‌گذاری ثبت کن.")
        comps = list(ProductComposition.objects.filter(product=ps.product).select_related("color"))
        if not comps or sum(int(comp.qty) for comp in comps) != int(ps.product.pack_qty):
            raise ValueError(
                f"ترکیب رنگ کد {ps.product.code} کامل نیست؛ قبل از ثبت فروش آن را در تعریف محصول اصلاح کن."
            )
        compositions[ps_id] = comps

    home = StockLocation.objects.get(key=StockLocation.HOME)
    order = TapsiOrder.objects.create(
        day=day, shipping_fee=SHIPPING_PER_ORDER,
        commission_percent=COMMISSION_PERCENT,
        discount_cost=discount_cost, note=note,
    )
    for ps_id, quantity in amounts.items():
        ps = product_sizes[ps_id]
        item = TapsiOrderItem.objects.create(
            order=order, product_size=ps, quantity=quantity, unit_price=prices[ps_id],
            unit_cost=product_unit_cost(ps, day.date), pack_qty=ps.product.pack_qty,
            code_snapshot=ps.product.code, title_snapshot=ps.product.title or ps.product.code,
        )
        _deduct_item(item, compositions[ps_id], home)
    return order


def order_metrics(order):
    items = list(order.items.all())
    gross = sum(int(item.unit_price) * int(item.quantity) for item in items)
    cogs = sum(int(item.unit_cost) * int(item.pack_qty) * int(item.quantity) for item in items)
    shorts = sum(int(item.pack_qty) * int(item.quantity) for item in items)
    packs = sum(int(item.quantity) for item in items)
    commission = money(Decimal(gross) * Decimal(order.commission_percent) / Decimal(100))
    shipping = int(order.shipping_fee)
    discount = int(order.discount_cost)
    fee = commission + shipping + discount
    return {
        "gross": gross, "commission": commission, "shipping": shipping,
        "discount": discount, "fee": fee, "cogs": cogs,
        "profit": gross - fee - cogs, "shorts": shorts, "packs": packs,
    }


def tapsi_day_summary(day):
    orders = list(
        TapsiOrder.objects.filter(day=day).prefetch_related(
            "items__product_size__product__brand", "items__product_size__size"
        ).order_by("-id")
    )
    aggregate = {
        "gross": 0, "commission": 0, "shipping": 0, "discount": 0,
        "fee": 0, "cogs": 0, "profit": 0, "shorts": 0, "packs": 0,
        "orders": len(orders),
    }
    display = []
    for order in orders:
        metrics = order_metrics(order)
        for key in ("gross", "commission", "shipping", "discount", "fee", "cogs", "profit", "shorts", "packs"):
            aggregate[key] += metrics[key]
        display.append({"obj": order, "items": list(order.items.all()), **metrics})
    return {"rows": display, "total": aggregate}


@transaction.atomic
def reverse_tapsi_order(order):
    """Exact allocation reversal, never infer today's composition or pricing."""
    obj = TapsiOrder.objects.select_for_update().get(pk=order.pk if hasattr(order, "pk") else order)
    items = list(
        obj.items.select_related("product_size__product__brand", "product_size__size")
        .prefetch_related("stock_allocations__color", "stock_allocations__location")
        .order_by("pk")
    )
    for item in items:
        allocations = list(item.stock_allocations.all())
        if int(item.quantity) > 0 and not allocations:
            raise ValueError("این سفارش سابقه برداشت دقیق موجودی ندارد؛ حذف متوقف شد.")
        if sum(int(a.quantity) for a in allocations) != int(item.quantity) * int(item.pack_qty):
            raise ValueError("مقادیر برداشت موجودی سفارش با کالاها تطبیق ندارند؛ حذف متوقف شد.")
    for item in items:
        for alloc in item.stock_allocations.all():
            bal = _locked_home_balance(
                item.product_size.product.brand, item.product_size.size,
                alloc.color, alloc.location,
            )
            bal.qty += int(alloc.quantity)
            bal.save(update_fields=["qty"])
            InventoryMovement.objects.create(
                movement_type=InventoryMovement.ADJUST,
                brand=item.product_size.product.brand, size=item.product_size.size,
                color=alloc.color, location=alloc.location,
                delta=int(alloc.quantity), reference=f"tapsi-item:{item.pk}:reverse",
            )
    obj.delete()
    return len(items)
