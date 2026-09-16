# Krushi Seva Backend (Step 18)

FastAPI modular monolith — foundation + PostgreSQL + farmer authentication
+ My Farm + Crop Management + Crop Activities + Weather + Market Prices
+ AI Krushi Mitra (RAG, mock-first) + Crop Image Analysis (uncertain
observations only) + Soil Tests + Fertilizer Records + Pest & Disease
Tracking (records only) + Krushi Store Catalogue + Cart/Orders/Delivery
+ Payments (mock-first, webhook-driven) + Digital Khata ledger (read-only,
separate from payments) + Inventory/Suppliers/Purchases (Step 16)
+ Store Staff RBAC (Step 17) + Counter Billing/POS (Step 18: draft →
complete bills, server-authoritative totals, cash/UPI/card/credit recording,
Khata-linked credit, receipt JSON). Facts and manual records only — no diagnosis, dosages,
prescriptions, predictions, recommendations, selling beyond catalogue
display, or autonomous decisions. No GST engine, no real payment gateway.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then set a real DATABASE_URL (+ JWT secret)
alembic upgrade head
uvicorn app.main:app --reload
```

- Health: `GET /health` and `GET /api/v1/health` (dependency-free)
- DB probe: `GET /api/v1/health/db` → `{"status":"ok","database":"connected"}`
- Auth: `POST /api/v1/auth/send-otp`, `POST /api/v1/auth/verify-otp`,
  `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`
- Profile: `GET/PUT /api/v1/farmer/profile`
- Farms: `GET/POST /api/v1/farms`, `GET/PUT/DELETE /api/v1/farms/{id}`
  (soft delete), `GET/POST/PUT /api/v1/farms/{id}/soil`
- Crops: `GET/POST /api/v1/farms/{farm_id}/crops`,
  `GET/PUT/DELETE /api/v1/farms/{farm_id}/crops/{crop_id}` (soft delete),
  `GET /api/v1/crop-varieties`, `GET /api/v1/crop-varieties/{id}`
- Activities: `GET/POST /api/v1/farms/{fid}/crops/{cid}/activities`,
  `GET/PUT/DELETE …/activities/{aid}` (soft delete),
  `GET …/crops/{cid}/timeline` (chronological)
- Weather: `GET /api/v1/weather/current|forecast?latitude=&longitude=`,
  `GET /api/v1/farms/{id}/weather/current|forecast` (own farm's GPS)
- Market: `GET /api/v1/market/commodities|markets[/{id}]`,
  `GET /api/v1/market/prices[?filters]`, `GET /api/v1/market/prices/history`,
  `GET /api/v1/market/nearby?lat&lon&radius`,
  `GET /api/v1/farms/{id}/market-prices` (facts only, no selling)
- AI Krushi Mitra: `POST/GET /api/v1/ai/conversations`,
  `GET/DELETE /api/v1/ai/conversations/{id}`,
  `POST …/messages` (RAG answer + sources; mock-first, never fabricated)
- Crop image check: `POST /api/v1/crop-images` (multipart, 1–3 photos),
  `GET /api/v1/crop-images[/{id}]`, `GET …/{id}/image`,
  `POST …/{id}/analyze`, `DELETE …/{id}` (uncertain observations only)
- Soil tests: `GET/POST /api/v1/farms/{id}/soil-tests`,
  `GET/PUT/DELETE …/{test_id}` (soft delete),
  `POST …/{test_id}/report`, `GET …/{test_id}/report` (PDF/JPG/PNG, authed)
- Fertilizers: `GET/POST /api/v1/farms/{fid}/crops/{cid}/fertilizers`,
  `GET/PUT/DELETE …/{app_id}` (soft delete; usage records only)
- Pest & disease: `GET/POST /api/v1/farms/{fid}/crops/{cid}/health`,
  `GET/PUT/DELETE …/{obs_id}` (soft delete; tracking only),
  `GET /api/v1/pests`, `GET /api/v1/diseases`,
  `GET/POST /api/v1/health/{obs_id}/actions`,
  `PUT/DELETE …/actions/{aid}` (recorded actions only)
- Krushi Store: `GET /api/v1/store/categories[/{id}]`,
  `GET /api/v1/store/products[?search&filters]`, `GET …/products/{id}`,
  `GET …/products/{id}/variants|images`, `GET /api/v1/store/images/{id}`
  (catalogue display only — no cart/orders/payments)
- Cart & checkout: `GET /api/v1/store/cart`, `POST …/cart/items`,
  `PUT|DELETE …/cart/items/{item_id}`, `DELETE …/cart`,
  `POST …/cart/validate`, `POST /api/v1/store/checkout`
  (server-side totals, single transaction, payment pending)
- Addresses: `GET|POST /api/v1/store/addresses`,
  `PUT|DELETE …/{address_id}`, `POST …/{address_id}/default`
- Orders: `GET /api/v1/store/orders[/{order_id}[/items]]`,
  `POST …/{order_id}/cancel` (farmer: pending/confirmed only)
- Payments (mock-first): `POST /api/v1/payments/initiate`,
  `POST /api/v1/payments/webhook` (HMAC, idempotent),
  `GET /api/v1/payments/{payment_id}` (webhook drives order paid + Khata entry)
- Khata (read-only, separate): `GET /api/v1/khata/summary`,
  `GET /api/v1/khata/entries` (immutable ledger, farmer-scoped)
- Docs: http://localhost:8000/docs
- Guides: [`docs/database.md`](../docs/database.md),
  [`docs/authentication.md`](../docs/authentication.md),
  [`docs/farms.md`](../docs/farms.md),
  [`docs/crops.md`](../docs/crops.md),
  [`docs/crop-activities.md`](../docs/crop-activities.md),
  [`docs/weather.md`](../docs/weather.md),
  [`docs/market-prices.md`](../docs/market-prices.md),
  [`docs/ai-krushi-mitra.md`](../docs/ai-krushi-mitra.md),
  [`docs/rag.md`](../docs/rag.md),
  [`docs/crop-image-analysis.md`](../docs/crop-image-analysis.md),
  [`docs/soil-management.md`](../docs/soil-management.md),
  [`docs/pest-disease-management.md`](../docs/pest-disease-management.md),
  [`docs/store-catalogue.md`](../docs/store-catalogue.md),
  [`docs/store-orders.md`](../docs/store-orders.md)

## Migrations

```powershell
alembic upgrade head   # apply (creates system_info)
alembic current        # applied revision
alembic history        # revision chain (no DB needed)
alembic downgrade -1   # roll back last migration
```

## Tests

```powershell
pytest -q
```

## Structure

```
app/
├── main.py            # App factory, CORS, handlers, router mount
├── core/
│   ├── config.py      # Pydantic Settings incl. DATABASE_*, JWT_*, OTP_* (env-driven)
│   ├── errors.py      # AppError + global JSON error handlers
│   └── time.py        # UTC helpers (SQLite/PG parity for expiry checks)
├── db/
│   ├── base.py        # Declarative Base + UUID/timestamp mixins
│   ├── session.py     # Engine, session factory, get_db dependency
│   └── health.py      # check_database() → 503 DatabaseUnavailableError
├── models/            # users, farmer_profiles, otp_*, refresh_tokens, farms, soil_records, crop_varieties, farm_crops, farm_activities, weather_records, markets, market_commodities, market_prices, documents, document_chunks, ai_conversations, ai_messages, crop_image_analyses, soil_tests, fertilizer_applications, pests, diseases, crop_health_observations, health_actions, product_categories, products, product_variants, product_images, carts, cart_items, delivery_addresses, orders, order_items, order_status_history, order_counters (+ system_info)
└── modules/
    ├── auth/          # security, repository, service, schemas, dependencies, router
    ├── farmers/       # profile service, schemas, router
    ├── farms/         # schemas, repository, service, router (farm + soil, farmer-scoped)
    ├── crops/         # schemas, repository, service, router (nested crops + varieties)
    ├── activities/    # schemas, repository, service, router (nested activities + timeline)
    ├── weather/       # providers (abstraction + open-meteo), units, schemas, repository, service, router
    ├── market/        # providers (abstraction + disabled), units, schemas, repository, service, router
    ├── ai/            # providers (AI + embedding, mock-first), chunking, ingestion, retrieval, prompts, schemas, repository, service, router
    ├── vision/        # providers (mock-first), images (validation/quality), storage, schemas, repository, service, router
    ├── soil/          # schemas, reports (PDF/image validation), repository, service, router (tests + report files)
    ├── fertilizers/   # schemas, repository, service, router (usage records + activity reuse)
    ├── health/        # schemas, repository, service, router (observations + actions + photos, tracking only)
    ├── store/         # schemas, repository, service, router (catalogue reads + admin foundations, display only)
    ├── commerce/      # schemas, repository, service, router (cart/addresses/checkout/orders, no payments)
