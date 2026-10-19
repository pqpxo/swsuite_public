from __future__ import annotations

from cryptography.fernet import Fernet


def generate_key() -> bytes:
    return Fernet.generate_key()


def load_key(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read().strip()


class Vault:
    def __init__(self, key: bytes) -> None:
        self._f = Fernet(key)

    def encrypt(self, value: str | None) -> bytes | None:
        if value is None:
            return None
        return self._f.encrypt(value.encode("utf-8"))

    def decrypt(self, blob: bytes | None) -> str | None:
        if blob is None:
            return None
        return self._f.decrypt(bytes(blob)).decode("utf-8")
