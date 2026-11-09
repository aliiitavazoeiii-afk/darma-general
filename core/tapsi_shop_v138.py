"""Tapsi Shop — independent pricing and order ledger, without Digikala SaleLine side effects.

Currency: toman. New V143 orders: 15% commission plus 10% VAT ON COMMISSION.
Historical orders: VAT = 0% to preserve their posted receivable/capital.
Delivery: 140,000 per order, irrespective of item count.
Discount input: manual sale-discount amount. V144+ Tapsi platform fee is 10% of that amount.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Prefetch

from .tapsi_infrastructure_v144 import infrastructure_allocations
from .darma_cost_v55 import darma_cost_for
from .novani_cost_v59 import novani_cost_for
from .takvin_pricing_v17 import takvin_cost_for
from .models import (
    InventoryMovement, ProductCode, ProductComposition, ProductSize, SaleDay,
    StockBalance, StockLocation, TapsiOrder, TapsiOrderItem,
    TapsiPriceRule, TapsiStockAllocation,
)


COMMISSION_PERCENT = Decimal("15.00")
VAT_ON_COMMISSION_PERCENT = Decimal("10.00")
SHIPPING_PER_ORDER = 140_000
INSURANCE_PERCENT = Decimal("1.50")
INFRASTRUCTURE_PERCENT = Decimal("0.30")
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


def initial_catalog_prices(product_sizes, on_date):
    """Read-only price for a newly added SKU before its first Tapsi-specific rule.

    An explicit Tapsi rule always wins. Otherwise use the existing canonical
    Digikala/manual product-size sale price as the initial default. The order
    snapshots the chosen price at registration; Tapsi price edits never mutate
    Digikala rules or past orders. This avoids making a new active size
    unselectable just because it was added after the one-time V140 price seed.
    """
    from .sale_price_v60 import sale_price_for
    entries = list(product_sizes)
    result = effective_prices([ps.pk for ps in entries], on_date)
    for ps in entries:
        if result.get(ps.pk, 0) <= 0:
            original = int(sale_price_for(ps, on_date) or 0)
            if original > 0:
                result[ps.pk] = original
    return result


def current_catalog(on_date):
    """Use exact shared product codes and titles; prices are Tapsi-exclusive."""
    products = list(
        ProductCode.objects.filter(active=True, brand__active=True)
        .exclude(brand__name="انبارش")  # manual-sale mirror of physical Darma, not an independent Digikala SKU
        .select_related("brand")
        .prefetch_related(
            Prefetch("sizes", queryset=ProductSize.objects.filter(active=True).select_related("size").order_by("size__sort_order", "size__id"))
        ).order_by("brand__name", "code", "id")
    )
    ids = [ps.pk for product in products for ps in product.sizes.all()]
    prices = initial_catalog_prices(
        [ps for product in products for ps in product.sizes.all()], on_date
    )
    catalog = []
    for product in products:
        sizes = [
            {"id": ps.pk, "name": ps.size.name, "price": prices.get(ps.pk, 0),
             "active": bool(ps.active)}
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
            item=item, brand=ps.product.brand, size=ps.size,
            color=comp.color, quantity=pieces, location=home,
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
        .exclude(product__brand__name="انبارش")
        .select_related("product__brand", "size")
    }
    if len(product_sizes) != len(amounts):
        raise ValueError("یکی از محصولات یا سایزهای سفارش غیرفعال یا نامعتبر است.")

    prices = initial_catalog_prices(product_sizes.values(), day.date)
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

    # Materialize only missing Tapsi prices on first successful order.
    # This freezes the imported/default price independently of future Digikala
    # repricing. transaction.atomic rolls this back if stock posting fails.
    missing = set(amounts) - set(effective_prices(amounts, day.date))
    for ps_id in missing:
        TapsiPriceRule.objects.get_or_create(
            product_size=product_sizes[ps_id], effective_from=day.date,
            defaults={"price": prices[ps_id]},
        )

    home = StockLocation.objects.get(key=StockLocation.HOME)
    order = TapsiOrder.objects.create(
        day=day, shipping_fee=SHIPPING_PER_ORDER,
        commission_percent=COMMISSION_PERCENT, vat_percent=VAT_ON_COMMISSION_PERCENT,
        insurance_percent=INSURANCE_PERCENT, infrastructure_percent=INFRASTRUCTURE_PERCENT,
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


def order_metrics(order, *, infrastructure=None):
    items = list(order.items.all())
    gross = sum(int(item.unit_price) * int(item.quantity) for item in items)
    cogs = sum(int(item.unit_cost) * int(item.pack_qty) * int(item.quantity) for item in items)
    shorts = sum(int(item.pack_qty) * int(item.quantity) for item in items)
    packs = sum(int(item.quantity) for item in items)
    commission = money(Decimal(gross) * Decimal(order.commission_percent) / Decimal(100))
    vat = money(Decimal(commission) * Decimal(order.vat_percent) / Decimal(100))
    insurance = money(Decimal(gross) * Decimal(order.insurance_percent) / Decimal(100))
    if infrastructure is None:
        infrastructure = infrastructure_allocations([order]).get(order.pk, 0)
    infrastructure = int(infrastructure)
    shipping = int(order.shipping_fee)
    # V144+ records store the user-entered sale-discount amount, not the Tapsi
    # charge. Tapsi's fee on that discount is 10%. Preserve historical V143
    # accounting semantics for earlier orders that have no infrastructure rate.
    entered_discount = int(order.discount_cost)
    discount = (money(Decimal(entered_discount) * Decimal("0.10"))
                if Decimal(order.infrastructure_percent) > 0 else entered_discount)
    fee = commission + vat + insurance + infrastructure + shipping + discount
    return {
        "gross": gross, "commission": commission, "vat": vat,
        "insurance": insurance, "infrastructure": infrastructure, "shipping": shipping,
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
        "gross": 0, "commission": 0, "vat": 0, "insurance": 0, "infrastructure": 0,
        "shipping": 0, "discount": 0, "fee": 0, "cogs": 0, "profit": 0,
        "shorts": 0, "packs": 0, "orders": len(orders),
    }
    allocated = infrastructure_allocations(orders)
    display = []
    for order in orders:
        metrics = order_metrics(order, infrastructure=allocated.get(order.id, 0))
        for key in ("gross", "commission", "vat", "insurance", "infrastructure", "shipping", "discount", "fee", "cogs", "profit", "shorts", "packs"):
            aggregate[key] += metrics[key]
        display.append({"obj": order, "items": list(order.items.all()), **metrics})
    return {"rows": display, "total": aggregate}


@transaction.atomic
def reverse_tapsi_order(order):
    """Exact allocation reversal, never infer today's composition or pricing."""
    obj = TapsiOrder.objects.select_for_update().get(pk=order.pk if hasattr(order, "pk") else order)
    items = list(
        obj.items.select_related("product_size__product__brand", "product_size__size")
        .prefetch_related("stock_allocations__brand", "stock_allocations__size", "stock_allocations__color", "stock_allocations__location")
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
                alloc.brand, alloc.size, alloc.color, alloc.location,
            )
            bal.qty += int(alloc.quantity)
            bal.save(update_fields=["qty"])
            InventoryMovement.objects.create(
                movement_type=InventoryMovement.ADJUST,
                brand=alloc.brand, size=alloc.size,
                color=alloc.color, location=alloc.location,
                delta=int(alloc.quantity), reference=f"tapsi-item:{item.pk}:reverse",
            )
    obj.delete()
    return len(items)


