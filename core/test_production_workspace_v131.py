"""V131 isolated DB tests: UI renders full legacy form payload, no account/stock writes."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from core import material_report_ui_v131 as ui, material_report_v23 as posting
from core.models import (
    AppSetting, Brand, BusinessPayment, Color, ExcelManualRow, MaterialReportBlock,
    MaterialReportOutputApplied, RawMaterialStock, Size, StockBalance, StockLocation
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

    def test_only_main_get_route_changed_and_original_post_routes_unchanged(self):
        self.assertIs(resolve("/material-report/").func, ui.material_report)
        self.assertIs(resolve(f"/material-report/{self.block.id}/save/").func, posting.material_block_save)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply/").func, posting.material_block_apply_materials)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply-color/").func, posting.material_block_apply_color)
        self.assertIs(resolve(f"/material-report/{self.block.id}/apply-output/").func, posting.material_block_apply_output)

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
        open_response = self.client.get(reverse("material_report"), {"mode": "open"})
        self.assertEqual(open_response.status_code, 200)
        self.assertContains(open_response, "P-old")

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
