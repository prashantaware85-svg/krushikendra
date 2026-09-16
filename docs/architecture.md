# Krushi Seva — Architecture (Step 1)

> Status: **STEP 1 — foundation only.** No business features yet.
> Last updated: 2026-09-04

## 1. Purpose

**Krushi Seva** is a production-ready agriculture platform for Indian farmers
(farmer/farm/crop management, weather, mandi prices, advisory, AI Krushi Mitra,
RAG knowledge system, disease/image analysis, marketplace, orders/payments,
ledger/expenses, expert consultation, government schemes, notifications, admin).

Step 1 establishes a clean, scalable skeleton so future modules can be added
without rewrites.

## 2. High-level architecture

We use a **modular monolith** (not microservices) at this stage:

```
┌──────────────┐      HTTP/JSON       ┌───────────────────┐
│  apps/web    │ ───────────────────▶ │  backend (FastAPI)│
│  Next.js 14+ │                      │  modular monolith │
│  TypeScript  │ ◀─────────────────── │  /api/v1/*        │
└──────────────┘                      └─────────┬─────────┘
                                                │ (Step 2+)
                                      ┌─────────▼─────────┐
                                      │ PostgreSQL (+pgvector
                                      │ for future RAG)   │
                                      │ Redis (future:    │
                                      │ cache/jobs)       │
                                      └───────────────────┘
                                      ┌───────────────────┐
                                      │ ai/ (future)      │
                                      │ Python RAG +      │
                                      │ vision services   │
                                      └───────────────────┘
```

### Why modular monolith?

| Decision | Rationale |
|---|---|
| Modular monolith over microservices | Single deployable, low ops overhead, still enforces module boundaries. Split later only if scale demands it. |
| Next.js App Router + TypeScript | Modern React, SSR/SSG ready, file-based routing, strong typing for farmer/market data models later. |
| FastAPI + Pydantic v2 | Async, auto OpenAPI docs, Pydantic Settings for 12-factor config. Ideal for AI/Python interop. |
| PostgreSQL (+ pgvector later) | Single source of truth; pgvector enables RAG without a second vector DB. Not wired in Step 1. |
| Redis later, not now | Added to compose/docs as a placeholder; no code dependency in Step 1 to avoid over-engineering. |
| `ai/` as separate folder, not service | Keeps future RAG/vision code isolated; backend will call it via internal module or HTTP once defined. |

## 3. Repository layout

```
krushi-seva/                  # repo root (= this folder)
├── apps/
│   ├── web/                  # Next.js frontend (Step 1: foundation + /api/health)
│   └── mobile/               # Placeholder (Step 1: README only, React Native/Expo later)
├── backend/                  # FastAPI modular monolith
│   └── app/
│       ├── main.py           # App factory, middleware, exception handlers, router mount
│       ├── core/
│       │   ├── config.py     # Pydantic Settings (env-driven, 12-factor)
│       │   └── errors.py     # Typed AppError + global handlers → consistent JSON errors
│       └── api/v1/
│           ├── router.py     # v1 aggregator — mount future modules here
│           └── endpoints/
│               └── health.py # GET /api/v1/health (liveness, no DB dependency)
├── ai/                       # Placeholder for future RAG/vision service
├── database/                 # Placeholder for migrations/seeds (Step 2+)
├── docs/
│   ├── architecture.md       # This file
│   └── development.md        # Local setup guide
├── scripts/                  # Dev helper scripts (e.g. dev.ps1)
├── docker-compose.yml        # Optional local infra (postgres/redis, profile-gated)
├── .env.example              # Root env template
└── README.md
```

## 4. Backend module conventions (to follow from Step 2 onward)

Each future domain (e.g. `farmers`, `crops`, `markets`) MUST live under
`backend/app/modules/<domain>/` with this shape:

```
backend/app/modules/<domain>/
├── router.py      # APIRouter with prefix + tags
├── schemas.py     # Pydantic request/response models
├── service.py     # Business logic (no FastAPI imports)
└── repository.py  # DB access only (Step 2+)
```

Rules:
- Routers are thin: validate → call service → return schema.
- Services hold business logic; never import `Request`/`APIRouter`.
- Shared code goes to `app/core/` (config, errors, security later).
- Version API under `/api/v1`; breaking changes → `/api/v2`.

## 5. Frontend conventions

- App Router (`apps/web/app/`), TypeScript `strict: true`.
- No global state library in Step 1; evaluate Zustand/React-Query when server state appears.
- Backend URL via `NEXT_PUBLIC_API_URL` (see `apps/web/.env.example`).
- Styling: plain CSS (`globals.css`) in Step 1 — Tailwind/shadcn can be adopted in Step 2 without rewrites.

## 6. Configuration & errors (Step 1 scope)

- **Config:** `backend/app/core/config.py` uses `pydantic-settings`. All env-driven,
  validated at startup. Fails fast on bad config.
- **Errors:** `backend/app/core/errors.py` defines `AppError(code, message, status_code)`
  + handlers for `AppError`, `RequestValidationError`, and catch-all `Exception`.
  All errors return `{ "error": { "code": "...", "message": "..." } }`.
- **Health:** `GET /health` (root, infrastructure liveness) and
  `GET /api/v1/health` (versioned API liveness). Both are dependency-free
  (no DB check) so orchestrators/load-balancers can use them safely.

## 7. What is explicitly OUT of Step 1

Auth, DB models/migrations, AI/RAG, pgvector, payments, marketplace, weather,
farmer/crop features, background jobs, notifications. Placeholders + docs only.

## 8. Future roadmap (high level)

1. Step 2: Postgres wiring, Alembic migrations, auth skeleton, farmer/farm CRUD.
2. Step 3: Weather/market integrations, advisory, schemes, notifications.
3. Step 4: Marketplace, orders/payments, ledger/expenses, expert consult, admin.
4. Step 5: `ai/` RAG knowledge base (pgvector), Krushi Mitra assistant, disease/image analysis.
