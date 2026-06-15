# Clara Money M5c — Waitlist Beta Launch

## Scope

Landing page pubblica che sostituisce lo scaffold default di Next.js, con form raccolta email per la waitlist beta. Backend proprio per storage email. Invite manuale (nessuna automazione).

**Fuori scope M5c:** email di conferma all'utente, automazione invite, test E2E, SVG icons per feature cards (design debt post-MVP).

---

## Architettura

### File da creare/modificare

| File | Azione | Responsabilità |
|------|--------|----------------|
| `backend/app/models.py` | Modifica | Aggiunge model `Waitlist` |
| `backend/app/waitlist/__init__.py` | Crea | Package waitlist |
| `backend/app/waitlist/router.py` | Crea | `POST /waitlist` + `GET /admin/waitlist` |
| `backend/app/main.py` | Modifica | Monta `waitlist_router` |
| `backend/tests/test_waitlist.py` | Crea | 5 test integrazione |
| `frontend/app/page.tsx` | Modifica | Landing page completa (rimpiazza scaffold) |
| `frontend/app/globals.css` | Modifica | Stili landing (aggiunge a quelli esistenti) |

---

## Backend

### Model

```python
class Waitlist(Base):
    __tablename__ = "waitlist"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

### Endpoint: `POST /waitlist`

- **Auth:** unauthenticated (pubblico)
- **Body:** `{"email": "user@example.com"}` — validato da Pydantic `EmailStr`
- **Successo (200):** `{"message": "Iscritto con successo"}`
- **Duplicato (409):** `{"detail": "Email già in lista"}`
- **Email non valida (422):** errore Pydantic automatico

```python
class WaitlistRequest(BaseModel):
    email: EmailStr

@router.post("/waitlist")
def join_waitlist(body: WaitlistRequest, db: Session = Depends(get_db)):
    existing = db.query(Waitlist).filter_by(email=body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email già in lista")
    db.add(Waitlist(email=body.email.lower()))
    db.commit()
    return {"message": "Iscritto con successo"}
```

### Endpoint: `GET /admin/waitlist`

- **Auth:** `Authorization: Bearer <digest_secret>` — stesso meccanismo di `/admin/run-digest` (riusa `_verify_secret` da `admin/router.py`)
- **Risposta (200):** `{"count": N, "emails": ["a@b.com", ...]}`

```python
@router.get("/admin/waitlist")
def get_waitlist(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    entries = db.query(Waitlist).order_by(Waitlist.joined_at.desc()).all()
    return {"count": len(entries), "emails": [e.email for e in entries]}
```

**Nota:** `_verify_secret` è importato da `app.admin.router` — nessuna duplicazione.

### Mount in `main.py`

```python
from app.waitlist.router import router as waitlist_router
app.include_router(waitlist_router, tags=["waitlist"])
```

---

## Frontend

### Layout C — Inline hero + repeat in fondo

**Struttura `app/page.tsx`:**

```
<Nav>        Logo Clara + "Hai già un account? Accedi →"
<Hero>       Badge "Beta in arrivo" + headline + sub + form inline
<Features>   3 card (3S / AI / 1°) — icons da rivedere post-MVP
<HowItWorks> 3 step numerati
<Pricing>    Free vs Pro (€8/mese)
<BottomCTA>  Form waitlist ripetuto su sfondo verde scuro
<Footer>     Copyright + email support + disclaimer legale
```

**Copy:**

- **Headline:** "I tuoi risparmi meritano un piano vero"
- **Sub:** "Clara analizza la tua situazione e mostra matematicamente cosa succede ai tuoi soldi in 3 scenari alternativi."
- **Hero note:** "Gratis. Senza carta di credito. Ti avvisiamo quando apriamo."
- **CTA primario:** "Iscriviti"
- **Nav secondario:** "Hai già un account? Accedi →" → `/auth`
- **Footer disclaimer:** "Solo educazione finanziaria, non consulenza"

**Comportamenti del form:**
- `loading` state: bottone disabilitato con testo "Caricamento..."
- Successo: messaggio inline "Sei in lista. Ti avvisiamo presto." (form nascosto)
- Duplicato (409): messaggio inline "Email già registrata."
- Errore generico: "Errore di rete, riprova."
- I due form (hero + bottom) sono indipendenti, ognuno ha il proprio stato

**CSS:** aggiunto a `globals.css` — stesse custom properties esistenti (`--accent`, `--bg`, ecc.), no Tailwind.

**Design debt (post-MVP):** sostituire le label abbreviate (3S / AI / 1°) delle feature card icon con SVG o illustrazioni.

---

## Testing

File: `backend/tests/test_waitlist.py`

```python
def test_join_waitlist_success(client, db):
    resp = client.post("/waitlist", json={"email": "test@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"message": "Iscritto con successo"}
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

def test_get_waitlist_returns_list(client, db, digest_settings):
    client.post("/waitlist", json={"email": "a@example.com"})
    client.post("/waitlist", json={"email": "b@example.com"})
    resp = client.get("/admin/waitlist", headers={"Authorization": "Bearer testsecret"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert "a@example.com" in data["emails"]
```

**Fixture riusata:** `digest_settings` da `conftest.py` (già presente, setta `digest_secret = "testsecret"`).

---

## Note di produzione

- Nessuna env var nuova richiesta — riusa `digest_secret` per `GET /admin/waitlist`
- Email normalizzate a `.lower()` (stesso pattern di `/auth/register`)
- `joined_at` con `server_default=func.now()` — timezone-aware (stesso pattern di `User.created_at`)
