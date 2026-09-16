# Krushi Seva — Local Development (Step 1)

> Prerequisites: **Node.js 18+**, **Python 3.11+**, npm, pip/venv.
> No database, Docker, or Redis needed for Step 1.

## 1. Clone & env setup

```powershell
# Windows PowerShell
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
Copy-Item backend\.env.example backend\.env
```

```bash
# macOS / Linux
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
cp backend/.env.example backend/.env
```

Edit values if your ports differ. Defaults:
- Backend → `http://localhost:8000`
- Frontend → `http://localhost:3000`

## 2. Run the backend (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify:

- Health (root): http://localhost:8000/health → `{"status":"ok",...}`
- Health (v1): http://localhost:8000/api/v1/health
- OpenAPI docs: http://localhost:8000/docs

Run tests:

```powershell
cd backend
pytest -q
```

## 3. Run the frontend (Next.js)

```powershell
cd apps\web
npm install
npm run dev
```

Open http://localhost:3000 — landing page shows backend health status
(fetched from `NEXT_PUBLIC_API_URL`). Health API: http://localhost:3000/api/health

Useful scripts (inside `apps/web`):

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server (port 3000) |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | Next.js lint |
| `npm run typecheck` | `tsc --noEmit` |

## 4. Run both together (optional helper)

```powershell
# From repo root — starts backend + frontend in two windows
.\scripts\dev.ps1
```

```bash
# macOS / Linux
./scripts/dev.sh
```

## 5. Optional infra (Step 2+, NOT required now)

```bash
docker compose --profile infra up db redis -d
```

This starts PostgreSQL 16 (`localhost:5432`) and Redis 7 (`localhost:6379`).
Backend does NOT connect to them in Step 1 — reserved for Step 2.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `uvicorn: command not found` | Virtualenv not activated, or `pip install -r requirements.txt` not run |
| Frontend shows "Backend unreachable" | Backend not running, or `NEXT_PUBLIC_API_URL` wrong — check `apps/web/.env.local` then restart `npm run dev` |
| Port 3000/8000 in use | Change `PORT` (frontend) or `BACKEND_PORT` (backend `.env`) |
| `tsc` errors | Run `npm install` again inside `apps/web` to ensure Next.js types are present |
