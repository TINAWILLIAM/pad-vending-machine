"""
config.py – centralised settings loaded from .env
"""
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, Field, AliasChoices
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────
    APP_NAME: str = "Pad Vending Machine API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── MongoDB ────────────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "pad_vending_db"

    # ── JWT ────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-must-be-32-chars-minimum"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ── OTP ────────────────────────────────────────────────────
    OTP_EXPIRE_MINUTES: int = 10

    # ── Email (SMTP) ───────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = Field("", validation_alias=AliasChoices("SMTP_USERNAME", "EMAIL_USERNAME"))
    SMTP_PASSWORD: str = Field("", validation_alias=AliasChoices("SMTP_PASSWORD", "EMAIL_PASSWORD"))
    FROM_EMAIL: str = ""
    FROM_NAME: str = "Pad Vending Machine"

    # ── Razorpay ──────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ── ESP32 ─────────────────────────────────────────────────
    ESP32_TIMEOUT_SECONDS: int = 30
    ESP32_RETRY_ATTEMPTS: int = 3

    # ── Frontend / CORS ───────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:4200"

    # ── Admin ─────────────────────────────────────────────────
    ADMIN_SECRET: str = "admin123"
    ADMIN_URL: str = "http://localhost:4200"
    ADMIN_EMAIL: str = "admin@forher.com"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_SECRET_KEY: str = "strong_admin_secret_key"

    ALLOWED_ORIGINS: str = "http://localhost:4200,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()