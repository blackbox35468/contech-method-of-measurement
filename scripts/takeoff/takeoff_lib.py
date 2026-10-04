"""Shared helpers for the CMM take-off sidecar and reference take-offs.

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
SIDECAR = REPO / "takeoff" / "CMM-1.0-takeoff-basis.json"
REFERENCE_DIR = REPO / "takeoff" / "reference"

ITEM_CODE = re.compile(r"\b(\d{2}\.[A-Z]\.\d+)\b")
SECTION_REF = re.compile(r"\bsections? (\d{2}(?:(?:, | and )\d{2})*)")

# How many dimensions one row carries for each unit kind. Anything else
# (thickness, width, depth) is stated in the description, not measured
# (cmm.general.02).
DIMS_PER_KIND = {"count": 0, "length": 1, "area": 2, "volume": 3}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_release():
    release = json.loads(RELEASE.read_text())
    manifest = json.loads(MANIFEST.read_text())
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
    """Item codes and section codes that a piece of CMM text sends work to."""
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


def billed_quantity(squared, unit):
    """Round a squared total for BOQ presentation (takeoff/README.md, rounding policy).

    Staged and squared quantities stay exact; only the billed figure is rounded.
    """
    exact = Decimal(squared.numerator) / Decimal(squared.denominator)
    if unit == "t":
        return exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole = exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if exact > 0 and whole == 0:
        return Decimal("1")
    return whole


def fraction_text(value):
    """Exact decimal text for a squared value (all reference dims are decimals)."""
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return format(exact.normalize(), "f")
