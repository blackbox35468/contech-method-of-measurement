"""Check the take-off sidecar and every reference take-off against CMM Edition 1.0.

    python3 scripts/takeoff/check.py

A reference take-off passes only when every quantity re-squares exactly from
its dimension rows, each row carries the number of dimensions its CMM unit
allows, every item particular is stated, and every piece of work an item
sends elsewhere is either measured in the take-off or recorded as not
required with a reason.
"""

import ast
import json
import operator
import sys
from decimal import Decimal
from fractions import Fraction

import build_basis
from takeoff_lib import (
    DIMS_PER_KIND,
    REFERENCE_DIR,
    billed_quantity,
    items_by_code,
    load_release,
    square_row,
    unit_kinds,
)

OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


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


def parameter_ids(item):
    return set(item["parameter_ids"])


def check_reference(path, release, digest, basis_by_code):
    errors = []
    doc = json.loads(path.read_text())
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

    entries = {}
    for group in doc["groups"]:
        for key in ("trade_heading", "signpost"):
            if not group.get(key):
                errors.append(f"group is missing {key}")
        for entry in group["entries"]:
            entries[entry["id"]] = entry

    squared_by_id = {}
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

        stated = set(entry.get("particulars", {}))
        missing = sorted(parameter_ids(item) - stated)
        unknown = sorted(stated - parameter_ids(item))
        blank = sorted(k for k, v in entry.get("particulars", {}).items() if not str(v).strip())
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
        billed = billed_quantity(squared, unit)
        if billed != Decimal(entry["billed"]):
            errors.append(f"{where}: billed quantity under the rounding policy is {billed}, not {entry['billed']}")
        squared_by_id[entry_id] = squared

    measured = {entry["cmm_code"] for entry in entries.values()}
    measured_sections = {code.split(".")[0] for code in measured}
    not_required = doc.get("not_required", {})
    for code in sorted(measured):
        basis = basis_by_code[code]
        for other in basis["measured_elsewhere"]:
            if other not in measured and not str(not_required.get(other, "")).strip():
                errors.append(f"coverage: {code} sends work to {other}; measure it or record why it is not required")
        for section in basis["measured_elsewhere_sections"]:
            key = f"section:{section}"
            if section not in measured_sections and not str(not_required.get(key, "")).strip():
                errors.append(f"coverage: {code} sends work to section {section}; measure it or record {key}")
    for key in not_required:
        target = key.split(":", 1)[1] if key.startswith("section:") else key
        if key.startswith("section:") and target in measured_sections:
            errors.append(f"not_required lists {key}, but that section is measured")
        if not key.startswith("section:") and (target in measured or target not in items):
            errors.append(f"not_required lists {key}, which is measured or is not a CMM item")

    return errors, squared_by_id


def main():
    failures = 0
    expected = build_basis.render(build_basis.build())
    if not build_basis.SIDECAR.exists() or build_basis.SIDECAR.read_text() != expected:
        print("FAIL takeoff basis: stale; run scripts/takeoff/build_basis.py")
        failures += 1
    else:
        print("ok   takeoff basis matches the CMM release")

    release, digest = load_release()
    basis_by_code = {entry["code"]: entry for entry in json.loads(expected)["items"]}
    references = sorted(REFERENCE_DIR.glob("*.json"))
    if not references:
        print("FAIL no reference take-offs found")
        failures += 1
    for path in references:
        errors, _ = check_reference(path, release, digest, basis_by_code)
        if errors:
            failures += 1
            print(f"FAIL {path.name}")
            for error in errors:
                print(f"     {error}")
        else:
            print(f"ok   {path.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
