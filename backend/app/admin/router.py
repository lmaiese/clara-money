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
