"""Bidirectional physical Darma HOME <-> KHORSHID transfers, without page reload."""
from django.contrib import messages
from functools import wraps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.views.csrf import csrf_failure as default_csrf_failure
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .brand_colors import colors_for_brand
from .final_services import sync_stock_transfer
from .inventory_operations_v15 import _date, _stock_snapshot_for_operations
from .models import Brand, Size, StockBalance, StockLocation, StockTransfer

def _ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def csrf_failure(request, reason=""):
    """Preserve normal Django CSRF HTML errors, but return JSON to transfer AJAX."""
    if (
        request.method == "POST"
        and request.path in (
            "/inventory/operations/transfer-direction/",
            "/inventory/operations/",
        )
        and _ajax(request)
    ):
        return JsonResponse({
            "ok": False, "code": "csrf_failed",
            "message": "اعتبار امنیتی صفحه منقضی شده است؛ صفحه را تازه‌سازی و دوباره وارد شو.",
        }, status=403)
    return default_csrf_failure(request, reason=reason)


def transfer_ajax_auth(view):
    """Prevent login_required from redirecting AJAX POST to an HTML login page."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated and _ajax(request):
            return JsonResponse({
                "ok": False, "code": "authentication_required",
                "message": "نشست ورود منقضی شده است؛ دوباره وارد حساب شو.",
            }, status=401)
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        return view(request, *args, **kwargs)
    return wrapped


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
def transfer(*, when, brand, size, direction, quantities):
    if brand.name != "دارما":
        raise ValueError("این انتقال فقط برای برند دارما است.")
    if direction not in DIRECTIONS:
        raise ValueError("جهت انتقال مشخص یا معتبر نیست.")
    from_key, to_key = DIRECTIONS[direction]
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
            from_location=source, to_location=target, note="",
        )
        sync_stock_transfer(obj)
        transferred.append(obj.pk)
    return {"count": len(transferred), "total": sum(q for _, q in quantities), "ids": transferred}


@transfer_ajax_auth
@login_required
@require_POST
def inventory_transfer_direction(request):
    ajax = _ajax(request)
    try:
        brand = Brand.objects.get(pk=request.POST.get("brand"), active=True, name="دارما")
        size = Size.objects.get(pk=request.POST.get("size"))
        direction = str(request.POST.get("direction") or "warehouse_to_home")
        colors = _positive_quantities(request.POST, brand)
        # The transfer and its response snapshot must succeed or fail together.
        # An old response-snapshot failure could report an error AFTER stock moved,
        # inviting the operator to accidentally post the same movement again.
        with transaction.atomic():
            result = transfer(
                when=_date(request.POST.get("date")), brand=brand, size=size,
                direction=direction, quantities=colors,
            )
            source_label, destination_label = (
                ("خانه", "انبار") if direction == "home_to_warehouse" else ("انبار", "خانه")
            )
            message = (
                f"انتقال {source_label} به {destination_label} ثبت شد: "
                f"{result['total']} عدد از {result['count']} رنگ."
            )
            if ajax:
                brands = Brand.objects.filter(active=True, name__in=["دارما", "تکوین", "Novani"])
                snapshot = _stock_snapshot_for_operations(brands)
                # Serialize the entire response before committing the stock move.
                response = JsonResponse({
                    "ok": True, "message": message,
                    "stock_snapshot": snapshot, "transfer_ids": result["ids"],
                })
                response["Cache-Control"] = "no-store"
                return response
        messages.success(request, message)
    except Exception as exc:
        if ajax:
            response = JsonResponse({
                "ok": False, "code": "transfer_failed", "message": str(exc),
            }, status=400)
            response["Cache-Control"] = "no-store"
            return response
        messages.error(request, str(exc))
    return redirect("inventory_operations")
