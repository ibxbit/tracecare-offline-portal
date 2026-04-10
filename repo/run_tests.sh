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

# Bring up the core services and wait for the backend to pass its healthcheck.
# We run 'up backend' which will trigger dependencies.
echo "[1/2] Preparing environment (db + backend)..."
$COMPOSE up -d backend

echo "[2/2] Running unit_tests/ and API_tests/..."
# The 'tester' service depends on 'backend' being healthy. 
# Docker Compose will automatically wait for the healthcheck to pass before running the tester.

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
