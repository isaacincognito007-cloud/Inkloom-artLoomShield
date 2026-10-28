"""
Pytest configuration and shared fixtures for LoomShield.
Sets LOOMSHIELD_DEPLOYMENT=local by default during automated test runs so
configured_role() does not inspect PYTEST_CURRENT_TEST in production code,
and resets in-memory rate limiters between test functions.
"""

import pytest


@pytest.fixture(autouse=True)
def set_local_deployment_for_tests(monkeypatch):
    monkeypatch.setenv("LOOMSHIELD_DEPLOYMENT", "local")
    try:
        import backend.main as main_mod
        main_mod.audit_rate_limiter.reset()
        main_mod.verify_rate_limiter.reset()
    except Exception:
        pass
