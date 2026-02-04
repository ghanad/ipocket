from __future__ import annotations

import hashlib
import secrets
from typing import Dict, Optional


_TOKENS: Dict[str, int] = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password


def create_access_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _TOKENS[token] = user_id
    return token


def get_user_id_for_token(token: str) -> Optional[int]:
    return _TOKENS.get(token)


def clear_tokens() -> None:
    _TOKENS.clear()
