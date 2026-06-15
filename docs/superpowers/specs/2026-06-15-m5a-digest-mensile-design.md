# Clara Money M5a — Digest Mensile Pro

## Scope

Cron mensile per utenti Pro: ricalcola scenari, computa delta vs mese precedente, genera narrativa Claude (opzionale), invia email digest via Resend.

**Fuori scope M5a:** Stripe Customer Portal, gestione cancellazione subscription in-app, deploy Railway (M5b), waitlist (M5c).

---

## Architettura

### Endpoint

`POST /admin/run-digest` — unauthenticated via cookie, protetto da `Authorization: Bearer <DIGEST_SECRET>`.

Auth logic (in questo ordine):
1. Se `settings.digest_secret == ""` → 401 (endpoint disabilitato, safe default)
2. Estrai token da header `Authorization: Bearer <token>`
3. Se token != `settings.digest_secret` → 401

### Cron

In produzione: Railway Cron chiama l'endpoint HTTP con schedule `0 8 1 * *` (1° del mese ore 08:00 UTC).
In locale: `curl -X POST http://localhost:8000/admin/run-digest -H "Authorization: Bearer <secret>"`

### Struttura file

| File | Azione | Responsabilità |
|------|--------|----------------|
| `backend/app/config.py` | Modifica | Aggiunge `digest_secret: str = ""` |
| `backend/app/admin/__init__.py` | Crea | Package admin |
| `backend/app/admin/digest.py` | Crea | `run_monthly_digest()` + `send_digest_email()` |
| `backend/app/admin/router.py` | Crea | `POST /admin/run-digest` |
| `backend/app/main.py` | Modifica | Monta `admin_router` senza auth dependency |
| `backend/tests/test_digest.py` | Crea | 5 test integrazione |

---

## Job Logic

`async def run_monthly_digest(db: Session) -> dict` in `digest.py`. Ritorna `{"sent": N, "skipped": N, "errors": N}`.

```python
from sqlalchemy import select, extract
from datetime import datetime, timezone
from types import SimpleNamespace

users = db.execute(
    select(User).join(Profile).where(User.plan == "pro")
).scalars().all()

for user in users:
    # leggi email e profile PRIMA di qualsiasi commit
    email = user.email
    profile = db.get(Profile, user.id)

    try:
        # 1. Verifica profilo completo
        if not profile or profile.onboarding_step < 5 or not profile.horizon_years:
            skipped += 1
            continue

        # 2. Dedup: skip se Scenario già generato questo mese
        now = datetime.now(timezone.utc)
        existing = db.execute(
            select(Scenario)
            .where(Scenario.user_id == user.id)
            .where(extract("year", Scenario.generated_at) == now.year)
            .where(extract("month", Scenario.generated_at) == now.month)
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        # 3. Carica ultimo Scenario (per delta)
        prev_scenario = db.execute(
            select(Scenario)
            .where(Scenario.user_id == user.id)
            .order_by(Scenario.generated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        # 4. Ricalcola scenari
        capital = float(profile.liquid_savings or 0)
        monthly_pmt = max(0.0, float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)))
        math_data = compute_scenarios(capital, monthly_pmt, profile.horizon_years)

        # 5. Delta vs mese precedente (None se primo scenario)
        delta = None
        if prev_scenario and prev_scenario.math_data:
            prev = prev_scenario.math_data
            delta = {k: math_data[k][-1] - prev[k][-1] for k in ["sicuro", "bilanciato", "crescita"]}

        # 6. Narrativa Claude (con timeout 30s) o fallback template
        profile_ns = SimpleNamespace(
            age=profile.age, monthly_income=profile.monthly_income,
            monthly_expenses=profile.monthly_expenses, liquid_savings=profile.liquid_savings,
            existing_investments=profile.existing_investments, goal=profile.goal,
            horizon_years=profile.horizon_years,
        )
        narratives = None
        if settings.anthropic_api_key:
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model=settings.claude_model, max_tokens=1024, timeout=30,
                    messages=[{"role": "user", "content": _build_prompt(profile_ns, math_data)}],
                )
                parsed = json.loads(response.content[0].text)
                if {"intro","sicuro","bilanciato","crescita"}.issubset(parsed.keys()):
                    narratives = parsed
            except Exception:
                logger.exception("Claude failed for user %s, using fallback", user.id)
        if narratives is None:
            narratives = _build_fallback(profile_ns, math_data)

        # 7. Costruisci profile_snapshot e salva nuovo Scenario
        profile_snapshot = {
            "age": profile.age, "monthly_income": profile.monthly_income,
            "monthly_expenses": profile.monthly_expenses, "liquid_savings": profile.liquid_savings,
            "existing_investments": profile.existing_investments,
            "goal": profile.goal, "horizon_years": profile.horizon_years,
        }
        scenario = Scenario(
            user_id=user.id, profile_snapshot=profile_snapshot,
            math_data=math_data, narratives=narratives, narrative_ready=True,
        )
        db.add(scenario)
        db.commit()

        # 8. Invia email (dopo commit — se email fallisce, scenario è già salvato)
        await send_digest_email(email, profile_ns, math_data, delta, narratives)
        sent += 1

    except Exception:
        logger.exception("Digest failed for user %s", user.id)
        db.rollback()
        errors += 1
```

**Import da `scenarios/service.py`:** `_build_prompt`, `_build_fallback`, `_fmt_eur`
(funzioni private — import diretto è ok, evita duplicazione del prompt)

---

## Email Digest

