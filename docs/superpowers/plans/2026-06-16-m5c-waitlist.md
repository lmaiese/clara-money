# M5c — Waitlist Beta Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sostituire la homepage scaffold con una landing page completa (hero + feature + how it works + pricing + form waitlist) e aggiungere backend per raccogliere email waitlist.

**Architecture:** Nuova tabella `waitlist` nel DB + router FastAPI `POST /waitlist` (pubblico) e `GET /admin/waitlist` (protetto con `digest_secret`). Frontend: `page.tsx` rimpiazzato con landing page React, stili aggiunti a `globals.css`. Il form usa `apiFetch` già presente in `lib/api.ts`. Nessuna email di conferma.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js 14 App Router + TypeScript (frontend), PostgreSQL, pytest, CSS custom properties (no Tailwind).

---

## File Structure

| File | Azione |
|------|--------|
| `backend/app/models.py` | Aggiunge class `Waitlist` |
| `backend/app/waitlist/__init__.py` | Crea — package vuoto |
| `backend/app/waitlist/router.py` | Crea — `POST /waitlist` + `GET /admin/waitlist` |
| `backend/app/main.py` | Monta `waitlist_router` |
| `backend/tests/test_waitlist.py` | Crea — 5 test integrazione |
| `frontend/app/globals.css` | Aggiunge stili landing page |
| `frontend/app/page.tsx` | Rimpiazza scaffold con landing page |

---

## Task 1: Waitlist model

**Files:**
- Modify: `backend/app/models.py`

Il file usa `Mapped`, `mapped_column`, `DateTime(timezone=True)`, `String`, `text("gen_random_uuid()")` — stesso pattern degli altri model. La tabella deve avere `UNIQUE` constraint sull'email.

- [ ] **Step 1: Aggiungere il model `Waitlist` in `backend/app/models.py`**

Aggiungere dopo il model `Document` (riga 71+):

```python
class Waitlist(Base):
    __tablename__ = "waitlist"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 2: Verificare che i test esistenti passino ancora (nessuna regressione)**

```bash
cd backend && python -m pytest tests/ -x -q
```

Expected: tutti i test passano (la tabella viene creata automaticamente da `Base.metadata.create_all` nel conftest).

- [ ] **Step 3: Commit**

```bash
git add backend/app/models.py
git commit -m "feat: add Waitlist model"
```

---

## Task 2: Backend endpoints + tests (TDD)

**Files:**
- Create: `backend/app/waitlist/__init__.py`
- Create: `backend/app/waitlist/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_waitlist.py`

**Contesto critico:**
- `_verify_secret` è definita in `backend/app/admin/router.py` — importarla da lì, non duplicarla
- Il conftest usa transazione rollback: ogni test riparte da DB pulito automaticamente
- `digest_settings` è definita in `test_digest.py` ma NON in conftest — definirla anche in `test_waitlist.py` (nominata `admin_secret` per evitare conflitti di scope)
- `AUTH = {"Authorization": "Bearer testsecret"}` — header per i test admin
- Email normalizzate a `.lower()` in tutti gli endpoint auth — fare lo stesso in `POST /waitlist`

- [ ] **Step 1: Scrivere i test RED in `backend/tests/test_waitlist.py`**

```python
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


