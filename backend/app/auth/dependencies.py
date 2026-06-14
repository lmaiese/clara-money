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
