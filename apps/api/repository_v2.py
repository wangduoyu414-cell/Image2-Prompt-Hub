"""Read-only projection of the active immutable Publication v2 snapshot."""

from __future__ import annotations

import os
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from pathlib import Path

import jsonschema
import psycopg
from psycopg.rows import dict_row

from content.database import ContentDatabaseError, ContentDatabaseSettings
from content.publication_store_v2 import PublicationV2Store
from content.publication import stable_json
from content.publication_v2 import freeze_candidate, publication_v2_digest

from .repository import AssetLocator, AssetNotAuthorized, CaseNotFound, PublicationSnapshotInvalid, PublicationUnavailable


_CANDIDATE_SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
)
_CANDIDATE_VALIDATOR = jsonschema.Draft202012Validator(_CANDIDATE_SCHEMA)


class PublicationV2Reader(Protocol):
    def inspect_current(self) -> Mapping[str, Any]: ...
    def locate_asset(self, content_sha256: str) -> AssetLocator: ...


class ContentPublicationV2Repository:
    def __init__(self, database_url: str) -> None:
        try:
            settings = ContentDatabaseSettings(database_url)
            settings.validate()
        except ContentDatabaseError as exc:
            raise PublicationUnavailable("publication v2 configuration is unavailable") from exc
        self._settings = settings
        self._store = PublicationV2Store(settings)

    @classmethod
    def from_environment(cls) -> "ContentPublicationV2Repository":
        return cls(os.environ.get("PUBLIC_API_DATABASE_URL", ""))

    def inspect_current(self) -> Mapping[str, Any]:
        try:
            return self._store.inspect_current()
        except ContentDatabaseError as exc:
            raise PublicationUnavailable("publication v2 is unavailable") from exc

    def locate_asset(self, content_sha256: str) -> AssetLocator:
        try:
            with psycopg.connect(self._settings.database_url, autocommit=True, row_factory=dict_row) as conn:
                rows = conn.execute(
                    """
                    SELECT asset.content_sha256, asset.object_bucket, asset.object_key,
                           asset.media_type, asset.byte_size
                    FROM content.publication_current_v2 current
                    JOIN content.publication_versions_v2 version
                      ON version.publication_version_v2_id=current.publication_version_v2_id AND version.state='active'
                    JOIN content.publication_assets_v2 asset
                      ON asset.publication_version_v2_id=version.publication_version_v2_id
                    WHERE current.singleton=true AND asset.content_sha256=%s
                      AND asset.display_policy IN ('mirror_allowed','attribution_required')
                    """,
                    (content_sha256,),
                ).fetchall()
        except psycopg.Error as exc:
            raise PublicationUnavailable("publication v2 asset authority is unavailable") from exc
        if not rows:
            raise AssetNotAuthorized("asset is not in the current v2 publication")
        locators = {
            AssetLocator(
                content_sha256=str(row["content_sha256"]),
                bucket=str(row["object_bucket"]),
                object_key=str(row["object_key"]),
                media_type=str(row["media_type"]),
                byte_size=int(row["byte_size"]),
            )
            for row in rows
        }
        if len(locators) != 1:
            raise PublicationSnapshotInvalid("same v2 public asset has inconsistent immutable locators")
        return next(iter(locators))


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicationSnapshotInvalid(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PublicationSnapshotInvalid(f"{label} must be an array")
    return list(value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PublicationSnapshotInvalid(f"{label} must be nonempty text")
    return value


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise PublicationSnapshotInvalid(f"{label} must be an integer")
    return value


def _output(output: Mapping[str, Any]) -> dict[str, Any]:
    rights = _mapping(output.get("rights"), "output.rights")
    return {
        "content_sha256": _text(output.get("content_sha256"), "output.content_sha256"),
        "media_type": _text(output.get("media_type"), "output.media_type"),
        "byte_size": _integer(output.get("byte_size"), "output.byte_size", 1),
        "ordinal": _integer(output.get("ordinal"), "output.ordinal"),
        "source_role": _text(output.get("source_role"), "output.source_role"),
        "public_display_role": _text(output.get("public_display_role"), "output.public_display_role"),
        "source_path": _text(output.get("source_path"), "output.source_path"),
        "source_url": _text(output.get("source_url"), "output.source_url"),
        "display_policy": _text(rights.get("display_policy"), "output.display_policy"),
    }


def _validate_entry(entry: Mapping[str, Any]) -> None:
    if entry.get("schema_version") != "public-case-publication-entry/v2":
        raise PublicationSnapshotInvalid("publication v2 entry schema is unsupported")
    candidate = {
        "schema_version": "public-case-candidate/v2",
        "state": "publishable",
        "source_case": {**_mapping(entry.get("source_case"), "source_case"), "source_case_version_id": 1},
        "prompt": entry.get("prompt"),
        "tags": entry.get("tags"),
        "generation_members": [
            {**_mapping(member, "generation member"), "generation_example_row_id": index + 1}
            for index, member in enumerate(_sequence(entry.get("generation_members"), "generation_members"))
        ],
        "rights_review": {**_mapping(entry.get("rights_review"), "rights_review"), "rights_review_batch_id": 1, "reviewer": "public-projection-validator"},
        "candidate_content_digest": entry.get("candidate_content_digest"),
    }
    try:
        _CANDIDATE_VALIDATOR.validate(candidate)
        expected = freeze_candidate(candidate)
    except (jsonschema.ValidationError, ValueError) as exc:
        raise PublicationSnapshotInvalid("publication v2 entry violates Candidate v2") from exc
    if stable_json(expected) != stable_json(dict(entry)):
        raise PublicationSnapshotInvalid("publication v2 entry does not match its deterministic frozen candidate")


class PublicReadRepositoryV2:
    def __init__(self, reader: PublicationV2Reader) -> None:
        self._reader = reader

    def _current(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        raw = self._reader.inspect_current()
        state = raw.get("state")
        if state == "no_current":
            if raw.get("publication_version") is not None or raw.get("entries") not in ([], ()):
                raise PublicationSnapshotInvalid("no_current v2 response carries publication data")
            return None, []
        if state != "active":
            raise PublicationSnapshotInvalid("publication v2 state is invalid")
        publication = _mapping(raw.get("publication_version"), "publication_version")
        entries = [_mapping(item, "publication entry") for item in _sequence(raw.get("entries"), "entries")]
        for entry in entries:
            _validate_entry(entry)
        if _integer(publication.get("included_count"), "included_count") != len(entries):
            raise PublicationSnapshotInvalid("publication v2 included count drifted")
        if _text(publication.get("content_digest"), "content_digest") != publication_v2_digest(entries):
            raise PublicationSnapshotInvalid("publication v2 digest drifted")
        return publication, entries

    @staticmethod
    def _publication(publication: Mapping[str, Any] | None, case_count: int) -> dict[str, Any]:
        if publication is None:
            return {"state": "no_current", "publication": None, "case_count": case_count}
        reason_counts = _mapping(publication.get("reason_counts"), "reason_counts")
        return {
            "state": "active",
            "publication": {
                "content_digest": _text(publication.get("content_digest"), "content_digest"),
                "included_count": _integer(publication.get("included_count"), "included_count"),
                "excluded_count": _integer(publication.get("excluded_count"), "excluded_count"),
                "reason_counts": {str(key): _integer(value, "reason count") for key, value in reason_counts.items()},
                "completed_at": publication.get("completed_at"),
            },
            "case_count": case_count,
        }

    @staticmethod
    def _case(entry: Mapping[str, Any]) -> dict[str, Any]:
        source = _mapping(entry.get("source_case"), "source_case")
        prompt = _mapping(entry.get("prompt"), "prompt")
        review = _mapping(entry.get("rights_review"), "rights_review")
        members = [_mapping(item, "generation member") for item in _sequence(entry.get("generation_members"), "generation_members")]
        outputs = [
            _output(_mapping(output, "public output"))
            for member in members
            for output in _sequence(member.get("public_outputs"), "public_outputs")
        ]
        if sum(item["public_display_role"] == "public_primary" for item in outputs) != 1:
            raise PublicationSnapshotInvalid("v2 case must have exactly one public primary")
        return {
            "public_case_key": _text(entry.get("public_case_key"), "public_case_key"),
            "prompt": {
                "prompt_id": _text(prompt.get("prompt_id"), "prompt.prompt_id"),
                "raw_text": _text(prompt.get("raw_text"), "prompt.raw_text"),
                "language": _text(prompt.get("language"), "prompt.language"),
                "source_path": _text(prompt.get("source_path"), "prompt.source_path"),
                "source_url": _text(prompt.get("source_url"), "prompt.source_url"),
            },
            "source": {
                "source_id": _text(source.get("source_id"), "source.source_id"),
                "repository_id": _text(source.get("repository_id"), "source.repository_id"),
                "revision_sha": _text(source.get("revision_sha"), "source.revision_sha"),
                "source_case_key": _text(source.get("source_case_key"), "source.source_case_key"),
            },
            "rights": {
                "repository_license": _text(review.get("repository_license"), "rights.repository_license"),
                "prompt_rights": _text(review.get("prompt_rights"), "rights.prompt_rights"),
                "author": _text(review.get("author"), "rights.author"),
                "original_url": _text(review.get("original_url"), "rights.original_url"),
                "evidence_url": _text(review.get("evidence_url"), "rights.evidence_url"),
                "reviewed_at": _text(review.get("reviewed_at"), "rights.reviewed_at"),
            },
            "tags": sorted({_text(value, "public tag") for value in _sequence(entry.get("tags"), "tags")}),
            "generation_members": [
                {
                    "generation_example_id": _text(member.get("generation_example_id"), "generation_example_id"),
                    "source_claim": _mapping(member.get("source_claim"), "source_claim"),
                    "reference_input_count": len(_sequence(member.get("reference_inputs"), "reference_inputs")),
                    "hidden_output_count": len(_sequence(member.get("hidden_outputs"), "hidden_outputs")),
                    "public_outputs": [
                        _output(_mapping(output, "public output"))
                        for output in _sequence(member.get("public_outputs"), "public_outputs")
                    ],
                }
                for member in members
            ],
            "candidate_content_digest": _text(entry.get("candidate_content_digest"), "candidate_content_digest"),
        }

    def publication(self) -> dict[str, Any]:
        publication, entries = self._current()
        return self._publication(publication, len(entries))

    def list_cases(
        self,
        *,
        q: str | None,
        source: str | None,
        display_policy: str | None,
        tag: str | None,
        has_reference: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        publication, entries = self._current()
        cases = [self._case(entry) for entry in entries]
        source_facets = Counter(item["source"]["source_id"] for item in cases)
        policy_facets: Counter[str] = Counter()
        for item in cases:
            policy_facets.update(
                {
                    output["display_policy"]
                    for member in item["generation_members"]
                    for output in member["public_outputs"]
                }
            )
        reference_facets = Counter(any(member["reference_input_count"] > 0 for member in item["generation_members"]) for item in cases)
        tag_facets: Counter[str] = Counter()
        for item in cases:
            tag_facets.update(set(item["tags"]))
        filtered = []
        needle = q.casefold() if q else None
        for item in cases:
            policies = sorted({output["display_policy"] for member in item["generation_members"] for output in member["public_outputs"]})
            has_ref = any(member["reference_input_count"] > 0 for member in item["generation_members"])
            searchable = " ".join((item["prompt"]["raw_text"], item["source"]["source_id"], item["rights"]["author"])).casefold()
            if needle and needle not in searchable:
                continue
            if source and item["source"]["source_id"] != source:
                continue
            if display_policy and display_policy not in policies:
                continue
            if has_reference is not None and has_ref != has_reference:
                continue
            if tag and tag not in item["tags"]:
                continue
            filtered.append(
                {
                    "public_case_key": item["public_case_key"],
                    "prompt_preview": item["prompt"]["raw_text"][:280],
                    "source_id": item["source"]["source_id"],
                    "display_policies": policies,
                    "has_reference": has_ref,
                    "public_output_count": sum(len(member["public_outputs"]) for member in item["generation_members"]),
                    "tags": item["tags"],
                    "primary_output": next(
                        output
                        for member in item["generation_members"]
                        for output in member["public_outputs"]
                        if output["public_display_role"] == "public_primary"
                    ),
                }
            )
        start = (page - 1) * page_size
        return {
            "publication": self._publication(publication, len(cases)),
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "cases": filtered[start : start + page_size],
            "facets": {
                "sources": [{"value": key, "count": value} for key, value in sorted(source_facets.items())],
                "display_policies": [{"value": key, "count": value} for key, value in sorted(policy_facets.items())],
                "has_reference": [{"value": key, "count": value} for key, value in sorted(reference_facets.items())],
                "tags": [{"value": key, "count": value} for key, value in sorted(tag_facets.items())],
            },
        }

    def case_detail(self, public_case_key: str) -> dict[str, Any]:
        publication, entries = self._current()
        for entry in entries:
            if entry.get("public_case_key") == public_case_key:
                return {"publication": self._publication(publication, len(entries)), "case": self._case(entry)}
        raise CaseNotFound("case is absent from current publication v2")

    def locate_current_asset(self, content_sha256: str) -> AssetLocator:
        self._current()
        return self._reader.locate_asset(content_sha256)

    def readiness(self) -> str:
        publication, _ = self._current()
        return "active" if publication is not None else "no_current"
