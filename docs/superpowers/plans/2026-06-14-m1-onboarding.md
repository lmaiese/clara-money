# Clara Money M1 — Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare registrazione, login, e wizard onboarding 5-step con salvataggio progressivo del profilo finanziario su PostgreSQL.

**Architecture:** FastAPI backend con JWT in httpOnly cookie; SQLAlchemy 2.x sync ORM; Next.js 15 App Router con `useWizard` state machine. Ogni step del wizard fa un PATCH parziale al profilo — se l'utente abbandona, riprende esattamente dallo step successivo all'ultimo salvato.

**Tech Stack:** Python 3.11, FastAPI 0.115, SQLAlchemy 2, Alembic, bcrypt, python-jose, pytest, PostgreSQL 16 (Docker); Next.js 15, TypeScript, Zod, Vitest, React Testing Library.

---

## Task 1: Backend scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/docker-compose.test.yml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Crea struttura directory backend**

```bash
mkdir -p backend/app/auth backend/app/profiles backend/tests backend/alembic/versions
touch backend/app/__init__.py backend/app/auth/__init__.py backend/app/profiles/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: Scrivi `backend/requirements.txt`**

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
```

- [ ] **Step 3: Scrivi `backend/docker-compose.test.yml`**

```yaml
services:
  db_test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: clara_test
    ports:
      - "5433:5432"
```

- [ ] **Step 4: Scrivi `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5433/clara_test"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 5: Scrivi `backend/app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Scrivi `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.router import router as auth_router
from app.profiles.router import router as profiles_router

app = FastAPI(title="Clara Money API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
```

- [ ] **Step 7: Installa dipendenze e verifica avvio**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose -f docker-compose.test.yml up -d
# Attendi 3 secondi poi:
uvicorn app.main:app --reload
# Apri http://localhost:8000/docs — deve rispondere 200
```

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "chore: backend scaffold — FastAPI + SQLAlchemy + Docker test DB"
```

---

## Task 2: DB models

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/alembic/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial.py`

- [ ] **Step 1: Scrivi `backend/app/models.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
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
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")
```

- [ ] **Step 2: Inizializza Alembic**

```bash
cd backend
alembic init alembic
```

Modifica `alembic/alembic.ini` — riga `sqlalchemy.url`:
```ini
sqlalchemy.url = postgresql://postgres:postgres@localhost:5433/clara_test
```

- [ ] **Step 3: Modifica `backend/alembic/env.py`** — aggiungi import models

Trova la riga `target_metadata = None` e sostituiscila:

```python
# all'inizio del file, dopo gli import esistenti
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import Base
from app import models  # noqa: F401 — registra i modelli

# sostituisci:
target_metadata = Base.metadata
```

- [ ] **Step 4: Genera migration iniziale**

```bash
cd backend
alembic revision --autogenerate -m "initial"
# Verifica il file generato in alembic/versions/ — deve contenere CREATE TABLE users e profiles
```

- [ ] **Step 5: Applica migration**

```bash
alembic upgrade head
# Expected output: Running upgrade  -> <hash>, initial
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/
git commit -m "feat: DB models User + Profile + Alembic migration"
```

---

## Task 3: Test fixtures (conftest)

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Scrivi `backend/tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from app.config import settings

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(settings.database_url)
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

- [ ] **Step 2: Verifica che i fixture si carichino senza errori**

```bash
cd backend
pytest tests/ --collect-only
# Expected: no errors, 0 tests collected (normale — test non ancora scritti)
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: conftest fixtures — PostgreSQL session con transaction rollback"
```

---

## Task 4: Auth service (password + JWT)

**Files:**
- Create: `backend/app/auth/service.py`
- Create: `backend/app/schemas.py`

- [ ] **Step 1: Scrivi il test per l'auth service**

Crea `backend/tests/test_auth_service.py`:

```python
from app.auth.service import hash_password, verify_password, create_token, decode_token
import uuid

def test_hash_and_verify_password():
    pw = "SecurePass123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_decode_token():
    user_id = uuid.uuid4()
    token = create_token(user_id)
    decoded = decode_token(token)
    assert decoded == user_id

def test_decode_invalid_token_raises():
    import pytest
    from jose import JWTError
    with pytest.raises(JWTError):
        decode_token("not.a.valid.token")
```

- [ ] **Step 2: Esegui il test — deve fallire**

```bash
cd backend
pytest tests/test_auth_service.py -v
# Expected: ERROR ImportError (modulo non esiste)
```

- [ ] **Step 3: Scrivi `backend/app/auth/service.py`**

```python
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError  # noqa: F401 — re-exported per i caller
from app.config import settings

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

def decode_token(token: str) -> uuid.UUID:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return uuid.UUID(payload["sub"])
```

- [ ] **Step 4: Esegui il test — deve passare**

