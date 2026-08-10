"""Pure canonicalization, publication-gate, snapshot, and digest policy."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class PublicationPolicyError(ValueError):
    """A caller supplied incomplete or non-canonical publication facts."""


PUBLIC_DISPLAY_POLICIES = frozenset({"mirror_allowed", "attribution_required", "link_only"})


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_prompt(raw_prompt: str) -> str:
    """Normalize only Unicode, EOLs, trailing line noise, and edge whitespace.

    This intentionally does not infer syntax, rewrite parameters, translate, or
    collapse meaningful internal whitespace.  It is the minimal stable form for
    an exact canonical key while preserving the raw prompt for publication.
    """

    if not isinstance(raw_prompt, str):
        raise PublicationPolicyError("raw prompt must be text")
    normalized = unicodedata.normalize("NFC", raw_prompt).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip()


def canonical_key(
    *, raw_prompt: str, input_hashes: Sequence[str], output_hashes: Sequence[str], source_claim: Mapping[str, Any]
) -> str:
    """Return the exact-only Canonical Case key for one Generation Example."""

    normalized_prompt = normalize_prompt(raw_prompt)
    if not normalized_prompt:
        raise PublicationPolicyError("canonical key requires a non-empty prompt")
    if not isinstance(source_claim, Mapping):
        raise PublicationPolicyError("canonical key requires an object source claim")
    for label, hashes in (("input", input_hashes), ("output", output_hashes)):
        if not isinstance(hashes, Sequence) or isinstance(hashes, (str, bytes)):
            raise PublicationPolicyError(f"canonical key {label} hashes must be an ordered sequence")
        if any(not isinstance(item, str) or len(item) != 64 for item in hashes):
            raise PublicationPolicyError(f"canonical key {label} hashes must be SHA-256 text")
    return json_digest(
        {
            "raw_prompt_normalized": normalized_prompt,
            "input_content_sha256_by_ordinal": list(input_hashes),
            "output_content_sha256_by_ordinal": list(output_hashes),
            "source_claim": dict(source_claim),
        }
    )


@dataclass(frozen=True)
class GateDecision:
    included: bool
    reason_codes: tuple[str, ...]


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evaluate_publication_gate(facts: Mapping[str, Any]) -> GateDecision:
    """Evaluate every minimum publication condition with stable fail-closed codes."""

    reasons: list[str] = []
    if not facts.get("canonical_case_id"):
        reasons.append("canonical_membership_missing")
    if not _nonempty(facts.get("raw_prompt")):
        reasons.append("prompt_missing")
    outputs = facts.get("outputs")
    inputs = facts.get("inputs", [])
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)) or not outputs:
        reasons.append("output_primary_missing")
    else:
        primary = [item for item in outputs if isinstance(item, Mapping) and item.get("role") == "output_primary"]
        if not primary:
            reasons.append("output_primary_missing")
        elif any(item.get("integrity_state") != "verified" for item in primary):
            reasons.append("output_unverified")
    all_assets = list(outputs) if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes)) else []
    if isinstance(inputs, Sequence) and not isinstance(inputs, (str, bytes)):
        all_assets.extend(inputs)
    elif inputs:
        reasons.append("asset_unverified")
    if any(not isinstance(item, Mapping) or item.get("integrity_state") != "verified" for item in all_assets):
        reasons.append("asset_unverified")
    if facts.get("pairing_status") != "strong":
        reasons.append("pairing_not_strong")
    source = facts.get("source")
    if not isinstance(source, Mapping) or not all(
        _nonempty(source.get(field)) for field in ("source_id", "repository_id", "revision_sha", "source_path", "source_url")
    ):
        reasons.append("source_provenance_incomplete")
    claim = facts.get("source_claim")
    if not isinstance(claim, Mapping) or claim.get("evidence_status") not in {"unknown", "source_claimed"}:
        reasons.append("model_claim_invalid")
    elif claim.get("evidence_status") == "source_claimed" and not _nonempty(claim.get("model_raw")):
        reasons.append("model_claim_invalid")
    tags = facts.get("taxonomy")
    if isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)) and any(
        isinstance(item, Mapping) and item.get("tag_source") == "blocked" for item in tags
    ):
        reasons.append("blocked_taxonomy")
    review = facts.get("rights_review")
    if not isinstance(review, Mapping):
        reasons.append("rights_review_missing")
    else:
        if not all(_nonempty(review.get(field)) for field in ("repository_license", "author", "original_url", "evidence_url", "reviewer")):
            reasons.append("rights_review_incomplete")
        if review.get("prompt_rights") != "approved" or review.get("asset_rights") != "approved":
            reasons.append("rights_not_approved")
        if review.get("display_policy") not in PUBLIC_DISPLAY_POLICIES:
            reasons.append("display_policy_not_public")
    return GateDecision(not reasons, tuple(reasons))


def _asset_snapshot(asset: Mapping[str, Any], *, link_only: bool) -> dict[str, Any]:
    base = {
        "ordinal": asset["ordinal"],
        "role": asset["role"],
        "content_sha256": asset["content_sha256"],
        "media_type": asset["media_type"],
        "byte_size": asset["byte_size"],
        "source_path": asset["source_path"],
        "source_url": asset["source_url"],
        "source_location": dict(asset["source_location"]),
    }
    if not link_only:
        base.update({"object_key": asset["object_key"], "object_bucket": asset["object_bucket"]})
    return base


def make_publication_snapshot(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze public fields and field-level provenance without later mutable joins."""

    decision = evaluate_publication_gate(facts)
    if not decision.included:
        raise PublicationPolicyError(f"publication snapshot gate failed: {','.join(decision.reason_codes)}")
    review = facts["rights_review"]
    assert isinstance(review, Mapping)
    source = facts["source"]
    assert isinstance(source, Mapping)
    outputs = facts["outputs"]
    inputs = facts.get("inputs", [])
    assert isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes))
    assert isinstance(inputs, Sequence) and not isinstance(inputs, (str, bytes))
    link_only = review["display_policy"] == "link_only"
    source_claim = facts["source_claim"]
    assert isinstance(source_claim, Mapping)
    return {
        "schema_version": "content-publication-entry/v1",
        "canonical": {"canonical_case_id": facts["canonical_case_id"], "canonical_key": facts["canonical_key"]},
        "generation_example": {
            "generation_example_row_id": facts["generation_example_row_id"],
            "generation_example_id": facts["generation_example_id"],
        },
        "prompt": {
            "raw_text": facts["raw_prompt"],
            "provenance": {
                "prompt_record_id": facts["prompt_record_id"],
                "source_path": source["source_path"],
                "source_url": source["source_url"],
            },
        },
        "outputs": [_asset_snapshot(item, link_only=link_only) for item in outputs if isinstance(item, Mapping)],
        "inputs": [_asset_snapshot(item, link_only=link_only) for item in inputs if isinstance(item, Mapping)],
        "source": dict(source),
        "rights": {
            "rights_review_event_id": review["rights_review_event_id"],
            "repository_license": review["repository_license"],
            "prompt_rights": review["prompt_rights"],
            "asset_rights": review["asset_rights"],
            "author": review["author"],
            "original_url": review["original_url"],
            "evidence_url": review["evidence_url"],
            "reviewer": review["reviewer"],
            "reviewed_at": review["reviewed_at"],
            "display_policy": review["display_policy"],
        },
        "model": {
            "source_claim": dict(source_claim),
            "warning": "model_unknown" if source_claim.get("evidence_status") == "unknown" else "source_claimed_not_officially_verified",
        },
        "taxonomy": [dict(item) for item in facts.get("taxonomy", []) if isinstance(item, Mapping)],
    }


def publication_content_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    """Hash an order-independent canonical publication entry set."""

    ordered = sorted(
        (
            {
                "canonical_key": item["snapshot"]["canonical"]["canonical_key"],
                "generation_example_row_id": item["snapshot"]["generation_example"]["generation_example_row_id"],
                "snapshot": item["snapshot"],
            }
            for item in entries
        ),
        key=lambda item: (str(item["canonical_key"]), int(item["generation_example_row_id"])),
    )
    return json_digest(ordered)
