"""V152: true historic allocations and signed stock reclassification, no financial writes."""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.azar_pack_colors_v152 import effective_sale_compositions
from core.final_services import sync_sale_inventory
from core.models import (
    Account, AccountEntry, Brand, Color, InventoryMovement, ProductCode,
    ProductComposition, ProductSize, SaleAllocation, SaleDay, SaleLine,
    SaleShortage, SaleSnapshot, Size, StockBalance, StockLocation,
)


class AzarPackColorV152Tests(TestCase):
    def setUp(self):
        self.brand=Brand.objects.create(name="دارما")
        self.anbaresh=Brand.objects.create(name="انبارش")
        self.home=StockLocation.objects.create(key=StockLocation.HOME,title="خانه")
        self.khorshid=StockLocation.objects.create(key=StockLocation.KHORSHID,title="خورشید")
        self.size=Size.objects.create(name="XL")
        self.colors={
            name: Color.objects.create(name=name)
            for name in ("کرم","قرمز","طوسی","مشکی","سفید")
        }
        self.codes={}
        for code, pack, comp in [
            ("06", 6, {"کرم":1,"مشکی":3,"سفید":2}),
            ("p12",12,{"طوسی":2,"مشکی":8,"سفید":2}),
        ]:
            p=ProductCode.objects.create(
                code=code,brand=self.brand,active=True,pack_qty=pack,
            )
            for name,qty in comp.items():
                ProductComposition.objects.create(
                    product=p,color=self.colors[name],qty=qty,
                )
            ps=ProductSize.objects.create(
                product=p,size=self.size,default_sale_price=920000,
            )
            self.codes[code]=ps
        # Baseline physical stock, including Khorshid untouched by correction.
        for name,color in self.colors.items():
            StockBalance.objects.create(
                brand=self.brand,size=self.size,color=color,
                location=self.home,qty=2000,
            )
            StockBalance.objects.create(
                brand=self.brand,size=self.size,color=color,
                location=self.khorshid,qty=900,
            )
        self.account=Account.objects.create(
            key=Account.DIGIKALA,title="دیجی‌کالا",opening_balance=0,
        )

    def historical_posting(self,code,when,packs):
        day,_=SaleDay.objects.get_or_create(date=when)
        ps=self.codes[code]
        line=SaleLine.objects.create(
            day=day,product_size=ps,quantity=packs,
            inventory_applied_quantity=packs,sale_price=920000,
        )
        for comp in ProductComposition.objects.filter(product=ps.product):
            needed=comp.qty*packs
            row=StockBalance.objects.get(
                brand=self.brand,size=self.size,color=comp.color,
                location=self.home,
            )
            row.qty-=needed
            row.save(update_fields=["qty"])
            SaleAllocation.objects.create(
                sale_line=line,color=comp.color,
                location=self.home,qty=needed,
            )
            InventoryMovement.objects.create(
                movement_type=InventoryMovement.SALE,
                brand=self.brand,size=self.size,
                color=comp.color,location=self.home,
                delta=-needed,reference=f"sale:{line.pk}",
            )
        SaleSnapshot.objects.create(
            sale_line=line,unit_cost=74000,pack_qty=ps.product.pack_qty,
            digikala_fee_unit=40000,
        )
        AccountEntry.objects.create(
            account=self.account,date=when,
            delta=890000*packs,reference=f"sale:{line.pk}:digikala",
            title="طلب فروش",entry_type="sale",
        )
        return line

    def allocations(self,line):
        out={}
        for a in line.allocations.select_related("color"):
            out[a.color.name]=out.get(a.color.name,0)+a.qty
        return out

    def balances(self,location):
        return {
            b.color.name:b.qty
            for b in StockBalance.objects.select_related("color")
            .filter(brand=self.brand,location=location)
        }

    def books(self):
        return (
            list(SaleLine.objects.order_by("id").values_list(
                "id","day__date","quantity","sale_price",
                "inventory_applied_quantity"
            )),
            list(SaleSnapshot.objects.order_by("pk").values_list(
                "sale_line_id","unit_cost","pack_qty","digikala_fee_unit",
            )),
            list(AccountEntry.objects.order_by("pk").values_list(
                "id","account_id","delta","date","reference",
            )),
            list(ProductComposition.objects.order_by("pk").values_list(
                "product_id","color_id","qty",
            )),
        )

    def test_dry_run_apply_stock_two_codes_older_date_unmodified_and_second_run_noop(self):
        old=self.historical_posting("06",date(2026,11,21),3)
        six=self.historical_posting("06",date(2026,11,22),2)
        twelve=self.historical_posting("p12",date(2026,11,23),3)
        old_allocation=self.allocations(old)
        before=self.balances(self.home)
        khorshid=self.balances(self.khorshid)
        accounting=self.books()
        initial_movements=InventoryMovement.objects.count()
        dry=StringIO()
        call_command("reclassify_azar_packs_v152",stdout=dry)
        self.assertIn("V152_DRY_RUN=OK",dry.getvalue())
        self.assertIn("color_pieces=2",dry.getvalue())
        self.assertIn("color_pieces=6",dry.getvalue())
        self.assertEqual(before,self.balances(self.home))
        self.assertEqual(accounting,self.books())
        self.assertEqual(initial_movements,InventoryMovement.objects.count())

        out=StringIO()
        call_command("reclassify_azar_packs_v152",apply=True,stdout=out)
        self.assertIn("V152_APPLIED=OK corrected_lines=2",out.getvalue())
        self.assertEqual(self.allocations(old),old_allocation)
        self.assertEqual(self.allocations(six),{"مشکی":6,"سفید":4,"قرمز":2})
        self.assertEqual(self.allocations(twelve),{"مشکی":24,"سفید":6,"قرمز":6})
        after=self.balances(self.home)
        self.assertEqual(after["کرم"],before["کرم"]+2)
        self.assertEqual(after["طوسی"],before["طوسی"]+6)
        self.assertEqual(after["قرمز"],before["قرمز"]-8)
        self.assertEqual(after["مشکی"],before["مشکی"])
        self.assertEqual(after["سفید"],before["سفید"])
        self.assertEqual(self.balances(self.khorshid),khorshid)
        self.assertEqual(accounting,self.books())
        self.assertEqual(InventoryMovement.objects.count(),initial_movements+4)

        # Repeat --apply is a true no-op, not a second decrement.
        second=StringIO()
        call_command("reclassify_azar_packs_v152",apply=True,stdout=second)
        self.assertIn("corrected_lines=0",second.getvalue())
        self.assertEqual(self.balances(self.home),after)
        self.assertEqual(InventoryMovement.objects.count(),initial_movements+4)
        self.assertEqual(accounting,self.books())

        # Re-upload of the same Digikala day uses date-correct recipe.
        sync_sale_inventory(six)
        self.assertEqual(self.allocations(six),{"مشکی":6,"سفید":4,"قرمز":2})
        self.assertEqual(self.balances(self.home),after)

    def test_new_postings_from_azar_use_revised_recipe_old_stays_old(self):
        day_before,_=SaleDay.objects.get_or_create(date=date(2026,11,21))
        day_after,_=SaleDay.objects.get_or_create(date=date(2026,11,22))
        older=SaleLine.objects.create(
            day=day_before,product_size=self.codes["p12"],quantity=1,sale_price=1,
        )
        after=SaleLine.objects.create(
            day=day_after,product_size=self.codes["06"],quantity=1,sale_price=1,
        )
        self.assertEqual(
            {c.color.name:c.qty for c in effective_sale_compositions(older)}["طوسی"],2,
        )
        self.assertNotIn(
            "کرم",{c.color.name:c.qty for c in effective_sale_compositions(after)},
        )
        self.assertEqual(
            {c.color.name:c.qty for c in effective_sale_compositions(after)}["قرمز"],1,
        )
        sync_sale_inventory(older)
        sync_sale_inventory(after)
        self.assertEqual(self.allocations(older),{"طوسی":2,"مشکی":8,"سفید":2})
        self.assertEqual(self.allocations(after),{"قرمز":1,"مشکی":3,"سفید":2})

    def test_invalid_sale_allocation_refuses_entire_batch_before_writing(self):
        a=self.historical_posting("06",date(2026,11,22),1)
        b=self.historical_posting("p12",date(2026,11,23),2)
        # Last line has a color-specific historical replacement/shortage,
        # making automatic interpretation unsafe.
        SaleShortage.objects.create(
            sale_line=b,source_color=self.colors["طوسی"],
            qty=1,resolved=False,
        )
        before_stock=self.balances(self.home)
        before_allocs=(self.allocations(a),self.allocations(b))
        before_books=self.books()
        before_moves=InventoryMovement.objects.count()
        with self.assertRaises(CommandError):
            call_command("reclassify_azar_packs_v152",apply=True,stdout=StringIO(),stderr=StringIO())
        self.assertEqual(self.balances(self.home),before_stock)
        self.assertEqual((self.allocations(a),self.allocations(b)),before_allocs)
        self.assertEqual(self.books(),before_books)
        self.assertEqual(InventoryMovement.objects.count(),before_moves)

    def test_existing_corrected_line_is_detected_without_any_stock_write(self):
        a=self.historical_posting("06",date(2026,11,22),2)
        call_command("reclassify_azar_packs_v152",apply=True,stdout=StringIO())
        before=self.balances(self.home)
        before_moves=InventoryMovement.objects.count()
        out=StringIO()
        call_command("reclassify_azar_packs_v152",stdout=out)
        self.assertIn("already_corrected=1",out.getvalue())
        self.assertEqual(self.balances(self.home),before)
        self.assertEqual(InventoryMovement.objects.count(),before_moves)

    def test_only_darma_brand_not_anbaresh_affected(self):
        d=SaleDay.objects.create(date=date(2026,11,22))
        mirrored=ProductCode.objects.create(
            brand=self.anbaresh,code="06",pack_qty=6,active=True,
        )
        mirrored_ps=ProductSize.objects.create(product=mirrored,size=self.size)
        SaleLine.objects.create(day=d,product_size=mirrored_ps,quantity=1)
        output=StringIO()
        call_command("reclassify_azar_packs_v152",stdout=output)
        self.assertIn("V152_SUMMARY_06: packs=0",output.getvalue())
