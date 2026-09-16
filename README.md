# 🌱 Krushi Seva

**Production-ready agriculture platform for Indian farmers** — farmer & farm
management, crops, weather, mandi prices, advisory, AI Krushi Mitra assistant,
RAG knowledge system, disease/image analysis, marketplace, orders & payments,
ledger/expenses, expert consultation, government schemes, notifications, admin.

> ⚠️ **STEP 14 — foundation + database + auth + My Farm + Crops +
> Activities + Weather + Market + AI Krushi Mitra (RAG, mock-first) +
> Crop Image Analysis (uncertain observations only) + Soil Tests +
> Fertilizer Records + Pest & Disease Tracking (records only) +
> Krushi Store Catalogue + Cart/Orders/Delivery (no payments).**
> No diagnosis, dosages, prescriptions, predictions, recommendations,
> selling beyond catalogue display, payments, or autonomous decisions yet.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + plain CSS (responsive) |
| Backend | Python 3.11+ + FastAPI + Pydantic v2 / pydantic-settings |
| Database (Step 2+) | PostgreSQL (+ pgvector for future RAG) |
| Cache/jobs (future) | Redis |
| AI/RAG (future) | Python module under `ai/` |
| Infra (optional) | Docker Compose (postgres/redis, profile-gated) |

See [`docs/architecture.md`](docs/architecture.md) for decisions,
[`docs/development.md`](docs/development.md) for setup,
[`docs/database.md`](docs/database.md) for PostgreSQL/Alembic,
  [`docs/authentication.md`](docs/authentication.md) for OTP/JWT auth,
  [`docs/farms.md`](docs/farms.md) for the My Farm module,
  [`docs/crops.md`](docs/crops.md) for crop management,
  [`docs/crop-activities.md`](docs/crop-activities.md) for activities/timeline,
  [`docs/weather.md`](docs/weather.md) for the weather foundation,
  [`docs/market-prices.md`](docs/market-prices.md) for market prices,
  [`docs/ai-krushi-mitra.md`](docs/ai-krushi-mitra.md) for the assistant,
  [`docs/rag.md`](docs/rag.md) for the knowledge base,
  [`docs/crop-image-analysis.md`](docs/crop-image-analysis.md) for image analysis,
  [`docs/soil-management.md`](docs/soil-management.md) for soil + fertilizer records,
  [`docs/pest-disease-management.md`](docs/pest-disease-management.md) for pest/disease tracking,
  [`docs/store-catalogue.md`](docs/store-catalogue.md) for the Krushi Store catalogue, and
  [`docs/store-orders.md`](docs/store-orders.md) for cart/orders/delivery.

## Folder structure

```
├── apps/
│   ├── web/        # Next.js frontend (runs now)
│   └── mobile/     # Placeholder — React Native/Expo later
├── backend/        # FastAPI modular monolith (runs now, /health)
│   └── app/
│       ├── main.py
│       ├── core/         # config + typed errors
│       └── api/v1/       # versioned routers (health only in Step 1)
├── ai/             # Placeholder — RAG / vision later
├── database/       # Placeholder — migrations/seeds (Step 2+)
├── docs/           # architecture.md, development.md
├── scripts/        # dev.ps1 / dev.sh helpers
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start

**1. Env files:**

```powershell
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
Copy-Item backend\.env.example backend\.env
```

**2. Backend (http://localhost:8000/health):**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**3. Frontend (http://localhost:3000):**

```powershell
cd apps\web
npm install
npm run dev
```

Full guide + troubleshooting: [`docs/development.md`](docs/development.md).

## Health checks

| Service | Endpoint | Expected |
|---|---|---|
| Backend | `GET /health` | `{"status":"ok","service":"krushi-seva-backend",...}` |
| Backend (v1) | `GET /api/v1/health` | `{"status":"ok",...}` |
| Backend DB probe | `GET /api/v1/health/db` | `{"status":"ok","database":"connected"}` (503 when DB down) |
| Frontend | `GET /api/health` | `{"status":"ok","service":"krushi-seva-web",...}` |

Backend OpenAPI docs: http://localhost:8000/docs

## Commands cheat-sheet

```powershell
# backend tests
cd backend; pytest -q

# frontend checks
cd apps\web; npm run lint; npm run typecheck; npm run build
```

## Future module roadmap

1. **Step 2:** Postgres + Alembic, auth skeleton, farmer/farm/crop CRUD.
2. **Step 3:** Weather, mandi prices, advisory, schemes, notifications.
3. **Step 4:** Marketplace, orders/payments, ledger/expenses, experts, admin.
4. **Step 5:** `ai/` RAG knowledge base (pgvector), Krushi Mitra assistant, disease/image analysis.

Contributions: Step 1 is closed — do not add domain features until Step 2 is scoped.
