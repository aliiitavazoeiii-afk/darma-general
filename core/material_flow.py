from decimal import Decimal

from django.db import transaction

from .models import MaterialReportConsumption, RawMaterialStock


FABRIC = RawMaterialStock.FABRIC
ELASTIC = RawMaterialStock.ELASTIC
WAREHOUSE = RawMaterialStock.WAREHOUSE
TAILOR = RawMaterialStock.TAILOR


COLOR_LABELS = {
    "black": "مشکی",
    "white": "سفید",
    "navy": "سرمه‌ای",
    "pink": "صورتی",
    "cream": "کرم",
    "red": "قرمز",
    "yellow": "زرد",
    "gray": "طوسی",
    "stripe": "راه راه",
}


def q(value):
    try:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value).replace("٬", "").replace(" ", "").replace(",", "."))
    except Exception:
        return Decimal("0")


def _weighted_price(old_qty, old_price, add_qty, add_price):
    total_qty = old_qty + add_qty
    if total_qty <= 0:
        return int(add_price or old_price or 0)
    total_value = old_qty * Decimal(int(old_price or 0)) + add_qty * Decimal(int(add_price or 0))
    return int(total_value / total_qty)


def _get_or_create_aggregate(kind, location, material_key, title, variant="", unit="کیلو", unit_price=0):
    row = RawMaterialStock.objects.filter(
        active=True,
        kind=kind,
        location=location,
        material_key=material_key,
        variant=variant,
        title=title,
    ).order_by("id").first()
    if row:
        return row
    return RawMaterialStock.objects.create(
        kind=kind,
        location=location,
        material_key=material_key,
        variant=variant,
        title=title,
        quantity=Decimal("0"),
        unit_price=int(unit_price or 0),
        unit=unit or "کیلو",
    )


@transaction.atomic
def add_warehouse_stock(*, kind, material_key, title, quantity, unit_price, variant="", unit="کیلو", note=""):
    quantity = q(quantity)
    if quantity <= 0:
        raise ValueError("مقدار باید بیشتر از صفر باشد.")
    unit_price = int(unit_price or 0)

    if kind == FABRIC:
        return RawMaterialStock.objects.create(
            kind=kind,
            location=WAREHOUSE,
            material_key=material_key,
            variant="",
            title=title,
            quantity=quantity,
            unit_price=unit_price,
            unit=unit or "کیلو",
            note=note,
        )

    row = _get_or_create_aggregate(kind, WAREHOUSE, material_key, title, variant, unit, unit_price)
    row.unit_price = _weighted_price(q(row.quantity), row.unit_price, quantity, unit_price)
    row.quantity = q(row.quantity) + quantity
    if note:
        row.note = note
    row.save()
    return row


@transaction.atomic
def transfer_fabric_to_tailor(source_id, quantity):
    quantity = q(quantity)
    source = RawMaterialStock.objects.select_for_update().get(
        id=source_id, kind=FABRIC, location=WAREHOUSE, active=True
    )
    if quantity <= 0:
        raise ValueError("وزن انتقال باید بیشتر از صفر باشد.")
    if q(source.quantity) < quantity:
        raise ValueError("وزن انتقال از موجودی انبار بیشتر است.")

    source.quantity = q(source.quantity) - quantity
    source.save(update_fields=["quantity", "updated_at"])
    target = RawMaterialStock.objects.create(
        kind=FABRIC,
        location=TAILOR,
        material_key=source.material_key,
        variant="",
        title=source.title,
        quantity=quantity,
        unit_price=source.unit_price,
        unit=source.unit,
        note=f"انتقال از انبار / ردیف {source.id}",
    )
    return target


