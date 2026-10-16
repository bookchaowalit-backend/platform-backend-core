# Decision: keep platform-backend-core (BOO-154)

**Decision: keep.** Do not archive in favour of `book-developer-platform`.
Recommended 2026-10-15 from repository evidence; confirmed by the owner on
2026-10-16.

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

## Evidence (2026-10-15; origin/main unless stated)

- `contracts/book-platform.contract.v1.schema.json.sha256` here is
  `d3664d19ffbf…`. The vendored schema pin in each of these ten repositories is the same
  digest: platform-ai, platform-api-gateway, platform-communication,
  platform-data, platform-developer, platform-identity, platform-media,
  platform-observability, platform-payment and platform-workflow.
- `platform-developer/scripts/check_schema_pin.py` names this repository as
  the canonical copy (under its former name `bookchaowalit-backend-core`; the
  script still needs a rename follow-up), and `--canonical` compares against a
  checkout of it.
- An open draft PR in platform-workflow (#1, branch
  `codex/shared-infrastructure-20261015`) plans to install a pinned
  `platform-backend-core` package (`docs/RUNTIME.md`, `docs/RUNBOOK.md` on that
  branch).
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
- Archive nothing; record this keep decision in the catalog when it is next refreshed.

| Field | Value |
|---|---|
| Decision | **keep** |
| Recorded by | Claude Code session, 2026-10-15 |
| Owner confirmation | Confirmed 2026-10-16 by bookchaowalit ("ทั้งหมด ยกเว้น 140/256 (Recommended)" — adopt the recommended option) |
