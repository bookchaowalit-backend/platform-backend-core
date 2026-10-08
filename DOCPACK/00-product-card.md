---
title: Backend Core — Product Card
doc_id: CARD-bookchaowalit-backend-core
doc_type: product-card
verdict: template
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
---

# Backend Core — Product Card

## 1. สรุปคุณค่าในหนึ่งประโยค

baseline ของ org `bookchaowalit-backend` ที่ถือ schema `book-platform.contract.v1` ฉบับ canonical ให้ repo platform ใน `book-backend` ใช้ตรวจ contract เดียวกัน

## 2. ปัญหาและผู้ใช้เป้าหมาย

- ปัญหา: repo platform หลายตัวต้องใช้ schema เดียวกันโดยไม่ drift
- ผู้ใช้เป้าหมาย: repo platform ใน `book-backend` (vendored schema + sha256 pin)

## 3. สิ่งที่ทำได้จริงตอนนี้

- `contracts/book-platform.contract.v1.schema.json` + `.sha256` และตัวอย่าง valid 2 / invalid 7 กรณี (เช่น path traversal, unknown dependency)
- `scripts/check.py` ตรวจ baseline, subset ของ JSON Schema, pin และตัวอย่าง; `scripts/check_platform_sync.py` (82 บรรทัด) ตรวจว่า repo พี่น้องใช้ schema ตรงกัน
- test 2 ไฟล์ และ CI รันทุก push/PR
- ไม่มี runtime หรือ service

## 4. หลักฐานสถานะ

- Stack: Python 3.11 standard library (`scripts/check.py`, `unittest`), GitHub Actions
- Commits: 6 (แรก 2026-08-04 / ล่าสุด 2026-10-01), branch `main`
- Source: 4 ไฟล์ / 489 บรรทัด; test files: 2
- CI workflows: 1; deploy config: ไม่มี
- Live URL: ไม่มี
- README: 44 บรรทัด ("bookchaowalit-backend-core"); template family size: 1

## 5. คุณค่าและจุดต่าง

- เป็นแหล่งความจริงเดียวของ contract — มีคุณค่าในการ reuse ภายในจริง
- **[สมมติฐาน]** ไม่มีมุมรายได้

## 6. ช่องว่างสำคัญ

- ไม่มีโค้ด backend ที่ใช้ร่วมกันตามชื่อ
- คุณค่าผูกกับ platform split ที่ส่วนใหญ่ยังเป็น scaffold

## 7. คำตัดสิน

**template** — foundation/starter ที่มีประโยชน์จริงในฐานะเจ้าของ schema แต่ไม่ใช่ผลิตภัณฑ์ เงื่อนไขที่จะเปลี่ยนคำตัดสิน: ถ้า platform split ถูกยกเลิก ให้ย้าย schema กลับ `solo-empire` และ `archive`

## 8. ขั้นต่อไป

1. คง repo นี้เป็น canonical ของ schema และรัน `check_platform_sync.py` เมื่อ schema เปลี่ยน
2. พิจารณาให้ `book-security-platform` ใช้ schema/pin ให้ครบเหมือนพี่น้อง

## การอนุมัติ

| บทบาท | การตัดสินใจ | วันที่ |
|---|---|---|
| Product owner (Book Dev) | [ต้องยืนยัน] verdict `template` | — |

## แหล่งข้อมูล

- `bookchaowalit-backend/book-backend/bookchaowalit-backend-core/README.md`
- `bookchaowalit-backend/book-backend/bookchaowalit-backend-core/PRODUCT.md`
- `bookchaowalit-backend/book-backend/bookchaowalit-backend-core/contracts/`
- `bookchaowalit-backend/book-backend/bookchaowalit-backend-core/scripts/check_platform_sync.py`
