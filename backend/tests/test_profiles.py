import pytest

@pytest.fixture
def auth_client(client):
    """Client con utente autenticato."""
    client.post("/auth/register", json={"email": "p@test.com", "password": "password123"})
    return client

def test_get_profile_returns_empty_for_new_user(auth_client):
    res = auth_client.get("/profiles/me")
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_step"] == 0
    assert data["age"] is None

def test_patch_profile_step1(auth_client):
    res = auth_client.patch("/profiles/me", json={"age": 32, "monthly_income": 2400, "onboarding_step": 1})
    assert res.status_code == 200
    profile = auth_client.get("/profiles/me").json()
    assert profile["age"] == 32
    assert profile["monthly_income"] == 2400
    assert profile["onboarding_step"] == 1

def test_patch_profile_step_by_step_full_onboarding(auth_client):
    steps = [
        {"age": 30, "monthly_income": 2000, "onboarding_step": 1},
        {"monthly_expenses": 1200, "onboarding_step": 2},
        {"liquid_savings": 15000, "onboarding_step": 3},
        {"existing_investments": 0, "onboarding_step": 4},
        {"goal": "growth", "horizon_years": 15, "onboarding_step": 5},
    ]
    for step in steps:
        res = auth_client.patch("/profiles/me", json=step)
        assert res.status_code == 200
    profile = auth_client.get("/profiles/me").json()
    assert profile["onboarding_step"] == 5
    assert profile["goal"] == "growth"
    assert profile["horizon_years"] == 15

def test_patch_rejects_invalid_age(auth_client):
    res = auth_client.patch("/profiles/me", json={"age": 150, "onboarding_step": 1})
    assert res.status_code == 422

def test_resume_from_step_3(auth_client):
    auth_client.patch("/profiles/me", json={"age": 28, "monthly_income": 1800, "onboarding_step": 1})
    auth_client.patch("/profiles/me", json={"monthly_expenses": 900, "onboarding_step": 2})
    auth_client.patch("/profiles/me", json={"liquid_savings": 5000, "onboarding_step": 3})
    profile = auth_client.get("/profiles/me").json()
    assert profile["onboarding_step"] == 3

def test_get_profile_requires_auth(client):
    res = client.get("/profiles/me")
    assert res.status_code == 401
