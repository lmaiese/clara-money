import pytest
from app.config import settings
from app.models import Waitlist

AUTH = {"Authorization": "Bearer testsecret"}


@pytest.fixture
def admin_secret(monkeypatch):
    monkeypatch.setattr(settings, "digest_secret", "testsecret")


def test_join_waitlist_success(client, db):
    resp = client.post("/waitlist", json={"email": "test@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"message": "Subscribed successfully"}
    entry = db.query(Waitlist).filter_by(email="test@example.com").first()
    assert entry is not None


def test_join_waitlist_duplicate(client, db):
    client.post("/waitlist", json={"email": "dup@example.com"})
    resp = client.post("/waitlist", json={"email": "dup@example.com"})
    assert resp.status_code == 409


def test_join_waitlist_invalid_email(client):
    resp = client.post("/waitlist", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_get_waitlist_unauthorized(client):
    resp = client.get("/admin/waitlist")
    assert resp.status_code == 401


def test_get_waitlist_returns_list(client, db, admin_secret):
    client.post("/waitlist", json={"email": "a@example.com"})
    client.post("/waitlist", json={"email": "b@example.com"})
    resp = client.get("/admin/waitlist", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert "a@example.com" in data["emails"]
    assert "b@example.com" in data["emails"]


def test_join_waitlist_normalizes_email(client, db):
    client.post("/waitlist", json={"email": "TEST@EXAMPLE.COM"})
    resp = client.post("/waitlist", json={"email": "test@example.com"})
    assert resp.status_code == 409
    entry = db.query(Waitlist).filter_by(email="test@example.com").first()
    assert entry is not None


def test_get_waitlist_empty(client, admin_secret):
    resp = client.get("/admin/waitlist", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["emails"] == []
