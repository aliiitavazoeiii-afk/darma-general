"""Dashboard chart-only regression. Uses Django's isolated test DB, never production."""
from datetime import date, timedelta

from django.test import TestCase

from .excel_dashboard_v89 import recent_paid_sale_days
from .models import Brand, DiaGallerySale, Color, ProductCode, ProductSize, SaleDay, SaleLine, Size


class DashboardChartDaysTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = date(2026, 10, 19)
        brand = Brand.objects.create(name="دارما", active=True)
        size = Size.objects.create(name="M")
        color = Color.objects.create(name="صورتی")
        product = ProductCode.objects.create(brand=brand, code="DASHBOARD-TEST", pack_qty=1)
        product_size = ProductSize.objects.create(product=product, size=size, unit_cost=10000)
        # Yesterday: positive quantity but zero price — old V89 created an
        # empty sale column and negative profit because costs/fees still apply.
        zero = SaleDay.objects.create(date=cls.today-timedelta(days=1))
        SaleLine.objects.create(day=zero, product_size=product_size, quantity=10, sale_price=0)
        # Earlier, a genuinely paid sale. Keep it.
        paid = SaleDay.objects.create(date=cls.today-timedelta(days=2))
        SaleLine.objects.create(day=paid, product_size=product_size, quantity=2, sale_price=85000)
        # Dia-only positive sale. Keep it.
        dia = SaleDay.objects.create(date=cls.today-timedelta(days=3))
        DiaGallerySale.objects.create(
            day=dia, size=size, color=color, quantity=1,
            unit_price=71000, unit_cost=60000,
        )
        # Dia Gallery uses a canonical fixed fee in the money calculations
        # even if a legacy stored unit_price is zero. Do not lose its day.
        dia_legacy = SaleDay.objects.create(date=cls.today-timedelta(days=5))
        DiaGallerySale.objects.create(
            day=dia_legacy, size=size, color=color, quantity=1,
            unit_price=0, unit_cost=60000,
        )
        # A zero-count, non-zero-price line cannot create a monetary sale.
        empty = SaleDay.objects.create(date=cls.today-timedelta(days=4))
        SaleLine.objects.create(day=empty, product_size=product_size, quantity=0, sale_price=85000)
        # Future paid sale should not enter today's chart.
        future = SaleDay.objects.create(date=cls.today+timedelta(days=1))
        SaleLine.objects.create(day=future, product_size=product_size, quantity=1, sale_price=85000)

    def test_no_zero_price_phantom_sales_day(self):
        dates = [day.date for day in recent_paid_sale_days(self.today, limit=30)]
        self.assertEqual(dates, [
            self.today-timedelta(days=5),
            self.today-timedelta(days=3),
            self.today-timedelta(days=2),
        ])

    def test_newest_limit_keeps_chronological_order(self):
        dates = [day.date for day in recent_paid_sale_days(self.today, limit=1)]
        self.assertEqual(dates, [self.today-timedelta(days=2)])

    def test_zero_gross_day_kept_in_database_for_manual_review(self):
        self.assertTrue(SaleLine.objects.filter(quantity=10, sale_price=0).exists())
