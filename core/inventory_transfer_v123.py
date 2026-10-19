"""Bidirectional physical Darma HOME <-> KHORSHID transfers, without page reload."""
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
import uuid

from .brand_colors import colors_for_brand
from .final_services import sync_stock_transfer
from .inventory_operations_v15 import _date, _stock_snapshot_for_operations
from .models import Brand, Size, StockBalance, StockLocation, StockTransfer

TRANSFER_TOKEN_PREFIX = "web-transfer:v125:"

def _transfer_token(value):
    if not value:
        return ""
    try:
        return TRANSFER_TOKEN_PREFIX + str(uuid.UUID(str(value).strip()))
    except (ValueError, AttributeError) as exc:
        raise ValueError("شناسه انتقال معتبر نیست؛ صفحه را تازه‌سازی کن.") from exc


def _existing_transfer_status(token_note):
    if not token_note:
        return None
    rows = list(
        StockTransfer.objects.filter(note=token_note)
        .select_related("from_location", "to_location")
        .order_by("id")
    )
    if not rows:
        return None
    return {
        "found": True,
        "transfer_ids": [x.pk for x in rows],
        "total": sum(int(x.qty or 0) for x in rows),
        "count": len(rows),
        "applied": all(x.applied for x in rows),
    }


DIRECTIONS = {
    "warehouse_to_home": (StockLocation.KHORSHID, StockLocation.HOME),
    "home_to_warehouse": (StockLocation.HOME, StockLocation.KHORSHID),
}


def _positive_quantities(post, brand):
    color_quantities = []
    for color in colors_for_brand(brand):
        raw = str(post.get(f"qty_{color.pk}") or "").strip().translate(
            str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        ).replace(",", "").replace("٬", "")
        if not raw:
            continue
        if not raw.isdecimal():
            raise ValueError(f"تعداد رنگ {color.name} باید عدد صحیح غیرمنفی باشد.")
        qty = int(raw)
        if qty:
            color_quantities.append((color, qty))
    if not color_quantities:
        raise ValueError("حداقل برای یک رنگ تعداد انتقال وارد کن.")
    return color_quantities


@transaction.atomic
def transfer(*, when, brand, size, direction, quantities, request_token=""):
    if brand.name != "دارما":
        raise ValueError("این انتقال فقط برای برند دارما است.")
    if direction not in DIRECTIONS:
        raise ValueError("جهت انتقال مشخص یا معتبر نیست.")
    from_key, to_key = DIRECTIONS[direction]
    token_note = _transfer_token(request_token)
    if token_note:
        # Serialize two submissions carrying the same token without a DB
        # migration; only this endpoint uses the brand lock. A retransmitted
        # HTTP POST can never create a second stock transfer.
        Brand.objects.select_for_update().get(pk=brand.pk)
        previous = list(
            StockTransfer.objects.select_for_update()
            .filter(note=token_note)
            .select_related("from_location", "to_location").order_by("color_id", "id")
        )
        if previous:
            expected = sorted((int(c.pk), int(q)) for c, q in quantities)
            actual = sorted((int(x.color_id), int(x.qty)) for x in previous)
            if (
                actual != expected
                or any(
                    x.date != when or x.brand_id != brand.pk or x.size_id != size.pk
                    or x.from_location.key != from_key or x.to_location.key != to_key
                    or not x.applied
                    for x in previous
                )
            ):
                raise ValueError("این شناسه قبلاً برای انتقال متفاوتی ثبت شده است؛ وضعیت انتقال را بررسی کن.")
            return {
                "count": len(previous), "total": sum(x.qty for x in previous),
                "ids": [x.pk for x in previous], "replayed": True,
            }
    source = StockLocation.objects.get(key=from_key)
    target = StockLocation.objects.get(key=to_key)
    if source.pk == target.pk:
        raise ValueError("مبدأ و مقصد نمی‌توانند یکسان باشند.")
    # Lock all SOURCE rows first, then verify the whole batch. No partial
    # transfers on shortage, and no negative physical source is permitted.
    for color, qty in sorted(quantities, key=lambda x: x[0].pk):
        StockBalance.objects.get_or_create(
            brand=brand, color=color, size=size, location=source, defaults={"qty": 0}
        )
        stock = StockBalance.objects.select_for_update().get(
            brand=brand, color=color, size=size, location=source
        )
        if int(stock.qty or 0) < qty:
            raise ValueError(
                f"موجودی مبدأ برای {color.name} سایز {size.name} کافی نیست؛ "
                f"موجود {int(stock.qty or 0)}، درخواستی {qty}."
            )
    transferred = []
    for color, qty in sorted(quantities, key=lambda x: x[0].pk):
        obj = StockTransfer.objects.create(
            date=when, brand=brand, size=size, color=color, qty=qty,
            from_location=source, to_location=target, note=token_note,
        )
        sync_stock_transfer(obj)
        transferred.append(obj.pk)
    return {"count": len(transferred), "total": sum(q for _, q in quantities), "ids": transferred, "replayed": False}


