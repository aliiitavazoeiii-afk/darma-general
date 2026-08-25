from django.db.models import Sum

from .models import InventoryModelCost, StockBalance
from .takvin_pricing_v17 import takvin_cost_for


def finished_inventory_value_v17():
    """Current finished-goods value, using today's Takvin rule and stored model costs elsewhere."""
    cost_map = {
        (row.brand_id, row.color_id, row.size_id): int(row.unit_cost or 0)
        for row in InventoryModelCost.objects.all()
    }
    total = 0
    rows = (
        StockBalance.objects.values(
            "brand_id", "brand__name", "color_id", "size_id", "size__name"
        ).annotate(qty=Sum("qty"))
    )
    for row in rows:
        qty = int(row["qty"] or 0)
        if row["brand__name"] == "تکوین":
            unit_cost = takvin_cost_for(row["size__name"])
        else:
            unit_cost = cost_map.get((row["brand_id"], row["color_id"], row["size_id"]), 0)
        total += qty * int(unit_cost or 0)
    return total
