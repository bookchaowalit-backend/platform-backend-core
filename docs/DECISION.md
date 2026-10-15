# Decision: keep platform-backend-core (BOO-154)

**Recommendation: keep.** Do not archive in favour of `book-developer-platform`.
Recorded 2026-10-15 from repository evidence. The owner still has to confirm it.

## The question

Is this repository redundant with `book-developer-platform`
(`bookchaowalit-backend/platform-developer`, which owns the `repo-template`,
`ci-cd` and `release-convention` capabilities)? Should one of the two be
archived?

## Comparison

| | platform-backend-core | book-developer-platform (`platform-developer`) |
|---|---|---|
| Role | Hosts the **canonical** `book-platform.contract.v1` JSON Schema, its sha256 pin and valid/invalid examples | One platform boundary among eleven; owns developer capabilities (repo-template, ci-cd, config, feature-flags, release-convention) |
| Schema | Canonical source (`contracts/`) | Vendored copy (`schema/`) pinned to this repo's digest |
| Status | Shared foundation; CI runs `scripts/check.py` and unit tests | `scaffolded` in `contract.json`; no runtime |
| Dependents | 10 platform repositories pin its schema digest | None found |

## Evidence (origin/main of each repository, 2026-10-15)

- `contracts/book-platform.contract.v1.schema.json.sha256` here is
  `d3664d19ffbf…`. The vendored schema pin in each of these ten repositories is the same
  digest: platform-ai, platform-api-gateway, platform-communication,
  platform-data, platform-developer, platform-identity, platform-media,
  platform-observability, platform-payment and platform-workflow.
- `platform-developer/scripts/check_schema_pin.py` names this repository as
  the canonical copy, and `--canonical` compares against a checkout of it.
- `platform-workflow/docs/RUNTIME.md` and `docs/RUNBOOK.md` already plan to
  install a pinned `platform-backend-core` package.
- Open draft PR #6 adds a shared workspace-auth and PostgreSQL runtime to this
  repository, so active work depends on it.

## Why not archive

Archiving would leave ten repositories pinned to a schema that no longer has a
maintained source. The developer platform is a capability boundary, not a
shared-contract host, so moving the schema there would mix those roles.

## Why not merge the other way

`book-developer-platform` is one consumer among ten. Its scope (templates,
CI/CD, flags) does not overlap this repository's shared-contract role.

## Follow-ups (not done here)

- Replace the vendored `check.py` copies in platform repositories with one
  shared check from this repository (roadmap `bcore` goal).
- Update the catalog and archive nothing until the owner confirms this decision.

| Field | Value |
|---|---|
| Decision | keep (recommended) |
| Recorded by | Claude Code session, 2026-10-15 |
| Owner confirmation | PENDING — bookchaowalit |