def tapsi_pricing_rows(on_date, size_names, darma_pack_qtys):
    """Two independent pricing blocks sharing the exact existing product catalog."""
    catalog = current_catalog(on_date)
    by_pack = defaultdict(list)
    individual = []
    for product in catalog:
        sizes = {entry["name"]: entry for entry in product["sizes"]}
        cells = [
            {"name": size, "id": sizes[size]["id"], "price": sizes[size]["price"], "active": True}
            if size in sizes else {"name": size, "active": False}
            for size in size_names
        ]
        individual.append({**product, "cells": cells})
        if product["brand"] == "دارما":
            by_pack[int(product["pack_qty"])].append(product)

    bulk = []
    for pack_qty in darma_pack_qtys:
        products = by_pack.get(int(pack_qty), [])
        cells = []
        for size in size_names:
            values = [
                entry["price"]
                for product in products for entry in product["sizes"]
                if entry["name"] == size
            ]
            mixed = len(set(values)) > 1
            cells.append({
                "name": size, "active": bool(values),
                "price": values[0] if values and not mixed else "",
                "mixed": mixed,
            })
        bulk.append({"pack_qty": pack_qty, "products": len(products), "cells": cells})
    return {"individual": individual, "bulk": bulk, "size_names": size_names}


@transaction.atomic
def save_tapsi_product_prices(product, effective_from, post):
    products = list(
        ProductSize.objects.filter(product=product, active=True, product__active=True)
        .select_related("size")
    )
    if not products:
        raise ValueError("این محصول سایز فعال ندارد.")
    updates = []
    for ps in products:
        raw = str(post.get(f"price_{ps.pk}") or "").strip()
        if not raw:
            continue
        price = positive_int(raw, f"قیمت {product.code}/{ps.size.name}")
        updates.append((ps, price))
    if not updates:
        raise ValueError("حداقل قیمت یک سایز را وارد کن.")
    for ps, price in updates:
        TapsiPriceRule.objects.update_or_create(
            product_size=ps, effective_from=effective_from,
            defaults={"price": price},
        )
    return len(updates)


