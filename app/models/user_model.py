"""
user_model.py – Pydantic schemas for Users
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr


class UserInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
