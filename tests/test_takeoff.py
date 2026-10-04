"""Tests for the CMM take-off sidecar, rounding policy and reference checker.

    python3 -m unittest discover -s tests
"""

import copy
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "takeoff"))

import build_basis  # noqa: E402
import check  # noqa: E402
from takeoff_lib import REFERENCE_DIR, billed_quantity, load_release, parse_times, square_row  # noqa: E402

REFERENCE = REFERENCE_DIR / "GS-01-garden-studio.json"


class SidecarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = build_basis.build()
        cls.by_code = {entry["code"]: entry for entry in cls.document["items"]}

    def test_covers_every_item_and_pins_the_release(self):
        release, digest = load_release()
        self.assertEqual(len(self.by_code), release["counts"]["measured_items"])
        self.assertEqual(self.document["cmm_canonical_sha256"], digest)
        self.assertFalse(self.document["canonical"])

    def test_checked_in_file_is_current(self):
        self.assertEqual(build_basis.SIDECAR.read_text(), build_basis.render(self.document))

    def test_known_measurement_bases(self):
        expected = {
            "10.B.1": "length_centreline",
            "02.A.1": "volume_gross",
            "11.B.1": "volume_plan_area_x_depth",
            "10.D.2": "volume_compacted",
            "15.A.4": "area_on_plan",
            "14.A.2": "area_on_face",
            "14.D.1": "length_centreline",
            "10.B.3": "count",
        }
        for code, basis in expected.items():
            with self.subTest(code=code):
                self.assertEqual(self.by_code[code]["basis"], basis)

    def test_item_wording_overrides_general_rules(self):
        self.assertFalse(self.by_code["13.A.2"]["laps_measured"])
        self.assertTrue(self.by_code["14.A.2"]["openings_deducted"])

    def test_exclusions_become_measured_elsewhere(self):
        entry = self.by_code["10.B.1"]
        self.assertEqual(entry["measured_elsewhere"], ["10.A.4", "10.C.1", "10.D.2", "10.F.2"])
        self.assertEqual(entry["measured_elsewhere_sections"], ["11", "12", "13"])

    def test_retired_items_point_to_successors(self):
        retired = [entry for entry in self.document["items"] if entry["status"] == "retired"]
        self.assertEqual(len(retired), 3)
        self.assertTrue(all(entry.get("successor_item_codes") for entry in retired))


class RoundingAndTimesingTests(unittest.TestCase):
    def test_billed_rounding(self):
        cases = [("0.4", "m3", "1"), ("2.5", "m3", "3"), ("2.49", "m", "2"), ("51.8348", "m2", "52"), ("1.005", "t", "1.01")]
        for squared, unit, billed in cases:
            with self.subTest(squared=squared, unit=unit):
                self.assertEqual(billed_quantity(Fraction(Decimal(squared)), unit), Decimal(billed))

    def test_timesing_is_fractions_with_dotting_on(self):
        self.assertEqual(parse_times("1+2"), 3)
        self.assertEqual(parse_times("1/2"), Fraction(1, 2))
        with self.assertRaises(ValueError):
            parse_times("0.5")

    def test_deduction_rows_are_negative(self):
        self.assertEqual(square_row({"times": ["2"], "dims": [1.80, 1.20], "deduct": True}), Fraction("-4.32"))


class ReferenceCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release, cls.digest = load_release()
        cls.basis = {entry["code"]: entry for entry in build_basis.build()["items"]}
        cls.reference = json.loads(REFERENCE.read_text())

    def run_checker(self, document):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "case.json"
            path.write_text(json.dumps(document))
            errors, _ = check.check_reference(path, self.release, self.digest, self.basis)
        return errors

    def entry(self, document, entry_id):
        return next(e for g in document["groups"] for e in g["entries"] if e["id"] == entry_id)

    def test_reference_passes(self):
        self.assertEqual(self.run_checker(self.reference), [])

    def test_strip_excavation_measured_as_volume_is_rejected(self):
        document = copy.deepcopy(self.reference)
        excavation = self.entry(document, "E1")
        excavation["rows"] = [{"times": [], "dims": [19.24, 0.60, 0.60]}]
        excavation["squared"], excavation["billed"] = "6.9264", "7"
        errors = self.run_checker(document)
        self.assertTrue(any("3 dimension(s) for a m item" in e for e in errors), errors)

    def test_wrong_square_is_rejected(self):
        document = copy.deepcopy(self.reference)
        self.entry(document, "E11")["squared"] = "54.834"
        self.assertTrue(any("squares to" in e for e in self.run_checker(document)))

    def test_dimension_must_match_its_waste_calc(self):
        document = copy.deepcopy(self.reference)
        self.entry(document, "E2")["rows"][0]["dims"][0] = 20.00
        self.assertTrue(any("does not match WC1" in e for e in self.run_checker(document)))

    def test_missing_particular_is_rejected(self):
        document = copy.deepcopy(self.reference)
        del self.entry(document, "E4")["particulars"]["sec.11.req.concrete_strength"]
        self.assertTrue(any("particulars not stated" in e for e in self.run_checker(document)))

    def test_unexplained_related_work_is_rejected(self):
        document = copy.deepcopy(self.reference)
        del document["not_required"]["10.C.1"]
        self.assertTrue(any("10.B.1 sends work to 10.C.1" in e for e in self.run_checker(document)))

    def test_anded_entry_needs_matching_unit(self):
        document = copy.deepcopy(self.reference)
        self.entry(document, "E5")["anded_with"] = "E2"
        self.assertTrue(any("different unit" in e for e in self.run_checker(document)))

    def test_bad_waste_calc_is_rejected(self):
        document = copy.deepcopy(self.reference)
        document["waste_calcs"][0]["result_mm"] = 20000
        self.assertTrue(any(e.startswith("WC1:") for e in self.run_checker(document)))


if __name__ == "__main__":
    unittest.main()
