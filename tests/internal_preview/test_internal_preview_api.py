"""Offline internal-preview API tests with injected fixed facts."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx

from apps.internal_preview.main import create_app
from apps.internal_preview.repository import (
    CURRENT_SOURCE_IDS,
    EXPECTED_CASE_COUNT,
    EXPECTED_OUTPUT_COUNT,
    EXPECTED_PROMPT_GROUP_COUNT,
    EXPECTED_QUALITY_EXCLUSION_COUNT,
    EXPECTED_VISIBLE_OUTPUT_COUNT,
    InternalPreviewRepository,
    PreviewAssetLocator,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"internal-preview" * 40
PNG_HASH = hashlib.sha256(PNG_BYTES).hexdigest()
ASSET_ID = "a" * 64


def test_current_internal_preview_contract_is_the_seven_source_v2_baseline() -> None:
    assert len(CURRENT_SOURCE_IDS) == 7
    assert "chaosrealmsai-gpt-image-2-gallery" in CURRENT_SOURCE_IDS
    assert (EXPECTED_CASE_COUNT, EXPECTED_OUTPUT_COUNT) == (3973, 9310)
    assert (EXPECTED_PROMPT_GROUP_COUNT, EXPECTED_VISIBLE_OUTPUT_COUNT, EXPECTED_QUALITY_EXCLUSION_COUNT) == (3933, 9286, 24)

    repository_root = Path(__file__).resolve().parents[2]
    runbook = (repository_root / "docs" / "content" / "internal-review-preview.md").read_text(encoding="utf-8")
    page = (repository_root / "apps" / "web" / "app" / "internal-preview" / "page.tsx").read_text(
        encoding="utf-8"
    )
    for expected in (
        "seven approved",
        "3,973",
        "9,310",
        "six-source v1 cache",
        "chaosrealmsai-gpt-image-2-gallery` | 2,460 | 7,380",
        "UV_PROJECT_ENVIRONMENT",
    ):
        assert expected in runbook
    assert "全部七个来源" in page


def repository(*, content: bytes = PNG_BYTES) -> InternalPreviewRepository:
    cases = fixture_cases()
    locator = PreviewAssetLocator(
        asset_id=ASSET_ID,
        source_id="source-a",
        revision_sha="b" * 40,
        source_path="images/one.png",
        content_sha256=PNG_HASH,
        media_type="image/png",
        byte_size=len(PNG_BYTES),
        role="output_primary",
    )
    return InternalPreviewRepository(cases=cases, assets={ASSET_ID: locator}, asset_reader=lambda _: content)


def fixture_cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "1" * 64,
            "source_id": "source-a",
            "revision_sha": "b" * 40,
            "source_case_key": "source-a:one",
            "source_url": "https://example.invalid/source-a/one",
            "prompt": "A cinematic glass pavilion above a lake",
            "language": "en",
            "model_claims": ["gpt-image-2"],
            "prompt_rights_status": "unknown",
            "asset_rights_status": "unknown",
            "review_state": "review_required",
            "outputs": [
                {
                    "asset_id": ASSET_ID,
                    "ordinal": 0,
                    "role": "output_primary",
                    "media_type": "image/png",
                    "byte_size": len(PNG_BYTES),
                    "content_sha256": PNG_HASH,
                    "source_url": "https://example.invalid/source-a/one.png",
                }
            ],
            "output_count": 1,
        },
        {
            "case_id": "2" * 64,
            "source_id": "source-b",
            "revision_sha": "c" * 40,
            "source_case_key": "source-b:two",
            "source_url": "https://example.invalid/source-b/two",
            "prompt": "Editorial poster with bold typography",
            "language": "en",
            "model_claims": [],
            "prompt_rights_status": "unknown",
            "asset_rights_status": "unknown",
            "review_state": "review_required",
            "outputs": [
                {
                    "asset_id": "d" * 64,
                    "ordinal": 0,
                    "role": "output_primary",
                    "media_type": "image/png",
                    "byte_size": len(PNG_BYTES),
                    "content_sha256": "e" * 64,
                    "source_url": "https://example.invalid/source-b/two.png",
                }
            ],
            "output_count": 1,
        },
    ]


async def request(app, method: str, path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path)


def test_internal_preview_list_is_review_required_searchable_and_paginated() -> None:
    app = create_app(repository=repository(), enforce_loopback=False)
    response = asyncio.run(request(app, "GET", "/api/internal-preview/v1/cases?q=glass&source=source-a&page=1&page_size=1"))
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "internal_review_required"
    assert "不得作为公开发布结果" in body["disclaimer"]
    assert body["total"] == 1
    assert body["case_count"] == 2
    assert body["prompt_group_count"] == 2
    assert body["visible_output_count"] == 2
    assert body["quality_exclusion_count"] == 0
    assert body["cases"][0]["review_state"] == "review_required"
    assert body["cases"][0]["outputs"][0]["asset_id"] == ASSET_ID
    assert body["cases"][0]["member_count"] == 1
    assert body["sources"] == [{"value": "source-a", "count": 1}, {"value": "source-b", "count": 1}]


def test_internal_preview_groups_exact_prompts_and_deduplicates_output_hashes() -> None:
    first = dict(fixture_cases()[0])
    duplicate = {
        **first,
        "case_id": "3" * 64,
        "source_id": "source-c",
        "revision_sha": "d" * 40,
        "source_case_key": "source-c:three",
        "source_url": "https://example.invalid/source-c/three",
    }
    locator = PreviewAssetLocator(
        asset_id=ASSET_ID,
        source_id="source-a",
        revision_sha="b" * 40,
        source_path="images/one.png",
        content_sha256=PNG_HASH,
        media_type="image/png",
        byte_size=len(PNG_BYTES),
        role="output_primary",
    )
    grouped = InternalPreviewRepository(
        cases=[first, duplicate],
        assets={ASSET_ID: locator},
        asset_reader=lambda _: PNG_BYTES,
    ).list_cases(q=None, source=None, page=1, page_size=24)
    assert grouped["case_count"] == 2
    assert grouped["prompt_group_count"] == 1
    assert grouped["cases"][0]["member_count"] == 2
    assert grouped["cases"][0]["output_count"] == 1
    assert grouped["cases"][0]["outputs"][0]["source_ids"] == ["source-a", "source-c"]
    source_filtered = InternalPreviewRepository(
        cases=[first, duplicate],
        assets={ASSET_ID: locator},
        asset_reader=lambda _: PNG_BYTES,
    ).list_cases(q=None, source="source-c", page=1, page_size=24)
    assert source_filtered["total"] == 1
    assert source_filtered["cases"][0]["output_count"] == 1


def test_internal_preview_asset_is_private_no_store_and_hash_checked() -> None:
    app = create_app(repository=repository(), enforce_loopback=False)
    response = asyncio.run(request(app, "GET", f"/api/internal-preview/v1/assets/{ASSET_ID}"))
    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-image2-preview-mode"] == "internal-review-required"

    corrupted = create_app(repository=repository(content=PNG_BYTES + b"corrupt"), enforce_loopback=False)
    failure = asyncio.run(request(corrupted, "GET", f"/api/internal-preview/v1/assets/{ASSET_ID}"))
    assert failure.status_code == 502
    assert failure.json()["error"]["code"] == "preview_asset_integrity_failed"


def test_internal_preview_unknown_asset_fails_closed() -> None:
    app = create_app(repository=repository(), enforce_loopback=False)
    response = asyncio.run(request(app, "GET", f"/api/internal-preview/v1/assets/{'f' * 64}"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "preview_asset_not_found"
