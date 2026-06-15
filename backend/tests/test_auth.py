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


def test_forgot_password_always_returns_200(client):
    res = client.post("/auth/forgot-password", json={"email": "nonexistent@test.com"})
    assert res.status_code == 200


def test_forgot_password_existing_email_returns_200(client):
    client.post("/auth/register", json={"email": "reset@test.com", "password": "password123"})
    res = client.post("/auth/forgot-password", json={"email": "reset@test.com"})
    assert res.status_code == 200


def test_reset_password_valid_token(client, db):
    from app.models import User
    from app.auth.service import create_reset_token
    client.post("/auth/register", json={"email": "newpass@test.com", "password": "oldpassword1"})
    user = db.query(User).filter_by(email="newpass@test.com").first()
    token = create_reset_token(user.id)
    res = client.post("/auth/reset-password", json={"token": token, "new_password": "newpassword1"})
    assert res.status_code == 200
    res2 = client.post("/auth/login", json={"email": "newpass@test.com", "password": "newpassword1"})
    assert res2.status_code == 200


def test_reset_password_invalid_token_returns_400(client):
    res = client.post("/auth/reset-password", json={"token": "not.a.token", "new_password": "newpassword1"})
    assert res.status_code == 400


def test_reset_password_wrong_purpose_token_returns_400(client, db):
    from app.models import User
    from app.auth.service import create_token
    client.post("/auth/register", json={"email": "wrongpurp@test.com", "password": "password123"})
    user = db.query(User).filter_by(email="wrongpurp@test.com").first()
    session_token = create_token(user.id)  # session token, not reset token
    res = client.post("/auth/reset-password", json={"token": session_token, "new_password": "newpassword1"})
    assert res.status_code == 400


def test_reset_password_short_password_returns_422(client, db):
    from app.models import User
    from app.auth.service import create_reset_token
    client.post("/auth/register", json={"email": "shortpw@test.com", "password": "password123"})
    user = db.query(User).filter_by(email="shortpw@test.com").first()
    token = create_reset_token(user.id)
    res = client.post("/auth/reset-password", json={"token": token, "new_password": "short"})
    assert res.status_code == 422
