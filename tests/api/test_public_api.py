"""Offline API contract tests using only injected immutable-snapshot and S3 fakes."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from apps.api.assets import AssetDelivery, AssetIntegrityFailure, AssetStoreSettings, AssetStoreUnavailable
from apps.api.main import create_app
from apps.api.repository import AssetLocator, PublicReadRepository, PublicationUnavailable
from scripts import validate_public_api as public_api_validator


PNG_BYTES = b"\x89PNG\r\n\x1a\npublic-api-offline-png"
PNG_HASH = hashlib.sha256(PNG_BYTES).hexdigest()


class FakeReader:
    def __init__(self, payload: Mapping[str, Any] | Exception) -> None:
        self.payload: Mapping[str, Any] | Exception = payload
        self.calls = 0

    def inspect_current(self) -> Mapping[str, Any]:
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeStore:
    def __init__(self, delivery: AssetDelivery | Exception = AssetDelivery(PNG_BYTES, "image/png", PNG_HASH)) -> None:
        self.delivery = delivery
        self.calls: list[AssetLocator] = []

    def read(self, locator: AssetLocator) -> AssetDelivery:
        self.calls.append(locator)
        if isinstance(self.delivery, Exception):
            raise self.delivery
        return self.delivery


def _asset(content_sha256: str, *, role: str, ordinal: int, downloadable: bool = True, media_type: str = "image/png") -> dict[str, Any]:
    value: dict[str, Any] = {
        "ordinal": ordinal,
        "role": role,
        "content_sha256": content_sha256,
        "media_type": media_type,
        "byte_size": len(PNG_BYTES),
        "source_path": f"fixtures/{content_sha256[:8]}.png",
        "source_url": f"https://source.invalid/{content_sha256[:8]}.png",
        "source_location": {"source_path": f"fixtures/{content_sha256[:8]}.png"},
    }
    if downloadable:
        value.update({"object_bucket": "private-publication", "object_key": f"sha256/{content_sha256[:2]}/{content_sha256}"})
    return value


def _entry(
    *,
    canonical_key: str,
    row_id: int,
    source_id: str,
    raw_prompt: str,
    author: str,
    policy: str,
    output_hash: str,
    tag: str,
    has_reference: bool = True,
) -> dict[str, Any]:
    downloadable = policy != "link_only"
    return {
        "schema_version": "content-publication-entry/v1",
        "canonical": {"canonical_case_id": row_id, "canonical_key": canonical_key},
        "generation_example": {"generation_example_row_id": row_id, "generation_example_id": f"generation:{row_id}"},
        "prompt": {
            "raw_text": raw_prompt,
            "provenance": {"prompt_record_id": row_id, "source_path": f"cases/{row_id}.md", "source_url": f"https://source.invalid/cases/{row_id}"},
        },
        "inputs": [_asset(PNG_HASH, role="input_reference", ordinal=0, downloadable=downloadable)] if has_reference else [],
        "outputs": [_asset(output_hash, role="output_primary", ordinal=0, downloadable=downloadable)],
        "source": {
            "source_id": source_id,
            "repository_id": f"example/{source_id}",
            "revision_sha": f"{row_id:040x}",
            "source_path": f"cases/{row_id}.md",
            "source_url": f"https://source.invalid/cases/{row_id}",
        },
        "rights": {
            "rights_review_event_id": row_id,
            "repository_license": "CC-BY-4.0",
            "prompt_rights": "approved",
            "asset_rights": "approved",
            "author": author,
            "original_url": f"https://source.invalid/original/{row_id}",
            "evidence_url": "https://source.invalid/license",
            "reviewer": "human-reviewer",
            "reviewed_at": "2026-01-01T00:00:00+00:00",
            "display_policy": policy,
        },
        "model": {
            "source_claim": {
                "evidence_status": "source_claimed",
                "model_raw": "gpt-image-2",
                "parameters_raw": {"size": "1024x1024"},
            },
            "warning": "source_claimed_not_officially_verified",
        },
        "taxonomy": [
            {
                "taxonomy_version": "taxonomy-v1",
                "classifier_version": "human-v1",
                "tag_value": tag,
                "tag_source": "human",
                "confidence": 1.0,
                "evidence": {"reviewer": "human-reviewer"},
            }
        ],
    }


def _active(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state": "active",
        "publication_version": {
            "publication_version_id": 99,
            "content_digest": "a" * 64,
            "included_count": len(entries),
            "excluded_count": 0,
            "reason_counts": {},
            "completed_at": "2026-01-01T00:00:00+00:00",
        },
        "entries": entries,
    }


def _empty() -> dict[str, Any]:
    return {"state": "no_current", "publication_version": None, "entries": []}


def _example_payload() -> dict[str, Any]:
    exact_key = "a" * 64
    different_key = "b" * 64
    link_only_key = "c" * 64
    output_other = hashlib.sha256(b"offline-different-output").hexdigest()
    output_link = hashlib.sha256(b"offline-link-only-output").hexdigest()
    return _active(
        [
            _entry(
                canonical_key=exact_key,
                row_id=2,
                source_id="source-b",
                raw_prompt="Create a precise glass sculpture under soft studio light.",
                author="Author B",
                policy="attribution_required",
                output_hash=PNG_HASH,
                tag="studio",
            ),
            _entry(
                canonical_key=exact_key,
                row_id=1,
                source_id="source-a",
                raw_prompt="Create a precise glass sculpture under soft studio light.",
                author="Author A",
                policy="mirror_allowed",
                output_hash=PNG_HASH,
                tag="studio",
            ),
            _entry(
                canonical_key=different_key,
                row_id=3,
                source_id="source-c",
                raw_prompt="Create a precise glass sculpture at sunset.",
                author="Author C",
                policy="mirror_allowed",
                output_hash=output_other,
                tag="sunset",
            ),
            _entry(
                canonical_key=link_only_key,
                row_id=4,
                source_id="source-d",
                raw_prompt="Link-only historic artwork.",
                author="Author D",
                policy="link_only",
                output_hash=output_link,
                tag="history",
                has_reference=False,
            ),
        ]
    )


def _request(app: Any, method: str, url: str) -> httpx.Response:
    async def invoke() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url)

    return asyncio.run(invoke())


def _app(payload: Mapping[str, Any] | Exception, store: FakeStore | None = None) -> tuple[Any, FakeReader, FakeStore]:
    reader = FakeReader(payload)
    fake_store = store or FakeStore()
    return create_app(repository=PublicReadRepository(reader), asset_store=fake_store), reader, fake_store


def test_health_and_empty_publication_are_stable_without_a_current_version() -> None:
    app, reader, _ = _app(_empty())

    assert _request(app, "GET", "/healthz").json() == {"status": "ok"}
    assert reader.calls == 0
    assert _request(app, "GET", "/readyz").json() == {"status": "ready", "state": "no_current"}
    publication = _request(app, "GET", "/api/v1/publication")
    cases = _request(app, "GET", "/api/v1/cases")

    assert publication.status_code == 200
    assert publication.json() == {"state": "no_current", "publication": None, "case_count": 0}
    assert cases.json()["total"] == 0
    assert cases.json()["cases"] == []
    assert cases.json()["facets"] == {"sources": [], "display_policies": [], "tags": [], "has_reference": []}


def test_current_snapshot_list_search_filters_facets_and_pagination_dedupe_canonical_cases() -> None:
    app, _, _ = _app(_example_payload())

    response = _request(app, "GET", "/api/v1/cases?page=1&page_size=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["canonical_key"] for item in body["cases"]] == ["a" * 64, "b" * 64]
    assert body["cases"][0]["member_count"] == 2
    assert body["cases"][0]["source_ids"] == ["source-a", "source-b"]
    assert body["cases"][0]["display_policies"] == ["attribution_required", "mirror_allowed"]
    assert {item["value"]: item["count"] for item in body["facets"]["tags"]} == {
        "history": 1,
        "studio": 1,
        "sunset": 1,
    }
    assert {item["value"]: item["count"] for item in body["facets"]["has_reference"]} == {False: 1, True: 2}

    assert _request(app, "GET", "/api/v1/cases?q=author%20b").json()["total"] == 1
    assert _request(app, "GET", "/api/v1/cases?q=studio").json()["total"] == 1
    assert _request(app, "GET", "/api/v1/cases?source=source-c").json()["cases"][0]["canonical_key"] == "b" * 64
    assert _request(app, "GET", "/api/v1/cases?display_policy=link_only").json()["total"] == 1
    assert _request(app, "GET", "/api/v1/cases?tag=sunset&has_reference=true").json()["total"] == 1
    assert _request(app, "GET", "/api/v1/cases?has_reference=false").json()["cases"][0]["canonical_key"] == "c" * 64


def test_detail_keeps_all_public_members_but_never_exposes_internal_locators_or_row_ids() -> None:
    app, _, _ = _app(_example_payload())

    response = _request(app, "GET", f"/api/v1/cases/{'a' * 64}")
    assert response.status_code == 200
    body = response.json()
    assert body["member_count"] == 2
    assert [member["source"]["source_id"] for member in body["members"]] == ["source-a", "source-b"]
    assert body["representative"]["prompt"]["raw_text"].startswith("Create a precise")
    assert body["representative"]["model"]["warning"] == "source_claimed_not_officially_verified"
    assert body["representative"]["inputs"][0]["role"] == "input_reference"
    rendered = json.dumps(body)
    for forbidden in ("object_key", "object_bucket", "generation_example_row_id", "prompt_record_id", "rights_review_event_id"):
        assert forbidden not in rendered

    missing = _request(app, "GET", "/api/v1/cases/not-current")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "case_not_found"


def test_asset_authorization_happens_before_store_access_and_current_pointer_switch_is_observed() -> None:
    reader = FakeReader(_example_payload())
    store = FakeStore()
    app = create_app(repository=PublicReadRepository(reader), asset_store=store)

    allowed = _request(app, "GET", f"/api/v1/assets/{PNG_HASH}")
    assert allowed.status_code == 200
    assert allowed.content == PNG_BYTES
    assert allowed.headers["content-type"] == "image/png"
    assert allowed.headers["etag"] == f'"{PNG_HASH}"'
    assert allowed.headers["content-length"] == str(len(PNG_BYTES))
    assert allowed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert len(store.calls) == 1

    link_hash = hashlib.sha256(b"offline-link-only-output").hexdigest()
    for path in (f"/api/v1/assets/{link_hash}", f"/api/v1/assets/{'d' * 64}"):
        response = _request(app, "GET", path)
        assert response.status_code == 404
    assert len(store.calls) == 1

    reader.payload = _active(
        [
            _entry(
                canonical_key="e" * 64,
                row_id=10,
                source_id="source-new",
                raw_prompt="Only the atomically switched current version is visible.",
                author="Author New",
                policy="mirror_allowed",
                output_hash=PNG_HASH,
                tag="new",
            )
        ]
    )
    assert _request(app, "GET", f"/api/v1/cases/{'a' * 64}").status_code == 404
    assert _request(app, "GET", f"/api/v1/cases/{'e' * 64}").status_code == 200


def test_link_only_does_not_construct_or_call_s3_when_private_storage_is_not_configured(monkeypatch: Any) -> None:
    for name in (
        "PUBLIC_API_S3_ENDPOINT_URL",
        "PUBLIC_API_S3_ACCESS_KEY_ID",
        "PUBLIC_API_S3_SECRET_ACCESS_KEY",
        "PUBLIC_API_S3_REGION",
    ):
        monkeypatch.delenv(name, raising=False)
    reader = FakeReader(_example_payload())
    app = create_app(repository=PublicReadRepository(reader))
    link_hash = hashlib.sha256(b"offline-link-only-output").hexdigest()

    response = _request(app, "GET", f"/api/v1/assets/{link_hash}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "asset_not_found"


def test_snapshot_location_with_a_storage_locator_fails_closed_before_public_projection() -> None:
    payload = _example_payload()
    payload["entries"][0]["outputs"][0]["source_location"]["nested"] = {"bucket_name": "private/should-not-project"}
    app, _, _ = _app(payload)

    response = _request(app, "GET", "/api/v1/cases")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "publication_unavailable"
    assert "private/should-not-project" not in response.text


def test_s3_endpoint_configuration_rejects_non_loopback_http_but_allows_https_or_loopback() -> None:
    with pytest.raises(AssetStoreUnavailable):
        AssetStoreSettings(
            endpoint_url="http://objects.example.invalid",
            access_key_id="private-access",
            secret_access_key="private-secret",
        ).validate()
    AssetStoreSettings(
        endpoint_url="https://objects.example.invalid",
        access_key_id="private-access",
        secret_access_key="private-secret",
    ).validate()
    AssetStoreSettings(
        endpoint_url="http://127.0.0.1:9000",
        access_key_id="private-access",
        secret_access_key="private-secret",
    ).validate()


def test_failure_mapping_is_fail_closed_and_redacts_connection_and_storage_secrets() -> None:
    secret = "postgresql://leaked-user:leaked-password@db.invalid/private"
    unavailable_app, _, _ = _app(PublicationUnavailable(secret))
    unavailable = _request(unavailable_app, "GET", "/api/v1/cases")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "publication_unavailable"
    assert "leaked" not in unavailable.text
    assert "password" not in unavailable.text

    integrity_store = FakeStore(AssetIntegrityFailure("private-key/should-not-leak"))
    integrity_app, _, _ = _app(_example_payload(), integrity_store)
    integrity = _request(integrity_app, "GET", f"/api/v1/assets/{PNG_HASH}")
    assert integrity.status_code == 502
    assert integrity.json()["error"]["code"] == "asset_integrity_failed"
    assert "private-key" not in integrity.text

    unavailable_store = FakeStore(AssetStoreUnavailable("secret-key/should-not-leak"))
    asset_app, _, _ = _app(_example_payload(), unavailable_store)
    unavailable_asset = _request(asset_app, "GET", f"/api/v1/assets/{PNG_HASH}")
    assert unavailable_asset.status_code == 503
    assert unavailable_asset.json()["error"]["code"] == "asset_unavailable"
    assert "secret-key" not in unavailable_asset.text


def test_invalid_parameters_and_openapi_expose_only_read_operations() -> None:
    app, _, _ = _app(_example_payload())

    invalid_page = _request(app, "GET", "/api/v1/cases?page=0")
    invalid_hash = _request(app, "GET", "/api/v1/assets/not-a-hash")
    assert invalid_page.status_code == 422
    assert invalid_hash.status_code == 422
    assert invalid_page.json()["error"]["code"] == "invalid_request"
    openapi = _request(app, "GET", "/openapi.json")
    assert openapi.status_code == 200
    for path_item in openapi.json()["paths"].values():
        assert set(path_item).issubset({"get", "head"})


def test_public_api_live_validator_uses_exact_dynamic_repository_migration_manifest(tmp_path: Any) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for index in range(1, 6):
        (migrations / f"{index:04d}_future_slice.sql").write_text(f"-- migration {index}\n", encoding="utf-8")

    expected = public_api_validator._repository_migration_manifest(migrations)

    assert [item["version"] for item in expected] == [f"{index:04d}_future_slice" for index in range(1, 6)]
    initial = [{**item, "status": "verified_existing"} for item in expected]
    replay = [{**item, "status": "verified_existing"} for item in expected]
    public_api_validator._assert_migration_results(
        initial, expected, phase="initial apply", allowed_statuses={"applied", "verified_existing"}
    )
    public_api_validator._assert_migration_results(replay, expected, phase="replay", allowed_statuses={"verified_existing"})


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda rows: rows.pop(), "result count"),
        (lambda rows: rows.__setitem__(-1, {**rows[-1], "version": rows[0]["version"]}), "duplicate version"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "version": "9999_wrong"}), "version mismatch"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "checksum_sha256": "0" * 64}), "checksum mismatch"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "status": "applied"}), "unexpected status"),
    ],
)
def test_public_api_live_validator_rejects_migration_result_drift(
    tmp_path: Any, mutate, message: str
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for index in range(1, 5):
        (migrations / f"{index:04d}_slice.sql").write_text(f"-- migration {index}\n", encoding="utf-8")
    expected = public_api_validator._repository_migration_manifest(migrations)
    actual = [{**item, "status": "verified_existing"} for item in expected]
    mutate(actual)

    with pytest.raises(public_api_validator.ValidationFailure, match=message):
        public_api_validator._assert_migration_results(
            actual, expected, phase="replay", allowed_statuses={"verified_existing"}
        )
