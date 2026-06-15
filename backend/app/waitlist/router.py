from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.admin.router import _verify_secret
from app.database import get_db
from app.models import Waitlist

router = APIRouter()


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("/waitlist", status_code=201)
def join_waitlist(body: WaitlistRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    existing = db.query(Waitlist).filter_by(email=email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    db.add(Waitlist(email=email))
    db.commit()
    return {"message": "Subscribed successfully"}


@router.get("/admin/waitlist")
def get_waitlist(
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    entries = db.query(Waitlist).order_by(Waitlist.joined_at.desc()).all()
    return {
        "count": len(entries),
        "entries": [{"email": e.email, "joined_at": e.joined_at.isoformat()} for e in entries],
    }
