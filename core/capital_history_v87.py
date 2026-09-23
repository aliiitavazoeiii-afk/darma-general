"""Dated, evidence-based capital snapshots; never synthesize historical balances.

This module ONLY observes the existing valuation/receivable helpers. It does not
modify sale, stock, payment, material or capital formulas.
"""
from datetime import date

from django.db.models import Sum
from django.utils import timezone

from .dia_gallery_v45 import dia_gallery_receivable_total
from .finance_excel_v9 import digikala_base_receivable, digikala_ledger_total
from .inventory_valuation_v17 import finished_inventory_value_v17
from .models import CapitalSnapshot, ExcelManualRow, ExcelManualSetting, RawMaterialStock, StockBalance
from .report_v5 import _raw_material_context
from .self_spend_v62 import is_self_tracking_row

CAPITAL_FIELDS = (
    "accounts_total", "finished_inventory_total", "materials_total",
    "inventory_total", "digikala_receivable", "dia_gallery_receivable",
    "takvin_debt", "assets_total", "capital_total",
)


def validate_capital_payload(data):
    """Reject incomplete or internally inconsistent snapshots before displaying them."""
    if not isinstance(data, dict) or any(k not in data for k in CAPITAL_FIELDS):
        raise ValueError("Incomplete capital snapshot.")
    values = {key: int(data[key]) for key in CAPITAL_FIELDS}
    if values["inventory_total"] != values["finished_inventory_total"] + values["materials_total"]:
        raise ValueError("Historical inventory total is inconsistent.")
    calculated = (
        values["accounts_total"] + values["inventory_total"]
        + values["digikala_receivable"] - values["takvin_debt"]
        + values["assets_total"]
    )
    if values["capital_total"] != calculated:
        raise ValueError("Historical capital does not match the established equation.")
    if "digikala_base" in data and "digikala_ledger" in data:
        if int(data["digikala_base"]) + int(data["digikala_ledger"]) != values["digikala_receivable"]:
            raise ValueError("Historical Digikala receivable ledger mismatch.")
    return data


def capture_current_capital_payload():
    """Read exactly the same live components used by report_v10 (no historical guesses)."""
    manual = list(
        ExcelManualRow.objects.filter(active=True).order_by("section", "sort_order", "id")
    )
    account_rows = [
        row for row in manual
        if row.section == ExcelManualRow.ACCOUNTS and not is_self_tracking_row(row)
    ]
    person_rows = [row for row in manual if row.section == ExcelManualRow.PERSONS]
    asset_rows = [row for row in manual if row.section == ExcelManualRow.ASSETS]

    dia = int(dia_gallery_receivable_total())
    accounts = (
        sum(int(row.amount or 0) for row in account_rows)
        + sum(int(row.amount or 0) for row in person_rows) + dia
    )
    assets = sum(int(row.amount or 0) for row in asset_rows)
    finished = int(finished_inventory_value_v17())
    raw = _raw_material_context()
    materials = int(raw["materials_total"])
    inventory = finished + materials
    digi_base = int(digikala_base_receivable())
    digi_ledger = int(digikala_ledger_total())
    digi = digi_base + digi_ledger
    debt_obj = ExcelManualSetting.objects.filter(key="takvin_debt").first()
    debt = int(debt_obj.value or 0) if debt_obj else 0

    # Precisely the existing report_v10 capital equation; never derive from sales alone.
    capital = accounts + inventory + digi - debt + assets
    rows = [
        {
            "section": row.section, "title": row.title, "amount": int(row.amount or 0),
            "note": row.note or "", "id": row.id,
            "included_in_capital": not is_self_tracking_row(row),
        }
        for row in manual if row.section in {
            ExcelManualRow.ACCOUNTS, ExcelManualRow.PERSONS, ExcelManualRow.ASSETS
        }
    ]
    stocks = [
        {
            "brand": row.brand.name, "color": row.color.name,
            "size": row.size.name, "location": row.location.title,
            "qty": int(row.qty or 0),
            "included_in_capital": row.brand.name != "انبارش",
        }
        for row in StockBalance.objects.select_related(
            "brand", "color", "size", "location"
        ).order_by("brand_id", "color_id", "size_id", "location_id")
    ]
    raw_rows = [
        {
            "kind": row.kind, "location": row.location,
            "title": row.title, "material_key": row.material_key,
            "variant": row.variant, "quantity": str(row.quantity or 0),
            "unit_price": int(row.unit_price or 0),
            "value": int(row.total_value or 0), "note": row.note or "", "id": row.id,
        }
        for row in RawMaterialStock.objects.filter(active=True).order_by(
            "kind", "location", "id"
        )
    ]
    payload = {
        "accounts_total": accounts,
        "finished_inventory_total": finished,
        "materials_total": materials,
        "inventory_total": inventory,
        "digikala_receivable": digi,
        "dia_gallery_receivable": dia,
        "takvin_debt": debt,
        "assets_total": assets,
        "capital_total": capital,
        "digikala_base": digi_base,
        "digikala_ledger": digi_ledger,
        "account_rows": rows,
        "stock_rows": stocks,
        "material_rows": raw_rows,
        "captured_at": timezone.localtime().isoformat(),
    }
    return validate_capital_payload(payload)


def period_capital(end_date: date, live_payload=None):
    """Exact end-date snapshot, current live state, or explicit unavailable status.

    The nearest earlier snapshot is NOT a substitute for the requested end date.
    """
    today = timezone.localdate()
    if end_date >= today:
        return {
            "available": True, "status": "live", "date": today,
            "data": validate_capital_payload(live_payload or capture_current_capital_payload()),
            "captured_at": timezone.localtime(), "source": "live",
        }
    snapshot = CapitalSnapshot.objects.filter(date=end_date).first()
    if snapshot is None:
        return {
            "available": False, "status": "missing", "date": end_date,
            "data": None, "captured_at": None, "source": None,
        }
    try:
        data = validate_capital_payload(snapshot.data)
    except (TypeError, ValueError, KeyError):
        return {
            "available": False, "status": "invalid", "date": end_date,
            "data": None, "captured_at": None, "source": snapshot.source,
        }
    return {
        "available": True, "status": "snapshot", "date": end_date,
        "data": data, "captured_at": snapshot.captured_at,
        "source": snapshot.source,
    }
