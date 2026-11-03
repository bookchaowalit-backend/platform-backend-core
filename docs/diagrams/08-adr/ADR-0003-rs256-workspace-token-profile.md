# ADR-0003 — RS256 workspace token profile; signed `ws` is the only workspace; reject delegation

- Status: accepted (retro-documented)

## Decision
`TokenVerifier` รับเฉพาะ RS256, issuer ตรง, audience เดียว (`strict_aud`), ต้องมี `sub ws iat exp jti iss aud`, lifetime ≤ ค่าที่ตั้ง (≤86400),
leeway 0..60 s, token ≤16 KiB; key source ต้องมีหนึ่งเดียว (PEM / injected / HTTPS JWKS); ถ้ามี `del` หรือ `obo` ปฏิเสธ;
workspace มาจาก `ws` ที่ลงนามเท่านั้น ไม่เคยจาก header/body

## Evidence
- src/platform_backend_core/auth.py (`verify`, `_JWKS`)
- docs/runtime.md (Stable public interface)
- runtime_tests/test_auth.py (`test_unsupported_delegation_claims_are_rejected_even_when_null`), runtime_tests/test_http.py (header `X-Workspace-ID` ถูกเพิกเฉย)
- commit 2d0ea51 "fix: reject unsupported delegated workspace tokens"

## Consequences
- ไม่มี revocation / jti replay check ใน core (runtime.md: shared services cannot enforce revocation)
- JWKS rotation เห็นผลช้าสุด ~1 นาที; refresh ล้มเหลว = fail closed
