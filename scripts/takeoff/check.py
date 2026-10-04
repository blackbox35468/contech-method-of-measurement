"""Check the take-off aids and every reference take-off against CMM Edition 1.0.

    python3 scripts/takeoff/check.py

A reference take-off passes only when every quantity re-squares exactly from
its dimension rows, each row carries the number of dimensions its CMM unit
allows, every item particular is stated, billed figures follow the quantity
policy, and every coverage-guidance prompt it triggers is either measured or
recorded as not required. Other exclusion references are reported as advisory.
"""

import ast
import operator
import sys
from decimal import Decimal
from fractions import Fraction

import build_refs
from takeoff_lib import (
    DIMS_PER_KIND,
    GUIDANCE,
    POLICY,
    REFERENCE_DIR,
    billed_quantity,
    items_by_code,
    load_json,
    load_release,
    rounding_rule,
    square_row,
    unit_kinds,
)

OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
RELATIONS = {"companion_if", "one_of", "counting", "measuring"}


def evaluate(expression):
    """Evaluate a waste calc: whole-number millimetres with + - * / and brackets only."""

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(node.value)
        raise ValueError(f"unsupported waste calc term in {expression!r}")

    return walk(ast.parse(expression, mode="eval"))


def reference_id(doc):
    return doc["titles"]["project"].split()[0]


def entries_of(doc):
    return {entry["id"]: entry for group in doc["groups"] for entry in group["entries"]}


def check_guidance(guidance, release, digest, references):
    """Every guidance entry must cite real CMM wording (or declare a gap) and real evidence."""
    errors = []
    items = items_by_code(release)
    if guidance.get("cmm_canonical_sha256") != digest:
        errors.append("coverage guidance is not pinned to this CMM release")
    seen = set()
    for entry in guidance["guidance"]:
        gid = entry["id"]
        if gid in seen:
            errors.append(f"{gid}: duplicate id")
        seen.add(gid)
        if entry["relation"] not in RELATIONS:
            errors.append(f"{gid}: unknown relation {entry['relation']}")
        for code in entry["when_measured"] + entry["consider"]:
            if code not in items:
                errors.append(f"{gid}: {code} is not a CMM item")
        if entry["relation"] in ("companion_if", "one_of") and not entry["consider"]:
            errors.append(f"{gid}: {entry['relation']} needs items to consider")
        source = entry.get("cmm_source")
        if source:
            if source["quote"] not in items.get(source["item"], {}).get("excluded", ""):
                errors.append(f"{gid}: quote not found in the exclusions of {source['item']}")
        elif not entry.get("gap"):
            errors.append(f"{gid}: give a cmm_source quote or state the gap")
        if not entry.get("evidence"):
            errors.append(f"{gid}: no evidence")
        for evidence in entry.get("evidence", []):
            doc = references.get(evidence["reference"])
            if doc is None:
                errors.append(f"{gid}: evidence names unknown reference {evidence['reference']}")
            elif "entry" in evidence and evidence["entry"] not in entries_of(doc):
                errors.append(f"{gid}: evidence names unknown entry {evidence['reference']} {evidence['entry']}")
            elif "not_required" in evidence and evidence["not_required"] not in doc.get("not_required", {}):
                errors.append(f"{gid}: evidence names a missing not_required record in {evidence['reference']}")
    return errors


