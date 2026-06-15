# Clara Money M4 — Stripe, Freemium Paywall, Password Reset

## Scope

M4 aggiunge tre capability indipendenti:

1. **Stripe Checkout** — piano Pro a 8 €/mese, hosted checkout, webhook upgrade
2. **Freemium paywall** — gate frontend su scenari Bilanciato/Crescita per utenti free
3. **Password reset** — email via Resend + JWT stateless (1 h)

**Fuori scope M4:** Supabase Auth (deferred), gestione cancellazione subscription (M5), Stripe Customer Portal (M5).

---

## Auth: nessuna modifica

Si mantiene il JWT custom con cookie httponly già in produzione. Nessuna migrazione verso Supabase Auth.

---

## Section 1 — Schema DB

Due colonne nuove su `users`:

```sql
ALTER TABLE users ADD COLUMN plan VARCHAR(10) NOT NULL DEFAULT 'free';
ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255);
```

Modello SQLAlchemy (`backend/app/models.py`):

```python
from sqlalchemy import CheckConstraint

class User(Base):
    ...
    plan: Mapped[str] = mapped_column(String(10), nullable=False, default="free", server_default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan"),
    )
```

`stripe_customer_id` nullable — null significa che l'utente non ha mai avviato un checkout. `plan` default `'free'` su tutti gli utenti esistenti tramite `server_default`.

Alembic autogenera la migration da queste modifiche al modello.

---

## Section 2 — Config (`backend/app/config.py`)

Già aggiornato (fix applicato nella sessione di systematic-debugging):

```python
stripe_secret_key: str = ""
stripe_webhook_secret: str = ""
resend_api_key: str = ""
```

`.env` in produzione deve includere tutti e tre. Empty string default evita crash dei test.

---

## Section 3 — Stripe Checkout Flow

### Architettura billing router

`backend/app/billing/router.py` espone **due router separati** per separare autenticazione:

```python
protected_router = APIRouter(prefix="/billing")   # endpoints protetti
webhook_router   = APIRouter(prefix="/billing")   # webhook SOLO — no auth

# In main.py:
app.include_router(protected_router, dependencies=[Depends(get_current_user)])
app.include_router(webhook_router)
```

Motivo: Stripe chiama il webhook senza cookie — `get_current_user` restituirebbe sempre 401.

### POST /billing/checkout (protetto)

```python
import asyncio
import stripe
from app.config import settings

stripe.api_key = settings.stripe_secret_key

@protected_router.post("/checkout")
async def create_checkout(user=Depends(get_current_user)):
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
```

`asyncio.to_thread` evita il blocco dell'event loop sulla chiamata sincrona Stripe.

### POST /billing/webhook (unauthenticated)

```python
@webhook_router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()          # bytes grezzi — PRIMA di qualsiasi parsing
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:   # stripe-python >= 5.0
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

**Regola critica:** `await request.body()` deve essere la prima istruzione. Se FastAPI/middleware consuma il body prima, la firma Stripe non corrisponde e ogni richiesta legittima viene rigettata.

### Flow utente end-to-end

```
[Dashboard] → click "Passa a Pro"
  → POST /billing/checkout
  → risposta: {checkout_url: "https://checkout.stripe.com/..."}
  → frontend: window.location.href = checkout_url

[Stripe Checkout hosted]
  → utente inserisce carta
  → pagamento completato

[Stripe → webhook] POST /billing/webhook
  → verifica firma
  → upgrade user.plan = "pro"
  → return 200

[Redirect] → /dashboard?upgrade=success
  → frontend mostra banner "Benvenuto in Pro!"
```

---

## Section 4 — Freemium Paywall (frontend)

### Principio

Il backend restituisce **sempre** tutti e tre gli scenari. Il gate è puramente presentazionale. Le proiezioni finanziarie non sono dati sensibili — il paywall è friction UX, non security wall. Backend enforcement in M5 se necessario.

### `plan` nel response chain

`UserResponse` schema (già esistente) aggiunge `plan`:

```python
class UserResponse(BaseModel):
    id: str
    email: str
    plan: str = "free"
    model_config = {"from_attributes": True}
