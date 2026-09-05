from datetime import date

from .models import AppSetting


DEFAULT_DARMA_UNIT_COST = 61_000
RULE_PREFIX = "darma_cost_rule_"
LEGACY_FALLBACK_KEY = "darma_accounting_unit_cost"


def _clean_int(value, default=0):
    try:
        return max(0, int(str(value if value not in (None, "") else default).replace("٬", "").replace(",", "").replace(" ", "")))
    except (TypeError, ValueError):
        return int(default or 0)


def _rule_key(effective_from):
    return f"{RULE_PREFIX}{effective_from.isoformat()}"


def _parse_rule_date(key):
    if not str(key).startswith(RULE_PREFIX):
        return None
    try:
        return date.fromisoformat(str(key)[len(RULE_PREFIX):])
    except (TypeError, ValueError):
        return None


def list_darma_cost_rules():
    rows = []
    for obj in AppSetting.objects.filter(key__startswith=RULE_PREFIX).order_by("key"):
        effective_from = _parse_rule_date(obj.key)
        unit_cost = _clean_int(obj.value)
        if effective_from and unit_cost > 0:
            rows.append({
                "id": obj.id,
                "key": obj.key,
                "effective_from": effective_from,
                "unit_cost": unit_cost,
            })
    rows.sort(key=lambda row: (row["effective_from"], row["id"]), reverse=True)
    return rows


def darma_cost_for(on_date=None):
    """Canonical accounting cost for one Darma short on a given date.

    Date-effective rules are the single source of truth for Darma COGS. Existing
    SaleSnapshot rows stay frozen; this function is used when a new snapshot is
    created and for current finished-inventory valuation.
    """
    on_date = on_date or date.today()
    best = None
    for row in list_darma_cost_rules():
        if row["effective_from"] <= on_date:
            if best is None or row["effective_from"] > best["effective_from"]:
                best = row
    if best:
        return int(best["unit_cost"])

    legacy = AppSetting.objects.filter(key=LEGACY_FALLBACK_KEY).values_list("value", flat=True).first()
    return _clean_int(legacy, DEFAULT_DARMA_UNIT_COST) or DEFAULT_DARMA_UNIT_COST


def set_darma_cost_rule(effective_from, unit_cost):
    if not isinstance(effective_from, date):
        raise ValueError("تاریخ شروع بهای تمام‌شده دارما معتبر نیست.")
    unit_cost = _clean_int(unit_cost)
    if unit_cost <= 0:
        raise ValueError("بهای تمام‌شده هر شورت دارما باید بیشتر از صفر باشد.")
    obj, _ = AppSetting.objects.update_or_create(
        key=_rule_key(effective_from),
        defaults={
            "value": str(unit_cost),
            "label": f"بهای تمام‌شده دارما از {effective_from.isoformat()}",
        },
    )
    return obj


def delete_darma_cost_rule(effective_from):
    return AppSetting.objects.filter(key=_rule_key(effective_from)).delete()[0]


def ensure_darma_cost_baseline():
    """Seed the user's confirmed historical/current baseline without overwriting it."""
    baseline = date(2021, 3, 21)  # 1400/01/01
    key = _rule_key(baseline)
    obj = AppSetting.objects.filter(key=key).first()
    if obj is None:
        return set_darma_cost_rule(baseline, DEFAULT_DARMA_UNIT_COST)
    return obj
