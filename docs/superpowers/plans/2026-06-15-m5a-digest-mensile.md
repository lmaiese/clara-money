# Clara Money M5a — Digest Mensile Pro — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere un endpoint `POST /admin/run-digest` che, chiamato da Railway Cron il 1° di ogni mese, ricalcola scenari per tutti gli utenti Pro, calcola il delta vs mese precedente, genera narrativa Claude (opzionale), salva nuovo Scenario in DB e invia email digest via Resend.

**Architecture:** Endpoint protetto da Bearer secret (non da cookie auth), job asincrono `run_monthly_digest` separato dal router per testabilità, dedup mensile per idempotenza, rollback per-utente in caso di errore.

**Tech Stack:** FastAPI, SQLAlchemy, httpx (Resend), anthropic SDK (Claude, opzionale), pytest + unittest.mock.

---

## File Map

| File | Azione | Responsabilità |
|------|--------|----------------|
| `backend/app/config.py` | Modifica | Aggiunge `digest_secret: str = ""` |
| `backend/app/admin/__init__.py` | Crea | Package admin (vuoto) |
| `backend/app/admin/digest.py` | Crea | `run_monthly_digest` + `send_digest_email` |
| `backend/app/admin/router.py` | Crea | `POST /admin/run-digest` con auth secret |
| `backend/app/main.py` | Modifica | Monta `admin_router` |
| `backend/tests/test_digest.py` | Crea | 6 test di integrazione |

**Non toccare:** `models.py`, `scenarios/service.py`, `scenarios/math.py`, `auth/email.py`. Vengono solo importati.

---

### Task 1: Config + admin package scaffold

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/admin/__init__.py`
- Create: `backend/app/admin/digest.py` (stub)
- Create: `backend/app/admin/router.py` (stub)

- [ ] **Step 1: Aggiungi `digest_secret` a config.py**

  Apri `backend/app/config.py`. Aggiungi la riga dopo `resend_api_key`:

  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict

  _DEV_JWT_SECRET = "dev-secret-change-in-production"


  class Settings(BaseSettings):
      database_url: str = "postgresql://postgres:postgres@localhost:5433/clara_test"
      jwt_secret: str = _DEV_JWT_SECRET
      jwt_algorithm: str = "HS256"
      jwt_expire_days: int = 7
      anthropic_api_key: str = ""
      openai_api_key: str = ""
      claude_model: str = "claude-sonnet-4-6"
      stripe_secret_key: str = ""
      stripe_webhook_secret: str = ""
      resend_api_key: str = ""
      digest_secret: str = ""
      frontend_url: str = "http://localhost:3000"
      cookie_secure: bool = False
      allowed_origins: list[str] = ["http://localhost:3000"]

      model_config = SettingsConfigDict(env_file=".env")


  settings = Settings()
  JWT_SECRET_IS_DEV_DEFAULT = settings.jwt_secret == _DEV_JWT_SECRET
  ```

- [ ] **Step 2: Crea il package admin**

  ```bash
  mkdir -p backend/app/admin
  touch backend/app/admin/__init__.py
  ```

- [ ] **Step 3: Crea `digest.py` stub**

  Crea `backend/app/admin/digest.py` con i segnature vuote — necessario per permettere import nei task successivi:

  ```python
  from sqlalchemy.orm import Session


  async def send_digest_email(to_email, profile, math_data, delta, narratives) -> None:
      pass


  async def run_monthly_digest(db: Session) -> dict:
      return {"sent": 0, "skipped": 0, "errors": 0}
  ```

- [ ] **Step 4: Crea `router.py` stub**

  Crea `backend/app/admin/router.py`:

  ```python
  from fastapi import APIRouter, Depends, HTTPException, Request
  from sqlalchemy.orm import Session
  from app.config import settings
  from app.database import get_db
  from app.admin.digest import run_monthly_digest

  router = APIRouter(prefix="/admin")


  def _verify_secret(request: Request) -> None:
      if not settings.digest_secret:
          raise HTTPException(status_code=401, detail="Admin endpoint not configured")
      auth = request.headers.get("Authorization", "")
      if not auth.startswith("Bearer ") or auth[len("Bearer "):] != settings.digest_secret:
          raise HTTPException(status_code=401, detail="Unauthorized")


  @router.post("/run-digest")
  async def run_digest(request: Request, db: Session = Depends(get_db)):
      _verify_secret(request)
      result = await run_monthly_digest(db)
      return result
  ```