def test_get_waitlist_returns_list(client, db, admin_secret):
    client.post("/waitlist", json={"email": "a@example.com"})
    client.post("/waitlist", json={"email": "b@example.com"})
    resp = client.get("/admin/waitlist", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert "a@example.com" in data["emails"]
    assert "b@example.com" in data["emails"]
```

- [ ] **Step 2: Eseguire i test per verificare che siano RED**

```bash
cd backend && python -m pytest tests/test_waitlist.py -v
```

Expected: `ERROR` o `FAILED` — `No route found for POST /waitlist` o `ImportError`.

- [ ] **Step 3: Creare il package `backend/app/waitlist/__init__.py`**

File vuoto:

```python
```

- [ ] **Step 4: Creare `backend/app/waitlist/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.admin.router import _verify_secret
from app.database import get_db
from app.models import Waitlist

router = APIRouter()


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("/waitlist")
def join_waitlist(body: WaitlistRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    existing = db.query(Waitlist).filter_by(email=email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email già in lista")
    db.add(Waitlist(email=email))
    db.commit()
    return {"message": "Iscritto con successo"}


@router.get("/admin/waitlist")
def get_waitlist(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    entries = db.query(Waitlist).order_by(Waitlist.joined_at.desc()).all()
    return {"count": len(entries), "emails": [e.email for e in entries]}
```

- [ ] **Step 5: Montare il router in `backend/app/main.py`**

Aggiungere dopo la riga `from app.admin.router import router as admin_router` (riga 10):

```python
from app.waitlist.router import router as waitlist_router
```

Aggiungere dopo `app.include_router(admin_router, tags=["admin"])` (riga 38):

```python
app.include_router(waitlist_router, tags=["waitlist"])
```

- [ ] **Step 6: Eseguire i test per verificare che siano GREEN**

```bash
cd backend && python -m pytest tests/test_waitlist.py -v
```

Expected:
```
tests/test_waitlist.py::test_join_waitlist_success PASSED
tests/test_waitlist.py::test_join_waitlist_duplicate PASSED
tests/test_waitlist.py::test_join_waitlist_invalid_email PASSED
tests/test_waitlist.py::test_get_waitlist_unauthorized PASSED
tests/test_waitlist.py::test_get_waitlist_returns_list PASSED
5 passed
```

- [ ] **Step 7: Eseguire la suite completa per verificare nessuna regressione**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: tutti i test precedenti passano ancora (54+ passed).

- [ ] **Step 8: Commit**

```bash
git add backend/app/waitlist/ backend/app/main.py backend/tests/test_waitlist.py
git commit -m "feat: waitlist endpoints — POST /waitlist + GET /admin/waitlist"
```

---

## Task 3: Frontend landing page

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/page.tsx`

**Contesto critico:**
- `globals.css` ha già una regola `form { display: flex; flex-direction: column; gap: 12px; }` — la landing usa form orizzontali, quindi usa classe `.waitlist-form { flex-direction: row; }` (specificità classe > tag, sovrascrive correttamente)
- `.brand` e `.brand-icon` esistono già in globals.css (usate dalla auth page) — riusarle, non ridefinirle
- `apiFetch` e `ApiError` sono in `@/lib/api` — importarli per il submit del form
- La landing è `'use client'` perché usa `useState`
- I due form (hero + bottom CTA) hanno stato React **indipendente** — estrarre componente `WaitlistForm` con prop `variant: 'hero' | 'bottom'`
- La metadata del layout (`app/layout.tsx`) va aggiornata: title e description

- [ ] **Step 1: Aggiornare `frontend/app/layout.tsx` — metadata**

Sostituire il blocco `metadata`:

```typescript
export const metadata: Metadata = {
  title: "Clara — Piano finanziario AI",
  description: "Scopri cosa fare con i tuoi risparmi. 3 scenari matematici personalizzati, narrativa AI, normativa italiana.",
};
```

- [ ] **Step 2: Aggiungere gli stili landing page in `frontend/app/globals.css`**

Aggiungere in fondo al file:

```css
/* ── Landing ── */
.landing-nav { display: flex; align-items: center; justify-content: space-between;
  padding: 16px 40px; background: var(--surface); border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10; }
.brand-name { font-size: 18px; font-weight: 700; }
.nav-login { color: var(--text-muted); font-size: 14px; text-decoration: none;
  padding: 8px 16px; border: 1px solid var(--border); border-radius: var(--radius); }
.nav-login:hover { border-color: var(--accent); color: var(--accent); }

.landing-hero { text-align: center; padding: 72px 40px 56px;
  background: linear-gradient(180deg, var(--accent-light) 0%, var(--bg) 100%); }
.hero-badge { display: inline-block; background: var(--accent-light); color: var(--accent);
  font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px;
  margin-bottom: 20px; letter-spacing: 0.5px; }
.landing-hero h1 { font-size: 42px; font-weight: 800; line-height: 1.15; margin-bottom: 16px;
  max-width: 640px; margin-left: auto; margin-right: auto; }
.hero-accent { color: var(--accent); }
.hero-sub { font-size: 18px; color: var(--text-muted); max-width: 480px;
  margin: 0 auto 32px; line-height: 1.6; }
.hero-note { font-size: 12px; color: var(--text-muted); margin-top: 12px; }

.waitlist-form { display: flex; flex-direction: row; gap: 10px;
  max-width: 420px; margin: 0 auto; }
.waitlist-form input { flex: 1; border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px; font-size: 14px; outline: none; background: var(--surface); }
.waitlist-form input:focus { border-color: var(--accent); }
.waitlist-success { text-align: center; color: var(--accent); font-weight: 600; font-size: 15px; padding: 12px; }
.waitlist-success--bottom { color: #fff; }
.waitlist-form-error { color: var(--error); font-size: 13px; text-align: center; margin-top: 4px; }

.landing-section { padding: 56px 40px; }
.landing-section--alt { background: var(--surface); }
.landing-section-title { text-align: center; font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.landing-section-sub { text-align: center; color: var(--text-muted); font-size: 15px; margin-bottom: 40px; }

.feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
  max-width: 860px; margin: 0 auto; }
.feature-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 28px 24px; }
.feature-icon { width: 40px; height: 40px; border-radius: 10px; background: var(--accent-light);
  color: var(--accent); font-weight: 800; font-size: 14px;
  display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.feature-card h3 { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
.feature-card p { font-size: 14px; color: var(--text-muted); line-height: 1.6; }

.steps-grid { display: flex; max-width: 720px; margin: 0 auto; }
.how-step { flex: 1; text-align: center; padding: 0 24px; position: relative; }
.how-step:not(:last-child)::after { content: '→'; position: absolute; right: -8px; top: 14px;
  color: var(--border); font-size: 20px; }
.step-num { width: 36px; height: 36px; border-radius: 50%; background: var(--accent-light);
  color: var(--accent); font-weight: 700; font-size: 15px;
  display: flex; align-items: center; justify-content: center; margin: 0 auto 14px; }
.how-step h3 { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.how-step p { font-size: 13px; color: var(--text-muted); line-height: 1.5; }

.pricing-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
  max-width: 600px; margin: 0 auto; }
.plan-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 28px 24px; position: relative; }
.plan-card--pro { border-color: var(--accent); }
.plan-badge { position: absolute; top: 12px; right: 12px; background: var(--accent);
  color: #fff; font-size: 10px; font-weight: 700; padding: 2px 8px;
  border-radius: 10px; letter-spacing: 0.5px; }
.plan-name { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px;
  text-transform: uppercase; letter-spacing: 0.5px; }
.plan-price { font-size: 32px; font-weight: 800; margin-bottom: 4px; }
.plan-price span { font-size: 14px; font-weight: 400; color: var(--text-muted); }
.plan-features { list-style: none; margin-top: 20px; display: flex; flex-direction: column; gap: 10px; }
.plan-features li { font-size: 13px; color: var(--text-muted); display: flex; gap: 8px; }
.plan-features li::before { content: '✓'; color: var(--accent); font-weight: 700; flex-shrink: 0; }

.landing-cta { background: linear-gradient(135deg, #064e3b 0%, #059669 100%);
  color: white; text-align: center; padding: 72px 40px; }
.landing-cta h2 { font-size: 30px; font-weight: 800; margin-bottom: 12px; }
.landing-cta > p { font-size: 16px; opacity: 0.85; margin-bottom: 32px;
  max-width: 440px; margin-left: auto; margin-right: auto; }
.waitlist-form--bottom input { background: white; border-color: white; }
.btn-white { background: white; color: var(--accent); font-weight: 700; font-size: 14px;
  padding: 12px 20px; border: none; border-radius: var(--radius); cursor: pointer; white-space: nowrap; }

.landing-footer { padding: 24px 40px; text-align: center; font-size: 12px;
  color: var(--text-muted); border-top: 1px solid var(--border); }
.landing-footer a { color: inherit; }
```

- [ ] **Step 3: Sostituire `frontend/app/page.tsx` con la landing page**

```typescript
'use client'
import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/api'

function WaitlistForm({ variant }: { variant: 'hero' | 'bottom' }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'duplicate' | 'error'>('idle')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('loading')
    try {
      await apiFetch('/waitlist', { method: 'POST', body: JSON.stringify({ email }) })
      setStatus('success')
    } catch (err) {
      setStatus(err instanceof ApiError && err.status === 409 ? 'duplicate' : 'error')
    }
  }

  if (status === 'success') {
    return (
      <p className={`waitlist-success${variant === 'bottom' ? ' waitlist-success--bottom' : ''}`}>
        Sei in lista. Ti avvisiamo presto.
      </p>
    )
  }

  return (
    <div>
      <form className={`waitlist-form waitlist-form--${variant}`} onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="La tua email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <button
          type="submit"
          className={variant === 'hero' ? 'btn-primary' : 'btn-white'}
          disabled={status === 'loading'}
        >
          {status === 'loading' ? 'Caricamento...' : 'Iscriviti'}
        </button>
      </form>
      {status === 'duplicate' && <p className="waitlist-form-error">Email già registrata.</p>}
      {status === 'error' && <p className="waitlist-form-error">Errore di rete, riprova.</p>}
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      <nav className="landing-nav">
        <div className="brand">
          <span className="brand-icon">C</span>
          <span className="brand-name">Clara</span>
        </div>
        <a href="/auth" className="nav-login">Hai già un account? Accedi →</a>
      </nav>

      <section className="landing-hero">
        <span className="hero-badge">Beta in arrivo</span>
        <h1>I tuoi risparmi meritano un <span className="hero-accent">piano vero</span></h1>
        <p className="hero-sub">
          Clara analizza la tua situazione e mostra matematicamente cosa succede
          ai tuoi soldi in 3 scenari alternativi.
        </p>
        <WaitlistForm variant="hero" />
        <p className="hero-note">Gratis. Senza carta di credito. Ti avvisiamo quando apriamo.</p>
      </section>

      <section className="landing-section">
        <h2 className="landing-section-title">Perché Clara</h2>
        <p className="landing-section-sub">Niente consulenti bancari. Niente prodotti da vendere. Solo matematica.</p>
        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">3S</div>
            <h3>3 scenari reali</h3>
            <p>Sicuro, bilanciato, crescita — con rendimenti storici documentati, anno per anno fino al tuo orizzonte.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">AI</div>
            <h3>Narrativa AI</h3>
            <p>Claude (Anthropic) spiega ogni scenario in italiano semplice, adattato alla tua età e ai tuoi obiettivi.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">1°</div>
            <h3>Aggiornamento mensile</h3>
            <p>Ogni mese ricevi un digest con i tuoi scenari aggiornati e il delta rispetto al mese precedente.</p>
          </div>
        </div>
      </section>

      <section className="landing-section landing-section--alt">
        <h2 className="landing-section-title">Come funziona</h2>
        <p className="landing-section-sub">5 minuti per avere il tuo piano finanziario</p>
        <div className="steps-grid">
          <div className="how-step">
            <div className="step-num">1</div>
            <h3>Racconti la tua situazione</h3>
            <p>Reddito, spese, risparmi, orizzonte. 5 domande, niente di personale.</p>
          </div>
          <div className="how-step">
            <div className="step-num">2</div>
            <h3>Clara calcola i tuoi scenari</h3>
            <p>Matematica compound mensile su 3 strategie: liquidità, obbligazionario, azionario.</p>
          </div>
          <div className="how-step">
            <div className="step-num">3</div>
            <h3>Capisci davvero</h3>
            <p>Grafici chiari, narrativa AI, normativa italiana aggiornata inclusa.</p>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <h2 className="landing-section-title">Prezzi</h2>
        <p className="landing-section-sub">Inizia gratis, passa a Pro quando sei pronto</p>
        <div className="pricing-grid">
          <div className="plan-card">
            <div className="plan-name">Free</div>
            <div className="plan-price">€0 <span>/ sempre</span></div>
            <ul className="plan-features">
              <li>Scenario Sicuro (liquidità)</li>
              <li>Onboarding 5 domande</li>
              <li>Dashboard con grafico</li>
            </ul>
          </div>
          <div className="plan-card plan-card--pro">
            <div className="plan-badge">PRO</div>
            <div className="plan-name">Pro</div>
            <div className="plan-price">€8 <span>/ mese</span></div>
            <ul className="plan-features">
              <li>Tutti e 3 gli scenari</li>
              <li>Digest mensile con delta</li>
              <li>Narrativa AI personalizzata</li>
              <li>Normativa italiana (RAG)</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="landing-cta">
        <h2>Unisciti alla waitlist</h2>
        <p>Sii tra i primi a scoprire cosa fare con i tuoi risparmi.</p>
        <WaitlistForm variant="bottom" />
      </section>

      <footer className="landing-footer">
        <p>© 2026 Clara · <a href="mailto:support@claramoney.it">support@claramoney.it</a> · Solo educazione finanziaria, non consulenza</p>
      </footer>
    </>
  )
}
```

- [ ] **Step 4: Testare manualmente la landing page**

```bash
cd frontend && npm run dev
```

Aprire `http://localhost:3000` e verificare:
- Nav sticky con logo "C" + link "Accedi →"
- Hero con badge "Beta in arrivo", headline, form inline
- Form hero: inserire email valida → messaggio "Sei in lista. Ti avvisiamo presto."
- Form hero: reinserire stessa email → "Email già registrata."
- Form hero: inserire stringa non-email → form HTML validation blocca l'invio
- 3 feature cards visibili
- Sezione "Come funziona" con 3 step numerati
- Pricing Free vs Pro con bordo verde su Pro
- Bottom CTA con sfondo verde scuro e form ripetuto
- Footer con disclaimer

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/app/globals.css frontend/app/layout.tsx
git commit -m "feat: landing page waitlist — layout C, hero + features + pricing + CTA"
```
