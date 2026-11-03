# ADR-0002 — Distribute the runtime by pinned Git commit, not PyPI

- Status: accepted (retro-documented)

## Context
runtime ต้องใช้ร่วมกันหลาย service แต่ไม่ publish สู่ PyPI

## Decision
consumer ติดตั้ง `platform-backend-core @ git+https://github.com/bookchaowalit-backend/platform-backend-core.git@<reviewed-commit>`
และ lock ใน `[tool.uv.sources]` ด้วย `rev` เดียวกับ Dockerfile; ห้ามใช้ hub absolute path เป็น deployed dependency

## Evidence
- docs/runtime.md (Installation: "Release consumers pin an immutable reviewed commit or wheel")
- PRODUCT.md (Consumers: "not published to PyPI")
- sibling consumers: platform-commerce/pyproject.toml (`[tool.uv.sources]` rev 21d5f44…, comment เรื่อง dependency confusion), platform-commerce/Dockerfile
- ไม่มี git tag ใน repo (`gh api .../tags` ว่าง, 2026-11-03)

## Consequences
- การ "release" = merge main + consumer repin; ไม่มี version bump (`version = "0.1.0"` ใน pyproject.toml ตลอด)
- package ไม่มี `py.typed` (consumer pyproject comments) จึงต้องตั้ง mypy ฝั่ง consumer
