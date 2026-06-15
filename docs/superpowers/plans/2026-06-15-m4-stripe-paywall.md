# Clara Money M4 — Stripe, Paywall, Password Reset

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere monetizzazione (Stripe Checkout Pro 8€/mese), freemium paywall sulla dashboard, e password reset via email (Resend).

**Architecture:** DB: aggiunta colonne `plan` + `stripe_customer_id` su `users`. Backend: billing router con due sub-router separati (checkout protetto + webhook unauthenticated), due nuovi endpoint auth (/me, /forgot-password, /reset-password). Frontend: hook `useDashboard` arricchito con `plan`, componente `PaywallGate`, due nuove pagine auth. Paywall è frontend-only per MVP (tutti i dati sempre restituiti dal backend, gate presentazionale).

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, stripe-python ≥ 5.0, httpx (già in requirements), python-jose (già installato), Next.js 14 App Router, TypeScript.

---

## File Map

**Backend — Modificati:**
- `backend/app/models.py` — aggiorna `plan` (String(10), nullable=False, server_default, CheckConstraint) e `stripe_customer_id` (String(255))
- `backend/app/schemas.py` — aggiunge `UserResponse`, `ForgotPasswordRequest`, `ResetPasswordRequest`
- `backend/app/auth/router.py` — aggiunge `GET /auth/me`, `POST /auth/forgot-password`, `POST /auth/reset-password`
- `backend/app/auth/service.py` — aggiunge `create_reset_token()`, `decode_reset_token()`
- `backend/app/main.py` — monta `billing.protected_router` e `billing.webhook_router`
- `backend/requirements.txt` — aggiunge `stripe`

**Backend — Creati:**
- `backend/alembic/versions/xxxx_m4_billing.py` — migration plan + stripe_customer_id
- `backend/app/auth/email.py` — `send_reset_email()` via Resend
- `backend/app/billing/__init__.py` — package vuoto
- `backend/app/billing/router.py` — protected_router (checkout) + webhook_router (webhook)

**Backend — Test:**
- `backend/tests/test_auth.py` — aggiunge test /me, /forgot-password, /reset-password
- `backend/tests/test_billing.py` — creato: test checkout, webhook (signature valida/invalida)

**Frontend — Modificati:**
- `frontend/lib/types.ts` — aggiunge interfaccia `User`
- `frontend/app/dashboard/useDashboard.ts` — fetcha `/auth/me`, aggiunge `plan` allo stato
- `frontend/app/dashboard/ScenarioCards.tsx` — accetta `plan` prop, rende `PaywallGate` per bilanciato/crescita quando free
- `frontend/app/dashboard/page.tsx` — passa `plan`, monta `PaywallBanner`, gestisce `?upgrade=success`
- `frontend/app/auth/page.tsx` — aggiunge link "Password dimenticata?"

**Frontend — Creati:**
- `frontend/app/dashboard/PaywallGate.tsx` — `PaywallGate` (card locked) + `PaywallBanner` (CTA banner)
- `frontend/app/auth/forgot-password/page.tsx` — form email per reset
- `frontend/app/reset-password/page.tsx` — form nuova password con token da URL

---

### Task 1: DB model update + Alembic migration

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/xxxx_m4_billing.py`
- Test: `backend/tests/test_auth.py` (run suite completa)

- [ ] **Step 1: Aggiorna User model in `backend/app/models.py`**

Aggiungi `CheckConstraint` agli import, poi modifica la classe `User`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(
        String(10), nullable=False, default="free", server_default="free"
    )

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)

    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan"),
    )
```

Lascia invariate le classi `Profile`, `Scenario`, `Document`.

