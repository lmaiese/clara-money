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
from app.waitlist.router import router as waitlist_router
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
app.include_router(waitlist_router, tags=["waitlist"])