- [ ] **Step 5: Monta il router in `main.py`**

  Apri `backend/app/main.py`. Aggiungi import e `include_router`:

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
  from app.admin.router import router as admin_router
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
  app.include_router(admin_router, tags=["admin"])
  ```

- [ ] **Step 6: Verifica che l'app si avvii e i test precedenti passino**

  ```bash
  cd backend
  python -m pytest tests/ -q --tb=short
  ```

  Expected: 47 passed (stessi di prima), 1 warning.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/app/config.py backend/app/admin/ backend/app/main.py
  git commit -m "feat: admin package scaffold + digest_secret config + router stub"
  ```

---

### Task 2: Test di autenticazione (TDD)

**Files:**
- Create: `backend/tests/test_digest.py`

- [ ] **Step 1: Scrivi i test di autenticazione**

  Crea `backend/tests/test_digest.py`:

  ```python
  import pytest
  from datetime import datetime, timezone
  from unittest.mock import AsyncMock, MagicMock, patch

  from app.config import settings
  from app.models import Profile, Scenario, User


  AUTH = {"Authorization": "Bearer testsecret"}


  @pytest.fixture
  def digest_settings(monkeypatch):
      """Configura digest_secret e resend_api_key per i test.
      anthropic_api_key rimane "" → narrativa fallback template (nessuna chiamata Claude)."""
      monkeypatch.setattr(settings, "digest_secret", "testsecret")
      monkeypatch.setattr(settings, "resend_api_key", "re_fake")


  @pytest.fixture
  def pro_user_with_profile(client, db):
      """Crea un utente Pro con profilo completo (onboarding_step=5)."""
      client.post("/auth/register", json={"email": "pro@test.com", "password": "password123"})
      user = db.query(User).filter_by(email="pro@test.com").first()
      user.plan = "pro"
      profile = db.get(Profile, user.id)
      profile.onboarding_step = 5
      profile.age = 30
      profile.monthly_income = 2000
      profile.monthly_expenses = 1000
      profile.liquid_savings = 5000
      profile.horizon_years = 10
      profile.goal = "casa"
      profile.existing_investments = 0
      db.commit()
      return user


  def _make_resend_mock():
      """Helper: mock per httpx.AsyncClient usato come context manager async."""
      mock_aclient = MagicMock()
      mock_aclient.__aenter__ = AsyncMock(return_value=mock_aclient)
      mock_aclient.__aexit__ = AsyncMock(return_value=None)
      mock_aclient.post = AsyncMock()
      return mock_aclient


  # ---------------------------------------------------------------------------
  # Auth tests
  # ---------------------------------------------------------------------------

  def test_run_digest_unauthorized(client):
      """Nessun header Authorization → 401."""
      resp = client.post("/admin/run-digest")
      assert resp.status_code == 401


  def test_run_digest_wrong_secret(client, digest_settings):
      """Secret sbagliato → 401."""
      resp = client.post("/admin/run-digest", headers={"Authorization": "Bearer wrong"})
      assert resp.status_code == 401
  ```

- [ ] **Step 2: Esegui i test — devono passare**

  Il router stub risponde già correttamente ai check di auth.

  ```bash
  cd backend
  python -m pytest tests/test_digest.py::test_run_digest_unauthorized tests/test_digest.py::test_run_digest_wrong_secret -v
  ```

  Expected:
  ```
  PASSED tests/test_digest.py::test_run_digest_unauthorized
  PASSED tests/test_digest.py::test_run_digest_wrong_secret
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add backend/tests/test_digest.py
  git commit -m "test: digest auth tests (unauthorized + wrong secret)"
  ```

