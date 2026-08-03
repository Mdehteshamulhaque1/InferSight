# QA Log — Final Verification Pass

Date: 2026-08-03
Scope: full project verification after the Copilot upload-first implementation
(commit `277dec3`), followed by cleanup and bug fixes.

## Summary

| Check | Result |
| --- | --- |
| Backend unit/integration tests | 107 passed (was 98) |
| Frontend build (`tsc --noEmit && vite build`) | Clean, strict TS flags enabled |
| Live API smoke test (62 routes, 93 assertions) | 93 passed, 0 failed |
| Dead-code / unused-import audit | 12 unused imports removed, 2 TS issues fixed |
| Git hygiene | `.gitignore` solid; no secrets; tracked files verified legitimate |

## New Test Coverage Added

`backend/tests/test_copilot.py` (9 tests) covers previously untested surface:

- `GET /api/v1/datasets/{id}/summary` — full composite payload shape, min-points
  422, per-user caching, cross-tenant 404.
- `POST /api/v1/ingest/auto` — upload-first dataset creation + immediate
  analyzability, bad-file 422, short-filename regression test.
- `POST /api/v1/ingest/preview` — no-dataset file preview.
- Per-user rate limiting — `POST /api/v1/chat` (30/60s) and
  `POST /api/v1/ingest/auto` (30/300s) return 429 after the budget is spent.

## Bugs Found & Fixed

1. **Summary cache consistency** (`app/api/v1/intelligence.py`) — Cached and
   uncached `/summary` responses were NOT byte-identical: on the uncached path
   FastAPI serializes `datetime` values as ISO-8601 `Z` format, while the cache
   (`json.dumps(default=str)`) stored them as `+00:00` space format. Introduced
   `_normalize_timestamps()` so the cached payload and the returned payload
   match exactly for forecast points and KPI metadata timestamps.

2. **`/ingest/auto` 500 on short filenames** (`app/api/v1/ingestion.py`) —
   Uploading a file whose inferred dataset name is one character (e.g.
   `r.csv`) raised an unhandled `ValidationError` (500). Fixed `_infer_name()`
   to fall back to `"<column> dataset"` for names shorter than 2 chars, and
   added a defensive `ValidationError` → 422 guard in `auto_import()`.

## Cleanup

- Removed 12 unused backend imports (AST-verified) across `api/v1/analytics.py`,
  `api/v1/datasets.py`, `models/insight.py`, and 7 service modules. Intentional
  `__init__.py` re-exports and `from __future__ import annotations` retained.
- Removed 1 unused import in `frontend/src/api/ingestion.ts` and 1 unused map
  parameter in `frontend/src/components/layout/CommandPalette.tsx`.
- Enabled `noUnusedLocals` and `noUnusedParameters` in `frontend/tsconfig.json`
  so regressions fail the build.
- Deleted stray broken venv at `backend/.venv` (gitignored cruft).

## Verified Negative (no issues)

- No TODO/FIXME/debug-log statements in application code (backend `print()`s
  exist only in `scripts/seed.py`, which is intentional).
- No dead frontend components; all files under `src/components` are referenced.
- Auth lifecycle, org RBAC, cross-tenant isolation, versioning/rollback, alert
  deliveries, exports (CSV/XLSX/PDF), and rate limits all pass end-to-end.