@require_http_methods(["GET", "POST"])
def inventory_transfer_direction(request):
    # AJAX must never receive a login-page HTML redirect. For ordinary
    # browser form posts, preserve the familiar login redirect.
    ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )
    if not request.user.is_authenticated:
        if ajax:
            return JsonResponse(
                {"ok": False, "code": "auth_required",
                 "message": "نشست کاربری تمام شده؛ دوباره وارد سایت شو. هیچ انتقالی توسط این درخواست ثبت نشد."},
                status=401
            )
        return redirect_to_login(request.get_full_path())

    if request.method == "GET":
        try:
            token_note = _transfer_token(request.GET.get("request_token"))
            result = _existing_transfer_status(token_note)
            return JsonResponse({
                "ok": True, "version": "v125", "found": bool(result),
                "result": result,
                "stock_snapshot": _stock_snapshot_for_operations(
                    Brand.objects.filter(active=True, name__in=["دارما", "تکوین", "Novani"])
                ) if result else None,
            })
        except ValueError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)

    try:
        brand = Brand.objects.get(pk=request.POST.get("brand"), active=True, name="دارما")
        size = Size.objects.get(pk=request.POST.get("size"))
        direction = str(request.POST.get("direction") or "warehouse_to_home")
        colors = _positive_quantities(request.POST, brand)
        result = transfer(
            when=_date(request.POST.get("date")), brand=brand, size=size,
            direction=direction, quantities=colors,
            request_token=request.POST.get("request_token") or "",
        )
        source_label, destination_label = (
            ("خانه", "انبار") if direction == "home_to_warehouse" else ("انبار", "خانه")
        )
        message = (
            f"انتقال {source_label} به {destination_label} ثبت شد: "
            f"{result['total']} عدد از {result['count']} رنگ."
        )
        if result.get("replayed"):
            message = "این انتقال قبلاً ثبت شده بود؛ دوباره از موجودی کسر نشد. " + message
        if ajax:
            response = {
                "ok": True, "version": "v125", "message": message,
                "transfer_ids": result["ids"], "replayed": result["replayed"],
            }
            # Never turn an already committed transfer into an apparent
            # error if the read-only stock snapshot unexpectedly fails.
            try:
                response["stock_snapshot"] = _stock_snapshot_for_operations(
                    Brand.objects.filter(active=True, name__in=["دارما", "تکوین", "Novani"])
                )
            except Exception:
                response["stock_snapshot"] = None
                response["refresh_needed"] = True
            return JsonResponse(response)
        messages.success(request, message)
    except Exception as exc:
        if ajax:
            return JsonResponse({
                "ok": False, "version": "v125", "code": "transfer_error",
                "message": str(exc),
            }, status=400)
        messages.error(request, str(exc))
    return redirect("inventory_operations")
