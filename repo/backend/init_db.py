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


def create_default_admin():
    db = SessionLocal()
    try:
        existing = db.execute(
            select(User).where(User.username == "admin")
        ).scalar_one_or_none()
        if existing:
            print("Default admin user already exists. Skipping creation.")
            return
        admin_email = "admin@tracecare.local"
        admin = User(
            username="admin",
            email=admin_email,
            email_hash=_email_hash(admin_email),
            hashed_password=hash_password("Admin@123!"),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("Default admin user created:")
        print("  Username: admin")
        print("  Password: Admin@123!")
        print("  IMPORTANT: Change the password immediately after first login!")
    finally:
        db.close()


if __name__ == "__main__":
    run_migrations()
    create_default_admin()
    print("\nDatabase initialization complete.")
