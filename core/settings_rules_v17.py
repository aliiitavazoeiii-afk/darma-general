from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .dateutils import format_jalali, parse_jalali_date
from .models import AppSetting, TakvinCostRule
from .takvin_pricing_v17 import TAKVIN_SIZES, create_rule_set, current_takvin_costs


def _money(value):
    try:
        return int(str(value or "0").replace("٬", "").replace(",", "").replace(" ", ""))
    except Exception:
        return 0


@login_required
def settings_rules(request):
    settings = list(AppSetting.objects.all().order_by("id"))

    if request.method == "POST":
        action = request.POST.get("action", "base_settings")
        try:
            if action == "takvin_cost_rule":
                effective_from = parse_jalali_date(request.POST.get("effective_from") or "")
                prices = {size: _money(request.POST.get(f"takvin_{size}")) for size in TAKVIN_SIZES}
                create_rule_set(effective_from, prices)
                messages.success(
                    request,
                    f"قیمت‌های تکوین از تاریخ {format_jalali(effective_from)} ذخیره شد. فروش‌های قبل از این تاریخ تغییر نمی‌کنند.",
                )
            elif action == "takvin_delete_rule_set":
                effective_from = parse_jalali_date(request.POST.get("effective_from") or "")
                deleted, _ = TakvinCostRule.objects.filter(effective_from=effective_from).delete()
                if deleted:
                    messages.success(request, f"قیمت‌های تکوین از تاریخ {format_jalali(effective_from)} حذف شد.")
                else:
                    messages.info(request, "برای این تاریخ قانونی پیدا نشد.")
            else:
                for item in settings:
                    if f"setting_{item.id}" in request.POST:
                        item.value = (request.POST.get(f"setting_{item.id}") or "").strip()
                        item.save(update_fields=["value", "updated_at"])
                messages.success(request, "تنظیمات محاسباتی ذخیره شد.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("settings_rules")

    current = current_takvin_costs()
    grouped = {}
    for rule in TakvinCostRule.objects.select_related("size").order_by("-effective_from", "size__sort_order"):
        key = rule.effective_from
        grouped.setdefault(key, {"date": rule.effective_from, "jalali": format_jalali(rule.effective_from), "prices": {}})
        grouped[key]["prices"][rule.size.name] = int(rule.unit_cost)

    history = list(grouped.values())
    return render(
        request,
        "core/settings_rules_v17.html",
        {
            "settings": settings,
            "takvin_sizes": TAKVIN_SIZES,
            "takvin_current": current,
            "takvin_history": history,
        },
    )
