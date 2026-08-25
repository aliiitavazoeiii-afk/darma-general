from decimal import Decimal, ROUND_HALF_UP

from .finance import digikala_fee_for_unit
from .final_services import inventory_unit_cost, setting_decimal
from .models import InventoryModelCost, SaleSnapshot
from .takvin_pricing_v17 import takvin_cost_for


def _round(value):
    return int(Decimal(value or 0).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _color_cost(brand_id, color_id, size_id):
    value = InventoryModelCost.objects.filter(
        brand_id=brand_id, color_id=color_id, size_id=size_id
    ).values_list("unit_cost", flat=True).first()
    return int(value or 0) or int(setting_decimal("darma_accounting_unit_cost", 61000))


def darma_actual_unit_cost(line, ps):
    allocations = list(line.allocations.select_related("color").all())
    if allocations:
        total_qty = sum(max(0, int(row.qty or 0)) for row in allocations)
        if total_qty > 0:
            total_value = sum(
                max(0, int(row.qty or 0)) * _color_cost(ps.product.brand_id, row.color_id, ps.size_id)
                for row in allocations
            )
            return _round(Decimal(total_value) / Decimal(total_qty))

    composition = list(ps.product.composition.all())
    if composition:
        pack_qty = int(ps.product.pack_qty or 0)
        if pack_qty > 0:
            pack_value = sum(
                int(comp.qty or 0) * _color_cost(ps.product.brand_id, comp.color_id, ps.size_id)
                for comp in composition
            )
            return _round(Decimal(pack_value) / Decimal(pack_qty))

    return int(ps.unit_cost or 0) or int(setting_decimal("darma_accounting_unit_cost", 61000))


def snapshot_sale_line(line, ps=None, price=None):
    ps = ps or line.product_size
    price = int(line.sale_price if price is None else price)
    snap, _ = SaleSnapshot.objects.get_or_create(sale_line=line)
    snap.pack_qty = int(ps.product.pack_qty or 0)
    if ps.product.brand.name == "دارما":
        snap.unit_cost = darma_actual_unit_cost(line, ps)
    elif ps.product.brand.name == "تکوین":
        # The rule effective on the SALE DATE is frozen into the snapshot.
        # Changing a later rule never rewrites old reports.
        snap.unit_cost = takvin_cost_for(ps.size, line.day.date)
    elif ps.unit_cost:
        snap.unit_cost = int(ps.unit_cost)
    else:
        snap.unit_cost = int(inventory_unit_cost(ps.product.brand, ps.size))
    snap.digikala_fee_unit = digikala_fee_for_unit(price)
    snap.save()
    return snap
