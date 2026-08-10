"""Pure rights-review and Public Case Candidate v2 policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .publication import json_digest


PROMPT_RIGHTS = frozenset({"approved", "unknown", "internal_only", "blocked"})
ASSET_RIGHTS = PROMPT_RIGHTS
DISPLAY_POLICIES = frozenset(
    {"mirror_allowed", "attribution_required", "link_only", "internal_only", "blocked"}
)
PUBLIC_DISPLAY_POLICIES = frozenset({"mirror_allowed", "attribution_required", "link_only"})
PUBLIC_DISPLAY_ROLES = frozenset({"public_primary", "public_gallery", "hidden"})
FORBIDDEN_CANDIDATE_KEYS = frozenset(
    {
        "object_key",
        "object_bucket",
        "object_locator",
        "storage_locator",
        "storage_uri",
        "database_url",
        "secret_access_key",
        "access_key_id",
        "password",
        "credentials",
    }
)
PRIVATE_LOCATOR_PREFIXES = (
    "s3://",
    "gs://",
    "file://",
    "private://",
    "minio://",
    "azure://",
    "arn:aws:s3",
)
OBJECT_STORAGE_HOST_SUFFIXES = (
    "s3.amazonaws.com",
    "storage.googleapis.com",
    "blob.core.windows.net",
    "digitaloceanspaces.com",
    "r2.cloudflarestorage.com",
)
UNSAFE_IDENTITY_SCHEMES = frozenset(
    {
        "http", "https", "ftp", "ftps", "ws", "wss", "data", "javascript",
        "blob", "filesystem", "view-source", "s3", "gs", "file", "private", "minio", "azure",
    }
)
SENSITIVE_CREDENTIAL_MARKERS = (
    "x-amz-credential=", "x-amz-signature=", "x-amz-security-token=",
    "x-goog-credential=", "x-goog-signature=", "awsaccesskeyid=",
)


class ReviewPolicyError(ValueError):
    """A review submission or candidate fact set violates the v2 contract."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewPolicyError(f"{label} must be nonempty text")
    return value.strip()


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ReviewPolicyError(f"{label} must be a positive integer")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewPolicyError(f"{label} must be an object")
    return dict(value)


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReviewPolicyError(f"{label} must be an array")
    return list(value)