---

### Task 3: Test job logic (TDD — scrivi prima, poi implementa)

**Files:**
- Modify: `backend/tests/test_digest.py`

- [ ] **Step 1: Aggiungi i 4 test job in `test_digest.py`**

  Aggiungi in fondo al file esistente `backend/tests/test_digest.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Job logic tests
  # ---------------------------------------------------------------------------

  def test_run_digest_skips_free_users(client, db, digest_settings):
      """Utente free con profilo completo → skippato, nessuna email inviata."""
      client.post("/auth/register", json={"email": "free@test.com", "password": "password123"})
      user = db.query(User).filter_by(email="free@test.com").first()
      # plan rimane "free" (default)
      profile = db.get(Profile, user.id)
      profile.onboarding_step = 5
      profile.age = 30
      profile.monthly_income = 2000
      profile.monthly_expenses = 1000
      profile.liquid_savings = 5000
      profile.horizon_years = 10
      profile.goal = "casa"
      profile.existing_investments = 0
      db.commit()

      mock_aclient = _make_resend_mock()
      with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
          resp = client.post("/admin/run-digest", headers=AUTH)

      assert resp.status_code == 200
      assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
      mock_aclient.post.assert_not_called()


  def test_run_digest_pro_user_gets_email(client, db, digest_settings, monkeypatch, pro_user_with_profile):
      """Utente Pro con Scenario precedente → email inviata con delta, nuovo Scenario salvato."""
      monkeypatch.setattr(settings, "anthropic_api_key", "sk-fake")
      user = pro_user_with_profile

      # Scenario precedente con valori noti (horizon=10 anni → lista di 11 valori; usiamo 2 per semplicità,
      # il codice accede solo all'ultimo elemento [-1])
      prev = Scenario(
          user_id=user.id,
          profile_snapshot={
              "age": 30, "monthly_income": 2000, "monthly_expenses": 1000,
              "liquid_savings": 5000, "existing_investments": 0,
              "goal": "casa", "horizon_years": 10,
          },
          math_data={
              "sicuro": [5000.0, 8000.0],
              "bilanciato": [5000.0, 9000.0],
              "crescita": [5000.0, 10000.0],
              "inflazione": [5000.0, 6000.0],
              "labels": [0, 1],
          },
          narrative_ready=True,
      )
      db.add(prev)
      db.commit()

      mock_aclient = _make_resend_mock()
      with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient), \
           patch("app.admin.digest.Anthropic") as mock_claude:
          mock_claude.return_value.messages.create.return_value.content = [
              MagicMock(text='{"intro":"intro","sicuro":"s","bilanciato":"b","crescita":"c"}')
          ]
          resp = client.post("/admin/run-digest", headers=AUTH)

      assert resp.status_code == 200
      assert resp.json()["sent"] == 1
      assert resp.json()["errors"] == 0
      # Nuovo Scenario salvato (2 totali: prev + nuovo)
      assert db.query(Scenario).filter_by(user_id=user.id).count() == 2
      # Email inviata all'indirizzo corretto con delta
      call_json = mock_aclient.post.call_args.kwargs["json"]
      assert user.email in call_json["to"]
      assert "vs mese scorso" in call_json["html"]


  def test_run_digest_no_previous_scenario(client, db, digest_settings, pro_user_with_profile):
      """Primo scenario dell'utente → email inviata senza delta."""
      user = pro_user_with_profile

      mock_aclient = _make_resend_mock()
      with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
          resp = client.post("/admin/run-digest", headers=AUTH)

      assert resp.status_code == 200
      assert resp.json()["sent"] == 1
      call_json = mock_aclient.post.call_args.kwargs["json"]
      assert "vs mese scorso" not in call_json["html"]


  def test_run_digest_dedup_skips_already_sent(client, db, digest_settings, pro_user_with_profile):
      """Scenario già generato questo mese → utente skippato, nessuna email."""
      user = pro_user_with_profile
      now = datetime.now(timezone.utc)

      existing = Scenario(
          user_id=user.id,
          profile_snapshot={
              "age": 30, "monthly_income": 2000, "monthly_expenses": 1000,
              "liquid_savings": 5000, "existing_investments": 0,
              "goal": "casa", "horizon_years": 10,
          },
          math_data={
              "sicuro": [5000.0], "bilanciato": [5000.0], "crescita": [5000.0],
              "inflazione": [5000.0], "labels": [0],
          },
          generated_at=now,
          narrative_ready=True,
      )
      db.add(existing)
      db.commit()

      mock_aclient = _make_resend_mock()
      with patch("app.admin.digest.httpx.AsyncClient", return_value=mock_aclient):
          resp = client.post("/admin/run-digest", headers=AUTH)

      assert resp.status_code == 200
      assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
      mock_aclient.post.assert_not_called()
  ```

