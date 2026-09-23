# IFC routing guide for CMM 1.0

This public guide covers **all 801 measured items** in the signed CMM 1.0 release. It helps an estimator find possible CMM work from IFC model objects. It does not change the CMM measurement rules, identify a complete bill item, calculate a bill quantity or supply a price.

| Result | Items | What it means |
|---|---:|---|
| Candidate for estimator review | 239 | The model can suggest the measured item. The estimator checks the full scope and unit. This includes 231 earlier exact-identity candidates and 8 newly reviewed direct candidates. |
| More information needed | 300 | An IFC class or type alone cannot distinguish the work. These routes are **not selectable** from the object alone. |
| No safe route with current evidence | 82 | The available model evidence does not justify an IFC-to-CMM route. |
| Not normally represented by an IFC product object | 180 | Measure the service, operation or other work from the contract and project records. |

These are final **review outcomes**, not a claim that every item can be found automatically in a model. A valid IFC class or type is evidence about an object, not proof of CMM scope. IFC object counts and model quantities are never bill quantities here. Apply each item's CMM rule and check inclusions, exclusions and contract details before measuring.

`CMM-IFC-guide-1.0.json` is the machine-readable guide. `schemas/CMM-IFC-guide-1.0.schema.json` defines its fields. `release-manifest.json` and `SHA256SUMS` identify the published bytes. The guide is pinned to the unchanged CMM 1.0 canonical checksum in `../../release/`.

Verify the files with `sha256sum -c SHA256SUMS`. This companion uses the repository's CC BY 4.0 licence and attribution terms; it does not alter the tagged `cmm-v1.0` standard.
