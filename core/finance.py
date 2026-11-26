from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .darma_cost_v55 import darma_cost_for
from .models import AppSetting
from .novani_cost_v59 import novani_cost_for
from .digikala_five_pack_v155 import applies_to as five_pack_19_applies
from .stripe_01_v151 import (
    applies_to as stripe01_offer_applies,
    stripe01_unit_cost_for,
    UNIT_COST as STRIPE01_BASE_UNIT_COST,
)


# One-off Digikala promotion/settlement rule reported for 1405/07/08 only.
# 1405/07/08 == 2026-09-30 Gregorian.
DIGIKALA_ZERO_COMMISSION_DATES = {date(2026, 9, 30)}


def _setting(key, default):
    value = AppSetting.objects.filter(key=key).values_list("value", flat=True).first()
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except Exception:
        return Decimal(str(default))


def _round_toman(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def is_digikala_zero_commission_date(sale_date):
    return sale_date in DIGIKALA_ZERO_COMMISSION_DATES


def digikala_fee_for_unit(sale_price, sale_date=None, *, product_code=None, brand_name=None, pack_qty=None):
    price = Decimal(sale_price or 0)
    commission_rate = _setting("digikala_commission_percent", 24) / Decimal(100)
    if is_digikala_zero_commission_date(sale_date):
        commission_rate = Decimal(0)
    elif five_pack_19_applies(sale_date, pack_qty):
        # V155: all 5-piece SKUs, only Azar 5, 6, 7. Processing/VAT untouched.
        commission_rate = Decimal("0.19")
    elif stripe01_offer_applies(sale_date, brand_name, product_code):
        # Only the NEW stripe-01 Darma SKU, only 1–10 Azar 1405.
        # Processing floor, VAT basis and other categories remain unchanged.
        commission_rate = Decimal("0.13")
    processing_rate = _setting("digikala_processing_percent", 7) / Decimal(100)
    processing_floor = _setting("digikala_processing_floor", 36000)
    vat_rate = _setting("digikala_vat_percent", 10) / Decimal(100)
    floor_taxable = _setting("digikala_floor_taxable_part", 18000)
    commission = price * commission_rate
    raw_processing = price * processing_rate
    if raw_processing < processing_floor:
        processing = processing_floor
        taxable_processing = floor_taxable
    else:
        processing = raw_processing
        taxable_processing = processing / Decimal(2)
    vat = (commission + taxable_processing) * vat_rate
    return _round_toman(commission + processing + vat)


def sale_line_metrics(line):
    qty = int(line.quantity or 0)
    try:
        snap = line.snapshot
    except Exception:
        snap = None
    pack_qty = int((snap.pack_qty if snap else 0) or line.product_size.product.pack_qty or 0)
    gross = qty * int(line.sale_price or 0)
    # V155: previous snapshots may contain a different fee. Override the fee
    # at read time for this date/pack window, leaving COGS and price frozen.
    recompute_promo_fee = five_pack_19_applies(line.day.date, pack_qty)
    fee_unit = int(
        digikala_fee_for_unit(
            line.sale_price, line.day.date,
            product_code=line.product_size.product.code,
            brand_name=line.product_size.product.brand.name,
            pack_qty=pack_qty,
        )
        if recompute_promo_fee else
        (
            (snap.digikala_fee_unit if snap else 0)
            or digikala_fee_for_unit(
                line.sale_price, line.day.date,
                product_code=line.product_size.product.code,
                brand_name=line.product_size.product.brand.name,
                pack_qty=pack_qty,
            )
        )
    )
    digikala_fee = qty * fee_unit
    shorts = qty * pack_qty

    if snap and int(snap.unit_cost or 0) > 0:
        unit_cost = int(snap.unit_cost)
    else:
        brand_name = line.product_size.product.brand.name
        if brand_name == "دارما" and line.product_size.product.code == "rahrah-01":
            unit_cost = stripe01_unit_cost_for(
                line.day.date, brand_name, line.product_size.product.code,
                line.product_size.unit_cost or STRIPE01_BASE_UNIT_COST,
            )
        elif brand_name in {"دارما", "انبارش"}:
            unit_cost = int(darma_cost_for(line.day.date))
        elif brand_name == "Novani":
            unit_cost = int(novani_cost_for(line.day.date))
        else:
            unit_cost = int(line.product_size.unit_cost or 0)

    cogs = shorts * unit_cost
    profit = gross - digikala_fee - cogs
    margin = (profit / gross * 100) if gross else 0
    return {"gross": gross, "digikala_fee": digikala_fee, "cogs": cogs, "profit": profit, "margin": margin, "shorts": shorts, "packs": qty}
