# Clara Money M2 — Engine Scenari Design

*Prodotto: 2026-06-15 — brainstorming 3 sezioni, visual companion*

---

## Scope

M2 copre: calcolo matematico proiezioni finanziarie per 3 scenari, integrazione Claude per narrativa, dashboard con card + grafico Chart.js interattivo. Nessun paywall (M4), nessuna RAG normativa (M3).

---

## Decisioni chiave

| Decisione | Scelta | Motivazione |
|---|---|---|
| Freemium gate | Tutti e 3 gli scenari visibili in M2 | Il valore è la comparazione: senza il gap tra i 3 numeri, l'utente non ha motivazione ad agire |
| Trigger generazione | Automatico al redirect `/dashboard` | Momento di massimo engagement: nessun bottone intermedio |
| Math vs narrativa | Math sincrono (istantaneo), narrativa Claude async | Zero latenza percepita; l'utente vede numeri + grafico subito |
| AI fallback | Template testuale (non seconda AI) | Seconda AI = complessità non giustificata per MVP beta; template = 10 righe Python |
| Layout dashboard | Card in cima, grafico + narrativa sotto (layout B) | I numeri finali sono il colpo d'occhio più immediato |
| Schema DB | 1 riga per generazione (non 3) | Generiamo sempre tutti e 3 insieme, non ha senso interrogarli separatamente |
| Chiavi scenari | `sicuro / bilanciato / crescita` | Nomi italiani coerenti con UI; spec originale `liquidity/bond/equity` deprecata |
| `existing_investments` | Non entra nel compound | Condizioni di uscita e rendimento attuale sconosciuti; citato nella narrativa Claude |

---

## Math Engine

### Input dal profilo

```python
capital      = profile.liquid_savings           # capitale iniziale
monthly_pmt  = max(0, profile.monthly_income - profile.monthly_expenses)
horizon_yrs  = profile.horizon_years            # da GOAL_HORIZON in M1
```

`existing_investments` non entra nel calcolo. Claude lo cita nella narrativa:
> "Hai già €X investiti — questo calcolo riguarda solo i tuoi risparmi liquidi."

### Formula compound mensile

```python
RATES = {"sicuro": 0.035, "bilanciato": 0.05, "crescita": 0.07}
INFLATION = 0.025

def project(capital, monthly_pmt, horizon_yrs, annual_rate) -> list[float]:
    r = (1 + annual_rate) ** (1/12) - 1
    values = []
    for year in range(horizon_yrs + 1):
        n = year * 12
        if r == 0:
            v = capital + monthly_pmt * n
        else:
            v = capital * (1 + r)**n + monthly_pmt * ((1 + r)**n - 1) / r
        values.append(round(v, 2))
    return values
```

Output: array di `horizon_years + 1` valori (anno 0 = oggi, anno N = valore finale).

Quarta serie: inflazione (linea grigia — cosa vale il denaro se non si fa nulla):
```python
inflation_series = [capital * (1.025)**year for year in range(horizon_yrs + 1)]
```

### Schema DB

```sql
scenarios(
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
  generated_at     TIMESTAMPTZ DEFAULT now(),
  profile_snapshot JSONB NOT NULL,
  math_data        JSONB NOT NULL,
  narratives       JSONB,
  narrative_ready  BOOLEAN DEFAULT false
)
```

`math_data` struttura:
```json
{
  "sicuro":     [10000, 10350, 10712, ...],
  "bilanciato": [10000, 10500, 11025, ...],
  "crescita":   [10000, 10700, 11449, ...],
  "inflazione": [10000,  9756,  9518, ...],
  "labels":     [0, 1, 2, ..., 15]
}
```

`narratives` struttura:
```json
{
  "intro":      "Con i tuoi €10k liquidi e un orizzonte di 15 anni...",
  "sicuro":     "Con un approccio prudente...",
  "bilanciato": "Un portafoglio bilanciato...",
  "crescita":   "Lo scenario più ambizioso..."
}
```

---

## API

### POST /scenarios/generate (JWT required)

1. Legge profilo — valida `onboarding_step == 5`, altrimenti 400
2. Calcola math per tutti e 3 gli scenari + inflazione (~1ms, Python puro)
3. Inserisce riga in `scenarios` con `math_data`, `narrative_ready=false`
4. Lancia `BackgroundTasks` per call Claude
5. Risponde immediatamente con `{scenario_id, math_data}`

### GET /scenarios/me (JWT required)

Restituisce lo scenario più recente dell'utente:
```json
{
  "scenario_id": "uuid",
  "math_data": {...},
  "narratives": null,
  "narrative_ready": false,
  "generated_at": "2026-06-15T..."
}
```