- [ ] **Step 2: Esegui i 4 nuovi test — devono fallire**

  ```bash
  cd backend
  python -m pytest tests/test_digest.py -k "not unauthorized and not wrong_secret" -v
  ```

  Expected: tutti e 4 FAILED (lo stub restituisce sempre `{"sent":0,"skipped":0,"errors":0}`).

- [ ] **Step 3: Commit dei test**

  ```bash
  git add backend/tests/test_digest.py
  git commit -m "test: digest job tests (skip free, email pro, no prev, dedup) — RED"
  ```

---

### Task 4: Implementazione `digest.py`

**Files:**
- Modify: `backend/app/admin/digest.py`

- [ ] **Step 1: Sostituisci `digest.py` con l'implementazione completa**

  Riscrivi completamente `backend/app/admin/digest.py`:

  ```python
  import json
  import logging
  from datetime import datetime, timezone
  from types import SimpleNamespace

  import httpx
  from sqlalchemy import extract, select
  from sqlalchemy.orm import Session

  from app.config import settings
  from app.models import Profile, Scenario, User
  from app.scenarios.math import compute_scenarios
  from app.scenarios.service import _build_fallback, _build_prompt, _fmt_eur

  logger = logging.getLogger(__name__)

  MESI = {
      1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
      5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
      9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
  }


  def _delta_str(delta: dict | None, key: str) -> str:
      """Restituisce stringa HTML colorata '+€X.XXX vs mese scorso' o stringa vuota."""
      if delta is None:
          return ""
      val = delta[key]
      sign = "+" if val >= 0 else "-"
      color = "#16a34a" if val >= 0 else "#dc2626"
      return (
          f' <span style="color:{color}">({sign}€{_fmt_eur(abs(val))} vs mese scorso)</span>'
      )


  async def send_digest_email(
      to_email: str,
      profile: SimpleNamespace,
      math_data: dict,
      delta: dict | None,
      narratives: dict,
  ) -> None:
      if not settings.resend_api_key:
          logger.warning("RESEND_API_KEY not set — skipping digest email for %s", to_email)
          return

      now = datetime.now(timezone.utc)
      subject = f"Il tuo aggiornamento mensile Clara — {MESI[now.month]} {now.year}"

      html = f"""<p>Ciao {to_email},</p>
  <p>Il tuo piano finanziario aggiornato per <strong>{profile.horizon_years} anni</strong>.</p>
  <table cellpadding="8">
    <tr>
      <td><strong>Scenario Sicuro</strong></td>
      <td>€{_fmt_eur(math_data["sicuro"][-1])}{_delta_str(delta, "sicuro")}</td>
    </tr>
    <tr>
      <td><strong>Scenario Bilanciato</strong></td>
      <td>€{_fmt_eur(math_data["bilanciato"][-1])}{_delta_str(delta, "bilanciato")}</td>
    </tr>
    <tr>
      <td><strong>Scenario Crescita</strong></td>
      <td>€{_fmt_eur(math_data["crescita"][-1])}{_delta_str(delta, "crescita")}</td>
    </tr>
  </table>
  <p>{narratives["intro"]}</p>
  <p><strong>Sicuro:</strong> {narratives["sicuro"]}</p>
  <p><strong>Bilanciato:</strong> {narratives["bilanciato"]}</p>
  <p><strong>Crescita:</strong> {narratives["crescita"]}</p>
  <hr>
  <p style="font-size:12px;color:#6b7280">Clara · Problemi? Scrivi a
  <a href="mailto:support@claramoney.it">support@claramoney.it</a></p>"""

      try:
          async with httpx.AsyncClient() as http:
              await http.post(
                  "https://api.resend.com/emails",
                  headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                  json={
                      "from": "Clara <noreply@claramoney.it>",
                      "to": [to_email],
                      "subject": subject,
                      "html": html,
                  },
              )
      except Exception:
          logger.exception("Failed to send digest email to %s", to_email)


  async def run_monthly_digest(db: Session) -> dict:
      sent = skipped = errors = 0
      now = datetime.now(timezone.utc)

      users = db.execute(
          select(User).join(Profile).where(User.plan == "pro")
      ).scalars().all()

      for user in users:
          email = user.email
          user_id = user.id
          profile = db.get(Profile, user_id)

          try:
              # 1. Profilo completo
              if not profile or profile.onboarding_step < 5 or not profile.horizon_years:
                  skipped += 1
                  continue

              # 2. Dedup: skip se già inviato questo mese
              existing = db.execute(
                  select(Scenario)
                  .where(Scenario.user_id == user_id)
                  .where(extract("year", Scenario.generated_at) == now.year)
                  .where(extract("month", Scenario.generated_at) == now.month)
              ).scalar_one_or_none()
              if existing:
                  skipped += 1
                  continue

              # 3. Ultimo scenario per calcolare delta
              prev_scenario = db.execute(
                  select(Scenario)
                  .where(Scenario.user_id == user_id)
                  .order_by(Scenario.generated_at.desc())
                  .limit(1)
              ).scalar_one_or_none()

              # 4. Ricalcola scenari
              capital = float(profile.liquid_savings or 0)
              monthly_pmt = max(
                  0.0,
                  float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)),
              )
              math_data = compute_scenarios(capital, monthly_pmt, profile.horizon_years)

              # 5. Delta (None se primo scenario)
              delta = None
              if prev_scenario and prev_scenario.math_data:
                  prev = prev_scenario.math_data
                  delta = {
                      k: math_data[k][-1] - prev[k][-1]
                      for k in ["sicuro", "bilanciato", "crescita"]
                  }

              # 6. Narrativa Claude (timeout 30s) o fallback template
              profile_ns = SimpleNamespace(
                  age=profile.age,
                  monthly_income=profile.monthly_income,
                  monthly_expenses=profile.monthly_expenses,
                  liquid_savings=profile.liquid_savings,
                  existing_investments=profile.existing_investments,
                  goal=profile.goal,
                  horizon_years=profile.horizon_years,
              )
              narratives = None
              if settings.anthropic_api_key:
                  try:
                      from anthropic import Anthropic
                      ai = Anthropic(api_key=settings.anthropic_api_key)
                      response = ai.messages.create(
                          model=settings.claude_model,
                          max_tokens=1024,
                          timeout=30,
                          messages=[{"role": "user", "content": _build_prompt(profile_ns, math_data)}],
                      )
                      parsed = json.loads(response.content[0].text)
                      if {"intro", "sicuro", "bilanciato", "crescita"}.issubset(parsed.keys()):
                          narratives = parsed
                  except Exception:
                      logger.exception("Claude failed for user %s, using fallback", user_id)
              if narratives is None:
                  narratives = _build_fallback(profile_ns, math_data)

              # 7. Salva nuovo Scenario (profile_snapshot obbligatorio — NOT NULL)
              profile_snapshot = {
                  "age": profile.age,
                  "monthly_income": profile.monthly_income,
                  "monthly_expenses": profile.monthly_expenses,
                  "liquid_savings": profile.liquid_savings,
                  "existing_investments": profile.existing_investments,
                  "goal": profile.goal,
                  "horizon_years": profile.horizon_years,
              }
              scenario = Scenario(
                  user_id=user_id,
                  profile_snapshot=profile_snapshot,
                  math_data=math_data,
                  narratives=narratives,
                  narrative_ready=True,
              )
              db.add(scenario)
              db.commit()

              # 8. Email dopo commit — se fallisce, scenario è già persistito
              await send_digest_email(email, profile_ns, math_data, delta, narratives)
              sent += 1

          except Exception:
              logger.exception("Digest failed for user %s", user_id)
              db.rollback()
              errors += 1

      return {"sent": sent, "skipped": skipped, "errors": errors}
  ```

