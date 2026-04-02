from cryptography.fernet import Fernet
from app.config import settings


class FieldEncryptor:
    def __init__(self, key: str):
        # Ensure proper padding for base64 key
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)

    def encrypt(self, text: str) -> str:
        if not text:
            return text
        return self._fernet.encrypt(text.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ciphertext
        return self._fernet.decrypt(ciphertext.encode()).decode()


encryptor = FieldEncryptor(settings.ENCRYPTION_KEY)