```

`GET /auth/me` e login response già restituiscono `UserResponse` — `plan` appare automaticamente.

Frontend (`frontend/app/auth/useAuth.ts` o equivalente): il tipo `User` include `plan: "free" | "pro"`.

### Paywall component

Basato sul design approvato `paywall-v2.html`:

- Scenario Sicuro: visibile completo ✅
- Scenario Bilanciato: valore esatto blurred, teaser colorato `+35%` visibile, pill `🔒 Pro`
- Scenario Crescita: valore esatto blurred, teaser colorato `+83%` visibile, pill `🔒 Pro`
- Banner CTA singolo in fondo: "Sblocca tutti gli scenari" → POST /billing/checkout

`useDashboard` legge `user.plan` dallo store auth. Nessun fetch aggiuntivo.

---

## Section 5 — Password Reset

### Principio

Stateless: JWT firmato con `JWT_SECRET`, payload `{sub: user_id, purpose: "password-reset", exp: now+1h}`. Nessuna tabella `password_reset_tokens`. Il claim `purpose` impedisce riuso di token di sessione normale come token di reset.

### Flow

```
POST /auth/forgot-password  {email: "..."}
  → cerca user per email (query case-insensitive)
  → se trovato: genera JWT reset (1h)
  → invia email Resend:
      subject: "Reimposta la tua password — Clara"
      body: link http://localhost:3000/reset-password?token=<jwt>
  → risponde SEMPRE 200 (non rivela se email esiste)

POST /auth/reset-password  {token: "...", new_password: "..."}
  → decodifica JWT con JWT_SECRET
  → verifica exp non scaduto
  → verifica purpose == "password-reset"
  → bcrypt hash di new_password
  → aggiorna user.password_hash
  → risponde 200
```

### Resend integration

```python
import httpx

async def send_reset_email(to_email: str, reset_link: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": "Clara <noreply@claramoney.it>",
                "to": [to_email],
                "subject": "Reimposta la tua password — Clara",
                "html": f'<p>Clicca qui per reimpostare la password: <a href="{reset_link}">{reset_link}</a></p><p>Il link scade tra 1 ora.</p>',
            },
        )
```

Errori Resend: loggati ma non propagati all'utente (l'endpoint risponde sempre 200).

---

## Section 6 — File Map

| File | Azione | Responsabilità |
|------|--------|----------------|
| `backend/app/models.py` | Modifica | Aggiunge `plan`, `stripe_customer_id` a User |
| `backend/app/schemas.py` | Modifica | `plan` in `UserResponse` |
| `backend/alembic/versions/xxx_m4.py` | Crea | Migration `plan` + `stripe_customer_id` |
| `backend/app/billing/__init__.py` | Crea | Package billing |
| `backend/app/billing/router.py` | Crea | `protected_router` + `webhook_router` |
| `backend/app/auth/router.py` | Modifica | Aggiunge `/forgot-password`, `/reset-password` |
| `backend/app/auth/email.py` | Crea | `send_reset_email()` via Resend |
| `backend/app/main.py` | Modifica | Monta entrambi i billing router |
| `frontend/app/auth/types.ts` (o equiv.) | Modifica | `plan: "free" \| "pro"` in User type |
| `frontend/app/dashboard/PaywallGate.tsx` | Crea | Wrapper paywall per scenari locked |
| `frontend/app/dashboard/page.tsx` | Modifica | Usa `PaywallGate` su bilanciato/crescita |
| `frontend/app/reset-password/page.tsx` | Crea | Form reset password con token da URL |

---

## Section 7 — Testing

Ogni endpoint ha test di integrazione:

- **webhook**: test con firma valida (mock `construct_event`) + firma invalida → 400
- **checkout**: test utente autenticato + utente non autenticato → 401
- **forgot-password**: test email esistente + email non esistente → entrambi 200
- **reset-password**: token valido → 200, token scaduto → 400, purpose errato → 400
- **paywall gate**: test visivo manuale tramite dev server (non automatizzabile facilmente)

---

## Note di produzione

- `stripe.api_key` impostato all'avvio (in `main.py` lifespan o nel modulo billing)
- Webhook endpoint deve essere registrato in Stripe Dashboard con l'URL pubblico del server
- `STRIPE_WEBHOOK_SECRET` si ottiene da Stripe Dashboard → Webhooks → Signing secret
- `RESEND_API_KEY` da Resend Dashboard; il dominio mittente (`claramoney.it`) va verificato in Resend
