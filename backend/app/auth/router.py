from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Profile
from app.schemas import RegisterRequest, LoginRequest, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.auth.service import hash_password, verify_password, create_token, create_reset_token, decode_reset_token
from app.auth.email import send_reset_email
from jose import JWTError
from app.auth.dependencies import get_current_user
from app.config import settings

router = APIRouter()

COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=3600 * 24 * 7)


@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    # Check for existing email first to avoid IntegrityError rollback issues in tests
    existing = db.query(User).filter_by(email=body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
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
    user = db.query(User).filter_by(email=body.email.lower()).first()
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


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user:
        token = create_reset_token(user.id)
        reset_link = f"{settings.frontend_url}/reset-password?token={token}"
        await send_reset_email(user.email, reset_link)
    return {"message": "Se l'email esiste, riceverai un link di reset"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user_id = decode_reset_token(body.token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Token non valido o scaduto")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Password aggiornata"}