@transaction.atomic
def save_tapsi_bulk_darma(pack_qty, effective_from, post):
    product_sizes = list(
        ProductSize.objects.filter(
            product__brand__name="دارما", product__pack_qty=int(pack_qty),
            product__active=True, active=True, size__name__in=DARMA_PACK_SIZES,
        ).select_related("size")
    )
    if not product_sizes:
        raise ValueError("برای این تعداد پک، محصول دارمای فعالی پیدا نشد.")
    group = defaultdict(list)
    for ps in product_sizes:
        group[ps.size.name].append(ps)
    updates = []
    for size, rows in group.items():
        value = str(post.get(f"price_{size}") or "").strip()
        if not value:
            raise ValueError(f"قیمت گروهی سایز {size} را وارد کن.")
        price = positive_int(value, f"قیمت گروهی سایز {size}")
        updates.extend((ps, price) for ps in rows)
    for ps, price in updates:
        TapsiPriceRule.objects.update_or_create(
            product_size=ps, effective_from=effective_from,
            defaults={"price": price},
        )
    return {"sizes": len(group), "rows": len(updates), "products": len({ps.product_id for ps, _ in updates})}


# V140: financial recognition is derived from recorded Tapsi orders, not a
# mutable manual account row. Until settlements are implemented every order is
# treated as unpaid; NEVER also add this receivable to a manual bank/account row.
def tapsi_receivable_total():
    orders = list(TapsiOrder.objects.select_related("day").prefetch_related("items").all())
    allocated = infrastructure_allocations(orders)
    return sum(int(m["gross"] - m["fee"]) for order in orders
               for m in [order_metrics(order, infrastructure=allocated.get(order.pk, 0))])


