from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction

from .cost_accounting_v14 import snapshot_sale_line
from .daily_order_import_v8 import (
    DailyOrderImportError,
    _compact_code,
    _resolve_product,
    _resolve_size,
    parse_delivery_report,
)
from .final_services import sync_sale_inventory
from .models import AccountEntry, ProductCode, ProductSize, SaleDay, SaleLine, StockBalance
from .variant_sale_v12 import (
    VARIANT_PRODUCT_CODE,
    assert_stock_invariant,
    resolve_variant_color,
    sold_units_by_brand,
    sync_variant_inventory,
)


IMPORT_BRANDS = ("دارما", "تکوین")


@dataclass(frozen=True)
class ResolvedOrderRowV12:
    source_row: int
    brand_name: str
    product_code: str
    size_name: str
    quantity: int
    color_name: str = ""


def _model_candidate(title: str) -> str:
    text = str(title or "")
    match = re.search(r"مدل\s+(.+?)(?:\s+مجموعه|\s*\|)", text, re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).strip()
    value = re.sub(r"^نخی\s+", "", value, flags=re.IGNORECASE)
    return value


def _product_maps_v19():
    """Digikala XLSX is intentionally limited to real marketplace brands.

    Anbaresh mirrors Darma codes for MANUAL daily entry, so including it here
    would make duplicate Darma codes ambiguous. Novani is inventory/production
    only and also must never be selected by the Digikala importer.
    """
    products = list(
        ProductCode.objects.select_related("brand").filter(
            active=True,
            brand__name__in=IMPORT_BRANDS,
        )
    )
    by_key = defaultdict(list)
    for product in products:
        by_key[_compact_code(product.code)].append(product)
    return by_key


def _resolve_product_v12(seller_code, title, by_key):
    """Resolve the marketplace product with the explicit title model first.

    Digikala seller-code metadata is not always trustworthy. A real export was
    observed with seller_code=rah220 while the title explicitly said D-220.
    Using seller code first incorrectly sold rah-220 / 4XL. When the title has
    a resolvable model, it is therefore authoritative; seller code is fallback.
    """
    candidate = _model_candidate(title)
    if candidate.lower() == VARIANT_PRODUCT_CODE and "دارما" in str(title or ""):
        return ProductCode.objects.filter(
            brand__name="دارما", code=VARIANT_PRODUCT_CODE, active=True
        ).first()

    # Force title-only resolution first by passing a blank seller code. This
    # still uses the existing aliases (D-220 -> D 220, model 6 -> 06, etc.) and
    # brand hints embedded in the title (دارما/تکوین).
    if candidate:
        title_product = _resolve_product("", title, by_key)
        if title_product and title_product.brand.name in IMPORT_BRANDS:
            return title_product

    # Only if the title cannot identify a configured product do we trust the
    # seller code as a fallback for legacy/abbreviated exports.
    product = _resolve_product(seller_code, title, by_key)
    if product and product.brand.name in IMPORT_BRANDS:
        return product
    return None


def resolve_rows_v12(parsed_rows):
    by_key = _product_maps_v19()
    resolved = []
    errors = []
    for row in parsed_rows:
        product = _resolve_product_v12(row.seller_code, row.title, by_key)
        size_name = _resolve_size(row.title)
        if product is None:
            shown_code = row.seller_code or _model_candidate(row.title) or "بدون کد"
            errors.append(f"ردیف {row.source_row}: کد «{shown_code}» به محصول سایت وصل نشد.")
            continue
        if not size_name:
            errors.append(f"ردیف {row.source_row}: سایز از عنوان «{row.title}» تشخیص داده نشد.")
            continue
        ps = (
            ProductSize.objects.filter(product=product, size__name=size_name, active=True)
            .select_related("size")
            .first()
        )
        if ps is None:
            errors.append(
                f"ردیف {row.source_row}: {product.brand.name} / {product.code} / {size_name} در سایت فعال نیست."
            )
            continue

        color_name = ""
        if product.brand.name == "دارما" and product.code == VARIANT_PRODUCT_CODE:
            color_name = resolve_variant_color(row.title, row.seller_code) or ""
            if not color_name:
                errors.append(
                    f"ردیف {row.source_row}: رنگ محصول s3 از عنوان/کد فروشنده تشخیص داده نشد."
                )
                continue
            if int(ps.default_sale_price or 0) <= 0:
                errors.append(
                    f"ردیف {row.source_row}: قیمت فروش s3 سایز {size_name} تعیین نشده؛ "
                    "از تنظیمات → محصولات و کدها → پک ۱ تایی قیمت را ثبت کن."
                )
                continue

        resolved.append(
            ResolvedOrderRowV12(
                source_row=row.source_row,
                brand_name=product.brand.name,
                product_code=product.code,
                size_name=size_name,
                quantity=int(row.quantity),
                color_name=color_name,
            )
        )
    return resolved, errors


def _aggregate(rows):
    grouped = defaultdict(int)
    for row in rows:
        grouped[(row.brand_name, row.product_code, row.size_name, row.color_name)] += int(row.quantity)
    return dict(grouped)


