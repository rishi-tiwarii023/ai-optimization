#!/bin/sh
set -eu

PORT="${PORT:-8000}"

python -c "import fastapi, uvicorn, pytest"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  exit 0
fi

curl -fsS "http://127.0.0.1:${PORT}/openapi.json" >/dev/null
