from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:Neeraj%401907@localhost:5432/empay_db"

    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DEBUG: bool = False
    APP_NAME: str = "EmPay HRMS Backend"
    APP_VERSION: str = "1.0.0"

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your-email@gmail.com"
    SMTP_PASSWORD: str = "your-email-password"
    MAIL_FROM: str = "no-reply@empay.com"
    MAIL_FROM_NAME: str = "EmPay HRMS"
    EMAILS_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
