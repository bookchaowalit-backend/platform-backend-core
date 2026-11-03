# 09 — ERD

core ไม่มี database ของตัวเอง แต่ **สร้างตารางหนึ่งตัวใน DB ของ consumer** (`platform_schema_migrations`) และกำหนด shape ของ
tenant table ที่ consumer ต้องทำตาม ส่วน contract document (`contract.json`) เป็นข้อมูล persisted ในรูปไฟล์ของแต่ละ platform repo

## ตารางที่ core สร้าง + shape ของ tenant table ที่บังคับใช้

```mermaid
erDiagram
    PLATFORM_SCHEMA_MIGRATIONS {
        text namespace PK
        text version PK
        text checksum "SHA-256 of SQL"
        timestamptz applied_at "default now()"
    }
    TENANT_TABLE_EXAMPLE {
        uuid workspace_id "NOT NULL, leading index, RLS key"
        uuid id
        text value
    }
```

Sources: src/platform_backend_core/migrations.py (`CREATE TABLE IF NOT EXISTS platform_schema_migrations`), docs/runtime.md (ตัวอย่าง `items` + RLS policy)

## Contract document (`contract.json`, validated by the canonical schema)

```mermaid
erDiagram
    CONTRACT ||--|| CURRENT_IMPLEMENTATION : has
    CONTRACT ||--|| MIGRATION : has
    CONTRACT ||--o{ INTERFACE : declares
    CONTRACT {
        string schema_version
        string platform_id "enum of 13 ids"
        string repository
        string status "scaffolded, pilot, active, retired"
        string api_version "vN"
        string data_owner "none or platform-x"
        array capabilities
        array depends_on "known platform ids"
        array migration_gates
        string surface_doc
    }
    CURRENT_IMPLEMENTATION {
        string repository
        string source_path
        array source_paths
        string source_status
    }
    MIGRATION {
        string compatibility_adapter
        string shadow_parity
        string cutover
        string rollback
    }
    INTERFACE {
        string id
        string kind "http, event, cli, object-store, table, config, workflow"
        string direction "provides, consumes"
        string name
        string status "current-in-solo-empire, implemented, pilot, planned"
        string source
        string contract
        string auth
    }
```

Sources: contracts/book-platform.contract.v1.schema.json, contracts/README.md (Contract fields)

## Open questions

- ไม่มี
