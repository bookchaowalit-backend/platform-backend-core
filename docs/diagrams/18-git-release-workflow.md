# 18 — Git & release workflow

```mermaid
gitGraph
    commit id: "b83b7fd bootstrap"
    commit id: "1c220a6 product brief"
    branch claude-session
    commit id: "8328d47 schema + check"
    commit id: "1e94dae pin + sync"
    checkout main
    merge claude-session id: "11f6288 PR 2"
    commit id: "087fd11 rename PR 3"
    commit id: "00d7a27 fix PR 4"
    commit id: "9fdf587 decision PR 7"
    commit id: "0b1b642 decision PR 8"
    commit id: "cd9e27a shared CI v1.1.1"
    branch shared-infrastructure
    commit id: "73fce52 runtime"
    commit id: "2d0ea51 reject delegation"
    checkout main
    merge shared-infrastructure id: "247a17d PR 6 local merge"
    commit id: "3f733de uv lock PR 9"
    branch pool-check
    commit id: "dbada06 pool check"
    checkout main
    merge pool-check id: "88306b2"
    branch connect-timeout
    commit id: "679d01d connect timeout"
    checkout main
    merge connect-timeout id: "21d5f44 pinned by 8"
    branch service-token-source
    commit id: "638aa06 ServiceTokenSource"
    checkout main
    merge service-token-source id: "dc1fa7d PR 10 pinned by workflow"
```

ภาพย่อ: แสดงเฉพาะ commit หลัก (ดูเต็มด้วย `git log --graph --oneline origin/main`)

Sources: `git log --graph origin/main` (2026-11-03), `gh pr list --state all` (PR #6 closed, merged locally as 247a17d)

```mermaid
flowchart LR
    A["Feature branch"] --> B["push: CI"]
    B --> C{"PR?"}
    C -->|yes| D["pull_request CI"]
    C -->|no| E["Local merge to main"]
    D --> E
    E --> F["push main: CI; required check starter-contract"]
    F --> G["No tag, no publish"]
    G --> H["Consumer PR bumps git rev SHA"]
    H --> I["Consumer CI + deploy"]
```

Sources: .github/workflows/ci.yml, branch protection API (required `starter-contract`, enforce_admins true, no required reviews), gh pr list, consumer pyproject.toml pins

## Open questions

- ไม่มี release tag / CHANGELOG — consumer รู้ว่า commit ไหน "reviewed" จากอะไร?
