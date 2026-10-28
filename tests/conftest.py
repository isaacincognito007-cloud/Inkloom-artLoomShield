import os
import sys
import tempfile
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Configure isolated temporary SQLite database for pytest runs (get_db_path() reads LOOMSHIELD_DB_PATH at call time)
_TEMP_DB_DIR = tempfile.mkdtemp(prefix="loomshield_pytest_db_")
_TEMP_TEST_DB_PATH = os.path.join(_TEMP_DB_DIR, "test_loomshield_isolated.db")
if "LOOMSHIELD_DB_PATH" not in os.environ or "test" not in os.environ.get("LOOMSHIELD_DB_PATH", "").lower():
    os.environ["LOOMSHIELD_DB_PATH"] = _TEMP_TEST_DB_PATH

from backend.main import audit_rate_limiter, verify_rate_limiter
from backend.database import init_db


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_db(request, monkeypatch):
    monkeypatch.setenv("LOOMSHIELD_DEPLOYMENT", "local")
    # test_loomshield_cycles_0_to_9.py manages its own module-scoped ISOLATED_TEST_DB and asserts get_db_path() == ISOLATED_TEST_DB
    if "test_loomshield_cycles_0_to_9" not in str(getattr(request.node, "fspath", "")):
        monkeypatch.setenv("LOOMSHIELD_DB_PATH", _TEMP_TEST_DB_PATH)
    init_db()
    audit_rate_limiter.reset()
    verify_rate_limiter.reset()
    yield
    audit_rate_limiter.reset()
    verify_rate_limiter.reset()