└── api/v1/
    ├── router.py      # v1 aggregator (health, health_db, auth, farmer, farms, crops, activities, weather, market, ai, vision, soil, fertilizers, pests/diseases/actions, store, commerce)
    └── endpoints/
        ├── health.py    # Liveness probe (no DB dependency)
        └── health_db.py # DB connectivity probe (SELECT 1)
alembic/
├── env.py             # URL from Settings, metadata from app.db.base.Base
└── versions/
    ├── 0001_create_system_info.py
    ├── 0002_create_auth_tables.py
    ├── 0003_create_farms.py
    ├── 0004_create_crops.py
    ├── 0005_create_activities.py
    ├── 0006_create_weather.py
    ├── 0007_create_market.py
    ├── 0008_create_ai_rag.py
    ├── 0009_create_crop_image.py
    ├── 0010_create_soil_fertilizer.py
    ├── 0011_create_pest_disease.py
    ├── 0012_create_store.py
    └── 0013_create_orders.py
scripts/
├── seed_crop_varieties.py  # DEV-ONLY catalogue seed (manual run, never production)
├── seed_market_sample.py    # DEV-ONLY sample prices, source-labelled (manual run, never production)
├── seed_pest_disease_sample.py  # DEV-ONLY unverified catalogue sample (manual run, never production)
└── seed_store_sample.py  # DEV-ONLY unverified catalogue + NULL prices (manual run, never production)
```

New domain modules MUST live under `app/modules/<domain>/`
(router.py, schemas.py, service.py, repository.py). See `docs/architecture.md`.