def _allocate_fee(amount, item_gross_values):
    """Distribute order-level charges to product sizes without rounding drift."""
    amount = int(amount)
    gross = sum(item_gross_values)
    if not item_gross_values:
        return []
    if not gross:
        return [0] * (len(item_gross_values) - 1) + [amount]
    shares = [amount * int(value) // gross for value in item_gross_values[:-1]]
    return shares + [amount - sum(shares)]


def tapsi_period_metrics(start, end):
    """Per-platform financial ledger for one reporting interval.

    Per-code and per-size profit includes its proportional share of the
    one-per-order shipping and 10% charge on the entered discount for V144+
    orders; values sum EXACTLY to order profit.
    No new side-effects: all snapshots originate in the immutable order items.
    """
    orders = list(
        TapsiOrder.objects.filter(day__date__gte=start, day__date__lte=end)
        .select_related("day")
        .prefetch_related(
            "items__product_size__product__brand",
            "items__product_size__size",
        )
        .order_by("day__date", "id")
    )
    totals = {
        "orders": len(orders), "gross": 0, "commission": 0, "vat": 0,
        "insurance": 0, "infrastructure": 0,
        "shipping": 0, "discount": 0, "fee": 0, "cogs": 0,
        "profit": 0, "shorts": 0, "packs": 0, "receivable": 0,
    }
    group = {}
    by_date = defaultdict(lambda: {"gross": 0, "profit": 0, "shorts": 0, "packs": 0})
    allocated = infrastructure_allocations(orders)
    for order in orders:
        metrics = order_metrics(order, infrastructure=allocated.get(order.id, 0))
        for k in ("gross", "commission", "vat", "insurance", "infrastructure", "shipping", "discount", "fee", "cogs", "profit", "shorts", "packs"):
            totals[k] += int(metrics[k])
        totals["receivable"] += metrics["gross"] - metrics["fee"]
        by_date[order.day.date]["gross"] += metrics["gross"]
        by_date[order.day.date]["profit"] += metrics["profit"]
        by_date[order.day.date]["shorts"] += metrics["shorts"]
        by_date[order.day.date]["packs"] += metrics["packs"]
        items = list(order.items.all())
        grosses = [int(it.unit_price) * int(it.quantity) for it in items]
        commission_parts = _allocate_fee(metrics["commission"], grosses)
        vat_parts = _allocate_fee(metrics["vat"], grosses)
        insurance_parts = _allocate_fee(metrics["insurance"], grosses)
        infrastructure_parts = _allocate_fee(metrics["infrastructure"], grosses)
        shipping_parts = _allocate_fee(metrics["shipping"], grosses)
        discount_parts = _allocate_fee(metrics["discount"], grosses)
        for i, item in enumerate(items):
            ps = item.product_size
            key = int(ps.pk)
            if key not in group:
                group[key] = {
                    "product_size_id": key,
                    "brand": ps.product.brand.name,
                    "code": item.code_snapshot or ps.product.code,
                    "title": item.title_snapshot or ps.product.title or ps.product.code,
                    "size": ps.size.name,
                    "packs": 0, "shorts": 0, "gross": 0, "cogs": 0,
                    "commission": 0, "vat": 0, "insurance": 0,
                    "infrastructure": 0, "shipping": 0, "discount": 0,
                    "fee": 0, "profit": 0,
                }
            row = group[key]
            item_gross = grosses[i]
            item_cogs = int(item.unit_cost) * int(item.pack_qty) * int(item.quantity)
            fees = (commission_parts[i] + vat_parts[i] + insurance_parts[i]
                    + infrastructure_parts[i] + shipping_parts[i] + discount_parts[i])
            row["gross"] += item_gross
            row["cogs"] += item_cogs
            row["packs"] += int(item.quantity)
            row["shorts"] += int(item.pack_qty) * int(item.quantity)
            row["commission"] += commission_parts[i]
            row["vat"] += vat_parts[i]
            row["insurance"] += insurance_parts[i]
            row["infrastructure"] += infrastructure_parts[i]
            row["shipping"] += shipping_parts[i]
            row["discount"] += discount_parts[i]
            row["fee"] += fees
            row["profit"] += item_gross - item_cogs - fees
    rows = sorted(group.values(), key=lambda row: (row["brand"], row["code"], row["size"]))
    # Guard against loss or double recognition when an order has multiple items.
    if sum(row["profit"] for row in rows) != totals["profit"]:
        raise RuntimeError("Tapsi profit reconciliation failed")
    if sum(row["fee"] for row in rows) != totals["fee"]:
        raise RuntimeError("Tapsi cost reconciliation failed")
    size_rows = defaultdict(lambda: {
        "packs": 0, "shorts": 0, "gross": 0, "cogs": 0, "fee": 0, "profit": 0,
    })
    for row in rows:
        dest = size_rows[row["size"]]
        for key in dest:
            dest[key] += row[key]
    return {
        "total": totals,
        "rows": rows,
        "by_size": [{"size": name, **values} for name, values in sorted(size_rows.items())],
        "by_date": dict(by_date),
    }
