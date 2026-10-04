"""Generate takeoff/CMM-1.0-exclusion-refs.json from the published CMM release.

CMM items already say what they exclude and where that work is measured.
This file lifts those references out of the wording, sentence by sentence, so
software can prompt for related work. It adds no rules of its own; rerun this
script rather than editing the JSON by hand.

    python3 scripts/takeoff/build_refs.py          # write
    python3 scripts/takeoff/build_refs.py --check  # fail if the file is stale
"""

import json
import re
import sys

from takeoff_lib import EXCLUSION_REFS, items_by_code, load_release, refs_in

SENTENCE = re.compile(r"(?<=\.)\s+(?=[A-Z])")


def exclusion_refs(item):
    refs = []
    for sentence in SENTENCE.split(item["excluded"] or ""):
        codes, sections = refs_in(sentence)
        codes = [code for code in codes if code != item["code"]]
        if codes or sections:
            refs.append({"items": codes, "sections": sections, "source": sentence.strip()})
    return refs


def sort_key(code):
    section, letter, number = code.split(".")
    return int(section), letter, int(number)


def build():
    release, digest = load_release()
    items = items_by_code(release)
    records = []
    for code in sorted(items, key=sort_key):
        item = items[code]
        record = {"code": code, "unit": item["unit"], "status": item.get("status", "active"), "exclusion_refs": exclusion_refs(item)}
        if item.get("successor_item_codes"):
            record["successor_item_codes"] = item["successor_item_codes"]
        records.append(record)
    with_rules = sum(1 for item in items.values() if item["measurement_rules"])
    return {
        "title": "CMM exclusion references (non-canonical consumer aid)",
        "canonical": False,
        "cmm_edition": release["standard"]["edition"],
        "cmm_canonical_sha256": digest,
        "generated_by": "scripts/takeoff/build_refs.py",
        "notice": (
            "Each reference is lifted from an item's own exclusion wording, which is quoted as its source. "
            "A reference says where related work is measured if it exists; it does not say the work is "
            "required. Some references are alternatives or boundaries. The release controls."
        ),
        "audit": {
            "measured_items": len(items),
            "items_with_item_rules": with_rules,
            "items_with_exclusion_refs": sum(1 for record in records if record["exclusion_refs"]),
            "general_rules": [rule["id"] for rule in release["general_rules"]],
        },
        "items": records,
    }


def render(document):
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def main(argv):
    text = render(build())
    if "--check" in argv:
        if not EXCLUSION_REFS.exists() or EXCLUSION_REFS.read_text() != text:
            print(f"{EXCLUSION_REFS.name} is stale; run scripts/takeoff/build_refs.py", file=sys.stderr)
            return 1
        print(f"{EXCLUSION_REFS.name} matches the CMM release")
        return 0
    EXCLUSION_REFS.write_text(text)
    print(f"Wrote takeoff/{EXCLUSION_REFS.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
