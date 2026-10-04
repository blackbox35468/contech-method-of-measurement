# CMM take-off aids (non-canonical)

This folder helps take-off software and people measure to CMM Edition 1.0. It is
**not part of the CMM release**. The release in `release/` controls: where anything
here differs from an item's own wording, follow the item.

## `CMM-1.0-takeoff-basis.json`

One record for each of the 813 measured items, generated from the release by
`scripts/takeoff/build_basis.py`. Do not edit it by hand.

| Field | Meaning |
|---|---|
| `basis` | What geometry the quantity comes from, e.g. `length_centreline`, `area_on_plan`, `area_on_face`, `volume_net_in_place`, `volume_gross`, `volume_plan_area_x_depth`, `count`. |
| `basis_source` | Where the basis came from: an item rule (`rule`), the item's "one unit is" wording (`one_unit_is`), its unit (`unit`), or, when the item gives none, the general rule or unit meaning that applies (`default`). |
| `openings_deducted` | Area items only. CMM general rule 03 deducts every opening, void, fitting and penetration in full, with no minimum size, unless the item says otherwise. |
| `laps_measured` | Area and length items only. `false` where the item says to make no allowance for laps. |
| `measured_elsewhere` | Items that this item's exclusions send work to. Use these as prompts in a coverage check: confirm each one is measured or not required. |
| `measured_elsewhere_sections` | Whole sections the exclusions send work to, e.g. "sections 11, 12 and 13". |

The file also repeats the release's seven general rules and records the quantity policy below.

### Quantity policy (ContechCost house policy)

CMM Edition 1.0 states no rounding rule. Until it does:

- **Staged and squared quantities are exact.** Never round them.
- **Billed quantities are rounded for BOQ presentation only**: to the nearest whole unit
  (half up), with any positive quantity under one unit billed as 1. Tonnes go to two
  decimal places.

## `reference/` – reference take-offs

Small jobs measured by hand to the dimension-paper conventions (titles, trade headings,
signposting, waste calcs in mm, fraction timesing with dotting on, deduction rows,
anding, squared and billed totals). Every automated take-off route should reproduce
their billed quantities.

`GS-01-garden-studio.json` covers a strip footing, a slab on ground and a block wall
with openings: 14 measured items, with a recorded reason for each related item that is
not required.

## Checks

```bash
python3 scripts/takeoff/build_basis.py --check   # sidecar matches the release
python3 scripts/takeoff/check.py                 # sidecar + every reference take-off
python3 -m unittest discover -s tests            # checker and policy tests
```

`check.py` fails a reference take-off when:

- a total does not square exactly from its rows;
- a row has the wrong number of dimensions for its CMM unit (a metre item takes one
  dimension; width and depth go in the description, per general rule 02);
- a dimension does not match the waste calc it cites;
- an item parameter is not stated;
- a billed figure breaks the rounding policy; or
- an item sends work elsewhere and that work is neither measured nor recorded as not required.
