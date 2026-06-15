from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


def _setup_completed_user(client: TestClient) -> None:
    """Register and complete the profile of a user."""
    client.post("/auth/register", json={"email": "m2user@clara.it", "password": "password123"})
    client.patch("/profiles/me", json={
        "age": 32,
        "monthly_income": 3000,
        "monthly_expenses": 1800,
        "liquid_savings": 15000,
        "existing_investments": 5000,
        "goal": "growth",
        "horizon_years": 15,
        "onboarding_step": 5,
    })


def test_generate_returns_math_data(client):
    _setup_completed_user(client)
    with patch("app.scenarios.service._run_narrative_generation"):
        res = client.post("/scenarios/generate")
    assert res.status_code == 200
    data = res.json()
    assert "math_data" in data
    assert set(data["math_data"].keys()) == {"sicuro", "bilanciato", "crescita", "inflazione", "labels"}
    assert len(data["math_data"]["labels"]) == 16  # horizon 15 → 0..15


def test_generate_creates_scenario_in_db(client):
    _setup_completed_user(client)
    with patch("app.scenarios.service._run_narrative_generation"):
        res = client.post("/scenarios/generate")
    assert res.status_code == 200
    data = res.json()
    assert "scenario_id" in data
    assert data["narrative_ready"] is False
    assert "sources" in data  # campo presente (può essere null)


def test_get_me_returns_latest_scenario(client):
    _setup_completed_user(client)
    with patch("app.scenarios.service._run_narrative_generation"):
        client.post("/scenarios/generate")
    res = client.get("/scenarios/me")
    assert res.status_code == 200
    data = res.json()
    assert "math_data" in data
    assert data["narrative_ready"] is False


def test_get_me_returns_null_if_no_scenarios(client):
    client.post("/auth/register", json={"email": "empty@clara.it", "password": "password123"})
    res = client.get("/scenarios/me")
    assert res.status_code == 200
    assert res.json() is None


def test_generate_returns_400_if_profile_incomplete(client):
    client.post("/auth/register", json={"email": "incomplete@clara.it", "password": "password123"})
    res = client.post("/scenarios/generate")
    assert res.status_code == 400
    assert "not complete" in res.json()["detail"]


def test_generate_requires_auth(client):
    # TestClient without session cookie
    from fastapi.testclient import TestClient as TC
    from app.main import app
    plain = TC(app)
    res = plain.post("/scenarios/generate")
    assert res.status_code == 401
