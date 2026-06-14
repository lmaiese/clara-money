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
