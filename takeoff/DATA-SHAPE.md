# Proposed data shape for ContechCost take-off (for agreement)

This proposal covers staged quantities, their workings, location and coverage decisions.
Agree it before any app change. Once approved, this storage and API shape moves into the
ContechCost repo; it stays here only until then. The worked examples in `reference/`
can exercise the shape, but GS-01 is synthetic and unverified and cannot serve as an
automated-route acceptance test. ContechCost owns the screens, storage and tools;
this is only the shape.

## Open decisions before approval

1. **Exact decimal storage.** Choose the database type for `quantity` and `dims` (e.g. Postgres
   `numeric` without a scale, or a decimal string) so the source precision survives storage,
   triggers and the API. Today staging rounds to 2 dp before saving.
2. **Legacy numeric compatibility.** Existing staged rows, BOQ link triggers, workbook files and
   API clients use plain numbers. Decide whether the API returns strings, numbers or both, and
   how older clients read new rows.
3. **Billing rule.** The owner selected rounding the final positive net billed quantity up
   to two decimal places on 2026-10-04. `quantity-policy.json` records that draft rule.
   Confirm its app and contract treatment before changing issued BOQ behaviour.

## 1. Staged quantity

```json
{
  "cmm_id": "31.B.1",
  "unit": "m",
  "quantity": "2.3977",
  "precision_source": "scaled",
  "rows": [
    {"times": ["1"], "dims": ["1.4985"], "deduct": false, "note": "Front", "from_calc": [null]},
    {"times": ["1"], "dims": ["0.8992"], "deduct": false, "note": "Return", "from_calc": [null]}
  ],
  "waste_calcs": [
    {"id": "WC1", "label": "Corner opening run", "expression": "1500 + 900", "result_mm": 2400}
  ],
  "location": {"level": "Ground floor", "zone": "North-east corner", "grid": null}
}
```

- **`quantity`**: a decimal string at the precision the source supplied. Do not round when
  staging. Today `src/lib/boq/staged-quantities.ts:222` rounds to 2 dp on capture; under
  this shape it would keep the source value.
- **`precision_source`**: one of `stamped`, `scaled`, `typed` or `derived`. It says how far
  the figure can be trusted. A stamped dimension governs over a scaled one; keep both as
  evidence.
- **`rows`** are optional for existing sources. Where they are present:
  - the quantity must equal the exact sum of the rows;
  - the number of `dims` per row must match the CMM unit (`m` 1, `m2` 2, `m3` 3, `nr` 0),
    and other sizes go in the description;
  - `times` takes fractions only, with dotting on written `"1+2"`;
  - deductions are rows with `deduct: true`.
- **Precision of `dims`**: tool sources keep their own precision. The 2 dp limit applies
  only to hand dimension paper.
- **`waste_calcs`** hold workings in whole millimetres. A row cites one by position in
  `from_calc`.
- **`location`** is free text from the source. Never infer it. Where an item has
  `cmm.location.level`, use `location.level` to prefill that particular for review.

## 2. Coverage decision

```json
{
  "guidance_id": "CG-01",
  "item": "10.F.2",
  "stage": "scope_draft",
  "decision": "open",
  "reason": null,
  "decided_by": null,
  "decided_at": null,
  "reopen_when": "trigger scope or quantity changes"
}
```

- **Prompts come from `coverage-guidance.json`.** Plain exclusion references may be shown
  as information but never create a prompt.
- **When the check runs:** in the scope draft and at staged take-off, then again at BOQ
  review. A check only at BOQ validation comes too late to catch missing work.
- **`decision`:** one of `open`, `measured`, `not_required` (with a reason) or
  `included_elsewhere` (with a reason).
- **Advisory:** prompts never block saving or pricing. Where a team wants a hold before
  submission, that is a separate project setting.
- **Reopening:** a decision reopens when the trigger item's scope or quantity changes.

## 3. Billing

Apply `quantity-policy.json` only at BOQ presentation or billing. Store source and squared
quantities without rounding. Counts and lump sums must be whole and are never rounded.
Item overrides take precedence.
