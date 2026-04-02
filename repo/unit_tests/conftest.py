"""
Unit-test configuration.

The tester Docker service mounts ./backend at /app and sets PYTHONPATH=/app,
so `from app.*` imports resolve automatically.  When running locally, set
PYTHONPATH to the repo's backend/ directory before invoking pytest.
"""
import sys
import os

# Ensure the backend source tree is importable when running outside Docker.
_backend_dir = os.environ.get("BACKEND_PATH", os.path.join(os.path.dirname(__file__), "..", "backend"))
if os.path.isdir(_backend_dir) and _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