```bash
pytest tests/test_auth_service.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Scrivi `backend/app/schemas.py`**

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/service.py backend/app/schemas.py backend/tests/test_auth_service.py
git commit -m "feat: auth service (bcrypt + JWT) + Pydantic schemas"
```

---

## Task 5: Auth dependencies

**Files:**
- Create: `backend/app/auth/dependencies.py`

- [ ] **Step 1: Scrivi `backend/app/auth/dependencies.py`**

```python
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models import User
from app.auth.service import decode_token

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw = request.cookies.get("access_token")
    if not raw or not raw.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        user_id = decode_token(raw.removeprefix("Bearer "))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/auth/dependencies.py
git commit -m "feat: get_current_user JWT cookie dependency"
```

---

## Task 6: Auth router (register + login + logout)

**Files:**
- Create: `backend/app/auth/router.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Scrivi i test per auth**

Crea `backend/tests/test_auth.py`:

```python
def test_register_creates_user_and_profile(client, db):
    from app.models import User, Profile
    res = client.post("/auth/register", json={"email": "user@test.com", "password": "password123"})
    assert res.status_code == 200
    assert res.json()["message"] == "registered"
    assert "access_token" in res.cookies
    user = db.query(User).filter_by(email="user@test.com").first()
    assert user is not None
    profile = db.query(Profile).filter_by(user_id=user.id).first()
    assert profile is not None
    assert profile.onboarding_step == 0

def test_register_duplicate_email_returns_409(client):
    client.post("/auth/register", json={"email": "dup@test.com", "password": "password123"})
    res = client.post("/auth/register", json={"email": "dup@test.com", "password": "password123"})
    assert res.status_code == 409

