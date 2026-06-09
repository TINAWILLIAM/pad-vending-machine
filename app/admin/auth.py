"""
admin/auth.py – Admin login: validates a shared admin secret → returns JWT.

Configure in .env:
    ADMIN_SECRET=choose-a-strong-secret
    ADMIN_EMAIL=admin@yourorg.com   (optional, for display)
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from jose import jwt

from app.config import settings

router = APIRouter(prefix="/admin/auth", tags=["Admin – Auth"])


class AdminLoginRequest(BaseModel):
    secret: str


@router.post("/login", summary="Admin login – returns a JWT with role=admin")
async def admin_login(request: AdminLoginRequest):
    """
    Compare the provided secret against ADMIN_SECRET in .env.
    On match, issue a JWT that carries role='admin'.
    """
    if request.secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret.",
        )

    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": exp},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }
