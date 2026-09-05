from .darma_cost_v55 import darma_cost_for
from .finance import digikala_fee_for_unit
from .final_services import inventory_unit_cost
from .models import SaleSnapshot
from .takvin_pricing_v17 import takvin_cost_for


def darma_actual_unit_cost(line, ps=None, stock_brand_id=None):
    """Compatibility wrapper for the canonical date-effective Darma cost.

    V55 intentionally ignores color/size InventoryModelCost for Darma accounting.
    Historical SaleSnapshot rows remain frozen; only new/rebuilt snapshots call
    this function and receive the rule effective on the sale date.
    """
    return int(darma_cost_for(line.day.date))


def snapshot_sale_line(line, ps=None, price=None):
    ps = ps or line.product_size
    price = int(line.sale_price if price is None else price)
    snap, _ = SaleSnapshot.objects.get_or_create(sale_line=line)
    snap.pack_qty = int(ps.product.pack_qty or 0)
    brand_name = ps.product.brand.name
    if brand_name in {"دارما", "انبارش"}:
        # Darma and Anbaresh (a Darma-backed sales channel) share one canonical
        # per-short accounting cost, frozen by the sale date.
        snap.unit_cost = int(darma_cost_for(line.day.date))
    elif brand_name == "تکوین":
        # The rule effective on the SALE DATE is frozen into the snapshot.
        snap.unit_cost = takvin_cost_for(ps.size, line.day.date)
    elif ps.unit_cost:
        snap.unit_cost = int(ps.unit_cost)
    else:
        snap.unit_cost = int(inventory_unit_cost(ps.product.brand, ps.size))
    snap.digikala_fee_unit = digikala_fee_for_unit(price)
    snap.save()
    return snap
