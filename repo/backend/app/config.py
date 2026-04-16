from pathlib import Path
from pydantic_settings import BaseSettings



import os
import sys
import secrets

class Settings(BaseSettings):
    """
    Application settings. All secrets/keys must be provided via environment variables in production.
    Fails fast if SECRET_KEY or ENCRYPTION_KEY are missing or weak (unless running tests).
    """
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://tracecare:tracecare@localhost:5432/tracecare")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_HOURS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", "12"))

    ATTACHMENTS_DIR: str = os.getenv("ATTACHMENTS_DIR", "./uploads/catalog")
    REVIEW_IMAGES_DIR: str = os.getenv("REVIEW_IMAGES_DIR", "./uploads/reviews")

    @property
    def attachments_path(self) -> Path:
        p = Path(self.ATTACHMENTS_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def review_images_path(self) -> Path:
        p = Path(self.REVIEW_IMAGES_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    class Config:
        env_file = ".env"
        extra = "ignore"


def _fail_fast_if_insecure(settings: Settings):
    # Allow insecure for pytest only
    if "pytest" in sys.modules:
        return
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32 or "change-me" in settings.SECRET_KEY:
        raise RuntimeError("SECURITY ERROR: SECRET_KEY must be set to a strong random value (>=32 chars) in .env or environment.")
    if not settings.ENCRYPTION_KEY or len(settings.ENCRYPTION_KEY) < 32:
        raise RuntimeError("SECURITY ERROR: ENCRYPTION_KEY must be set to a strong random value (>=32 chars, base64) in .env or environment.")

settings = Settings()
_fail_fast_if_insecure(settings)
