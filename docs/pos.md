# Krushi Seva — POS Counter Billing (Step 18)

> Scope: in-store counter sales for staff — product lookup, draft bills,
> atomic completion (stock + payment + Khata), manager-only cancellation,
> JSON receipts, day summary. Single store (`DEFAULT_STORE_ID`); no `stores`
> table. Backend untouched by this step's frontend work — this doc describes
> verified backend behaviour (read from `backend/app/modules/pos/*`,
> `backend/app/models/pos.py`) plus the Step 18 frontend.

## 1. Architecture

- `pos_bills`: UUID PK; `store_id` (default store, no FK); human `bill_number`
  (unique per store); nullable `customer_id` (plain UUID = `users.id`,
  walk-in = NULL); money as integer paise (`subtotal/discount/other_charges/
  total_paise`); `sale_status` (draft/completed/cancelled); `payment_status`
  (pending/paid/partial/credit); nullable `payment_mode`; `amount_received/
  amount_paid/balance_due_paise`; `payment_reference`; `notes`; `sold_by`
  (staff user id), `cancelled_by`, `cancel_reason`; timestamps.
- `pos_bill_items`: UUID PK; bill FK CASCADE; `variant_id` plain UUID (no hard
  FK to `product_variants` — mirrors inventory/vision loose coupling);
  `product_name_snapshot` / `variant_name_snapshot` (immutable history, reads
  never re-join the catalogue); `qty` Numeric(14,3) CHECK > 0;
  `unit_price_paise`; `discount_paise` (per-line, currently always 0 —
  discounts live at bill level); `line_total_paise`.
- `pos_bill_counters`: integer PK with autoincrement; each new row's `id`
  feeds the bill number (see §9).
- No `store_id` on users (single store): customer validation checks user
  existence + active only. Catalogue has no SKU/barcode fields (Step 13), so
  product search covers product name + variant name (ILIKE) only.

## 2. Draft + complete flow

1. `POST /store/pos/bills {items[] {variant_id, qty}, customer_id?,
   discount_paise?, other_charges_paise?, payment_mode?, notes?}` → `201`
   with a **draft** bill (`sale_status="draft"`, `payment_status="pending"`).
   - Server re-reads live variant rows, recomputes every line total
     (`qty × unit_price`, ROUND_HALF_UP), snapshots names/prices; client
     totals are never trusted.
   - `discount ≤ subtotal` else `422 POS_DISCOUNT_INVALID`; negative
     discount/other `422 POS_BILL_INVALID`; bad mode `422
     POS_PAYMENT_MODE_INVALID`; staff discount cap (§3).
   - `payment_mode` in the create payload is accepted but **not stored**
     (`payment_mode=None` on the draft) — the mode is chosen at completion.
   - Draft holds intent only: **no stock deduction, no Khata entry**.
   - Bill items are immutable after create — there are no draft-edit
     endpoints; the frontend cart stays client-side until POST.
2. `POST /store/pos/bills/{id}/complete {payment_mode,
   amount_received_paise?, payment_reference?, amount_paid_paise?}` →
   `{bill, duplicate}`.
   - Idempotent: already-completed → `{duplicate: True}` no-op; cancelled
     bills cannot complete (`422 POS_BILL_CANCELLED`).
   - Full payment: `paid=total, balance=0, status="paid"`. Cash requires
     `amount_received_paise ≥ total` else `422 POS_PAYMENT_INSUFFICIENT`.
   - Partial (`amount_paid_paise` set and ≠ total): must be `> 0` and `<
     total` else `422 POS_PARTIAL_INVALID`; **requires a customer** (`422
     POS_CUSTOMER_REQUIRED`); `status="partial"`; cash-partial additionally
     requires `received ≥ paid`.
   - Credit (`mode="credit"`): **requires a customer**; `paid=0,
     balance=total, status="credit"`; received is always NULL.
   - Stock + Khata + bill update commit atomically; any failure rolls back.
     Concurrent stock races surface as `422 INVENTORY_INSUFFICIENT`.

## 3. Pricing / discount (staff cap)

- Unit prices come from live variant rows (`price_paise`); price-on-request
  variants (`price_paise NULL`) are flagged and cannot be billed (no unit
  price ⇒ no valid line total).
- Bill-level `discount_paise` (default 0): plain `store_staff` cashiers may
  grant at most `settings.pos_staff_max_discount_paise` (**₹200**) per bill
  (`403 BILL_DISCOUNT_FORBIDDEN` above the cap); `store_manager`/`admin` are
  unlimited. The discount may never exceed the subtotal (`422`), even for
  managers.
