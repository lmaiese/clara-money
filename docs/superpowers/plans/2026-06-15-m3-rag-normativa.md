# Clara Money M3 — RAG Normativa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere un layer RAG che recupera chunk da documenti normativi italiani (pgvector) e li inietta nel prompt Claude, con sezione "Fonti" collapsibile nella dashboard.

**Architecture:** Corpus statico di PDF curati → ingestione one-shot (pymupdf4llm + OpenAI embeddings → pgvector). Al momento della generazione narrativa (BackgroundTask), si recuperano i top-2 chunk per scenario via cosine search e si iniettano nel prompt Claude. Se OpenAI embedding fallisce: skip silente, narrativa senza contesto normativo. I titoli dei chunk recuperati vengono salvati in `scenarios.sources` JSONB e mostrati nel frontend come sezione collapsibile sotto la narrativa.

**Tech Stack:** pgvector 0.3.x (PostgreSQL extension), pgvector Python client, pymupdf + pymupdf4llm (PDF parsing), OpenAI `text-embedding-3-small` (1536 dim), langchain-text-splitters (MarkdownTextSplitter), FastAPI BackgroundTasks (esistente), Next.js 15 (esistente).

---

## File map

**Backend — nuovi:**
- `backend/app/rag/__init__.py`
- `backend/app/rag/retrieval.py` — `RETRIEVAL_QUERIES`, `_embed_query`, `_cosine_search`, `retrieve_context`, `retrieve_all_contexts`
- `backend/app/rag/ingest.py` — `extract_text`, `chunk_text`, `embed_chunks`, `ingest_folder`
- `backend/scripts/ingest_docs.py` — CLI entry point (chiama `ingest_folder`)
- `backend/alembic/versions/<rev>_m3_rag.py` — migration: vector extension + documents table + scenarios.sources
- `backend/tests/test_retrieval.py`
- `backend/tests/test_ingest.py`

**Backend — modificati:**
- `backend/app/models.py` — aggiunge `Document`, aggiunge `Scenario.sources`
- `backend/app/schemas.py` — aggiunge `Source`, aggiorna `ScenarioResponse`
- `backend/app/scenarios/service.py` — aggiorna `_build_prompt` + `_run_narrative_generation`
- `backend/app/scenarios/router.py` — aggiunge `sources` in entrambi gli endpoint
- `backend/app/config.py` — aggiunge `openai_api_key`
- `backend/requirements.txt` — aggiunge 5 pacchetti
- `backend/docker-compose.test.yml` — immagine pgvector
- `backend/tests/conftest.py` — `CREATE EXTENSION vector` prima di `create_all`
- `backend/tests/test_scenarios_api.py` — aggiorna 1 test per campo `sources`

**Frontend — nuovi:**
- `frontend/app/dashboard/SourcesSection.tsx`
- `frontend/__tests__/SourcesSection.test.tsx`

**Frontend — modificati:**
- `frontend/lib/types.ts` — aggiunge `Source`, aggiorna `ScenarioResponse`
- `frontend/app/dashboard/page.tsx` — aggiunge `<SourcesSection>`
- `frontend/app/globals.css` — aggiunge CSS `.sources-section`

---

## Task 1: pgvector infrastructure — Docker, deps, modelli, migration, conftest

**Files:**
- Modify: `backend/docker-compose.test.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/alembic/versions/<rev>_m3_rag.py`

- [ ] **Step 1: Aggiorna `backend/docker-compose.test.yml`**

Cambia l'immagine da `postgres:16-alpine` a `pgvector/pgvector:pg16`:

```yaml
services:
  db_test:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: clara_test
    ports:
      - "5433:5432"
```

- [ ] **Step 2: Aggiorna `backend/requirements.txt`**

Aggiungi i 5 pacchetti nuovi in fondo:

```
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.0
python-jose[cryptography]==3.3.0
bcrypt==4.2.1
pydantic-settings==2.7.0
pytest==8.3.4
httpx==0.28.1
anthropic==0.40.0
pgvector==0.3.6
pymupdf==1.24.14
pymupdf4llm==0.0.17
openai==1.58.1
langchain-text-splitters==0.3.3
```

- [ ] **Step 3: Installa le dipendenze**

