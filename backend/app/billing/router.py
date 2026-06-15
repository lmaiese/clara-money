import asyncio
import uuid as _uuid
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User

stripe.api_key = settings.stripe_secret_key

protected_router = APIRouter(prefix="/billing")
webhook_router = APIRouter(prefix="/billing")


@protected_router.post("/checkout")
async def create_checkout(user: User = Depends(get_current_user)):
    # stripe SDK is sync — acceptable latency for MVP
    session = await asyncio.to_thread(
        stripe.checkout.Session.create,
        mode="subscription",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": 800,
                "recurring": {"interval": "month"},
                "product_data": {"name": "Clara Pro"},
            },
            "quantity": 1,
        }],
        client_reference_id=str(user.id),
        success_url=f"{settings.frontend_url}/dashboard?upgrade=success",
        cancel_url=f"{settings.frontend_url}/dashboard",
    )
    return {"checkout_url": session.url}


@webhook_router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        raw_user_id = session_obj.get("client_reference_id")
        stripe_customer_id = session_obj.get("customer")
        if raw_user_id:
            try:
                user_id = _uuid.UUID(raw_user_id)
            except ValueError:
                return {"status": "ok"}
            user = db.get(User, user_id)
            if user:
                user.plan = "pro"
                user.stripe_customer_id = stripe_customer_id
                db.commit()

    elif event["type"] == "customer.subscription.deleted":
        stripe_customer_id = event["data"]["object"].get("customer")
        if stripe_customer_id:
            user = db.query(User).filter_by(stripe_customer_id=stripe_customer_id).first()
            if user:
                user.plan = "free"
                db.commit()

    return {"status": "ok"}
