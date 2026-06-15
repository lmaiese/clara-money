import secrets
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
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth[len("Bearer "):]
    if not secrets.compare_digest(token, settings.digest_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/run-digest")
async def run_digest(
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    result = await run_monthly_digest(db)
    return result