def test_login_returns_jwt_cookie(client):
    client.post("/auth/register", json={"email": "login@test.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "login@test.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.cookies

def test_login_wrong_password_returns_401(client):
    client.post("/auth/register", json={"email": "wrong@test.com", "password": "password123"})
    res = client.post("/auth/login", json={"email": "wrong@test.com", "password": "wrongpass"})
    assert res.status_code == 401

def test_logout_clears_cookie(client):
    client.post("/auth/register", json={"email": "logout@test.com", "password": "password123"})
    res = client.post("/auth/logout")
    assert res.status_code == 200
    # cookie access_token deve essere vuoto o scaduto
    assert res.cookies.get("access_token", "") == ""
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
pytest tests/test_auth.py -v
# Expected: ERROR (router non esiste)
```

- [ ] **Step 3: Scrivi `backend/app/auth/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import User, Profile
from app.schemas import RegisterRequest, LoginRequest
from app.auth.service import hash_password, verify_password, create_token
from app.auth.dependencies import get_current_user

router = APIRouter()

COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=False, max_age=3600 * 24 * 7)

@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    profile = Profile(user_id=user.id)
    db.add(profile)
    db.commit()
    db.refresh(user)
    response.set_cookie("access_token", f"Bearer {create_token(user.id)}", **COOKIE_OPTS)
    return {"message": "registered"}

@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie("access_token", f"Bearer {create_token(user.id)}", **COOKIE_OPTS)
    return {"message": "logged in"}

@router.post("/logout")
def logout(response: Response, _=Depends(get_current_user)):
    response.delete_cookie("access_token")
    return {"message": "logged out"}
```

- [ ] **Step 4: Esegui i test — devono passare**

```bash
pytest tests/test_auth.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/router.py backend/tests/test_auth.py
git commit -m "feat: auth router register/login/logout con httpOnly cookie"
```

---

## Task 7: Profile service + router

**Files:**
- Create: `backend/app/profiles/service.py`
- Create: `backend/app/profiles/router.py`
- Create: `backend/tests/test_profiles.py`

- [ ] **Step 1: Scrivi i test per i profile**

Crea `backend/tests/test_profiles.py`:

```python
import pytest

@pytest.fixture
def auth_client(client):
    """Client con utente autenticato."""
    client.post("/auth/register", json={"email": "p@test.com", "password": "password123"})
    return client

def test_get_profile_returns_empty_for_new_user(auth_client):
    res = auth_client.get("/profiles/me")
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_step"] == 0
    assert data["age"] is None

def test_patch_profile_step1(auth_client):
    res = auth_client.patch("/profiles/me", json={"age": 32, "monthly_income": 2400, "onboarding_step": 1})
    assert res.status_code == 200
    profile = auth_client.get("/profiles/me").json()
    assert profile["age"] == 32
    assert profile["monthly_income"] == 2400
    assert profile["onboarding_step"] == 1

def test_patch_profile_step_by_step_full_onboarding(auth_client):
    steps = [
        {"age": 30, "monthly_income": 2000, "onboarding_step": 1},
        {"monthly_expenses": 1200, "onboarding_step": 2},
        {"liquid_savings": 15000, "onboarding_step": 3},
        {"existing_investments": 0, "onboarding_step": 4},
        {"goal": "growth", "horizon_years": 15, "onboarding_step": 5},
    ]
    for step in steps:
        res = auth_client.patch("/profiles/me", json=step)
        assert res.status_code == 200
    profile = auth_client.get("/profiles/me").json()
    assert profile["onboarding_step"] == 5
    assert profile["goal"] == "growth"
    assert profile["horizon_years"] == 15

def test_patch_rejects_invalid_age(auth_client):
    res = auth_client.patch("/profiles/me", json={"age": 150, "onboarding_step": 1})
    assert res.status_code == 422

def test_resume_from_step_3(auth_client):
    auth_client.patch("/profiles/me", json={"age": 28, "monthly_income": 1800, "onboarding_step": 1})
    auth_client.patch("/profiles/me", json={"monthly_expenses": 900, "onboarding_step": 2})
    auth_client.patch("/profiles/me", json={"liquid_savings": 5000, "onboarding_step": 3})
    profile = auth_client.get("/profiles/me").json()
    assert profile["onboarding_step"] == 3

def test_get_profile_requires_auth(client):
    res = client.get("/profiles/me")
    assert res.status_code == 401
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
pytest tests/test_profiles.py -v
# Expected: ERROR (router non esiste)
```

- [ ] **Step 3: Scrivi `backend/app/profiles/service.py`**

```python
from sqlalchemy.orm import Session
from app.models import Profile, User
from app.schemas import ProfilePatch

GOAL_HORIZON: dict[str, int] = {"growth": 15, "house": 5, "pension": 20}

def get_profile(db: Session, user: User) -> Profile:
    return db.get(Profile, user.id)

def upsert_profile(db: Session, user: User, patch: ProfilePatch) -> Profile:
    profile = db.get(Profile, user.id)
    data = patch.model_dump(exclude_none=True)
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
```

- [ ] **Step 4: Scrivi `backend/app/profiles/router.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import ProfilePatch, ProfileResponse
from app.auth.dependencies import get_current_user
from app.profiles.service import get_profile, upsert_profile

router = APIRouter()

@router.get("/me", response_model=ProfileResponse)
def read_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_profile(db, user)

@router.patch("/me", response_model=ProfileResponse)
def patch_profile(
    body: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upsert_profile(db, user, body)
```

- [ ] **Step 5: Esegui i test — devono passare**

```bash
pytest tests/test_profiles.py -v
# Expected: 6 passed
```

- [ ] **Step 6: Esegui tutta la suite backend**

```bash
pytest tests/ -v
# Expected: 14 passed (3 service + 5 auth + 6 profiles)
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/profiles/ backend/tests/test_profiles.py
git commit -m "feat: profile router GET+PATCH /profiles/me con salvataggio progressivo"
```

---

## Task 8: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/validation.ts`
- Create: `frontend/middleware.ts`

- [ ] **Step 1: Crea progetto Next.js**

```bash
cd /Users/maiesel/Obsidian/clara-money
npx create-next-app@15 frontend --typescript --app --no-tailwind --no-src-dir --import-alias "@/*"
cd frontend
```

- [ ] **Step 2: Installa dipendenze aggiuntive**

```bash
npm install zod
npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 3: Scrivi `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

- [ ] **Step 4: Crea `frontend/vitest.setup.ts`**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 5: Scrivi `frontend/lib/validation.ts`**

```typescript
import { z } from 'zod'

export const GOAL_HORIZON: Record<string, number> = {
  growth: 15,
  house: 5,
  pension: 20,
}

export const step1Schema = z.object({
  age: z.number().int().min(18, 'Età minima 18 anni').max(75, 'Età massima 75 anni'),
  monthly_income: z.number().int().min(1).max(50000, 'Massimo 50.000€'),
})

export const step2Schema = z.object({
  monthly_expenses: z.number().int().min(1, 'Inserisci un importo valido'),
})

export const step3Schema = z.object({
  liquid_savings: z.number().int().min(0),
})

export const step4Schema = z.object({
  existing_investments: z.number().int().min(0),
})

export const step5Schema = z.object({
  goal: z.enum(['growth', 'house', 'pension']),
})

export type StepData =
  | z.infer<typeof step1Schema>
  | z.infer<typeof step2Schema>
  | z.infer<typeof step3Schema>
  | z.infer<typeof step4Schema>
  | z.infer<typeof step5Schema>
```

- [ ] **Step 6: Scrivi `frontend/lib/api.ts`**

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? 'Request failed')
  }
  return res.json()
}
```

- [ ] **Step 7: Scrivi `frontend/middleware.ts`**

```typescript
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token')
  const isOnboarding = request.nextUrl.pathname.startsWith('/onboarding')
  const isDashboard = request.nextUrl.pathname.startsWith('/dashboard')

  if (!token && (isOnboarding || isDashboard)) {
    const url = request.nextUrl.clone()
    url.pathname = '/auth'
    url.searchParams.set('redirect', request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  if (token && request.nextUrl.pathname === '/auth') {
    return NextResponse.redirect(new URL('/onboarding', request.url))
  }
}

export const config = {
  matcher: ['/onboarding/:path*', '/dashboard/:path*', '/auth'],
}
```

- [ ] **Step 8: Verifica che Next.js si avvii**

```bash
cd frontend
npm run dev
# Apri http://localhost:3000 — deve rispondere (anche con 404, basta che il server parta)
```

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "chore: frontend scaffold — Next.js 15 + Zod + Vitest + middleware auth"
```

---

## Task 9: useWizard hook

**Files:**
- Create: `frontend/app/onboarding/useWizard.ts`
- Create: `frontend/__tests__/useWizard.test.ts`

- [ ] **Step 1: Scrivi il test per useWizard**

Crea `frontend/__tests__/useWizard.test.ts`:

```typescript
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useWizard } from '@/app/onboarding/useWizard'

const mockFetch = vi.fn()
global.fetch = mockFetch

function mockProfile(onboarding_step: number) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ onboarding_step }),
  })
}

function mockPatchOk() {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ onboarding_step: 1 }),
  })
}

function mockPatchError(status: number) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    json: async () => ({ detail: 'error' }),
  })
}

beforeEach(() => vi.clearAllMocks())

describe('useWizard', () => {
  it('starts at onboarding_step from server', async () => {
    mockProfile(2)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.currentStep).toBe(2)
  })

  it('advances step on successful PATCH', async () => {
    mockProfile(0)
    mockPatchOk()
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.next({ age: 30, monthly_income: 2000 }) })
    expect(result.current.currentStep).toBe(1)
    expect(result.current.error).toBeNull()
  })

  it('sets error on network failure without advancing', async () => {
    mockProfile(0)
    mockPatchError(500)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.next({ age: 30, monthly_income: 2000 }) })
    expect(result.current.currentStep).toBe(0)
    expect(result.current.error).toBe('Errore di rete, riprova')
  })

  it('back() decrements step without PATCH', async () => {
    mockProfile(2)
    const { result } = renderHook(() => useWizard())
    await waitFor(() => expect(result.current.loading).toBe(false))
    act(() => { result.current.back() })
    expect(result.current.currentStep).toBe(1)
    expect(mockFetch).toHaveBeenCalledTimes(1) // solo il GET iniziale
  })
})
```

- [ ] **Step 2: Esegui i test — devono fallire**

```bash
cd frontend
npx vitest run __tests__/useWizard.test.ts
# Expected: ERROR (modulo non trovato)
```

- [ ] **Step 3: Scrivi `frontend/app/onboarding/useWizard.ts`**

```typescript
'use client'
import { useState, useEffect } from 'react'
import { apiFetch, ApiError } from '@/lib/api'
import { GOAL_HORIZON, StepData } from '@/lib/validation'

type FormData = Partial<{
  age: number
  monthly_income: number
  monthly_expenses: number
  liquid_savings: number
  existing_investments: number
  goal: 'growth' | 'house' | 'pension'
  horizon_years: number
}>

interface ProfileResponse {
  onboarding_step: number
}

export function useWizard() {
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState<FormData>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<ProfileResponse>('/profiles/me')
      .then(p => setCurrentStep(p.onboarding_step))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function next(stepData: StepData) {
    setError(null)
    const newStep = currentStep + 1
    const patch: Record<string, unknown> = { ...stepData, onboarding_step: newStep }

    if ('goal' in stepData && stepData.goal) {
      patch.horizon_years = GOAL_HORIZON[stepData.goal]
    }

    try {
      await apiFetch('/profiles/me', {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setFormData(prev => ({ ...prev, ...stepData }))
      setCurrentStep(newStep)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = '/auth?redirect=/onboarding'
        return
      }
      setError('Errore di rete, riprova')
    }
  }

  function back() {
    setCurrentStep(prev => Math.max(0, prev - 1))
  }

  return { currentStep, formData, loading, error, next, back }
}
```

- [ ] **Step 4: Esegui i test — devono passare**

```bash
npx vitest run __tests__/useWizard.test.ts
# Expected: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add frontend/app/onboarding/useWizard.ts frontend/__tests__/useWizard.test.ts
git commit -m "feat: useWizard hook — state machine con resume, error handling, GOAL_HORIZON"
```

---

## Task 10: WizardProgress component

**Files:**
- Create: `frontend/app/onboarding/WizardProgress.tsx`

- [ ] **Step 1: Scrivi `frontend/app/onboarding/WizardProgress.tsx`**

```tsx
'use client'

const STEP_LABELS = [
  'Età e reddito',
  'Spese mensili',
  'Risparmi',
  'Investimenti',
  'Obiettivo',
]

interface Props {
  currentStep: number  // 0-4 (passo corrente mostrato, non completati)
  total?: number
}

export function WizardProgress({ currentStep, total = 5 }: Props) {
  return (
    <div className="wizard-progress">
      <div className="progress-header">
        <span className="progress-label">Il tuo profilo</span>
        <span className="progress-count">{currentStep + 1} / {total}</span>
      </div>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${((currentStep + 1) / total) * 100}%` }}
        />
      </div>
      <div className="progress-steps">
        {STEP_LABELS.map((label, i) => (
          <span
            key={i}
            className={
              i < currentStep ? 'step-done' :
              i === currentStep ? 'step-current' :
              'step-pending'
            }
          >
            {i < currentStep ? `✓ ${label}` : label}
          </span>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/onboarding/WizardProgress.tsx
git commit -m "feat: WizardProgress component — progress bar + step labels"
```

---

## Task 11: Step components (1–5)

**Files:**
- Create: `frontend/app/onboarding/steps/Step1.tsx`
- Create: `frontend/app/onboarding/steps/Step2.tsx`
- Create: `frontend/app/onboarding/steps/Step3.tsx`
- Create: `frontend/app/onboarding/steps/Step4.tsx`
- Create: `frontend/app/onboarding/steps/Step5.tsx`

- [ ] **Step 1: Crea directory**

```bash
mkdir -p frontend/app/onboarding/steps
```

- [ ] **Step 2: Scrivi `frontend/app/onboarding/steps/Step1.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { step1Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { age: number; monthly_income: number }) => void
  error: string | null
}

export function Step1({ onNext, error }: Props) {
  const [age, setAge] = useState('')
  const [income, setIncome] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  function handleSubmit() {
    const result = step1Schema.safeParse({
      age: Number(age),
      monthly_income: Number(income),
    })
    if (!result.success) {
      const errs: Record<string, string> = {}
      result.error.errors.forEach(e => { errs[e.path[0] as string] = e.message })
      setFieldErrors(errs)
      return
    }
    setFieldErrors({})
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanti anni hai e qual è il tuo reddito netto mensile?</h2>
      <p className="step-hint">Reddito netto = quello che ricevi in busta paga.</p>

      <div className="field">
        <label>Età</label>
        <input
          type="number"
          placeholder="es. 32"
          value={age}
          onChange={e => setAge(e.target.value)}
        />
        {fieldErrors.age && <span className="field-error">{fieldErrors.age}</span>}
      </div>

      <div className="field">
        <label>Reddito netto mensile (€)</label>
        <div className="chips">
          {['< 1.500€', '1.500–2.500€', '2.500–4.000€', '> 4.000€'].map(label => (
            <button key={label} className="chip" type="button"
              onClick={() => {
                const map: Record<string, string> = {
                  '< 1.500€': '1200', '1.500–2.500€': '2000',
                  '2.500–4.000€': '3000', '> 4.000€': '4500',
                }
                setIncome(map[label])
              }}
            >{label}</button>
          ))}
        </div>
        <input
          type="number"
          placeholder="oppure importo esatto"
          value={income}
          onChange={e => setIncome(e.target.value)}
        />
        {fieldErrors.monthly_income && <span className="field-error">{fieldErrors.monthly_income}</span>}
      </div>

      {error && <p className="api-error">{error}</p>}
      <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
    </div>
  )
}
```

- [ ] **Step 3: Scrivi `frontend/app/onboarding/steps/Step2.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { step2Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { monthly_expenses: number }) => void
  onBack: () => void
  error: string | null
}

export function Step2({ onNext, onBack, error }: Props) {
  const [expenses, setExpenses] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: '< 800€', value: '600' },
    { label: '800–1.200€', value: '1000' },
    { label: '1.200–1.800€', value: '1500' },
    { label: '> 1.800€', value: '2200' },
  ]

  function handleSubmit() {
    const result = step2Schema.safeParse({ monthly_expenses: Number(expenses) })
    if (!result.success) { setFieldError(result.error.errors[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanto spendi ogni mese?</h2>
      <p className="step-hint">Stima approssimativa — affitto, cibo, trasporti, svago.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setExpenses(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={expenses} onChange={e => setExpenses(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Scrivi `frontend/app/onboarding/steps/Step3.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { step3Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { liquid_savings: number }) => void
  onBack: () => void
  error: string | null
}

export function Step3({ onNext, onBack, error }: Props) {
  const [savings, setSavings] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: '< 5.000€', value: '3000' },
    { label: '5.000–20.000€', value: '12000' },
    { label: '20.000–50.000€', value: '35000' },
    { label: '> 50.000€', value: '60000' },
  ]

  function handleSubmit() {
    const result = step3Schema.safeParse({ liquid_savings: Number(savings) })
    if (!result.success) { setFieldError(result.error.errors[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Quanto hai risparmiato oggi?</h2>
      <p className="step-hint">Liquidità disponibile: conto corrente + conto deposito. Stima.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setSavings(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={savings} onChange={e => setSavings(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Scrivi `frontend/app/onboarding/steps/Step4.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { step4Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { existing_investments: number }) => void
  onBack: () => void
  error: string | null
}

export function Step4({ onNext, onBack, error }: Props) {
  const [investments, setInvestments] = useState('')
  const [fieldError, setFieldError] = useState('')

  const CHIPS = [
    { label: 'Nessuno (0€)', value: '0' },
    { label: '< 10.000€', value: '5000' },
    { label: '10.000–50.000€', value: '25000' },
    { label: '> 50.000€', value: '60000' },
  ]

  function handleSubmit() {
    const result = step4Schema.safeParse({ existing_investments: Number(investments) })
    if (!result.success) { setFieldError(result.error.errors[0].message); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Hai già investimenti?</h2>
      <p className="step-hint">Fondo pensione, ETF, BTP, azioni. Stima il valore totale attuale. Zero se nessuno.</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.value} className="chip" type="button" onClick={() => setInvestments(c.value)}>
            {c.label}
          </button>
        ))}
      </div>
      <input type="number" placeholder="oppure importo esatto (€)"
        value={investments} onChange={e => setInvestments(e.target.value)} />
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Avanti →</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Scrivi `frontend/app/onboarding/steps/Step5.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { step5Schema } from '@/lib/validation'

interface Props {
  onNext: (data: { goal: 'growth' | 'house' | 'pension' }) => void
  onBack: () => void
  error: string | null
}

const GOALS = [
  {
    key: 'growth' as const,
    title: 'Crescere i risparmi',
    desc: 'Voglio che i miei soldi lavorino nel lungo periodo.',
    horizon: '~15 anni',
  },
  {
    key: 'house' as const,
    title: 'Comprare casa',
    desc: 'Sto accumulando per un acquisto immobiliare.',
    horizon: '~5 anni',
  },
  {
    key: 'pension' as const,
    title: 'Pensare alla pensione',
    desc: 'Voglio costruire una rendita integrativa.',
    horizon: '~20 anni',
  },
]

export function Step5({ onNext, onBack, error }: Props) {
  const [selected, setSelected] = useState<'growth' | 'house' | 'pension' | null>(null)
  const [fieldError, setFieldError] = useState('')

  function handleSubmit() {
    const result = step5Schema.safeParse({ goal: selected })
    if (!result.success) { setFieldError('Seleziona un obiettivo per continuare.'); return }
    setFieldError('')
    onNext(result.data)
  }

  return (
    <div className="step">
      <h2>Qual è il tuo obiettivo principale?</h2>
      <p className="step-hint">Scegli quello che ti rappresenta di più.</p>
      <div className="goal-cards">
        {GOALS.map(g => (
          <button
            key={g.key}
            className={`goal-card ${selected === g.key ? 'selected' : ''}`}
            onClick={() => setSelected(g.key)}
          >
            <strong>{g.title}</strong>
            <span>{g.desc}</span>
            <small>Orizzonte temporale consigliato: {g.horizon}</small>
          </button>
        ))}
      </div>
      {fieldError && <span className="field-error">{fieldError}</span>}
      {error && <p className="api-error">{error}</p>}
      <div className="step-nav">
        <button className="btn-secondary" onClick={onBack}>← Indietro</button>
        <button className="btn-primary" onClick={handleSubmit}>Vedi i miei scenari →</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/app/onboarding/steps/
git commit -m "feat: wizard step components Step1–Step5 con chip rapidi e validazione Zod"
```

---

## Task 12: Onboarding page + Auth page + Dashboard placeholder

**Files:**
- Create: `frontend/app/onboarding/page.tsx`
- Create: `frontend/app/auth/page.tsx`
- Create: `frontend/app/dashboard/page.tsx`

- [ ] **Step 1: Scrivi `frontend/app/onboarding/page.tsx`**

```tsx
'use client'
import { useRouter } from 'next/navigation'
import { useWizard } from './useWizard'
import { WizardProgress } from './WizardProgress'
import { Step1 } from './steps/Step1'
import { Step2 } from './steps/Step2'
import { Step3 } from './steps/Step3'
import { Step4 } from './steps/Step4'
import { Step5 } from './steps/Step5'

export default function OnboardingPage() {
  const router = useRouter()
  const { currentStep, loading, error, next, back } = useWizard()

  if (loading) return <div className="loading">Caricamento...</div>
  if (currentStep >= 5) { router.replace('/dashboard'); return null }

  const stepProps = { error, onBack: back }

  return (
    <main className="onboarding-layout">
      <WizardProgress currentStep={currentStep} />
      {currentStep === 0 && <Step1 onNext={next} error={error} />}
      {currentStep === 1 && <Step2 onNext={next} {...stepProps} />}
      {currentStep === 2 && <Step3 onNext={next} {...stepProps} />}
      {currentStep === 3 && <Step4 onNext={next} {...stepProps} />}
      {currentStep === 4 && <Step5 onNext={next} {...stepProps} />}
    </main>
  )
}
```

- [ ] **Step 2: Scrivi `frontend/app/auth/page.tsx`**

```tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiFetch, ApiError } from '@/lib/api'

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'register' | 'login'>('register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiFetch(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      router.replace('/onboarding')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 409 ? 'Email già registrata — accedi.' : err.message)
      } else {
        setError('Errore di rete, riprova.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-layout">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-icon">C</span>
          <h1>Clara</h1>
        </div>
        <p className="auth-subtitle">
          {mode === 'register' ? 'Scopri cosa fare con i tuoi risparmi.' : 'Bentornato.'}
        </p>
        <div className="auth-tabs">
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
            Registrati
          </button>
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>
            Accedi
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password (min. 8 caratteri)" value={password}
            onChange={e => setPassword(e.target.value)} required />
          {error && <p className="form-error">{error}</p>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Caricamento...' : mode === 'register' ? 'Inizia gratis' : 'Accedi'}
          </button>
        </form>
      </div>
    </main>
  )
}
```

- [ ] **Step 3: Scrivi `frontend/app/dashboard/page.tsx`**

```tsx
export default function DashboardPage() {
  return (
    <main className="dashboard-placeholder">
      <h1>I tuoi scenari arrivano in M2 🚀</h1>
      <p>Profilo completato. Il simulatore finanziario sarà disponibile nella prossima milestone.</p>
    </main>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/onboarding/page.tsx frontend/app/auth/page.tsx frontend/app/dashboard/page.tsx
git commit -m "feat: onboarding page, auth page, dashboard placeholder"
```

---

## Task 13: CSS base (layout wizard)

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Sostituisci `frontend/app/globals.css`**

Il palette è chiaro e attraente (bianco caldo + verde/teal per accenti). Sostituisci il contenuto completo:

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #0f172a;
  --text-muted: #64748b;
  --accent: #059669;       /* emerald-600 */
  --accent-light: #d1fae5; /* emerald-100 */
  --accent-hover: #047857;
  --error: #dc2626;
  --radius: 10px;
  --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04);
}

body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; }

/* ── Auth ── */
.auth-layout { display: flex; align-items: center; justify-content: center;
  min-height: 100vh; padding: 24px; }
.auth-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 16px; padding: 40px; width: 100%; max-width: 400px;
  box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 20px; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand-icon { background: var(--accent); color: #fff; font-weight: 800;
  font-size: 18px; width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; }
.brand h1 { font-size: 22px; font-weight: 700; }
.auth-subtitle { color: var(--text-muted); font-size: 14px; }
.auth-tabs { display: flex; border-bottom: 2px solid var(--border); }
.auth-tabs button { flex: 1; padding: 10px; background: none; border: none;
  cursor: pointer; font-size: 14px; color: var(--text-muted);
  border-bottom: 2px solid transparent; margin-bottom: -2px; }
.auth-tabs button.active { color: var(--accent); border-bottom-color: var(--accent);
  font-weight: 600; }
form { display: flex; flex-direction: column; gap: 12px; }
form input { border: 1px solid var(--border); border-radius: var(--radius);
  padding: 11px 14px; font-size: 14px; width: 100%; outline: none; }
form input:focus { border-color: var(--accent); }
.form-error { color: var(--error); font-size: 13px; }

/* ── Onboarding layout ── */
.onboarding-layout { max-width: 540px; margin: 0 auto; padding: 40px 24px;
  display: flex; flex-direction: column; gap: 32px; }

/* ── Progress ── */
.wizard-progress { display: flex; flex-direction: column; gap: 8px; }
.progress-header { display: flex; justify-content: space-between; }
.progress-label { font-size: 12px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-muted); }
.progress-count { font-size: 12px; font-weight: 700; color: var(--accent); }
.progress-bar-track { height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: var(--accent); border-radius: 3px;
  transition: width .3s ease; }
.progress-steps { display: flex; gap: 8px; flex-wrap: wrap; }
.progress-steps span { font-size: 11px; }
.step-done { color: var(--accent); }
.step-current { color: var(--text); font-weight: 600; }
.step-pending { color: var(--border); }

/* ── Steps ── */
.step { display: flex; flex-direction: column; gap: 20px; }
.step h2 { font-size: 22px; font-weight: 700; line-height: 1.3; }
.step-hint { color: var(--text-muted); font-size: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 13px; font-weight: 600; }
.field input, .step input[type="number"] {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 11px 14px; font-size: 14px; width: 100%; outline: none; }
.field input:focus, .step input[type="number"]:focus { border-color: var(--accent); }
.field-error { color: var(--error); font-size: 12px; }
.api-error { color: var(--error); font-size: 13px;
  background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 14px; }

/* ── Chips ── */
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { background: var(--surface); border: 1px solid var(--border); border-radius: 20px;
  padding: 6px 14px; font-size: 13px; cursor: pointer; transition: all .15s; }
.chip:hover { border-color: var(--accent); color: var(--accent); }
.chip.selected { background: var(--accent-light); border-color: var(--accent);
  color: var(--accent); font-weight: 600; }

/* ── Goal cards ── */
.goal-cards { display: flex; flex-direction: column; gap: 12px; }
.goal-card { background: var(--surface); border: 2px solid var(--border);
  border-radius: 12px; padding: 18px; text-align: left; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; transition: all .15s; }
.goal-card:hover { border-color: var(--accent); }
.goal-card.selected { border-color: var(--accent); background: var(--accent-light); }
.goal-card strong { font-size: 15px; }
.goal-card span { font-size: 13px; color: var(--text-muted); }
.goal-card small { font-size: 12px; color: var(--accent); margin-top: 4px; }

/* ── Nav ── */
.step-nav { display: flex; justify-content: space-between; align-items: center; }
.btn-primary { background: var(--accent); color: #fff; border: none;
  border-radius: var(--radius); padding: 12px 24px; font-size: 14px;
  font-weight: 600; cursor: pointer; transition: background .15s; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary { background: none; border: 1px solid var(--border); color: var(--text-muted);
  border-radius: var(--radius); padding: 11px 20px; font-size: 14px; cursor: pointer; }
.btn-secondary:hover { border-color: var(--text-muted); }

/* ── Dashboard placeholder ── */
.dashboard-placeholder { display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 100vh; gap: 12px; padding: 24px; text-align: center; }
.dashboard-placeholder h1 { font-size: 24px; }
.dashboard-placeholder p { color: var(--text-muted); }

/* ── Loading ── */
.loading { display: flex; align-items: center; justify-content: center;
  min-height: 100vh; color: var(--text-muted); }
```

- [ ] **Step 2: Verifica visivamente**

```bash
cd frontend && npm run dev
# Apri http://localhost:3000/auth
# Verifica: card bianca, bottone verde, testo leggibile e attraente
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: CSS base — palette chiaro emerald, wizard layout, chip, goal cards"
```

---

## Task 14: Smoke test integrato + .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Crea `.gitignore` root**

```
backend/.venv/
backend/__pycache__/
backend/.pytest_cache/
frontend/.next/
frontend/node_modules/
.superpowers/
.env
*.pyc
```

- [ ] **Step 2: Esegui suite backend completa**

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
# Expected: 14 passed
```

- [ ] **Step 3: Esegui suite frontend**

```bash
cd frontend
npx vitest run
# Expected: 4 passed (useWizard tests)
```

- [ ] **Step 4: Test manuale happy path**

```bash
# Terminal 1: backend
cd backend && uvicorn app.main:app --reload

# Terminal 2: frontend
cd frontend && npm run dev
```

Passi da verificare manualmente:
1. Apri `http://localhost:3000` → redirect a `/auth`
2. Registrati con email + password → redirect a `/onboarding`
3. Completa i 5 step → redirect a `/dashboard`
4. Ricarica la pagina → nessun redirect (cookie JWT valido)
5. Apri `/onboarding` → redirect a `/dashboard` (step=5)

- [ ] **Step 5: Commit finale**

```bash
git add .gitignore
git commit -m "chore: .gitignore — esclude venv, node_modules, .next, .superpowers"
```

---

## Riepilogo task e ordine

| # | Task | File chiave | Test |
|---|------|-------------|------|
| 1 | Backend scaffold | main.py, config.py, database.py | — |
| 2 | DB models + Alembic | models.py, 001_initial.py | — |
| 3 | Test fixtures | conftest.py | — |
| 4 | Auth service + schemas | auth/service.py, schemas.py | test_auth_service.py |
| 5 | Auth dependencies | auth/dependencies.py | (coperto da Task 6) |
| 6 | Auth router | auth/router.py | test_auth.py |
| 7 | Profile service + router | profiles/service.py, profiles/router.py | test_profiles.py |
| 8 | Frontend scaffold | lib/api.ts, lib/validation.ts, middleware.ts | — |
| 9 | useWizard hook | useWizard.ts | useWizard.test.ts |
| 10 | WizardProgress | WizardProgress.tsx | — |
| 11 | Step components 1–5 | steps/Step1-5.tsx | — |
| 12 | Pages | onboarding/page.tsx, auth/page.tsx, dashboard/page.tsx | — |
| 13 | CSS | globals.css | visivo |
| 14 | Smoke test + .gitignore | .gitignore | manuale |
