"""V155: 19% Digikala commission for any five-piece pack sold 5–7 Azar 1405.

This rule affects only the commission percentage. Processing, VAT calculation,
prices, unit costs, inventory and other payment terms are unchanged.
"""
from datetime import date

START = date(2026, 11, 26)  # 1405/09/05, inclusive
END = date(2026, 11, 28)    # 1405/09/07, inclusive
COMMISSION_PERCENT = 19


def applies_to(sale_date, pack_qty):
    try:
        qty = int(pack_qty)
    except (ValueError, TypeError):
        return False
    return sale_date is not None and START <= sale_date <= END and qty == 5
