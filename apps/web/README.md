# krushi-seva-web (Step 14)

Next.js 14 + TypeScript frontend: foundation + OTP auth + My Farm + Crop
+ Activity + Weather + Market + Krushi Mitra chat + Crop Problem Check
+ Soil Tests + Fertilizer Records + Pest & Disease Tracking + Krushi Store
+ Cart/Orders/Delivery (Marathi-first UI, mobile-first, no UI libraries).

## Run

```powershell
npm install
npm run dev   # http://localhost:3000
```

Env: copy `.env.example` → `.env.local` and set `NEXT_PUBLIC_API_URL`
(public backend URL only — no secrets in frontend env, ever).

## Routes

- `/` — status dashboard (public) with login entry point
- `/login` — mobile number → send OTP (guest-only, redirects to `/home` if authed)
- `/verify-otp` — OTP entry, shows DEV-OTP banner in dev mode (guest-only)
- `/profile-setup` — farmer profile form (auth-only)
- `/home` — greeting, profile, My Farms entry, logout (auth-only)
- `/farms` — My Farms cards (name, area, village, soil, irrigation) (auth-only)
- `/farms/new` — Add Farm form (auth-only)
- `/farms/[id]` — Farm Details: Basic / Location / Soil / Irrigation (auth-only)
- `/farms/[id]/edit` — Edit Farm (auth-only)
- `/farms/[id]/soil` — Soil Information view (auth-only)
- `/farms/[id]/soil/edit` — Add/edit soil record (auth-only, creates if absent)
- `/farms/[id]/crops` — Farm Crops list (auth-only)
- `/farms/[id]/crops/new` — Add Crop with Crop → Variety picker (auth-only)
- `/farms/[id]/crops/[cropId]` — Crop Details incl. farm context (auth-only)
- `/farms/[id]/crops/[cropId]/edit` — Edit Crop (auth-only)
- `/farms/[id]/crops/[cropId]/activities` — Crop Calendar: month grid with
  dots, status/type filters, timeline list view (auth-only)
- `/farms/[id]/crops/[cropId]/activities/new` — Add Activity (auth-only)
- `/farms/[id]/crops/[cropId]/activities/[activityId]` — Activity Details
  with Mark completed / Edit / Delete (auth-only)
- `/farms/[id]/crops/[cropId]/activities/[activityId]/edit` — Edit (auth-only)
- `/market` — commodity search + list, market list (auth-only, facts only)
- `/market/[commodityId]` — latest/compare table, history table, min/max/modal (auth-only)
- `/ai` — Krushi Mitra chat: conversations, farm/crop context, sources, voice placeholder (auth-only)
- `/crop-check` — farm/crop selectors, photo capture/upload + preview, analyze, history (auth-only)
- `/crop-check/[id]` — uncertain result, quality, sources, next steps, disclaimer, Ask-Mitra link (auth-only)
- `/farms/[id]/soil-tests` — soil history, newest first (auth-only)
- `/farms/[id]/soil-tests/new` — add soil test, date required, rest optional (auth-only)
- `/farms/[id]/soil-tests/[testId]` — details + report view/upload (auth-only)
- `/farms/[id]/soil-tests/[testId]/edit` — edit (auth-only)
- `/farms/[id]/crops/[cropId]/fertilizers` — fertilizer history (auth-only)
- `/farms/[id]/crops/[cropId]/fertilizers/new` — record use (auth-only)
- `/farms/[id]/crops/[cropId]/fertilizers/[fertId]` — details (auth-only)
- `/farms/[id]/crops/[cropId]/fertilizers/[fertId]/edit` — edit (auth-only)
- `/farms/[id]/crops/[cropId]/health` — health timeline (auth-only, tracking only)
- `/farms/[id]/crops/[cropId]/health/new` — record observation (auth-only)
- `/farms/[id]/crops/[cropId]/health/[obsId]` — details + photos + linked analysis + actions (auth-only)
- `/farms/[id]/crops/[cropId]/health/[obsId]/edit` — edit (auth-only)
- `/store` — search + category chips + product cards (auth-only, facts only)
- `/store/[id]` — images, facts, packs, verification status, add-to-cart (auth-only)
- `/store/cart` — lines with +/-, validation issues, subtotal, checkout (auth-only)
- `/store/checkout` — address select, server-computed summary, confirm (auth-only, no payment UI)
- `/store/orders` — order number, date, total, status (auth-only)
- `/store/orders/[id]` — items, address, totals, timeline, cancel rule (auth-only)
- `/store/addresses` — list/add/edit/delete/default (auth-only)
- Home `/home` — today's weather card + 7-day forecast (first GPS farm)
- Farm `/farms/[id]` — 🌦️ weather section (own farm's GPS or guidance)

## Auth plumbing

- `lib/api.ts` — typed backend client (`ApiError` with code/message)
- `lib/auth.tsx` — `AuthProvider`: session restore on refresh, login/logout,
  language state (tokens in localStorage — see hardening note below)
- `components/AuthGate.tsx` — `mode="auth"|"guest"` route guard
- `components/FarmForm.tsx`, `components/SoilForm.tsx` — shared create/edit
  forms (all labels via `t.*`, no hardcoded text)
- `lib/i18n.ts` — `en` complete + fallback; `mr` complete (DEFAULT language
  for farmer UI); `hi` covers farmer keys (screens use `t.key`)

> Security note: tokens persist in `localStorage` for Step 3 development.
> Harden to httpOnly cookies + CSRF before production (see `docs/authentication.md`).

## Health

- Page `/` shows live backend status (fetched from `NEXT_PUBLIC_API_URL/health`).
- `GET /api/health` — frontend liveness probe (dependency-free).
