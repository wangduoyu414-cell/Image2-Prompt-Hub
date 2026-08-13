"""Versioned content-quality authority over immutable source facts."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from content.publication import normalize_prompt


LEDGER_PATH = Path(__file__).resolve().parents[1] / "config" / "content-quality-v1.json"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "content-quality-v1.schema.json"


class ContentQualityError(ValueError):
    """The repository content-quality authority is malformed or drifted."""


@dataclass(frozen=True)
class ContentQualityDecision:
    source_id: str
    revision_sha: str
    source_case_key: str
    prompt_sha256: str
    output_content_sha256: tuple[str, ...]
    verdict: str
    reason_code: str
    review_method: str
    review_note: str

    @property
    def blocks_publication(self) -> bool:
        return self.verdict in {"blocked", "duplicate_only"}

    def public_facts(self) -> dict[str, str]:
        return {
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "review_method": self.review_method,
        }


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentQualityError(f"{label} must be nonempty text")
    return value.strip()


def _hashes(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContentQualityError(f"{label} must be an array")
    result = tuple(_text(item, f"{label} item") for item in value)
    if not result or len(result) != len(set(result)) or any(len(item) != 64 for item in result):
        raise ContentQualityError(f"{label} must contain unique SHA-256 values")
    return result


@lru_cache(maxsize=1)
def load_content_quality_ledger(
    ledger_path: Path = LEDGER_PATH,
    schema_path: Path = SCHEMA_PATH,
) -> tuple[ContentQualityDecision, ...]:
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(ledger)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        raise ContentQualityError("content quality ledger is unreadable or invalid") from exc
    raw_decisions = ledger.get("decisions") if isinstance(ledger, Mapping) else None
    if not isinstance(raw_decisions, list):
        raise ContentQualityError("content quality decisions are missing")
    decisions: list[ContentQualityDecision] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in raw_decisions:
        if not isinstance(raw, Mapping):
            raise ContentQualityError("content quality decision must be an object")
        decision = ContentQualityDecision(
            source_id=_text(raw.get("source_id"), "source_id"),
            revision_sha=_text(raw.get("revision_sha"), "revision_sha"),
            source_case_key=_text(raw.get("source_case_key"), "source_case_key"),
            prompt_sha256=_text(raw.get("prompt_sha256"), "prompt_sha256"),
            output_content_sha256=_hashes(raw.get("output_content_sha256"), "output_content_sha256"),
            verdict=_text(raw.get("verdict"), "verdict"),
            reason_code=_text(raw.get("reason_code"), "reason_code"),
            review_method=_text(raw.get("review_method"), "review_method"),
            review_note=_text(raw.get("review_note"), "review_note"),
        )
        key = (decision.source_id, decision.revision_sha, decision.source_case_key)
        if key in seen:
            raise ContentQualityError("content quality decision identity is duplicated")
        seen.add(key)
        decisions.append(decision)
    return tuple(sorted(decisions, key=lambda item: (item.source_id, item.revision_sha, item.source_case_key)))


def content_quality_decision(
    *,
    source_id: str,
    revision_sha: str,
    source_case_key: str,
    raw_prompt: str,
    output_content_sha256: Sequence[str],
) -> ContentQualityDecision | None:
    key = (source_id, revision_sha, source_case_key)
    decision = next(
        (
            item
            for item in load_content_quality_ledger()
            if (item.source_id, item.revision_sha, item.source_case_key) == key
        ),
        None,
    )
    if decision is None:
        return None
    prompt_sha256 = hashlib.sha256(normalize_prompt(raw_prompt).encode("utf-8")).hexdigest()
    outputs = tuple(sorted(str(item) for item in output_content_sha256))
    if prompt_sha256 != decision.prompt_sha256 or outputs != tuple(sorted(decision.output_content_sha256)):
        raise ContentQualityError("content quality authority no longer matches immutable source facts")
    return decision


def quality_state_for_facts(case_facts: Mapping[str, Any]) -> dict[str, str]:
    source = case_facts.get("source")
    prompt = case_facts.get("prompt")
    generations = case_facts.get("generations")
    if not isinstance(source, Mapping) or not isinstance(prompt, Mapping) or not isinstance(generations, Sequence):
        raise ContentQualityError("case facts are incomplete for quality evaluation")
    output_hashes: list[str] = []
    for generation in generations:
        if not isinstance(generation, Mapping):
            raise ContentQualityError("case generation is malformed for quality evaluation")
        outputs = generation.get("outputs")
        if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes, bytearray)):
            raise ContentQualityError("case outputs are malformed for quality evaluation")
        for output in outputs:
            if not isinstance(output, Mapping):
                raise ContentQualityError("case output is malformed for quality evaluation")
            output_hashes.append(_text(output.get("content_sha256"), "content_sha256"))
    decision = content_quality_decision(
        source_id=_text(source.get("source_id"), "source_id"),
        revision_sha=_text(source.get("revision_sha"), "revision_sha"),
        source_case_key=_text(source.get("source_case_key"), "source_case_key"),
        raw_prompt=_text(prompt.get("raw_text"), "raw_text"),
        output_content_sha256=output_hashes,
    )
    return {"verdict": "eligible", "reason_code": "not_blocked"} if decision is None else decision.public_facts()


def assert_quality_submission_compatible(case_facts: Mapping[str, Any], normalized_review: Mapping[str, Any]) -> None:
    """Reject a rights decision that would contradict a fixed quality block."""

    quality = quality_state_for_facts(case_facts)
    if quality["verdict"] not in {"blocked", "duplicate_only"}:
        return
    decisions = normalized_review.get("output_decisions")
    public_output = isinstance(decisions, Sequence) and not isinstance(decisions, (str, bytes, bytearray)) and any(
        isinstance(item, Mapping) and item.get("public_display_role") in {"public_primary", "public_gallery"}
        for item in decisions
    )
    if normalized_review.get("prompt_rights") == "approved" or public_output:
        raise ContentQualityError("quality-blocked source cases cannot receive a public approval decision")
