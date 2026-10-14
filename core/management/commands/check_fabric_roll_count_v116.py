"""Read-only fabric roll audit, with source sheet codes for each Darma color."""
from django.core.management.base import BaseCommand
from types import SimpleNamespace


def _test_white_pink_roll_semantics():
    """Pure in-memory cases; never insert/delete business rows."""
    class Outputs:
        def __init__(self, rows=()):
            self.rows = rows

        def all(self):
            return self.rows

    def sheet(color, code="", cut=0, weight="", applied=0, brand="دارما"):
        return SimpleNamespace(
            brand=SimpleNamespace(name=brand),
            input_data={color: {
                "fabric_code": code, "cut": str(cut), "weight": str(weight),
            }},
            output_applications=Outputs([
                SimpleNamespace(model_key=color, quantity=applied)
            ] if applied else []),
        )

    samples = [
        sheet("white", "W-01", cut=8, applied=8),  # completed sheet still registers a roll
        sheet("white", "W-02", cut=10, applied=4),
        sheet("white", "W-03", weight="2.1"),
        sheet("white", "W-04"),  # an explicitly saved code with incomplete quantities
        sheet("white", "W-02", cut=0),  # reused code counts once
        sheet("white", "", cut=3, weight=1),  # uncoded entry is never an invented roll
        sheet("pink", "P-01"),
        sheet("pink", "P-02", cut=7, applied=7),
        sheet("pink", "P-03"),
        sheet("pink", "P-04", weight="4"),
        sheet("pink", "P-04", cut=2),
        sheet("pink", "", weight=2),
        sheet("white", "W-05", brand="Novani"),  # other brands are excluded
    ]
    result = {row["key"]: row for row in report._summarize_open_base_colors(samples)}
    white, pink = result["white"], result["pink"]
    if (white["roll_count"], white["rolls_without_code"]) != (4, 1):
        raise RuntimeError(f"White count/uncoded regression: {white!r}")
    if (white["expected"], white["delivered"], white["pending"]) != (13, 4, 9):
        raise RuntimeError(f"White open-delivery work regression: {white!r}")
    if (pink["roll_count"], pink["rolls_without_code"]) != (4, 1):
        raise RuntimeError(f"Pink count/uncoded regression: {pink!r}")
    if (pink["expected"], pink["delivered"], pink["pending"]) != (2, 0, 2):
        raise RuntimeError(f"Pink open-delivery work regression: {pink!r}")
    if any(result[key]["roll_count"] for key in ("black", "navy", "cream")):
        raise RuntimeError("Unexpected registration leakage between material colors")


from core import material_report_v92 as report
from core.models import MaterialReportBlock


class Command(BaseCommand):
    help = "Audit registered fabric codes vs uncoded material sheets; never change stock."

    def handle(self, *args, **kwargs):
        _test_white_pink_roll_semantics()
        self.stdout.write("IN-MEMORY WHITE/PINK = 4 UNIQUE ROLLS EACH; NO UNCoded INFLATION")
        blocks = list(
            MaterialReportBlock.objects.select_related("brand")
            .prefetch_related("output_applications").all()
        )
        rows = report._summarize_open_base_colors(blocks)
        for result in rows:
            codes = {}
            missing = []
            for block in blocks:
                if block.brand.name != "دارما":
                    continue
                values = (block.input_data or {}).get(result["key"]) or {}
                code = str(values.get("fabric_code") or "").strip()
                cut = max(0, report.v23.v20._int(values.get("cut")))
                weight = max(report._decimal(values.get("weight")), report.Decimal("0"))
                if code:
                    codes.setdefault(code, []).append(block.id)
                elif cut > 0 or weight > 0:
                    missing.append(block.id)
            if result["roll_count"] != len(codes):
                raise RuntimeError(f"Count mismatch for {result['key']}")
            self.stdout.write(
                f"{result['label']} | unique_registered_codes={len(codes)} "
                f"| missing_code_sheets={len(missing)} "
                f"| open_cut={result['expected']} "
                f"| applied_output={result['delivered']} "
                f"| pending_output={result['pending']}"
            )
            self.stdout.write("  coded_sheets="+repr(codes))
            self.stdout.write("  uncoded_sheet_ids="+repr(missing))
        self.stdout.write(self.style.SUCCESS("SUCCESS: FABRIC ROLL COUNT AUDIT V116 PASSED"))
