#!/usr/bin/env bash
# Start everything for a phone demo: backend (local 8000 + public phone port 8001) and the frontend (5173).
# Expose only 8001 to the internet yourself:  sudo tailscale funnel --bg 8001
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENVF="$ROOT/.phone.env"
if [ ! -f "$ENVF" ]; then
  umask 077
  echo "PHONE_TOOLS_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" > "$ENVF"
  echo "Created $ENVF — paste its token into Sarvam dashboard → Secrets (do not share it elsewhere)."
fi
set -a; . "$ENVF"; set +a
mkdir -p "$ROOT/logs" "$ROOT/.demo"
export BACKEND_DB_PATH="${BACKEND_DB_PATH:-$ROOT/.demo/demo.db}"   # demo DB outside backend/; delete .demo/ to reset
cd "$ROOT/backend"
.venv/bin/uvicorn app:app --port 8000 > "$ROOT/logs/backend-8000.out" 2>&1 &
.venv/bin/uvicorn public_app:app --port 8001 > "$ROOT/logs/backend-8001.out" 2>&1 &
cd "$ROOT/frontend" && npm run dev -- --port 5173 > "$ROOT/logs/frontend.out" 2>&1 &
sleep 3
curl -fsS localhost:8000/health >/dev/null && echo "backend  :8000 up (local only)"
curl -fsS localhost:8001/health >/dev/null && echo "phone    :8001 up (expose with: sudo tailscale funnel --bg 8001)"
echo "frontend http://localhost:5173   — stop all with: kill $(jobs -p | tr '\n' ' ')"
wait
