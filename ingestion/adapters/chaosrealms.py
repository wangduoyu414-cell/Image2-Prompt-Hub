"""Strict fixed-history adapter for ChaosRealmsAI's three-WebP case layout."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping

from ..registry import SourceConfig, repo_root
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import read_snapshot_text, regular_relative_files, safe_repository_path, snapshot_file


SOURCE_ID = "chaosrealmsai-gpt-image-2-gallery"
ADMISSION_PATH = repo_root() / "config" / "fixed-history" / f"{SOURCE_ID}-v1.json"
INDEX_PATH = "works/index.json"
SAFE_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
EXPECTED_VARIANTS = (
    ("01-primary-w1600", "image.w1600.webp", "output_primary", 1600),
    ("02-secondary-w400", "image.w400.webp", "output_secondary", 400),
    ("03-secondary-w2400", "image.w2400.webp", "output_secondary", 2400),
)


class ChaosRealmsAdapterError(AdapterError):
    """Stable fail-closed error for the admitted fixed-history snapshot."""


def _shape(message: str) -> ChaosRealmsAdapterError:
    return ChaosRealmsAdapterError("source_shape_invalid", message)


def _data(message: str) -> ChaosRealmsAdapterError:
    return ChaosRealmsAdapterError("source_data_invalid", message)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape(f"{label} must be a nonempty string")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise _shape(f"{label} must be a string array")
    if len(value) != len(set(value)):
        raise _shape(f"{label} may not contain duplicates")
    return list(value)


def _load_json_text(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _data(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise _shape(f"{label} must contain an object")
    return value


def _load_admission(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admission authority is unreadable") from exc
    if not isinstance(value, dict):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admission authority must be an object")
    return value


def _location(config: SourceConfig, path: str, native_id: str, selector: str) -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": native_id,
        "selector": selector,
    }


def _validate_admission(admission: Mapping[str, Any], config: SourceConfig) -> tuple[set[str], set[str]]:
    if (
        admission.get("schema_version") != "fixed-history-admission/v1"
        or admission.get("source_id") != SOURCE_ID
        or admission.get("source_id") != config.source_id
        or admission.get("revision") != config.verified_commit_sha
        or admission.get("mode") != "fixed_history"
        or admission.get("structure_strategy") != "chaos_meta_three_webp_v1"
        or admission.get("family_role") != "canonical"
        or admission.get("sync_eligible") is not False
        or admission.get("one_shot_import_only") is not True
    ):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admission identity or mode drifted")
    if config.ingestion_mode != "fixed_history" or config.sync_enabled or not config.one_shot_import_only:
        raise ChaosRealmsAdapterError("registry_invalid", "Chaos source is not configured as one-shot fixed history")

    admitted = admission.get("admitted_case_ids")
    exclusions = admission.get("exclusions")
    if not isinstance(admitted, list) or not admitted or not all(isinstance(item, str) for item in admitted):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admitted case IDs are malformed")
    if admitted != sorted(admitted) or len(admitted) != len(set(admitted)):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admitted case IDs must be sorted and unique")
    if admission.get("case_count") != len(admitted):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history admitted case count drifted")
    if not isinstance(exclusions, list) or not all(isinstance(item, dict) for item in exclusions):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history exclusions are malformed")
    exclusion_pairs = [(item.get("case_id"), item.get("reason")) for item in exclusions]
    if any(not isinstance(case_id, str) or not isinstance(reason, str) for case_id, reason in exclusion_pairs):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history exclusion identity is malformed")
    if exclusion_pairs != sorted(exclusion_pairs) or len(exclusion_pairs) != len(set(exclusion_pairs)):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history exclusions must be sorted and unique")
    excluded_ids = {str(case_id) for case_id, _ in exclusion_pairs}
    admitted_ids = set(admitted)
    if admitted_ids & excluded_ids:
        raise ChaosRealmsAdapterError("registry_invalid", "one case cannot be both admitted and excluded")
    if admission.get("excluded_case_count") != len(excluded_ids):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history excluded case count drifted")
    if admission.get("raw_case_count") != len(admitted_ids | excluded_ids):
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history raw case partition does not close")
    declared_variants = admission.get("output_variants")
    expected_variants = [
        {"suffix": suffix, "filename": filename, "role": role, "width": width}
        for suffix, filename, role, width in EXPECTED_VARIANTS
    ]
    if declared_variants != expected_variants:
        raise ChaosRealmsAdapterError("registry_invalid", "fixed-history output variant contract drifted")
    return admitted_ids, excluded_ids


def parse_chaos_snapshot(
    snapshot_root: Path,
    source_config: SourceConfig,
    *,
    admission_path: Path | None = None,
) -> tuple[list[ParsedCase], None]:
    admission = _load_admission((admission_path or ADMISSION_PATH).resolve())
    admitted_ids, excluded_ids = _validate_admission(admission, source_config)
    index = _load_json_text(
        read_snapshot_text(
            snapshot_root,
            INDEX_PATH,
            label=INDEX_PATH,
            error_factory=_shape,
            read_error_factory=_data,
        ),
        INDEX_PATH,
    )
    rows = index.get("images")
    if index.get("schema_version") != 1 or not isinstance(rows, list) or not rows:
        raise _shape("works/index.json must contain the fixed nonempty images array")

    indexed: dict[str, dict[str, Any]] = {}
    for position, value in enumerate(rows):
        if not isinstance(value, dict):
            raise _shape(f"works/index.json images[{position}] must be an object")
        case_id = _text(value.get("id"), f"images[{position}].id")
        if SAFE_CASE_ID.fullmatch(case_id) is None or ".." in case_id.split("/"):
            raise _shape(f"images[{position}].id is unsafe")
        if case_id in indexed:
            raise ChaosRealmsAdapterError("source_duplicate_id", f"duplicate Chaos case ID: {case_id}")
        indexed[case_id] = value
    if set(indexed) != admitted_ids | excluded_ids:
        raise ChaosRealmsAdapterError("source_count_mismatch", "Chaos index does not equal the admitted plus excluded case partition")

    parsed: list[ParsedCase] = []
    for case_id in sorted(admitted_ids):
        value = indexed[case_id]
        meta_path = safe_repository_path(
            _text(value.get("meta_path"), f"{case_id}.meta_path"),
            label=f"{case_id}.meta_path",
            error_factory=_shape,
        )
        meta = _load_json_text(
            read_snapshot_text(
                snapshot_root,
                meta_path,
                label=meta_path,
                error_factory=_shape,
                read_error_factory=_data,
            ),
            meta_path,
        )
        native_id = case_id
        image_id = case_id.rsplit("/", 1)[-1]
        if meta.get("id") != image_id or value.get("image_id") != image_id:
            raise _shape(f"{case_id} meta/index image identity disagrees")
        if value.get("topic_slug") != case_id.split("/", 1)[0]:
            raise _shape(f"{case_id} topic identity disagrees")
        raw_prompt = _text(meta.get("prompt"), f"{case_id}.prompt")
        if len(re.sub(r"\s+", "", normalize_prompt(raw_prompt))) < 80:
            raise ChaosRealmsAdapterError("source_prompt_invalid", f"{case_id} prompt is too short")
        generation = meta.get("generation")
        if not isinstance(generation, dict) or generation.get("model") != "gpt-image-2" or generation.get("mode") != "image":
            raise _shape(f"{case_id} generation claim is not the fixed gpt-image-2 image shape")
        if generation.get("depends_on") not in ([], None) or meta.get("refs") not in ([], None) or generation.get("ref_urls") not in ([], None):
            raise _shape(f"{case_id} unexpectedly depends on reference input")

        case_directory = Path(meta_path).parent.as_posix()
        expected_files = {meta_path, *(f"{case_directory}/{filename}" for _, filename, _, _ in EXPECTED_VARIANTS)}
        observed_files = regular_relative_files(snapshot_root, case_directory, error_factory=_shape)
        if observed_files != expected_files:
            raise _shape(f"{case_id} directory must contain exactly meta.json and the three admitted WebP variants")

        source_case_key = f"{source_config.source_id}:{case_id}"
        prompt_id = f"prompt:sha256:{prompt_sha256(raw_prompt)}"
        case_location = _location(source_config, meta_path, native_id, "meta JSON object")
        prompt_location = _location(source_config, meta_path, native_id, "prompt")
        references: list[dict[str, Any]] = []
        pairings: list[dict[str, Any]] = []
        bindings: list[AssetPathBinding] = []
        for suffix, filename, role, width in EXPECTED_VARIANTS:
            image_path = f"{case_directory}/{filename}"
            snapshot_file(snapshot_root, image_path, label=image_path, error_factory=_shape)
            asset_ref_id = f"asset-ref:{source_case_key}:{suffix}"
            image_location = _location(source_config, image_path, native_id, filename)
            references.append(
                {
                    "asset_ref_id": asset_ref_id,
                    "role": role,
                    "resolution_state": "unresolved",
                    "source_location": image_location,
                    "extensions": {"chaosrealms.variant": {"filename": filename, "width": width}},
                }
            )
            pairings.append(
                {
                    "prompt_id": prompt_id,
                    "asset_ref_id": asset_ref_id,
                    "method": "stable_native_mapping",
                    "status": "strong",
                    "evidence": [case_location, prompt_location, image_location],
                }
            )
            bindings.append(AssetPathBinding(asset_ref_id, image_path))

        tags = sorted(
            {
                str(value.get("topic_slug")),
                *_string_list(meta.get("tags", []), f"{case_id}.tags"),
            }
        )
        metadata = {
            key: copy.deepcopy(meta[key])
            for key in ("id", "title", "description", "type", "aspect_ratio", "tags", "status", "display")
            if key in meta
        }
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": case_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": raw_prompt,
                "language": "en",
                "source_location": prompt_location,
            },
            "asset_references": references,
            "pairings": pairings,
            "source_claim": {
                "evidence_status": "source_claimed",
                "model_raw": "gpt-image-2",
                "parameters_raw": {"aspect_ratio": meta.get("aspect_ratio"), "mode": "image"},
            },
            "raw_tags": tags,
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Fixed-history admission and repository license evidence do not authorize publication.",
            },
            "extensions": {
                "chaosrealms.source": {
                    "category": str(value.get("topic_slug")),
                    "meta": metadata,
                    "registry_rights": source_config.rights,
                }
            },
        }
        parsed.append(ParsedCase(source_case_key, native_id, tuple(bindings), adapter_record))

    return parsed, None


__all__ = ["ChaosRealmsAdapterError", "parse_chaos_snapshot"]
