"""V151 strictly scoped Digikala offer for a NEW Darma single-piece stripe SKU.

Product title is authoritative, NOT seller code. Persian navy (سرمه ای)
maps to the legacy unqualified stripe stock color (راه راه); other
title colors map to distinct existing/created stripe-colored inventory.
"""
from datetime import date

PRODUCT_CODE = "rahrah-01"
PRODUCT_TITLE = "راه راه 01"
BRAND_NAME = "دارما"
PACK_QTY = 1
SALE_PRICE = 139_000
UNIT_COST = 67_000  # User-provided production cost for this product

STOCK_COLOR_NAMES = ("راه راه", "راه راه قرمز", "راه راه طوسی", "راه راه مشکی")
TITLE_COLOR_ALIASES = {
    "سرمه ای": "راه راه",
    "سرمه‌ای": "راه راه",
    "قرمز": "راه راه قرمز",
    "طوسی": "راه راه طوسی",
    "مشکی": "راه راه مشکی",
}
OFFER_START = date(2026, 11, 22)  # 1405/09/01 (inclusive)
OFFER_END = date(2026, 12, 1)     # 1405/09/10 (inclusive)
COMMISSION_PERCENT = 13


def applies_to(when, brand_name, product_code):
    return (
        when is not None
        and OFFER_START <= when <= OFFER_END
        and str(brand_name or "") == BRAND_NAME
        and str(product_code or "") == PRODUCT_CODE
    )


# V153: separate price/COGS window. The 13% commission remains governed
# by the already-approved 1–10 Azar V151 rule above, without changing it.
PROFIT_START = date(2026, 11, 26)  # 1405/09/05 (inclusive)
PROFIT_END = date(2026, 12, 1)     # 1405/09/10 (inclusive)
PROFIT_SALE_PRICE = 162_500
PROFIT_UNIT_COST = 76_000


def profit_rule_applies(when, brand_name, product_code):
    return (
        when is not None
        and PROFIT_START <= when <= PROFIT_END
        and str(brand_name or "") == BRAND_NAME
        and str(product_code or "") == PRODUCT_CODE
    )


def promotional_sale_price(when, brand_name, product_code):
    """Return the dated offer price or None; do not change the catalog baseline."""
    if profit_rule_applies(when, brand_name, product_code):
        return PROFIT_SALE_PRICE
    return None


def stripe01_unit_cost_for(when, brand_name, product_code, baseline_cost):
    """Keep the user-confirmed 76k COGS on Azar 5–10 only."""
    if profit_rule_applies(when, brand_name, product_code):
        return PROFIT_UNIT_COST
    return int(baseline_cost)