**Mittente:** `Clara <noreply@claramoney.it>` (dominio già verificato in Resend per password reset)
**Oggetto:** `Il tuo aggiornamento mensile Clara — {mese_italiano} {anno}`
**Transport:** `async def send_digest_email(...)` via `httpx.AsyncClient` — stesso pattern di `auth/email.py`

### Mese italiano

```python
MESI = {1:"Gennaio",2:"Febbraio",3:"Marzo",4:"Aprile",5:"Maggio",6:"Giugno",
        7:"Luglio",8:"Agosto",9:"Settembre",10:"Ottobre",11:"Novembre",12:"Dicembre"}
mese = MESI[datetime.now(timezone.utc).month]
```

### Contenuto HTML

```
Ciao {email},

Il tuo piano finanziario aggiornato per {horizon_years} anni.

Scenario Sicuro      €{_fmt_eur(math_data["sicuro"][-1])}    [+€1.200 vs mese scorso / assente se delta=None]
Scenario Bilanciato  €{_fmt_eur(math_data["bilanciato"][-1])} [+€2.100 vs mese scorso]
Scenario Crescita    €{_fmt_eur(math_data["crescita"][-1])}   [+€3.800 vs mese scorso]

{narratives["intro"]}

Sicuro: {narratives["sicuro"]}
Bilanciato: {narratives["bilanciato"]}
Crescita: {narratives["crescita"]}

Clara · Problemi? Scrivi a support@claramoney.it
```

- Delta: `+€X.XXX` (verde) / `-€X.XXX` (rosso) formattato con `_fmt_eur`. Omesso se `delta is None`.
- Se `settings.resend_api_key == ""`: log warning, return (nessun errore propagato).

---

## Config

```python
digest_secret: str = ""
```

`digest_secret == ""` → endpoint sempre 401 (safe default: disabilitato finché non configurato).

---

## Testing

File: `backend/tests/test_digest.py`

### Fixture comune

```python
@pytest.fixture
def digest_settings(monkeypatch):
    monkeypatch.setattr(settings, "digest_secret", "testsecret")
    monkeypatch.setattr(settings, "resend_api_key", "re_fake")

AUTH = {"Authorization": "Bearer testsecret"}

@pytest.fixture
def pro_user_with_profile(client, db):
    # 1. Registra utente via POST /auth/register
    # 2. Imposta plan="pro" direttamente sul modello nel DB
    # 3. Crea Profile(user_id=..., onboarding_step=5,
    #        monthly_income=2000, monthly_expenses=1000,
    #        liquid_savings=5000, horizon_years=10,
    #        age=30, goal="casa", existing_investments=0)
    # 4. db.commit()
    # ritorna user
```

### Test

**1. `test_run_digest_unauthorized`**
```python
resp = client.post("/admin/run-digest")
assert resp.status_code == 401
```

**2. `test_run_digest_wrong_secret`**
```python
# digest_settings fixture attiva
resp = client.post("/admin/run-digest", headers={"Authorization": "Bearer wrong"})
assert resp.status_code == 401
```

**3. `test_run_digest_skips_free_users`**
```python
# digest_settings fixture, utente con plan="free" e profilo completo
with patch("httpx.AsyncClient.post") as mock_resend:
    resp = client.post("/admin/run-digest", headers=AUTH)
assert resp.status_code == 200
assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
mock_resend.assert_not_called()
```

**4. `test_run_digest_pro_user_gets_email`**
```python
# digest_settings fixture, pro_user_with_profile, uno Scenario precedente nel DB
with patch("httpx.AsyncClient.post") as mock_resend, \
     patch("app.admin.digest.Anthropic") as mock_claude:
    mock_claude.return_value.messages.create.return_value.content = [
        MagicMock(text='{"intro":"i","sicuro":"s","bilanciato":"b","crescita":"c"}')
    ]
    resp = client.post("/admin/run-digest", headers=AUTH)

assert resp.status_code == 200
assert resp.json()["sent"] == 1
# Nuovo Scenario salvato
assert db.query(Scenario).filter_by(user_id=user.id).count() == 2
# Email inviata all'indirizzo corretto
call_kwargs = mock_resend.call_args[1]["json"]
assert user.email in str(call_kwargs["to"])
# Delta presente nell'HTML (ha scenario precedente)
assert "vs mese scorso" in call_kwargs["html"]
```

**5. `test_run_digest_no_previous_scenario`**
```python
# digest_settings, pro_user_with_profile, NESSUNO Scenario precedente
with patch("httpx.AsyncClient.post") as mock_resend:
    resp = client.post("/admin/run-digest", headers=AUTH)
assert resp.status_code == 200
assert resp.json()["sent"] == 1
# Email inviata senza delta
call_kwargs = mock_resend.call_args[1]["json"]
assert "vs mese scorso" not in call_kwargs["html"]
```

**6. `test_run_digest_dedup_skips_already_sent`**
```python
# digest_settings, pro_user_with_profile, Scenario già creato QUESTO mese nel DB
with patch("httpx.AsyncClient.post") as mock_resend:
    resp = client.post("/admin/run-digest", headers=AUTH)
assert resp.json() == {"sent": 0, "skipped": 1, "errors": 0}
mock_resend.assert_not_called()
```

---

## Note di produzione

- `DIGEST_SECRET`: stringa random 32+ caratteri in Railway env vars
- `ANTHROPIC_API_KEY` assente → narrativa fallback template (zero costo API, email inviata comunque)
- `RESEND_API_KEY` assente → log warning, nessuna email (safe default)
- Dedup per mese garantisce idempotenza: doppio run nello stesso mese → secondo run skippato
- Dominio `claramoney.it` già verificato in Resend (usato per password reset)
