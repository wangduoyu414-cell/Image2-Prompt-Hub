from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from apps.admin_api.auth import AdminAuthService, AdminAuthSettings, AdminUser, hash_password
from apps.admin_api.main import create_app
from apps.api.assets import AssetDelivery
from apps.api.repository import AssetLocator
from content.review import ReviewSubmission


ASSET_BYTES = b"RIFF" + b"x" * 4 + b"WEBP" + b"admin-review-asset" * 40
ASSET_HASH = hashlib.sha256(ASSET_BYTES).hexdigest()


@dataclass
class FakeRepository:
    submitted: ReviewSubmission | None = None
    publication_action: str | None = None

    def readiness(self) -> str:
        return "ready"

    def operations_status(self) -> dict[str, Any]:
        return {"status": "ready", "eligible_source_count": 6, "sources": [], "open_alerts": [], "review_queue": {"subject_count": 0, "output_count": 0, "state_counts": {}}}

    def list_queue(self, *, state: str | None, limit: int, offset: int) -> dict[str, Any]:
        return {
            "subject_count": 1,
            "output_count": 1,
            "filtered_count": 1,
            "state_counts": {"pending": 1, "review_required": 0, "publishable": 0, "internal_only": 0, "blocked": 0},
            "items": [
                {
                    "source_case_version_id": 7,
                    "source_id": "source",
                    "source_case_key": "source:case",
                    "revision_sha": "a" * 40,
                    "prompt_preview": "Prompt",
                    "output_count": 1,
                    "state": "pending",
                    "latest_batch_id": None,
                }
            ],
            "limit": limit,
            "offset": offset,
        }

    def inspect_subject(self, source_case_version_id: int) -> dict[str, Any]:
        return {
            "state": "pending",
            "case_facts": {
                "source_case_version_id": source_case_version_id,
                "source": {"source_id": "source", "source_case_key": "source:case", "revision_sha": "a" * 40},
                "prompt": {"raw_text": "Prompt", "source_url": "https://example.com/prompt"},
                "existing_rights_evidence": {"prompt_rights_status": "unknown", "asset_rights_status": "unknown"},
                "generations": [
                    {
                        "generation_example_id": "generation:1",
                        "source_claim": {"model_raw": "gpt-image-2"},
                        "inputs": [],
                        "outputs": [
                            {
                                "generation_output_id": 11,
                                "ordinal": 0,
                                "source_role": "output_primary",
                                "content_sha256": ASSET_HASH,
                                "media_type": "image/webp",
                                "byte_size": len(ASSET_BYTES),
                                "source_path": "image.webp",
                                "source_url": "https://example.com/image.webp",
                                "source_location": {},
                            }
                        ],
                    }
                ],
            },
            "latest_review": None,
            "review_defaults": {
                "repository_license": "MIT",
                "original_url": "https://example.com/prompt",
                "evidence_url": "https://example.com/license",
                "author": None,
            },
        }

    def submit_review(self, submission: ReviewSubmission) -> dict[str, Any]:
        self.submitted = submission
        return {"status": "recorded", "review": {"rights_review_batch_id": 3, "state": "internal_only"}}

    def inspect_batch(self, batch_id: int) -> dict[str, Any]:
        return {"rights_review_batch_id": batch_id, "state": "internal_only"}

    def preview_candidate(self, source_case_version_id: int) -> dict[str, Any]:
        return {"schema_version": "public-case-candidate/v2", "source_case_version_id": source_case_version_id, "state": "pending"}

    def locate_output(self, generation_output_id: int) -> AssetLocator:
        assert generation_output_id == 11
        return AssetLocator(ASSET_HASH, "bucket", f"sha256/{ASSET_HASH}", "image/webp", len(ASSET_BYTES))

    def publication_v2_status(self) -> dict[str, Any]:
        return {
            "current": {"state": "no_current"},
            "takedowns": {"total": 0, "items": []},
            "revision_selection": {"source": "a" * 40},
        }

    def build_publication_v2(self, *, actor: str, idempotency_key: str) -> dict[str, Any]:
        self.publication_action = f"build:{actor}:{idempotency_key}"
        return {"publication_version_v2_id": 9, "state": "ready", "included_count": 0}

    def activate_publication_v2(self, version_id: int) -> dict[str, Any]:
        self.publication_action = f"activate:{version_id}"
        return {"publication_version_v2_id": version_id, "state": "active"}

    def rollback_publication_v2(self, version_id: int) -> dict[str, Any]:
        self.publication_action = f"rollback:{version_id}"
        return {"publication_version_v2_id": version_id, "state": "active"}

    def record_takedown_v2(self, **facts: Any) -> dict[str, Any]:
        self.publication_action = f"takedown:{facts['requested_by']}:{facts['scope_type']}:{facts['action']}"
        return {"status": "recorded", "takedown_request_v2_id": 4}


class FakeAssetStore:
    def read(self, locator: AssetLocator) -> AssetDelivery:
        assert locator.content_sha256 == ASSET_HASH
        return AssetDelivery(ASSET_BYTES, "image/webp", ASSET_HASH)


