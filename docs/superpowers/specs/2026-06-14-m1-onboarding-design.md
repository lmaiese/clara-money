# Clara Money M1 — Onboarding Design

*Prodotto: 2026-06-14 — brainstorming 3 sezioni, 2 validazioni critiche*

---

## Scope

M1 copre esclusivamente: registrazione utente, login, wizard onboarding 5 step, salvataggio profilo progressivo su DB. Nessun engine scenari (M2), nessuna normativa RAG (M3), nessuna Supabase Auth definitiva (M4).

---

## Decisioni chiave

| Decisione | Scelta | Motivazione |
|---|---|---|
| UX pattern | Wizard con progress bar | Validazione per-step semplice, progresso visibile |
| Auth timing | Auth prima dell'onboarding | `user_id` sempre disponibile, nessun profilo anonimo da linkare |
| Partial completion | Salvataggio progressivo passo per passo | Resilienza: utente riprende da dove si è fermato |
| API auth (M1) | python-jose JWT in httpOnly cookie | Supabase Auth arriva in M4 — interfaccia JWT non cambia |
| `horizon_years` | Derivato da `goal` (non chiesto) | Mantiene 5 step, riduce frizione |
| Test DB | PostgreSQL in Docker | SQLite non supporta UUID nativo né pgvector (M3) |

---

## Schema DB

```sql
users(
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email            TEXT UNIQUE NOT NULL,
  password_hash    TEXT NOT NULL,          -- rimosso in M4 (Supabase Auth)
  created_at       TIMESTAMPTZ DEFAULT now(),
  stripe_customer_id TEXT,
  plan             TEXT DEFAULT 'free'     -- 'free' | 'pro'
)

profiles(
  user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
  age              INT,                    -- nullable: salvataggio progressivo
  monthly_income   INT,
  monthly_expenses INT,
  liquid_savings   INT,
  existing_investments INT,
  goal             TEXT,                   -- 'growth' | 'house' | 'pension'
  horizon_years    INT,                    -- derivato, NON chiesto all'utente
  onboarding_step  INT DEFAULT 0,          -- completati: 0–5 (5 = profilo completo)
  updated_at       TIMESTAMPTZ DEFAULT now()
)
```

**Semantica `onboarding_step`:** valore = numero di passi *completati*. Step=3 → il wizard mostra il passo 4. Step=5 → redirect a `/dashboard` senza mostrare il wizard.

**Profile row creation:** creata al momento del register con tutti i campi NULL e `onboarding_step=0`. GET `/profiles/me` non restituisce mai 404 per utenti registrati.

**`horizon_years` — mapping derivato:**
```python
GOAL_HORIZON = {"growth": 15, "house": 5, "pension": 20}
```
Viene calcolato e salvato insieme a `goal` al passo 5.

---

## Validazione campi

Costanti condivise tra Pydantic (backend) e Zod (frontend):

| Campo | Tipo | Regola |
|---|---|---|
| `age` | INT | 18 ≤ age ≤ 75 |
| `monthly_income` | INT | > 0, ≤ 50.000 |
| `monthly_expenses` | INT | > 0 |
| `liquid_savings` | INT | ≥ 0 |
| `existing_investments` | INT | ≥ 0 (0 = nessun investimento) |
| `goal` | ENUM | `growth` \| `house` \| `pension` |

Errori di validazione: messaggio inline sotto il campo, step non avanza.

---

## FastAPI — Route M1

| Method | Path | Auth | Pydantic model | Scopo |
|--------|------|------|----------------|-------|
| POST | `/auth/register` | No | `RegisterRequest(email, password)` | Crea user + profile row, restituisce JWT in httpOnly cookie |
| POST | `/auth/login` | No | `LoginRequest(email, password)` | Verifica password, restituisce JWT in httpOnly cookie |
| POST | `/auth/logout` | JWT | — | Cancella cookie |
| GET | `/profiles/me` | JWT | — | Restituisce profilo + `onboarding_step` |
| PATCH | `/profiles/me` | JWT | `ProfilePatch` (tutti i campi opzionali + `onboarding_step`) | Upsert parziale |

