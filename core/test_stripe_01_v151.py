"""V151: 9 actual XLSX rows, 4 precise physical colors, 13% ONLY Azar 1-10."""
from collections import defaultdict
from datetime import date
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zipfile import ZipFile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.brand_colors import norm
from core.daily_order_import_v12 import resolve_rows_v12
from core.daily_order_import_v23 import (
    apply_delivery_report, preview_delivery_report,
)
from core.daily_order_import_v8 import ParsedOrderRow
from core.finance import digikala_fee_for_unit, sale_line_metrics
from core.models import (
    AppSetting, Brand, Color, ProductCode, ProductSize, SaleDay,
    SaleLine, Size, StockBalance, StockLocation, InventoryMovement,
    SaleSnapshot,
)
from core.stripe_01_v151 import (
    PRODUCT_CODE, PRODUCT_TITLE, OFFER_START, OFFER_END,
    SALE_PRICE, UNIT_COST,
)
from core.title_product_resolver_v27 import resolve_product_from_title
from core.variant_sale_v12 import resolve_variable_product_color


REAL_XLSX_ROWS = [
    (3, "XL", "مشکی", 7),
    (5, "XXL", "مشکی", 6),
    (9, "XXL", "قرمز", 4),
    (14, "XL", "سرمه ای", 3),
    (15, "XXL", "طوسی", 3),
    (53, "XXL", "سرمه ای", 1),
    (54, "M", "طوسی", 1),
    (55, "XL", "طوسی", 1),
    (56, "XL", "قرمز", 1),
]
COLOR_MAP = {
    "مشکی": "راه راه مشکی",
    "قرمز": "راه راه قرمز",
    "طوسی": "راه راه طوسی",
    "سرمه ای": "راه راه",
}


def title(size, color):
    return (
        "شورت اسلیپ زنانه دارما مدل راه راه 01 | " + size +
        " | " + color + " | گارانتی اصالت و سلامت فیزیکی کالا"
    )


