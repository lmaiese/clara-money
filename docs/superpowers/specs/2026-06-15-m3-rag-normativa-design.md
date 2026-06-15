# Clara Money M3 — RAG Normativa Design

*Prodotto: 2026-06-15 — brainstorming con ricerca Railway/pgvector e PDF parsing*

---

## Scope

M3 aggiunge un layer RAG (Retrieval-Augmented Generation) alla narrative generation di M2. Un corpus statico di ~10-20 PDF normativi italiani (BdI, AE, CONSOB) viene indicizzato con pgvector. Prima di chiamare Claude, si recuperano i chunk più rilevanti per scenario e si iniettano nel prompt. L'utente vede una sezione "Fonti" collassabile sotto la narrativa.

Nessun cron automatico (M5), nessun paywall (M4), nessun endpoint pubblico per il retrieval.

---

## Decisioni chiave

| Decisione | Scelta | Motivazione |
|---|---|---|
| Embedding model | OpenAI `text-embedding-3-small` (1536 dim) | Qualità alta su italiano legale/normativo; costo trascurabile per MVP |
| Corpus | Documenti statici curati manualmente (~10-20 PDF) | Qualità > quantità; scraper automatico a M5 |
| PDF parsing | `pymupdf4llm` con `header=False, footer=False` | Unica lib con header/footer suppression nativa; output Markdown pulito |
| Query retrieval | Query fisse per scenario type (non da profilo utente) | Deterministiche, testabili, più rilevanti per contesto normativo |
| Fallback RAG | Skip silente se OpenAI embedding fallisce | Narrativa degraded ma funzionante; nessun errore visibile all'utente |
| UI | Sezione "Fonti" collassabile sotto NarrativeSection | Aggiunge fiducia senza impatto sul flow principale |
| `sources` storage | Colonna separata `scenarios.sources JSONB` | Mantiene `narratives` JSONB invariato da M2 |
| Deploy DB (M5) | Vercel Postgres (Neon) invece di Railway standard | Neon supporta pgvector natively; Railway standard non lo include |
| Docker test image | `pgvector/pgvector:pg16` (da `postgres:16`) | pgvector richiede estensione non presente nell'immagine standard |

---

## Corpus documentale

