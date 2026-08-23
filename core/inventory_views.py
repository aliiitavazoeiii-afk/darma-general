from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Color


@login_required
@require_POST
def add_color_model(request):
    name = (request.POST.get("name") or "").strip()
    code = (request.POST.get("code") or "").strip()
    brand_id = (request.POST.get("brand") or "").strip()

    if not name:
        messages.error(request, "نام رنگ / مدل را وارد کن.")
    else:
        color, created = Color.objects.get_or_create(
            name=name,
            defaults={"code": code, "active": True},
        )
        if not created:
            changed = False
            if code and color.code != code:
                color.code = code
                changed = True
            if not color.active:
                color.active = True
                changed = True
            if changed:
                color.save(update_fields=["code", "active"])
            messages.info(request, "این رنگ / مدل از قبل وجود داشت و فعال شد.")
        else:
            messages.success(request, f"«{name}» اضافه شد و از همین حالا در موجودی نمایش داده می‌شود.")

    url = reverse("inventory")
    if brand_id:
        url += f"?brand={brand_id}"
    return redirect(url)
