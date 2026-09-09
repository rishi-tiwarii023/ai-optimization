#!/bin/sh
set -eu

TRIAL_ID="${TRIAL_ID:-local}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
TRIAL_DIR="/var/trial/${TRIAL_ID}"

mkdir -p "${TRIAL_DIR}"
printf '%s\n' "${TRIAL_ID}" > /var/trial/id
printf 'task=health-api\ntrial_id=%s\n' "${TRIAL_ID}" > "${TRIAL_DIR}/meta"

echo "sandbox: trial=${TRIAL_ID} workspace=${WORKSPACE:-/workspace}"

if [ "${RUN_TESTS:-0}" = "1" ]; then
  exec pytest /opt/task/tests -q
fi

if [ "${SKIP_SERVER:-0}" = "1" ]; then
  exec sleep infinity
fi

exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
