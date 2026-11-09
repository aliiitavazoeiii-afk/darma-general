"""V147: automatic warehouse -> tailor FABRIC transfer for newly-created Darma sheets.

The sheet stores an opt-in creation flag, so historical sheets are NEVER
retroactively transferred. The per-source-lot ledger makes save idempotent,
allows exact delta updates, and guarantees safe rollback on deletion.
ELASTIC is deliberately excluded, and production consumption is a separate
operation that must never trigger an additional transfer.
"""
from decimal import Decimal
from django.db import transaction
from .material_flow import FABRIC, WAREHOUSE, TAILOR, q, transfer_fabric_to_tailor
from .models import MaterialReportFabricTransfer, RawMaterialStock


def _target_weight(value, key):
    raw = str(value or "").strip()
    if not raw:
        return Decimal("0.000")
    # q() accepts Persian decimal separators but converts invalid input to zero;
    # never silently shift warehouse inventory for a malformed input.
    parsed = q(raw)
    if parsed < 0 or (parsed == 0 and raw not in {"0", "0.0", "0.00", "0.000", "۰", "۰.۰"}):
        raise ValueError(f"وزن پارچه رنگ {key} معتبر نیست.")
    if parsed != parsed.quantize(Decimal("0.001")):
        raise ValueError("وزن پارچه حداکثر سه رقم اعشار می‌تواند داشته باشد.")
    return parsed


def _sheet_enabled(block):
    return block.brand.name == "دارما" and bool(
        ((block.input_data or {}).get("_meta") or {}).get("auto_fabric_transfer_v147")
    )


@transaction.atomic
def sync_sheet_auto_fabric(block):
    """Reconcile target weights, never transfer twice on repeated saves."""
    if not _sheet_enabled(block):
        return {}
    input_data = block.input_data or {}
    old = list(
        MaterialReportFabricTransfer.objects.select_for_update()
        .filter(block=block).select_related("source", "tailor_stock").order_by("id")
    )
    current = {}
    for allocation in old:
        current[allocation.material_key] = current.get(allocation.material_key, Decimal(0)) + allocation.quantity
    keys = set(current) | {k for k in input_data if k != "_meta"}
    result = {}
    for key in sorted(keys):
        raw = (input_data.get(key) or {}).get("weight") if isinstance(input_data.get(key), dict) else ""
        wanted = _target_weight(raw, key)
        previous = current.get(key, Decimal(0))
        delta = wanted - previous
        if delta == 0:
            continue
        if delta > 0:
            lots = list(RawMaterialStock.objects.select_for_update().filter(
                active=True, kind=FABRIC, location=WAREHOUSE,
                material_key=key,
            ).order_by("id"))
            available = sum((max(Decimal(0), row.quantity) for row in lots), Decimal(0))
            if available < delta:
                raise ValueError(
                    f"موجودی پارچه رنگ {key} در انبار کافی نیست؛ "
                    f"موجود {available} کیلو، انتقال درخواستی {delta} کیلو. "
                    "صورت و موجودی بدون تغییر باقی ماندند."
                )
            remaining = delta
            for source in lots:
                take = min(max(Decimal(0), source.quantity), remaining)
                if take <= 0:
                    continue
                tailor = transfer_fabric_to_tailor(source.pk, take)
                row, _ = MaterialReportFabricTransfer.objects.select_for_update().get_or_create(
                    block=block, material_key=key, source=source,
                    defaults={"tailor_stock": tailor, "quantity": Decimal("0.000")},
                )
                if row.tailor_stock_id != tailor.id:
                    raise ValueError("سند محل پارچه با انتقال فعلی مغایرت دارد؛ عملیات متوقف شد.")
                row.quantity += take
                row.save(update_fields=["quantity"])
                remaining -= take
                if remaining == 0:
                    break
            if remaining != 0:
                raise ValueError("انتقال کامل پارچه ثبت نشد؛ کل عملیات برگشت.")
        else:
            # Return ONLY the saved source-lot portions, never infer from
            # unrelated stock or subtract consumed material a second time.
            remaining = -delta
            rows = [row for row in reversed(old) if row.material_key == key]
            for row in rows:
                amount = min(row.quantity, remaining)
                if amount <= 0:
                    continue
                source = RawMaterialStock.objects.select_for_update().get(pk=row.source_id)
                tailor = RawMaterialStock.objects.select_for_update().get(pk=row.tailor_stock_id)
                if not source.active or not tailor.active or source.location != WAREHOUSE or tailor.location != TAILOR:
                    raise ValueError("سابقه محل پارچه تغییر کرده و برگشت خودکار امن نیست.")
                if tailor.quantity < amount:
                    raise ValueError(
                        f"از پارچه {key} نزد خیاط مصرف شده است؛ برای کاهش وزن صورت ابتدا "
                        "مصرف قبلی آن را برگردان. موجودی خودکار تغییر نکرد."
                    )
                tailor.quantity -= amount
                source.quantity += amount
                tailor.save(update_fields=["quantity", "updated_at"])
                source.save(update_fields=["quantity", "updated_at"])
                row.quantity -= amount
                if row.quantity == 0:
                    row.delete()
                else:
                    row.save(update_fields=["quantity"])
                remaining -= amount
                if remaining == 0:
                    break
            if remaining != 0:
                raise ValueError("سند انتقال برای برگشت وزن کامل نیست؛ عملیات برگشت.")
        result[key] = delta
    return result


@transaction.atomic
def reverse_sheet_auto_fabric(block):
    """Undo all sheet-owned moves before deleting the sheet, if still available."""
    if not _sheet_enabled(block):
        return
    current = dict(block.input_data or {})
    # Source data stays immutable until the entire DB transaction commits.
    for key, values in current.items():
        if key == "_meta" or not isinstance(values, dict):
            continue
        values["weight"] = "0"
    block.input_data = current
    sync_sheet_auto_fabric(block)
    if MaterialReportFabricTransfer.objects.filter(block=block).exists():
        raise ValueError("برگشت خودکار پارچه این صورت کامل نشد.")
