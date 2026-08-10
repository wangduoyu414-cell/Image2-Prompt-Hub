"""Strict compiled-manifest adapter for the frozen ConardLi gallery."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ..registry import SourceConfig
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import (
    read_snapshot_text,
    regular_relative_files,
    safe_repository_path,
    snapshot_file,
)


SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX_ACCENT = re.compile(r"^#[0-9A-Fa-f]{6}$")
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")

TOP_LEVEL_FIELDS = frozenset({"generated_at", "summary", "categories", "templates", "cases"})
SUMMARY_FIELDS = frozenset({"templates", "cases"})
CATEGORY_FIELDS = frozenset({"accent", "cn", "key", "label", "ready", "templates", "total"})
TEMPLATE_FIELDS = frozenset({"cases_count", "category", "content", "description", "key", "label", "md_path", "name"})
CASE_FIELDS = frozenset(
    {
        "id",
        "category",
        "category_label",
        "category_accent",
        "template_key",
        "template_label",
        "idx",
        "title",
        "brief",
        "format",
        "prompt_path",
        "prompt_url",
        "image_url",
        "thumb_url",
        "has_image",
        "prompt_content",
    }
)
MAPPING_TOP_FIELDS = frozenset({"summary", "items"})
MAPPING_ITEM_FIELDS = frozenset({"category", "template_basename", "template_md", "prompt_dir", "source_md", "cases"})
MAPPING_CASE_FIELDS = frozenset({"idx", "title", "brief", "format", "file"})


class ConardLiAdapterError(AdapterError):
    """Stable, fail-closed parsing error for the ConardLi compiled source."""


def _shape_error(message: str) -> ConardLiAdapterError:
    return ConardLiAdapterError("source_shape_invalid", message)


def _data_error(message: str) -> ConardLiAdapterError:
    return ConardLiAdapterError("source_data_invalid", message)


def _prompt_error(message: str) -> ConardLiAdapterError:
    return ConardLiAdapterError("source_prompt_invalid", message)


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape_error(f"{label} must be a nonempty string")
    return value


def _require_count(value: Any, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0):
        qualifier = "positive integer" if positive else "nonnegative integer"
        raise _shape_error(f"{label} must be a {qualifier}")
    return value


def _safe_slug(value: Any, label: str) -> str:
    text = _require_string(value, label)
    if not SAFE_SLUG.fullmatch(text):
        raise _shape_error(f"{label} must use a safe lowercase slug")
    return text


def _safe_path(value: Any, label: str) -> str:
    return safe_repository_path(_require_string(value, label), label=label, error_factory=_shape_error)


def _location(config: SourceConfig, path: str, native_id: str, selector: str) -> dict[str, str]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": native_id,
        "selector": selector,
    }


def _load_json(snapshot_root: Path, path: str, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(read_snapshot_text(snapshot_root, path, label=label, error_factory=_shape_error, read_error_factory=_data_error))
    except json.JSONDecodeError as exc:
        raise _data_error(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise _data_error(f"{label} must contain a JSON object")
    return value


def _validate_generated_at(value: Any) -> str:
    text = _require_string(value, "generated_at")
    if not RFC3339.fullmatch(text):
        raise _shape_error("generated_at must be an RFC3339 timestamp with an explicit timezone")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _shape_error("generated_at must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise _shape_error("generated_at must include a timezone")
    return text


def _validate_summary(value: Any, *, label: str, template_count: int, case_count: int) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != SUMMARY_FIELDS:
        raise _shape_error(f"{label} must use the exact templates/cases field set")
    summary = {
        "templates": _require_count(value.get("templates"), f"{label}.templates"),
        "cases": _require_count(value.get("cases"), f"{label}.cases"),
    }
    if summary != {"templates": template_count, "cases": case_count}:
        raise _shape_error(f"{label} does not match compiled template/case counts")
    return summary


def _validate_categories(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise _shape_error("categories must be a nonempty object")
    result: dict[str, dict[str, Any]] = {}
    for key, raw in value.items():
        category_key = _safe_slug(key, "category key")
        if not isinstance(raw, dict) or set(raw) != CATEGORY_FIELDS:
            raise _shape_error(f"category {category_key} must use the exact compiled field set")
        if _safe_slug(raw.get("key"), f"category {category_key}.key") != category_key:
            raise _shape_error(f"category {category_key}.key does not match its object key")
        if not HEX_ACCENT.fullmatch(_require_string(raw.get("accent"), f"category {category_key}.accent")):
            raise _shape_error(f"category {category_key}.accent must be a hex color")
        _require_string(raw.get("cn"), f"category {category_key}.cn")
        _require_string(raw.get("label"), f"category {category_key}.label")
        _require_count(raw.get("ready"), f"category {category_key}.ready", positive=True)
        template_keys = raw.get("templates")
        if not isinstance(template_keys, list) or not template_keys:
            raise _shape_error(f"category {category_key}.templates must be a nonempty array")
        normalized_templates = [_safe_path(item, f"category {category_key}.templates") for item in template_keys]
        if len(set(normalized_templates)) != len(normalized_templates):
            raise _shape_error(f"category {category_key}.templates contains duplicates")
        _require_count(raw.get("total"), f"category {category_key}.total", positive=True)
        result[category_key] = copy.deepcopy(raw)
    return result


def _validate_templates(value: Any, categories: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise _shape_error("templates must be a nonempty object")
    result: dict[str, dict[str, Any]] = {}
    for key, raw in value.items():
        template_key = _safe_path(key, "template key")
        if not isinstance(raw, dict) or set(raw) != TEMPLATE_FIELDS:
            raise _shape_error(f"template {template_key} must use the exact compiled field set")
        category = _safe_slug(raw.get("category"), f"template {template_key}.category")
        if category not in categories:
            raise _shape_error(f"template {template_key} references an unknown category")
        name = _safe_slug(raw.get("name"), f"template {template_key}.name")
        if template_key != f"{category}/{name}" or raw.get("key") != template_key:
            raise _shape_error(f"template {template_key} key/category/name mapping is inconsistent")
        _require_string(raw.get("label"), f"template {template_key}.label")
        _safe_path(raw.get("md_path"), f"template {template_key}.md_path")
        if raw.get("content") is not None and not isinstance(raw.get("content"), str):
            raise _shape_error(f"template {template_key}.content must be null or text")
        if raw.get("description") is not None and not isinstance(raw.get("description"), str):
            raise _shape_error(f"template {template_key}.description must be null or text")
        _require_count(raw.get("cases_count"), f"template {template_key}.cases_count", positive=True)
        result[template_key] = copy.deepcopy(raw)

    for category_key, category in categories.items():
        listed = [_safe_path(item, f"category {category_key}.templates") for item in category["templates"]]
        actual = {key for key, template in result.items() if template["category"] == category_key}
        if set(listed) != actual:
            raise _shape_error(f"category {category_key}.templates does not exactly match the template index")
        if int(category["total"]) != sum(int(result[key]["cases_count"]) for key in actual):
            raise _shape_error(f"category {category_key}.total does not match its template case counts")
        if int(category["ready"]) != int(category["total"]):
            raise _shape_error(f"category {category_key}.ready must equal its compiled total")
    return result


def _path_from_case_url(value: Any, *, expected: str, label: str) -> None:
    if _require_string(value, label) != f"/case/{expected}":
        raise _shape_error(f"{label} does not match its stable native file mapping")


def _nonempty_regular_file(snapshot_root: Path, path: str, *, label: str) -> None:
    file_path = snapshot_file(snapshot_root, path, label=label, error_factory=_shape_error)
    try:
        if file_path.stat().st_size <= 0:
            raise _shape_error(f"{label} must be nonempty")
    except OSError as exc:
        raise _shape_error(f"{label} is unreadable") from exc


def _validate_cases(
    snapshot_root: Path,
    value: Any,
    *,
    categories: dict[str, dict[str, Any]],
    templates: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(value, list) or not value:
        raise _shape_error("cases must be a nonempty array")
    cases: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    for index, raw in enumerate(value):
        label = f"cases[{index}]"
        if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
            raise _shape_error(f"{label} must use the exact compiled field set")
        category_key = _safe_slug(raw.get("category"), f"{label}.category")
        category = categories.get(category_key)
        if category is None:
            raise _shape_error(f"{label} references an unknown category")
        template_key = _safe_path(raw.get("template_key"), f"{label}.template_key")
        template = templates.get(template_key)
        if template is None or template.get("category") != category_key:
            raise _shape_error(f"{label} references an unknown or cross-category template")
        if raw.get("category_label") != category["cn"] or raw.get("category_accent") != category["accent"]:
            raise _shape_error(f"{label} category label/accent does not match the category index")
        if raw.get("template_label") != template["label"]:
            raise _shape_error(f"{label} template label does not match the template index")
        idx = _require_count(raw.get("idx"), f"{label}.idx", positive=True)
        native_id = _require_string(raw.get("id"), f"{label}.id")
        if native_id != f"{template_key}/{idx}":
            raise _shape_error(f"{label}.id does not match category/template/idx")
        if native_id in by_id:
            raise ConardLiAdapterError("source_duplicate_id", f"duplicate case id: {native_id}")
        prompt_format = raw.get("format")
        if prompt_format not in {"json", "txt"}:
            raise _shape_error(f"{label}.format must be json or txt")
        if raw.get("has_image") is not True:
            raise _shape_error(f"{label}.has_image must be true")
        _require_string(raw.get("title"), f"{label}.title")
        _require_string(raw.get("brief"), f"{label}.brief")
        prompt_content = _require_string(raw.get("prompt_content"), f"{label}.prompt_content")
        if not normalize_prompt(prompt_content):
            raise _prompt_error(f"{label}.prompt_content must be nonempty")
        prompt_path = _safe_path(raw.get("prompt_path"), f"{label}.prompt_path")
        if prompt_path != f"{native_id}.{prompt_format}":
            raise _shape_error(f"{label}.prompt_path does not match id and format")
        image_path = f"{native_id}.png"
        thumbnail_path = f"{native_id}-thumb.webp"
        _path_from_case_url(raw.get("prompt_url"), expected=prompt_path, label=f"{label}.prompt_url")
        _path_from_case_url(raw.get("image_url"), expected=image_path, label=f"{label}.image_url")
        _path_from_case_url(raw.get("thumb_url"), expected=thumbnail_path, label=f"{label}.thumb_url")
        for path in (prompt_path, image_path, thumbnail_path):
            if path in seen_paths:
                raise _shape_error(f"{label} has a duplicate compiled file path")
            seen_paths.add(path)
        actual_prompt = read_snapshot_text(
            snapshot_root,
            f"public/case/{prompt_path}",
            label=f"prompt file for {native_id}",
            error_factory=_shape_error,
            read_error_factory=_data_error,
        )
        if actual_prompt != prompt_content:
            raise _prompt_error(f"prompt file for {native_id} does not exactly match prompt_content")
        if prompt_format == "json":
            try:
                parsed_prompt = json.loads(actual_prompt)
            except json.JSONDecodeError as exc:
                raise _prompt_error(f"JSON prompt for {native_id} is invalid") from exc
            if not isinstance(parsed_prompt, dict):
                raise _prompt_error(f"JSON prompt for {native_id} must be an object")
        elif not actual_prompt.strip():
            raise _prompt_error(f"TXT prompt for {native_id} must be nonempty")
        _nonempty_regular_file(snapshot_root, f"public/case/{image_path}", label=f"PNG output for {native_id}")
        _nonempty_regular_file(snapshot_root, f"public/case/{thumbnail_path}", label=f"thumbnail for {native_id}")
        copied = copy.deepcopy(raw)
        cases.append(copied)
        by_id[native_id] = copied

    counts = Counter(str(case["template_key"]) for case in cases)
    for template_key, template in templates.items():
        if counts.get(template_key, 0) != template["cases_count"]:
            raise _shape_error(f"template {template_key}.cases_count does not match its cases")
    for category_key, category in categories.items():
        if sum(1 for case in cases if case["category"] == category_key) != category["total"]:
            raise _shape_error(f"category {category_key}.total does not match its cases")
    return cases, by_id


def _validate_mapping(
    snapshot_root: Path,
    *,
    summary: dict[str, int],
    templates: dict[str, dict[str, Any]],
    cases_by_id: dict[str, dict[str, Any]],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    mapping = _load_json(snapshot_root, "public/case/_mapping.json", label="public/case/_mapping.json")
    if set(mapping) != MAPPING_TOP_FIELDS:
        raise _shape_error("public/case/_mapping.json must use the exact summary/items field set")
    _validate_summary(mapping.get("summary"), label="mapping.summary", template_count=len(templates), case_count=len(cases_by_id))
    if mapping["summary"] != summary:
        raise _shape_error("mapping.summary does not exactly match cases.json summary")
    items = mapping.get("items")
    if not isinstance(items, list) or not items:
        raise _shape_error("mapping.items must be a nonempty array")
    seen_templates: set[str] = set()
    seen_cases: set[str] = set()
    mapping_rows: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for index, item in enumerate(items):
        label = f"mapping.items[{index}]"
        if not isinstance(item, dict) or set(item) != MAPPING_ITEM_FIELDS:
            raise _shape_error(f"{label} must use the exact compiled item field set")
        category = _safe_slug(item.get("category"), f"{label}.category")
        basename = _safe_slug(item.get("template_basename"), f"{label}.template_basename")
        template_key = f"{category}/{basename}"
        template = templates.get(template_key)
        if template is None or template_key in seen_templates:
            raise _shape_error(f"{label} does not map one unique compiled template")
        seen_templates.add(template_key)
        template_md = _safe_path(item.get("template_md"), f"{label}.template_md")
        source_md = _safe_path(item.get("source_md"), f"{label}.source_md")
        prompt_dir = _safe_path(item.get("prompt_dir"), f"{label}.prompt_dir")
        if template_md != template["md_path"]:
            raise _shape_error(f"{label}.template_md does not match the compiled template metadata")
        if source_md != f"{category}/{basename}.md" or prompt_dir != template_key:
            raise _shape_error(f"{label} source_md/prompt_dir does not match its compiled template")
        nested_cases = item.get("cases")
        if not isinstance(nested_cases, list) or not nested_cases:
            raise _shape_error(f"{label}.cases must be a nonempty array")
        if len(nested_cases) != template["cases_count"]:
            raise _shape_error(f"{label}.cases does not match template cases_count")
        for nested_index, nested in enumerate(nested_cases):
            nested_label = f"{label}.cases[{nested_index}]"
            if not isinstance(nested, dict) or set(nested) != MAPPING_CASE_FIELDS:
                raise _shape_error(f"{nested_label} must use the exact compiled nested-case field set")
            idx = _require_count(nested.get("idx"), f"{nested_label}.idx", positive=True)
            native_id = f"{template_key}/{idx}"
            case = cases_by_id.get(native_id)
            if case is None or native_id in seen_cases:
                raise _shape_error(f"{nested_label} does not map one unique compiled case")
            if nested.get("title") != case["title"] or nested.get("brief") != case["brief"]:
                raise _shape_error(f"{nested_label} title/brief does not match cases.json")
            if nested.get("format") != case["format"] or _safe_path(nested.get("file"), f"{nested_label}.file") != case["prompt_path"]:
                raise _shape_error(f"{nested_label} format/file does not match cases.json")
            seen_cases.add(native_id)
            mapping_rows[native_id] = (copy.deepcopy(item), copy.deepcopy(nested))
    if seen_templates != set(templates):
        raise _shape_error("mapping.items does not exactly cover compiled templates")
    if seen_cases != set(cases_by_id):
        raise _shape_error("mapping.items cases do not exactly cover cases.json")
    return mapping_rows


def _validate_file_set(snapshot_root: Path, cases: list[dict[str, Any]]) -> None:
    expected = {"public/case/_mapping.json", "public/case/INDEX.md"}
    for case in cases:
        native_id = str(case["id"])
        expected.update(
            {
                f"public/case/{case['prompt_path']}",
                f"public/case/{native_id}.png",
                f"public/case/{native_id}-thumb.webp",
            }
        )
    actual = regular_relative_files(snapshot_root, "public/case", error_factory=_shape_error)
    if actual != expected:
        raise _shape_error("public/case regular-file set does not exactly match the compiled manifest")


def parse_conardli_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], None]:
    """Parse the complete static gallery without heuristic pairing or discovery."""

    manifest = _load_json(snapshot_root, "src/data/cases.json", label="src/data/cases.json")
    if set(manifest) != TOP_LEVEL_FIELDS:
        raise _shape_error("src/data/cases.json must use the exact compiled top-level field set")
    _validate_generated_at(manifest.get("generated_at"))
    categories = _validate_categories(manifest.get("categories"))
    templates = _validate_templates(manifest.get("templates"), categories)
    cases, cases_by_id = _validate_cases(snapshot_root, manifest.get("cases"), categories=categories, templates=templates)
    summary = _validate_summary(
        manifest.get("summary"), label="summary", template_count=len(templates), case_count=len(cases)
    )
    mapping_rows = _validate_mapping(
        snapshot_root,
        summary=summary,
        templates=templates,
        cases_by_id=cases_by_id,
    )
    _validate_file_set(snapshot_root, cases)

    parsed: list[ParsedCase] = []
    for case in cases:
        native_id = str(case["id"])
        category_key = str(case["category"])
        template_key = str(case["template_key"])
        template_name = str(templates[template_key]["name"])
        mapping_item, mapping_case = mapping_rows[native_id]
        source_case_key = f"{source_config.source_id}:{native_id}"
        prompt_path = f"public/case/{case['prompt_path']}"
        image_path = f"public/case/{native_id}.png"
        thumbnail_path = f"public/case/{native_id}-thumb.webp"
        manifest_location = _location(
            source_config,
            "src/data/cases.json",
            native_id,
            f"cases[id={native_id}]",
        )
        mapping_location = _location(
            source_config,
            "public/case/_mapping.json",
            native_id,
            f"items[category={category_key},template_basename={template_name}].cases[idx={case['idx']}]",
        )
        prompt_location = _location(
            source_config,
            prompt_path,
            native_id,
            f"cases[id={native_id}].prompt_path",
        )
        image_location = _location(
            source_config,
            image_path,
            native_id,
            f"cases[id={native_id}].image_url",
        )
        thumbnail_location = _location(
            source_config,
            thumbnail_path,
            native_id,
            f"cases[id={native_id}].thumb_url",
        )
        prompt_id = f"prompt:sha256:{prompt_sha256(str(case['prompt_content']))}"
        asset_ref_id = f"asset-ref:{source_case_key}:output-primary"
        case_metadata = {key: copy.deepcopy(value) for key, value in case.items() if key != "prompt_content"}
        mapping_item_metadata = {key: copy.deepcopy(value) for key, value in mapping_item.items() if key != "cases"}
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": manifest_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": str(case["prompt_content"]),
                "language": "mixed",
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
                    "method": "stable_native_mapping",
                    "status": "strong",
                    "evidence": [manifest_location, mapping_location, prompt_location, image_location],
                }
            ],
            "source_claim": {
                "evidence_status": "unknown",
                "model_raw": None,
                "parameters_raw": None,
            },
            "raw_tags": [category_key],
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Registry review_required evidence is retained without approval or publication authorization.",
            },
            "extensions": {
                "conardli.source": {
                    "case": case_metadata,
                    "category": copy.deepcopy(categories[category_key]),
                    "template": copy.deepcopy(templates[template_key]),
                    "manifest_location": manifest_location,
                    "mapping": {"item": mapping_item_metadata, "case": mapping_case, "location": mapping_location},
                    "thumbnail_location": thumbnail_location,
                }
            },
        }
        parsed.append(
            ParsedCase(source_case_key, native_id, (AssetPathBinding(asset_ref_id, image_path),), adapter_record)
        )
    parsed.sort(key=lambda item: item.source_case_key)
    return parsed, None
