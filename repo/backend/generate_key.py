#!/usr/bin/env python3
"""
Generate secure keys for TraceCare configuration.
Run this script to generate fresh cryptographic keys before deployment.
"""
import secrets

print("=== TraceCare Key Generator ===\n")

# SECRET_KEY - 32 random bytes as hex
secret_key = secrets.token_hex(32)
print(f"SECRET_KEY={secret_key}")

# ENCRYPTION_KEY - Fernet key (urlsafe base64, 32 bytes)
try:
    from cryptography.fernet import Fernet
    encryption_key = Fernet.generate_key().decode()
    print(f"ENCRYPTION_KEY={encryption_key}")
except ImportError:
    print("Install cryptography package first: pip install cryptography")

print("\nAdd these to your .env file or docker-compose.yml environment.")
print("WARNING: Keep these keys secure and back them up!")
print("Losing the ENCRYPTION_KEY means encrypted data cannot be decrypted.")
