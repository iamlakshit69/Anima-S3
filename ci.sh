#!/usr/bin/env bash
# ci.sh — Continuous Integration runner for ANIMA-S3.
#
# Runs:
#   1. Protocol vector tests
#   2. Server unit and integration tests
#   3. C++ firmware host tests
#   4. anima_check system diagnostics
#
# Exit 0 if all test suites pass, 1 if any suite fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=========================================================="
echo "         ANIMA-S3 CONTINUOUS INTEGRATION RUNNER           "
echo "=========================================================="

PYTHON_BIN=".venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

# 1. Protocol Tests
echo ""
echo "[1/4] Running Protocol vector tests..."
PYTHONPATH=. "$PYTHON_BIN" -m pytest protocol/tests -q
echo "✓ Protocol tests passed"

# 2. Server Tests
echo ""
echo "[2/4] Running Server unit and integration tests..."
PYTHONPATH=server "$PYTHON_BIN" -m pytest server/tests -q
echo "✓ Server tests passed"

# 3. C++ Host Tests
echo ""
echo "[3/4] Building and executing C++ Host Tests..."
cmake -S firmware/host_test -B firmware/host_test/build >/dev/null
cmake --build firmware/host_test/build >/dev/null
ctest --test-dir firmware/host_test/build --output-on-failure
echo "✓ C++ host tests passed"

# 4. Diagnostics check
echo ""
echo "[4/4] Running anima_check diagnostics..."
PYTHONPATH=server "$PYTHON_BIN" -m anima_server.diagnostics
echo "✓ Diagnostics check completed"

echo ""
echo "=========================================================="
echo "        ALL ANIMA-S3 TEST SUITES PASSED (GREEN)           "
echo "=========================================================="
