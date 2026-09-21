# Contech Method of Measurement (CMM)

CMM is a rate-free method of measurement for construction. It gives people and software one consistent way to identify measured work, understand what one unit means and apply the same scope boundaries.

## The three levels

1. **Work section** — a broad area of construction work.
2. **Work subsection** — a related family of work within the section.
3. **Measured item** — the specific work being measured, with its unit, measurement basis, inclusions, exclusions and required contract details.

CMM stops at the measured item. It does not contain construction methods, labour gangs, resources, productivity, prices or regional rates.

## Release 1.0

The `release/` directory contains the complete CMM 1.0 issue:

- `CMM-1.0.json` — the canonical machine-readable standard;
- `schemas/CMM-1.0.schema.json` — its validation schema;
- `release-manifest.json` — release identity, counts and checksums;
- `verification/release-verification.json` — the checks applied before publication; and
- `SHA256SUMS` — the checksum register for every release file.

The canonical CMM 1.0 SHA-256 is:

```text
8e227a98b038a2eb5bd10527fd311d496b1f5e43380564d13fb75c1744a3ff2c
```

Verify the release after downloading it:

```bash
cd release
sha256sum -c SHA256SUMS
```

## Using CMM

Construction professionals can read the item names and measurement rules directly. Software can validate the same release against the supplied schema. The ContechCost CMM Reader provides read-only MCP access to the released information for authorised AI clients.

Always retain the edition and canonical checksum with any copied or transformed CMM data. Mark changes clearly rather than presenting an adaptation as the unchanged CMM release.

## Licence and attribution

Contech Method of Measurement (CMM), Edition 1.0, © 2026 BLACKBOX TRADING PTY LTD.

Licensed under the [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/). See [`LICENSE`](LICENSE) for the full legal text.

Suggested attribution:

```text
Contech Method of Measurement (CMM), Edition 1.0, © 2026 BLACKBOX TRADING PTY LTD, licensed CC BY 4.0.
```

## Corrections and proposals

Use this repository's Issues page to report unclear wording, missing work or a possible measurement conflict. A proposal does not change the released standard until it appears in a later tagged release.
