"""Strict multi-output adapter for erickkkyt's fixed prompts manifest."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from ..registry import SourceConfig
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import read_snapshot_text, regular_relative_files, safe_repository_path, snapshot_file


ROW_FIELDS = frozenset(
    {
        "index",
        "id",
        "prompt",
        "author",
        "author_name",
        "image",
        "images",
        "image_count",
        "image_width",
        "image_height",
        "image_aspect_ratio",
        "image_dimensions",
        "model",
        "date",
        "published",
        "languages",
        "source",
        "source_url",
        "pair_ids",
    }
)
DIMENSION_FIELDS = frozenset({"image", "width", "height", "aspect_ratio"})
SAFE_NATIVE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
SAFE_PAIR_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
KNOWN_FIXED_ORPHAN_ASSET_FILES = frozenset(
    {
        "assets/gpt-image-2-web-examples/api-pricing-comparison-table.png",
        "assets/gpt-image-2-web-examples/arena-alpha-performance-comparison-chart.png",
        "assets/gpt-image-2-web-examples/comic-book-panel-readable-speech-bubbles.png",
        "assets/gpt-image-2-web-examples/desk-scene-packingtape-alpha.jpg",
        "assets/gpt-image-2-web-examples/futuristic-city-at-sunset.webp",
        "assets/gpt-image-2-web-examples/ikea-storefront-at-night.jpeg",
        "assets/gpt-image-2-web-examples/item-shop-ui-readable-prices.jpg",
        "assets/gpt-image-2-web-examples/minecraft-scene-ui-art-style.png",
        "assets/gpt-image-2-web-examples/multi-word-label-social-graphic.png",
        "assets/gpt-image-2-web-examples/official-launch-promo-youtube-screenshot.png",
        "assets/gpt-image-2-web-examples/photo-editing-app-ui-mockup.webp",
        "assets/gpt-image-2-web-examples/photorealistic-beach-selfie.png",
        "assets/gpt-image-2-web-examples/realistic-budgeting-app-screen.png",
        "assets/gpt-image-2-web-examples/realistic-handwritten-notes.png",
        "assets/gpt-image-2-web-examples/welcome-to-the-art-gallery-sign.webp",
        "assets/gpt-image-2-web-examples/world-map-topographic-details-and-cities.webp",
        "assets/gpt-image-2-x-discussions/just-upload-one-portrait-photo-yourself-generate-1.jpg",
        "assets/gpt-image-2-x-discussions/luxury-glam-beauty-portrait-1.jpg",
        "assets/gpt-image-2-x-discussions/luxury-glam-beauty-portrait-2.jpg",
        "assets/gpt-image-2-x-discussions/seedance-2-0-nano-banana-etc-prompts-1.jpg",
        "assets/gpt-image-2-x-discussions/singapore-team-realistic-photo-case-1.jpg",
        "assets/gpt-image-2-x-discussions/suppress-fragmented-rendering-negative-prompt-1.jpg",
        "assets/readme-gpt-image-2-prompts-cover.png",
        "assets/README.md",
    }
)


class ErickkkytAdapterError(AdapterError):
    """Stable fail-closed error for the fixed erickkkyt source shape."""


def _shape(message: str) -> ErickkkytAdapterError:
    return ErickkkytAdapterError("source_shape_invalid", message)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape(f"{label} must be a nonempty string")
    return value


def _language(values: list[str]) -> str:
    if values == ["en"]:
        return "en"
    if values == ["zh"]:
        return "zh"
    return "mixed"


def _location(config: SourceConfig, path: str, native_id: str, selector: str) -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": native_id,
        "selector": selector,
    }


def parse_erickkkyt_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], str]:
    try:
        rows = json.loads(
            read_snapshot_text(
                snapshot_root,
                "prompts/prompts.json",
                label="prompts/prompts.json",
                error_factory=_shape,
                read_error_factory=lambda message: ErickkkytAdapterError("source_data_invalid", message),
            )
        )
    except json.JSONDecodeError as exc:
        raise ErickkkytAdapterError("source_data_invalid", "prompts/prompts.json must be valid JSON") from exc
    if not isinstance(rows, list) or not rows:
        raise ErickkkytAdapterError("source_data_invalid", "prompts/prompts.json must be a nonempty array")

    parsed: list[ParsedCase] = []
    seen_native_ids: set[str] = set()
    seen_pair_ids: set[str] = set()
    seen_image_paths: set[str] = set()
    for position, value in enumerate(rows, start=1):
        if not isinstance(value, dict) or set(value) != ROW_FIELDS:
            raise _shape(f"prompts[{position - 1}] must use the exact fixed field set")
        if value.get("index") != position:
            raise _shape(f"prompts[{position - 1}].index must equal its one-based position")
        native_id = _text(value.get("id"), f"prompts[{position - 1}].id")
        if SAFE_NATIVE_ID.fullmatch(native_id) is None:
            raise _shape(f"{native_id}: id is not a safe stable native identity")
        if native_id in seen_native_ids:
            raise ErickkkytAdapterError("source_duplicate_id", f"duplicate native id: {native_id}")
        seen_native_ids.add(native_id)
        raw_prompt = _text(value.get("prompt"), f"{native_id}.prompt")
        if len(re.sub(r"\s+", "", normalize_prompt(raw_prompt))) < 8:
            raise ErickkkytAdapterError("source_prompt_invalid", f"{native_id}: prompt is too short")
        if value.get("model") != "gpt-image-2":
            raise _shape(f"{native_id}: model must remain gpt-image-2")
        images = value.get("images")
        pair_ids = value.get("pair_ids")
        dimensions = value.get("image_dimensions")
        if not isinstance(images, list) or not images or not all(isinstance(item, str) for item in images):
            raise _shape(f"{native_id}: images must be a nonempty string array")
        if not isinstance(pair_ids, list) or len(pair_ids) != len(images) or not all(isinstance(item, str) for item in pair_ids):
            raise _shape(f"{native_id}: pair_ids must align one-to-one with images")
        if not isinstance(dimensions, list) or len(dimensions) != len(images):
            raise _shape(f"{native_id}: image_dimensions must align one-to-one with images")
        if value.get("image_count") != len(images) or value.get("image") != images[0]:
            raise _shape(f"{native_id}: image/image_count diverges from images")
        if len(images) != len(set(images)) or len(pair_ids) != len(set(pair_ids)):
            raise _shape(f"{native_id}: images and pair_ids must be unique within the record")
        languages = value.get("languages")
        if not isinstance(languages, list) or not languages or not all(isinstance(item, str) and item for item in languages):
            raise _shape(f"{native_id}: languages must be a nonempty string array")
        for field in ("author", "author_name", "date", "published", "source", "source_url", "image_aspect_ratio"):
            _text(value.get(field), f"{native_id}.{field}")
        for field in ("image_width", "image_height"):
            if not isinstance(value.get(field), int) or isinstance(value.get(field), bool) or value[field] <= 0:
                raise _shape(f"{native_id}.{field} must be a positive integer")

        source_case_key = f"{source_config.source_id}:{native_id}"
        prompt_id = f"prompt:sha256:{prompt_sha256(raw_prompt)}"
        case_location = _location(source_config, "prompts/prompts.json", native_id, f"records[id={native_id}]")
        prompt_location = _location(source_config, "prompts/prompts.json", native_id, f"records[id={native_id}].prompt")
        bindings: list[AssetPathBinding] = []
        references: list[dict[str, Any]] = []
        pairings: list[dict[str, Any]] = []
        for image_index, (image_value, pair_id, dimension) in enumerate(zip(images, pair_ids, dimensions, strict=True)):
            if SAFE_PAIR_ID.fullmatch(pair_id) is None or pair_id in seen_pair_ids:
                raise ErickkkytAdapterError("source_duplicate_id", f"duplicate or unsafe pair id: {pair_id}")
            seen_pair_ids.add(pair_id)
            image_path = safe_repository_path(image_value, label=f"{native_id}.images[{image_index}]", error_factory=_shape)
            if image_path in seen_image_paths:
                raise _shape(f"image path is reused across records: {image_path}")
            seen_image_paths.add(image_path)
            snapshot_file(snapshot_root, image_path, label=f"{native_id} image {image_index}", error_factory=_shape)
            if not isinstance(dimension, dict) or set(dimension) != DIMENSION_FIELDS or dimension.get("image") != image_value:
                raise _shape(f"{native_id}.image_dimensions[{image_index}] does not bind its image")
            width = dimension.get("width")
            height = dimension.get("height")
            if not isinstance(width, int) or isinstance(width, bool) or width <= 0 or not isinstance(height, int) or isinstance(height, bool) or height <= 0:
                raise _shape(f"{native_id}.image_dimensions[{image_index}] dimensions must be positive integers")
            _text(dimension.get("aspect_ratio"), f"{native_id}.image_dimensions[{image_index}].aspect_ratio")
            role = "output_primary" if image_index == 0 else "output_secondary"
            asset_ref_id = f"asset-ref:{source_case_key}:{pair_id}"
            image_location = _location(
                source_config, image_path, native_id, f"records[id={native_id}].images[{image_index}]"
            )
            references.append(
                {
                    "asset_ref_id": asset_ref_id,
                    "role": role,
                    "resolution_state": "unresolved",
                    "source_location": image_location,
                    "extensions": {
                        "erickkkyt.variant": {
                            "pair_id": pair_id,
                            "source_index": image_index,
                            "dimensions": copy.deepcopy(dimension),
                        }
                    },
                }
            )
            pairings.append(
                {
                    "prompt_id": prompt_id,
                    "asset_ref_id": asset_ref_id,
                    "method": "explicit_structured_reference",
                    "status": "strong",
                    "evidence": [case_location, prompt_location, image_location],
                }
            )
            bindings.append(AssetPathBinding(asset_ref_id, image_path))
        metadata = {key: copy.deepcopy(value[key]) for key in ROW_FIELDS - {"prompt", "image", "images", "image_dimensions"}}
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": case_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": raw_prompt,
                "language": _language(languages),
                "source_location": prompt_location,
            },
            "asset_references": references,
            "pairings": pairings,
            "source_claim": {
                "evidence_status": "source_claimed",
                "model_raw": "gpt-image-2",
                "parameters_raw": None,
            },
            "raw_tags": sorted(set([str(value["source"]), *languages])),
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Repository license is unasserted; internal ingestion does not authorize publication.",
            },
            "extensions": {"erickkkyt.source": {"record": metadata, "registry_rights": source_config.rights}},
        }
        parsed.append(ParsedCase(source_case_key, native_id, tuple(bindings), adapter_record))
    asset_files = regular_relative_files(snapshot_root, "assets", error_factory=_shape)
    if asset_files - seen_image_paths != KNOWN_FIXED_ORPHAN_ASSET_FILES or seen_image_paths - asset_files:
        raise _shape("asset file set differs from manifest plus the fixed non-case files")
    parsed.sort(key=lambda item: item.source_case_key)
    return parsed, "gpt-image-2"
