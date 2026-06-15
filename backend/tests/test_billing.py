import stripe
from unittest.mock import patch, MagicMock


def test_checkout_unauthenticated_returns_401(client):
    res = client.post("/billing/checkout")
    assert res.status_code == 401


def test_checkout_returns_checkout_url(client):
    client.post("/auth/register", json={"email": "checkout@test.com", "password": "password123"})
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test-session-url"
    with patch("app.billing.router.stripe.checkout.Session.create", return_value=mock_session):
        res = client.post("/billing/checkout")
    assert res.status_code == 200
    assert res.json()["checkout_url"] == "https://checkout.stripe.com/test-session-url"


def test_webhook_invalid_signature_returns_400(client):
    with patch("app.billing.router.stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = stripe.SignatureVerificationError("bad", "sig")
        res = client.post(
            "/billing/webhook",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=bad"},
        )
    assert res.status_code == 400


def test_webhook_valid_signature_upgrades_plan(client, db):
    from app.models import User
    client.post("/auth/register", json={"email": "wh@test.com", "password": "password123"})
    user = db.query(User).filter_by(email="wh@test.com").first()
    user_id = str(user.id)

    mock_event = {
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": user_id, "customer": "cus_test123"}},
    }
    with patch("app.billing.router.stripe.Webhook.construct_event", return_value=mock_event):
        res = client.post(
            "/billing/webhook",
            content=b'{"type":"checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=ok"},
        )
    assert res.status_code == 200
    db.refresh(user)
    assert user.plan == "pro"
    assert user.stripe_customer_id == "cus_test123"


def test_webhook_unknown_event_type_returns_200(client):
    mock_event = {"type": "customer.subscription.deleted", "data": {"object": {}}}
    with patch("app.billing.router.stripe.Webhook.construct_event", return_value=mock_event):
        res = client.post(
            "/billing/webhook",
            content=b'{"type":"customer.subscription.deleted"}',
            headers={"stripe-signature": "t=1,v1=ok"},
        )
    assert res.status_code == 200
