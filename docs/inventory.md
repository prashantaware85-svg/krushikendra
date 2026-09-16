# Krushi Seva — Inventory, Purchases & Suppliers (Step 16)

> Scope: store stock levels, supplier purchases, immutable stock-movement
> audit trail, order-linked deduction/restoration. NO GST computation, NO
> coupons, NO valuation, NO batch traceability. Money in integer paise;
> quantities in `Numeric(14, 3)`. Migration revision:
> `0016_create_inventory` (down: `0015_backfill_step3_11_domains`).

## 1. Architecture & tables

Five tables; every row carries `store_id` filled from single-store default
`DEFAULT_STORE_ID = 11111111-1111-4111-8111-111111111111`
(`backend/app/models/inventory.py:49`). There is NO `stores` table —
multi-store is future work (constant becomes a FK).

| Table | Purpose | Key constraints |
|---|---|---|
| `suppliers` | Purchase source (name, mobile, email, address, gstin, notes, is_active) | `ix_suppliers_store_id` |
| `purchases` | Purchase header (supplier FK `SET NULL`, `purchase_number`, date, subtotal/discount/other/total `_paise`, status, created_by) | `uq_purchases_store_id_purchase_number` |
| `purchase_items` | One variant line (purchase FK `CASCADE`, variant_id, qty, unit_cost_paise, line_total_paise) | `ix_purchase_items_{purchase_id,variant_id}` |
| `inventory_items` | Per-variant stock level; one row per (store, variant): qty_on_hand, qty_reserved, reorder_level, reorder_qty, is_active | `uq_inventory_items_store_id_variant_id`, `ck_inventory_items_qty_on_hand_nonneg` (`qty_on_hand >= 0`), `ck_inventory_items_qty_reserved_nonneg` |
| `stock_movements` | Immutable audit line (khata-style: never edited/deleted; corrections are offsetting rows) | `uq_stock_move_ref_type`, `ck_stock_movements_movement_type`, `ck_stock_movements_qty_positive` (`qty > 0`) |

Coupling: `variant_id` / `created_by` / `store_id` are plain `Uuid`
columns (no hard FKs to `product_variants`/`users`/stores — mirrors the
vision/soil pattern), validated service-side, indexed for lookups.

## 2. Source of truth decision

- `InventoryItem.qty_on_hand − qty_reserved = available` is actual
  availability for tracked variants.
- Catalogue `ProductVariant.stock_qty` is **legacy display only** — Step 16
  never reads or writes it (`inventory/service.py` docstring; commerce hook
  comment: "stays legacy display (never touched)").
- `available` and status (`out`: available ≤ 0; `low`: available ≤
  reorder_level; else `in`) are computed on every read, never stored.

## 3. Stock movements

10 types (`STOCK_MOVEMENT_TYPES`): `purchase`, `sale`, `adjustment_in`,
`adjustment_out`, `return_in`, `damaged_out`, `expired_out`,
`transfer_in`, `transfer_out`, `opening_stock`. Rules:

- `qty` always positive; direction comes from `movement_type`.
- `qty_before → qty_after` snapshots are server-computed per change, in
  the SAME transaction as the stock write.
- Per-line uniqueness `uq_stock_move_ref_type` on
  `(reference_type, reference_id, movement_type, inventory_item_id)` —
  multi-line documents (purchase with N variants, order with N lines)
  write one row per line; repeating the same line is rejected (idempotency
  backbone). Manual adjustments carry `reference_type/id = NULL`.
- Movement history is staff-only; farmers see only availability.

## 4. Purchase receiving

Flow: `draft → received` (single transaction). `cancelled` never stocks.

- Draft scaffolding: header first (`PO-XXXXXXXX`, 3-attempt retry on
  number collision), empty draft allowed; lines added/removed draft-only.
  Server math always wins: `line_total = round(qty × unit_cost)`,
  `subtotal = Σ lines`, `total = subtotal − discount + other_charges`
  (negative total rejected; client totals ignored).