```bash
cd backend && pip install pgvector==0.3.6 pymupdf==1.24.14 pymupdf4llm==0.0.17 openai==1.58.1 langchain-text-splitters==0.3.3
```

Expected: `Successfully installed ...` per tutti i pacchetti.

- [ ] **Step 4: Aggiungi `openai_api_key` a `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/clara_test"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

- [ ] **Step 5: Aggiungi `Document` e `Scenario.sources` a `backend/app/models.py`**

Sostituisci l'intero file con:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, text
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
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default="free")

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_income: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_expenses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liquid_savings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    existing_investments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goal: Mapped[str | None] = mapped_column(String, nullable=True)
    horizon_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    math_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    narratives: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 6: Aggiorna `backend/tests/conftest.py` per creare l'estensione vector**

```python
import pytest
from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.config import settings


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 7: Riavvia il container Docker con la nuova immagine**

```bash
cd backend && docker compose -f docker-compose.test.yml down && docker compose -f docker-compose.test.yml up -d
sleep 3
docker compose -f docker-compose.test.yml ps
```

Expected: container `db_test` con status `running` (immagine `pgvector/pgvector:pg16`).

- [ ] **Step 8: Crea la migration Alembic manualmente**

```bash
cd backend && alembic revision -m "m3_rag"
```

