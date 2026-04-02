#!/usr/bin/env bash
# run_tests.sh — TraceCare test runner (idempotent, no manual setup required).
#
# Usage:
#   ./run_tests.sh
#
# What it does:
#   1. Ensures db and backend services are running (starts them if needed).
#   2. Waits for the backend health-check to pass.
#   3. Runs all unit tests (unit_tests/) and API tests (API_tests/) inside
#      the tester Docker service, then exits with the pytest exit code.
#
# Requirements: docker compose v2  (docker compose plugin, not docker-compose)

set -euo pipefail

COMPOSE="docker compose"

echo "======================================================"
echo "  TraceCare Test Suite"
echo "======================================================"

# Bring up the backend stack in detached mode (idempotent — safe to re-run).
echo "[1/3] Starting core services (db + backend)..."
$COMPOSE up -d db backend

# Poll until backend is healthy (up to 90 s).
echo "[2/3] Waiting for backend to become healthy..."
RETRIES=18
INTERVAL=5
for i in $(seq 1 $RETRIES); do
    STATUS=$($COMPOSE ps --format json backend 2>/dev/null | python3 -c "
import sys, json
data = sys.stdin.read().strip()
# docker compose ps --format json may emit one JSON object per line
for line in data.splitlines():
    try:
        obj = json.loads(line)
        print(obj.get('Health', obj.get('Status', 'unknown')))
        break
    except Exception:
        pass
print('unknown')
" 2>/dev/null | head -1 || echo "unknown")

    if [[ "$STATUS" == "healthy" ]]; then
        echo "  Backend is healthy."
        break
    fi

    if [[ $i -eq $RETRIES ]]; then
        echo "  ERROR: Backend did not become healthy after $((RETRIES * INTERVAL)) seconds."
        $COMPOSE logs backend | tail -30
        exit 1
    fi

    echo "  Waiting ($i/$RETRIES)... status=${STATUS}"
    sleep $INTERVAL
done

# Run the tester service (--profile test activates it; --rm removes container after).
echo "[3/3] Running unit_tests/ and API_tests/..."
$COMPOSE --profile test run --rm tester
EXIT_CODE=$?

echo "======================================================"
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "  ALL TESTS PASSED"
else
    echo "  TESTS FAILED (exit code $EXIT_CODE)"
fi
echo "======================================================"
exit $EXIT_CODE