def check_reference(doc, release, digest, refs_by_code, guidance, policy):
    """Return (errors, advisory notes) for one reference take-off."""
    errors, notes = [], []
    items = items_by_code(release)
    kinds = unit_kinds(release)
    titles = doc["titles"]

    if titles.get("cmm_edition") != release["standard"]["edition"]:
        errors.append("titles.cmm_edition does not match the release")
    if titles.get("cmm_canonical_sha256") != digest:
        errors.append("titles.cmm_canonical_sha256 does not match the release")
    for key in ("project", "drawings", "measured_by", "date"):
        if not titles.get(key):
            errors.append(f"titles.{key} is missing")

    calcs = {}
    for calc in doc.get("waste_calcs", []):
        value = evaluate(calc["expression"])
        if value != calc["result_mm"]:
            errors.append(f"{calc['id']}: {calc['expression']} = {value}, not {calc['result_mm']}")
        calcs[calc["id"]] = Fraction(calc["result_mm"], 1000)

    for group in doc["groups"]:
        for key in ("trade_heading", "signpost"):
            if not group.get(key):
                errors.append(f"group is missing {key}")
    entries = entries_of(doc)

    for entry_id, entry in entries.items():
        where = f"{entry_id} {entry['cmm_code']}"
        item = items.get(entry["cmm_code"])
        if item is None:
            errors.append(f"{where}: not a CMM item")
            continue
        if item.get("status") == "retired":
            errors.append(f"{where}: retired item; use {item.get('successor_item_codes')}")
        unit = item["unit"]
        kind = kinds[unit]
        if not entry.get("description"):
            errors.append(f"{where}: description is missing")

        particulars = entry.get("particulars", {})
        required = set(item["parameter_ids"])
        missing = sorted(required - set(particulars))
        unknown = sorted(set(particulars) - required)
        blank = sorted(key for key, value in particulars.items() if not str(value).strip())
        if missing:
            errors.append(f"{where}: particulars not stated: {', '.join(missing)}")
        if unknown:
            errors.append(f"{where}: particulars not defined for this item: {', '.join(unknown)}")
        if blank:
            errors.append(f"{where}: particulars left blank: {', '.join(blank)}")

        if "anded_with" in entry:
            source = entries.get(entry["anded_with"])
            if entry.get("rows"):
                errors.append(f"{where}: an anded entry takes its dimensions from {entry['anded_with']}, not its own rows")
            if source is None or "anded_with" in source:
                errors.append(f"{where}: anded_with must name an entry with its own rows")
                continue
            if items[source["cmm_code"]]["unit"] != unit:
                errors.append(f"{where}: anded with {entry['anded_with']}, which has a different unit")
            rows = source["rows"]
        else:
            rows = entry.get("rows", [])
        if not rows:
            errors.append(f"{where}: no dimension rows")
            continue

        expected_dims = DIMS_PER_KIND.get(kind)
        squared = Fraction(0)
        for number, row in enumerate(rows, 1):
            dims = row.get("dims", [])
            if expected_dims is not None and len(dims) != expected_dims:
                errors.append(
                    f"{where} row {number}: {len(dims)} dimension(s) for a {unit} item; "
                    f"CMM measures {unit} with {expected_dims} (state other sizes in the description)"
                )
            for dim in dims:
                if Decimal(str(dim)).as_tuple().exponent < -2 or dim <= 0:
                    errors.append(f"{where} row {number}: dimension {dim} must be positive metres to 2 decimals")
            for position, calc_id in enumerate(row.get("from_calc", [])):
                if calc_id is None:
                    continue
                if calc_id not in calcs:
                    errors.append(f"{where} row {number}: unknown waste calc {calc_id}")
                elif position >= len(dims) or Fraction(Decimal(str(dims[position]))) != calcs[calc_id]:
                    errors.append(f"{where} row {number}: dimension {position + 1} does not match {calc_id}")
            try:
                squared += square_row(row)
            except ValueError as error:
                errors.append(f"{where} row {number}: {error}")

        if squared != Fraction(Decimal(entry["squared"])):
            errors.append(f"{where}: squares to {float(squared)}, not {entry['squared']}")
        try:
            billed = billed_quantity(squared, rounding_rule(policy, entry["cmm_code"], unit, kind))
        except ValueError as error:
            errors.append(f"{where}: {error}")
            continue
        if billed != Decimal(entry["billed"]):
            errors.append(f"{where}: billed quantity under the quantity policy is {billed}, not {entry['billed']}")

    measured = {entry["cmm_code"] for entry in entries.values()}
    not_required = doc.get("not_required", {})
    guidance_ids = {g["id"] for g in guidance["guidance"]}
    prompted = set()
    for rule in guidance["guidance"]:
        if not measured.intersection(rule["when_measured"]):
            continue
        if rule["relation"] == "companion_if":
            for code in rule["consider"]:
                prompted.add(code)
                if code not in measured and not str(not_required.get(code, "")).strip():
                    errors.append(f"coverage {rule['id']}: measure {code} or record why it is not required ({rule['condition']})")
        elif rule["relation"] == "one_of":
            prompted.update(rule["consider"])
            if not measured.intersection(rule["consider"]) and not str(not_required.get(rule["id"], "")).strip():
                errors.append(f"coverage {rule['id']}: measure one of {', '.join(rule['consider'])} or record why none is required under {rule['id']}")

    for code in sorted(measured):
        for ref in refs_by_code[code]["exclusion_refs"]:
            for other in ref["items"]:
                if other not in measured and other not in prompted and other not in not_required:
                    notes.append(f"{code} -> {other}: {ref['source']}")

    for key in not_required:
        if key in guidance_ids or key.startswith("section:"):
            continue
        if key in measured or key not in items:
            errors.append(f"not_required lists {key}, which is measured or is not a CMM item or guidance id")

    return errors, notes


def main(argv):
    verbose = "-v" in argv
    failures = 0
    expected = build_refs.render(build_refs.build())
    if not build_refs.EXCLUSION_REFS.exists() or build_refs.EXCLUSION_REFS.read_text() != expected:
        print("FAIL exclusion refs: stale; run scripts/takeoff/build_refs.py")
        failures += 1
    else:
        print("ok   exclusion refs match the CMM release")

    release, digest = load_release()
    refs_by_code = {record["code"]: record for record in load_json(build_refs.EXCLUSION_REFS)["items"]}
    guidance = load_json(GUIDANCE)
    policy = load_json(POLICY)
    references = {}
    for path in sorted(REFERENCE_DIR.glob("*.json")):
        doc = load_json(path)
        references[reference_id(doc)] = (path, doc)
    if not references:
        print("FAIL no reference take-offs found")
        failures += 1

    guidance_errors = check_guidance(guidance, release, digest, {key: doc for key, (_, doc) in references.items()})
    if guidance_errors:
        failures += 1
        print("FAIL coverage guidance")
        for error in guidance_errors:
            print(f"     {error}")
    else:
        print(f"ok   coverage guidance ({len(guidance['guidance'])} entries)")

    for key, (path, doc) in references.items():
        errors, notes = check_reference(doc, release, digest, refs_by_code, guidance, policy)
        if errors:
            failures += 1
            print(f"FAIL {path.name}")
            for error in errors:
                print(f"     {error}")
        else:
            print(f"ok   {path.name} ({len(notes)} advisory exclusion refs; -v to list)")
        if verbose:
            for note in notes:
                print(f"     advisory {note}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
