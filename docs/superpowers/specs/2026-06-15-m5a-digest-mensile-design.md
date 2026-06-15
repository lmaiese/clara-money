# Clara Money M5a — Digest Mensile Pro

## Scope

Cron mensile per utenti Pro: ricalcola scenari, computa delta vs mese precedente, genera narrativa Claude (opzionale), invia email digest via Resend.

**Fuori scope M5a:** Stripe Customer Portal, gestione cancellazione subscription in-app, deploy Railway (M5b), waitlist (M5c).

---

## Architettura

### Endpoint

`POST /admin/run-digest` — unauthenticated via cookie, protetto da `Authorization: Bearer <DIGEST_SECRET>`.

```
Authorization: Bearer <settings.digest_secret>
```

Se il secret non corrisponde o è assente → 401. Endpoint montato in `main.py` senza `get_current_user` dependency.

### Cron

In produzione: Railway Cron chiama l'endpoint HTTP ogni 1° del mese. In locale: `curl -X POST http://localhost:8000/admin/run-digest -H "Authorization: Bearer <secret>"`.

### Struttura file

| File | Azione | Responsabilità |
|------|--------|----------------|
| `backend/app/config.py` | Modifica | Aggiunge `digest_secret: str = ""` |
| `backend/app/admin/__init__.py` | Crea | Package admin |
| `backend/app/admin/digest.py` | Crea | Logica job + `send_digest_email()` |
| `backend/app/admin/router.py` | Crea | `POST /admin/run-digest` |
| `backend/app/main.py` | Modifica | Monta `admin_router` |
| `backend/tests/test_digest.py` | Crea | 5 test integrazione |

---

## Job Logic

`run_monthly_digest(db: Session) -> dict` in `digest.py`. Ritorna `{"sent": N, "skipped": N, "errors": N}`.

```
Per ogni utente con plan="pro":
  1. Carica Profile → se onboarding_step < 5: skipped++, continua
  2. Carica ultimo Scenario dal DB (ORDER BY generated_at DESC LIMIT 1)
  3. Ricalcola: compute_scenarios(capital, monthly_pmt, horizon_years)
  4. Calcola delta: se Scenario precedente esiste
       delta = {k: nuovo[-1] - vecchio[-1] for k in ["sicuro","bilanciato","crescita"]}
     altrimenti delta = None
  5. Genera narrativa:
       se settings.anthropic_api_key: chiama Claude con _build_prompt() importato da scenarios/service.py (try/except → fallback)
       altrimenti: usa NARRATIVE_FALLBACK importato da scenarios/service.py
       (importazione diretta di funzioni private è ok — evita duplicare il prompt)
  6. Salva nuovo Scenario in DB (math_data=nuovo, narratives=narrativa, narrative_ready=True)
  7. send_digest_email(user.email, profile, math_data, delta, narratives) via Resend
  8. Errori per singolo utente: loggati, errors++, loop continua
```

`capital = float(profile.liquid_savings or 0)`
`monthly_pmt = max(0.0, float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)))`

---

## Email Digest

**Mittente:** `Clara <noreply@claramoney.it>`
**Oggetto:** `Il tuo aggiornamento mensile Clara — {Mese} {Anno}` (es. "Giugno 2026")
**Transport:** Resend REST API via `httpx.AsyncClient` (stesso pattern di `auth/email.py`)

### Contenuto HTML

```
Ciao {email},

Il tuo piano finanziario aggiornato per {horizon_years} anni.

┌─────────────────────────────────────────────────────┐
│ Scenario Sicuro      €XX.XXX   [+€1.200 vs mese scorso]  │
│ Scenario Bilanciato  €XX.XXX   [+€2.100 vs mese scorso]  │
│ Scenario Crescita    €XX.XXX   [+€3.800 vs mese scorso]  │
└─────────────────────────────────────────────────────┘

[Narrativa — intro + sicuro + bilanciato + crescita]

Clara · Problemi? Scrivi a support@claramoney.it
```

- Delta: `+€X.XXX` verde / `-€X.XXX` rosso. Assente se primo scenario (delta=None).
- Se `settings.resend_api_key` assente: log warning, skip invio (non errore).
- Nessun link "disdici abbonamento" funzionale in M5a — solo `mailto:support@claramoney.it`.

---

## Config

```python
digest_secret: str = ""
```

Se `digest_secret == ""`: endpoint risponde sempre 401 (secret non configurato = endpoint disabilitato).

---

## Testing

File: `backend/tests/test_digest.py`

### Setup comune

```python
@pytest.fixture
def pro_user_with_profile(client, db):
    # registra utente, imposta plan="pro", crea Profile completo (step=5)
    # con valori: monthly_income=2000, monthly_expenses=1000,
    #             liquid_savings=5000, horizon_years=10, goal="casa"
```

### Test

1. **`test_run_digest_unauthorized`**
   - POST /admin/run-digest senza header `Authorization`
   - Assert: 401

2. **`test_run_digest_wrong_secret`**
   - POST /admin/run-digest con `Authorization: Bearer wrongsecret`
   - `settings.digest_secret = "correctsecret"` via override
   - Assert: 401

3. **`test_run_digest_skips_free_users`**
   - Crea utente con `plan="free"` e profilo completo
   - Mock `httpx.AsyncClient.post` (Resend)
   - POST /admin/run-digest con secret corretto
   - Assert: 200, `{"sent": 0, "skipped": 1, "errors": 0}`, Resend non chiamato

4. **`test_run_digest_pro_user_gets_email`**
   - `pro_user_with_profile` fixture
   - Crea Scenario precedente nel DB con valori noti
   - Mock Resend + mock `anthropic.Anthropic`
   - POST /admin/run-digest
   - Assert: 200, `{"sent": 1, "skipped": 0, "errors": 0}`
   - Assert: nuovo Scenario salvato in DB (count = 2)
   - Assert: Resend chiamato con email utente, valori numerici nei kwargs

5. **`test_run_digest_no_previous_scenario`**
   - `pro_user_with_profile` senza Scenario precedente
   - Mock Resend
   - POST /admin/run-digest
   - Assert: 200, `{"sent": 1, ...}`
   - Assert: Resend chiamato (delta assente nel payload — non crashare)

---

## Note di produzione

- `DIGEST_SECRET` in Railway env vars: stringa random 32+ caratteri
- Railway Cron schedule: `0 8 1 * *` (1° del mese alle 08:00 UTC)
- `ANTHROPIC_API_KEY` assente → narrativa template statico (zero costo API)
- `RESEND_API_KEY` assente → log warning, nessuna email inviata (safe default)
- Il job è idempotente: girarlo due volte nello stesso mese crea 2 Scenario e 2 email — Railway Cron garantisce run singolo
