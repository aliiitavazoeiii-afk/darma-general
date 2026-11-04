"""Isolated read-only tests for selected-month and all-history production analytics."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from core import material_report_ui_v131 as monthly_ui
from core import material_report_overall_v137 as overall
from core import material_report_v23 as v23
from core.models import (
    AppSetting, Brand, MaterialReportBlock, MaterialReportConsumption,
    MaterialReportOutputApplied, MaterialReportOutputLocation,
    RawMaterialStock, StockLocation, Size, StockBalance, BusinessPayment
)


class ProductionOverallV137Tests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="overall-v137", password="no-secret-data")
        self.client.force_login(user)
        self.brand = Brand.objects.create(name="دارما")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        StockLocation.objects.create(key="khorshid", title="خورشید")
        Size.objects.bulk_create([
            Size(name=name, sort_order=i)
            for i, name in enumerate(("M", "L", "XL", "XXL", "3XL", "4XL"), 1)
        ])
        AppSetting.objects.create(key="pedram_dozen_wage", label="مزد", value="110000")
        self.newer = MaterialReportBlock.objects.create(
            date=date(2026, 10, 25), title="Pink P8", brand=self.brand,
            input_data={
                "_meta": {"active_material_keys": list(v23.BASE_KEYS)},
                "pink": {
                    "fabric_code": "P8", "weight": "20", "cut": "760",
                    "elastic16": "2.5", "elastic16_key": "pink",
                    "elastic25": "2.5", "elastic25_key": "pink",
                    "remain16": "", "remain25": "",
                },
            },
            output_data={"pink": {"m": "30", "xl": "20"}}
        )
        self.older = MaterialReportBlock.objects.create(
            date=date(2026, 10, 1), title="Navy N1", brand=self.brand,
            input_data={
                "_meta": {"active_material_keys": list(v23.BASE_KEYS)},
                "navy": {"fabric_code": "N1", "weight": "17.73", "cut": "684"},
            },
            output_data={"navy": {"m": "15"}}
        )
        applied_m = MaterialReportOutputApplied.objects.create(
            block=self.newer, model_key="pink", size_key="m", quantity=10
        )
        MaterialReportOutputApplied.objects.create(
            block=self.newer, model_key="pink", size_key="xl", quantity=20
        )
        MaterialReportOutputApplied.objects.create(
            block=self.older, model_key="navy", size_key="m", quantity=20
        )
        MaterialReportOutputLocation.objects.create(
            applied=applied_m, location=self.home, quantity=10
        )
        MaterialReportConsumption.objects.create(
            block=self.newer, kind="fabric", material_key="pink",
            quantity=Decimal("20"), variant=""
        )
        for kind, key, variant, qty, price in (
            ("fabric", "pink", "", "30", 2000000),
            ("elastic", "pink", "16", "10", 2400000),
            ("elastic", "pink", "25", "10", 2400000),
        ):
            RawMaterialStock.objects.create(
                kind=kind, material_key=key, variant=variant,
                location="tailor", quantity=Decimal(qty),
                unit_price=price, title=key
            )

    def _get_all(self):
        return self.client.get(reverse("material_production_overall"))

    def test_monthly_cards_are_scoped_to_month_and_overall_report_is_distinct(self):
        monthly = self.client.get(reverse("material_report"))
        self.assertEqual(monthly.status_code, 200)
        self.assertEqual(monthly.context["scope"]["cut"], 760)
        self.assertEqual(monthly.context["scope"]["weight"], Decimal("20"))
        self.assertNotIn("all_totals", monthly.context)
        self.assertContains(monthly, 'data-scope-metric="average_cost"')
        self.assertContains(monthly, 'data-countable="1"')
        self.assertContains(monthly, reverse("material_production_overall"))

        archive = self.client.get(reverse("material_report"), {
            "mode": "archive", "report_month": "1405/07"
        })
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archive.context["scope"]["cut"], 684)
        self.assertContains(archive, "بازده برش معادل ۲۰ کیلو")

        full = self._get_all()
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.context["report"]["all"]["cut"], 1444)
        self.assertEqual(full.context["report"]["all"]["rolls"], 2)
        self.assertEqual(full.context["report"]["all"]["sheets"], 2)
        self.assertContains(full, "گزارش کلی تولید")
        self.assertContains(full, "مقایسه رنگ‌ها")
        self.assertContains(full, "روند تولید ماهانه")

    def test_cost_material_consumption_followups_and_destinations_are_accurate(self):
        v23._reset_request_caches()
        report = overall.build_overall_report([self.newer, self.older])
        all_stats = report["all"]
        self.assertEqual(all_stats["weight"], Decimal("37.73"))
        self.assertEqual(all_stats["entered"], 65)
        self.assertEqual(all_stats["applied"], 50)
        self.assertEqual(all_stats["remaining"], 1379)
        self.assertEqual(all_stats["unsynced"], 20)
        self.assertEqual(all_stats["reverse_due"], 5)
        self.assertEqual(all_stats["material_applied"], 1)
        self.assertEqual(all_stats["material_pending"], 1)
        self.assertEqual(all_stats["incomplete_cost"], 1)  # navy fabric price missing
        self.assertEqual(all_stats["yield20"], v23.round_money(
            Decimal("1444") * Decimal("20") / Decimal("37.73")
        ))
        pink_cost = 20*2000000 + 5*2400000 + v23.v20._wage_for_pieces(760, 110000)
        self.assertEqual(all_stats["fabric_cost"], pink_cost - 5*2400000)
        self.assertEqual(all_stats["elastic_cost"], 5*2400000)
        self.assertEqual(all_stats["unit_cost"], v23.round_money(
            Decimal(all_stats["cost_total"]) / Decimal(1444)
        ))
        self.assertEqual(report["destinations"]["home"], 10)
        self.assertEqual(report["destinations"]["legacy_unknown"], 40)
        self.assertEqual(len(report["monthly"]), 2)
        self.assertEqual({m["cut"] for m in report["monthly"]}, {684, 760})
        self.assertEqual({c["name"] for c in report["colors"]}, {"دارما · صورتی", "دارما · سرمه‌ای"})
        m = next(row for row in report["sizes"] if row["name"] == "M")
        self.assertEqual((m["entered"], m["applied"], m["pending"]), (45, 30, 20))
        self.assertEqual(report["followup_total"], 2)
        self.assertEqual(all_stats["cost_total"],
                         all_stats["fabric_cost"] + all_stats["elastic_cost"] + all_stats["labor_cost"])

    def test_overall_view_does_not_modify_stock_ledger_payments_or_sheets(self):
        before = {
            "blocks": list(MaterialReportBlock.objects.values_list("id", "input_data", "output_data", "delivery_wage")),
            "materials": list(RawMaterialStock.objects.values_list("id", "quantity", "unit_price")),
            "consumptions": list(MaterialReportConsumption.objects.values_list("id", "quantity")),
            "applied": list(MaterialReportOutputApplied.objects.values_list("id", "quantity")),
            "balances": list(StockBalance.objects.values_list("id", "qty")),
            "payments": BusinessPayment.objects.count(),
        }
        response = self._get_all()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stock"]["tailor_fabric"], Decimal("30"))
        self.assertEqual(response.context["stock"]["tailor_elastic"], Decimal("20"))
        self.assertEqual(response.context["stock"]["warehouse_fabric"], Decimal("0"))
        after = {
            "blocks": list(MaterialReportBlock.objects.values_list("id", "input_data", "output_data", "delivery_wage")),
            "materials": list(RawMaterialStock.objects.values_list("id", "quantity", "unit_price")),
            "consumptions": list(MaterialReportConsumption.objects.values_list("id", "quantity")),
            "applied": list(MaterialReportOutputApplied.objects.values_list("id", "quantity")),
            "balances": list(StockBalance.objects.values_list("id", "qty")),
            "payments": BusinessPayment.objects.count(),
        }
        self.assertEqual(before, after)

    def test_route_and_authentication(self):
        self.assertIs(resolve("/material-report/overall/").func, overall.production_overall)
        self.client.logout()
        response = self._get_all()
        self.assertIn(response.status_code, (301, 302))
        self.assertNotIn("گزارش کلی تولید", response.content.decode("utf-8"))

    def test_zero_data_has_no_fake_unit_price_or_yield(self):
        empty = overall.build_overall_report([])
        self.assertEqual(empty["all"]["cut"], 0)
        self.assertEqual(empty["all"]["unit_cost"], 0)
        self.assertEqual(empty["all"]["yield20"], 0)
        self.assertEqual(empty["monthly"], [])
        self.assertEqual(empty["colors"], [])
        self.assertEqual(empty["followup_total"], 0)