@transaction.atomic
def transfer_elastic_to_tailor(material_key, title, qty16=0, qty25=0):
    moved = []
    for variant, quantity in (("16", q(qty16)), ("25", q(qty25))):
        if quantity <= 0:
            continue
        source = RawMaterialStock.objects.select_for_update().filter(
            active=True,
            kind=ELASTIC,
            location=WAREHOUSE,
            material_key=material_key,
            variant=variant,
        ).order_by("id").first()
        if not source or q(source.quantity) < quantity:
            raise ValueError(f"موجودی کش {variant} این رنگ در انبار کافی نیست.")
        source.quantity = q(source.quantity) - quantity
        source.save(update_fields=["quantity", "updated_at"])

        target = _get_or_create_aggregate(
            ELASTIC, TAILOR, material_key, title, variant, source.unit, source.unit_price
        )
        target.unit_price = _weighted_price(q(target.quantity), target.unit_price, quantity, source.unit_price)
        target.quantity = q(target.quantity) + quantity
        target.save()
        moved.append(target)
    if not moved:
        raise ValueError("حداقل یکی از مقادیر کش 16 یا 25 را وارد کن.")
    return moved


def _consume_rows(kind, material_key, variant, delta):
    """Apply positive delta as consumption from tailor; negative delta returns stock."""
    delta = q(delta)
    if delta == 0:
        return

    rows = list(
        RawMaterialStock.objects.select_for_update().filter(
            active=True,
            kind=kind,
            location=TAILOR,
            material_key=material_key,
            variant=variant,
        ).order_by("id")
    )
    title = COLOR_LABELS.get(material_key, material_key or "نامشخص")

    if delta > 0:
        remaining = delta
        last_price = 0
        for row in rows:
            available = max(q(row.quantity), Decimal("0"))
            if available <= 0:
                continue
            take = min(available, remaining)
            row.quantity = q(row.quantity) - take
            last_price = row.unit_price
            row.save(update_fields=["quantity", "updated_at"])
            remaining -= take
            if remaining <= 0:
                break
        if remaining > 0:
            shortage = _get_or_create_aggregate(
                kind, TAILOR, material_key, title, variant, "کیلو", last_price
            )
            shortage.quantity = q(shortage.quantity) - remaining
            shortage.save(update_fields=["quantity", "updated_at"])
    else:
        amount = -delta
        target = rows[0] if rows else _get_or_create_aggregate(
            kind, TAILOR, material_key, title, variant, "کیلو", 0
        )
        target.quantity = q(target.quantity) + amount
        target.save(update_fields=["quantity", "updated_at"])


def desired_consumption(input_data):
    desired = {}
    input_data = input_data or {}
    for key in COLOR_LABELS:
        values = input_data.get(key, {}) or {}
        fabric = q(values.get("weight"))
        if fabric:
            desired[(FABRIC, key, "")] = max(fabric, Decimal("0"))

        delivered16 = q(values.get("elastic16"))
        delivered25 = q(values.get("elastic25"))
        remain16_raw = values.get("remain16")
        remain25_raw = values.get("remain25")
        used16 = delivered16 - q(remain16_raw) if remain16_raw not in (None, "") else delivered16
        used25 = delivered25 - q(remain25_raw) if remain25_raw not in (None, "") else delivered25
        if used16:
            desired[(ELASTIC, key, "16")] = max(used16, Decimal("0"))
        if used25:
            desired[(ELASTIC, key, "25")] = max(used25, Decimal("0"))
    return desired


@transaction.atomic
def sync_report_consumption(block):
    desired = desired_consumption(block.input_data)
    existing = {
        (row.kind, row.material_key, row.variant): row
        for row in MaterialReportConsumption.objects.select_for_update().filter(block=block)
    }
    keys = set(desired) | set(existing)
    for key in keys:
        old = q(existing[key].quantity) if key in existing else Decimal("0")
        new = q(desired.get(key, 0))
        delta = new - old
        _consume_rows(key[0], key[1], key[2], delta)
        if new == 0:
            if key in existing:
                existing[key].delete()
        elif key in existing:
            existing[key].quantity = new
            existing[key].save(update_fields=["quantity"])
        else:
            MaterialReportConsumption.objects.create(
                block=block,
                kind=key[0],
                material_key=key[1],
                variant=key[2],
                quantity=new,
            )


@transaction.atomic
def reverse_report_consumption(block):
    for row in list(MaterialReportConsumption.objects.select_for_update().filter(block=block)):
        _consume_rows(row.kind, row.material_key, row.variant, -q(row.quantity))
    MaterialReportConsumption.objects.filter(block=block).delete()
