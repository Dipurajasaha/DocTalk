from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password is required")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    if not password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False
