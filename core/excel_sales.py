from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .finance import digikala_fee_for_unit
from .finance_excel_v9 import sync_sale_receivable
from .final_services import inventory_unit_cost, setting_decimal, sync_sale_inventory
from .models import Color, ProductSize, SaleDay, SaleLine, SaleShortage, SaleSnapshot


def _int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(str(value).replace(" ", "").replace(",", "").replace("٬", "").strip())
    except (TypeError, ValueError):
        return default


@login_required
@require_POST
@transaction.atomic
def sale_line_save(request):
    day = get_object_or_404(SaleDay, id=request.POST.get("day_id"))
    ps = get_object_or_404(
        ProductSize.objects.select_related("product__brand", "size"),
        id=request.POST.get("product_size_id"),
    )
    if ps.product.brand.name == "تکوین" and ps.size.name in ("3XL", "4XL"):
        return HttpResponse("این سایز برای تکوین فعال نیست.", status=400)

    qty = max(0, _int(request.POST.get("quantity")))
    price = max(0, _int(request.POST.get("sale_price"), ps.default_sale_price))
    line, _ = SaleLine.objects.select_for_update().get_or_create(
        day=day,
        product_size=ps,
        defaults={"quantity": 0, "sale_price": price},
    )
    line.quantity = qty
    line.sale_price = price
    line.save(update_fields=["quantity", "sale_price"])

    # Snapshot keeps old daily reports stable even if master prices change later.
    snap, _ = SaleSnapshot.objects.get_or_create(sale_line=line)
    snap.pack_qty = int(ps.product.pack_qty or 0)
    if ps.unit_cost:
        snap.unit_cost = int(ps.unit_cost)
    elif ps.product.brand.name == "دارما":
        snap.unit_cost = int(setting_decimal("darma_accounting_unit_cost", 61000))
    else:
        snap.unit_cost = int(inventory_unit_cost(ps.product.brand, ps.size))
    snap.digikala_fee_unit = digikala_fee_for_unit(price)
    snap.save()

    result = sync_sale_inventory(line)
    sync_sale_receivable(line)
    pending = list(line.shortages.filter(resolved=False).select_related("source_color"))
    return render(
        request,
        "core/_sale_saved_final.html",
        {
            "line": line,
            "pending": pending,
            "colors": Color.objects.filter(active=True),
            "result": result,
        },
    )


@login_required
@require_POST
@transaction.atomic
def shortage_resolve(request, shortage_id):
    shortage = get_object_or_404(
        SaleShortage.objects.select_for_update().select_related("sale_line"),
        id=shortage_id,
    )
    choice = request.POST.get("target_color")
    keep_negative = choice == "none"
    target = None
    if choice and choice != "none":
        target = get_object_or_404(Color, id=choice)

    shortage.resolved = True
    shortage.target_color = None if keep_negative else target
    shortage.save(update_fields=["resolved", "target_color"])
    line = shortage.sale_line
    result = sync_sale_inventory(line)
    sync_sale_receivable(line)
    pending = list(line.shortages.filter(resolved=False).select_related("source_color"))
    return render(
        request,
        "core/_sale_saved_final.html",
        {
            "line": line,
            "pending": pending,
            "colors": Color.objects.filter(active=True),
            "result": result,
        },
    )
