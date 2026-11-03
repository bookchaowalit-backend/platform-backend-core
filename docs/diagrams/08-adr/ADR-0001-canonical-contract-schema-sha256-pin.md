# ADR-0001 — Canonical contract schema here, vendored with a sha256 pin

- Status: accepted (retro-documented)
- Date of evidence: 2026-09-30 (commit 1e94dae), keep decision 2026-10-16 (docs/DECISION.md)

## Context
platform repo หลายตัวต้องใช้ `book-platform.contract.v1` ตัวเดียวกันโดยไม่ drift และตรวจ offline ได้

## Decision
schema ฉบับ canonical อยู่ที่ `contracts/` ของ repo นี้; แต่ละ platform repo vendor สำเนาที่ `schema/` พร้อม pin `.sha256`
และ CI ของเขาเองตรวจด้วย `scripts/check_schema_pin.py`; validator ใช้ JSON Schema subset เท่านั้น และ `scripts/check.py` ปฏิเสธ keyword อื่น

## Evidence
- contracts/README.md, contracts/book-platform.contract.v1.schema.json.sha256
- scripts/check.py (`SUPPORTED_KEYWORDS`, `pin_errors`), scripts/check_platform_sync.py
- docs/DECISION.md (10 repos pin digest เดียวกัน; owner confirmed keep 2026-10-16)

## Consequences
- ต้อง copy schema + pin ไปทุก repo ในการเปลี่ยนครั้งเดียว (มือ)
- `check_platform_sync.py` รันได้เฉพาะ local (CI ไม่มี sibling checkout)
