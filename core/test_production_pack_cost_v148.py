"""V148: read-only pack costs from production cut-weighted color-specific months."""
from datetime import date
from decimal import Decimal

import jdatetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse, resolve

from core.material_cost_v23 import round_money
from core.models import (
    AppSetting, Brand, Color, ProductCode, ProductComposition,
    ProductSize, Size, MaterialReportBlock, RawMaterialStock, Account,
    InventoryMovement, StockBalance, TapsiOrder,
)
from core.production_pack_cost_v148 import (
    _jalali_period, _selected_color_costs, build_pack_cost_report,
    production_pack_costs,
)


class ProductionPackCostV148Tests(TestCase):
    def setUp(self):
        user=get_user_model().objects.create_user(username="v148-pack", password="test")
        self.client.force_login(user)
        self.brand=Brand.objects.create(name="دارما")
        self.other=Brand.objects.create(name="Novani")
        self.size=Size.objects.create(name="M")
        self.black=Color.objects.create(name="مشکی")
        self.pink=Color.objects.create(name="صورتی")
        self.gray=Color.objects.create(name="طوسی")
        self.white=Color.objects.create(name="سفید")
        AppSetting.objects.create(key="pedram_dozen_wage",label="دوجین",value="110000")
        self.product=ProductCode.objects.create(
            brand=self.brand,code="P4",title="پک چهار رنگ",pack_qty=4
        )
        for color,qty in ((self.black,2),(self.pink,1),(self.gray,1)):
            ProductComposition.objects.create(product=self.product,color=color,qty=qty)
        ProductSize.objects.create(product=self.product,size=self.size,active=True)
        today=date.today()
        now=jdatetime.date.fromgregorian(date=today)
        self.today=today
        self.current=jdatetime.date(now.year,now.month,1).togregorian()
        if now.month==1:
            self.prev_j=jdatetime.date(now.year-1,12,1)
        else:
            self.prev_j=jdatetime.date(now.year,now.month-1,1)
        self.previous=self.prev_j.togregorian()
        self._stock("black",1900000)
        self._stock("pink",2000000)
        self._stock("gray",1600000)
        self._stock(f"color:{self.white.id}",1750000)

    def _stock(self,key,price):
        RawMaterialStock.objects.create(
            kind="fabric",location="warehouse",material_key=key,
            title=key,unit="کیلو",unit_price=price,quantity=Decimal("60"),
        )

    def _block(self,key,when,weight,cut,code="XX",brand=None):
        return MaterialReportBlock.objects.create(
            date=when,brand=brand or self.brand,
            title=code,
            input_data={
                "_meta":{"active_material_keys":[key]},
                key:{"fabric_code":code,"weight":str(weight),"cut":str(cut)},
            },
            output_data={},
        )

    def test_weighted_by_cut_not_simple_roll_mean_and_pack_composition(self):
        self._block("black",self.current,10,100,"B1")
        self._block("black",self.today,10,200,"B2")
        self._block("pink",self.previous,10,100,"P1")
        self._block("gray",self.previous,10,100,"G1")
        report=build_pack_cost_report(self.today)
        colors=_selected_color_costs(self.today)
        black=colors["مشکی"]
        self.assertEqual(black["cut"],300)
        self.assertEqual(black["rolls"],2)
        self.assertEqual(black["unit_cost"],round_money(
            Decimal(black["total_cost"])/Decimal(300)
        ))
        # The two roll costs are very different. A simple arithmetic mean
        # of their unit costs must NOT match a cut-weighted monthly mean.
        self.assertNotEqual(black["unit_cost"],round_money(
            (Decimal(199167)+Decimal(104167))/2
        ))
        self.assertFalse(black["older"])
        self.assertTrue(colors["صورتی"]["older"])
        self.assertTrue(colors["طوسی"]["older"])
        self.assertEqual(report["products_ready"],1)
        pack=report["products"][0]
        expected=2*black["unit_cost"]+colors["صورتی"]["unit_cost"]+colors["طوسی"]["unit_cost"]
        self.assertEqual(pack["cost"],expected)
        self.assertEqual(pack["count"],4)
        self.assertTrue(pack["complete"])
        self.assertEqual([row["qty"] for row in pack["contents"]],[2,1,1])

    def test_current_month_always_wins_and_fallback_skips_empty_months(self):
        self._block("black",self.previous,15,100,"OLD")
        self._block("black",self.current,10,100,"NEW")
        data=_selected_color_costs(self.today)
        self.assertEqual(data["مشکی"]["month"],_jalali_period(self.today))
        self.assertFalse(data["مشکی"]["older"])
        self.assertEqual(data["مشکی"]["cut"],100)
        self.assertTrue(data["مشکی"]["available"])
        self.assertNotEqual(data["مشکی"]["unit_cost"],round_money(Decimal(15*1900000)/100))

    def test_unknown_color_or_missing_weight_will_never_fake_zero_cost(self):
        self._block("black",self.current,0,100,"BROKEN")
        self._block("black",self.previous,12,100,"OLD_VALID")
        self._block("pink",self.previous,10,100,"P1")
        # Gray has no cut sheet. Current black has a cut sheet, but missing
        # its fabric weight. Neither should silently fall back to older price.
        result=build_pack_cost_report(self.today)
        self.assertEqual(result["products_ready"],0)
        self.assertIsNone(result["products"][0]["cost"])
        self.assertTrue(_selected_color_costs(self.today)["مشکی"]["incomplete"])
        self.assertIn("طوسی",result["products"][0]["missing"])
        self.assertIn("مشکی",result["products"][0]["missing"])

    def test_multi_color_key_uses_id_and_incorrect_composition_is_blocked(self):
        product=ProductCode.objects.create(brand=self.brand,code="WHITE",pack_qty=1)
        ProductComposition.objects.create(product=product,color=self.white,qty=1)
        ProductSize.objects.create(product=product,size=self.size,active=True)
        self._block(f"color:{self.white.id}",self.current,10,100,"DYNAMIC")
        result=build_pack_cost_report(self.today)
        white=next(row for row in result["products"] if row["code"]=="WHITE")
        self.assertIsNotNone(white["cost"])
        self.assertEqual(white["cost"],_selected_color_costs(self.today)["سفید"]["unit_cost"])
        product.pack_qty=2
        product.save(update_fields=["pack_qty"])
        result=build_pack_cost_report(self.today)
        white=next(row for row in result["products"] if row["code"]=="WHITE")
        self.assertIsNone(white["cost"])
        self.assertIn("ترکیب رنگ‌ها با تعداد پک مطابقت ندارد",white["missing"])

    def test_other_brand_and_future_sheet_are_excluded(self):
        self._block("black",self.current,10,100,"B1",brand=self.other)
        self._block("pink",self.previous,10,100,"P1",brand=self.other)
        self._block("black",date.max,10,100,"FUTURE")
        self.assertNotIn("مشکی",_selected_color_costs(self.today))
        self.assertNotIn("صورتی",_selected_color_costs(self.today))

    def test_get_requires_login_and_does_not_change_stocks_or_finance(self):
        self._block("black",self.current,10,100,"CURRENT")
        self._block("pink",self.previous,10,100,"PREV")
        self._block("gray",self.previous,10,100,"PREV-G")
        self.assertIs(resolve("/material-report/pack-costs/").func,production_pack_costs)
        before={
            "materials":list(RawMaterialStock.objects.order_by("id").values_list("id","quantity","unit_price")),
            "sheets":list(MaterialReportBlock.objects.order_by("id").values_list("id","input_data","output_data")),
            "inventory":list(StockBalance.objects.values_list("id","qty")),
            "movements":InventoryMovement.objects.count(),
            "accounts":Account.objects.count(),
            "orders":TapsiOrder.objects.count(),
        }
        response=self.client.get(reverse("production_pack_costs"))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"بهای تمام‌شده محصولات")
        self.assertContains(response,'data-pack-cost-report="v148"')
        self.assertContains(response,'data-color-cost-report="v148"')
        self.assertContains(response,"P4")
        self.assertContains(response,"پک چهار رنگ")
        self.assertEqual(before["materials"],list(RawMaterialStock.objects.order_by("id").values_list("id","quantity","unit_price")))
        self.assertEqual(before["sheets"],list(MaterialReportBlock.objects.order_by("id").values_list("id","input_data","output_data")))
        self.assertEqual(before["inventory"],list(StockBalance.objects.values_list("id","qty")))
        self.assertEqual(before["movements"],InventoryMovement.objects.count())
        self.assertEqual(before["accounts"],Account.objects.count())
        self.assertEqual(before["orders"],TapsiOrder.objects.count())
        self.assertContains(self.client.get(reverse("material_report")),reverse("production_pack_costs"))
        self.assertContains(self.client.get(reverse("material_production_overall")),reverse("production_pack_costs"))
        self.client.logout()
        response=self.client.get(reverse("production_pack_costs"))
        self.assertEqual(response.status_code,302)
