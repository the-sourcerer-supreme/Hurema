from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:Hash123@localhost:5432/empay_db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = DEFAULT_DATABASE_URL

    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DEBUG: bool = False
    APP_NAME: str = "Hurema HRMS Backend"
    APP_VERSION: str = "1.0.0"

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]

    SMTP_SERVER: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = "no-reply@hurema.app"
    MAIL_FROM_NAME: str = "Hurema HRMS"
    EMAILS_ENABLED: bool = False
    BREVO_API_URL: str = "https://api.brevo.com/v3/smtp/email"
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = ""
    BREVO_SENDER_NAME: str = "Hurema HRMS"
    
    class Config:
        env_file = str(DEFAULT_ENV_PATH)
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
