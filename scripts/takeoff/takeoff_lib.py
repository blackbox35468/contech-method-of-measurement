"""Shared helpers for the CMM take-off aids and reference take-offs.

Everything here reads the published CMM release and never writes to it.
"""

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RELEASE = REPO / "release" / "CMM-1.0.json"
MANIFEST = REPO / "release" / "release-manifest.json"
TAKEOFF = REPO / "takeoff"
EXCLUSION_REFS = TAKEOFF / "CMM-1.0-exclusion-refs.json"
GUIDANCE = TAKEOFF / "coverage-guidance.json"
POLICY = TAKEOFF / "quantity-policy.json"
REFERENCE_DIR = TAKEOFF / "reference"

ITEM_CODE = re.compile(r"\b(\d{2}\.[A-Z]\.\d+)\b")
SECTION_REF = re.compile(r"\bsections? (\d{2}(?:(?:, | and )\d{2})*)")

# How many dimensions one row carries for each unit kind. Other sizes
# (thickness, width, depth) are stated in the description (cmm.general.02).
DIMS_PER_KIND = {"count": 0, "length": 1, "area": 2, "volume": 3}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text())


def load_release():
    release = load_json(RELEASE)
    manifest = load_json(MANIFEST)
    digest = sha256(RELEASE)
    if digest != manifest["canonical_sha256"]:
        raise SystemExit(f"CMM release checksum {digest} does not match the manifest")
    return release, digest


def items_by_code(release):
    return {
        item["code"]: item
        for section in release["sections"]
        for subsection in section["subsections"]
        for item in subsection["items"]
    }


def unit_kinds(release):
    return {unit["symbol"]: unit["kind"] for unit in release["units"]}


def refs_in(text):
    """Item codes and section codes named in a piece of CMM text."""
    codes = sorted(set(ITEM_CODE.findall(text or "")))
    sections = set()
    for match in SECTION_REF.findall(text or ""):
        sections.update(re.findall(r"\d{2}", match))
    return codes, sorted(sections)


def parse_times(factor):
    """Parse one timesing factor. Fractions only, no decimals; '2+1' is dotting on."""
    factor = str(factor).strip()
    if "." in factor:
        raise ValueError(f"timesing factor {factor!r} uses a decimal; use a fraction")
    return sum((Fraction(part) for part in factor.split("+")), Fraction(0))


def square_row(row):
    """Exact squared value of one dimension row, signed for deductions."""
    value = Fraction(1)
    for factor in row.get("times", []):
        value *= parse_times(factor)
    for dim in row.get("dims", []):
        value *= Fraction(Decimal(str(dim)))
    return -value if row.get("deduct") else value


def rounding_rule(policy, code, unit, kind):
    """The billing rule for one item: item override, then unit, then unit kind, then default."""
    rules = policy["billing"]
    return (
        rules["items"].get(code)
        or rules["units"].get(unit)
        or rules["unit_kinds"].get(kind)
        or rules["default"]
    )


def billed_quantity(squared, rule):
    """Apply a billing rule to an exact squared total. Source quantities are never rounded."""
    exact = Decimal(squared.numerator) / Decimal(squared.denominator)
    if rule["method"] == "exact_whole":
        if squared.denominator != 1:
            raise ValueError(f"count {exact} is not a whole number")
        return exact
    places = Decimal(1).scaleb(-rule["decimals"])
    billed = exact.quantize(places, rounding=ROUND_HALF_UP)
    if rule.get("minimum_when_positive") and exact > 0 and billed == 0:
        return Decimal(str(rule["minimum_when_positive"]))
    return billed
