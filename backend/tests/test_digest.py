import pytest
from datetime import datetime, timezone, timedelta
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
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()  # non solleva, simula 2xx
    mock_aclient = MagicMock()
    mock_aclient.__aenter__ = AsyncMock(return_value=mock_aclient)
    mock_aclient.__aexit__ = AsyncMock(return_value=None)
    mock_aclient.post = AsyncMock(return_value=mock_response)
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


# ---------------------------------------------------------------------------
# Job logic tests
# ---------------------------------------------------------------------------

def test_run_digest_skips_free_users(client, db, digest_settings):
    """Utente free con profilo completo → skippato, nessuna email inviata."""
    client.post("/auth/register", json={"email": "free@test.com", "password": "password123"})
    user = db.query(User).filter_by(email="free@test.com").first()
    # plan rimane "free" (default)
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

    mock_aclient = _make_resend_mock()
    with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
        resp = client.post("/admin/run-digest", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
    mock_aclient.post.assert_not_called()


def test_run_digest_email_failure_does_not_commit_scenario(client, db, digest_settings, pro_user_with_profile):
    """Se Resend ritorna errore → scenario NON salvato in DB, errors=1, retry possibile il run successivo."""
    import httpx as _httpx
    user = pro_user_with_profile

    # Mock Resend che ritorna 422
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "422 Unprocessable Entity", request=MagicMock(), response=MagicMock()
    )
    mock_aclient = MagicMock()
    mock_aclient.__aenter__ = AsyncMock(return_value=mock_aclient)
    mock_aclient.__aexit__ = AsyncMock(return_value=None)
    mock_aclient.post = AsyncMock(return_value=mock_response)

    with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
        resp = client.post("/admin/run-digest", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json() == {"sent": 0, "skipped": 0, "errors": 1}
    # Scenario NON committato → retry possibile al prossimo run
    assert db.query(Scenario).filter_by(user_id=user.id).count() == 0


def test_run_digest_pro_user_gets_email(client, db, digest_settings, monkeypatch, pro_user_with_profile):
    """Utente Pro con Scenario precedente → email inviata con delta, nuovo Scenario salvato."""
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake")
    user = pro_user_with_profile

    # Scenario precedente del mese scorso con valori noti
    now = datetime.now(timezone.utc)
    last_month = now.replace(day=1) - timedelta(days=1)
    prev = Scenario(
        user_id=user.id,
        generated_at=last_month,
        profile_snapshot={
            "age": 30, "monthly_income": 2000, "monthly_expenses": 1000,
            "liquid_savings": 5000, "existing_investments": 0,
            "goal": "casa", "horizon_years": 10,
        },
        math_data={
            "sicuro": [5000.0, 8000.0],
            "bilanciato": [5000.0, 9000.0],
            "crescita": [5000.0, 10000.0],
            "inflazione": [5000.0, 6000.0],
            "labels": [0, 1],
        },
        narrative_ready=True,
    )
    db.add(prev)
    db.commit()

    mock_aclient = _make_resend_mock()
    with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient), \
         patch("app.admin.digest.Anthropic") as mock_claude:
        mock_claude.return_value.messages.create.return_value.content = [
            MagicMock(text='{"intro":"intro","sicuro":"s","bilanciato":"b","crescita":"c"}')
        ]
        resp = client.post("/admin/run-digest", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json()["sent"] == 1
    assert resp.json()["errors"] == 0
    # Nuovo Scenario salvato (2 totali: prev + nuovo)
    assert db.query(Scenario).filter_by(user_id=user.id).count() == 2
    # Email inviata all'indirizzo corretto con delta
    call_json = mock_aclient.post.call_args.kwargs["json"]
    assert user.email in call_json["to"]
    assert "vs mese scorso" in call_json["html"]


def test_run_digest_no_previous_scenario(client, db, digest_settings, pro_user_with_profile):
    """Primo scenario dell'utente → email inviata senza delta."""
    user = pro_user_with_profile

    mock_aclient = _make_resend_mock()
    with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
        resp = client.post("/admin/run-digest", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json()["sent"] == 1
    call_json = mock_aclient.post.call_args.kwargs["json"]
    assert "vs mese scorso" not in call_json["html"]


def test_run_digest_dedup_skips_already_sent(client, db, digest_settings, pro_user_with_profile):
    """Scenario già generato questo mese → utente skippato, nessuna email."""
    user = pro_user_with_profile
    now = datetime.now(timezone.utc)

    existing = Scenario(
        user_id=user.id,
        profile_snapshot={
            "age": 30, "monthly_income": 2000, "monthly_expenses": 1000,
            "liquid_savings": 5000, "existing_investments": 0,
            "goal": "casa", "horizon_years": 10,
        },
        math_data={
            "sicuro": [5000.0], "bilanciato": [5000.0], "crescita": [5000.0],
            "inflazione": [5000.0], "labels": [0],
        },
        generated_at=now,
        narrative_ready=True,
    )
    db.add(existing)
    db.commit()

    mock_aclient = _make_resend_mock()
    with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
        resp = client.post("/admin/run-digest", headers=AUTH)

    assert resp.status_code == 200
    assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
    mock_aclient.post.assert_not_called()
