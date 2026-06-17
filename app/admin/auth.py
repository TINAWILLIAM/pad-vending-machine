"""
admin/auth.py – Admin login: validates a shared admin secret or email/password -> returns JWT.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from jose import jwt

from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin – Auth"])


class AdminLoginSecretRequest(BaseModel):
    secret: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login", summary="Legacy Admin login – returns a JWT with role=admin")
async def admin_login_secret(request: AdminLoginSecretRequest):
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
        settings.ADMIN_SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/login", summary="Admin credentials login – returns JWT and admin details")
async def admin_login(request: AdminLoginRequest):
    """
    Verify email and password against ADMIN_EMAIL and ADMIN_PASSWORD.
    On success, return JWT access token and admin info details.
    """
    if request.email != settings.ADMIN_EMAIL or request.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    exp = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode(
        {"sub": "admin", "role": "admin", "email": request.email, "exp": exp},
        settings.ADMIN_SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "admin": {
            "email": request.email,
            "role": "Super Admin"
        }
    }
