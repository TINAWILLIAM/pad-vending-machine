"""
auth_routes.py – Email OTP authentication endpoints
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from jose import jwt

from app.config import settings
from app.database import get_collection
from app.services.otp_service import generate_and_store_otp, send_otp_email, verify_otp
from app.models.user_model import TokenResponse, UserResponse
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / response schemas ─────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


# ── JWT helper ─────────────────────────────────────────────────────────────────

def _create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/send-otp", summary="Send a 4-digit OTP to the user's email")
async def send_otp(request: SendOTPRequest):
    """
    Generate a 4-digit OTP, store it with a TTL, and email it to the user.
    """
    try:
        col = get_collection("users")
        user_doc = await col.find_one({"email": request.email})
        
        if user_doc and user_doc.get("is_verified") is True:
            now = datetime.utcnow()
            user_doc = await col.find_one_and_update(
                {"email": request.email},
                {
                    "$set": {
                        "last_login": now,
                        "is_active": True
                    }
                },
                return_document=True
            )
            user_id = str(user_doc["_id"])
            token = _create_access_token({"sub": user_id, "email": request.email})
            return {
                "already_verified": True,
                "access_token": token,
                "user": UserResponse(
                    id=user_id,
                    email=user_doc["email"],
                    is_active=user_doc.get("is_active", True),
                    created_at=user_doc.get("created_at", now),
                    last_login=user_doc.get("last_login"),
                )
            }

        otp = await generate_and_store_otp(request.email)
        await send_otp_email(request.email, otp)
    except Exception as exc:
        logger.error(f"send-otp failed for {request.email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP. Please try again.",
        )
    return {
        "already_verified": False,
        "message": f"OTP sent to {request.email}. Valid for {settings.OTP_EXPIRE_MINUTES} minutes."
    }


@router.post("/verify-otp", response_model=TokenResponse, summary="Verify OTP and issue JWT")
async def verify_otp_endpoint(request: VerifyOTPRequest):
    """
    Verify the OTP. On success, upsert the user document and return a JWT.
    """
    try:
        await verify_otp(request.email, request.otp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Upsert user
    col = get_collection("users")
    now = datetime.utcnow()
    user_doc = await col.find_one_and_update(
        {"email": request.email},
        {
            "$set": {
    "last_login": now,
    "is_active": True,
    "is_verified": True
                     },
            "$setOnInsert": {"email": request.email, "created_at": now},
        },
        upsert=True,
        return_document=True,
    )

    user_id = str(user_doc["_id"])
    token = _create_access_token({"sub": user_id, "email": request.email})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_doc["email"],
            is_active=user_doc.get("is_active", True),
            created_at=user_doc.get("created_at", now),
            last_login=user_doc.get("last_login"),
        ),
    )
