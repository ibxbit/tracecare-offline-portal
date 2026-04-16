#!/usr/bin/env python3
"""
Initialize database: run Alembic migrations + create default admin user.
Usage: python init_db.py
"""
import subprocess
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.encrypted_type import email_hash as _email_hash
from sqlalchemy import select


def run_migrations():
    print("Running Alembic migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        print(f"Migration failed:\n{result.stderr}")
        sys.exit(1)
    print(result.stdout)
    print("Migrations applied successfully.")


DEFAULT_USERS = [
    # (username, email, password, role)
    ("admin",   "admin@example.com",   "Admin@123!",    UserRole.admin),
    ("staff",   "staff@example.com",   "Staff@123!",    UserRole.clinic_staff),
    ("catalog", "catalog@example.com", "Catalog@123!",  UserRole.catalog_manager),
    ("patient", "patient@example.com", "Patient@123!",  UserRole.end_user),
]


def create_default_users():
    """Seed the four demo users documented in the README.

    Idempotent: existing users are left alone so repeated startups are safe.
    """
    db = SessionLocal()
    try:
        for username, email, password, role in DEFAULT_USERS:
            existing = db.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if existing:
                print(f"Default user '{username}' already exists. Skipping.")
                continue
            u = User(
                username=username,
                email=email,
                email_hash=_email_hash(email),
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(u)
            print(f"Seeded default user: {username} / {password} ({role.value})")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run_migrations()
    create_default_users()
    print("\nDatabase initialization complete.")
