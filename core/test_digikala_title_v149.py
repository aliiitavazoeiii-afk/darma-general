"""V149 regression for uploaded Digikala XLSX row 50: bear-01 / 40-42.

The registered product's canonical code is 'bear' while its display title
is 'bear-01'. The actual XLSX seller-code field is 'bear' but the importer
must resolve from title ONLY. No fuzzy matching or inventory mutation on
invalid model title is permitted.
"""
from datetime import date
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.daily_order_import_v12 import resolve_rows_v12
from core.daily_order_import_v8 import ParsedOrderRow
from core.daily_order_import_v23 import preview_delivery_report
from core.daily_order_views_v60 import apply_delivery_reports_v60
from core.models import (
    Brand, Color, ProductCode, ProductComposition, ProductSize, Size,
    SaleDay, SaleLine, StockBalance, StockLocation, InventoryMovement,
)
from core.title_product_resolver_v27 import resolve_product_from_title


BEAR_DIGIKALA_ROW = (
    "شورت زنانه دارما مدل bear-01 مجموعه 3 عددی | 40-42 | "
    "چند رنگ | گارانتی اصالت و سلامت فیزیکی کالا"
)


def single_row_xlsx(title, seller_code="bear", quantity=1):
    """Minimal valid XLSX containing the exact columns of Digikala export."""
    from xml.sax.saxutils import escape
    values = [
        ["کد تنوع", "کد فروشنده", "عنوان", "تعداد ارسالی", "وضعیت"],
        ["91994714", seller_code, title, str(quantity), "دریافت شده"],
    ]
    rows = []
    for r, fields in enumerate(values, 1):
        cells = []
        for c, val in enumerate(fields):
            col = "ABCDE"[c]
            cells.append(
                f'<c r="{col}{r}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>'
            )
        rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    doc = f'<worksheet xmlns="{main}"><sheetData>{"".join(rows)}</sheetData></worksheet>'
    workbook = (
        f'<workbook xmlns="{main}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rel = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    stream=BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rel)
        z.writestr("xl/worksheets/sheet1.xml", doc)
    return stream.getvalue()


class DigikalaExactProductTitleV149Tests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="دارما")
        self.mirror = Brand.objects.create(name="انبارش")
        self.size = Size.objects.create(name="XL")
        self.black = Color.objects.create(name="مشکی")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        StockLocation.objects.create(key="khorshid", title="خورشید")
        self.product = ProductCode.objects.create(
            brand=self.brand, code="bear", title="bear-01",
            pack_qty=3, active=True,
        )
        self.mirrored = ProductCode.objects.create(
            brand=self.mirror, code="bear", title="bear-01",
            pack_qty=3, active=True,
        )
        self.ps=ProductSize.objects.create(
            product=self.product, size=self.size,
            default_sale_price=750000, active=True,
        )
        ProductSize.objects.create(
            product=self.mirrored, size=self.size,
            default_sale_price=750000, active=True,
        )
        ProductComposition.objects.create(product=self.product, color=self.black, qty=3)
        ProductComposition.objects.create(product=self.mirrored, color=self.black, qty=3)
        self.stock=StockBalance.objects.create(
            brand=self.brand, size=self.size, color=self.black,
            location=self.home, qty=20,
        )

    def test_real_excel_row_50_title_resolves_only_darma_product(self):
        resolved=resolve_product_from_title(BEAR_DIGIKALA_ROW)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.pk,self.product.pk)
        self.assertEqual(resolved.code,"bear")
        parsed=[ParsedOrderRow(
            source_row=50,seller_code="",
            title=BEAR_DIGIKALA_ROW, quantity=1, status="دریافت شده",
        )]
        rows,errors=resolve_rows_v12(parsed)
        self.assertEqual(errors,[])
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0].brand_name,rows[0].product_code,rows[0].size_name),
                         ("دارما","bear","XL"))

    def test_real_title_xlsx_preview_reads_without_any_stock_or_sales_write(self):
        before=(self.stock.qty,SaleLine.objects.count(),InventoryMovement.objects.count())
        preview=preview_delivery_report(single_row_xlsx(BEAR_DIGIKALA_ROW),"delivery.xlsx")
        self.assertEqual(preview["errors"],[])
        self.assertEqual(preview["total_quantity"],1)
        self.assertEqual(preview["rows"],[{
            "brand":"دارما","code":"bear","size":"XL","color":"","quantity":1
        }])
        self.stock.refresh_from_db()
        self.assertEqual(before,
            (self.stock.qty,SaleLine.objects.count(),InventoryMovement.objects.count()))

    def test_xlsx_import_debits_exact_three_shorts_and_reimport_is_idempotent(self):
        day=SaleDay.objects.create(date=date.today())
        content=single_row_xlsx(BEAR_DIGIKALA_ROW)
        before=self.stock.qty
        result=apply_delivery_reports_v60(day,[(content,"first.xlsx")])
        self.assertEqual(result["total_quantity"],1)
        line=SaleLine.objects.get(day=day,product_size=self.ps)
        self.assertEqual(line.quantity,1)
        self.assertEqual(line.sale_price,750000)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.qty,before-3)
        self.assertFalse(SaleLine.objects.filter(product_size__product=self.mirrored).exists())
        result=apply_delivery_reports_v60(day,[(content,"reimport.xlsx")])
        self.assertEqual(result["total_quantity"],1)
        line.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(line.quantity,1)
        self.assertEqual(self.stock.qty,before-3)

    def test_wrong_seller_code_does_not_overrule_exact_title(self):
        parsed=[ParsedOrderRow(
            source_row=50,seller_code="arbitrary-wrong-seller-code",
            title=BEAR_DIGIKALA_ROW,quantity=1,status="دریافت شده",
        )]
        rows,errors=resolve_rows_v12(parsed)
        self.assertEqual(errors,[])
        self.assertEqual(rows[0].product_code,"bear")

    def test_model_name_must_match_entire_registered_title_not_partial(self):
        titles=[
            BEAR_DIGIKALA_ROW.replace("bear-01","bear-010"),
            BEAR_DIGIKALA_ROW.replace("bear-01","unregistered-bear-01"),
            BEAR_DIGIKALA_ROW.replace("bear-01","ghost"),
        ]
        for title in titles:
            self.assertIsNone(resolve_product_from_title(title))

    def test_duplicate_display_title_in_same_brand_fails_closed(self):
        ProductCode.objects.create(
            brand=self.brand,code="other-01",title="bear-01",pack_qty=1
        )
        self.assertIsNone(resolve_product_from_title(BEAR_DIGIKALA_ROW))

    def test_explicit_brand_limits_match_and_brandless_collisions_fail_closed(self):
        other=Brand.objects.create(name="تکوین")
        ProductCode.objects.create(brand=other,code="other-code",title="bear-01")
        self.assertEqual(resolve_product_from_title(BEAR_DIGIKALA_ROW).pk,self.product.pk)
        brandless=BEAR_DIGIKALA_ROW.replace("شورت زنانه دارما","شورت زنانه")
        self.assertIsNone(resolve_product_from_title(brandless))

    def test_canonical_code_always_precedes_matching_display_title(self):
        code_product=ProductCode.objects.create(
            brand=self.brand,code="bear-01",title="different-title",pack_qty=1
        )
        self.assertEqual(resolve_product_from_title(BEAR_DIGIKALA_ROW).pk,code_product.pk)

    def test_inactive_catalog_products_do_not_resolve_by_title(self):
        self.product.active=False
        self.product.save(update_fields=["active"])
        self.assertIsNone(resolve_product_from_title(BEAR_DIGIKALA_ROW))
