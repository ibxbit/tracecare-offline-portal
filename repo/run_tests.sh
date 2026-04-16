#!/usr/bin/env bash
# run_tests.sh — TraceCare unified test runner (Docker-only).
#
# Runs the full test matrix from a single command inside Docker Compose:
#
#   1. Backend unit_tests/  — pure-logic pytest (no DB)
#   2. Backend API_tests/   — real HTTP against the live backend + real DB
#   3. Frontend vitest       — Vue component and store tests (jsdom)
#
# All suites run inside Docker containers for CI reproducibility.
# No host-local toolchain required beyond docker + docker compose v2.
#
# Usage:
#   ./run_tests.sh              # run everything
#   ./run_tests.sh backend      # backend only (unit + API)
#   ./run_tests.sh frontend     # frontend only
#
# Exit code: 0 if every suite passes, non-zero otherwise.

set -uo pipefail

COMPOSE="docker compose"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-tracecare}"
MODE="${1:-all}"

BACKEND_CODE=0
FRONTEND_CODE=0

run_backend() {
    echo "======================================================"
    echo "  [1/2] Backend (unit_tests/ + API_tests/)"
    echo "======================================================"
    $COMPOSE -p "$PROJECT_NAME" up -d backend
    $COMPOSE -p "$PROJECT_NAME" --profile test run --rm tester
    BACKEND_CODE=$?
    echo "  backend tests exit code: $BACKEND_CODE"
}

run_frontend() {
    echo "======================================================"
    echo "  [2/2] Frontend (vitest)"
    echo "======================================================"
    $COMPOSE -p "$PROJECT_NAME" --profile test run --rm frontend-tester
    FRONTEND_CODE=$?
    echo "  frontend tests exit code: $FRONTEND_CODE"
}

case "$MODE" in
    backend)
        run_backend
        TOTAL=$BACKEND_CODE
        ;;
    frontend)
        run_frontend
        TOTAL=$FRONTEND_CODE
        ;;
    all|*)
        run_backend
        run_frontend
        TOTAL=$(( BACKEND_CODE | FRONTEND_CODE ))
        ;;
esac

echo "======================================================"
if [[ $TOTAL -eq 0 ]]; then
    echo "  ALL TESTS PASSED"
else
    echo "  TESTS FAILED (backend=$BACKEND_CODE, frontend=$FRONTEND_CODE)"
fi
echo "======================================================"
exit $TOTAL