- [ ] **Step 2: Verifica che i test esistenti passino ancora**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/ -v
```

Expected: tutti e 34 test passano. Il conftest usa `Base.metadata.create_all()` che legge il modello aggiornato direttamente.

- [ ] **Step 3: Crea la Alembic migration manualmente**

Crea il file `backend/alembic/versions/a1b2c3d4e5f6_m4_billing.py` (usa un id di 12 caratteri hex come prefisso):

```python
"""m4_billing

Revision ID: a1b2c3d4e5f6
Revises: 8fa9f3ea26c8
Create Date: 2026-06-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8fa9f3ea26c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "plan", sa.String(10), nullable=False, server_default="free"
    ))
    op.add_column("users", sa.Column(
        "stripe_customer_id", sa.String(255), nullable=True
    ))
    op.create_check_constraint("ck_users_plan", "users", "plan IN ('free', 'pro')")


def downgrade() -> None:
    op.drop_constraint("ck_users_plan", "users", type_="check")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "plan")
```

- [ ] **Step 4: Verifica sintassi migration (non eseguirla sul DB — il DB di test usa create_all)**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && python -c "from alembic.config import Config; from alembic import command; c = Config('alembic.ini'); print('OK')"
```

Expected: stampa `OK` senza errori.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/a1b2c3d4e5f6_m4_billing.py
git commit -m "feat: add plan and stripe_customer_id to User model + M4 migration"
```

---

### Task 2: UserResponse schema + GET /auth/me

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/auth/router.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Scrivi i test fallenti per /auth/me in `backend/tests/test_auth.py`**

Aggiungi alla fine del file esistente:

```python
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
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_auth.py::test_me_returns_user_with_plan tests/test_auth.py::test_me_unauthenticated_returns_401 -v
```

Expected: FAIL con `404 Not Found` (route non esiste ancora).

- [ ] **Step 3: Aggiungi `UserResponse` a `backend/app/schemas.py`**

Aggiungi dopo `LoginRequest`:

```python
import uuid as _uuid


class UserResponse(BaseModel):
    id: _uuid.UUID
    email: str
    plan: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Aggiungi `GET /auth/me` a `backend/app/auth/router.py`**

Aggiungi l'import `UserResponse`:

```python
from app.schemas import RegisterRequest, LoginRequest, UserResponse
```

Aggiungi l'endpoint alla fine del file:

```python
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user
```

- [ ] **Step 5: Esegui i test — devono passare**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_auth.py -v
```

Expected: tutti i test di test_auth.py passano.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/auth/router.py backend/tests/test_auth.py
git commit -m "feat: UserResponse schema + GET /auth/me endpoint"
```

---

### Task 3: Stripe billing router (checkout + webhook)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/billing/__init__.py`
- Create: `backend/app/billing/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_billing.py`

- [ ] **Step 1: Aggiungi `stripe` a requirements e installa**

In `backend/requirements.txt`, aggiungi alla fine:

```
stripe>=5.0.0
```

Poi installa:

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pip install "stripe>=5.0.0"
```

Expected: `Successfully installed stripe-X.Y.Z`.

- [ ] **Step 2: Scrivi i test fallenti in `backend/tests/test_billing.py`**

```python
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
```

- [ ] **Step 3: Esegui i test — devono fallire**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_billing.py -v
```

Expected: FAIL con `404` o import error.

- [ ] **Step 4: Crea `backend/app/billing/__init__.py`**

File vuoto:

```python
```

- [ ] **Step 5: Crea `backend/app/billing/router.py`**

```python
import asyncio
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
        success_url="http://localhost:3000/dashboard?upgrade=success",
        cancel_url="http://localhost:3000/dashboard",
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
        user_id = session_obj.get("client_reference_id")
        stripe_customer_id = session_obj.get("customer")
        if user_id:
            user = db.get(User, user_id)
            if user:
                user.plan = "pro"
                user.stripe_customer_id = stripe_customer_id
                db.commit()

    return {"status": "ok"}
```

- [ ] **Step 6: Registra i router in `backend/app/main.py`**

Aggiungi i due import e include_router:

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.router import router as auth_router
from app.profiles.router import router as profiles_router
from app.scenarios.router import router as scenarios_router
from app.billing.router import protected_router as billing_protected_router
from app.billing.router import webhook_router as billing_webhook_router
from app.config import settings, JWT_SECRET_IS_DEV_DEFAULT

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if JWT_SECRET_IS_DEV_DEFAULT:
        logger.warning("⚠️  JWT_SECRET is using the dev default — set JWT_SECRET in .env before deploying")
    yield


app = FastAPI(title="Clara Money API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
app.include_router(scenarios_router, prefix="/scenarios", tags=["scenarios"])
app.include_router(billing_protected_router, tags=["billing"])
app.include_router(billing_webhook_router, tags=["billing"])
```

- [ ] **Step 7: Esegui i test — devono passare**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_billing.py -v
```

Expected: tutti e 5 i test billing passano.

- [ ] **Step 8: Esegui la suite completa**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: tutti i test passano.

- [ ] **Step 9: Commit**

```bash
git add backend/requirements.txt backend/app/billing/ backend/app/main.py backend/tests/test_billing.py
git commit -m "feat: Stripe billing router — checkout + webhook with signature verification"
```

---

### Task 4: Password reset backend (forgot-password + reset-password + email)

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/auth/service.py`
- Create: `backend/app/auth/email.py`
- Modify: `backend/app/auth/router.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Scrivi i test fallenti in `backend/tests/test_auth.py`**

Aggiungi alla fine del file:

```python
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
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_auth.py::test_forgot_password_always_returns_200 -v
```

Expected: FAIL con `404`.

- [ ] **Step 3: Aggiungi `create_reset_token` e `decode_reset_token` a `backend/app/auth/service.py`**

Aggiungi dopo `decode_token`:

```python
def create_reset_token(user_id: uuid.UUID) -> str:
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": str(user_id), "purpose": "password-reset", "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_reset_token(token: str) -> uuid.UUID:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("purpose") != "password-reset":
        raise JWTError("Invalid token purpose")
    return uuid.UUID(payload["sub"])
```

L'import `from datetime import timedelta` è locale per non inquinare il namespace del modulo (ma se preferisci puoi aggiungerlo agli import top-level — il modulo usa già `datetime` e `timedelta` indirettamente).

Nota: il file importa già `from jose import jwt, JWTError` — ✅

- [ ] **Step 4: Crea `backend/app/auth/email.py`**

```python
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def send_reset_email(to_email: str, reset_link: str) -> None:
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping password reset email")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": "Clara <noreply@claramoney.it>",
                    "to": [to_email],
                    "subject": "Reimposta la tua password — Clara",
                    "html": (
                        f"<p>Hai richiesto il reset della password.</p>"
                        f"<p><a href='{reset_link}'>Clicca qui per reimpostare</a> (link valido 1 ora).</p>"
                        f"<p>Se non hai richiesto il reset, ignora questa email.</p>"
                    ),
                },
            )
    except Exception:
        logger.exception("Failed to send reset email to %s", to_email)
```

- [ ] **Step 5: Aggiungi gli schema a `backend/app/schemas.py`**

Aggiungi dopo `LoginRequest`:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
```

- [ ] **Step 6: Aggiungi i tre endpoint a `backend/app/auth/router.py`**

Aggiungi gli import necessari in cima al file:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Profile
from app.schemas import RegisterRequest, LoginRequest, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.auth.service import hash_password, verify_password, create_token, create_reset_token, decode_reset_token
from app.auth.dependencies import get_current_user
from app.auth.email import send_reset_email
from app.config import settings
from jose import JWTError
```

Poi aggiungi alla fine del file:

```python
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user:
        token = create_reset_token(user.id)
        reset_link = f"http://localhost:3000/reset-password?token={token}"
        await send_reset_email(user.email, reset_link)
    return {"message": "Se l'email esiste, riceverai un link di reset"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user_id = decode_reset_token(body.token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Password aggiornata"}
```

Nota: `GET /auth/me` è già stato aggiunto nel Task 2. Assicurati di non duplicarlo — se è già presente nel file, salta questo endpoint.

- [ ] **Step 7: Esegui i test — devono passare**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/test_auth.py -v
```

Expected: tutti i test di test_auth.py passano (inclusi i 6 nuovi).

- [ ] **Step 8: Esegui la suite completa**

```bash
source .venv/bin/activate && pytest tests/ -v
```

Expected: tutti i test passano.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas.py backend/app/auth/service.py backend/app/auth/email.py backend/app/auth/router.py backend/tests/test_auth.py
git commit -m "feat: password reset — forgot-password + reset-password endpoints + Resend email"
```

---

### Task 5: Frontend — plan state + PaywallGate

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/app/dashboard/useDashboard.ts`
- Create: `frontend/app/dashboard/PaywallGate.tsx`
- Modify: `frontend/app/dashboard/ScenarioCards.tsx`
- Modify: `frontend/app/dashboard/page.tsx`

- [ ] **Step 1: Aggiungi `User` a `frontend/lib/types.ts`**

Aggiungi dopo `ScenarioResponse`:

```typescript
export interface User {
  id: string
  email: string
  plan: 'free' | 'pro'
}
```

- [ ] **Step 2: Aggiorna `frontend/app/dashboard/useDashboard.ts`**

```typescript
'use client'
import { useState, useEffect } from 'react'
import { apiFetch, ApiError } from '@/lib/api'
import type { MathData, Narratives, Source, ScenarioResponse, User } from '@/lib/types'

type Plan = 'free' | 'pro'

type DashboardState =
  | { status: 'loading' }
  | { status: 'math_ready'; mathData: MathData; plan: Plan }
  | { status: 'narrative_ready'; mathData: MathData; narratives: Narratives; sources: Source[] | null; plan: Plan }
  | { status: 'error'; message: string }

export function useDashboard(): DashboardState {
  const [state, setState] = useState<DashboardState>({ status: 'loading' })

  useEffect(() => {
    let stopped = false

    async function run() {
      try {
        const [user, generated] = await Promise.all([
          apiFetch<User>('/auth/me'),
          apiFetch<ScenarioResponse>('/scenarios/generate', { method: 'POST' }),
        ])
        if (stopped) return
        setState({ status: 'math_ready', mathData: generated.math_data, plan: user.plan })

        while (!stopped) {
          await new Promise(r => setTimeout(r, 2000))
          if (stopped) break
          const latest = await apiFetch<ScenarioResponse>('/scenarios/me')
          if (latest.narrative_ready && latest.narratives) {
            setState({
              status: 'narrative_ready',
              mathData: latest.math_data,
              narratives: latest.narratives,
              sources: latest.sources,
              plan: user.plan,
            })
            return
          }
        }
      } catch (err) {
        if (!stopped) {
          setState({
            status: 'error',
            message: err instanceof ApiError ? err.message : 'Errore di rete',
          })
        }
      }
    }

    run()
    return () => { stopped = true }
  }, [])

  return state
}
```

- [ ] **Step 3: Crea `frontend/app/dashboard/PaywallGate.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { apiFetch } from '@/lib/api'

interface PaywallGateProps {
  label: string
  rate: string
  risk: string
  color: string
  relativeValue: string
}

export function PaywallGate({ label, rate, risk, color, relativeValue }: PaywallGateProps) {
  return (
    <div className="scenario-card scenario-card--locked" style={{ borderTopColor: color }}>
      <div className="scenario-label">{label} · {rate}</div>
      <div className="scenario-value scenario-value--blurred">€ ••••••</div>
      <div className="scenario-risk">Rischio: {risk}</div>
      <div className="paywall-teaser" style={{ color }}>{relativeValue} vs Sicuro</div>
      <span className="paywall-pill">🔒 Pro</span>
    </div>
  )
}

export function PaywallBanner() {
  const [loading, setLoading] = useState(false)

  async function handleUpgrade() {
    setLoading(true)
    try {
      const { checkout_url } = await apiFetch<{ checkout_url: string }>('/billing/checkout', {
        method: 'POST',
      })
      window.location.href = checkout_url
    } catch {
      setLoading(false)
    }
  }

  return (
    <div className="paywall-banner">
      <p>
        Sblocca tutti gli scenari con <strong>Clara Pro</strong> — 8 €/mese
      </p>
      <button className="btn-primary" onClick={handleUpgrade} disabled={loading}>
        {loading ? 'Caricamento...' : 'Passa a Pro'}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Aggiorna `frontend/app/dashboard/ScenarioCards.tsx`**

```tsx
'use client'
import type { MathData } from '@/lib/types'
import { PaywallGate } from './PaywallGate'

const SCENARIOS = [
  { key: 'sicuro' as const, label: 'Sicuro', rate: '3.5%', risk: 'Basso', color: '#86efac' },
  { key: 'bilanciato' as const, label: 'Bilanciato', rate: '5%', risk: 'Medio', color: '#4ade80' },
  { key: 'crescita' as const, label: 'Crescita', rate: '7%', risk: 'Alto', color: '#059669' },
] as const

function formatEur(value: number): string {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

function relativePercent(value: number, base: number): string {
  return `+${Math.round((value / base - 1) * 100)}%`
}

interface Props {
  mathData: MathData
  plan: 'free' | 'pro'
}

export function ScenarioCards({ mathData, plan }: Props) {
  const sicuroFinal = mathData.sicuro[mathData.sicuro.length - 1]

  return (
    <div className="scenario-cards">
      {SCENARIOS.map(({ key, label, rate, risk, color }) => {
        const finalValue = mathData[key][mathData[key].length - 1]
        const isLocked = plan === 'free' && key !== 'sicuro'

        if (isLocked) {
          return (
            <PaywallGate
              key={key}
              label={label}
              rate={rate}
              risk={risk}
              color={color}
              relativeValue={relativePercent(finalValue, sicuroFinal)}
            />
          )
        }

        return (
          <div key={key} className="scenario-card" style={{ borderTopColor: color }}>
            <div className="scenario-label">{label} · {rate}</div>
            <div className="scenario-value">{formatEur(finalValue)}</div>
            <div className="scenario-risk">Rischio: {risk}</div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 5: Aggiorna `frontend/app/dashboard/page.tsx`**

```tsx
'use client'
import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import dynamic from 'next/dynamic'
import { useDashboard } from './useDashboard'
import { ScenarioCards } from './ScenarioCards'
import { NarrativeSection } from './NarrativeSection'
import { SourcesSection } from './SourcesSection'
import { PaywallBanner } from './PaywallGate'

const ScenarioChart = dynamic(
  () => import('./ScenarioChart').then(m => ({ default: m.ScenarioChart })),
  { ssr: false }
)

function UpgradeBanner() {
  const params = useSearchParams()
  if (params.get('upgrade') !== 'success') return null
  return <div className="upgrade-banner">Benvenuto in Clara Pro! 🎉</div>
}

export default function DashboardPage() {
  const state = useDashboard()

  if (state.status === 'loading') {
    return <main className="loading">Calcolo scenari in corso...</main>
  }

  if (state.status === 'error') {
    return (
      <main className="dashboard-layout">
        <p className="api-error">{state.message}</p>
      </main>
    )
  }

  const mathData = state.mathData
  const plan = state.plan
  const narratives = state.status === 'narrative_ready' ? state.narratives : null
  const sources = state.status === 'narrative_ready' ? state.sources : null
  const ready = state.status === 'narrative_ready'

  return (
    <main className="dashboard-layout">
      <Suspense>
        <UpgradeBanner />
      </Suspense>
      <h1>I tuoi scenari</h1>
      <ScenarioCards mathData={mathData} plan={plan} />
      <ScenarioChart mathData={mathData} />
      <NarrativeSection narratives={narratives} ready={ready} />
      <SourcesSection sources={sources} />
      {plan === 'free' && <PaywallBanner />}
    </main>
  )
}
```

- [ ] **Step 6: Verifica che il frontend compili senza errori TypeScript**

```bash
cd /Users/maiesel/Obsidian/clara-money/frontend
npx tsc --noEmit
```

Expected: nessun errore TypeScript.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/types.ts frontend/app/dashboard/
git commit -m "feat: paywall gate — plan state in useDashboard, PaywallGate component, ScenarioCards gated"
```

---

### Task 6: Frontend — password reset pages

**Files:**
- Modify: `frontend/app/auth/page.tsx`
- Create: `frontend/app/auth/forgot-password/page.tsx`
- Create: `frontend/app/reset-password/page.tsx`

- [ ] **Step 1: Aggiungi link "Password dimenticata?" a `frontend/app/auth/page.tsx`**

Aggiungi dopo il `<button type="submit">`, prima di `</form>`:

```tsx
          {mode === 'login' && (
            <a href="/auth/forgot-password" className="forgot-link">
              Password dimenticata?
            </a>
          )}
```

La forma finale di `auth/page.tsx`:

```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, ApiError } from '@/lib/api'

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'register' | 'login'>('register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiFetch(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      router.replace('/onboarding')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? 'Email già registrata — accedi.' : err.message)
      } else {
        setError('Errore di rete, riprova.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-icon">C</span>
          <h1>Clara</h1>
        </div>
        <p className="auth-subtitle">
          {mode === 'register' ? 'Scopri cosa fare con i tuoi risparmi.' : 'Bentornato.'}
        </p>
        <div className="auth-tabs">
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            Registrati
          </button>
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            Accedi
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password (min. 8 caratteri)" value={password}
            onChange={e => setPassword(e.target.value)} required />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Caricamento...' : mode === 'register' ? 'Inizia gratis' : 'Accedi'}
          </button>
          {mode === 'login' && (
            <a href="/auth/forgot-password" className="forgot-link">
              Password dimenticata?
            </a>
          )}
        </form>
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Crea `frontend/app/auth/forgot-password/page.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore di rete')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <main className="auth-layout">
        <div className="auth-card">
          <p>Controlla la tua email — ti abbiamo inviato un link di reset.</p>
          <a href="/auth">Torna al login</a>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <h1>Reimposta password</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Invio...' : 'Invia link di reset'}
          </button>
        </form>
        <a href="/auth">Torna al login</a>
      </div>
    </main>
  )
}
```

- [ ] **Step 3: Crea `frontend/app/reset-password/page.tsx`**

`useSearchParams` in Next.js App Router richiede Suspense. Il pattern: componente interno usa il hook, pagina esterna lo wrappa.

```tsx
'use client'
import { useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { apiFetch, ApiError } from '@/lib/api'

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      router.replace('/auth?reset=success')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Errore di rete')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <main className="auth-layout">
        <div className="auth-card">
          <p className="form-error">
            Link non valido.{' '}
            <a href="/auth/forgot-password">Richiedi un nuovo link.</a>
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <h1>Nuova password</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Nuova password (min. 8 caratteri)"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Salvataggio...' : 'Salva nuova password'}
          </button>
        </form>
      </div>
    </main>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordContent />
    </Suspense>
  )
}
```

- [ ] **Step 4: Verifica che il frontend compili senza errori**

```bash
cd /Users/maiesel/Obsidian/clara-money/frontend
npx tsc --noEmit
```

Expected: nessun errore TypeScript.

- [ ] **Step 5: Esegui la suite backend completa (sanity check finale)**

```bash
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/ -v
```

Expected: tutti i test passano.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/auth/ frontend/app/reset-password/
git commit -m "feat: password reset pages — forgot-password form + reset-password with token"
```

---

## Verifica finale

Dopo tutti i task:

```bash
# Backend: tutti i test passano
cd /Users/maiesel/Obsidian/clara-money/backend
source .venv/bin/activate && pytest tests/ -v

# Frontend: nessun errore TypeScript
cd /Users/maiesel/Obsidian/clara-money/frontend
npx tsc --noEmit
```

**Smoke test manuale (con dev server):**
1. Registra nuovo utente → `/auth` → inizia gratis
2. Completa onboarding → dashboard
3. Verifica: scenario Sicuro visibile, Bilanciato/Crescita con `🔒 Pro` e percentuale relativa
4. Verifica banner "Passa a Pro" in fondo alla dashboard
5. Click "Passa a Pro" → redirect a Stripe (in test mode se `STRIPE_SECRET_KEY` è una chiave test)
6. Login → click "Password dimenticata?" → form email → submit → messaggio conferma
7. (Se RESEND_API_KEY configurato) verifica email ricevuta con link reset

**Variabili d'ambiente necessarie per smoke test completo** (aggiungere in `backend/.env`):
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
RESEND_API_KEY=re_...
```