**`ProfilePatch`** accetta qualsiasi sottoinsieme di campi + il nuovo `onboarding_step`. Il backend valida solo i campi presenti nel payload (Pydantic `model_config = ConfigDict(extra='forbid')`).

**Sicurezza:**
- Password hashata con bcrypt (passlib)
- JWT in httpOnly cookie (non localStorage) — immune a XSS
- `SameSite=Lax` + `Secure=True` in produzione

---

## Next.js — Struttura

```
app/
  auth/
    page.tsx            → register + login tabs (redirect a /onboarding se JWT presente)
  onboarding/
    page.tsx            → legge onboarding_step → resume o step 1
    useWizard.ts        → state machine: currentStep, formData, patch(), resume()
    steps/
      Step1.tsx         → età (INT) + reddito netto (INT) — 2 campi, 1 step
      Step2.tsx         → spese mensili (chip rapidi + input esatto)
      Step3.tsx         → risparmi liquidi (chip rapidi + input)
      Step4.tsx         → investimenti esistenti (chip 0/fascia/importo esatto)
      Step5.tsx         → obiettivo (3 card: crescita / casa / pensione)
  dashboard/
    page.tsx            → placeholder "I tuoi scenari arrivano in M2"
  middleware.ts         → redirect /onboarding → /auth se cookie JWT assente
```

**`useWizard` — responsabilità:**
1. Al mount: `GET /profiles/me` → se `onboarding_step > 0`, imposta `currentStep = onboarding_step`
2. `next(stepData)`: valida → `PATCH /profiles/me {stepData, onboarding_step: currentStep+1}` → se 200: avanza step
3. `back()`: decrementa `currentStep` (no PATCH — non si cancellano dati già salvati)
4. Su PATCH 401: redirect `/auth?redirect=/onboarding`
5. Su PATCH errore rete: toast "Errore, riprova" — step non avanza, `formData` in memoria

**Colori:** palette chiaro e attraente (non dark). Definito durante implementazione con `/frontend-design`.

---

## Flusso completo — Happy path

```
/auth (register)
  → POST /auth/register
  → SET httpOnly cookie JWT
  → INSERT users + INSERT profiles (onboarding_step=0)
  → redirect /onboarding

/onboarding (step 1)
  → GET /profiles/me → onboarding_step=0 → mostra Step1
  → utente compila età + reddito → click Avanti
  → PATCH /profiles/me {age, monthly_income, onboarding_step: 1} → 200
  → mostra Step2 … Step5

/onboarding (step 5 completato)
  → PATCH /profiles/me {goal: "growth", horizon_years: 15, onboarding_step: 5}
  → redirect /dashboard
```

---

## Testing

**Backend (pytest + PostgreSQL Docker):**
- `docker-compose.test.yml`: PostgreSQL isolato, reset tra test con transaction rollback (fixture `db_session`)
- Test obbligatori:
  - `test_register_creates_user_and_profile`
  - `test_login_returns_jwt_cookie`
  - `test_patch_profile_step_by_step` (5 PATCH sequenziali → profilo completo)
  - `test_resume_from_step_3` (GET /profiles/me restituisce onboarding_step=3)
  - `test_patch_rejects_invalid_age` (age=150 → 422)
  - `test_patch_rejects_expenses_gt_income`

**Frontend (Vitest + React Testing Library):**
- `renderHook(() => useWizard())` con fetch mockato
- Test: avanzamento step, resume da step preesistente, comportamento su errore PATCH

**No E2E in M1** — Playwright arriva in M5 con il deploy.

---

## Out of scope M1

- Supabase Auth (M4)
- Stripe (M4)
- Engine scenari (M2)
- RAG normativa (M3)
- Email verification al register
- Test E2E
