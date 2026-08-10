"""Strict adapter for freestylefly's fixed data/cases.json gallery."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from ..registry import SourceConfig
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import read_snapshot_text, regular_relative_files, safe_repository_path, snapshot_file


TOP_FIELDS = frozenset({"repository", "totalCases", "categories", "styles", "scenes", "cases"})
CASE_FIELDS = frozenset(
    {
        "id",
        "title",
        "image",
        "imageAlt",
        "sourceLabel",
        "sourceUrl",
        "prompt",
        "promptPreview",
        "category",
        "styles",
        "scenes",
        "featured",
        "githubUrl",
    }
)
CASE_IMAGE = re.compile(r"^/images/case([1-9][0-9]*)\.(?:jpg|png)$")
KNOWN_FIXED_ORPHAN_CASE_IMAGES = {
    "data/images/case12.jpg",
    "data/images/case169.jpg",
    "data/images/case170.jpg",
}


class FreestyleflyAdapterError(AdapterError):
    """Stable fail-closed error for the fixed freestylefly source shape."""


def _shape(message: str) -> FreestyleflyAdapterError:
    return FreestyleflyAdapterError("source_shape_invalid", message)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape(f"{label} must be a nonempty string")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise _shape(f"{label} must be a nonempty-string array")
    if len(value) != len(set(value)):
        raise _shape(f"{label} may not contain duplicates")
    return list(value)


def _location(config: SourceConfig, path: str, native_id: str, selector: str) -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": native_id,
        "selector": selector,
    }


def _image_path(value: Any, case_id: int) -> str:
    image = _text(value, f"case {case_id} image")
    match = CASE_IMAGE.fullmatch(image)
    if match is None or int(match.group(1)) != case_id:
        raise _shape(f"case {case_id} image must be /images/case<ID>.jpg|png")
    return safe_repository_path(
        f"data{image}", label=f"case {case_id} image", error_factory=_shape
    )


def parse_freestylefly_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], None]:
    try:
        payload = json.loads(
            read_snapshot_text(
                snapshot_root,
                "data/cases.json",
                label="data/cases.json",
                error_factory=_shape,
                read_error_factory=lambda message: FreestyleflyAdapterError("source_data_invalid", message),
            )
        )
    except json.JSONDecodeError as exc:
        raise FreestyleflyAdapterError("source_data_invalid", "data/cases.json must be valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != TOP_FIELDS:
        raise _shape("data/cases.json must use the exact fixed top-level field set")
    cases = payload.get("cases")
    total = payload.get("totalCases")
    if not isinstance(cases, list) or not cases or not isinstance(total, int) or isinstance(total, bool) or total != len(cases):
        raise FreestyleflyAdapterError("source_count_mismatch", "totalCases must equal the nonempty cases array")
    if payload.get("repository") != source_config.repository_url:
        raise _shape("repository identity differs from the registered source")
    for field in ("categories", "styles", "scenes"):
        _string_list(payload.get(field), field)

    parsed: list[ParsedCase] = []
    expected_images: set[str] = set()
    seen_ids: set[int] = set()
    for index, value in enumerate(cases):
        if not isinstance(value, dict) or set(value) != CASE_FIELDS:
            raise _shape(f"cases[{index}] must use the exact fixed field set")
        case_id = value.get("id")
        if not isinstance(case_id, int) or isinstance(case_id, bool) or case_id <= 0:
            raise _shape(f"cases[{index}].id must be a positive integer")
        if case_id in seen_ids:
            raise FreestyleflyAdapterError("source_duplicate_id", f"duplicate native id: {case_id}")
        seen_ids.add(case_id)
        native_id = str(case_id)
        raw_prompt = _text(value.get("prompt"), f"case {case_id} prompt")
        if len(re.sub(r"\s+", "", normalize_prompt(raw_prompt))) < 8:
            raise FreestyleflyAdapterError("source_prompt_invalid", f"case {case_id} prompt is too short")
        image_path = _image_path(value.get("image"), case_id)
        snapshot_file(snapshot_root, image_path, label=f"case {case_id} image", error_factory=_shape)
        expected_images.add(image_path)
        title = _text(value.get("title"), f"case {case_id} title")
        category = _text(value.get("category"), f"case {case_id} category")
        styles = _string_list(value.get("styles"), f"case {case_id} styles")
        scenes = _string_list(value.get("scenes"), f"case {case_id} scenes")
        if not isinstance(value.get("featured"), bool):
            raise _shape(f"case {case_id} featured must be boolean")
        for field in ("imageAlt", "sourceLabel", "promptPreview", "githubUrl"):
            _text(value.get(field), f"case {case_id} {field}")
        if not isinstance(value.get("sourceUrl"), str):
            raise _shape(f"case {case_id} sourceUrl must be a string")

        source_case_key = f"{source_config.source_id}:{native_id}"
        prompt_id = f"prompt:sha256:{prompt_sha256(raw_prompt)}"
        asset_ref_id = f"asset-ref:{source_case_key}:output-primary"
        case_location = _location(source_config, "data/cases.json", native_id, f"cases[id={case_id}]")
        prompt_location = _location(source_config, "data/cases.json", native_id, f"cases[id={case_id}].prompt")
        image_location = _location(source_config, image_path, native_id, f"cases[id={case_id}].image")
        metadata = {key: copy.deepcopy(value[key]) for key in CASE_FIELDS - {"prompt", "image"}}
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": case_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": raw_prompt,
                "language": "unknown",
                "source_location": prompt_location,
            },
            "asset_references": [
                {
                    "asset_ref_id": asset_ref_id,
                    "role": "output_primary",
                    "resolution_state": "unresolved",
                    "source_location": image_location,
                }
            ],
            "pairings": [
                {
                    "prompt_id": prompt_id,
                    "asset_ref_id": asset_ref_id,
                    "method": "explicit_structured_reference",
                    "status": "strong",
                    "evidence": [case_location, prompt_location, image_location],
                }
            ],
            "source_claim": {"evidence_status": "unknown", "model_raw": None, "parameters_raw": None},
            "raw_tags": sorted(set([category, *styles, *scenes])),
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Registry rights evidence is retained; internal ingestion does not authorize publication.",
            },
            "extensions": {"freestylefly.source": {"case": metadata, "registry_rights": source_config.rights}},
        }
        parsed.append(
            ParsedCase(source_case_key, native_id, (AssetPathBinding(asset_ref_id, image_path),), adapter_record)
        )

    image_files = {
        path
        for path in regular_relative_files(snapshot_root, "data/images", error_factory=_shape)
        if re.fullmatch(r"data/images/case[1-9][0-9]*\.(?:jpg|png)", path)
    }
    if image_files - expected_images != KNOWN_FIXED_ORPHAN_CASE_IMAGES or expected_images - image_files:
        raise _shape("case image file set differs from manifest plus the three fixed orphan images")
    parsed.sort(key=lambda item: item.source_case_key)
    return parsed, None
