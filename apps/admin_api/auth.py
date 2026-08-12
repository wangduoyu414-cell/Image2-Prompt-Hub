"""Environment-owned users, scrypt passwords, signed sessions, and CSRF policy."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping


USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
ROLES = frozenset({"viewer", "reviewer", "admin"})
SCRYPT_N = 1 << 14
SCRYPT_R = 8
SCRYPT_P = 1
SESSION_VERSION = 1
SESSION_COOKIE = "image2_admin_session"


class AdminAuthError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class AdminUser:
    username: str
    role: str
    password_hash: str


@dataclass(frozen=True)
class AdminPrincipal:
    username: str
    role: str
    csrf_token: str
    expires_at: int


@dataclass(frozen=True)
class AdminAuthSettings:
    users: tuple[AdminUser, ...]
    session_secret: bytes
    allowed_origins: frozenset[str]
    secure_cookies: bool
    session_ttl_seconds: int = 8 * 60 * 60

    @classmethod
    def from_environment(cls) -> "AdminAuthSettings":
        raw_users = os.environ.get("IMAGE2_ADMIN_USERS_JSON", "")
        raw_secret = os.environ.get("IMAGE2_ADMIN_SESSION_SECRET", "")
        raw_origins = os.environ.get("IMAGE2_ADMIN_ALLOWED_ORIGINS", "http://127.0.0.1:3000")
        secure = os.environ.get("IMAGE2_ADMIN_SECURE_COOKIES", "false").strip().casefold() == "true"
        try:
            payload = json.loads(raw_users)
        except json.JSONDecodeError as exc:
            raise AdminAuthError("admin_auth_config_invalid", "admin user configuration is invalid") from exc
        if not isinstance(payload, dict) or not payload:
            raise AdminAuthError("admin_auth_config_invalid", "at least one admin user is required")
        users: list[AdminUser] = []
        for username, value in payload.items():
            if not isinstance(username, str) or USERNAME.fullmatch(username) is None or not isinstance(value, Mapping):
                raise AdminAuthError("admin_auth_config_invalid", "admin user identity is invalid")
            role = value.get("role")
            password_hash = value.get("password_hash")
            if role not in ROLES or not isinstance(password_hash, str) or not password_hash:
                raise AdminAuthError("admin_auth_config_invalid", "admin user role or password hash is invalid")
            _parse_password_hash(password_hash)
            users.append(AdminUser(username=username, role=str(role), password_hash=password_hash))
        if len(raw_secret.encode("utf-8")) < 32:
            raise AdminAuthError("admin_auth_config_invalid", "admin session secret must contain at least 32 bytes")
        origins = frozenset(item.strip().rstrip("/") for item in raw_origins.split(",") if item.strip())
        if not origins or any(not item.startswith(("http://", "https://")) for item in origins):
            raise AdminAuthError("admin_auth_config_invalid", "admin allowed origins are invalid")
        return cls(tuple(sorted(users, key=lambda item: item.username)), raw_secret.encode("utf-8"), origins, secure)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise AdminAuthError("admin_session_invalid", "admin session is invalid") from exc


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        raise AdminAuthError("admin_password_invalid", "admin password must contain 12 to 256 characters")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(actual_salt)}${_b64(digest)}"


def _parse_password_hash(value: str) -> tuple[bytes, bytes]:
    parts = value.split("$")
    if len(parts) != 6 or parts[:4] != ["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P)]:
        raise AdminAuthError("admin_auth_config_invalid", "admin password hash policy is unsupported")
    salt, digest = _unb64(parts[4]), _unb64(parts[5])
    if len(salt) != 16 or len(digest) != 32:
        raise AdminAuthError("admin_auth_config_invalid", "admin password hash is malformed")
    return salt, digest


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 256:
        return False
    salt, expected = _parse_password_hash(encoded)
    observed = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    return hmac.compare_digest(observed, expected)


class AdminAuthService:
    def __init__(self, settings: AdminAuthSettings) -> None:
        self.settings = settings
        self._users = {item.username: item for item in settings.users}
        self._dummy_password_hash = hash_password("invalid-login-password", salt=b"\0" * 16)
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _failure_key(self, client_id: str, username: str) -> str:
        return hashlib.sha256(f"{client_id}\0{username.casefold()}".encode("utf-8")).hexdigest()

    def _assert_not_rate_limited(self, key: str, now: float) -> None:
        with self._lock:
            recent = [stamp for stamp in self._failures.get(key, []) if now - stamp < 300]
            self._failures[key] = recent
            if len(recent) >= 5:
                raise AdminAuthError("admin_login_rate_limited", "too many failed login attempts")

    def _record_failure(self, key: str, now: float) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(now)

    def authenticate_credentials(self, username: str, password: str, *, client_id: str) -> AdminUser:
        normalized = username.strip() if isinstance(username, str) else ""
        key = self._failure_key(client_id, normalized)
        now = time.time()
        self._assert_not_rate_limited(key, now)
        user = self._users.get(normalized)
        # Equalize the expensive path for unknown users without storing a reusable secret.
        encoded = user.password_hash if user is not None else self._dummy_password_hash
        if not verify_password(password, encoded) or user is None:
            self._record_failure(key, now)
            raise AdminAuthError("admin_credentials_invalid", "username or password is invalid")
        with self._lock:
            self._failures.pop(key, None)
        return user

    def issue_session(self, user: AdminUser, *, now: int | None = None) -> tuple[str, AdminPrincipal]:
        issued = int(time.time()) if now is None else int(now)
        principal = AdminPrincipal(
            username=user.username,
            role=user.role,
            csrf_token=secrets.token_urlsafe(24),
            expires_at=issued + self.settings.session_ttl_seconds,
        )
        payload = {
            "v": SESSION_VERSION,
            "sub": principal.username,
            "role": principal.role,
            "authv": hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:24],
            "csrf": principal.csrf_token,
            "iat": issued,
            "exp": principal.expires_at,
        }
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        signature = _b64(hmac.new(self.settings.session_secret, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{encoded}.{signature}", principal

    def verify_session(self, token: str | None, *, now: int | None = None) -> AdminPrincipal:
        if not isinstance(token, str) or token.count(".") != 1:
            raise AdminAuthError("admin_session_required", "admin authentication is required")
        encoded, signature = token.split(".", 1)
        expected = _b64(hmac.new(self.settings.session_secret, encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise AdminAuthError("admin_session_invalid", "admin session is invalid")
        try:
            payload = json.loads(_unb64(encoded).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdminAuthError("admin_session_invalid", "admin session is invalid") from exc
        current = int(time.time()) if now is None else int(now)
        username = payload.get("sub") if isinstance(payload, dict) else None
        role = payload.get("role") if isinstance(payload, dict) else None
        auth_version = payload.get("authv") if isinstance(payload, dict) else None
        csrf = payload.get("csrf") if isinstance(payload, dict) else None
        expires = payload.get("exp") if isinstance(payload, dict) else None
        issued = payload.get("iat") if isinstance(payload, dict) else None
        user = self._users.get(username) if isinstance(username, str) else None
        if (
            payload.get("v") != SESSION_VERSION
            or user is None
            or role != user.role
            or auth_version != hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:24]
            or not isinstance(csrf, str)
            or len(csrf) < 20
            or not isinstance(expires, int)
            or not isinstance(issued, int)
            or issued > current + 60
            or expires <= current
            or expires - issued != self.settings.session_ttl_seconds
        ):
            raise AdminAuthError("admin_session_invalid", "admin session is invalid or expired")
        return AdminPrincipal(username=user.username, role=user.role, csrf_token=csrf, expires_at=expires)

    def assert_origin(self, origin: str | None) -> None:
        normalized = origin.rstrip("/") if isinstance(origin, str) else ""
        if normalized not in self.settings.allowed_origins:
            raise AdminAuthError("admin_origin_forbidden", "request origin is not authorized")

    @staticmethod
    def assert_role(principal: AdminPrincipal, *roles: str) -> None:
        if principal.role not in roles:
            raise AdminAuthError("admin_permission_denied", "the authenticated role cannot perform this action")

    @staticmethod
    def assert_csrf(principal: AdminPrincipal, token: str | None) -> None:
        if not isinstance(token, str) or not hmac.compare_digest(token, principal.csrf_token):
            raise AdminAuthError("admin_csrf_invalid", "CSRF token is missing or invalid")


__all__ = [
    "AdminAuthError",
    "AdminAuthService",
    "AdminAuthSettings",
    "AdminPrincipal",
    "AdminUser",
    "SESSION_COOKIE",
    "hash_password",
    "verify_password",
]
