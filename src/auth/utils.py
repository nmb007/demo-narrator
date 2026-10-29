"""Password hashing and JWT helpers."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from src.auth.config import auth_settings
from src.auth.exceptions import InvalidCredentials

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(*, user_id: UUID, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=auth_settings.JWT_EXP_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALG)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            auth_settings.JWT_SECRET,
            algorithms=[auth_settings.JWT_ALG],
        )
    except InvalidTokenError as exc:
        raise InvalidCredentials() from exc
