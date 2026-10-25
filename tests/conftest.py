import os
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Configure isolated SQLite database for all pytest runs before backend import
if "LOOMSHIELD_DB_PATH" not in os.environ or "test" not in os.environ.get("LOOMSHIELD_DB_PATH", "").lower():
    test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_loomshield_isolated.db"))
    os.environ["LOOMSHIELD_DB_PATH"] = test_db_path

from backend.main import audit_rate_limiter
from backend.database import init_db


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_db():
    init_db()
    audit_rate_limiter.reset()
    yield
    audit_rate_limiter.reset()
