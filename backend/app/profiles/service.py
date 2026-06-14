from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import Profile, User
from app.schemas import ProfilePatch

GOAL_HORIZON: dict[str, int] = {"growth": 15, "house": 5, "pension": 20}

def get_profile(db: Session, user: User) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

def upsert_profile(db: Session, user: User, patch: ProfilePatch) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    data = patch.model_dump(exclude_none=True)
    # Auto-derive horizon_years from goal if not explicitly set
    if "goal" in data and "horizon_years" not in data:
        data["horizon_years"] = GOAL_HORIZON[data["goal"]]
    for field, value in data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
