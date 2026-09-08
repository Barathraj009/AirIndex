"""
AirIndex India — Security core
=================================
Password hashing, JWT issuance/verification, and RBAC permission
checking.

Note on password hashing: the spec calls for passlib[bcrypt]. bcrypt
isn't installable in this offline build sandbox, so this module prefers
bcrypt via passlib **if available** at import time, and falls back to a
stdlib-only PBKDF2-HMAC-SHA256 implementation (600,000 iterations, a
NIST/OWASP-recommended iteration count for PBKDF2-SHA256 as of 2023-2024
guidance) otherwise. This fallback is itself a legitimate, secure
password hashing scheme — not a placeholder — and is what's actually
exercised by the tests in this sandbox. Once deployed with internet
access and `pip install -r requirements.txt`, this module will
transparently switch to bcrypt without any code changes elsewhere,
since callers only ever use `hash_password` / `verify_password`.

JWT is implemented with PyJWT, which *is* available in this sandbox, so
token issuance/verification here is real, executed, tested code.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import jwt  # PyJWT

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

try:
    from passlib.context import CryptContext  # type: ignore
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _USING_BCRYPT = True
except ImportError:
    _pwd_context = None
    _USING_BCRYPT = False

_PBKDF2_ITERATIONS = 600_000
_PBKDF2_ALGO = "sha256"


def hash_password(plain_password: str) -> str:
    if _USING_BCRYPT:
        return _pwd_context.hash(plain_password)  # type: ignore[union-attr]

    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, plain_password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
        except ValueError:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        derived = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected)

    # bcrypt hashes always start with one of these version prefixes.
    if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
        if _USING_BCRYPT:
            return _pwd_context.verify(plain_password, stored_hash)  # type: ignore[union-attr]
        # Hash was created by bcrypt but bcrypt isn't available to verify
        # it here (e.g. DB seeded on a machine with bcrypt, running here
        # without it) — this is an environment problem, not "wrong
        # password", so it's raised rather than silently returning False.
        raise RuntimeError("Cannot verify a bcrypt hash: passlib[bcrypt] is not installed in this environment.")

    # Not a recognized hash format at all (corrupted data, wrong field,
    # etc.) — this is invalid, not a bcrypt-availability problem.
    return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

class Role(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


# Least-privilege permission matrix. Routers check `has_permission`
# rather than hardcoding role checks inline, so the matrix is the single
# source of truth (spec section 9: "Use roles such as ADMIN, ANALYST and
# VIEWER with suitable permissions").
PERMISSIONS = {
    "view_dashboard": {Role.ADMIN, Role.ANALYST, Role.VIEWER},
    "view_data_quality": {Role.ADMIN, Role.ANALYST, Role.VIEWER},
    "view_scraping_monitor": {Role.ADMIN, Role.ANALYST, Role.VIEWER},
    "export_data": {Role.ADMIN, Role.ANALYST},
    "run_backtesting": {Role.ADMIN, Role.ANALYST},
    "trigger_ingestion": {Role.ADMIN, Role.ANALYST},
    "manage_routes": {Role.ADMIN},
    "manage_route_weights": {Role.ADMIN},
    "manage_data_sources": {Role.ADMIN},
    "manage_index_config": {Role.ADMIN},
    "manage_users": {Role.ADMIN},
    "view_audit_log": {Role.ADMIN},
}


def has_permission(role: Role, permission: str) -> bool:
    allowed_roles = PERMISSIONS.get(permission)
    if allowed_roles is None:
        raise ValueError(f"Unknown permission: {permission}")
    return role in allowed_roles


@dataclass
class TokenConfig:
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7


def create_access_token(subject: str, role: Role, config: TokenConfig,
                         extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=config.access_token_expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, config.secret_key, algorithm=config.algorithm)


def create_refresh_token(subject: str, config: TokenConfig) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=config.refresh_token_expire_days),
    }
    return jwt.encode(payload, config.secret_key, algorithm=config.algorithm)


class TokenError(Exception):
    pass


def decode_token(token: str, config: TokenConfig, expected_type: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[config.algorithm])
    except jwt.ExpiredSignatureError:
        raise TokenError("token_expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"token_invalid: {e}")

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"wrong_token_type: expected {expected_type}, got {payload.get('type')}")

    return payload
