from __future__ import annotations

import pytest

from apps.admin_api.auth import (
    AdminAuthError,
    AdminAuthService,
    AdminAuthSettings,
    AdminUser,
    hash_password,
    verify_password,
)


def _service() -> AdminAuthService:
    password_hash = hash_password("correct-horse-battery", salt=b"1" * 16)
    return AdminAuthService(
        AdminAuthSettings(
            users=(AdminUser("reviewer", "reviewer", password_hash),),
            session_secret=b"s" * 32,
            allowed_origins=frozenset({"http://testserver"}),
            secure_cookies=False,
            session_ttl_seconds=60,
        )
    )


def test_scrypt_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct-horse-battery", salt=b"1" * 16)
    second = hash_password("correct-horse-battery", salt=b"2" * 16)
    assert first != second
    assert verify_password("correct-horse-battery", first)
    assert not verify_password("wrong-password-value", first)


def test_session_signature_role_and_expiry_fail_closed() -> None:
    service = _service()
    user = service.authenticate_credentials("reviewer", "correct-horse-battery", client_id="client")
    token, principal = service.issue_session(user, now=100)
    assert service.verify_session(token, now=120) == principal
    encoded, signature = token.split(".", 1)
    with pytest.raises(AdminAuthError):
        service.verify_session(f"{encoded}x.{signature}", now=120)
    with pytest.raises(AdminAuthError):
        service.verify_session(token, now=161)
    rotated = AdminAuthService(
        AdminAuthSettings(
            users=(AdminUser("reviewer", "reviewer", hash_password("rotated-password-value", salt=b"2" * 16)),),
            session_secret=b"s" * 32,
            allowed_origins=frozenset({"http://testserver"}),
            secure_cookies=False,
            session_ttl_seconds=60,
        )
    )
    with pytest.raises(AdminAuthError):
        rotated.verify_session(token, now=120)


def test_login_rate_limit_is_bounded_per_client_and_user() -> None:
    service = _service()
    for _ in range(5):
        with pytest.raises(AdminAuthError) as failure:
            service.authenticate_credentials("reviewer", "wrong-password-value", client_id="client")
        assert failure.value.error_code == "admin_credentials_invalid"
    with pytest.raises(AdminAuthError) as limited:
        service.authenticate_credentials("reviewer", "correct-horse-battery", client_id="client")
    assert limited.value.error_code == "admin_login_rate_limited"
