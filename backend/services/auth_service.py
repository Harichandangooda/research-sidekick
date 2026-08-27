from __future__ import annotations

import sqlite3

from fastapi import HTTPException, status

from backend.auth import (
    create_access_token,
    get_jwt_secret_key,
    hash_password,
    validate_email,
    validate_password,
    verify_password,
)
from backend.storage import session_store


def build_auth_response(user: dict) -> dict:
    return {
        "access_token": create_access_token(user["id"], user["email"]),
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


def register_user(email: str, password: str) -> dict:
    normalized_email = validate_email(email)
    validate_password(password)
    ensure_jwt_configured()
    try:
        user = session_store.create_user(normalized_email, hash_password(password))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    return build_auth_response(user)


def login_user(email: str, password: str) -> dict:
    normalized_email = validate_email(email)
    ensure_jwt_configured()
    user_with_hash = session_store.get_user_with_password(normalized_email)
    if user_with_hash is None or not verify_password(password, user_with_hash["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return build_auth_response({"id": user_with_hash["id"], "email": user_with_hash["email"]})


def ensure_jwt_configured() -> None:
    try:
        get_jwt_secret_key()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET_KEY is not configured",
        ) from exc
