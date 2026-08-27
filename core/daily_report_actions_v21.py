from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .cost_accounting_v14 import snapshot_sale_line
from .finance import digikala_fee_for_unit
from .finance_excel_v9 import sync_sale_receivable
from .models import SaleLine
from .sale_inventory_v19 import sync_sale_inventory_v19


def _money(value):
    try:
        return int(str(value or "0").replace("٬", "").replace(",", "").replace(" ", ""))
    except (TypeError, ValueError):
        return 0


def _report_redirect(line):
    return redirect("daily_report", day_id=line.day_id)


@login_required
@require_POST
@transaction.atomic
def sale_price_update(request, line_id):
    line = get_object_or_404(
        SaleLine.objects.select_for_update().select_related(
            "day", "product_size__product__brand", "product_size__size"
        ),
        id=line_id,
    )
    price = _money(request.POST.get("sale_price"))
    if price <= 0:
        messages.error(request, "قیمت فروش باید بیشتر از صفر باشد.")
        return _report_redirect(line)

    old_price = int(line.sale_price or 0)
    if old_price == price:
        messages.info(request, "قیمت تغییری نکرد.")
        return _report_redirect(line)

    line.sale_price = price
    line.save(update_fields=["sale_price"])

    # Editing a selling price must NOT rewrite historical COGS. Preserve the
    # frozen snapshot cost/pack quantity and only refresh the fee component.
    try:
        snap = line.snapshot
    except Exception:
        snap = None
    if snap is None:
        snapshot_sale_line(line, line.product_size, price)
    else:
        snap.digikala_fee_unit = digikala_fee_for_unit(price)
        snap.save(update_fields=["digikala_fee_unit", "updated_at"])

    sync_sale_receivable(line)
    messages.success(
        request,
        f"قیمت {line.product_size.product.code} / {line.product_size.size.name} از {old_price:,} به {price:,} اصلاح شد.",
    )
    return _report_redirect(line)


@login_required
@require_POST
@transaction.atomic
def sale_line_delete(request, line_id):
    line = get_object_or_404(
        SaleLine.objects.select_for_update().select_related(
            "day", "product_size__product__brand", "product_size__size"
        ),
        id=line_id,
    )
    day_id = line.day_id
    label = f"{line.product_size.product.code} / {line.product_size.size.name}"

    # Quantity zero is the supported inventory-reversal path. It restores all
    # allocations first; only after finance is cleared is the SaleLine deleted.
    line.quantity = 0
    line.save(update_fields=["quantity"])
    sync_sale_inventory_v19(line)
    sync_sale_receivable(line)
    line.delete()

    messages.success(request, f"فروش {label} حذف شد و اثر موجودی و طلب دیجی آن برگشت.")
    return redirect("daily_report", day_id=day_id)
