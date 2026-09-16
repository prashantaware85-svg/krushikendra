# Krushi Seva — Store RBAC (Step 17)

> Frontend: `apps/web/app/store/staff/*` + reorder UI in
> `apps/web/app/store/inventory/[variant_id]/page.tsx`.
> Backend contract (authoritative): DB-backed staff roles.
> This doc describes the contract the frontend codes against.

## 1. Roles

| Role value | Marathi badge | Scope |
|---|---|---|
| `admin` | प्रशासक | Full store back-office: staff CRUD, reorder, all Step 16 writes |
| `store_manager` | दुकान व्यवस्थापक | Operational writes incl. reorder; NO staff management |
| `store_staff` | दुकान कर्मचारी | Day-to-day writes (Step 16 scope); NO staff management, NO reorder |

Role values are exact strings: `admin | store_manager | store_staff`.

## 2. Permission matrix (route → role)

Base `/api/v1`; all store routes need auth (401 without token).

| Method & path | admin | store_manager | store_staff | Notes |
|---|---|---|---|---|
| `GET /store/staff` | ✅ | 403 | 403 | List; `{staff: [...]}` (client also accepts bare `[...]`) |
| `POST /store/staff` → 201 | ✅ | 403 | 403 | Body `{mobile_number?, user_id?, role}`; at least one identity |
| `GET /store/staff/{id}` | ✅ | 403 | 403 | Detail |
| `PUT /store/staff/{id}` | ✅ | 403 | 403 | Body `{role?, is_active?}` only |
| `POST /store/staff/{id}/deactivate` | ✅ | 403 | 403 | Soft off |
| `POST /store/staff/{id}/activate` | ✅ | 403 | 403 | Soft on |
| `DELETE /store/staff/{id}` | ✅ | 403 | 403 | Soft delete → `{active: false}`, never hard |
| `PUT /store/inventory/{variant_id}/reorder-level` | ✅ | ✅ | 403 | Body `{reorder_level >= 0, reorder_quantity? > 0}` |
| Step 16 writes (suppliers, purchases, inventory adjust, movements) | ✅ | ✅ | ✅ | Pre-existing staff scope (see `docs/inventory.md`) |
| Store reads (inventory list/detail, suppliers/purchases reads per backend) | ✅ | ✅ | ✅ | Auth-only; reorder level/quantity visible to all |

Frontend route map: `/store/staff` (list), `/store/staff/new` (create),
`/store/staff/[id]` (detail + audit note), `/store/staff/[id]/edit`
(role/active form); reorder editor lives on `/store/inventory/[variant_id]`.

## 3. Allowlist retirement status

- Legacy (Step 16): `STORE_STAFF_MOBILES` / `settings.store_staff_mobiles`
  allowlist in `backend/app/modules/inventory_access.py`
  (`require_store_staff` → 403 `STORE_STAFF_REQUIRED`; empty allowlist denies
  everyone, fail closed).
- Step 17: DB-backed staff table is **authoritative** for the routes above.
  The mobile allowlist is legacy and must not gate staff/reorder routes;
  keep it only until Step 16 call sites migrate, then remove
  `inventory_access.py` + the setting.

## 4. Bootstrap (dev-only)

- The first `admin` is created by a **dev-only backend bootstrap script**
  (local/dev databases only — never production).
- Frontend has no bootstrap UI and sends no seed requests; if no admin
  exists, staff routes 403/404 until bootstrap runs.
- Production admin provisioning is an operator action outside the app.

## 5. Last-admin guard

Backend refuses to remove the last active admin: demoting, deactivating,
or (soft-)deleting the final `admin` (active) fails with 422/409 and a
Marathi message. The frontend surfaces the server message as-is and keeps
local state unchanged (no optimistic removal).

## 6. Audit log

Staff mutations (create, role change, activate/deactivate, soft delete)
append immutable audit rows (actor, action, target, timestamp) server-side.
Movement/stock audit semantics are unchanged (see `docs/inventory.md` §3).
The staff detail page shows an audit-note card; the frontend never fabricates
audit entries.

## 7. Store isolation (single store)

Single-store deployment: every row carries `store_id` filled from the
constant `DEFAULT_STORE_ID = 11111111-1111-4111-8111-111111111111`
(`backend/app/models/inventory.py`, `docs/inventory.md` §1). There is no
`stores` table; cross-store access collapses to 404 (see below).

## 8. 401 / 403 / 404 semantics

| Code | Meaning | Frontend handling |
|---|---|---|
| 401 | Missing/invalid token | `AuthGate mode="auth"` redirects to `/login` |
| 403 | Authenticated but role lacks permission (e.g. staff/manager on staff routes; staff on reorder PUT) | Hide management actions; show `प्रवेश नाही (Access restricted)` (list/detail) or `फक्त व्यवस्थापक` read-only note (reorder form). Never guess role client-side |
| 404 | Missing record OR cross-store record (intentionally indistinguishable) | Show server message; creation with unknown `user_id` 404 clears on next input |

No self-role endpoint exists, so the frontend never gates by a local role
guess: staff pages rely on the list/detail 403, and the reorder form is
always rendered — a 403 from PUT flips it to the read-only notice.

## 9. Future-role extensibility

- Roles are data, not code branches: the frontend renders badges via a
  label map (`admin → प्रशासक`, `store_manager → दुकान व्यवस्थापक`,
  `store_staff → दुकान कर्मचारी`) with unknown values passed through.
- New roles default-deny: backend grants them nothing until the matrix is
  extended; frontend role filters compare exact strings, so new roles appear
  unfiltered rather than misclassified.
- Prefer adding roles over widening `store_staff`; keep `admin` as the only
  staff-management role and keep deletes soft.
