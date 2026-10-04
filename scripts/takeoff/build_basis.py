"""Generate takeoff/CMM-1.0-takeoff-basis.json from the published CMM release.

The output is a non-canonical consumer aid for take-off software: a
machine-readable measurement basis for each item and the items its
exclusions send work to. It is derived deterministically; rerun this script
rather than editing the JSON by hand.

    python3 scripts/takeoff/build_basis.py          # write
    python3 scripts/takeoff/build_basis.py --check  # fail if the file is stale
"""

import json
import re
import sys

from takeoff_lib import SIDECAR, items_by_code, load_release, refs_in, unit_kinds

# Ordered: the first pattern that matches the item's own wording wins.
LENGTH_PATTERNS = [
    ("length_profile", r"tendon profile"),
    ("length_toe_depth", r"to the toe|cut-off to toe|along the bore|driven length|rail head"),
    ("length_face_line", r"front face|fence line|edging line|barrier line|boundary of|marked line|line of the embedded wall|along the wall"),
    ("length_centreline", r"centre ?line|along (its|the|each)? ?(installed )?(run|length)|along the run|along the (trench|swale|boardwalk|capping|drain)|along each installed"),
]
AREA_PATTERNS = [
    ("area_on_plan", r"on plan|plan area|slab area|deck area|floor area"),
    ("area_on_face", r"on (the |one )?(\w+ )?face|on the face|exposed faces?|face of the wall|formed face|treated face|wall face|soffit"),
]
VOLUME_PATTERNS = [
    ("volume_in_stockpile", r"in the stockpile"),
    ("volume_gross", r"gross (\w+ )?(zone|volume)|external volume"),
    ("volume_plan_area_x_depth", r"plan area .{0,40}multiplied by"),
    ("volume_compacted", r"compacted"),
    ("volume_net_in_place", r"measured net|net\b|in place|in-place|in-situ|in situ|excavated volume"),
]
FIXED_BASIS = {
    "count": "count",
    "lump sum": "lump_sum",
    "time": "duration",
    "mass": "mass",
}
DEFAULTS = {
    # Unit kind -> (basis, general rule or unit meaning that supplies it).
    "length": ("length_centreline", "cmm.general.05"),
    "area": ("area_stated_face_or_plan", "unit:m2"),
    "volume": ("volume_net_in_place", "cmm.general.01"),
}
PATTERNS = {"length": LENGTH_PATTERNS, "area": AREA_PATTERNS, "volume": VOLUME_PATTERNS}

NO_LAPS = re.compile(r"(no allowance|no addition) for laps|before laps")
NOT_DEDUCTED = re.compile(r"not deducted")


def convention_texts(item):
    texts = [
        (rule["id"], rule["text"])
        for rule in item["measurement_rules"]
        if rule["kind"] == "convention"
    ]
    texts.append((f"cmm.item.{item['code']}#one_unit_is", item["one_unit_is"]))
    return texts


def classify(item, kind):
    if kind in FIXED_BASIS:
        basis = FIXED_BASIS[kind]
        if item["unit"] == "visit":
            basis = "count"
        return basis, {"kind": "unit", "id": f"unit:{item['unit']}"}
    for source_id, text in convention_texts(item):
        lowered = text.lower()
        for basis, pattern in PATTERNS.get(kind, []):
            if re.search(pattern, lowered):
                source_kind = "one_unit_is" if source_id.endswith("#one_unit_is") else "rule"
                return basis, {"kind": source_kind, "id": source_id, "text": text}
    if kind in DEFAULTS:
        basis, source = DEFAULTS[kind]
        return basis, {"kind": "default", "id": source}
    return "needs_review", {"kind": "none", "id": None}


def entry(item, kinds):
    kind = kinds[item["unit"]]
    basis, source = classify(item, kind)
    wording = " ".join(text for _, text in convention_texts(item)).lower()
    measured_elsewhere, sections = refs_in(item["excluded"])
    record = {
        "code": item["code"],
        "title": item["title"],
        "unit": item["unit"],
        "unit_kind": kind,
        "basis": basis,
        "basis_source": source,
        "status": item.get("status", "active"),
        "measured_elsewhere": [code for code in measured_elsewhere if code != item["code"]],
        "measured_elsewhere_sections": sections,
    }
    if kind == "area":
        record["openings_deducted"] = not NOT_DEDUCTED.search(wording)
    if kind in ("area", "length"):
        record["laps_measured"] = not NO_LAPS.search(wording)
    if item.get("successor_item_codes"):
        record["successor_item_codes"] = item["successor_item_codes"]
    return record


def build():
    release, digest = load_release()
    kinds = unit_kinds(release)
    items = items_by_code(release)
    return {
        "title": "CMM take-off basis (non-canonical consumer aid)",
        "canonical": False,
        "cmm_edition": release["standard"]["edition"],
        "cmm_canonical_sha256": digest,
        "generated_by": "scripts/takeoff/build_basis.py",
        "notice": (
            "Derived from CMM Edition 1.0 for take-off software. The release text "
            "controls: where this file and an item's wording differ, follow the item. "
            "basis_source.kind 'default' means the item gives no basis of its own and "
            "the general rule or unit meaning named in basis_source.id applies."
        ),
        "general_rules": release["general_rules"],
        "quantity_policy": {
            "staged_quantities": "exact; never rounded",
            "billed_quantities": "rounded for BOQ presentation only",
            "rounding": {
                "default": "nearest whole unit, half up; any positive quantity under one unit is billed as 1",
                "t": "two decimal places, half up",
            },
            "status": "ContechCost house policy; CMM Edition 1.0 states no rounding rule",
        },
        "items": [entry(items[code], kinds) for code in sorted(items, key=sort_key)],
    }


def sort_key(code):
    section, letter, number = code.split(".")
    return int(section), letter, int(number)


def render(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def main(argv):
    text = render(build())
    if "--check" in argv:
        if not SIDECAR.exists() or SIDECAR.read_text() != text:
            print(f"{SIDECAR.name} is stale; run scripts/takeoff/build_basis.py", file=sys.stderr)
            return 1
        print(f"{SIDECAR.name} matches the CMM release")
        return 0
    SIDECAR.write_text(text)
    print(f"Wrote {SIDECAR.relative_to(SIDECAR.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