def _reject_forbidden_keys(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_CANDIDATE_KEYS:
                raise ReviewPolicyError(f"{path}.{key} is forbidden in Candidate v2 facts")
            _reject_forbidden_keys(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, path=f"{path}[{index}]")


def _reject_private_locator_values(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_private_locator_values(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _reject_private_locator_values(item, path=f"{path}[{index}]")
    elif isinstance(value, str) and value.strip().lower().startswith(PRIVATE_LOCATOR_PREFIXES):
        raise ReviewPolicyError(f"{path} contains a private object locator")


def _looks_like_legacy_ipv4_literal(hostname: str) -> bool:
    parts = hostname.split(".")
    if not 1 <= len(parts) <= 4:
        return False
    for part in parts:
        if not part:
            return False
        if part.lower().startswith("0x"):
            digits = part[2:]
            if not digits or any(character not in "0123456789abcdefABCDEF" for character in digits):
                return False
        elif not part.isdigit():
            return False
    return True


def _public_https_url(value: Any, label: str) -> str:
    url = _text(value, label)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ReviewPolicyError(f"{label} must be a public HTTPS URL without embedded credentials")
    hostname = parsed.hostname.lower()
    if parsed.netloc != parsed.netloc.lower() or parsed.query:
        raise ReviewPolicyError(f"{label} must use a lowercase host and must not contain a query string")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ReviewPolicyError(f"{label} contains an invalid port") from exc
    if port not in {None, 443}:
        raise ReviewPolicyError(f"{label} may only use the default HTTPS port")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ReviewPolicyError(f"{label} must not target localhost")
    if _looks_like_legacy_ipv4_literal(hostname):
        raise ReviewPolicyError(f"{label} must not use a numeric IP address")
    if "." not in hostname:
        raise ReviewPolicyError(f"{label} must use a public DNS hostname")
    if (
        hostname in OBJECT_STORAGE_HOST_SUFFIXES
        or any(hostname.endswith("." + suffix) for suffix in OBJECT_STORAGE_HOST_SUFFIXES)
        or (hostname.startswith("s3.") and hostname.endswith(".amazonaws.com"))
        or (".s3." in hostname and hostname.endswith(".amazonaws.com"))
    ):
        raise ReviewPolicyError(f"{label} must not target an object-storage host")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ReviewPolicyError(f"{label} must not use a literal IP address")
    _reject_private_locator_values(url, path=label)
    return url


def _public_source_path(value: Any, label: str) -> str:
    path = _text(value, label).replace("\\", "/")
    parsed = urlparse(path)
    parts = PurePosixPath(path).parts
    if parsed.scheme or path.startswith("/") or not parts or any(part in {"", ".", ".."} for part in parts):
        raise ReviewPolicyError(f"{label} must be a safe repository-relative path")
    _reject_private_locator_values(path, path=label)
    return path


def _public_metadata_text(value: Any, label: str) -> str:
    text = _text(value, label)
    parsed = urlparse(text)
    if (
        parsed.scheme
        or text.startswith("//")
        or (len(text) >= 3 and text[0].isalpha() and text[1] == ":" and text[2] in {"/", "\\"})
    ):
        raise ReviewPolicyError(f"{label} must be public metadata text, not a URL or storage locator")
    _reject_private_locator_values(text, path=label)
    return text


def _public_identity_text(value: Any, label: str) -> str:
    text = _text(value, label)
    lowered = text.lower()
    opaque_private_prefixes = ("s3:", "gs:", "file:", "private:", "minio:", "azure:", "arn:aws:s3")
    parsed = urlparse(text)
    if (
        "://" in text
        or text.startswith("//")
        or parsed.scheme.lower() in UNSAFE_IDENTITY_SCHEMES
        or any(f"{scheme}:" in lowered for scheme in UNSAFE_IDENTITY_SCHEMES)
        or lowered.startswith(opaque_private_prefixes)
        or any(suffix in lowered for suffix in OBJECT_STORAGE_HOST_SUFFIXES)
        or any(marker in lowered for marker in SENSITIVE_CREDENTIAL_MARKERS)
    ):
        raise ReviewPolicyError(f"{label} must be a public identifier, not a URL or storage locator")
    return text


def _public_source_claim(value: Any) -> dict[str, Any]:
    claim = _mapping(value, "source_claim")
    if set(claim) != {"evidence_status", "model_raw", "parameters_raw"}:
        raise ReviewPolicyError("source_claim must use the generation-example v1 fields")
    status = claim.get("evidence_status")
    if status not in {"unknown", "source_claimed"}:
        raise ReviewPolicyError("source_claim.evidence_status is unsupported")
    model_raw = claim.get("model_raw")
    if model_raw is not None and (not isinstance(model_raw, str) or not model_raw.strip()):
        raise ReviewPolicyError("source_claim.model_raw must be null or nonempty text")
    if status == "source_claimed" and model_raw is None:
        raise ReviewPolicyError("source-claimed model evidence requires model_raw")
    parameters = claim.get("parameters_raw")
    if parameters is not None and not isinstance(parameters, Mapping):
        raise ReviewPolicyError("source_claim.parameters_raw must be an object or null")
    _reject_forbidden_keys(parameters, path="source_claim.parameters_raw")
    _reject_private_locator_values(parameters, path="source_claim.parameters_raw")
    return {
        "evidence_status": status,
        "model_raw": _public_metadata_text(model_raw, "source_claim.model_raw")
        if isinstance(model_raw, str)
        else None,
    }


def _public_source_location(value: Any, label: str) -> dict[str, Any]:
    location = _mapping(value, label)
    allowed = {"source_path", "source_url", "native_id", "selector"}
    if set(location) - allowed:
        raise ReviewPolicyError(f"{label} contains unsupported locator fields")
    if not location.get("source_path") and not location.get("source_url"):
        raise ReviewPolicyError(f"{label} requires source_path or source_url")
    result: dict[str, Any] = {}
    for key in ("source_path", "source_url", "native_id", "selector"):
        raw = location.get(key)
        if raw is None:
            if key in location:
                result[key] = None
            continue
        result[key] = (
            _public_https_url(raw, f"{label}.{key}")
            if key == "source_url"
            else _public_source_path(raw, f"{label}.{key}")
            if key == "source_path"
            else _public_metadata_text(raw, f"{label}.{key}")
        )
    _reject_forbidden_keys(result, path=label)
    return result


@dataclass(frozen=True)
class OutputReviewDecision:
    generation_output_id: int
    asset_rights: str
    display_policy: str
    public_display_role: str
    decision_note: str | None = None

    def normalized(self) -> dict[str, Any]:
        output_id = _integer(self.generation_output_id, "generation_output_id")
        if self.asset_rights not in ASSET_RIGHTS:
            raise ReviewPolicyError("asset_rights is unsupported")
        if self.display_policy not in DISPLAY_POLICIES:
            raise ReviewPolicyError("display_policy is unsupported")
        if self.public_display_role not in PUBLIC_DISPLAY_ROLES:
            raise ReviewPolicyError("public_display_role is unsupported")
        if self.public_display_role in {"public_primary", "public_gallery"} and (
            self.asset_rights != "approved" or self.display_policy not in PUBLIC_DISPLAY_POLICIES
        ):
            raise ReviewPolicyError("public output roles require approved rights and a public display policy")
        note = None
        if self.decision_note is not None:
            note = _text(self.decision_note, "decision_note")
        return {
            "generation_output_id": output_id,
            "asset_rights": self.asset_rights,
            "display_policy": self.display_policy,
            "public_display_role": self.public_display_role,
            "decision_note": note,
        }


@dataclass(frozen=True)
class ReviewSubmission:
    source_case_version_id: int
    idempotency_key: str
    expected_latest_batch_id: int | None
    repository_license: str
    prompt_rights: str
    author: str
    original_url: str
    evidence_url: str
    reviewer: str
    reviewed_at: datetime
    output_decisions: tuple[OutputReviewDecision, ...]
    review_note: str | None = None

    def normalized(self, *, expected_output_ids: Sequence[int], now: datetime | None = None) -> dict[str, Any]:
        case_version_id = _integer(self.source_case_version_id, "source_case_version_id")
        key = _text(self.idempotency_key, "idempotency_key")
        if len(key) > 200:
            raise ReviewPolicyError("idempotency_key is too long")
        if self.expected_latest_batch_id is not None:
            _integer(self.expected_latest_batch_id, "expected_latest_batch_id")
        if self.prompt_rights not in PROMPT_RIGHTS:
            raise ReviewPolicyError("prompt_rights is unsupported")
        if self.reviewed_at.tzinfo is None:
            raise ReviewPolicyError("reviewed_at must include a timezone")
        current = now or datetime.now(timezone.utc)
        if self.reviewed_at.astimezone(timezone.utc) > current.astimezone(timezone.utc):
            raise ReviewPolicyError("reviewed_at cannot be in the future")
        decisions = [item.normalized() for item in self.output_decisions]
        ids = [int(item["generation_output_id"]) for item in decisions]
        expected = sorted({_integer(item, "expected generation_output_id") for item in expected_output_ids})
        if len(expected) != len(list(expected_output_ids)):
            raise ReviewPolicyError("expected output ids must be unique")
        if len(ids) != len(set(ids)):
            raise ReviewPolicyError("output decisions may not contain duplicate generation_output_id values")
        if sorted(ids) != expected:
            raise ReviewPolicyError("output decisions must cover the exact source-case output set")
        if sum(item["public_display_role"] == "public_primary" for item in decisions) > 1:
            raise ReviewPolicyError("a review batch may select at most one public_primary")
        if self.review_note is None:
            raise ReviewPolicyError("review_note must be explicit nonempty text")
        note = _text(self.review_note, "review_note")
        return {
            "source_case_version_id": case_version_id,
            "idempotency_key": key,
            "expected_latest_batch_id": self.expected_latest_batch_id,
            "repository_license": _text(self.repository_license, "repository_license"),
            "prompt_rights": self.prompt_rights,
            "author": _text(self.author, "author"),
            "original_url": _public_https_url(self.original_url, "original_url"),
            "evidence_url": _public_https_url(self.evidence_url, "evidence_url"),
            "reviewer": _text(self.reviewer, "reviewer"),
            "reviewed_at": self.reviewed_at.astimezone(timezone.utc).isoformat(),
            "review_note": note,
            "output_decisions": sorted(decisions, key=lambda item: int(item["generation_output_id"])),
        }


def submission_digest(document: Mapping[str, Any]) -> str:
    """Hash the normalized semantic request, excluding only the replay key."""

    payload = dict(document)
    payload.pop("idempotency_key", None)
    return json_digest(payload)


def effective_review_state(review: Mapping[str, Any] | None) -> str:
    if review is None:
        return "pending"
    prompt_rights = review.get("prompt_rights")
    decisions = _sequence(review.get("output_decisions"), "output_decisions")
    normalized = [
        OutputReviewDecision(
            generation_output_id=_integer(item.get("generation_output_id"), "generation_output_id"),
            asset_rights=str(item.get("asset_rights")),
            display_policy=str(item.get("display_policy")),
            public_display_role=str(item.get("public_display_role")),
            decision_note=item.get("decision_note") if isinstance(item.get("decision_note"), str) else None,
        ).normalized()
        for item in (_mapping(value, "output decision") for value in decisions)
    ]
    if prompt_rights == "blocked":
        return "blocked"
    if prompt_rights == "internal_only":
        return "internal_only"
    primary_count = sum(item["public_display_role"] == "public_primary" for item in normalized)
    public_count = sum(item["public_display_role"] in {"public_primary", "public_gallery"} for item in normalized)
    if prompt_rights == "approved" and primary_count == 1 and public_count >= 1:
        return "publishable"
    if normalized and all(
        item["asset_rights"] == "blocked" or item["display_policy"] == "blocked" for item in normalized
    ):
        return "blocked"
    if normalized and all(
        item["public_display_role"] == "hidden"
        and (item["asset_rights"] == "internal_only" or item["display_policy"] == "internal_only")
        for item in normalized
    ):
        return "internal_only"
    return "review_required"


def build_public_case_candidate(case_facts: Mapping[str, Any], review: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build a redacted, non-activating Candidate v2 document."""

    _reject_forbidden_keys(case_facts, path="case_facts")
    _reject_private_locator_values(case_facts, path="case_facts")
    if review is not None:
        _reject_forbidden_keys(review, path="review")
        _reject_private_locator_values(review, path="review")
    source_case_version_id = _integer(case_facts.get("source_case_version_id"), "source_case_version_id")
    source = _mapping(case_facts.get("source"), "source")
    prompt = _mapping(case_facts.get("prompt"), "prompt")
    generations = _sequence(case_facts.get("generations"), "generations")
    if not generations:
        raise ReviewPolicyError("generations must be nonempty")

    decision_by_output: dict[int, dict[str, Any]] = {}
    review_summary: dict[str, Any] | None = None
    if review is not None:
        decisions = _sequence(review.get("output_decisions"), "output_decisions")
        for raw in decisions:
            item = _mapping(raw, "output decision")
            normalized = OutputReviewDecision(
                generation_output_id=_integer(item.get("generation_output_id"), "generation_output_id"),
                asset_rights=str(item.get("asset_rights")),
                display_policy=str(item.get("display_policy")),
                public_display_role=str(item.get("public_display_role")),
                decision_note=item.get("decision_note") if isinstance(item.get("decision_note"), str) else None,
            ).normalized()
            output_id = int(normalized["generation_output_id"])
            if output_id in decision_by_output:
                raise ReviewPolicyError("review contains duplicate output decisions")
            decision_by_output[output_id] = normalized
        review_summary = {
            "rights_review_batch_id": _integer(review.get("rights_review_batch_id"), "rights_review_batch_id"),
            "repository_license": _public_identity_text(review.get("repository_license"), "repository_license"),
            "prompt_rights": str(review.get("prompt_rights")),
            "author": _public_identity_text(review.get("author"), "author"),
            "original_url": _public_https_url(review.get("original_url"), "original_url"),
            "evidence_url": _public_https_url(review.get("evidence_url"), "evidence_url"),
            "reviewer": _public_identity_text(review.get("reviewer"), "reviewer"),
            "reviewed_at": _text(review.get("reviewed_at"), "reviewed_at"),
        }

    state = effective_review_state(review)
    seen_outputs: set[int] = set()
    members: list[dict[str, Any]] = []
    public_outputs_flat: list[dict[str, Any]] = []
    digest_generations: list[dict[str, Any]] = []
    for raw_generation in generations:
        generation = _mapping(raw_generation, "generation")
        generation_row_id = _integer(generation.get("generation_example_row_id"), "generation_example_row_id")
        generation_id = _public_identity_text(generation.get("generation_example_id"), "generation_example_id")
        claim = _public_source_claim(generation.get("source_claim"))
        outputs = _sequence(generation.get("outputs"), "generation.outputs")
        if not outputs:
            raise ReviewPolicyError("every generation must contain at least one output")
        member_outputs: list[dict[str, Any]] = []
        digest_outputs: list[dict[str, Any]] = []
        member_hidden = 0
        for raw_output in outputs:
            output = _mapping(raw_output, "generation output")
            output_id = _integer(output.get("generation_output_id"), "generation_output_id")
            if output_id in seen_outputs:
                raise ReviewPolicyError("generation_output_id is duplicated across the source case")
            seen_outputs.add(output_id)
            source_role = _text(output.get("source_role"), "source_role")
            content_sha256 = _text(output.get("content_sha256"), "content_sha256")
            if len(content_sha256) != 64:
                raise ReviewPolicyError("content_sha256 must be SHA-256 text")
            digest_output = {
                "generation_output_id": output_id,
                "ordinal": int(output.get("ordinal", 0)),
                "source_role": source_role,
                "content_sha256": content_sha256,
            }
            decision = decision_by_output.get(output_id)
            if decision is not None:
                digest_output["review"] = decision
            digest_outputs.append(digest_output)
            if state != "publishable" or decision is None or decision["public_display_role"] == "hidden":
                member_hidden += 1
                continue
            public_output = {
                "generation_output_id": output_id,
                "ordinal": int(output.get("ordinal", 0)),
                "source_role": source_role,
                "public_display_role": decision["public_display_role"],
                "content_sha256": content_sha256,
                "media_type": _text(output.get("media_type"), "media_type"),
                "byte_size": _integer(output.get("byte_size"), "byte_size"),
                "source_path": _public_source_path(output.get("source_path"), "source_path"),
                "source_url": _public_https_url(output.get("source_url"), "source_url"),
                "source_location": _public_source_location(output.get("source_location"), "source_location"),
                "rights": {
                    "asset_rights": decision["asset_rights"],
                    "display_policy": decision["display_policy"],
                },
            }
            member_outputs.append(public_output)
            public_outputs_flat.append(public_output)
        members.append(
            {
                "generation_example_row_id": generation_row_id,
                "generation_example_id": generation_id,
                "source_claim": claim,
                "public_outputs": sorted(member_outputs, key=lambda item: (item["ordinal"], item["generation_output_id"])),
                "hidden_outputs": [{"redacted": True} for _ in range(member_hidden)],
            }
        )
        digest_generations.append(
            {
                "generation_example_id": generation_id,
                "source_claim": claim,
                "outputs": sorted(digest_outputs, key=lambda item: (item["ordinal"], item["generation_output_id"])),
            }
        )
    if review is not None and set(decision_by_output) != seen_outputs:
        raise ReviewPolicyError("review decisions must cover the exact case output set")

    if state == "publishable" and sum(
        item["public_display_role"] == "public_primary" for item in public_outputs_flat
    ) != 1:
        raise ReviewPolicyError("publishable Candidate v2 requires exactly one public_primary")
    digest_document = {
        "source": {
            "source_id": _public_identity_text(source.get("source_id"), "source_id"),
            "repository_id": _public_identity_text(source.get("repository_id"), "repository_id"),
            "revision_sha": _text(source.get("revision_sha"), "revision_sha"),
            "source_case_key": _public_identity_text(source.get("source_case_key"), "source_case_key"),
        },
        "prompt": {
            "prompt_id": _public_identity_text(prompt.get("prompt_id"), "prompt_id"),
            "raw_text": _text(prompt.get("raw_text"), "raw_text"),
            "language": _public_identity_text(prompt.get("language"), "language"),
        },
        "generations": sorted(digest_generations, key=lambda item: item["generation_example_id"]),
        "review": None
        if review_summary is None
        else {key: value for key, value in review_summary.items() if key != "rights_review_batch_id"},
        "state": state,
    }
    return {
        "schema_version": "public-case-candidate/v2",
        "state": state,
        "source_case": {
            "source_case_version_id": source_case_version_id,
            **digest_document["source"],
        },
        "prompt": {
            **digest_document["prompt"],
            "source_path": _public_source_path(prompt.get("source_path"), "prompt.source_path"),
            "source_url": _public_https_url(prompt.get("source_url"), "prompt.source_url"),
        },
        "generation_members": sorted(members, key=lambda item: item["generation_example_id"]),
        "rights_review": review_summary,
        "candidate_content_digest": json_digest(digest_document),
    }
