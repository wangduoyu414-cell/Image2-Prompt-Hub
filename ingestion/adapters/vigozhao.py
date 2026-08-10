"""Strict two-preview adapter for VigoZhao's fixed style directories."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from ..registry import SourceConfig
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import fixed_snapshot_root, read_snapshot_text, regular_relative_files, snapshot_file


REQUIRED_FIELDS = frozenset(
    {
        "style_name",
        "style_slug",
        "style_version",
        "style_summary",
        "environment_variables",
        "style_fidelity_anchors",
        "source_content_to_avoid",
        "visual_deconstruction",
        "composition",
        "typography",
        "color_palette",
        "design_rules",
        "do",
        "avoid",
        "prompt_template",
        "negative_prompt",
        "examples",
    }
)
OPTIONAL_FIELDS = frozenset({"image_treatment", "photographic_direction"})
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class VigoZhaoAdapterError(AdapterError):
    """Stable fail-closed error for the fixed VigoZhao source shape."""


def _shape(message: str) -> VigoZhaoAdapterError:
    return VigoZhaoAdapterError("source_shape_invalid", message)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape(f"{label} must be a nonempty string")
    return value


def _location(config: SourceConfig, path: str, native_id: str, selector: str) -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": native_id,
        "selector": selector,
    }


def parse_vigozhao_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], None]:
    root = fixed_snapshot_root(snapshot_root, error_factory=_shape)
    files = regular_relative_files(snapshot_root, "styles", error_factory=_shape)
    if not files:
        raise VigoZhaoAdapterError("source_data_invalid", "styles must contain fixed style directories")
    style_slugs = sorted({path.split("/")[1] for path in files if path.count("/") == 2})
    expected_files = {
        f"styles/{slug}/{filename}"
        for slug in style_slugs
        for filename in ("style.json", "preview-16x9.jpg", "preview-9x16.jpg")
    }
    if files != expected_files:
        raise _shape("each style directory must contain exactly style.json and the two fixed previews")

    parsed: list[ParsedCase] = []
    seen_slugs: set[str] = set()
    for slug in style_slugs:
        if SAFE_SLUG.fullmatch(slug) is None or slug in seen_slugs:
            raise VigoZhaoAdapterError("source_duplicate_id", f"duplicate or unsafe style slug: {slug}")
        seen_slugs.add(slug)
        style_path = f"styles/{slug}/style.json"
        try:
            payload = json.loads(
                read_snapshot_text(
                    snapshot_root,
                    style_path,
                    label=style_path,
                    error_factory=_shape,
                    read_error_factory=lambda message: VigoZhaoAdapterError("source_data_invalid", message),
                )
            )
        except json.JSONDecodeError as exc:
            raise VigoZhaoAdapterError("source_data_invalid", f"{style_path} must be valid JSON") from exc
        if not isinstance(payload, dict) or not REQUIRED_FIELDS.issubset(payload) or set(payload) - REQUIRED_FIELDS - OPTIONAL_FIELDS:
            raise _shape(f"{style_path} does not use the fixed style field set")
        if payload.get("style_slug") != slug:
            raise _shape(f"{style_path} style_slug must equal its directory")
        for field in ("style_name", "style_version", "style_summary", "prompt_template", "negative_prompt"):
            _text(payload.get(field), f"{slug}.{field}")
        raw_prompt = str(payload["prompt_template"])
        if len(re.sub(r"\s+", "", normalize_prompt(raw_prompt))) < 80:
            raise VigoZhaoAdapterError("source_prompt_invalid", f"{slug}: prompt_template is too short")
        if not isinstance(payload.get("environment_variables"), dict) or not payload["environment_variables"]:
            raise _shape(f"{slug}.environment_variables must be a nonempty object")
        for field in ("style_fidelity_anchors", "source_content_to_avoid", "design_rules", "do", "avoid", "examples"):
            if not isinstance(payload.get(field), list) or not payload[field]:
                raise _shape(f"{slug}.{field} must be a nonempty array")
        if not isinstance(payload.get("visual_deconstruction"), dict) or not payload["visual_deconstruction"]:
            raise _shape(f"{slug}.visual_deconstruction must be a nonempty object")
        for field in ("composition", "typography", "color_palette"):
            if not isinstance(payload.get(field), (dict, list)) or not payload[field]:
                raise _shape(f"{slug}.{field} must be a nonempty object or array")

        source_case_key = f"{source_config.source_id}:{slug}"
        prompt_id = f"prompt:sha256:{prompt_sha256(raw_prompt)}"
        case_location = _location(source_config, style_path, slug, "style JSON object")
        prompt_location = _location(source_config, style_path, slug, "prompt_template")
        bindings: list[AssetPathBinding] = []
        references: list[dict[str, Any]] = []
        pairings: list[dict[str, Any]] = []
        variants = (
            ("preview-16x9.jpg", "output_primary", "output-primary-16x9", "16x9"),
            ("preview-9x16.jpg", "output_secondary", "output-secondary-9x16", "9x16"),
        )
        for filename, role, suffix, aspect_ratio in variants:
            image_path = f"styles/{slug}/{filename}"
            snapshot_file(snapshot_root, image_path, label=image_path, error_factory=_shape)
            asset_ref_id = f"asset-ref:{source_case_key}:{suffix}"
            image_location = _location(source_config, image_path, slug, filename)
            references.append(
                {
                    "asset_ref_id": asset_ref_id,
                    "role": role,
                    "resolution_state": "unresolved",
                    "source_location": image_location,
                    "extensions": {"vigozhao.variant": {"aspect_ratio": aspect_ratio, "filename": filename}},
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
        metadata = {key: copy.deepcopy(value) for key, value in payload.items() if key != "prompt_template"}
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
            "source_claim": {"evidence_status": "unknown", "model_raw": None, "parameters_raw": None},
            "raw_tags": ["style-cookbook"],
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Repository license evidence is retained; individual prompt/assets remain review_required.",
            },
            "extensions": {"vigozhao.source": {"style": metadata, "registry_rights": source_config.rights}},
        }
        parsed.append(ParsedCase(source_case_key, slug, tuple(bindings), adapter_record))
    if any(path.parent == root / "styles" and path.is_file() for path in (root / "styles").iterdir()):
        raise _shape("styles root may not contain loose files")
    parsed.sort(key=lambda item: item.source_case_key)
    return parsed, None
