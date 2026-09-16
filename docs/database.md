# Krushi Seva — Database Setup (Step 2)

> Scope: PostgreSQL foundation only — engine/session config, Alembic, one
> `system_info` verification table, `GET /api/v1/health/db`. No business
> tables yet (users, farms, … arrive in Step 3+).

## 1. PostgreSQL requirement

- **PostgreSQL 14+** (16 recommended) running locally or reachable over the network.
- You need a role + empty database, e.g. database `krushi_seva`.
- No extensions required in Step 2. (`pgvector` will be enabled in the future
  AI/RAG step — nothing to install now.)

Create the database (example):

```sql
-- in psql as a superuser
CREATE ROLE krushi WITH LOGIN PASSWORD 'choose-a-strong-password';
CREATE DATABASE krushi_seva OWNER krushi;
```

## 2. Environment variables

Copy the template and fill in **real** credentials (the `.env` file is
gitignored and must never be committed):

```powershell
Copy-Item backend\.env.example backend\.env
```

| Variable | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:password@localhost:5432/krushi_seva` | SQLAlchemy URL (sync `psycopg` driver). Password only ever lives in `.env`. |
| `DATABASE_POOL_SIZE` | `10` | Persistent `QueuePool` connections. |
| `DATABASE_MAX_OVERFLOW` | `20` | Extra burst connections beyond the pool. |
| `DATABASE_CONNECT_TIMEOUT` | `5` | Seconds before a connect attempt fails fast (keeps `/health/db` honest). |

Validate at startup: `Settings` (see `backend/app/core/config.py`) rejects a
bad `ENVIRONMENT` and coerces pool sizes; the app fails fast on bad config.

## 3. Install dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # includes SQLAlchemy 2.x, Alembic, psycopg[binary]
```

## 4. Running Alembic migrations

All commands run from `backend/` (where `alembic.ini` lives). Alembic reads
the live URL from `DATABASE_URL` via `app.core.config.Settings` — the URL in
`alembic.ini` is a placeholder and is always overridden.

```powershell
cd backend

# Apply all pending migrations (creates system_info)
alembic upgrade head

# Verify what is applied
alembic current        # shows current revision, e.g. 0001_system_info
alembic history        # full revision chain (works WITHOUT a live DB)
```

Step 2 ships exactly one migration: `0001_system_info` (creates the
`system_info` key/value table used to prove migrations work end-to-end).

## 5. Checking migration status

```powershell
cd backend
alembic current        # revision the database is on (needs DB connection)
alembic history        # revision chain on disk (no DB needed)
alembic check          # exit non-zero if models diverged from migrations
```

## 6. Rolling back a migration

```powershell
cd backend
alembic downgrade -1   # revert the last applied migration (drops system_info)
alembic upgrade head   # re-apply
```

## 7. Database health endpoint

With the backend running (`uvicorn app.main:app --reload`):

- `GET /api/v1/health/db` → database reachable:
  ```json
  { "status": "ok", "database": "connected" }
  ```
- Database down/unreachable → `503` with a generic envelope (no host, user,
  password, or DSN details are ever returned):
  ```json
  { "error": { "code": "DATABASE_UNAVAILABLE", "message": "Database is currently unavailable. Please try again later." } }
  ```

Unlike `GET /health` (dependency-free liveness), `/health/db` opens a real
connection (`SELECT 1`) and is the correct probe for DB readiness.

## 8. Conventions for future tables (Step 3+)

- Models live in `backend/app/models/<domain>.py`, inherit `app.db.base.Base`,
  and are imported in `backend/app/models/__init__.py` (so Alembic sees them).
- Primary keys: UUID via `UUIDPrimaryKeyMixin` — no auto-increment integers.
- Timestamps: UTC via `TimestampMixin` (`server_default=func.now()`).
- Request-scoped sessions via the `get_db` FastAPI dependency
  (`backend/app/db/session.py`) — always closed in `finally`, never leaked.
- New migrations: `alembic revision --autogenerate -m "describe change"`,
  review the generated diff, then `alembic upgrade head`.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `/health/db` returns 503 | Postgres not running, wrong `DATABASE_URL`, or firewall — check `backend/.env`, then `Test-NetConnection 127.0.0.1 -Port 5432` |
| `connection refused / timeout` from Alembic | Same as above; Alembic uses the same `DATABASE_URL` |
| `password authentication failed` | Role/password mismatch — reset with `ALTER ROLE krushi WITH PASSWORD '...'` |
| `database "krushi_seva" does not exist` | `CREATE DATABASE krushi_seva OWNER krushi;` |
| Tests fail importing `psycopg` | Re-run `pip install -r requirements.txt` in the active venv |
