"""Yerel CMS kullanıcıları için parola güvenliği ve erişim işlemleri."""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata

from app.database.database import SessionLocal
from app.models.user import User


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
HASH_BYTES = 64


def normalize_username(username: str) -> str:
    value = unicodedata.normalize("NFKC", username or "").strip().lower()
    if not 3 <= len(value) <= 64:
        raise ValueError("Kullanıcı adı 3 ile 64 karakter arasında olmalı.")
    return value


def hash_password(password: str) -> str:
    if len(password or "") < 8:
        raise ValueError("Parola en az 8 karakter olmalı.")

    salt = os.urandom(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=HASH_BYTES,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            salt.hex(),
            digest.hex(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt, digest = stored_hash.split("$")
        if algorithm != "scrypt":
            return False

        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest)),
        )
        return hmac.compare_digest(candidate.hex(), digest)
    except (AttributeError, TypeError, ValueError):
        return False


def create_user(username: str, password: str) -> User:
    """Yeni yerel kullanıcı oluşturur; parola hiçbir zaman düz metin saklanmaz."""
    normalized_username = normalize_username(username)
    password_hash = hash_password(password)

    db = SessionLocal()
    try:
        existing = (
            db.query(User)
            .filter(User.username == normalized_username)
            .first()
        )
        if existing is not None:
            raise ValueError("Bu kullanıcı adı zaten kayıtlı.")

        user = User(
            username=normalized_username,
            password_hash=password_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> User | None:
    """Kullanıcı adı ve parola doğruysa kullanıcıyı döndürür."""
    try:
        normalized_username = normalize_username(username)
    except ValueError:
        return None

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.username == normalized_username)
            .first()
        )
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user
    finally:
        db.close()
