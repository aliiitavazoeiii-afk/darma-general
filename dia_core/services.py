from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from .models import (
    Account,
    AccountEntry,
    AppSetting,
    InventoryMovement,
    ProductVariant,
    PurchaseLine,
    ReturnRecord,
    SaleLine,
    StockBalance,
    StockLocation,
)


def _setting_decimal(key, default=0):
    raw = AppSetting.objects.filter(key=key).values_list("value", flat=True).first()
    try:
        return Decimal(str(default if raw in (None, "") else raw))
    except Exception:
        return Decimal(str(default))


def _round_toman(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def digikala_fee_for_unit(sale_price):
    """Same internal Digikala commission formula used by the reference panel.

    This function performs no network/API call. Values are local AppSetting rows and
    can later be changed from Dia Gallery settings.
    """
    price = Decimal(sale_price or 0)
    commission_rate = _setting_decimal("digikala_commission_percent", 24) / Decimal(100)
    processing_rate = _setting_decimal("digikala_processing_percent", 7) / Decimal(100)
    processing_floor = _setting_decimal("digikala_processing_floor", 36000)
    vat_rate = _setting_decimal("digikala_vat_percent", 10) / Decimal(100)
    floor_taxable = _setting_decimal("digikala_floor_taxable_part", 18000)

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


def main_location():
    return StockLocation.objects.get(key="main")


def stock_for(variant, location=None, *, lock=False):
    location = location or main_location()
    obj, _ = StockBalance.objects.get_or_create(
        variant=variant,
        location=location,
        defaults={"qty": 0},
    )
    if lock:
        return StockBalance.objects.select_for_update().get(pk=obj.pk)
    return obj


def sale_metrics(line):
    qty = int(line.quantity or 0)
    gross = qty * int(line.sale_price or 0)
    fee = qty * int(line.digikala_fee_unit or 0)
    cogs = qty * int(line.unit_cost_snapshot or 0)
    profit = gross - fee - cogs
    return {
        "gross": gross,
        "digikala_fee": fee,
        "cogs": cogs,
        "profit": profit,
        "quantity": qty,
        "margin": (profit * 100 / gross) if gross else 0,
    }


@transaction.atomic
def sync_sale_inventory(line):
    line = SaleLine.objects.select_for_update().select_related("variant", "day").get(pk=line.pk)
    target = max(0, int(line.quantity or 0))
    applied = max(0, int(line.inventory_applied_quantity or 0))
    delta = target - applied
    if not delta:
        return 0

    location = main_location()
    balance = stock_for(line.variant, location, lock=True)
    balance.qty = int(balance.qty or 0) - delta
    balance.save(update_fields=["qty"])
    InventoryMovement.objects.create(
        date=line.day.date,
        movement_type=InventoryMovement.SALE,
        variant=line.variant,
        location=location,
        delta=-delta,
        reference=f"sale:{line.id}",
    )
    line.inventory_applied_quantity = target
    line.save(update_fields=["inventory_applied_quantity", "updated_at"])
    return delta


@transaction.atomic
def sync_purchase_inventory(line):
    line = PurchaseLine.objects.select_for_update().select_related("variant").get(pk=line.pk)
    target = max(0, int(line.quantity or 0))
    applied = max(0, int(line.inventory_applied_quantity or 0))
    delta = target - applied
    if not delta:
        return 0

    location = main_location()
    balance = stock_for(line.variant, location, lock=True)
    balance.qty = int(balance.qty or 0) + delta
    balance.save(update_fields=["qty"])
    InventoryMovement.objects.create(
        date=line.date,
        movement_type=InventoryMovement.PURCHASE,
        variant=line.variant,
        location=location,
        delta=delta,
        reference=f"purchase:{line.id}",
        note=line.note,
    )
    line.inventory_applied_quantity = target
    line.save(update_fields=["inventory_applied_quantity", "updated_at"])
    return delta


@transaction.atomic
def create_return(*, date, variant, quantity, note=""):
    qty = max(0, int(quantity or 0))
    if qty <= 0:
        raise ValueError("تعداد مرجوعی باید بیشتر از صفر باشد.")
    row = ReturnRecord.objects.create(date=date, variant=variant, quantity=qty, note=note or "")
    location = main_location()
    balance = stock_for(variant, location, lock=True)
    balance.qty = int(balance.qty or 0) + qty
    balance.save(update_fields=["qty"])
    InventoryMovement.objects.create(
        date=date,
        movement_type=InventoryMovement.RETURN,
        variant=variant,
        location=location,
        delta=qty,
        reference=f"return:{row.id}",
        note=note or "",
    )
    return row


@transaction.atomic
def create_adjustment(*, date, variant, location, delta, note=""):
    delta = int(delta or 0)
    if delta == 0:
        raise ValueError("مقدار اصلاح نمی‌تواند صفر باشد.")
    from .models import InventoryAdjustment

    row = InventoryAdjustment.objects.create(
        date=date,
        variant=variant,
        location=location,
        delta=delta,
        note=note or "",
    )
    balance = stock_for(variant, location, lock=True)
    balance.qty = int(balance.qty or 0) + delta
    balance.save(update_fields=["qty"])
    InventoryMovement.objects.create(
        date=date,
        movement_type=InventoryMovement.ADJUST,
        variant=variant,
        location=location,
        delta=delta,
        reference=f"adjust:{row.id}",
        note=note or "",
    )
    return row


def account_balance(account):
    entries = account.entries.aggregate(v=Sum("delta"))["v"] or 0
    return int(account.opening_balance or 0) + int(entries)


def create_account_entry(*, account, date, delta, title, reference="", note=""):
    return AccountEntry.objects.create(
        account=account,
        date=date,
        delta=int(delta),
        title=title,
        reference=reference,
        note=note or "",
    )
