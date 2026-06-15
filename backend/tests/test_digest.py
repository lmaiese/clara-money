import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.models import Profile, Scenario, User


AUTH = {"Authorization": "Bearer testsecret"}


@pytest.fixture
def digest_settings(monkeypatch):
    """Configura digest_secret e resend_api_key per i test.
    anthropic_api_key rimane "" → narrativa fallback template (nessuna chiamata Claude)."""
    monkeypatch.setattr(settings, "digest_secret", "testsecret")
    monkeypatch.setattr(settings, "resend_api_key", "re_fake")


@pytest.fixture
def pro_user_with_profile(client, db):
    """Crea un utente Pro con profilo completo (onboarding_step=5)."""
    client.post("/auth/register", json={"email": "pro@test.com", "password": "password123"})
    user = db.query(User).filter_by(email="pro@test.com").first()
    user.plan = "pro"
    profile = db.get(Profile, user.id)
    profile.onboarding_step = 5
    profile.age = 30
    profile.monthly_income = 2000
    profile.monthly_expenses = 1000
    profile.liquid_savings = 5000
    profile.horizon_years = 10
    profile.goal = "casa"
    profile.existing_investments = 0
    db.commit()
    return user


def _make_resend_mock():
    """Helper: mock per httpx.AsyncClient usato come context manager async."""
    mock_aclient = MagicMock()
    mock_aclient.__aenter__ = AsyncMock(return_value=mock_aclient)
    mock_aclient.__aexit__ = AsyncMock(return_value=None)
    mock_aclient.post = AsyncMock()
    return mock_aclient


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_run_digest_unauthorized(client):
    """Nessun header Authorization → 401."""
    resp = client.post("/admin/run-digest")
    assert resp.status_code == 401


def test_run_digest_wrong_secret(client, digest_settings):
    """Secret sbagliato → 401."""
    resp = client.post("/admin/run-digest", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401
