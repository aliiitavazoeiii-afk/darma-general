from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from . import material_report_v20 as v20
from .models import InventoryMovement, MaterialReportBlock, MaterialReportOutputApplied


def _apply_output_delta(block):
    """
    Darma keeps the existing production behavior.
    Novani output is intentionally isolated: only Novani finished inventory + its
    production ledger are changed. No Darma stock/cost and no tailor balance are touched.
    """
    v20._validate_output_floor(block)
    total_delta = 0
    details = []
    sizes = v20._output_sizes_for_block(block)

    for model_key, _label in v20.OUTPUT_MODELS:
        for size_key, _size in sizes:
            target = v20._target_qty(block, model_key, size_key)
            applied, _ = MaterialReportOutputApplied.objects.select_for_update().get_or_create(
                block=block,
                model_key=model_key,
                size_key=size_key,
                defaults={"quantity": 0},
            )
            done = int(applied.quantity or 0)
            delta = target - done
            if delta <= 0:
                continue

            brand, color, size, destination, _destination_label, label, size_name = v20._production_objects(
                block, model_key, size_key
            )
            if brand.name == "دارما":
                v20._sync_finished_stock_costed(
                    v20._sparse_output(model_key, size_key, delta),
                    block.input_data or {},
                    +1,
                )
            elif brand.name == "Novani":
                v20._apply_novani_stock(brand, color, size, destination, delta)
            else:
                raise ValueError("برند صورت مواد معتبر نیست.")

            InventoryMovement.objects.create(
                movement_type=InventoryMovement.PRODUCTION,
                brand=brand,
                color=color,
                size=size,
                location=destination,
                delta=delta,
                reference=f"material-report:{block.id}:output-v21",
            )
            applied.quantity = target
            applied.save(update_fields=["quantity", "updated_at"])
            total_delta += delta
            details.append(f"{label}/{size_name}: +{delta}")

    if total_delta and block.brand.name == "دارما":
        wage_delta = v20._wage_for_pieces(total_delta, v20._dozen_wage())
        v20._adjust_tailor_balance(-wage_delta)
    else:
        # Novani output changes nothing except Novani finished inventory/ledger.
        wage_delta = 0

    return total_delta, wage_delta, details


@login_required
@require_POST
def material_block_apply_output(request, block_id):
    try:
        with transaction.atomic():
            block = MaterialReportBlock.objects.select_for_update().select_related("brand").get(id=block_id)
            v20._save_block_data(block, request)
            v20._validate_output_floor(block)
            delta, wage, details = _apply_output_delta(block)
            destination_label = v20._destination_for_brand(block.brand)[1]
        if delta:
            if block.brand.name == "Novani":
                messages.success(
                    request,
                    f"{delta} شورت فقط به {destination_label} اضافه شد. هیچ موجودی دارما و هیچ حساب دیگری تغییر نکرد. "
                    + " | ".join(details),
                )
            else:
                messages.success(
                    request,
                    f"فقط تحویل جدید اعمال شد: {delta} شورت به {destination_label} اضافه شد و مزد همین {delta} عدد "
                    f"({wage:,} تومان) اعمال شد. " + " | ".join(details),
                )
        else:
            messages.info(request, "هیچ تحویل جدیدی برای اعمال وجود نداشت؛ موجودی تغییر نکرد.")
    except MaterialReportBlock.DoesNotExist:
        messages.error(request, "صورت پیدا نشد.")
    except Exception as exc:
        messages.error(request, f"اعمال تحویل انجام نشد و کل عملیات برگشت: {exc}")
    return redirect(f"/material-report/#block-{block_id}")
