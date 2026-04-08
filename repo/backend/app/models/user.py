import enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.core.encrypted_type import EncryptedString
from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    clinic_staff = "clinic_staff"
    catalog_manager = "catalog_manager"
    end_user = "end_user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    # email is stored Fernet-encrypted at rest; use email_hash for uniqueness checks.
    email: Mapped[str] = mapped_column(EncryptedString(500), nullable=False)
    # SHA-256 of normalised (lowercased) email — for O(1) unique/lookup queries.
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.end_user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Session & security tracking
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until
