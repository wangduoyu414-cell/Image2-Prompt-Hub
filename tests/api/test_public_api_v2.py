"""Offline Public API v2 tests over injected immutable Publication v2 facts."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Mapping

import httpx

from apps.api.assets import AssetDelivery
from apps.api.main import create_app
from apps.api.repository import AssetLocator
from apps.api.repository_v2 import PublicReadRepositoryV2
from content.publication_v2 import freeze_candidate, publication_v2_digest


PNG = b"\x89PNG\r\n\x1a\npublication-v2"
PRIMARY = hashlib.sha256(PNG).hexdigest()
GALLERY = hashlib.sha256(b"gallery-v2").hexdigest()


class Reader:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def inspect_current(self) -> Mapping[str, Any]:
        return self.payload

    def locate_asset(self, content_sha256: str) -> AssetLocator:
        if content_sha256 != PRIMARY:
            from apps.api.repository import AssetNotAuthorized

            raise AssetNotAuthorized()
        return AssetLocator(PRIMARY, "private", "sha256/primary", "image/png", len(PNG))


class Store:
    def read(self, locator: AssetLocator) -> AssetDelivery:
        return AssetDelivery(PNG, "image/png", PRIMARY)


def entry() -> dict[str, Any]:
    candidate = {
        "schema_version": "public-case-candidate/v2",
        "state": "publishable",
        "source_case": {
            "source_case_version_id": 7,
            "source_id": "source-a",
            "repository_id": "github:source/a",
            "revision_sha": "b" * 40,
            "source_case_key": "case-1",
        },
        "prompt": {
            "prompt_id": "prompt-1",
            "raw_text": "Create one public multi-image design.",
            "language": "en",
            "source_path": "cases/one.json",
            "source_url": "https://example.invalid/cases/one.json",
        },
        "tags": ["studio", "multi-output"],
        "generation_members": [
            {
                "generation_example_row_id": 11,
                "generation_example_id": "generation:1",
                "source_claim": {"evidence_status": "source_claimed", "model_raw": "gpt-image-2"},
                "reference_inputs": [{"redacted": True}],
                "public_outputs": [
                    {
                        "generation_output_id": 101,
                        "ordinal": 0,
                        "source_role": "output_primary",
                        "public_display_role": "public_primary",
                        "content_sha256": PRIMARY,
                        "media_type": "image/png",
                        "byte_size": len(PNG),
                        "source_path": "assets/primary.png",
                        "source_url": "https://example.invalid/assets/primary.png",
                        "source_location": {"source_path": "assets/primary.png"},
                        "rights": {"asset_rights": "approved", "display_policy": "mirror_allowed"},
                    },
                    {
                        "generation_output_id": 102,
                        "ordinal": 1,
                        "source_role": "output_secondary",
                        "public_display_role": "public_gallery",
                        "content_sha256": GALLERY,
                        "media_type": "image/png",
                        "byte_size": 900,
                        "source_path": "assets/gallery.png",
                        "source_url": "https://example.invalid/assets/gallery.png",
                        "source_location": {"source_path": "assets/gallery.png"},
                        "rights": {"asset_rights": "approved", "display_policy": "link_only"},
                    },
                ],
                "hidden_outputs": [{"redacted": True}],
            }
        ],
        "rights_review": {
            "rights_review_batch_id": 5,
            "repository_license": "MIT",
            "prompt_rights": "approved",
            "author": "Author",
            "original_url": "https://example.invalid/original",
            "evidence_url": "https://example.invalid/evidence",
            "reviewer": "reviewer",
            "reviewed_at": "2026-08-11T00:00:00+00:00",
        },
        "candidate_content_digest": "c" * 64,
    }
    return freeze_candidate(candidate)


def active() -> dict[str, Any]:
    rows = [entry()]
    return {
        "state": "active",
        "publication_version": {
            "publication_version_v2_id": 1,
            "content_digest": publication_v2_digest(rows),
            "included_count": 1,
            "excluded_count": 0,
            "reason_counts": {},
            "created_by": "operator",
            "completed_at": "2026-08-11T00:00:00+00:00",
        },
        "entries": rows,
    }


def request(app: Any, url: str) -> httpx.Response:
    async def invoke() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(url)

    return asyncio.run(invoke())


def test_v2_list_detail_multi_image_and_asset_authorization_are_independent_from_v1() -> None:
    repository = PublicReadRepositoryV2(Reader(active()))
    app = create_app(repository_v2=repository, asset_store=Store())

    listing = request(app, "/api/v2/cases")
    assert listing.status_code == 200
    assert listing.json()["cases"][0]["public_output_count"] == 2
    assert listing.json()["cases"][0]["tags"] == ["multi-output", "studio"]
    assert listing.json()["cases"][0]["primary_output"]["public_display_role"] == "public_primary"

    key = entry()["public_case_key"]
    detail = request(app, f"/api/v2/cases/{key}")
    assert detail.status_code == 200
    case = detail.json()["case"]
    assert case["generation_members"][0]["reference_input_count"] == 1
    assert case["generation_members"][0]["hidden_output_count"] == 1
    assert len(case["generation_members"][0]["public_outputs"]) == 2
    rendered = detail.text
    for forbidden in ("object_key", "object_bucket", "source_case_version_id", "rights_review_batch_id", "reviewer"):
        assert forbidden not in rendered

    allowed = request(app, f"/api/v2/assets/{PRIMARY}")
    assert allowed.status_code == 200 and allowed.content == PNG
    denied = request(app, f"/api/v2/assets/{GALLERY}")
    assert denied.status_code == 404


def test_v2_empty_current_is_stable_and_openapi_remains_read_only() -> None:
    empty = {"state": "no_current", "publication_version": None, "entries": []}
    app = create_app(repository_v2=PublicReadRepositoryV2(Reader(empty)), asset_store=Store())
    assert request(app, "/api/v2/publication").json() == {"state": "no_current", "publication": None, "case_count": 0}
    assert request(app, "/api/v2/cases").json()["cases"] == []
    openapi = request(app, "/openapi.json").json()
    assert "/api/v1/cases" in openapi["paths"] and "/api/v2/cases" in openapi["paths"]
    assert all(set(item).issubset({"get", "head"}) for item in openapi["paths"].values())


def test_v2_snapshot_with_internal_identity_or_impossible_candidate_fails_closed() -> None:
    payload = active()
    payload["entries"][0]["rights_review"]["reviewer"] = "internal-login"
    app = create_app(repository_v2=PublicReadRepositoryV2(Reader(payload)), asset_store=Store())
    response = request(app, "/api/v2/cases")
    assert response.status_code == 503
    assert "internal-login" not in response.text

    impossible = active()
    impossible["entries"][0]["generation_members"][0]["public_outputs"] = []
    impossible["publication_version"]["content_digest"] = publication_v2_digest(impossible["entries"])
    app = create_app(repository_v2=PublicReadRepositoryV2(Reader(impossible)), asset_store=Store())
    assert request(app, "/api/v2/cases").status_code == 503
