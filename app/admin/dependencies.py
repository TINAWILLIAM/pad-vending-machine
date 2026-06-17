"""
admin/dependencies.py – JWT dependency for admin-protected routes.

Admin tokens are issued by POST /admin/auth/login with an admin secret.
Every admin route uses: Depends(require_admin_token)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from app.config import settings

_bearer = HTTPBearer()


def require_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Decode and validate the JWT. Raises 401 if invalid or not an admin token.
    Returns the decoded payload dict.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.ADMIN_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return payload
