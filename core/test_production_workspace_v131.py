"""V131 isolated DB tests: UI renders full legacy form payload, no account/stock writes."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from core import material_report_ui_v131 as ui, material_report_v23 as posting
from core.models import (
    AppSetting, Brand, BusinessPayment, Color, ExcelManualRow, MaterialReportBlock,
    MaterialReportOutputApplied, MaterialReportConsumption, RawMaterialStock, Size, StockBalance, StockLocation
)


class ProductionWorkspaceV131Tests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="v131-test", password="test-only")
        self.client.force_login(user)
        self.brand = Brand.objects.create(name="دارما")
        self.color = Color.objects.create(name="صورتی")
        self.home = StockLocation.objects.create(key="home", title="خانه")
        self.khorshid = StockLocation.objects.create(key="khorshid", title="خورشید")
        Size.objects.bulk_create([
            Size(name=name, sort_order=i)
            for i, name in enumerate(("M", "L", "XL", "XXL", "3XL", "4XL"), 1)
        ])
        AppSetting.objects.create(key="pedram_dozen_wage", label="مزد", value="110000")
        self.block = MaterialReportBlock.objects.create(
            date=date(2026, 10, 25), title="P8 + W1", brand=self.brand,
            input_data={
                "_meta": {"active_material_keys": ["black", "white", "navy", "pink", "cream"]},
                "pink": {
                    "fabric_code": "P8", "weight": "20", "cut": "760",
                    "elastic16_key": "pink", "elastic16": "2.5",
                    "elastic25_key": "pink", "elastic25": "2.5",
                    "remain16": "", "remain25": "",
                },
                "white": {
                    "fabric_code": "W1", "weight": "21", "cut": "755",
                    "elastic16_key": "white", "elastic16": "2.5",
                    "elastic25_key": "cream", "elastic25": "2.5",
                    "remain16": "", "remain25": "",
                },
            },
            output_data={
                "pink": {"m": "30", "xl": "20",
                         "_delivery_parts": {"m": ["20", "10", ""], "xl": ["20", "", ""]}},
                "white": {"m": "0", "xl": "0"},
            }
        )
        MaterialReportOutputApplied.objects.create(
            block=self.block, model_key="pink", size_key="m", quantity=30
        )
        MaterialReportOutputApplied.objects.create(
            block=self.block, model_key="pink", size_key="xl", quantity=20
        )

    def _visible_codes(self, response):
        return {
            row["code"]
            for editor in response.context["editors"]
            for row in editor["rows"]
        }

    def test_only_main_get_route_changed_and_original_post_routes_unchanged(self):
        self.assertIs(resolve("/material-report/").func, ui.material_report)
        self.assertIs(resolve(f"/material-report/{self.block.id}/save/").func, posting.material_block_save)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply/").func, posting.material_block_apply_materials)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply-color/").func, posting.material_block_apply_color)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply-output/").func, posting.material_block_apply_output)
        from core import material_report_v20 as legacy
        self.assertIs(resolve(f"/material-report/{self.block.id}/delete/").func, legacy.material_block_delete)

    def test_two_fabric_codes_same_sheet_without_losing_other_color_fields(self):
        editor = ui._editor(self.block)
        self.assertEqual({row["code"] for row in editor["rows"]}, {"P8", "W1"})
        self.assertEqual(len(editor["rows"]), 2)
        pink = next(row for row in editor["rows"] if row["code"] == "P8")
        self.assertEqual(pink["remaining"], 710)
        self.assertEqual(pink["entered"], 50)
        self.assertEqual(pink["applied"], 50)
        self.assertEqual(len(pink["sizes"]), 6)
        self.assertTrue(all(len(size["parts"]) == 3 for size in pink["sizes"]))
        names = {part["name"] for row in editor["rows"] for size in row["sizes"] for part in size["parts"]}
        self.assertIn("out_pink_m_1", names)
        self.assertIn("out_white_m_1", names)
        self.assertIn("out_pink_4xl_3", names)
        self.assertIn("in_white_elastic25_key",
                      {field["name"] for row in editor["rows"] for field in row["fields"]})

    def test_page_is_read_only_and_contains_complete_linked_form(self):
        before = {
            "stock": list(StockBalance.objects.values_list("pk", "qty")),
            "block": (self.block.input_data.copy(), self.block.output_data.copy()),
            "payments": BusinessPayment.objects.count(),
            "tailor": list(ExcelManualRow.objects.values_list("pk", "amount")),
            "applied": list(MaterialReportOutputApplied.objects.values_list("pk", "quantity")),
        }
        response = self.client.get(reverse("material_report"), {"report_month": "1405/08"})
        self.assertEqual(response.status_code, 200)
        page = response.content.decode("utf-8")
        for item in (
            "P8", "W1", "کل برش", "in_pink_fabric_code", "in_white_fabric_code",
            'name="out_pink_m_1"', 'name="out_pink_m_2"', 'name="out_pink_m_3"',
            'name="out_pink_4xl_3"', 'name="out_white_m_1"',
            'name="delivery_destination"', 'value="home"', 'value="khorshid"',
            'form="material-form-', "اعمال مصرف همین رنگ", "فقط ذخیره اطلاعات",
        ):
            self.assertIn(item, page, item)
        self.block.refresh_from_db()
        after = {
            "stock": list(StockBalance.objects.values_list("pk", "qty")),
            "block": (self.block.input_data.copy(), self.block.output_data.copy()),
            "payments": BusinessPayment.objects.count(),
            "tailor": list(ExcelManualRow.objects.values_list("pk", "amount")),
            "applied": list(MaterialReportOutputApplied.objects.values_list("pk", "quantity")),
        }
        self.assertEqual(before, after)

    def test_month_scoping_and_separate_open_work_tab(self):
        older = MaterialReportBlock.objects.create(
            date=date(2026, 10, 1), title="Older 1405/07", brand=self.brand,
            input_data={"pink": {"fabric_code": "P-old", "weight": "20", "cut": "760"}},
            output_data={},
        )
        response = self.client.get(reverse("material_report"), {"report_month": "1405/08"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "P8")
        self.assertNotContains(response, "P-old")
        archive_response = self.client.get(reverse("material_report"), {"mode": "archive"})
        self.assertEqual(archive_response.status_code, 200)
        self.assertContains(archive_response, "P-old")
        self.assertNotIn("P8", self._visible_codes(archive_response))
        self.assertContains(archive_response, "ماه‌های گذشته")
        self.assertNotContains(archive_response, "کارهای باز")

    def test_empty_new_sheet_allows_each_base_color_and_preserves_schema(self):
        new = MaterialReportBlock.objects.create(
            date=date(2026, 10, 26), title="New", brand=self.brand,
            input_data={"_meta": {"active_material_keys": list(posting.BASE_KEYS)}},
            output_data={},
        )
        editor = ui._editor(new)
        self.assertEqual({x["key"] for x in editor["rows"]}, set(posting.BASE_KEYS))
        self.assertEqual(len(editor["rows"]), 5)
        self.assertEqual(len(editor["hidden_fields"]), 0)

    def test_months_are_isolated_not_one_combined_previous_sheet_list(self):
        MaterialReportBlock.objects.create(
            date=date(2026, 10, 1), title="October", brand=self.brand,
            input_data={"pink": {"fabric_code": "OLD-07", "weight": "20", "cut": "700"}},
            output_data={},
        )
        MaterialReportBlock.objects.create(
            date=date(2026, 9, 1), title="September", brand=self.brand,
            input_data={"white": {"fabric_code": "OLD-06", "weight": "20", "cut": "700"}},
            output_data={},
        )
        october = self.client.get(reverse("material_report"), {
            "mode": "archive", "report_month": "1405/07",
        })
        self.assertEqual(october.status_code, 200)
        self.assertContains(october, "OLD-07")
        self.assertNotContains(october, "OLD-06")
        self.assertNotIn("P8", self._visible_codes(october))
        september = self.client.get(reverse("material_report"), {
            "mode": "archive", "report_month": "1405/06",
        })
        self.assertEqual(september.status_code, 200)
        self.assertContains(september, "OLD-06")
        self.assertNotContains(september, "OLD-07")
        self.assertNotIn("P8", self._visible_codes(september))
        self.assertContains(september, "data-color-filter=\"white\"")

    def test_per_color_material_applied_badge_and_no_bulk_apply(self):
        MaterialReportConsumption.objects.create(
            block=self.block, kind="fabric", material_key="pink",
            quantity=Decimal("20"), variant=""
        )
        response = self.client.get(reverse("material_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "prod131-mat-state is-applied")
        self.assertContains(response, "prod131-mat-state is-unapplied")
        self.assertContains(response, "اعمال مصرف همین رنگ")
        self.assertNotContains(response, "اعمال مصرف کل صورت")
        self.assertContains(response, "data-surplus=")

    def test_live_fabric_elastic_and_wage_cost_in_total_and_color_report(self):
        stocks = [
            ("fabric", "pink", "", "20", 2_000_000),
            ("elastic", "pink", "16", "10", 2_400_000),
            ("elastic", "pink", "25", "10", 2_400_000),
        ]
        for kind, key, variant, quantity, unit_price in stocks:
            RawMaterialStock.objects.create(
                kind=kind, material_key=key, variant=variant,
                location="tailor", title="test-"+key, quantity=Decimal(quantity),
                unit_price=unit_price,
            )
        posting._reset_request_caches()
        rolls = ui._roll_entries(self.block)
        pink = next(row for row in rolls if row["code"] == "P8")
        expected_wage = posting.v20._wage_for_pieces(760, 110000)
        expected = 20*2_000_000 + 5*2_400_000 + expected_wage
        self.assertEqual(pink["cost_total"], expected)
        self.assertEqual(pink["cost_per_piece"], posting.round_money(Decimal(expected)/760))
        total = ui._totals([self.block])
        self.assertEqual(total["cut"], 1515)
        self.assertEqual(total["cost_total"], sum(row["cost_total"] for row in rolls))
        self.assertEqual(total["average_unit_cost"], posting.round_money(Decimal(total["cost_total"])/1515))
        response = self.client.get(reverse("material_report"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"]["cost_total"], total["cost_total"])
        self.assertContains(response, "data-cost-total=")
        self.assertContains(response, "میانگین بهای تمام‌شده هر شورت")


    def test_weight_adjusted_20kg_yield_excludes_missing_or_zero_weight(self):
        # 684 pieces from 17.73kg is better yield than 760 from 20kg.
        raw = self.block.input_data
        raw["pink"]["weight"] = "17.73"
        raw["pink"]["cut"] = "684"
        raw["white"]["weight"] = "20"
        raw["white"]["cut"] = "760"
        self.block.input_data = raw
        self.block.save(update_fields=["input_data"])
        totals = ui._totals([self.block])
        expected = posting.round_money(
            Decimal("1444") * Decimal("20") / Decimal("37.73")
        )
        self.assertEqual(totals["yield_per_20kg"], expected)
        self.assertNotEqual(totals["yield_per_20kg"], totals["average_cut"])

        # A roll with unknown weight must not distort normalized yield.
        raw["white"]["weight"] = ""
        self.block.input_data = raw
        self.block.save(update_fields=["input_data"])
        totals = ui._totals([self.block])
        self.assertEqual(
            totals["yield_per_20kg"],
            posting.round_money(Decimal("684") * Decimal("20") / Decimal("17.73"))
        )

    def test_material_status_filters_use_fabric_consumption_not_delivery_sync(self):
        from pathlib import Path
        from django.conf import settings
        MaterialReportConsumption.objects.create(
            block=self.block, kind="fabric", material_key="pink",
            quantity=Decimal("17.73"), variant=""
        )
        response = self.client.get(reverse("material_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-material-filter="all"')
        self.assertContains(response, 'data-material-filter="unapplied"')
        self.assertContains(response, 'data-material-filter="applied"')
        self.assertContains(response, 'data-material-status="applied"')
        self.assertContains(response, 'data-material-status="unapplied"')
        self.assertNotContains(response, "تحویل هماهنگ")
        self.assertContains(response, "بازده برش معادل ۲۰ کیلو")
        self.assertContains(response, "محدوده: همه رنگ‌ها")
        rows = ui._editor(self.block)["rows"]
        self.assertTrue(next(x for x in rows if x["key"] == "pink")["material_applied"])
        self.assertFalse(next(x for x in rows if x["key"] == "white")["material_applied"])
        script = (Path(settings.BASE_DIR) / "core/static/core/production_workspace_v131.js").read_text("utf-8")
        for marker in ("selectedMaterial", "matchesMaterial", "validWeight", "validCut", "materialMeaningful"):
            self.assertIn(marker, script)


    def test_new_sheet_color_chooser_creates_only_selected_blank_editor(self):
        brand = self.brand
        for key in ("black", "white", "navy", "pink", "cream"):
            with self.subTest(key=key):
                before = MaterialReportBlock.objects.count()
                response = self.client.post(reverse("material_report"), {
                    "brand": str(brand.pk), "title": f"Selected {key}",
                    "date": "1405/08/13", "initial_material_key": key,
                })
                self.assertEqual(response.status_code, 302)
                self.assertEqual(MaterialReportBlock.objects.count(), before + 1)
                new = MaterialReportBlock.objects.latest("pk")
                self.assertEqual(new.input_data["_meta"]["initial_material_key"], key)
                self.assertEqual(len(ui._editor(new)["rows"]), 1)
                self.assertEqual(ui._editor(new)["rows"][0]["key"], key)
                self.assertFalse(new.stock_consumptions.exists())
                self.assertFalse(new.output_applications.exists())
                self.assertIn(f"#block-{new.pk}", response.url)

    def test_new_sheet_color_chooser_lists_material_catalog_and_rejects_bad_keys(self):
        RawMaterialStock.objects.create(
            kind="fabric", material_key="teal", variant="", location="tailor",
            title="فیروزه‌ای", quantity=Decimal("20"), unit_price=2100000,
        )
        response = self.client.get(reverse("material_report"))
        self.assertContains(response, 'name="initial_material_key"')
        self.assertContains(response, '<option value="pink">صورتی</option>', html=False)
        self.assertContains(response, '<option value="teal">', html=False)
        self.assertContains(response, 'prod131-create-color')
        response = self.client.post(reverse("material_report"), {
            "brand": str(self.brand.pk), "date": "1405/08/13",
            "initial_material_key": "teal",
        })
        self.assertEqual(response.status_code, 302)
        new = MaterialReportBlock.objects.latest("pk")
        self.assertEqual(ui._editor(new)["rows"][0]["key"], "teal")
        self.assertEqual(len(ui._editor(new)["rows"]), 1)
        self.assertIn("teal", new.input_data["_meta"]["active_material_keys"])

        count = MaterialReportBlock.objects.count()
        failed = self.client.post(reverse("material_report"), {
            "brand": str(self.brand.pk), "date": "1405/08/13",
            "initial_material_key": "unrecognized-material-unsafe",
        })
        self.assertEqual(failed.status_code, 302)
        self.assertEqual(MaterialReportBlock.objects.count(), count)

    def test_delete_unapplied_whole_sheet_and_protect_applied_material_or_output(self):
        from core import material_report_v20 as legacy
        self.assertIs(resolve(reverse("material_block_delete", args=[self.block.pk])).func, legacy.material_block_delete)
        blank = MaterialReportBlock.objects.create(
            date=date(2026, 10, 25), brand=self.brand, title="Wrong black",
            input_data={"_meta": {"active_material_keys": list(posting.BASE_KEYS),
                                   "initial_material_key": "black"}},
            output_data=posting._blank_output_data_for_brand(self.brand),
        )
        response = self.client.get(reverse("material_report"))
        self.assertContains(response, f'form="prod131-delete-form-{blank.pk}"')
        self.assertContains(response, "حذف کل صورت")
        before_stock = list(StockBalance.objects.values_list("pk", "qty"))
        deleted = self.client.post(reverse("material_block_delete", args=[blank.pk]))
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(MaterialReportBlock.objects.filter(pk=blank.pk).exists())
        self.assertEqual(before_stock, list(StockBalance.objects.values_list("pk", "qty")))

        # Existing applied delivery must never be silently reversed or deleted.
        protected = self.client.post(reverse("material_block_delete", args=[self.block.pk]))
        self.assertEqual(protected.status_code, 302)
        self.assertTrue(MaterialReportBlock.objects.filter(pk=self.block.pk).exists())
        self.assertEqual(self.block.output_applications.filter(quantity__gt=0).count(), 2)

        material = MaterialReportConsumption.objects.create(
            block=self.block, kind="fabric", material_key="pink",
            quantity=Decimal("20"), variant="",
        )
        editor = ui._editor(self.block)
        self.assertFalse(editor["deletable"])
        blocked = self.client.post(reverse("material_block_delete", args=[self.block.pk]))
        self.assertEqual(blocked.status_code, 302)
        self.assertTrue(MaterialReportConsumption.objects.filter(pk=material.pk).exists())

    def test_surplus_not_clamped_away_in_visual_row(self):
        self.block.output_data["pink"]["m"] = "790"
        self.block.save(update_fields=["output_data"])
        rows = ui._editor(self.block)["rows"]
        pink = next(row for row in rows if row["key"] == "pink")
        self.assertEqual(pink["remaining"], 0)
        self.assertEqual(pink["surplus"], 50)
        response = self.client.get(reverse("material_report"))
        self.assertContains(response, "is-surplus")
