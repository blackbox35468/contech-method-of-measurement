# Contech Method of Measurement (CMM)

CMM is a rate-free method of measurement for construction. It gives people and software one consistent way to identify measured work, understand what one unit means and apply the same scope boundaries.

## The three levels

1. **Work section** — a broad area of construction work.
2. **Work subsection** — a related family of work within the section.
3. **Measured item** — the specific work being measured, with its unit, measurement basis, inclusions, exclusions and required contract details.

CMM stops at the measured item. It does not contain construction methods, labour gangs, resources, productivity, prices or regional rates.

## Current release: Edition 1.0.2

The `release-1.0.2/` directory contains the current CMM issue: 59 work sections, 203 work subsections and 813 measured-item records, including three retired items kept for reference. The signed original Edition 1.0 stays in `release/`; Edition 1.0.1 stays in `release-1.0.1/` for earlier references.

- `CMM-1.0.2.json` — the canonical machine-readable standard;
- `schemas/CMM-1.0.2.schema.json` — its validation schema;
- `release-manifest.json` — release identity, counts, checksums and validation status; and
- `SHA256SUMS` — the checksum register for every release file.

The canonical CMM 1.0.2 SHA-256 is:

```text
8cb74c0579667022108a1216baee364178053ca3344a93e7f63ba7c028f3ed0c
```

Items 60.C.1–60.C.3 are retired but remain readable so older references can be reviewed. Their successors use different measurement bases: re-measure the work rather than converting an old quantity. Worked examples pass; quantity boundaries have been checked on worked examples and remain under observation in live use. Edition 1.0.2 retains the clean public rule IDs and their migration aliases, and states five civil contract facts already required by the items' measurement wording. Item codes, units and quantity rules are unchanged from 1.0.1.

Verify the release after downloading it:

```bash
cd release-1.0.2
sha256sum -c SHA256SUMS
```

## Using CMM

Construction professionals can read the item names and measurement rules directly. Software can validate the same release against the supplied schema. The ContechCost CMM Reader provides read-only MCP access to the released information for authorised AI clients.

Always retain the edition and canonical checksum with any copied or transformed CMM data. Mark changes clearly rather than presenting an adaptation as the unchanged CMM release.

## Licence and attribution

Contech Method of Measurement (CMM), Edition 1.0.2, © 2026 BLACKBOX TRADING PTY LTD.

Licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/). See [`LICENSE`](LICENSE) for the full legal text.

Suggested attribution:

```text
Contech Method of Measurement (CMM), Edition 1.0.2, © 2026 BLACKBOX TRADING PTY LTD, licensed CC BY 4.0.
```

## Corrections and proposals

Use this repository's Issues page to report unclear wording, missing work or a possible measurement conflict. A proposal does not change the released standard until it appears in a later tagged release.
