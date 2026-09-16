# Krushi Seva — Market Prices Foundation (Step 8)

> Scope: factual mandi price DATA (catalogue, quotes, history, nearby).
> NO selling, marketplace, orders, predictions, or recommendations — Step 8
> presents facts only.

## 1. Market architecture

```
MarketPriceProvider (ABC — service depends ONLY on this)
  └── DisabledProvider (default, fails closed; live source = new subclass)
        ↓ (validated quotes)
market.service (cache-first flow, ingest validation, haversine, farm view)
  → market_records: markets / market_commodities / market_prices (DB cache)
```

Swapping sources = new subclass + factory entry + MARKET_PROVIDER name;
no service/router changes. Mirrors the Step 7 weather module on purpose.

## 2. Provider abstraction

`get_current_prices(commodity?, market?, price_date?)` and
`get_price_history(commodity?, market?, from→to)` return normalized
`PriceQuote` dataclasses (Decimal money, explicit unit). `ProviderError`
carries no secrets/payloads. Raw payloads are never persisted. The default
`DisabledProvider` makes "no live source" a safe state: labelled DB rows
or 503 MARKET_DATA_UNAVAILABLE — never invented prices.

## 3. Data model

**markets**: UUID PK; name/state/district (+taluka/village nullable);
optional GPS (needed for nearby); is_active. **market_commodities**: UUID
PK; unique name; category + local_name; is_active. **Commodity ≠ crop by
design**: market sources use their own naming ("Soybean" vs "सोयाबीन"); a
future mapping table can link them without touching either side.
**market_prices**: UUID PK; market/commodity FKs CASCADE; `price_date`
(what the quote represents) separate from `fetched_at` (when ingested);
NUMERIC min/max/modal (never float); `unit` stored verbatim (CHECK
quintal/kg/tonne/other — never converted); currency (default INR);
`source` origin label; dedup unique key
(market, commodity, date, source); CHECKs (non-negative, min≤max,
modal-in-range); indexes on market+date, commodity+date, all three.

## 4. Commodity vs crop

Separate tables, separate concepts, separate endpoints. Rationale: external
naming conventions drift independently of the farmer's crop records.

## 5. Price units & validation

Units shown verbatim next to every value (₹5,100 / Quintal ≠ ₹51 / Kg).
Ingest rejects (skip + non-sensitive log, never silent fix): negatives,
min>max, modal outside [min,max], bad units, unknown market/commodity
names (catalogue stays admin-curated — no auto-creation). DB CHECKs
backstop the same rules.

## 6. Caching

DB-backed `market_prices` (service-level abstraction; Redis-ready later):
fresh-in-TTL → "cached" (no provider call); stale → refresh attempt →
"fresh"; provider fail + old rows → "stale" (labeled); empty → 503.
Refresh UPDATES rows in place (no buildup). TTL configurable
(`MARKET_CACHE_TTL_MINUTES`, default 360 — mandi prices move daily).

## 7. Nearby calculation

Haversine in Python over active geo-tagged markets (radius default 50 km,
max 500; farm view default 100 km), nearest-first with `distance_km`.
PostGIS-ready: replace the loop with ST_DWithin later, same signature.

## 8. API endpoints

| Method & path | Notes |
|---|---|
| `GET /market/commodities[?search=]` · `GET /market/commodities/{id}` | active only, 404 inactive/missing |
| `GET /market/markets[?state&district]` · `GET /market/markets/{id}` | active only |
| `GET /market/prices?commodity_id&market_id&state&district&price_date&limit&offset` | bounded (default 50, max 200), newest first, `data_state` |
| `GET /market/prices/history?commodity_id&market_id&from_date&to_date` | chronological; needs ≥1 id; ≤366 days; from≤to (422s) |
| `GET /market/nearby?latitude&longitude&radius_km` | validated coords, ordered + distance |
| `GET /farms/{id}/market-prices[?radius_km]` | own farm's GPS → nearby + latest quotes; 404 farm / FARM_LOCATION_MISSING |

All auth-required; price rows carry `unit`, `source`, `is_sample`.

## 9. Data freshness & failure

`data_state`: fresh (just refreshed) / cached (in TTL) / stale (labeled
fallback). `is_sample` flags dev-seed rows (source "SAMPLE (dev only)")
with a visible badge — sample can never pass as live. Empty result sets
→ 503 MARKET_DATA_UNAVAILABLE. Related codes: HISTORY_FILTER_REQUIRED,
HISTORY_INVALID_RANGE, HISTORY_RANGE_TOO_LARGE (422s), FARM_LOCATION_MISSING
(404). No raw provider exceptions surface.

## 10. Dev seed

`backend/scripts/seed_market_sample.py` — 4 Maharashtra markets (Lasur,
Jalna, Chhatrapati Sambhajinagar, Lasalgaon, real coords), 8 commodities,
7 days of clearly-labeled sample quotes. Idempotent, refuses production,
manual run only, never farmer sales.

## 11. Future tracks (untouched)

PostGIS nearby; live Agmarknet/eNAM provider subclass; selling/
marketplace, orders, payments (separate modules); price predictions and
"sell now" advice (require a validated decision-support system — explicitly
out of scope here, as is any buy/sell recommendation in UI copy).
