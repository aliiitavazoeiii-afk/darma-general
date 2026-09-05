from decimal import Decimal, ROUND_HALF_UP

from .darma_cost_v55 import darma_cost_for
from .models import AppSetting


def _setting(key, default):
    value = AppSetting.objects.filter(key=key).values_list("value", flat=True).first()
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except Exception:
        return Decimal(str(default))


def _round_toman(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def digikala_fee_for_unit(sale_price):
    price = Decimal(sale_price or 0)
    commission_rate = _setting("digikala_commission_percent", 24) / Decimal(100)
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
    fee_unit = int((snap.digikala_fee_unit if snap else 0) or digikala_fee_for_unit(line.sale_price))
    digikala_fee = qty * fee_unit
    shorts = qty * pack_qty

    if snap and int(snap.unit_cost or 0) > 0:
        unit_cost = int(snap.unit_cost)
    else:
        brand_name = line.product_size.product.brand.name
        if brand_name in {"دارما", "انبارش"}:
            # V55 safety fallback: even a legacy/missing Snapshot must resolve Darma
            # COGS from the one date-effective source of truth, never ProductSize or
            # color/size InventoryModelCost.
            unit_cost = int(darma_cost_for(line.day.date))
        else:
            unit_cost = int(line.product_size.unit_cost or 0)

    cogs = shorts * unit_cost
    profit = gross - digikala_fee - cogs
    margin = (profit / gross * 100) if gross else 0
    return {"gross": gross, "digikala_fee": digikala_fee, "cogs": cogs, "profit": profit, "margin": margin, "shorts": shorts, "packs": qty}