- [ ] **Step 2: Esegui tutti i test digest**

  ```bash
  cd backend
  python -m pytest tests/test_digest.py -v
  ```

  Expected:
  ```
  PASSED tests/test_digest.py::test_run_digest_unauthorized
  PASSED tests/test_digest.py::test_run_digest_wrong_secret
  PASSED tests/test_digest.py::test_run_digest_skips_free_users
  PASSED tests/test_digest.py::test_run_digest_pro_user_gets_email
  PASSED tests/test_digest.py::test_run_digest_no_previous_scenario
  PASSED tests/test_digest.py::test_run_digest_dedup_skips_already_sent
  6 passed
  ```

  Se un test fallisce:
  - `test_run_digest_pro_user_gets_email` fallisce su `"vs mese scorso" in html`: verifica che `_delta_str` venga chiamata con `delta != None` e che il prev_scenario abbia `math_data` con chiavi `sicuro/bilanciato/crescita`.
  - `test_run_digest_dedup_skips_already_sent` fallisce: verifica che il `generated_at` dello Scenario creato nel test sia nel mese corrente (usa `datetime.now(timezone.utc)`).

- [ ] **Step 3: Esegui la suite completa**

  ```bash
  cd backend
  python -m pytest tests/ -q --tb=short
  ```

  Expected: 53 passed (47 precedenti + 6 nuovi), 1 warning.

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/admin/digest.py
  git commit -m "feat: digest.py — run_monthly_digest + send_digest_email (GREEN)"
  ```

---

### Task 5: Verifica manuale end-to-end

**Files:** nessuno (verifica)

- [ ] **Step 1: Avvia il backend**

  ```bash
  cd backend
  uvicorn app.main:app --reload --port 8000
  ```

- [ ] **Step 2: Testa endpoint senza secret (deve dare 401)**

  ```bash
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/admin/run-digest
  ```

  Expected: `401`

- [ ] **Step 3: Testa endpoint con `digest_secret` non configurato**

  Se `.env` non ha `DIGEST_SECRET`, il default è `""` → 401 anche con header Bearer.

  ```bash
  curl -s -X POST http://localhost:8000/admin/run-digest \
    -H "Authorization: Bearer qualcosa" | python3 -m json.tool
  ```

  Expected: `{"detail": "Admin endpoint not configured"}`

- [ ] **Step 4: Testa con secret configurato**

  Aggiungi temporaneamente a `.env`:
  ```
  DIGEST_SECRET=localtest123
  ```

  Riavvia uvicorn, poi:

  ```bash
  curl -s -X POST http://localhost:8000/admin/run-digest \
    -H "Authorization: Bearer localtest123" | python3 -m json.tool
  ```

  Expected (se nessun utente Pro nel DB):
  ```json
  {"sent": 0, "skipped": 0, "errors": 0}
  ```

- [ ] **Step 5: Commit finale**

  ```bash
  git add backend/app/admin/
  git commit -m "feat: M5a digest mensile Pro — endpoint + job + email + 6 test"
  ```

---

## Note per Railway (deploy M5b)

- Aggiungere `DIGEST_SECRET` nelle env vars Railway (stringa 32+ caratteri random)
- Railway Cron schedule: `0 8 1 * *` (1° del mese, 08:00 UTC)
- URL: `https://<railway-domain>/admin/run-digest`
- `ANTHROPIC_API_KEY` opzionale — senza di esso il digest usa template testo statico
- `RESEND_API_KEY` obbligatorio per inviare email in produzione
