# InferSight — Backend

FastAPI analytics platform: JWT auth, time-series datasets, analytics, anomaly detection, forecasting, AI insights, and CSV/XLSX/PDF report exports.

## Stack

- **FastAPI** (0.141) + **Pydantic v2** + **SQLAlchemy 2.0** (sync ORM)
- **SQLite** for zero-config development, **PostgreSQL** for production (swap one env var)
- **PyJWT** access tokens + rotating, revocable refresh tokens (salted SHA-256 digests, bcrypt at 12 rounds)
- Optional **Redis** response cache — degrades to an in-process TTL cache when unreachable
- Optional **LLM enrichment** for insights (OpenAI / Anthropic / Google) — rule-based engine is the default
- **pytest** suite with isolated in-memory SQLite (98 tests)

## Project layout

```
backend/
├── app/
│   ├── api/            # FastAPI routers (auth, datasets, analytics, anomalies, forecasts, insights, reports)
│   ├── core/           # security: bcrypt + JWT + refresh-token rotation
│   ├── database/       # engine, session, init
│   ├── models/         # SQLAlchemy models (User, RefreshToken, Dataset, MetricPoint, Insight)
│   ├── schemas/        # Pydantic request/response models
│   └── services/       # business logic engines
├── scripts/seed.py     # demo user + sample revenue/transaction series
├── tests/              # pytest suite (isolated in-memory DB, dependency-override pattern)
├── .env.example        # every setting documented
└── requirements.txt
```

## Quickstart

```bash
# 1. create & activate a virtualenv, install deps
python -m venv .venv
.venv\Scripts\activate                 # Windows
pip install -r requirements.txt

# 2. configure
copy .env.example .env                # defaults target local SQLite — already valid

# 3. seed demo data (optional)
python -m scripts.seed                # demo@infersight.dev / demo12345

# 4. run
uvicorn app.main:app --reload
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

## Running the tests

```bash
python -m pytest tests -q
```

## Feature docs

- [Alert Routing & Escalation](../docs/alert-routing-escalation.md) — rules, routing pipeline, Celery delivery, Beat escalation.
- [Correlation-Based Root Cause Analysis](../docs/correlation-root-cause.md) — related-signals scoring, alignment, caching.
- [Dashboard Redesign](../docs/dashboard-redesign.md) — dark-slate design system and its application.

The suite uses an **isolated in-memory SQLite** database bound to a `StaticPool`, with `AUTO_CREATE_TABLES=false` so tests never touch a file or the dev DB. The `get_db` dependency is overridden per test, the cache is reset between tests, and a bootstrap admin is created in the test DB only.

## Frontend

A React + TypeScript dashboard lives in `../frontend` (Vite). See its README for run steps; the dev server proxies `/api` to this backend on `localhost:8000`.

## Manual operations

### Swap SQLite → PostgreSQL

The Postgres driver (**psycopg v3**) is already in `requirements.txt`, so no
extra install is needed.

1. Point `DATABASE_URL` at your instance:

   ```env
   DATABASE_URL=postgresql+psycopg://infersight:password@localhost:5432/infersight
   ```

   A bare `postgresql://` URL (like Render's injected connection string) is
   normalized to `postgresql+psycopg://` at startup.

2. `AUTO_CREATE_TABLES=true` creates the schema on startup (development convenience).
   For production, generate migrations instead:

   ```bash
   pip install alembic
   alembic init migrations
   alembic revision --autogenerate -m "initial schema"
   alembic upgrade head
   ```

   then set `AUTO_CREATE_TABLES=false`.

### Redis caching

Enabled by default (`REDIS_ENABLED=true`). If Redis isn't reachable, the cache layer logs a warning and falls back to an in-process TTL cache — nothing breaks. Disable entirely with `REDIS_ENABLED=false`. The analytics endpoint and login rate limiter are the main consumers.

### LLM-powered insights

The insight engine is deterministic (rule-based) by default. To let it write prose summaries, set one of:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
# or ANTHROPIC_API_KEY=... / GOOGLE_API_KEY=...
```

When the API key is invalid or the provider is unreachable, generation **degrades silently** to the rule-based output — insights never fail because of the LLM. If no key is configured, the `enrich_with_llm` query flag is ignored.

### Running against the live frontend

```bash
uvicorn app.main:app --reload --port 8000     # backend
npm run dev                                    # frontend on :5173, proxies /api -> :8000
```

## Deploying

### Backend → Render

A `render.yaml` blueprint sits at the repo root. It provisions a Python web
service plus a managed Postgres database.

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** and select the repo.
3. After the first deploy, set these values in the service dashboard:
   - `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(64))"`
   - `ADMIN_PASSWORD` — a strong bootstrap-admin password
   - `CORS_ORIGINS` — your Vercel frontend origin (e.g. `https://infersight.vercel.app`)
4. Redeploy. The API lives at `https://<service>.onrender.com`, with `/health`
   and `/docs` ready to use.

If you'd rather create the service by hand instead of the blueprint:
`New → Web Service → repo → Root directory: backend` → build `pip install -r
requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`,
attach a Postgres database, and set the env vars above.

### Frontend → Vercel

The frontend is a standard Vite SPA; `frontend/vercel.json` adds an SPA rewrite
so deep links (`/app/dashboard`) resolve.

1. Push to GitHub, then **Vercel → Add New → Project** with the `frontend`
   directory as root.
2. Set the environment variable:
   - `VITE_API_URL=https://<your-render-service>.onrender.com/api/v1`
3. Deploy. Everything works out of the box — the API client falls back to
   `/api/v1` (the local Vite proxy) when `VITE_API_URL` is unset.

CORS note: the browser enforces the origin on the *backend*. Any new frontend
origin (local dev server, Vercel domain, custom domain) must be listed in the
backend's `CORS_ORIGINS`.

## Security notes

- Passwords hashed with **bcrypt** (12 rounds); never stored or logged in plaintext.
- Access tokens: 30-min HS256 JWTs with `sub` + `exp`. Refresh tokens are stored as salted SHA-256 digests, single-use (rotated on every refresh), revocable per-device or globally.
- Login/register are rate-limited (20 req / 5 min per client).
- Dataset access is **strictly per-user** — resources are scoped to their owner.
- Pydantic validators enforce password strength, slug format, granularity, and metric types; all inputs are bounded (`max_points`, `limit`, `horizon`, etc.).
- Swap `SECRET_KEY` in production (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) and set `ENVIRONMENT=production`, `DEBUG=false`.

## API surface

| Group | Routes |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`, `POST /auth/change-password`, `/auth/revoke-sessions` |
| Datasets | CRUD `/datasets`, `GET/POST /datasets/{id}/points` (idempotent ingest) |
| Analytics | `GET /analytics/datasets/{id}` (+ `/kpis`, `/series`, `/trend` sub-routes) |
| Anomalies | `GET /anomalies/datasets/{id}` (robust rolling z-score) |
| Forecasts | `GET /forecasts/datasets/{id}` (linear / exponential smoothing / Holt, holdout-scored) |
| Insights | `POST /insights/datasets/{id}`, `GET /insights`, `DELETE /insights/{id}` |
| Related signals | `GET /intelligence/{id}/anomalies/{index}/related`, `POST /intelligence/{id}/root-cause` |
| Alert rules | CRUD `/alert-rules`, `GET /alerts/{id}/deliveries` |
| Reports | `GET /reports/datasets/{id}.{csv,xlsx,pdf}` |
