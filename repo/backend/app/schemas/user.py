from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.end_user


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str          # decrypted by EncryptedString TypeDecorator before reaching here
    role: UserRole
    is_active: bool
    created_at: datetime
    # email_hash is intentionally excluded — internal lookup field only

    model_config = {"from_attributes": True}


# Re-export UserRole for convenience
__all__ = ["UserCreate", "UserUpdate", "UserResponse", "UserRole"]
