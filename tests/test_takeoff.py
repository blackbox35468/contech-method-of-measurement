"""Tests for the CMM take-off aids, quantity policy and reference checker.

    python3 -m unittest discover -s tests
"""

import copy
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "takeoff"))

import build_refs  # noqa: E402
import check  # noqa: E402
from takeoff_lib import (  # noqa: E402
    GUIDANCE,
    POLICY,
    REFERENCE_DIR,
    billed_quantity,
    load_json,
    load_release,
    parse_times,
    rounding_rule,
    square_row,
)

RELEASE, DIGEST = load_release()
POLICY_DOC = load_json(POLICY)
GUIDANCE_DOC = load_json(GUIDANCE)
REFERENCES = {path.stem.split("-")[0] + "-" + path.stem.split("-")[1]: load_json(path) for path in REFERENCE_DIR.glob("*.json")}


class ExclusionRefsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = build_refs.build()
        cls.by_code = {record["code"]: record for record in cls.document["items"]}

    def test_covers_every_item_and_pins_the_release(self):
        self.assertEqual(len(self.by_code), RELEASE["counts"]["measured_items"])
        self.assertEqual(self.document["cmm_canonical_sha256"], DIGEST)
        self.assertFalse(self.document["canonical"])

    def test_checked_in_file_is_current(self):
        self.assertEqual(build_refs.EXCLUSION_REFS.read_text(), build_refs.render(self.document))

    def test_each_reference_quotes_its_source_sentence(self):
        refs = self.by_code["10.B.1"]["exclusion_refs"]
        self.assertIn({"items": ["10.F.2"], "sections": [], "source": "Disposal, measured at 10.F.2."}, refs)
        self.assertIn(["11", "12", "13"], [ref["sections"] for ref in refs])

    def test_retired_items_point_to_successors(self):
        retired = [record for record in self.document["items"] if record["status"] == "retired"]
        self.assertEqual(len(retired), 3)
        self.assertTrue(all(record.get("successor_item_codes") for record in retired))


class QuantityPolicyTests(unittest.TestCase):
    def rule(self, code, unit, kind):
        return rounding_rule(POLICY_DOC, code, unit, kind)

    def test_billed_rounding(self):
        cases = [
            ("0.4", "10.F.2", "m3", "volume", "1"),
            ("2.5", "10.F.2", "m3", "volume", "3"),
            ("2.49", "10.B.1", "m", "length", "2"),
            ("1.8076", "31.B.1", "m", "length", "2"),
            ("1.005", "13.A.1", "t", "mass", "1.01"),
            ("3", "14.F.3", "nr", "count", "3"),
        ]
        for squared, code, unit, kind, billed in cases:
            with self.subTest(squared=squared, unit=unit):
                self.assertEqual(billed_quantity(Fraction(Decimal(squared)), self.rule(code, unit, kind)), Decimal(billed))

    def test_counts_are_never_rounded(self):
        with self.assertRaises(ValueError):
            billed_quantity(Fraction(5, 2), self.rule("14.F.3", "nr", "count"))

    def test_item_override_wins(self):
        policy = copy.deepcopy(POLICY_DOC)
        policy["billing"]["items"]["10.B.1"] = {"method": "half_up", "decimals": 1}
        self.assertEqual(billed_quantity(Fraction(Decimal("19.24")), rounding_rule(policy, "10.B.1", "m", "length")), Decimal("19.2"))

    def test_timesing_is_fractions_with_dotting_on(self):
        self.assertEqual(parse_times("1+2"), 3)
        self.assertEqual(parse_times("1/2"), Fraction(1, 2))
        with self.assertRaises(ValueError):
            parse_times("0.5")

    def test_deduction_rows_are_negative(self):
        self.assertEqual(square_row({"times": ["2"], "dims": [1.80, 1.20], "deduct": True}), Fraction("-4.32"))


