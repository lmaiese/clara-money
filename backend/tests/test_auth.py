def test_register_creates_user_and_profile(client, db):
    from app.models import User, Profile
    res = client.post("/auth/register", json={"email": "user@test.com", "password": "password123"})
    assert res.status_code == 200
    assert res.json()["message"] == "registered"
    assert "access_token" in res.cookies
    user = db.query(User).filter_by(email="user@test.com").first()
    assert user is not None
    profile = db.query(Profile).filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.onboarding_step == 0


def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@test.com", "password": "password123"})
    res = client.post("/auth/register", json={"email": "dup@test.com", "password": "password123"})
    assert res.status_code == 409


def test_login_returns_jwt_cookie(client):
    client.post("/auth/register", json={"email": "login@test.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "login@test.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.cookies


def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "wrong@test.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "wrong@test.com", "password": "wrongpass"})
    assert res.status_code == 401


def test_logout_clears_cookie(client):
    client.post("/auth/register", json={"email": "logout@test.com", "password": "password123"})
    res = client.post("/auth/logout")
    assert res.status_code == 200
    assert res.cookies.get("access_token", "") == ""


def test_me_returns_user_with_plan(client):
    client.post("/auth/register", json={"email": "me@test.com", "password": "password123"})
    res = client.get("/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "me@test.com"
    assert data["plan"] == "free"
    assert "id" in data


def test_me_unauthenticated_returns_401(client):
    res = client.get("/auth/me")
    assert res.status_code == 401
