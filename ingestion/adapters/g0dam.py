"""Static-JSON adapter for the frozen g0dam source structure."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..registry import SourceConfig, normalize_repository_path
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256


class G0damAdapterError(AdapterError):
    """Backward-compatible g0dam-specific adapter error name."""


def _nonempty_string(value: Any, label: str, case_id: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        prefix = f"{case_id}: " if case_id else ""
        raise G0damAdapterError("source_shape_invalid", f"{prefix}{label} must be a nonempty string")
    return value


def _source_location(config: SourceConfig, case_id: str, selector: str, path: str = "data/prompts.json") -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": case_id,
        "selector": selector,
    }


def _raw_tags(value: Any, case_id: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise G0damAdapterError("source_shape_invalid", f"{case_id}: tags must be a string array")
    return sorted(set(value))


def _extension_value(item: dict[str, Any], config: SourceConfig) -> dict[str, Any]:
    prompt = item.get("prompt") if isinstance(item.get("prompt"), dict) else {}
    return {
        "title_raw": item.get("title"),
        "prompt_zh_raw": prompt.get("zh"),
        "category_raw": item.get("category"),
        "license_note_raw": item.get("license_note"),
        "source_reference_ids_raw": item.get("source_reference_ids"),
        "registry_rights": config.rights,
    }


def parse_g0dam_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], str]:
    """Parse every structured record without importing or executing source code."""
    data_path = snapshot_root / "data" / "prompts.json"
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise G0damAdapterError("source_data_invalid", f"cannot read data/prompts.json: {exc}") from exc
    if not isinstance(payload, dict):
        raise G0damAdapterError("source_data_invalid", "data/prompts.json must contain an object")
    count = payload.get("count")
    prompts = payload.get("prompts")
    model_target = _nonempty_string(payload.get("model_target"), "model_target")
    if not isinstance(count, int) or isinstance(count, bool) or not isinstance(prompts, list) or count != len(prompts):
        raise G0damAdapterError("source_count_mismatch", "top-level count must equal prompts length")
    cases: list[ParsedCase] = []
    seen_native_ids: set[str] = set()
    for index, item in enumerate(prompts):
        if not isinstance(item, dict):
            raise G0damAdapterError("source_shape_invalid", f"prompts[{index}] must be an object")
        case_id = _nonempty_string(item.get("id"), "id")
        if case_id in seen_native_ids:
            raise G0damAdapterError("source_duplicate_id", f"duplicate native id: {case_id}")
        seen_native_ids.add(case_id)
        prompt_object = item.get("prompt")
        category = item.get("category")
        if not isinstance(prompt_object, dict) or not isinstance(category, dict):
            raise G0damAdapterError("source_shape_invalid", f"{case_id}: prompt and category must be objects")
        raw_text = _nonempty_string(prompt_object.get("en"), "prompt.en", case_id)
        if len(re.sub(r"\s+", "", normalize_prompt(raw_text))) < 80:
            raise G0damAdapterError("source_prompt_invalid", f"{case_id}: prompt.en is too short")
        image_path = normalize_repository_path(_nonempty_string(item.get("image_path"), "image_path", case_id))
        category_slug = _nonempty_string(category.get("slug"), "category.slug", case_id)
        prompt_id = f"prompt:sha256:{prompt_sha256(raw_text)}"
        source_case_key = f"{source_config.source_id}:{case_id}"
        case_location = _source_location(source_config, case_id, f"prompts[id={case_id}]")
        prompt_location = _source_location(source_config, case_id, f"prompts[id={case_id}].prompt.en")
        image_location = {
            "source_path": image_path,
            "source_url": source_config.raw_url(image_path),
            "native_id": case_id,
            "selector": f"prompts[id={case_id}].image_path",
        }
        asset_ref_id = f"asset-ref:{source_case_key}:output-primary"
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": case_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": raw_text,
                "language": "en",
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
                    "evidence": [
                        _source_location(
                            source_config,
                            case_id,
                            f"one structured prompts[id={case_id}] record binds prompt.en and image_path",
                        )
                    ],
                }
            ],
            "source_claim": {
                "evidence_status": "source_claimed",
                "model_raw": model_target,
                "parameters_raw": None,
            },
            "raw_tags": _raw_tags(item.get("tags"), case_id),
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Registry rights are retained as source evidence; no approval or publication decision is implied.",
            },
            "extensions": {"g0dam.source": _extension_value(item, source_config)},
        }
        cases.append(ParsedCase(source_case_key, case_id, (AssetPathBinding(asset_ref_id, image_path),), adapter_record))
    cases.sort(key=lambda item: item.source_case_key)
    return cases, model_target
