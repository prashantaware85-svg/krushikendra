# Krushi Seva — Authentication (Step 3)

> Scope: passwordless mobile-OTP auth + farmer profile foundation only.
> No farm/crop, marketplace, AI, or other domains yet.

## 1. Architecture

Mobile number is the primary login identifier (Indian farmers often have no
email). Flow:

```
New farmer:      mobile → send-otp → verify-otp → [user + profile created] → tokens → profile-setup → home
Existing farmer: mobile → send-otp → verify-otp → tokens → home
```

Components (`backend/app/modules/auth/`):

| File | Role |
|---|---|
| `security.py` | Pure crypto: mobile normalisation, OTP gen/HMAC, refresh gen/hash, JWT create/decode. No DB. |
| `repository.py` | CRUD only (users, profiles, OTP + refresh rows). No policy. |
| `service.py` | Policy: expiry, attempts, cooldown, hourly cap, rotation, login. |
| `schemas.py` | Pydantic request/response contracts (no hashes/secrets leak). |
| `dependencies.py` | `get_current_user` (Bearer access token → active `User`, else 401). |
| `router.py` | Thin endpoints under `/api/v1/auth`. |

Farmer profiles live in `backend/app/modules/farmers/` (`GET/PUT /api/v1/farmer/profile`).

## 2. OTP flow

1. `POST /api/v1/auth/send-otp {mobile_number}` — normalises (`+91…`/`0…` → 10
   digits, must match `[6-9]xxxxxxxxx`), enforces resend cooldown + hourly cap,
   stores **HMAC-SHA256 hash only**, returns `{mobile_number, resend_after_seconds}`
   (+ `dev_otp`, see §3).
2. `POST /api/v1/auth/verify-otp {mobile_number, otp}` — constant-time compare;
   on success burns the OTP (`consumed_at`), creates the user (verified) +
   default profile for new farmers, returns access + refresh tokens and
   `is_new_user` so the frontend routes to profile-setup vs home.
3. Wrong codes increment `attempts`; exhaustion or expiry kills the record —
   the farmer requests a fresh OTP (no unlock endpoint by design).

## 3. Development OTP behavior (DEV-ONLY)

- No SMS provider is integrated in Step 3. `service.request_otp()` has a marked
  hook where the SMS call will plug in later.
- When `AUTH_DEV_OTP_ENABLED=true` **and** `ENVIRONMENT != production`,
  `send-otp` returns the OTP as `dev_otp`; the frontend shows it in a
  "DEV ONLY" banner. The value is never hard-coded anywhere.
- Production is fail-fast: app startup raises if `ENVIRONMENT=production` with
  the default JWT secret or `AUTH_DEV_OTP_ENABLED=true`; `dev_otp` is `None`
  regardless (covered by `test_dev_otp_never_exposed_in_production`).
- OTPs are logged at most at debug level in dev mode, never in production
  (production logs only the last 4 digits on issuance).

## 4. Security considerations

- **No plaintext secrets at rest:** OTPs = HMAC-SHA256, refresh tokens =
  SHA-256 hex. DB dumps yield nothing replayable (refresh needs the raw
  288-bit token; OTP needs the code + server secret).
- **Tokens:** access = JWT HS256, 30 min (`sub`=user id, `type`=access);
  refresh = opaque, 30 days, **rotated on every use**, revocable (logout).
  Refresh failures are deliberately generic (no valid/revoked/expired oracle).
- **Rate limits (service-level, DB-backed, survive restarts):**
  `OTP_RESEND_COOLDOWN_SECONDS` (60), `OTP_MAX_SENDS_PER_HOUR` (5),
  `OTP_MAX_ATTEMPTS` (5). Violations → 429 with `OTP_*` codes.
- **Responses:** consistent `{error: {code, message}}` envelope; 401 for all
  auth failures; no hashes, DSNs, or stack traces (verified by tests).
- **Uniqueness:** `users.mobile_number` unique (login key);
  `farmer_profiles.user_id` unique (one-to-one); `refresh_tokens.token_hash`
  unique. Mobile is stored normalised so `+91…`/`0…` variants can't duplicate.
- **Known Step 3 limitation:** frontend persists tokens in `localStorage`
  (fine for dev). Harden to httpOnly cookies + CSRF before production —
  tracked as a future step, not implemented here.

## 5. Token lifecycle

```
verify-otp → access (30m) + refresh (30d)
request with `Authorization: Bearer <access>` → get_current_user
access expired → POST /refresh {refresh_token} → NEW pair (old revoked)
logout → POST /logout {refresh_token} → revoked (idempotent)
compromise response → logout (revoke) → all derived access tokens die by expiry
```

## 6. API endpoints

| Method & path | Auth | Success | Errors |
|---|---|---|---|
| `POST /api/v1/auth/send-otp` | – | 200 `{mobile_number, resend_after_seconds, dev_otp?}` | 422 bad mobile · 429 cooldown/cap |
| `POST /api/v1/auth/verify-otp` | – | 200 tokens + `is_new_user` | 400 invalid/expired/none · 429 attempts exhausted |
| `POST /api/v1/auth/refresh` | – | 200 new pair (rotation) | 401 invalid/expired/revoked |
| `POST /api/v1/auth/logout` | – | 200 (idempotent) | – |
| `GET /api/v1/auth/me` | Bearer | 200 `{id, mobile_number, is_verified, profile}` | 401 |
| `GET /api/v1/farmer/profile` | Bearer | 200 profile | 401 |
| `PUT /api/v1/farmer/profile` | Bearer | 200 updated profile | 401 · 422 bad language/empty name |

Full interactive docs: `http://localhost:8000/docs`.

## 7. Frontend session handling

- `lib/api.ts` — typed client, throws `ApiError(code, message, status)`.
  Only `NEXT_PUBLIC_API_URL` is used (public by design — no secrets in frontend env).
- `lib/auth.tsx` — `AuthProvider`: `status` (`loading`/`guest`/`authed`),
  restore-on-refresh (`/me`, one `refresh` retry, else guest), login/logout,
  language state.
- `components/AuthGate.tsx` — `<AuthGate mode="auth"|"guest">` redirects
  guests → `/login`, authed users → `/home`.
- `lib/i18n.ts` — `en` complete + fallback; `hi`/`mr` empty partials.
  Translating = filling two dicts; screens use `t.key` and need no rewrites.
  `preferred_language` syncs from the backend profile.

## 8. Future SMS provider integration

1. Implement `send_otp_via_sms(mobile, otp)` (e.g. MSG91/Twilio/Amazon SNS)
   behind an interface in the auth service; call it from `request_otp`
   where the DEV-ONLY hook is marked.
2. Add `SMS_PROVIDER` + provider credentials to env (never commit).
3. Keep `dev_otp` for non-prod environments; gate by `ENVIRONMENT`.
4. Add delivery-status tracking column on `otp_verifications` if receipts
   are needed. No endpoint changes required.
