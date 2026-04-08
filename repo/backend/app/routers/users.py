from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password
from app.core.dependencies import get_current_user, require_role
from app.core.encrypted_type import email_hash as _email_hash
from app.schemas.user import UserCreate, UserUpdate, UserResponse


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=10, description="Min 10 characters")

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    h = _email_hash(payload.email)
    existing = db.execute(
        select(User).where(
            (User.username == payload.username) | (User.email_hash == h)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already in use",
        )
    user = User(
        username=payload.username,
        email=payload.email,
        email_hash=h,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    skip: int = 0,
    limit: int = 100,
):
    users = db.execute(select(User).offset(skip).limit(limit)).scalars().all()
    return users


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.email is not None:
        current_user.email = payload.email
        current_user.email_hash = _email_hash(payload.email)
    if payload.password is not None:
        current_user.hashed_password = hash_password(payload.password)
    # Non-admin cannot change their own role or active status
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.email is not None:
        user.email = payload.email
        user.email_hash = _email_hash(payload.email)
    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the authenticated user's own password.  Audited; invalidates all sessions."""
    from app.core.audit import audit
    from app.models.audit import AuditEventType

    if not verify_password(payload.current_password, current_user.hashed_password):
        audit(db, AuditEventType.login_failure,
              user_id=current_user.id, username=current_user.username,
              ip=request.client.host if request.client else None,
              detail="wrong current_password on change-password")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Current password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    # Rotate session hash → forces re-login on all devices
    current_user.session_token_hash = None
    db.commit()

    audit(db, AuditEventType.password_change,
          user_id=current_user.id, username=current_user.username,
          ip=request.client.host if request.client else None,
          detail="password changed; all sessions invalidated")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()
