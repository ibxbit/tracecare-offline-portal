from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://tracecare:tracecare@localhost:5432/tracecare"
    SECRET_KEY: str = "change-me-32-char-secret-key-here-00"
    ENCRYPTION_KEY: str = "Xk5MdUQ3c3pZSmtkekFLQ0lDN0NJcTlUMVVsR3BaTks="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_HOURS: int = 12

    # Local filesystem paths for uploaded files (created on first use).
    ATTACHMENTS_DIR: str = "./uploads/catalog"
    REVIEW_IMAGES_DIR: str = "./uploads/reviews"

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


settings = Settings()