Apri il file generato in `alembic/versions/` e sostituisci il contenuto con:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE documents ADD COLUMN embedding vector(1536)")

    op.add_column("scenarios", sa.Column("sources", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenarios", "sources")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 9: Applica la migration al DB di sviluppo**

Il DB di sviluppo è lo stesso di test (porta 5433). Se non esiste ancora la connessione principale, usate la stessa stringa del `.env` o la default.

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade 13500510252a -> <new_rev>, m3_rag`

- [ ] **Step 10: Verifica import**

```bash
cd backend && python -c "from app.models import Document; from pgvector.sqlalchemy import Vector; print('OK')"
```

Expected: `OK`

- [ ] **Step 11: Verifica che i test esistenti passino ancora**

```bash
cd backend && pytest -q 2>&1 | tail -5
```

Expected: `28 passed` (nessuna regressione).

- [ ] **Step 12: Commit**

```bash
git add backend/docker-compose.test.yml backend/requirements.txt backend/app/config.py backend/app/models.py backend/tests/conftest.py backend/alembic/versions/
git commit -m "feat: pgvector infra — Document model, Scenario.sources, migration m3_rag"
```

---

## Task 2: Modulo retrieval + test (TDD)

**Files:**
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/retrieval.py`
- Create: `backend/tests/test_retrieval.py`

- [ ] **Step 1: Crea la directory RAG**

```bash
mkdir -p backend/app/rag && touch backend/app/rag/__init__.py
```

- [ ] **Step 2: Scrivi i test failing**

Crea `backend/tests/test_retrieval.py`:

```python
from unittest.mock import patch, MagicMock
from app.rag.retrieval import retrieve_context, retrieve_all_contexts, RETRIEVAL_QUERIES


def _fake_doc(title="relazione [1/10]", source="BdI", content="testo normativo"):
    doc = MagicMock()
    doc.title = title
    doc.source = source
    doc.content = content
    return doc


def test_retrieve_context_returns_docs_within_threshold(db):
    fake_embedding = [0.1] * 1536
    fake_doc = _fake_doc()

    with patch("app.rag.retrieval._embed_query", return_value=fake_embedding):
        with patch("app.rag.retrieval._cosine_search", return_value=[(fake_doc, 0.2)]):
            result = retrieve_context(db, "sicuro")

    assert len(result) == 1
    assert result[0].title == "relazione [1/10]"


def test_retrieve_context_excludes_docs_above_threshold(db):
    fake_embedding = [0.1] * 1536
    fake_doc = _fake_doc()

    with patch("app.rag.retrieval._embed_query", return_value=fake_embedding):
        with patch("app.rag.retrieval._cosine_search", return_value=[(fake_doc, 0.5)]):
            result = retrieve_context(db, "sicuro")

    assert result == []


def test_retrieve_all_contexts_silent_fallback_on_error(db):
    with patch("app.rag.retrieval._embed_query", side_effect=Exception("OpenAI down")):
        result = retrieve_all_contexts(db)

    assert result == {}
```

- [ ] **Step 3: Esegui i test — devono fallire**

```bash
cd backend && pytest tests/test_retrieval.py -v 2>&1 | tail -10
```

Expected: `ImportError: No module named 'app.rag.retrieval'`

- [ ] **Step 4: Implementa `backend/app/rag/retrieval.py`**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings

RETRIEVAL_QUERIES: dict[str, str] = {
    "sicuro":     "conti deposito BTP obbligazioni garantite normativa italiana rendimento",
    "bilanciato": "ETF obbligazionario misto MiFID II consulenza finanziaria rischio moderato",
    "crescita":   "ETF azionario globale CONSOB rischio mercato orizzonte lungo termine",
}

MAX_DISTANCE = 0.35


def _embed_query(query: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=[query])
    return response.data[0].embedding


def _cosine_search(db: Session, embedding: list[float]) -> list[tuple]:
    from app.models import Document
    rows = db.execute(
        select(
            Document,
            Document.embedding.cosine_distance(embedding).label("distance"),
        )
        .order_by(Document.embedding.cosine_distance(embedding))
        .limit(2)
    ).all()
    return [(row.Document, row.distance) for row in rows]


def retrieve_context(db: Session, scenario_type: str) -> list:
    embedding = _embed_query(RETRIEVAL_QUERIES[scenario_type])
    rows = _cosine_search(db, embedding)
    return [doc for doc, dist in rows if dist <= MAX_DISTANCE]


def retrieve_all_contexts(db: Session) -> dict[str, list]:
    result: dict[str, list] = {}
    for scenario_type in RETRIEVAL_QUERIES:
        try:
            docs = retrieve_context(db, scenario_type)
            if docs:
                result[scenario_type] = docs
        except Exception:
            pass
    return result
```

- [ ] **Step 5: Esegui i test — devono passare**

```bash
cd backend && pytest tests/test_retrieval.py -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 6: Esegui la suite completa**

```bash
cd backend && pytest -q 2>&1 | tail -5
```

Expected: `31 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/rag/ backend/tests/test_retrieval.py
git commit -m "feat: RAG retrieval — cosine search pgvector, query fisse per scenario, fallback silente"
```

---

## Task 3: Modulo ingest + script CLI + test (TDD)

**Files:**
- Create: `backend/app/rag/ingest.py`
- Create: `backend/scripts/ingest_docs.py`
- Create: `backend/tests/test_ingest.py`

- [ ] **Step 1: Scrivi i test failing**

Crea `backend/tests/test_ingest.py`:

```python
from unittest.mock import patch
from app.rag.ingest import chunk_text, ingest_folder
from app.models import Document


def test_chunk_text_splits_long_text():
    long_text = "parola " * 500
    chunks = chunk_text(long_text)
    assert len(chunks) > 1


def test_ingest_folder_inserts_documents(db, tmp_path):
    pdf_dir = tmp_path / "bdi"
    pdf_dir.mkdir()
    (pdf_dir / "relazione.pdf").touch()

    fake_text = "Testo normativo italiano. " * 30

    with patch("app.rag.ingest.extract_text", return_value=fake_text):
        with patch("app.rag.ingest.embed_chunks", side_effect=lambda chunks: [[0.1] * 1536] * len(chunks)):
            count = ingest_folder(db, tmp_path)

    assert count >= 1
    docs = db.query(Document).all()
    assert len(docs) >= 1
    assert docs[0].source == "BdI"


def test_ingest_folder_skips_duplicate_documents(db, tmp_path):
    pdf_dir = tmp_path / "ae"
    pdf_dir.mkdir()
    (pdf_dir / "circolare.pdf").touch()

    fake_text = "Testo unico finanza. " * 30

    with patch("app.rag.ingest.extract_text", return_value=fake_text):
        with patch("app.rag.ingest.embed_chunks", side_effect=lambda chunks: [[0.2] * 1536] * len(chunks)):
            count1 = ingest_folder(db, tmp_path)
            count2 = ingest_folder(db, tmp_path)

    assert count1 >= 1
    assert count2 == 0
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
cd backend && pytest tests/test_ingest.py -v 2>&1 | tail -10
```

Expected: `ImportError: No module named 'app.rag.ingest'`

- [ ] **Step 3: Implementa `backend/app/rag/ingest.py`**

```python
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings

SOURCE_MAP: dict[str, str] = {
    "bdi": "BdI",
    "ae": "AE",
    "consob": "CONSOB",
}


def extract_text(pdf_path: Path) -> str:
    import pymupdf4llm
    return pymupdf4llm.to_markdown(str(pdf_path), header=False, footer=False)


def chunk_text(text: str) -> list[str]:
    from langchain_text_splitters import MarkdownTextSplitter
    splitter = MarkdownTextSplitter(chunk_size=400, chunk_overlap=50)
    return splitter.split_text(text)


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model="text-embedding-3-small", input=chunks)
    return [item.embedding for item in response.data]


def ingest_folder(db: Session, folder: Path) -> int:
    from app.models import Document

    count = 0
    for pdf_path in sorted(folder.rglob("*.pdf")):
        source_key = pdf_path.parent.name.lower()
        source = SOURCE_MAP.get(source_key, source_key.upper())
        stem = pdf_path.stem

        text = extract_text(pdf_path)
        chunks = chunk_text(text)
        if not chunks:
            continue

        embeddings = embed_chunks(chunks)
        total = len(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            title = f"{stem} [{i + 1}/{total}]"
            existing = db.query(Document).filter_by(title=title, content=chunk).first()
            if existing:
                continue
            doc = Document(title=title, source=source, content=chunk, embedding=embedding)
            db.add(doc)
            count += 1

        db.commit()

    return count
```

- [ ] **Step 4: Crea `backend/scripts/ingest_docs.py`**

```python
#!/usr/bin/env python
"""CLI per ingestione documenti normativi nel corpus RAG."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.rag.ingest import ingest_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta PDF normativi in pgvector")
    parser.add_argument("--folder", required=True, help="Path alla cartella docs_corpus/")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Errore: cartella '{folder}' non trovata", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        count = ingest_folder(db, folder)
        print(f"Ingestione completata: {count} chunk inseriti")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

Assicurarsi che la cartella `backend/scripts/` esista:

```bash
mkdir -p backend/scripts && touch backend/scripts/__init__.py
```

- [ ] **Step 5: Esegui i test — devono passare**

```bash
cd backend && pytest tests/test_ingest.py -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 6: Esegui la suite completa**

```bash
cd backend && pytest -q 2>&1 | tail -5
```

Expected: `34 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/rag/ingest.py backend/scripts/ backend/tests/test_ingest.py
git commit -m "feat: RAG ingest — pymupdf4llm, MarkdownTextSplitter, embed, idempotente"
```

---

## Task 4: Aggiorna service.py + schemas + router + test API

**Files:**
- Modify: `backend/app/scenarios/service.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/scenarios/router.py`
- Modify: `backend/tests/test_scenarios_api.py`

- [ ] **Step 1: Aggiorna `backend/app/schemas.py`**

Aggiungi `Source` e aggiorna `ScenarioResponse` (aggiungi `sources` in fondo, campo opzionale):

```python
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal
import uuid


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfilePatch(BaseModel):
    age: int | None = None
    monthly_income: int | None = None
    monthly_expenses: int | None = None
    liquid_savings: int | None = None
    existing_investments: int | None = None
    goal: Literal["growth", "house", "pension"] | None = None
    horizon_years: int | None = None
    onboarding_step: int | None = None

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int | None) -> int | None:
        if v is not None and not (18 <= v <= 75):
            raise ValueError("age must be between 18 and 75")
        return v

    @field_validator("monthly_income")
    @classmethod
    def validate_income(cls, v: int | None) -> int | None:
        if v is not None and not (0 < v <= 50000):
            raise ValueError("monthly_income must be between 1 and 50000")
        return v

    @field_validator("monthly_expenses")
    @classmethod
    def validate_expenses(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("monthly_expenses must be > 0")
        return v

    @field_validator("liquid_savings", "existing_investments")
    @classmethod
    def validate_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("value must be >= 0")
        return v

    model_config = {"extra": "forbid"}


class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    age: int | None
    monthly_income: int | None
    monthly_expenses: int | None
    liquid_savings: int | None
    existing_investments: int | None
    goal: str | None
    horizon_years: int | None
    onboarding_step: int

    model_config = {"from_attributes": True}


class Source(BaseModel):
    title: str
    source: str


class ScenarioResponse(BaseModel):
    scenario_id: uuid.UUID
    math_data: dict
    narratives: dict | None
    narrative_ready: bool
    generated_at: datetime
    sources: list[Source] | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Aggiorna `backend/app/scenarios/service.py`**

Sostituisci l'intero file con:

```python
import json
from types import SimpleNamespace
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Profile, Scenario
from app.scenarios.math import MathData, compute_scenarios


NARRATIVE_FALLBACK = {
    "intro": "Ecco cosa potrebbero fare i tuoi risparmi in {anni} anni.",
    "sicuro": (
        "Con un approccio prudente (3.5% annuo), potresti arrivare a circa €{valore}. "
        "Strumenti tipici: conti deposito, BTP. Rischio: basso."
    ),
    "bilanciato": (
        "Un portafoglio bilanciato (5% annuo) potrebbe portarti a circa €{valore}. "
        "Strumenti tipici: ETF obbligazionari misti. Rischio: medio."
    ),
    "crescita": (
        "Lo scenario più ambizioso (7% annuo) punta a circa €{valore} in {anni} anni. "
        "Strumenti tipici: ETF azionario globale diversificato. Rischio: alto."
    ),
}


def _fmt_eur(value: float) -> str:
    return f"{int(value):,}".replace(",", ".")


def _build_fallback(profile: SimpleNamespace, math_data: MathData) -> dict:
    return {
        "intro": NARRATIVE_FALLBACK["intro"].format(anni=profile.horizon_years),
        "sicuro": NARRATIVE_FALLBACK["sicuro"].format(valore=_fmt_eur(math_data["sicuro"][-1])),
        "bilanciato": NARRATIVE_FALLBACK["bilanciato"].format(valore=_fmt_eur(math_data["bilanciato"][-1])),
        "crescita": NARRATIVE_FALLBACK["crescita"].format(
            valore=_fmt_eur(math_data["crescita"][-1]), anni=profile.horizon_years
        ),
    }


def _build_prompt(profile: SimpleNamespace, math_data: MathData, contexts: dict | None = None) -> str:
    investments_note = (
        f"Nota: l'utente ha già {profile.existing_investments}€ investiti — citalo come contesto."
        if (profile.existing_investments or 0) > 0
        else ""
    )

    normative_section = ""
    if contexts:
        lines = ["", "Contesto normativo di riferimento (usa solo se pertinente, non citare testualmente):"]
        for scenario_type, docs in contexts.items():
            chunks = " / ".join(d.content[:200] for d in docs)
            lines.append(f"{scenario_type.capitalize()}: {chunks}")
        normative_section = "\n".join(lines)

    return f"""Sei Clara, consulente finanziaria italiana semplice e diretta.
L'utente ha {profile.age} anni, reddito netto {profile.monthly_income}€/mese,
spese {profile.monthly_expenses}€/mese, risparmi liquidi {profile.liquid_savings}€,
obiettivo: {profile.goal}, orizzonte: {profile.horizon_years} anni.
{investments_note}
{normative_section}

Hai calcolato 3 scenari. Per ognuno scrivi 2-3 frasi in italiano semplice:
cosa significa il valore finale, che categoria di strumento si usa, rischio in una parola.
Scenario Sicuro: valore finale €{int(math_data['sicuro'][-1])}.
Scenario Bilanciato: valore finale €{int(math_data['bilanciato'][-1])}.
Scenario Crescita: valore finale €{int(math_data['crescita'][-1])}.
Non nominare prodotti specifici. Solo categorie.

Rispondi SOLO con JSON valido senza markdown:
{{"intro":"...","sicuro":"...","bilanciato":"...","crescita":"..."}}"""


def _run_narrative_generation(scenario_id: str, profile_data: dict, math_data: MathData) -> None:
    db: Session = SessionLocal()
    try:
        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            return

        profile = SimpleNamespace(**profile_data)

        # RAG retrieval — skip silently on any error
        contexts: dict = {}
        sources: list = []
        try:
            from app.rag.retrieval import retrieve_all_contexts
            contexts = retrieve_all_contexts(db)
            seen: set[str] = set()
            for docs in contexts.values():
                for doc in docs:
                    if doc.title not in seen:
                        seen.add(doc.title)
                        sources.append({"title": doc.title, "source": doc.source})
        except Exception:
            pass

        narratives = None
        if settings.anthropic_api_key:
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": _build_prompt(profile, math_data, contexts)}],
                )
                parsed = json.loads(response.content[0].text)
                _REQUIRED = {"intro", "sicuro", "bilanciato", "crescita"}
                if _REQUIRED.issubset(parsed.keys()):
                    narratives = parsed
            except Exception:
                pass

        if narratives is None:
            narratives = _build_fallback(profile, math_data)

        scenario.narratives = narratives
        scenario.narrative_ready = True
        scenario.sources = sources if sources else None
        db.commit()
    finally:
        db.close()


def generate_scenarios(db: Session, user, background_tasks: BackgroundTasks) -> tuple[Scenario, MathData]:
    profile = db.get(Profile, user.id)
    if profile is None or profile.onboarding_step < 5:
        raise HTTPException(status_code=400, detail="Profile not complete")

    capital = float(profile.liquid_savings or 0)
    monthly_pmt = max(0.0, float((profile.monthly_income or 0) - (profile.monthly_expenses or 0)))
    math_data = compute_scenarios(capital, monthly_pmt, profile.horizon_years)

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
        user_id=user.id,
        profile_snapshot=profile_snapshot,
        math_data=math_data,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    background_tasks.add_task(_run_narrative_generation, str(scenario.id), profile_snapshot, math_data)
    return scenario, math_data


def get_latest_scenario(db: Session, user) -> Scenario | None:
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == user.id)
        .order_by(Scenario.generated_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
```

- [ ] **Step 3: Aggiorna `backend/app/scenarios/router.py`**

Aggiungi `sources=scenario.sources` a entrambi gli endpoint:

```python
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.scenarios.service import generate_scenarios, get_latest_scenario
from app.schemas import ScenarioResponse

router = APIRouter()


@router.post("/generate", response_model=ScenarioResponse)
def generate(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario, math_data = generate_scenarios(db, current_user, background_tasks)
    return ScenarioResponse(
        scenario_id=scenario.id,
        math_data=math_data,
        narratives=scenario.narratives,
        narrative_ready=scenario.narrative_ready,
        generated_at=scenario.generated_at,
        sources=None,
    )


@router.get("/me", response_model=ScenarioResponse | None)
def get_my_scenario(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = get_latest_scenario(db, current_user)
    if scenario is None:
        return None
    return ScenarioResponse(
        scenario_id=scenario.id,
        math_data=scenario.math_data,
        narratives=scenario.narratives,
        narrative_ready=scenario.narrative_ready,
        generated_at=scenario.generated_at,
        sources=scenario.sources,
    )
```

- [ ] **Step 4: Aggiorna `backend/tests/test_scenarios_api.py`**

Aggiorna solo `test_generate_creates_scenario_in_db` per verificare che `sources` sia presente nella response:

```python
def test_generate_creates_scenario_in_db(client):
    _setup_completed_user(client)
    with patch("app.scenarios.service._run_narrative_generation"):
        res = client.post("/scenarios/generate")
    assert res.status_code == 200
    data = res.json()
    assert "scenario_id" in data
    assert data["narrative_ready"] is False
    assert "sources" in data  # campo presente (può essere null)
```

Gli altri 5 test in `test_scenarios_api.py` rimangono invariati.

- [ ] **Step 5: Esegui la suite completa**

```bash
cd backend && pytest -q 2>&1 | tail -5
```

Expected: `34 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/scenarios/service.py backend/app/schemas.py backend/app/scenarios/router.py backend/tests/test_scenarios_api.py
git commit -m "feat: RAG integrato in service — _build_prompt con contesto normativo, sources in ScenarioResponse"
```

---

## Task 5: Frontend — SourcesSection + types + page + CSS

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/app/dashboard/SourcesSection.tsx`
- Create: `frontend/__tests__/SourcesSection.test.tsx`
- Modify: `frontend/app/dashboard/page.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Aggiorna `frontend/lib/types.ts`**

```typescript
export interface MathData {
  sicuro: number[]
  bilanciato: number[]
  crescita: number[]
  inflazione: number[]
  labels: number[]
}

export interface Narratives {
  intro: string
  sicuro: string
  bilanciato: string
  crescita: string
}

export interface Source {
  title: string
  source: string
}

export interface ScenarioResponse {
  scenario_id: string
  math_data: MathData
  narratives: Narratives | null
  narrative_ready: boolean
  generated_at: string
  sources: Source[] | null
}
```

- [ ] **Step 2: Scrivi i test failing**

Crea `frontend/__tests__/SourcesSection.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { SourcesSection } from '../app/dashboard/SourcesSection'

const SOURCES = [
  { title: 'relazione-annuale-2024 [3/47]', source: 'BdI' },
  { title: 'guida-mifid2 [5/23]', source: 'CONSOB' },
]

it('shows source titles and badges when sources provided', () => {
  render(<SourcesSection sources={SOURCES} />)
  expect(screen.getByText(/relazione-annuale-2024/)).toBeInTheDocument()
  expect(screen.getByText('BdI')).toBeInTheDocument()
  expect(screen.getByText('CONSOB')).toBeInTheDocument()
})

it('renders nothing when sources is null', () => {
  const { container } = render(<SourcesSection sources={null} />)
  expect(container.firstChild).toBeNull()
})
```

- [ ] **Step 3: Esegui i test — devono fallire**

```bash
cd frontend && npx vitest run __tests__/SourcesSection.test.tsx 2>&1 | tail -10
```

Expected: `Cannot find module '../app/dashboard/SourcesSection'`

- [ ] **Step 4: Crea `frontend/app/dashboard/SourcesSection.tsx`**

```tsx
'use client'
import type { Source } from '@/lib/types'

interface Props {
  sources: Source[] | null
}

export function SourcesSection({ sources }: Props) {
  if (!sources || sources.length === 0) return null

  return (
    <details className="sources-section">
      <summary className="sources-summary">Basato su fonti normative</summary>
      <ul className="sources-list">
        {sources.map((s, i) => (
          <li key={i} className="sources-item">
            <span className="sources-title">{s.title}</span>
            <span className="sources-badge">{s.source}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
```

- [ ] **Step 5: Esegui i test — devono passare**

```bash
cd frontend && npx vitest run __tests__/SourcesSection.test.tsx 2>&1 | tail -10
```

Expected: `2 passed`

- [ ] **Step 6: Aggiorna `frontend/app/dashboard/page.tsx`**

Aggiungi l'import di `SourcesSection` e il tag `<SourcesSection>` dopo `<NarrativeSection>`:

```tsx
'use client'
import dynamic from 'next/dynamic'
import { useDashboard } from './useDashboard'
import { ScenarioCards } from './ScenarioCards'
import { NarrativeSection } from './NarrativeSection'
import { SourcesSection } from './SourcesSection'

const ScenarioChart = dynamic(
  () => import('./ScenarioChart').then(m => ({ default: m.ScenarioChart })),
  { ssr: false }
)

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
  const narratives = state.status === 'narrative_ready' ? state.narratives : null
  const sources = state.status === 'narrative_ready' ? (state as any).sources ?? null : null
  const ready = state.status === 'narrative_ready'

  return (
    <main className="dashboard-layout">
      <h1>I tuoi scenari</h1>
      <ScenarioCards mathData={mathData} />
      <ScenarioChart mathData={mathData} />
      <NarrativeSection narratives={narratives} ready={ready} />
      <SourcesSection sources={sources} />
    </main>
  )
}
```

Nota: `sources` non è ancora nel tipo `DashboardState` — per ora usiamo `(state as any).sources` finché il tipo non viene aggiornato. Questa è un'approssimazione temporanea accettabile per M3.

Alternativa più pulita: aggiornare `useDashboard.ts` per includere `sources` nella state. Il tipo `narrative_ready` diventa:

```typescript
| { status: 'narrative_ready'; mathData: MathData; narratives: Narratives; sources: Source[] | null }
```

E in `useDashboard.ts`, riga dove si fa `setState({ status: 'narrative_ready', ... })`, aggiungere `sources: latest.sources`:

```typescript
setState({
  status: 'narrative_ready',
  mathData: latest.math_data,
  narratives: latest.narratives,
  sources: latest.sources,
})
```

Implementa questa versione pulita e aggiorna `page.tsx` per usare `state.sources` senza cast.

- [ ] **Step 7: Aggiorna `frontend/app/dashboard/useDashboard.ts`**

```typescript
'use client'
import { useState, useEffect } from 'react'
import { apiFetch, ApiError } from '@/lib/api'
import type { MathData, Narratives, ScenarioResponse, Source } from '@/lib/types'

type DashboardState =
  | { status: 'loading' }
  | { status: 'math_ready'; mathData: MathData }
  | { status: 'narrative_ready'; mathData: MathData; narratives: Narratives; sources: Source[] | null }
  | { status: 'error'; message: string }

export function useDashboard(): DashboardState {
  const [state, setState] = useState<DashboardState>({ status: 'loading' })

  useEffect(() => {
    let stopped = false

    async function run() {
      try {
        const generated = await apiFetch<ScenarioResponse>('/scenarios/generate', { method: 'POST' })
        if (stopped) return
        setState({ status: 'math_ready', mathData: generated.math_data })

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

Aggiorna `frontend/app/dashboard/page.tsx` per usare `state.sources` senza cast:

```tsx
'use client'
import dynamic from 'next/dynamic'
import { useDashboard } from './useDashboard'
import { ScenarioCards } from './ScenarioCards'
import { NarrativeSection } from './NarrativeSection'
import { SourcesSection } from './SourcesSection'

const ScenarioChart = dynamic(
  () => import('./ScenarioChart').then(m => ({ default: m.ScenarioChart })),
  { ssr: false }
)

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
  const narratives = state.status === 'narrative_ready' ? state.narratives : null
  const sources = state.status === 'narrative_ready' ? state.sources : null
  const ready = state.status === 'narrative_ready'

  return (
    <main className="dashboard-layout">
      <h1>I tuoi scenari</h1>
      <ScenarioCards mathData={mathData} />
      <ScenarioChart mathData={mathData} />
      <NarrativeSection narratives={narratives} ready={ready} />
      <SourcesSection sources={sources} />
    </main>
  )
}
```

- [ ] **Step 8: Aggiungi CSS a `frontend/app/globals.css`**

Aggiungi in fondo al file (dopo `.skeleton-line`):

```css

/* ── Sources ── */
.sources-section { background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 20px; box-shadow: var(--shadow); }
.sources-summary { font-size: 12px; font-weight: 600; color: var(--text-muted);
  cursor: pointer; user-select: none; list-style: none; }
.sources-summary::-webkit-details-marker { display: none; }
.sources-summary::before { content: '▶ '; font-size: 10px; }
details[open] .sources-summary::before { content: '▼ '; }
.sources-list { margin: 10px 0 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 6px; }
.sources-item { display: flex; align-items: center; justify-content: space-between;
  gap: 12px; font-size: 12px; }
.sources-title { color: var(--text-muted); }
.sources-badge { background: var(--accent-light); color: var(--accent);
  font-size: 10px; font-weight: 700; padding: 2px 6px;
  border-radius: 4px; white-space: nowrap; }
```

- [ ] **Step 9: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -10
```

Expected: nessun output (clean).

- [ ] **Step 10: Esegui tutti i test frontend**

```bash
cd frontend && npx vitest run 2>&1 | tail -10
```

Expected: `10 passed` (8 M1+M2 + 2 SourcesSection).

- [ ] **Step 11: Esegui tutti i test backend**

```bash
cd backend && pytest -q 2>&1 | tail -5
```

Expected: `34 passed`

- [ ] **Step 12: Commit**

```bash
cd /Users/maiesel/Obsidian/clara-money
git add frontend/lib/types.ts frontend/app/dashboard/SourcesSection.tsx frontend/__tests__/SourcesSection.test.tsx frontend/app/dashboard/page.tsx frontend/app/dashboard/useDashboard.ts frontend/app/globals.css
git commit -m "feat: SourcesSection + types + CSS — fonti normative collassabili in dashboard"
```
