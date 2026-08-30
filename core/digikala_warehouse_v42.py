from urllib.parse import urlencode

from django.core.cache import cache
from django.utils import timezone

from .digikala_client_v40 import DigikalaAPIError, get_json


WAREHOUSE_CACHE_KEY = "digikala-v42-free-warehouse"
WAREHOUSE_CACHE_SECONDS = 60


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _data(response):
    if not isinstance(response, dict):
        return {}
    value = response.get("data")
    return value if isinstance(value, dict) else {}


def _extract_size(title):
    known = {
        "M", "L", "XL", "XXL", "3XL", "4XL",
        "36-38", "38-40", "40-42", "42-44", "44-46", "46-48",
    }
    for part in (title or "").split("|"):
        value = part.strip()
        if value in known:
            return value
    return "—"


def _paginated_items(path, *, size, max_pages):
    page = 1
    rows = []
    while True:
        separator = "&" if "?" in path else "?"
        response = get_json(f"{path}{separator}{urlencode({'page': page, 'size': size})}")
        data = _data(response)
        items = data.get("items")
        if isinstance(items, list):
            rows.extend(item for item in items if isinstance(item, dict))

        pager = data.get("pager") if isinstance(data.get("pager"), dict) else {}
        total_pages = max(_int(pager.get("total_pages")), 1)
        if page >= total_pages:
            break
        page += 1
        if page > max_pages:
            raise DigikalaAPIError("تعداد صفحات API دیجی‌کالا غیرمنتظره است؛ خواندن موجودی متوقف شد.")
    return rows


def _commitment_map():
    rows = _paginated_items(
        "/open-api/v1/commitments?sort=variant_id&order=asc",
        size=50,
        max_pages=20,
    )
    result = {}
    for row in rows:
        variant_id = _int(row.get("variantId"))
        if not variant_id:
            continue
        commitment = row.get("commitment")
        commitment = commitment if isinstance(commitment, dict) else {}
        result[variant_id] = _int(commitment.get("all"))
    return result


def _inventory_rows():
    return _paginated_items(
        "/open-api/v1/inventories",
        size=100,
        max_pages=30,
    )


def get_free_warehouse_board(*, force=False):
    """Return the seller's current free/sellable stock physically held by Digikala.

    This reproduces the live reconciliation tested against the seller account:

      sellable_dk_stock = available - marketplace_seller_stock + reserve
      requested_dk_reserve = reserve - seller_commitment
      reserved_from_current_dk_stock = min(sellable_dk_stock, requested_dk_reserve)
      free_dk_stock = sellable_dk_stock - reserved_from_current_dk_stock

    Calculations are per variant and clamped at zero. Return/dead stock is not counted
    as sellable stock. Nothing is persisted to the DARMA database.
    """
    if not force:
        cached = cache.get(WAREHOUSE_CACHE_KEY)
        if cached:
            return cached

    commitments = _commitment_map()
    inventories = _inventory_rows()

    rows = []
    sellable_total = 0
    reserved_total = 0
    free_total = 0
    reserve_over_stock_total = 0

    for item in inventories:
        variant_id = _int(item.get("product_variant_id"))
        if not variant_id:
            continue

        marketplace = _int(item.get("marketplace_seller_stock"))
        available = _int(item.get("available"))
        reserve = _int(item.get("reserve"))
        seller_commitment = commitments.get(variant_id, 0)

        sellable_stock = max(0, available - marketplace + reserve)
        requested_dk_reserve = max(0, reserve - seller_commitment)
        reserved_from_stock = min(sellable_stock, requested_dk_reserve)
        free_stock = max(0, sellable_stock - reserved_from_stock)
        reserve_over_stock = max(0, requested_dk_reserve - sellable_stock)

        if sellable_stock <= 0:
            continue

        title = str(item.get("title") or "—")
        row = {
            "variant_id": variant_id,
            "supplier_code": item.get("supplier_code") or "—",
            "title": title,
            "size": _extract_size(title),
            "product_image": item.get("img_src") or "",
            "product_link": item.get("product_url") or "",
            "sellable_stock": sellable_stock,
            "reserved_stock": reserved_from_stock,
            "free_stock": free_stock,
            "requested_dk_reserve": requested_dk_reserve,
            "reserve_over_stock": reserve_over_stock,
            "seller_commitment": seller_commitment,
            "raw_reserve": reserve,
            "warehouse_stock": _int(item.get("warehouse_stock")),
            "return_stock": _int(item.get("return_stock")),
            "status": "free" if free_stock > 0 else "zero",
        }
        rows.append(row)

        sellable_total += sellable_stock
        reserved_total += reserved_from_stock
        free_total += free_stock
        reserve_over_stock_total += reserve_over_stock

    rows.sort(
        key=lambda row: (
            0 if row["free_stock"] > 0 else 1,
            -row["free_stock"],
            -row["sellable_stock"],
            str(row["supplier_code"]),
            str(row["title"]),
        )
    )

    free_variant_count = sum(1 for row in rows if row["free_stock"] > 0)
    zero_variant_count = sum(1 for row in rows if row["free_stock"] == 0)

    board = {
        "rows": rows,
        "sellable_total": sellable_total,
        "reserved_total": reserved_total,
        "free_total": free_total,
        "variant_count": len(rows),
        "free_variant_count": free_variant_count,
        "zero_variant_count": zero_variant_count,
        "reserve_over_stock_total": reserve_over_stock_total,
        "inventory_rows_scanned": len(inventories),
        "commitment_variant_count": len(commitments),
        "updated_at": timezone.localtime().isoformat(),
    }
    cache.set(WAREHOUSE_CACHE_KEY, board, WAREHOUSE_CACHE_SECONDS)
    return board