def preview_delivery_report(file_bytes: bytes, filename: str = "") -> dict:
    parsed, meta = parse_delivery_report(file_bytes, filename)
    resolved, errors = resolve_rows_v12(parsed)
    grouped = _aggregate(resolved)
    rows = [
        {
            "brand": brand,
            "code": code,
            "size": size,
            "color": color,
            "quantity": qty,
        }
        for (brand, code, size, color), qty in sorted(
            grouped.items(), key=lambda x: (x[0][0], x[0][2], x[0][1], x[0][3])
        )
    ]
    return {
        **meta,
        "filename": os.path.basename(filename or ""),
        "rows": rows,
        "errors": errors,
        "grouped_lines": len(rows),
        "total_quantity": sum(row["quantity"] for row in rows),
    }


def _stock_totals():
    totals = defaultdict(int)
    for row in StockBalance.objects.all().values("brand_id", "qty"):
        totals[row["brand_id"]] += int(row["qty"] or 0)
    return dict(totals)


@transaction.atomic
def apply_delivery_report(day: SaleDay, file_bytes: bytes, filename: str = "") -> dict:
    preview = preview_delivery_report(file_bytes, filename)
    if preview["errors"]:
        raise DailyOrderImportError("\n".join(preview["errors"]))

    quantity_by_key = defaultdict(int)
    variant_colors_by_key = defaultdict(lambda: defaultdict(int))
    for row in preview["rows"]:
        key = (row["brand"], row["code"], row["size"])
        quantity_by_key[key] += int(row["quantity"])
        if row.get("color"):
            variant_colors_by_key[key][row["color"]] += int(row["quantity"])

    targets = {}
    product_sizes = {}
    key_by_ps = {}
    for key, qty in quantity_by_key.items():
        brand_name, code, size_name = key
        ps = ProductSize.objects.select_related("product__brand", "size").get(
            product__brand__name=brand_name,
            product__code=code,
            size__name=size_name,
            active=True,
            product__active=True,
        )
        targets[ps.id] = qty
        product_sizes[ps.id] = ps
        key_by_ps[ps.id] = key

    # The XLSX is authoritative only for the Digikala-import brands. Manual
    # Anbaresh lines can coexist on the same SaleDay and must never be zeroed
    # merely because they are absent from the delivery-report file.
    existing_lines = {
        line.product_size_id: line
        for line in SaleLine.objects.select_for_update()
        .filter(day=day, product_size__product__brand__name__in=IMPORT_BRANDS)
        .select_related("product_size__product__brand", "product_size__size")
    }

    before_stock = _stock_totals()
    old_sold = sold_units_by_brand(list(existing_lines.values()))

    all_ps_ids = set(existing_lines) | set(targets)
    shortage_count = 0
    changed_lines = 0
    for ps_id in all_ps_ids:
        ps = product_sizes.get(ps_id)
        line = existing_lines.get(ps_id)
        if ps is None and line is not None:
            ps = line.product_size
        qty = int(targets.get(ps_id, 0))
        if line is None:
            price = int(ps.default_sale_price or 0)
            line = SaleLine.objects.create(day=day, product_size=ps, quantity=0, sale_price=price)
        else:
            price = int(line.sale_price or ps.default_sale_price or 0)

        if qty > 0 and price <= 0:
            raise DailyOrderImportError(
                f"قیمت فروش {ps.product.code} / {ps.size.name} صفر است؛ قبل از Import قیمت را تعیین کن."
            )

        if int(line.quantity or 0) != qty or int(line.sale_price or 0) != price:
            changed_lines += 1
        line.quantity = qty
        line.sale_price = price
        line.save(update_fields=["quantity", "sale_price"])

        if ps.product.brand.name == "دارما" and ps.product.code == VARIANT_PRODUCT_CODE:
            key = key_by_ps.get(ps_id, (ps.product.brand.name, ps.product.code, ps.size.name))
            result = sync_variant_inventory(line, dict(variant_colors_by_key.get(key, {})))
        else:
            result = sync_sale_inventory(line)
        shortage_count += len(result.get("shortages") or [])

        # Snapshot after inventory allocation so Darma COGS uses the actual colors sold.
        if qty > 0:
            snapshot_sale_line(line, ps, price)

        AccountEntry.objects.filter(reference=f"sale:{line.id}:digikala").delete()

    current_lines = list(
        SaleLine.objects.filter(
            day=day,
            quantity__gt=0,
            product_size__product__brand__name__in=IMPORT_BRANDS,
        ).select_related("product_size__product__brand", "product_size__size")
    )
    after_stock = _stock_totals()
    new_sold = sold_units_by_brand(current_lines)
    try:
        assert_stock_invariant(before_stock, after_stock, old_sold, new_sold)
    except ValueError as exc:
        raise DailyOrderImportError(str(exc)) from exc

    preview["changed_lines"] = changed_lines
    preview["shortage_count"] = shortage_count
    preview["sale_day_id"] = day.id
    return preview