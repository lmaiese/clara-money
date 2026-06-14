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