- `receive_purchase`: recomputes totals, auto-creates missing
  `InventoryItem` rows (receive/opening/adjustment_in are the only
  auto-creators), `qty_on_hand += line.qty` per line + one `purchase`
  movement each (`reference_type="purchase_receipt"`,
  `reference_id=purchase.id`, `created_by=purchase.created_by`), then
  `status="received"`.
- Idempotent: already-`received` returns current purchase with
  `duplicate=True`; `cancelled → receive` is 422 `PURCHASE_CANCELLED`;
  concurrent double-receive collides on `uq_stock_move_ref_type` → 422
  `PURCHASE_RECEIVE_CONFLICT`.
- `cancel_purchase`: `draft → cancelled` only. `received → cancel` is 422
  `PURCHASE_ALREADY_RECEIVED`; already-`cancelled` returns
  `duplicate=True`.
- Draft mutation after terminal state: 422 `PURCHASE_NOT_DRAFT`.

## 5. Order deduction (confirm hook)

`commerce/service.py:transition_order` — `to_status == "confirmed"`
lazily calls `record_order_sale(db, order, commit=False)` in the SAME
transaction (no commit of its own); `"cancelled"` calls
`reverse_order_sale` likewise.

- One `sale` movement per order line (`reference_type="order_sale"`,
  `reference_id=order.id`); validates `available ≥ qty` per tracked line.
- **Skip-if-untracked** (deliberate deviation from strict governance):
  variants with no `InventoryItem` row are skipped, so pre-stock Step 14
  confirm flows behave exactly as before; only tracked variants gate the
  order.
- **Payment separation**: deduction fires on order **confirm**, NOT on
  payment success — commerce never touches payments/khata, and inventory
  never reads `payment_status` (Steps 13–15 boundary preserved).
- **SAVEPOINT + missing-table tolerance**: work runs in
  `db.begin_nested()`; `_is_missing_table` (sqlite "no such table" /
  postgres "undefined table" / "relation … does not exist") → silent
  no-op so Steps 1–15 legacy databases leave commerce untouched.
- Already-recorded sale → returns `True` (idempotent no-op).

## 6. Cancellation restoration

`reverse_order_sale`: for each prior `sale` movement, `qty_on_hand +=
sale.qty` + one `return_in` movement (`reference_type="order_sale"`,
`reason="Order cancelled."`).

