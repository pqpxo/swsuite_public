from __future__ import annotations

import bcrypt
from itsdangerous import BadSignature, URLSafeSerializer

_SALT = "kicker-session"
# bcrypt only considers the first 72 bytes of the password.
_MAX_BCRYPT_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def make_session(username: str, secret: str) -> str:
    return URLSafeSerializer(secret, salt=_SALT).dumps({"u": username})


def read_session(token: str, secret: str) -> str | None:
    try:
        data = URLSafeSerializer(secret, salt=_SALT).loads(token)
        return data.get("u")
    except (BadSignature, Exception):
        return None
