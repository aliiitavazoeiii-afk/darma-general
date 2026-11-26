"""Regression: five-piece pack Digikala 19% campaign, 1405/09/05–07."""
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.cost_accounting_v14 import snapshot_sale_line
from core.digikala_five_pack_v155 import START, END, applies_to
from core.finance import digikala_fee_for_unit, sale_line_metrics
from core.models import (
    Account, AccountEntry, AppSetting, Brand, ProductCode,
    ProductSize, SaleDay, SaleLine, Size,
)


class FivePackCommissionV155Tests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="دارما")
        self.takvin = Brand.objects.create(name="تکوین")
        self.size = Size.objects.create(name="XL", sort_order=1)
        self.account = Account.objects.create(
            key=Account.DIGIKALA, title="دیجی‌کالا",
        )
        for key, value in [
            ("digikala_commission_percent", "24"),
            ("digikala_processing_percent", "7"),
            ("digikala_processing_floor", "36000"),
            ("digikala_vat_percent", "10"),
            ("digikala_floor_taxable_part", "18000"),
        ]:
            AppSetting.objects.create(key=key, value=value, label=key)

    def line(self, when, pack=5, brand=None, price=650000, qty=2):
        p = ProductCode.objects.create(
            brand=brand or self.brand, code=f"P-{SaleLine.objects.count()}-{pack}-{when}",
            title="arbitrary", pack_qty=pack, active=True,
        )
        ps = ProductSize.objects.create(
            product=p, size=self.size, active=True,
            default_sale_price=price, unit_cost=76000,
        )
        day, _ = SaleDay.objects.get_or_create(date=when)
        return SaleLine.objects.create(
            day=day, product_size=ps, quantity=qty, sale_price=price,
        )

    def test_exact_three_dates_all_brands_only_five_pack(self):
        self.assertEqual((START, END), (date(2026,11,26), date(2026,11,28)))
        for day in [START, date(2026,11,27), END]:
            for brand in [self.brand, self.takvin]:
                with self.subTest(day=day, brand=brand):
                    line = self.line(day, brand=brand)
                    snap = snapshot_sale_line(line)
                    self.assertEqual(snap.pack_qty, 5)
                    self.assertEqual(snap.digikala_fee_unit, 183625)
                    self.assertEqual(sale_line_metrics(line)["digikala_fee"], 367250)
                    self.assertEqual(sale_line_metrics(line)["cogs"], snap.unit_cost * 10)
                    self.assertEqual(sale_line_metrics(line)["gross"], 1300000)
        for when in [date(2026,11,25),date(2026,11,29)]:
            line = self.line(when)
            self.assertEqual(snapshot_sale_line(line).digikala_fee_unit, 219375)
        for pack in [1,3,4,6]:
            line = self.line(START,pack=pack)
            self.assertEqual(snapshot_sale_line(line).digikala_fee_unit, 219375)
        self.assertFalse(applies_to(None, 5))
        self.assertFalse(applies_to(START, "NaN"))

    def test_old_snapshot_does_not_mask_new_report_commission(self):
        line = self.line(START)
        snap = snapshot_sale_line(line)
        snap.digikala_fee_unit = 219375
        snap.save(update_fields=["digikala_fee_unit"])
        line.refresh_from_db()
        m = sale_line_metrics(line)
        self.assertEqual(m["digikala_fee"], 367250)
        self.assertEqual(m["profit"], m["gross"] - m["digikala_fee"] - m["cogs"])

    def test_dry_run_apply_and_idempotent_ledger_preservation(self):
        line = self.line(START)
        snap = snapshot_sale_line(line)
        snap.digikala_fee_unit = 219375
        snap.save(update_fields=["digikala_fee_unit"])
        entry = AccountEntry.objects.create(
            date=START, account=self.account,
            delta=(650000-219375)*2,
            title="initial", reference=f"sale:{line.id}:digikala",
            entry_type="sale", note="unchanged",
        )
        old=(line.quantity,line.sale_price,snap.unit_cost,snap.pack_qty)
        output=StringIO()
        call_command("reprice_5pack_digikala_v155",stdout=output)
        self.assertIn("SNAPSHOT_UPDATES=1",output.getvalue())
        self.assertIn("LEDGER_UPDATES=1",output.getvalue())
        snap.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(snap.digikala_fee_unit,219375)
        self.assertEqual(entry.delta,(650000-219375)*2)
        call_command("reprice_5pack_digikala_v155",apply=True,stdout=StringIO())
        snap.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(snap.digikala_fee_unit,183625)
        self.assertEqual(entry.delta,(650000-183625)*2)
        self.assertEqual((line.quantity,line.sale_price,snap.unit_cost,snap.pack_qty),old)
        self.assertEqual(entry.title,"initial")
        self.assertEqual(entry.note,"unchanged")
        self.assertEqual(AccountEntry.objects.count(),1)
        out=StringIO()
        call_command("reprice_5pack_digikala_v155",apply=True,stdout=out)
        self.assertIn("SNAPSHOT_UPDATES=0",out.getvalue())
        self.assertIn("LEDGER_UPDATES=0",out.getvalue())
        call_command("reprice_5pack_digikala_v155",verify=True,stdout=StringIO())

    def test_non_campaign_existing_ledger_untouched(self):
        line=self.line(date(2026,11,29))
        snap=snapshot_sale_line(line)
        acc=AccountEntry.objects.create(
            date=line.day.date,account=self.account,
            delta=123,title="keep",reference=f"sale:{line.pk}:digikala",entry_type="sale",
        )
        call_command("reprice_5pack_digikala_v155",apply=True,stdout=StringIO())
        acc.refresh_from_db()
        snap.refresh_from_db()
        self.assertEqual(acc.delta,123)
        self.assertEqual(snap.digikala_fee_unit,219375)