- Written **once**: `first_return_movement` present → returns `True`
  (duplicate flag). Concurrent-restoration race lost → returns `True`
  (winner's rows stand).
- **Pending-cancel no-op**: no `sale` movements (e.g. `pending →
  cancelled`) → returns `False`, stock untouched.

## 7. Low stock

`available <= reorder_level` (includes out-of-stock). Sorted out-of-stock
first, then lowest `available / reorder_level`. Frontend badges:
🔴 out, 🟠 low, 🟢 in. `GET /summary` returns in/low/out counts + 10
recent movements.

## 8. Manual adjustments (staff-only)

Whitelist (`schemas.py`): in-types `adjustment_in, return_in,
opening_stock`; out-types `adjustment_out, damaged_out, expired_out`.

- `sale`/`purchase` rejected with 422 (system-owned: orders/purchases
  only); unknown types rejected.
- Reason required for `adjustment_in, adjustment_out, damaged_out,
  expired_out` (422 `INVENTORY_REASON_REQUIRED` when blank).
- In-types auto-create the item row; out-types 404/422 when missing or
  `available < qty` (`INVENTORY_INSUFFICIENT`). `qty` must be positive.

## 9. Suppliers (staff-only)

CRUD minus delete: list (search, paginated), create, get, update. `PUT`
doubles as the active-flag toggle — no hard-delete route.
`gstin` is **stored-only**: whitespace stripped, max 20 chars, NO GST
validation. Purchase creation/update 404s on unknown `supplier_id`.

## 10. Authorization (interim gate)

`inventory_access.py:require_store_staff` — interim `store_staff_mobiles`
allowlist (comma-separated, normalised to 10-digit) until real RBAC
lands. Non-staff → 403 `STORE_STAFF_REQUIRED`; **empty allowlist denies
everyone (fail closed)**. Reads need auth; farmers get safe availability
only (`list`/`detail` shape via non-raising `is_store_staff`); movement
history, adjustments, suppliers, and all purchase routes are staff-gated.

## 11. Concurrency

Last-writer-wins is prevented by three layers: service pre-check
(`available ≥ qty` → 422 before write), DB `CHECK (qty_on_hand >= 0)`
as the hard floor, and `IntegrityError → 422 INVENTORY_INSUFFICIENT`
with Marathi message `पुरेसा स्टॉक उपलब्ध नाही.` The overselling
second writer is rejected; it never silently drives stock negative.

## 12. Idempotency summary

| Operation | Repeat behaviour |
|---|---|
| `POST /store/purchases/{id}/receive` | `duplicate=True`, stock untouched |
| Order confirm (sale hook) | returns `True`, no second deduction |
| Order cancel (restore hook) | returns `True`, no second restoration |
| `POST /store/purchases/{id}/cancel` | `duplicate=True` |
| Pending → cancelled order | no-op (`False`), no movements |

## 13. Money & quantity conventions

Per Steps 13–15: all money is integer paise (`*_paise`: purchase
subtotal/discount/other/total, line totals, unit costs) — integer
arithmetic, no float rounding. Quantities (kgs/litres/units) are
`Numeric(14, 3)` (`Decimal`) because fractional. The inventory module
itself carries NO money fields (no valuation by design).

## 14. Future batch/lot extensibility

Movement architecture is ready: every movement already carries
`reference_type/reference_id`, `variant_id`, `inventory_item_id`,
before/after snapshots, and per-line uniqueness — a batch/lot layer can
attach `batch_id/expiry` columns plus a `batch_id` leg in the uniqueness
key without changing the flow. No batch columns exist yet (explicitly
out of scope).

## 15. API table

Base `/store`; purchases/suppliers/adjust/movements staff-only (403),
inventory reads auth-only.

| Method & path | Description |
|---|---|
| `GET /store/inventory?product_id=&category_id=&variant_id=&status=&limit=&offset=` | Availability list (farmer-safe) |
| `GET /store/inventory/summary` | in/low/out counts + 10 recent movements |
| `GET /store/inventory/low-stock?limit=&offset=` | `available ≤ reorder`, out-first |
| `GET /store/inventory/{variant_id}` | Detail: staff = internal levels, farmer = safe view |
| `GET /store/inventory/{variant_id}/movements?movement_type=&date_from=&date_to=` | Audit history (staff) |
| `POST /store/inventory/{variant_id}/adjust` | Manual adjustment (staff; whitelist + reason rules) |
| `POST /store/purchases` → 201 | Create draft header |
| `GET /store/purchases?status=` | List (draft/received/cancelled filter) |
| `GET /store/purchases/{id}` | Header + items |
| `PUT /store/purchases/{id}` | Edit draft only |
| `GET /store/purchases/{id}/items` | List lines |
| `POST /store/purchases/{id}/items` → 201 | Add draft line (server totals) |
| `DELETE /store/purchases/{id}/items/{item_id}` | Remove draft line |
| `POST /store/purchases/{id}/receive` | draft → received + stock (idempotent) |
| `POST /store/purchases/{id}/cancel` | draft → cancelled (idempotent) |
| `GET /store/suppliers?search=` | List suppliers (staff) |
| `POST /store/suppliers` → 201 | Create supplier (staff) |
| `GET /store/suppliers/{id}` | Get supplier (staff) |
| `PUT /store/suppliers/{id}` | Update / active-toggle (staff) |

## 16. Frontend routes (`apps/web/app/store/`)

| Route | Purpose |
|---|---|
| `/store/inventory` | Summary cards + list with search/status filters |
| `/store/inventory/low-stock` | Low-stock view (🔴🟠🟢 badges) |
| `/store/inventory/[variant_id]` | Detail + movements + adjust form |
| `/store/purchases` | Purchase list (status filter) |
| `/store/purchases/new` | Draft creation form |
| `/store/purchases/[id]` | Draft edit, items, receive/cancel actions |
| `/store/suppliers` | Supplier list + create |
| `/store/suppliers/[id]` | Supplier detail/edit |
