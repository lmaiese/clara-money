import secrets
from fastapi import HTTPException, Request
from app.config import settings


def verify_admin_secret(request: Request) -> None:
    if not settings.digest_secret:
        raise HTTPException(status_code=401, detail="Admin endpoint not configured")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth[len("Bearer "):]
    if not secrets.compare_digest(token, settings.digest_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
