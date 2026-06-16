from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.admin.digest import run_monthly_digest
from app.dependencies import verify_admin_secret

router = APIRouter(prefix="/admin")


@router.post("/run-digest")
async def run_digest(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_secret),
):
    result = await run_monthly_digest(db)
    return result
