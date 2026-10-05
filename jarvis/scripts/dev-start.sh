#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# check python deps
if [ ! -f "apps/web/dist/index.html" ]; then
  echo "→ Building web..."
  (cd apps/web && npm install && npm run build)
else
  echo "→ Web dist exists — skipping build (remove apps/web/dist to rebuild)"
fi

echo "→ Installing python deps..."
pip install -q -r requirements.txt || pip install -r requirements.txt

echo "→ Starting JARVIS gateway on :8000"
# ensure data dir
mkdir -p data/workspace

# run with reload if requested
if [ "$1" = "--reload" ]; then
  PYTHONPATH="$ROOT" python -m apps.gateway.main --port 8000 --reload
else
  PYTHONPATH="$ROOT" python -m apps.gateway.main --port 8000
fi
