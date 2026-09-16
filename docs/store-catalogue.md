# Krushi Seva — Krushi Store Product Catalogue (Step 13)

> Scope: browsable product catalogue (categories, products, packs, photos).
> NO cart, orders, payments, delivery, checkout, refunds, coupons, reviews,
> seller marketplace, or farmer-to-farmer selling — those are future steps.

## 1. Category architecture

`product_categories`: UUID PK; name/slug (unique, indexed); description;
self-referencing `parent_id` (SET NULL, NULL = top level) for trees like
Seeds → Cotton/Soybean/Maize/Vegetable Seeds, Fertilizers → NPK/Organic/
Micronutrients, Crop Protection → Insect/Disease/Weed Control, plus Bio
Products, Agricultural Accessories, Other. Category IDs are UUIDs generated
at insert — never hard-coded. No admin endpoints in Step 13 (service
functions reserved for a future authorized admin layer).

## 2. Product model

`products`: UUID PK; `category_id` FK SET NULL (survives category removal);
name/slug (unique); short/description; brand/manufacturer (facts only);
`product_type` CHECK (seed/fertilizer/crop_protection/bio_product/
accessory/other); `registration_number` + `manufacturer` stored ONLY when
genuinely known — blank, never invented; `is_active` (farmer visibility);
`is_verified` default false, exposed verbatim so the UI shows Verified vs
pending (never the reverse). Products and crops stay INDEPENDENT (no FK
either way) so the catalogue can never become a recommendation engine.

## 3. Product variants / pack sizes

`product_variants`: UUID PK; product FK CASCADE; `pack_size` NUMERIC(10,3)
> 0 CHECK; `pack_unit` CHECK (gram/kg/ml/litre/piece/packet/bag/other);
optional unique `sku`; `mrp`/`selling_price` NUMERIC(12,2) ≥ 0 CHECKs,
NULLABLE — NULL means unknown and the UI renders "price unavailable",
never a fabricated value; `stock_status` CHECK
(in_stock/low_stock/out_of_stock/unavailable) — catalogue-level
availability ONLY, not inventory management (a future module owns counts).

## 4. Pack sizes

Stored verbatim in the source unit (`1 kg`, `500 ml`); never converted
between units (₹/Quintal ≠ ₹/Kg rule from market data applies in spirit).
Range of units above covers seeds/liquids/tools; `other` escapes cleanly.

## 5. Product images

`product_images`: UUID PK; product FK CASCADE; opaque `image_reference`
(never bytes/paths); `alt_text`, `sort_order`, `is_primary`. Binaries live
in object storage via the reused Step 10 `LocalImageStorage` CLASS with a
dedicated root (`storage/store_images`, gitignored) — same contract, no
duplicated logic. Uploads validated by the Step 10 gates (magic bytes,
size/dimension caps, darkness/blur heuristics). Bytes served only through
the authed `/store/images/{id}` route (no public URLs). Admin-side add
exists as a service function (no farmer endpoint).

## 6. Price handling

NUMERIC end-to-end, JSON strings on the wire (repo Decimal convention).
Display rules (frontend): both present → MRP + Selling Price; MRP only →
MRP; neither → "किंमत उपलब्ध नाही". No conversions, no predictions, no
"best deal" labels.

## 7. Verification

`is_verified` default false; `admin_verify_product` is an explicit grant
(never automatic). UI shows ✓ Verified Product vs Verification pending
from the flag — unverified rows are NOT hidden (distinguishable, never
misrepresented). Seed rows are unverified with sample branding.

## 8. Regulatory fields

`registration_number`, `manufacturer`, `product_type` record facts when
known; unknown stays blank. No dosage, mixing, spray, or safety text is
generated from the catalogue — those prohibitions are release gates.

## 9. Search / filter

`GET /products` supports `search` (ilike across name/brand/manufacturer/
category), `category_id`, `product_type`, `brand` (exact, case-insensitive),
`stock_status` (any active matching variant), `limit` (default 20, max
100) + `offset`. Only active products; newest-first is name-ordered for
stable browsing. No unbounded responses.

## 10. Authorization

Catalogue + image-byte routes require auth (Bearer) but no roles in Step
13 — every farmer reads the same shared catalogue. Management exists ONLY
as service functions (create/update/deactivate/verify/add-variant/add-image);
there are deliberately NO POST/PUT/DELETE store routes, so normal farmers
cannot reach them (unknown paths 404 — tested). A future admin layer adds
authorization + endpoints around these functions.

## 11. Admin foundation

Service functions ready: create/update/deactivate category; create/update/
deactivate/verify product; add/update variant; add product image
(validated + stored + linked). Tested directly (no HTTP).

## 12. Safety limitations (binding)

No pesticide/fertilizer dosage, mixing, schedules, prescriptions; no crop→
product recommendations ("cotton → buy X" forbidden); no disease→product
mapping; no price predictions; catalogue NEVER linked to AI advisory
automatically. Product info stays separate from advisory, enforced by the
absence of any FK, import, or call between the modules.

## 13. Future cart/order/payment architecture (untouched)

Future `cart_items` (user + variant + qty), `orders`/`order_items`
(snapshotted prices), payment intents, delivery addresses, invoices —
all new tables referencing `product_variants.id`; catalogue tables need
zero changes (prices snapshotted at order time, never live-joined).