Struttura cartelle locale (non committata nel repo — solo i PDF dell'operatore):

```
backend/docs_corpus/
  bdi/
    relazione-annuale-2024.pdf
    rendimenti-storici-btp-2024.pdf
  ae/
    circolare-detrazioni-investimenti-2024.pdf
  consob/
    guida-mifid2-investitori-retail.pdf
  ...
```

`source` è derivato dal nome della cartella padre (`bdi` → `"BdI"`, `ae` → `"AE"`, `consob` → `"CONSOB"`).
`title` è derivato da `"{nome_file} [{chunk_n}/{total_chunks}]"`.

---

## Architettura

```
PDF curati
     ↓
scripts/ingest_docs.py (CLI, one-shot, idempotente)
     ↓ pymupdf4llm → MarkdownTextSplitter(400/50) → openai embed → pgvector
     ↓
tabella documents (pgvector, stesso PostgreSQL)

Al momento della narrativa (BackgroundTask):
RETRIEVAL_QUERIES[scenario_type]
     ↓ embed (OpenAI) → cosine search top-2, distanza ≤ 0.35
     ↓ chunk.content → iniettato in prompt Claude
     ↓ chunk.title + chunk.source → salvati in scenarios.sources
     ↓
GET /scenarios/me → ScenarioResponse.sources: [{"title": ..., "source": ...}]
     ↓
SourcesSection.tsx — collapsibile, solo se sources non è null
```

---

## Schema DB

### Nuova tabella `documents`

```sql
documents(
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  source      TEXT NOT NULL,   -- "BdI" | "AE" | "CONSOB"
  content     TEXT NOT NULL,
  embedding   vector(1536),
  ingested_at TIMESTAMPTZ DEFAULT now()
)

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops);
```

Deduplicazione: skip INSERT se `(title, content)` già presente.

### Modifica `scenarios`

```sql
ALTER TABLE scenarios ADD COLUMN sources JSONB;
-- ex: [{"title": "relazione-annuale-2024 [3/47]", "source": "BdI"}]
```

### Docker test

`docker-compose.test.yml`: immagine `postgres:16` → `pgvector/pgvector:pg16`.
Migration aggiunge `CREATE EXTENSION IF NOT EXISTS vector;` prima di `create_table`.

---

## Ingestione — `backend/scripts/ingest_docs.py`

```bash
# Eseguire una volta dopo aver aggiunto PDF a docs_corpus/
cd backend && python scripts/ingest_docs.py --folder docs_corpus/
```

**Flow per ogni PDF:**
1. `pymupdf4llm.to_markdown(path, header=False, footer=False)` → Markdown pulito
2. `MarkdownTextSplitter(chunk_size=400, chunk_overlap=50).split_text(md)` → lista chunk
3. Per ogni chunk: `openai.embeddings.create(model="text-embedding-3-small", input=chunk)`
4. `INSERT INTO documents ... ON CONFLICT DO NOTHING` (idempotente su title+content)

Dipendenze nuove: `pymupdf`, `pymupdf4llm`, `openai`, `langchain-text-splitters`.

---

## Retrieval

### Query fisse per scenario

```python
RETRIEVAL_QUERIES: dict[str, str] = {
    "sicuro":     "conti deposito BTP obbligazioni garantite normativa italiana rendimento",
    "bilanciato": "ETF obbligazionario misto MiFID II consulenza finanziaria rischio moderato",
    "crescita":   "ETF azionario globale CONSOB rischio mercato orizzonte lungo termine",
}
```

### Funzione `retrieve_context`

```python
def retrieve_context(db: Session, scenario_type: str) -> list[Document]:
    # 1. Embed RETRIEVAL_QUERIES[scenario_type] via OpenAI
    # 2. SELECT ... ORDER BY embedding <=> query_vec LIMIT 2
    # 3. Filtra distanza > 0.35 (chunk non abbastanza rilevante)
    # 4. Ritorna lista Document (può essere vuota)
```

Wrapper `retrieve_all_contexts(db) -> dict[str, list[Document]]` chiama `retrieve_context` per tutti e 3 gli scenari in sequenza.

### Fallback

```python
try:
    contexts = retrieve_all_contexts(db)
except Exception:
    contexts = {}   # skip RAG silente
```

Se `contexts` è vuoto (errore o nessun chunk sopra soglia), il prompt Claude non include sezione normativa — comportamento identico a M2.

---

## Integrazione nel prompt Claude

`_build_prompt` aggiornato per accettare `contexts: dict[str, list[Document]]`:

```
[sezione esistente M2 — profilo utente + scenari]

Contesto normativo di riferimento (usa solo se pertinente, non citare testualmente):
Sicuro: <content_chunk1> / <content_chunk2>
Bilanciato: <content_chunk1> / <content_chunk2>
Crescita: <content_chunk1> / <content_chunk2>
```

Se `contexts` è vuoto o mancante, la sezione non viene aggiunta.

---

## API

### `ScenarioResponse` (aggiornato)

```python
class Source(BaseModel):
    title: str
    source: str

class ScenarioResponse(BaseModel):
    scenario_id: uuid.UUID
    math_data: dict
    narratives: dict | None
    narrative_ready: bool
    generated_at: datetime
    sources: list[Source] | None = None   # nuovo campo
    model_config = {"from_attributes": True}
```

### GET /scenarios/me

Risposta invariata tranne il campo `sources` aggiunto.

---

## Frontend

### Modifiche

**`frontend/lib/types.ts`** — aggiunge:
```typescript
export interface Source {
  title: string
  source: string
}

// ScenarioResponse aggiunge:
sources: Source[] | null
```

**`frontend/app/dashboard/SourcesSection.tsx`** — nuovo componente:
```tsx
// Render null se sources è null o vuoto
// Altrimenti: details/summary collassabile
// "▼ Basato su fonti normative"
//   · Relazione BdI 2024 [3/47]   [BdI]
//   · Guida MiFID2 CONSOB [5/23]  [CONSOB]
```

**`frontend/app/dashboard/page.tsx`** — aggiunge `<SourcesSection sources={sources} />` dopo `<NarrativeSection>`.

**`frontend/app/globals.css`** — aggiunge CSS per `.sources-section`, `.sources-item`.

### `useDashboard.ts`

Nessuna modifica alla state machine — `sources` è incluso automaticamente nella `ScenarioResponse` del polling GET /scenarios/me.

---

## Testing

### Backend

**`backend/tests/test_ingest.py`** — 3 unit test:
- Chunking su PDF fixture (file PDF minimale di test) → N chunk prodotti
- Embedding mock → INSERT in DB con embedding corretto
- Deduplicazione → secondo run non duplica righe

**`backend/tests/test_retrieval.py`** — 3 test:
- `retrieve_context` con embedding mock restituisce chunk corretto
- Chunk sotto soglia distanza (> 0.35) escluso
- Fallback: errore OpenAI → `retrieve_all_contexts` ritorna `{}`, narrativa generata senza crash

**`backend/tests/test_scenarios_api.py`** — 1 test aggiornato:
- `test_generate_creates_scenario_in_db` verifica che `sources` sia presente in response (può essere `null` se OpenAI non configurata in test)

### Frontend

**`frontend/__tests__/SourcesSection.test.tsx`** — 2 test:
- Render con `sources` popolato → mostra titoli
- Render con `sources: null` → non mostra il blocco

---

## Licenza nota

`pymupdf` è AGPL-3.0: ok per MVP beta privato. Da rivalutare per M5 (SaaS pubblico) — alternativa commerciale: licenza PyMuPDF Pro.

---

## Out of scope M3

- Scraper automatico documenti (M5)
- Cron re-ingestion (M5)
- Paywall narrativa arricchita (M4)
- Endpoint pubblico per ricerca documenti
- OCR per PDF scansionati
- Traduzione documenti in lingue diverse dall'italiano
