# Krushi Seva — Store Cart, Orders & Delivery (Step 14)

> Scope: cart, checkout validation, orders with snapshotted items, delivery
> addresses, order status tracking. NO payment gateway — every order is
> created with `payment_status = "pending"` and stays there (Step 15 owns
> processing). Never fake payment success.

## 1. Cart architecture

`carts`: UUID PK; `farmer_id` FK CASCADE (derived server-side, never from
the client); status CHECK (active/converted/abandoned). Exactly one
`active` cart per farmer (`get_or_create_active_cart`; converted carts are
history, never reused). `cart_items`: UUID PK; cart FK CASCADE; variant FK
CASCADE; quantity > 0 CHECK; UNIQUE(cart_id, product_variant_id) — adding
the same variant twice merges quantity (capped), never duplicates rows.
Items link variants ONLY — no copied names/prices (live catalogue data is
joined at read time).

## 2. Cart validation

`POST /store/cart/validate` (and every checkout) reports per-line issues —
never silently removes lines: VARIANT_INACTIVE / PRODUCT_INACTIVE /
PRODUCT_UNAVAILABLE (only `unavailable` blocks; low/out_of_stock remain
purchasable at catalogue level) / QTY_LIMIT / PRICE_UNAVAILABLE. Empty
issues == safe to checkout. Quantity caps are configurable
(`CART_MAX_QTY_PER_ITEM`, `CART_MAX_ITEMS`).

## 3. Address architecture

`delivery_addresses`: UUID PK; farmer FK CASCADE; full_name, mobile
(normalized to 10-digit Indian format, same validator as auth), address
lines, village/taluka/district/state, 6-digit pincode (digits extracted,
strictly validated), landmark; `is_default` (exactly one — first created
wins, delete passes it to the newest remaining); `is_active` soft delete.
Owner-scoped CRUD + set-default; cross-farmer access 404s uniformly.

## 4. Checkout transaction

`POST /store/checkout {address_id, notes?}` runs 16 spec steps inside ONE
transaction: load farmer → active cart (non-empty) → validate every line
→ re-read live prices → validate address ownership → server-side totals
(subtotal + configurable delivery − zero discount) → snapshot items →
create order + items + "placed" history → cart `converted` → fresh active
cart. Single commit; any failure rolls back (SQLAlchemy discards
uncommitted state), so partial orders are structurally impossible. Tested
by fault injection. Order numbers (`KSK-YYYY-NNNNNN`) come from a per-year
counter table with a unique constraint + bounded retry (concurrency-safe).

## 5. Price snapshotting

Order items persist product_name/brand/pack_size/pack_unit/unit_price/
quantity/line_total (all NUMERIC/Decimal, never float). `product_variant_id`
is kept but NULLABLE so deactivation never breaks history — reads never
join the catalogue for orders. Tamper attempts (extra price/total fields)
are ignored or rejected; server math always wins (tested).

## 6. Order architecture

`orders`: UUID PK; unique human number (DB ids never shown as numbers);
farmer FK CASCADE; address FK SET NULL + `address_snapshot` text (address
edits can't rewrite history); status/payment CHECKs; NUMERIC
subtotal/delivery/discount/total; currency INR; `placed_at`.
`order_status_history`: append-only (order FK CASCADE), one row per
transition including creation ("Order placed").

## 7. Order status machine

pending → confirmed → processing → packed → shipped → out_for_delivery →
delivered; cancel allowed from pending/confirmed only. Invalid jumps
(e.g. pending → delivered) rejected with `ORDER_TRANSITION_INVALID`.
Farmers can NEVER set status (no endpoint exists — guessed routes 404);
farmer cancel is pending/confirmed-only (`ORDER_CANCEL_INVALID`
otherwise). Admin transitions live in service functions
(`admin_list/get/set_status`) with NO routes in Step 14 — a future
authorized admin layer adds endpoints around them.

## 8. Authorization

Bearer auth everywhere; farmer derived server-side; cart/address/order
rows resolve through owned farmer_id; uniform 404s (no existence oracle);
unknown admin paths 404/405. Cart/address/order tests assert cross-farmer
isolation per operation.

## 9. Price tampering protection

Request schemas carry ids + quantities + addresses ONLY. Checkout ignores
unknown fields; totals recompute from live DB rows; history reads
snapshots. Covered by dedicated tests.

## 10. Cancellation

Farmer: pending/confirmed → cancelled (+ history row), order retained.
Terminal/shipped+ states → 422. No deletion, ever.

## 11. Future payment integration (untouched)

Step 15 adds gateway intents against `orders.id`/`total_amount`,
transitions `payment_status` pending → paid/failed (+ refunded flow),
and webhooks — checkout and history need zero changes (payment stays a
status column + external records, never inline card data).
