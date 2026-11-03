# 15 — CI/CD pipeline

workflow เดียว `.github/workflows/ci.yml` (name `CI`); ไม่มี CD เพราะไม่มีอะไร deploy

```mermaid
flowchart TD
    T1["push (any branch)"] --> W["CI workflow, concurrency ci-ref, cancel-in-progress"]
    T2["pull_request"] --> W
    T3["workflow_dispatch"] --> W
    W --> J1["starter-contract: ubuntu-latest, Python 3.11, 10 min"]
    W --> J2["lint-and-test: reusable ci-python.yml at 87dc5e1 v1.1.1"]
    W --> J3["security: reusable security.yml at 87dc5e1 v1.1.1"]
    J1 --> S1["python3 scripts/check.py"]
    S1 --> S2["python3 -m unittest discover -s tests -v"]
    J2 --> L1["Python 3.12, postgres: true, uv sync --frozen --all-extras"]
    L1 --> L2["Ruff + mypy, format-check false"]
    L2 --> L3["scripts/check.py then pytest with PLATFORM_TEST_DSN, coverage gate 88"]
    J1 -. "required status check on main" .-> P["Branch protection main"]
```

ทั้ง 3 job ไม่มี `needs` ต่อกัน (รันขนาน)

Sources: .github/workflows/ci.yml, README.md (CI), branch protection API (2026-11-03); ขั้นตอนภายใน `ci-python.yml` อ้างตาม comment ใน ci.yml และ README.md (ไฟล์อยู่ใน repo `bookchaowalit/platform-ci-workflows`)

ผล run ล่าสุด: ทุก run บน `main` ตั้งแต่ 2026-08-04 ถึง 2026-10-29 = success (`gh run list -R bookchaowalit-backend/platform-backend-core --limit 100`)

repo เป็น PUBLIC (`gh repo view --json visibility`, 2026-11-03) จึงใช้ GitHub-hosted runner ตามนโยบาย

## Open questions

- `lint-and-test` / `security` ไม่ใช่ required check (มีแค่ `starter-contract`) — ตั้งใจหรือไม่?
