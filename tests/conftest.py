import pytest
from backend.main import audit_rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    audit_rate_limiter.reset()
    yield
    audit_rate_limiter.reset()
