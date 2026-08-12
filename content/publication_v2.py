"""Pure Publication v2 policy over reviewed Public Case Candidate documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .publication import json_digest, stable_json


class PublicationV2PolicyError(ValueError):
    """A Candidate v2 document cannot become a public snapshot entry."""


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicationV2PolicyError(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PublicationV2PolicyError(f"{label} must be an array")
    return list(value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PublicationV2PolicyError(f"{label} must be nonempty text")
    return value


def freeze_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact immutable public snapshot for one publishable Candidate."""

    document = _mapping(candidate, "candidate")
    if document.get("schema_version") != "public-case-candidate/v2":
        raise PublicationV2PolicyError("candidate schema version is unsupported")
    if document.get("state") != "publishable":
        raise PublicationV2PolicyError("only publishable Candidate v2 documents may be frozen")
    source_case = _mapping(document.get("source_case"), "candidate.source_case")
    prompt = _mapping(document.get("prompt"), "candidate.prompt")
    review = _mapping(document.get("rights_review"), "candidate.rights_review")
    members = [_mapping(item, "candidate.generation_members item") for item in _sequence(document.get("generation_members"), "candidate.generation_members")]
    if not members:
        raise PublicationV2PolicyError("candidate must contain generation members")
    public_outputs: list[dict[str, Any]] = []
    for member in members:
        for output in _sequence(member.get("public_outputs"), "candidate public outputs"):
            public_outputs.append(_mapping(output, "candidate public output"))
    if sum(output.get("public_display_role") == "public_primary" for output in public_outputs) != 1:
        raise PublicationV2PolicyError("candidate must contain exactly one public primary")
    if any(
        output.get("rights", {}).get("asset_rights") != "approved"
        or output.get("rights", {}).get("display_policy")
        not in {"mirror_allowed", "attribution_required", "link_only"}
        for output in public_outputs
    ):
        raise PublicationV2PolicyError("every public output must retain approved public rights")
    if review.get("prompt_rights") != "approved":
        raise PublicationV2PolicyError("candidate Prompt rights must be approved")
    candidate_digest = _text(document.get("candidate_content_digest"), "candidate_content_digest")
    if len(candidate_digest) != 64:
        raise PublicationV2PolicyError("candidate_content_digest must be SHA-256 text")
    source_case_version_id = source_case.get("source_case_version_id")
    review_batch_id = review.get("rights_review_batch_id")
    if not isinstance(source_case_version_id, int) or isinstance(source_case_version_id, bool) or source_case_version_id <= 0:
        raise PublicationV2PolicyError("source_case_version_id must be positive")
    if not isinstance(review_batch_id, int) or isinstance(review_batch_id, bool) or review_batch_id <= 0:
        raise PublicationV2PolicyError("rights_review_batch_id must be positive")
    public_case_key = json_digest(
        {
            "source_id": _text(source_case.get("source_id"), "source_case.source_id"),
            "source_case_key": _text(source_case.get("source_case_key"), "source_case.source_case_key"),
        }
    )
    return {
        "schema_version": "public-case-publication-entry/v2",
        "public_case_key": public_case_key,
        "source_case_version_id": source_case_version_id,
        "rights_review_batch_id": review_batch_id,
        "source_case": source_case,
        "prompt": prompt,
        "generation_members": members,
        "rights_review": review,
        "candidate_content_digest": candidate_digest,
    }


def publication_v2_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    """Hash the complete sorted entry set, including review and output authority."""

    ordered = sorted(
        (_mapping(entry, "publication entry") for entry in entries),
        key=lambda item: _text(item.get("public_case_key"), "public_case_key"),
    )
    return json_digest(ordered)


def snapshot_digest(entry: Mapping[str, Any]) -> str:
    return json_digest(_mapping(entry, "publication entry"))


def canonical_snapshot(entry: Mapping[str, Any]) -> str:
    return stable_json(_mapping(entry, "publication entry"))