class GuidanceTests(unittest.TestCase):
    def test_guidance_passes(self):
        self.assertEqual(check.check_guidance(GUIDANCE_DOC, RELEASE, DIGEST, REFERENCES), [])

    def test_quote_must_exist_in_cmm(self):
        guidance = copy.deepcopy(GUIDANCE_DOC)
        guidance["guidance"][0]["cmm_source"]["quote"] = "Disposal is always required."
        self.assertTrue(any("quote not found" in e for e in check.check_guidance(guidance, RELEASE, DIGEST, REFERENCES)))

    def test_gap_or_source_is_required(self):
        guidance = copy.deepcopy(GUIDANCE_DOC)
        del guidance["guidance"][6]["gap"]
        self.assertTrue(any("cmm_source quote or state the gap" in e for e in check.check_guidance(guidance, RELEASE, DIGEST, REFERENCES)))

    def test_evidence_must_exist(self):
        guidance = copy.deepcopy(GUIDANCE_DOC)
        guidance["guidance"][0]["evidence"] = [{"reference": "GS-01", "entry": "E99"}]
        self.assertTrue(any("unknown entry" in e for e in check.check_guidance(guidance, RELEASE, DIGEST, REFERENCES)))


class ReferenceCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = {record["code"]: record for record in build_refs.build()["items"]}

    def run_checker(self, document):
        errors, _ = check.check_reference(document, RELEASE, DIGEST, self.refs, GUIDANCE_DOC, POLICY_DOC)
        return errors

    def entry(self, document, entry_id):
        return check.entries_of(document)[entry_id]

    def test_references_pass(self):
        for name, document in REFERENCES.items():
            with self.subTest(reference=name):
                self.assertEqual(self.run_checker(document), [])

    def test_strip_excavation_measured_as_volume_is_rejected(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        excavation = self.entry(document, "E1")
        excavation["rows"] = [{"times": [], "dims": [19.24, 0.60, 0.60]}]
        excavation["squared"], excavation["billed"] = "6.9264", "7"
        self.assertTrue(any("3 dimension(s) for a m item" in e for e in self.run_checker(document)))

    def test_wrong_square_is_rejected(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        self.entry(document, "E11")["squared"] = "54.834"
        self.assertTrue(any("squares to" in e for e in self.run_checker(document)))

    def test_dimension_must_match_its_waste_calc(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        self.entry(document, "E2")["rows"][0]["dims"][0] = 20.00
        self.assertTrue(any("does not match WC1" in e for e in self.run_checker(document)))

    def test_missing_particular_is_rejected(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        del self.entry(document, "E4")["particulars"]["sec.11.req.concrete_strength"]
        self.assertTrue(any("particulars not stated" in e for e in self.run_checker(document)))

    def test_guided_companion_must_be_measured_or_explained(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        document["groups"][0]["entries"] = [e for e in document["groups"][0]["entries"] if e["id"] != "E2"]
        self.assertTrue(any("coverage CG-01: measure 10.F.2" in e for e in self.run_checker(document)))

    def test_one_of_needs_a_choice_or_a_reason(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        del document["not_required"]["CG-03"]
        self.assertTrue(any("coverage CG-03" in e for e in self.run_checker(document)))

    def test_unguided_exclusions_are_advisory_only(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        del document["not_required"]["14.G.1"]
        _, notes = check.check_reference(document, RELEASE, DIGEST, self.refs, GUIDANCE_DOC, POLICY_DOC)
        self.assertEqual(self.run_checker(document), [])
        self.assertTrue(any(note.startswith("14.A.2 -> 14.G.1") for note in notes))

    def test_corner_window_counted_twice_is_rejected_by_its_billed_figure(self):
        document = copy.deepcopy(REFERENCES["CW-01"])
        self.entry(document, "E1")["rows"] = [{"times": ["2"], "dims": []}]
        self.assertTrue(any("squares to 2.0, not 1" in e for e in self.run_checker(document)))

    def test_fractional_count_is_rejected(self):
        document = copy.deepcopy(REFERENCES["CW-01"])
        self.entry(document, "E1")["rows"] = [{"times": ["1/2"], "dims": []}]
        self.entry(document, "E1")["squared"] = "0.5"
        self.assertTrue(any("not a whole number" in e for e in self.run_checker(document)))

    def test_anded_entry_needs_matching_unit(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        self.entry(document, "E5")["anded_with"] = "E2"
        self.assertTrue(any("different unit" in e for e in self.run_checker(document)))

    def test_bad_waste_calc_is_rejected(self):
        document = copy.deepcopy(REFERENCES["GS-01"])
        document["waste_calcs"][0]["result_mm"] = 20000
        self.assertTrue(any(e.startswith("WC1:") for e in self.run_checker(document)))


if __name__ == "__main__":
    unittest.main()
