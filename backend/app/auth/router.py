from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Profile
from app.schemas import RegisterRequest, LoginRequest, UserResponse
from app.auth.service import hash_password, verify_password, create_token
from app.auth.dependencies import get_current_user
from app.config import settings

router = APIRouter()

COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=3600 * 24 * 7)


@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    # Check for existing email first to avoid IntegrityError rollback issues in tests
    existing = db.query(User).filter_by(email=body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
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


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user