Quando `narrative_ready=true`, `narratives` contiene i testi.

### BackgroundTask — Claude integration

Prompt:
```
Sei Clara, consulente finanziaria italiana semplice e diretta.
L'utente ha {age} anni, reddito netto {monthly_income}€/mese,
spese {monthly_expenses}€/mese, risparmi liquidi {liquid_savings}€,
investimenti esistenti {existing_investments}€, obiettivo: {goal},
orizzonte: {horizon_years} anni.

Hai calcolato 3 scenari. Per ognuno scrivi 2-3 frasi in italiano semplice:
cosa significa il valore finale, che categoria di strumento si usa, rischio in una parola.
Per lo scenario Sicuro il valore finale è {sicuro_finale}€.
Per Bilanciato è {bilanciato_finale}€. Per Crescita è {crescita_finale}€.
Cita gli investimenti esistenti come contesto se > 0.
Non nominare prodotti specifici. Solo categorie.

Rispondi SOLO con JSON valido:
{"intro":"...","sicuro":"...","bilanciato":"...","crescita":"..."}
```

Timeout: 30s. Se fallisce o timeout → **template fallback**:

```python
NARRATIVE_FALLBACK = {
    "intro": "Ecco cosa potrebbero fare i tuoi {capital}€ in {anni} anni.",
    "sicuro": "Con un approccio prudente (3.5% annuo), potresti arrivare a "
              "{valore}€. Strumenti tipici: conti deposito, BTP. Rischio: basso.",
    "bilanciato": "Un portafoglio bilanciato (5% annuo) potrebbe portarti a "
                  "{valore}€. Strumenti tipici: ETF obbligazionari misti. Rischio: medio.",
    "crescita": "Lo scenario più ambizioso (7% annuo) punta a {valore}€ in {anni} anni. "
                "Strumenti tipici: ETF azionario globale. Rischio: alto.",
}
```

In entrambi i casi: aggiorna `narratives` + `narrative_ready=true` in DB.

---

## Frontend

### Struttura file nuovi / modificati

```
frontend/app/dashboard/
  page.tsx          → modifica: da placeholder a dashboard reale
  useDashboard.ts   → nuovo: fetch POST generate + polling GET /me
  ScenarioCards.tsx → nuovo: 3 card con valore finale + rischio
  ScenarioChart.tsx → nuovo: Chart.js line chart (client-only)
  NarrativeSection.tsx → nuovo: skeleton durante polling, testo quando pronto
```

### useDashboard — state machine

```typescript
type DashboardState =
  | { status: 'loading' }
  | { status: 'math_ready'; mathData: MathData }
  | { status: 'narrative_ready'; mathData: MathData; narratives: Narratives }
  | { status: 'error'; message: string }

// Al mount:
// 1. POST /scenarios/generate → mathData → status: math_ready
// 2. Poll GET /scenarios/me ogni 2s (max 30s)
// 3. Quando narrative_ready=true → status: narrative_ready
// Nessun timeout lato frontend: il backend garantisce narrative_ready=true
// entro 30s (Claude riuscito o fallback template). Il polling si ferma
// alla prima risposta con narrative_ready=true.
```

### ScenarioChart

Chart.js importato con `dynamic(() => import(...), { ssr: false })` — richiede canvas, non funziona in SSR.

4 dataset: sicuro (verde chiaro), bilanciato (verde medio), crescita (verde scuro), inflazione (grigio tratteggiato). Tooltip hover: anno + valore formattato in €.

### Loading state narrativa

Mentre `narrative_ready=false`: skeleton con 3 barre grigie animate + testo "Clara sta analizzando il tuo profilo...". Quando arriva, sostituzione diretta senza reload.

---

## Testing

**Backend:**
- `test_math_engine.py` — 5 test unitari: crescita/bilanciato/sicuro valori attesi, versamento zero, horizon 1 anno
- `test_scenarios_api.py` — 4 test: generate crea riga DB, GET restituisce math_data, narrative_ready flips a true, profilo incompleto → 400
- Claude mockato in tutti i test (`unittest.mock.patch`)

**Frontend:**
- `useDashboard.test.ts` — 3 test Vitest: polling si ferma a narrative_ready=true, timeout 30s, errore POST → status error

---

## Out of scope M2

- Paywall / freemium gate (M4)
- Rigenerazione scenari se profilo cambia
- RAG normativa (M3)
- Scenario personalizzato (tasso personalizzabile dall'utente)
- Condivisione scenari
