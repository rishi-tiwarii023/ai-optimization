#!/bin/sh
set -eu

# Launch one isolated sandbox per trial.
# Networks, volumes, and containers never overlap across concurrent trials.

TRIAL_ID="${TRIAL_ID:?set TRIAL_ID}"
SAFE_ID=$(printf '%s' "${TRIAL_ID}" | tr '/: ' '___' | tr -cd 'A-Za-z0-9_-')
export TRIAL_ID

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

docker compose \
  --project-name "health-api-${SAFE_ID}" \
  --file "${SCRIPT_DIR}/docker-compose.yml" \
  up --build --remove-orphans --force-recreate "$@"
