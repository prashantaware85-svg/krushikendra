#!/usr/bin/env bash
# Start Krushi Seva backend + frontend for local development (Step 1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

(cd "$ROOT/backend" && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
(cd "$ROOT/apps/web" && npm run dev) &

wait