def _auth() -> AdminAuthService:
    return AdminAuthService(
        AdminAuthSettings(
            users=(
                AdminUser("reviewer", "reviewer", hash_password("reviewer-password-123", salt=b"r" * 16)),
                AdminUser("viewer", "viewer", hash_password("viewer-password-12345", salt=b"v" * 16)),
                AdminUser("admin", "admin", hash_password("admin-password-123456", salt=b"a" * 16)),
            ),
            session_secret=b"session-secret-for-admin-tests-1234",
            allowed_origins=frozenset({"http://testserver"}),
            secure_cookies=False,
        )
    )


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/admin/v1/session/login",
        headers={"Origin": "http://testserver"},
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _review_payload() -> dict[str, Any]:
    return {
        "source_case_version_id": 7,
        "idempotency_key": "admin-review-0001",
        "expected_latest_batch_id": None,
        "repository_license": "MIT",
        "prompt_rights": "internal_only",
        "author": "Repository author",
        "original_url": "https://example.com/prompt",
        "evidence_url": "https://example.com/license",
        "output_decisions": [
            {
                "generation_output_id": 11,
                "asset_rights": "internal_only",
                "display_policy": "internal_only",
                "public_display_role": "hidden",
                "decision_note": "Keep internal pending stronger evidence.",
            }
        ],
        "review_note": "Explicit internal-only review for test evidence.",
    }


def test_admin_api_requires_session_and_serves_authenticated_subject_assets() -> None:
    repository = FakeRepository()
    client = TestClient(create_app(auth_service=_auth(), repository=repository, asset_store=FakeAssetStore()))
    assert client.get("/api/admin/v1/review-queue").status_code == 401
    csrf = _login(client, "reviewer", "reviewer-password-123")
    session = client.get("/api/admin/v1/session")
    assert session.json()["user"] == {"username": "reviewer", "role": "reviewer"}
    assert session.json()["csrf_token"] == csrf
    assert client.get("/api/admin/v1/review-queue").json()["subject_count"] == 1
    assert client.get("/api/admin/v1/operations").json()["eligible_source_count"] == 6
    assert client.get("/api/admin/v1/review-subjects/7").json()["case_facts"]["generations"][0]["outputs"][0]["generation_output_id"] == 11
    asset = client.get("/api/admin/v1/review-assets/11")
    assert asset.status_code == 200
    assert asset.content == ASSET_BYTES
    assert asset.headers["cache-control"] == "private, no-store"


def test_review_submission_uses_authenticated_identity_and_csrf() -> None:
    repository = FakeRepository()
    client = TestClient(create_app(auth_service=_auth(), repository=repository, asset_store=FakeAssetStore()))
    csrf = _login(client, "reviewer", "reviewer-password-123")
    denied = client.post(
        "/api/admin/v1/reviews",
        headers={"Origin": "http://testserver", "X-CSRF-Token": "wrong"},
        json=_review_payload(),
    )
    assert denied.status_code == 403
    response = client.post(
        "/api/admin/v1/reviews",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        json=_review_payload(),
    )
    assert response.status_code == 200
    assert response.json()["authenticated_reviewer"] == "reviewer"
    assert repository.submitted is not None
    assert repository.submitted.reviewer == "reviewer"
    assert repository.submitted.reviewed_at.tzinfo is not None


def test_viewer_cannot_submit_and_logout_clears_session() -> None:
    client = TestClient(create_app(auth_service=_auth(), repository=FakeRepository(), asset_store=FakeAssetStore()))
    csrf = _login(client, "viewer", "viewer-password-12345")
    response = client.post(
        "/api/admin/v1/reviews",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
        json=_review_payload(),
    )
    assert response.status_code == 403
    logged_out = client.post(
        "/api/admin/v1/session/logout",
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
    )
    assert logged_out.status_code == 200
    assert client.get("/api/admin/v1/session").status_code == 401


def test_publication_and_takedown_operations_require_admin_and_bind_actor() -> None:
    repository = FakeRepository()
    client = TestClient(create_app(auth_service=_auth(), repository=repository, asset_store=FakeAssetStore()))
    reviewer_csrf = _login(client, "reviewer", "reviewer-password-123")
    denied = client.post(
        "/api/admin/v1/publication-v2/build",
        headers={"Origin": "http://testserver", "X-CSRF-Token": reviewer_csrf},
        json={"idempotency_key": "build-1"},
    )
    assert denied.status_code == 403
    client.post(
        "/api/admin/v1/session/logout",
        headers={"Origin": "http://testserver", "X-CSRF-Token": reviewer_csrf},
    )
    admin_csrf = _login(client, "admin", "admin-password-123456")
    status = client.get("/api/admin/v1/publication-v2")
    assert status.status_code == 200 and status.json()["current"]["state"] == "no_current"
    built = client.post(
        "/api/admin/v1/publication-v2/build",
        headers={"Origin": "http://testserver", "X-CSRF-Token": admin_csrf},
        json={"idempotency_key": "build-1"},
    )
    assert built.status_code == 200 and repository.publication_action == "build:admin:build-1"
    activated = client.post(
        "/api/admin/v1/publication-v2/activate",
        headers={"Origin": "http://testserver", "X-CSRF-Token": admin_csrf},
        json={"publication_version_v2_id": 9},
    )
    assert activated.status_code == 200 and repository.publication_action == "activate:9"
    takedown = client.post(
        "/api/admin/v1/takedowns-v2",
        headers={"Origin": "http://testserver", "X-CSRF-Token": admin_csrf},
        json={
            "idempotency_key": "take-1",
            "scope_type": "case",
            "scope_key": "source:case",
            "action": "remove",
            "reason_code": "request",
            "evidence_url": "https://example.com/evidence",
            "note": "Remove after verified request.",
        },
    )
    assert takedown.status_code == 200 and repository.publication_action == "takedown:admin:case:remove"