- Totals: `total = subtotal − discount + other_charges`, integer paise —
  no rounding, no floats.
- Frontend shows the ₹200 staff cap as helper text next to the discount
  input; the backend stays authoritative (422 surfaces verbatim).

## 4. Inventory (pos_sale ref, idempotency, concurrency)

- Draft bills have **zero** stock effect. Completion decrements each line's
  `qty_on_hand` and appends one `StockMovement` per line:
  `movement_type="sale"`, `reference_type="pos_sale"`,
  `reference_id=bill.id`, with `qty_before/after` and `created_by`.
- Untracked variants (no inventory row) skip stock governance — mirrors the
  order-sale path. Insufficient `qty_on_hand − qty_reserved` aborts the
  whole completion (`422 INVENTORY_INSUFFICIENT`, nothing commits).
- Idempotency: complete is idempotent via `duplicate=True`; cancel is
  idempotent the same way. No client idempotency keys in this step.
- Concurrency: bill numbers come from a counter table with bounded retry on
  unique violation (safe under concurrent creates); a lost
  cancel-restoration race still marks the bill cancelled and reports
  `duplicate=True` (winner's `return_in` rows stand).

## 5. Payment modes

Accepted modes: `cash | upi | card | credit` (no payment gateway in this
step — cash/UPI/card are recorded, not processed). Outcome statuses:
`pending (draft) | paid | partial | credit`.

| Mode | Required fields | Result |
|---|---|---|
| cash | `amount_received_paise ≥ due` | paid; change = received − paid (receipt only) |
| upi / card | optional `payment_reference` | paid |
| credit | `customer_id` on bill | paid=0, balance=total, status=credit |
| partial (any mode, `amount_paid_paise`) | customer; `0 < paid < total`; cash needs received ≥ paid | status=partial, Khata debit for balance |

## 6. Credit / Khata linkage + reversal

- On completion with `balance > 0` (credit or partial — both guarantee a
  customer), the backend appends `khata.record_debit(farmer=customer,
  amount=balance, order_id=None, note="POS {bill_number}")` in the same
  transaction. Walk-in (NULL customer) bills can never carry a balance.
- On cancel of a **completed** bill with `balance_due > 0` and a customer,
  the backend appends the offsetting `record_credit(...,
  note="POS {bill_number} cancelled")`. Fully-paid cash/UPI/card cancels get
  **no** automatic refund — the receipt carries `refund_note =
  "परतावा प्रक्रिया स्वतंत्रपणे करावी लागेल."` (refund must be handled
  separately).
- Khata entries are never edited — only appended (immutable ledger).

## 7. Cancellation

`POST /store/pos/bills/{id}/cancel {reason?}` → `{bill, duplicate}`
(manager+ only, §8). Draft → cancelled (no stock effect). Completed →
cancelled **plus** one `return_in` movement per original `pos_sale`
(reference_type `pos_sale`, reference_id = bill id, reason "POS bill
cancelled.") **plus** the Khata credit reversal (§6) when a balance exists.
Return rows are written once (guarded by
`first_pos_return_movement`); repeat cancels return `duplicate=True` and
never hard-delete anything. Frontend confirms via `window.confirm` with an
optional reason field.

## 8. RBAC matrix

| Action | farmer / guest | store_staff | store_manager | admin |
|---|---|---|---|---|
| products list/get, bills create/list/get/complete, receipt, summary | 401/403 | ✅ | ✅ | ✅ |
| bills **cancel** | 401/403 | ❌ 403 `STORE_MANAGER_REQUIRED` | ✅ | ✅ |

Frontend rule: no role is guessed client-side — the backend 401/403 is the
signal. 401/403 on reads renders `प्रवेश नाही` access notices; the Cancel
button is shown to all staff with a "manager+ only (staff 403)" note, and a
403 from the cancel POST flips the note to read-only.

## 9. Bill numbering

`KSK-{year}-{seq:06d}` (e.g. `KSK-2026-000041`), mirroring `OrderCounter`:
one `pos_bill_counters` row per bill, per-year sequence with a
store+bill_number unique constraint and bounded retry — concurrency-safe.

## 10. No-GST / tax note

There is **no GST engine** in this step: no tax fields on any schema, no tax
rows on the receipt, and the day summary explicitly excludes profit/GST.
Bill math is exactly `total = subtotal − discount + other_charges`. The
frontend therefore **omits the Tax/GST row entirely** (bill detail, receipt,
counter) and notes "कर (Tax/GST): लागू नाही" next to totals; this section
is the normative record.

## 11. APIs (frontend-used)

Base: `GET /api/v1/store/pos/...` (trailing shape verified against
`backend/app/modules/pos/router.py` + `schemas.py`).

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/products?search` | Returns a **bare array** `PosProductOut[]` (NOT `{items,total}`); `limit/offset` are accepted by the frontend signature but currently ignored server-side — the client forwards them harmlessly and normalises array-or-envelope. |
| GET | `/products/{variant_id}` | Single `PosProductOut`. |
| POST | `/bills` | → `201 PosBillOut` (draft). |
| GET | `/bills?bill_number&customer_id&payment_mode&payment_status&sale_status&date_from&date_to&limit&offset` | → `{bills, total, limit, offset}`. |
| GET | `/bills/{id}` | → `PosBillOut`. |
| POST | `/bills/{id}/complete` | → `{bill, duplicate}` (**no** `change_paise` — change is receipt-side / client-derived). |
| POST | `/bills/{id}/cancel` | → `{bill, duplicate}`; manager+. |
| GET | `/bills/{id}/receipt` | → `{store:{name}, bill_number, created_at, cashier, customer, items[], subtotal_paise, discount_paise, other_charges_paise, total_paise, sale_status, payment_status, payment{mode,paid_paise,received_paise?,change_paise?(cash),balance_due_paise,reference?,refund_note?}, footer}`. Cashier/customer are display names only (no UUIDs/mobiles). |
| GET | `/summary?day=` | → `{date, bills, total_paise, breakdown:{mode:{bills,total_paise}}}` over **completed** bills only. |

Field-name note: bill items use `product_name_snapshot` /
`variant_name_snapshot` (+ `id`, per-line `discount_paise`, Decimal `qty`
as string) — the frontend types match the backend exactly and renders via
`posItemProductName()/posItemVariantName()` helpers.

## 12. Frontend routes (Step 18)

- `app/store/pos/page.tsx` — counter: product search + stock badges (backend
  emoji shown as-is) + draft panel (add/inc/dec/remove/clear, estimated
  line totals marked अंदाज) + walk-in default with optional manual
  customer-ID input + payment modal (total/mode/received/change preview/
  reference/optional partial + credit-customer guard) + Create/Complete +
  today summary cards (bills/sales/cash/UPI/card/credit) + 403 notice.
- `app/store/pos/bills/page.tsx` — history with all 7 filters + limit/offset
  pagination (20/page, total + prev/next).
- `app/store/pos/bills/[id]/page.tsx` — detail (items, totals without tax
  row, paid/received/balance/reference/notes) + receipt link + Cancel with
  confirm + manager-only 403 note.
- `app/store/pos/bills/[id]/receipt/page.tsx` — print-friendly receipt +
  `window.print()` button + `@media print` CSS (chrome hidden on paper).
- `apps/web/lib/api.ts` — `PosProduct/PosBill*/PosReceipt/PosSummary`
  types + 9 methods (`listPosProducts/getPosProduct/createPosBill/
  listPosBills/getPosBill/completePosBill/cancelPosBill/posReceipt/
  posSummary`), additive, no `any`. Shared `formatPaise` from `lib/khata.ts`;
  `AuthGate mode="auth"` + existing CSS classes throughout.

## 13. Known limitation — customer selection

No customer-search endpoint exists in the backend (verified: the customer
screens derive ledger groups client-side from Khata entries, which carry no
user UUIDs). The counter therefore defaults to walk-in and offers a manual
customer-ID (`users.id` UUID) text input with helper text; staff paste the
UUID from the customers/Khata screen. Credit and partial payments are
blocked client-side without a customer (backend would 422).

## 14. Future extensions (not in this step)

Customer search/select endpoint + picker; barcode/SKU lookup (catalogue has
no SKU fields today); draft-edit endpoints (currently immutable — edit means
cancel + re-create); returns/exchange flow beyond cancel-restore; holds/
parked bills; shift/open-close cash reconciliation; printed 58mm thermal
layout; GST engine (would add tax fields to schemas, receipt, summary and
bring back the Tax row); UPI deeplink/QR + gateway settlement; discounts
per-line use; multi-store support.
