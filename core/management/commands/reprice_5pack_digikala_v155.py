"""V155 historical commission reconciliation. DRY-RUN unless --apply.

Only existing SaleSnapshot.digikala_fee_unit and verified Digikala
AccountEntry.delta may be adjusted. No sales, stock, cost or price changes.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.digikala_five_pack_v155 import START, END, applies_to
from core.finance import digikala_fee_for_unit
from core.models import AccountEntry, SaleLine


def _get_snapshot(line):
    try:
        return line.snapshot
    except Exception:
        return None


@transaction.atomic
def reconcile(*, apply=False, verify=False):
    # Lock SaleLines to avoid racing with an order re-import/edit.
    lines = (
        SaleLine.objects.select_for_update()
        .filter(day__date__range=(START, END), quantity__gt=0)
        .select_related("day", "product_size__product__brand", "product_size__size", "snapshot")
        .order_by("day__date", "id")
    )
    result = {
        "matching_lines": 0, "matching_packs": 0,
        "snapshot_updates": 0, "ledger_updates": 0,
        "missing_snapshot": 0, "missing_ledger": 0,
        "previous_fee_total": 0, "target_fee_total": 0,
    }
    updates = []
    for line in lines:
        snap = _get_snapshot(line)
        pack_qty = int((snap.pack_qty if snap else 0) or line.product_size.product.pack_qty or 0)
        if not applies_to(line.day.date, pack_qty):
            continue
        qty = int(line.quantity)
        price = int(line.sale_price or 0)
        if price <= 0:
            raise CommandError(f"SaleLine {line.pk} has zero price; no changes applied")
        brand = line.product_size.product.brand.name
        code = line.product_size.product.code
        target_fee = digikala_fee_for_unit(
            price, line.day.date, product_code=code, brand_name=brand,
            pack_qty=pack_qty,
        )
        previous_fee = int(
            (snap.digikala_fee_unit if snap else 0)
            or digikala_fee_for_unit(
                price, line.day.date, product_code=code, brand_name=brand,
            )
        )
        expected_old = (price - previous_fee) * qty
        expected_new = (price - target_fee) * qty
        entries = list(
            AccountEntry.objects.select_for_update().filter(
                reference=f"sale:{line.pk}:digikala",
            )
        )
        if len(entries) > 1:
            raise CommandError(f"SaleLine {line.pk}: duplicated ledger reference")
        entry = entries[0] if entries else None
        if entry is not None:
            if entry.account.key != "digikala" or entry.entry_type != "sale":
                raise CommandError(f"SaleLine {line.pk}: ledger entry has unexpected source/type")
            if int(entry.delta) not in {expected_old, expected_new}:
                raise CommandError(
                    f"SaleLine {line.pk}: current receivable {entry.delta} does not match "
                    f"stored {expected_old} or new {expected_new}; manual review required"
                )
        result["matching_lines"] += 1
        result["matching_packs"] += qty
        result["previous_fee_total"] += previous_fee * qty
        result["target_fee_total"] += target_fee * qty
        if snap is None:
            result["missing_snapshot"] += 1
        if entry is None:
            result["missing_ledger"] += 1
        if snap is not None and int(snap.digikala_fee_unit or 0) != target_fee:
            result["snapshot_updates"] += 1
        if entry is not None and int(entry.delta) != expected_new:
            result["ledger_updates"] += 1
        updates.append((snap, target_fee, entry, expected_new))

    if verify and (result["snapshot_updates"] or result["ledger_updates"]):
        raise CommandError(
            "Historical commission mismatch remains; run dry-run, then --apply if approved"
        )
    if apply:
        for snap, target_fee, entry, expected_new in updates:
            if snap is not None and int(snap.digikala_fee_unit or 0) != target_fee:
                snap.digikala_fee_unit = target_fee
                snap.save(update_fields=["digikala_fee_unit", "updated_at"])
            if entry is not None and int(entry.delta) != expected_new:
                entry.delta = expected_new
                entry.save(update_fields=["delta"])
    return result


class Command(BaseCommand):
    help = "V155: preview/explicitly reconcile ONLY existing five-pack Digikala fees 1405/09/05–07"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verify", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and options["verify"]:
            raise CommandError("--apply and --verify are mutually exclusive")
        result = reconcile(apply=options["apply"], verify=options["verify"])
        self.stdout.write(
            "V155_FIVEPACK_RECONCILIATION=" +
            ("APPLIED" if options["apply"] else "VERIFIED" if options["verify"] else "DRY_RUN")
        )
        for k, v in result.items():
            self.stdout.write(f"{k.upper()}={v}")
        self.stdout.write("V155_INVENTORY_SALES_PRICES_COGS_UNCHANGED=YES")