def make_xlsx():
    headers = [
        "کد تنوع", "کد فروشنده", "عنوان", "تعداد پیشنهادی",
        "تعداد ارسالی", "تعداد مغایرت", "وضعیت",
    ]
    records = [
        [92534000 + number, "", title(size, color), "0", str(qty), "0", "اماده ارسال/تحویل"]
        for number, (row, size, color, qty) in enumerate(REAL_XLSX_ROWS)
    ]
    rows = []
    for i, fields in enumerate([headers] + records, start=1):
        cells = []
        for j, val in enumerate(fields):
            cells.append(
                f'<c r="{"ABCDEFG"[j]}{i}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>'
            )
        rows.append(f'<row r="{i}">{"".join(cells)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = f'<worksheet xmlns="{ns}"><sheetData>{"".join(rows)}</sheetData></worksheet>'
    workbook = (
        f'<workbook xmlns="{ns}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rel = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    out=BytesIO()
    with ZipFile(out,"w") as z:
        z.writestr("xl/workbook.xml",workbook)
        z.writestr("xl/_rels/workbook.xml.rels",rel)
        z.writestr("xl/worksheets/sheet1.xml",sheet)
    return out.getvalue()


class Stripe01ImportV151Tests(TestCase):
    def setUp(self):
        self.brand=Brand.objects.create(name="دارما")
        self.anbaresh=Brand.objects.create(name="انبارش")
        self.other_brand=Brand.objects.create(name="تکوین")
        self.sizes={
            name: Size.objects.create(name=name,sort_order=i)
            for i,name in enumerate(["M","L","XL","XXL","3XL","4XL"])
        }
        self.home=StockLocation.objects.create(key="home",title="خانه")
        StockLocation.objects.create(key="khorshid",title="خورشید")
        Color.objects.create(name="راه راه")
        Color.objects.create(name="راه راه طوسی")
        self.day=SaleDay.objects.create(date=OFFER_START)
        self.legacy=ProductCode.objects.create(
            brand=self.brand,code="striped",title="شورت زنانه دارما مدل striped مجموعه 3 عددی",
            pack_qty=3,active=True,
        )
        for key,val in [
            ("digikala_commission_percent",24),
            ("digikala_processing_percent",7),
            ("digikala_processing_floor",36000),
            ("digikala_vat_percent",10),
            ("digikala_floor_taxable_part",18000),
        ]:
            AppSetting.objects.create(key=key,value=str(val),label=key)
        for variant, amount in [("مشکی",13),("قرمز",5),("طوسی",5),("سرمه ای",4)]:
            pass

    def apply_catalog(self):
        output=StringIO()
        call_command("configure_stripe_01_v151",apply=True,stdout=output)
        self.assertIn("V151_VERIFY=OK",output.getvalue())
        product=ProductCode.objects.get(brand=self.brand,code=PRODUCT_CODE)
        for cname in COLOR_MAP.values():
            color=next(c for c in Color.objects.filter(active=True) if norm(c.name)==norm(cname))
            for size in ["M","XL","XXL"]:
                StockBalance.objects.get_or_create(
                    brand=self.brand,size=self.sizes[size],
                    color=color,location=self.home,defaults={"qty":100},
                )
        return product

    def test_read_only_preflight_and_idempotent_focused_catalog_only(self):
        before=(ProductCode.objects.count(),Color.objects.count(),ProductSize.objects.count(),
                InventoryMovement.objects.count(),StockBalance.objects.count())
        out=StringIO()
        call_command("configure_stripe_01_v151",stdout=out)
        self.assertIn("V151_READ_ONLY=YES",out.getvalue())
        self.assertEqual(before,(ProductCode.objects.count(),Color.objects.count(),
                                 ProductSize.objects.count(),InventoryMovement.objects.count(),
                                 StockBalance.objects.count()))
        product=self.apply_catalog()
        self.assertEqual(product.title,PRODUCT_TITLE)
        self.assertEqual(product.pack_qty,1)
        self.assertFalse(product.composition.exists())
        self.assertEqual(ProductSize.objects.filter(product=product,active=True).count(),6)
        self.assertEqual(Color.objects.count(),4)
        before=(ProductCode.objects.count(),Color.objects.count(),ProductSize.objects.count())
        call_command("configure_stripe_01_v151",apply=True,stdout=StringIO())
        self.assertEqual(before,(ProductCode.objects.count(),Color.objects.count(),
                                 ProductSize.objects.count()))
        self.assertEqual(InventoryMovement.objects.count(),0)
        self.assertEqual(StockBalance.objects.count(),12)

    def test_model_title_not_seller_code_and_exact_color_map_all_nine_rows(self):
        product=self.apply_catalog()
        rows=[
            ParsedOrderRow(source_row=row,seller_code="",title=title(size,color),
                           quantity=qty,status="اماده ارسال/تحویل")
            for row,size,color,qty in REAL_XLSX_ROWS
        ]
        resolved,errors=resolve_rows_v12(rows)
        self.assertEqual(errors,[])
        self.assertEqual(sum(r.quantity for r in resolved),27)
        self.assertEqual(len(resolved),9)
        grouped=defaultdict(int)
        for raw,r in zip(REAL_XLSX_ROWS,resolved):
            self.assertEqual(r.product_code,PRODUCT_CODE)
            self.assertEqual(r.brand_name,"دارما")
            self.assertEqual(r.size_name,raw[1])
            self.assertEqual(r.color_name,COLOR_MAP[raw[2]])
            grouped[r.color_name]+=r.quantity
        self.assertEqual(dict(grouped),{
            "راه راه مشکی":13,"راه راه قرمز":5,
            "راه راه طوسی":5,"راه راه":4,
        })
        self.assertEqual(ProductCode.objects.get(pk=product.pk).pack_qty,1)
        self.assertEqual(ProductCode.objects.get(pk=self.legacy.pk).pack_qty,3)

    def test_actual_xlsx_parse_preview_then_import_and_reimport_stock_idempotence(self):
        product=self.apply_catalog()
        content=make_xlsx()
        before={
            (balance.size.name,balance.color.name):balance.qty
            for balance in StockBalance.objects.filter(brand=self.brand)
        }
        preview=preview_delivery_report(content,"packageDeliveryReport_17952954362484.xlsx")
        self.assertEqual(preview["errors"],[])
        self.assertEqual(preview["total_quantity"],27)
        self.assertEqual(sum(int(r["quantity"]) for r in preview["rows"]),27)
        self.assertEqual(SaleLine.objects.count(),0)
        self.assertEqual(InventoryMovement.objects.count(),0)
        result=apply_delivery_report(self.day,content,"packageDeliveryReport_17952954362484.xlsx")
        self.assertEqual(result["total_quantity"],27)
        self.assertEqual(SaleLine.objects.filter(day=self.day).count(),3)
        self.assertEqual(
            {(line.product_size.size.name,line.quantity) for line in SaleLine.objects.filter(day=self.day).select_related("product_size__size")},
            {("M",1),("XL",12),("XXL",14)},
        )
        expected=defaultdict(int)
        for _,size,color,qty in REAL_XLSX_ROWS:
            expected[(size,COLOR_MAP[color])]+=qty
        after={(b.size.name,b.color.name):b.qty for b in StockBalance.objects.filter(brand=self.brand)}
        for key,qty in expected.items():
            self.assertEqual(after[key],before[key]-qty)
        for line in SaleLine.objects.filter(day=self.day):
            self.assertEqual(line.product_size.product.pk,product.pk)
            self.assertEqual(line.sale_price,139000)
            self.assertEqual(line.snapshot.pack_qty,1)
            self.assertEqual(line.snapshot.unit_cost,67000)
            self.assertEqual(line.snapshot.digikala_fee_unit,57677)
            self.assertEqual(sale_line_metrics(line)["profit"],14323*line.quantity)
        first=after.copy()
        apply_delivery_report(self.day,content,"reupload.xlsx")
        second={(b.size.name,b.color.name):b.qty for b in StockBalance.objects.filter(brand=self.brand)}
        self.assertEqual(first,second)
        self.assertEqual(SaleLine.objects.filter(day=self.day).count(),3)

    def test_fee_effect_only_on_specific_darma_sku_exact_10_dates(self):
        product=self.apply_catalog()
        self.assertEqual((OFFER_START,OFFER_END),(date(2026,11,22),date(2026,12,1)))
        self.assertEqual(
            digikala_fee_for_unit(139000,OFFER_START,product_code=PRODUCT_CODE,brand_name="دارما"),
            57677
        )
        self.assertEqual(
            digikala_fee_for_unit(139000,OFFER_END,product_code=PRODUCT_CODE,brand_name="دارما"),
            57677
        )
        for when in (date(2026,11,21),date(2026,12,2)):
            self.assertEqual(digikala_fee_for_unit(
                139000,when,product_code=PRODUCT_CODE,brand_name="دارما"
            ),74496)
        for code,brand in [
            ("striped","دارما"),("rah-110","دارما"),
            (PRODUCT_CODE,"تکوین"),(PRODUCT_CODE,"انبارش"),
        ]:
            self.assertEqual(digikala_fee_for_unit(
                139000,OFFER_START,product_code=code,brand_name=brand
            ),74496)
        self.assertEqual(digikala_fee_for_unit(139000,OFFER_START),74496)

    def test_unknown_title_color_fails_without_stock_write(self):
        self.apply_catalog()
        bad=ParsedOrderRow(source_row=9,seller_code="",
            title=title("XXL","صورتی"),quantity=4,status="اماده ارسال/تحویل")
        _rows,errors=resolve_rows_v12([bad])
        self.assertTrue(errors)
        self.assertIn("رنگ محصول",errors[0])
        self.assertFalse(SaleLine.objects.exists())
        self.assertFalse(InventoryMovement.objects.exists())

    def test_conflicting_existing_title_fails_without_catalog_changes(self):
        ProductCode.objects.create(
            brand=self.brand,code="custom-old",
            title="راه راه 01",pack_qty=2,active=False,
        )
        before=(ProductCode.objects.count(),ProductSize.objects.count(),Color.objects.count())
        with self.assertRaises(CommandError):
            call_command("configure_stripe_01_v151",apply=True,stdout=StringIO())
        self.assertEqual(before,(ProductCode.objects.count(),
                                 ProductSize.objects.count(),Color.objects.count()))
