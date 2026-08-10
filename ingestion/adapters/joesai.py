"""Strict manifest-and-Markdown adapter for the frozen JoeSai pilot."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..registry import SourceConfig
from .base import AdapterError, AssetPathBinding, ParsedCase, normalize_prompt, prompt_sha256
from .snapshot_files import (
    fixed_snapshot_root as _shared_fixed_snapshot_root,
    read_snapshot_text as _shared_read_snapshot_text,
    regular_relative_files as _shared_regular_relative_files,
    reject_symlink_components as _shared_reject_symlink_components,
    safe_repository_path as _shared_safe_repository_path,
    snapshot_file as _shared_snapshot_file,
)


SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_IMAGE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.png$")
MANIFEST_FIELDS = frozenset(
    {
        "slug",
        "category",
        "title",
        "title_zh",
        "use_case",
        "asset_type",
        "languages",
        "featured",
        "example_image",
    }
)


class JoeSaiAdapterError(AdapterError):
    """Stable, fail-closed parsing error for the JoeSai source shape."""


def _shape_error(message: str) -> JoeSaiAdapterError:
    return JoeSaiAdapterError("source_shape_invalid", message)


def _safe_path(value: str, *, label: str) -> str:
    return _shared_safe_repository_path(value, label=label, error_factory=_shape_error)


def _fixed_snapshot_root(snapshot_root: Path) -> Path:
    return _shared_fixed_snapshot_root(snapshot_root, error_factory=_shape_error)


def _reject_symlink_components(root: Path, candidate: Path, *, label: str) -> None:
    _shared_reject_symlink_components(root, candidate, label=label, error_factory=_shape_error)


def _snapshot_file(snapshot_root: Path, relative_path: str, *, label: str) -> Path:
    return _shared_snapshot_file(snapshot_root, relative_path, label=label, error_factory=_shape_error)


def _read_snapshot_text(snapshot_root: Path, relative_path: str, *, label: str) -> str:
    return _shared_read_snapshot_text(
        snapshot_root,
        relative_path,
        label=label,
        error_factory=_shape_error,
        read_error_factory=lambda message: JoeSaiAdapterError("source_data_invalid", message),
    )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _shape_error(f"{label} must be a nonempty string")
    return value


def _safe_slug(value: Any, label: str) -> str:
    text = _require_text(value, label)
    if not SAFE_SLUG.fullmatch(text):
        raise _shape_error(f"{label} must use a safe lowercase slug")
    return text


def _manifest_rows(snapshot_root: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(_read_snapshot_text(snapshot_root, "data/prompts.json", label="data/prompts.json"))
    except json.JSONDecodeError as exc:
        raise JoeSaiAdapterError("source_data_invalid", "data/prompts.json must be valid JSON") from exc
    if not isinstance(payload, list) or not payload:
        raise JoeSaiAdapterError("source_data_invalid", "data/prompts.json must be a nonempty array")
    rows: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    seen_images: set[str] = set()
    for index, value in enumerate(payload):
        if not isinstance(value, dict) or set(value) != MANIFEST_FIELDS:
            raise _shape_error(f"manifest[{index}] must use the exact JoeSai field set")
        slug = _safe_slug(value.get("slug"), f"manifest[{index}].slug")
        category = _safe_slug(value.get("category"), f"manifest[{index}].category")
        if slug in seen_slugs:
            raise JoeSaiAdapterError("source_duplicate_id", f"duplicate manifest slug: {slug}")
        seen_slugs.add(slug)
        for field in ("title", "title_zh", "use_case", "asset_type"):
            _require_text(value.get(field), f"manifest[{index}].{field}")
        languages = value.get("languages")
        if not isinstance(languages, list) or set(languages) != {"en", "zh-CN"} or len(languages) != 2:
            raise _shape_error(f"manifest[{index}].languages must be the exact en/zh-CN language pair")
        if not isinstance(value.get("featured"), bool):
            raise _shape_error(f"manifest[{index}].featured must be boolean")
        image_path = _safe_path(_require_text(value.get("example_image"), f"manifest[{index}].example_image"), label="example_image")
        image_parts = image_path.split("/")
        if len(image_parts) != 3 or image_parts[:2] != ["assets", "examples"] or not SAFE_IMAGE.fullmatch(image_parts[2]):
            raise _shape_error(f"manifest[{index}].example_image must be a safe assets/examples PNG path")
        if image_path in seen_images:
            raise _shape_error(f"duplicate manifest example_image: {image_path}")
        seen_images.add(image_path)
        row = dict(value)
        row["slug"] = slug
        row["category"] = category
        row["example_image"] = image_path
        rows.append(row)
    return rows


def _regular_relative_files(root: Path, relative_root: str, suffix: str | None = None) -> set[str]:
    return _shared_regular_relative_files(root, relative_root, suffix=suffix, error_factory=_shape_error)


def _validate_file_sets(snapshot_root: Path, rows: list[dict[str, Any]]) -> None:
    expected_pages = {f"prompts/{row['category']}/{row['slug']}.md" for row in rows}
    actual_pages = _regular_relative_files(snapshot_root, "prompts")
    if any(not path.endswith(".md") for path in actual_pages):
        raise _shape_error("prompts contains a non-Markdown file outside the fixed page contract")
    if actual_pages != expected_pages | {"prompts/README.md"}:
        raise _shape_error("case Markdown pages must exactly equal manifest paths plus prompts/README.md")
    expected_images = {str(row["example_image"]) for row in rows}
    actual_images = _regular_relative_files(snapshot_root, "assets/examples")
    if actual_images != expected_images:
        raise _shape_error("example image files must exactly equal manifest example_image values")


def _skip_blank(lines: list[str], cursor: int) -> int:
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    return cursor


def _section_text(lines: list[str], cursor: int, *, label: str) -> tuple[str, int]:
    content: list[str] = []
    while cursor < len(lines) and not lines[cursor].startswith("## "):
        if lines[cursor].startswith("#") or lines[cursor] == "```" or lines[cursor].startswith("```"):
            raise _shape_error(f"{label} contains an unexpected heading or fence")
        content.append(lines[cursor])
        cursor += 1
    # Blank lines delimit Markdown sections; preserve all interior source text
    # while excluding those structural separators from extension values.
    while content and not content[0].strip():
        content.pop(0)
    while content and not content[-1].strip():
        content.pop()
    value = "\n".join(content)
    if not normalize_prompt(value):
        raise _shape_error(f"{label} must be nonempty")
    return value, cursor


def _text_fence(lines: list[str], cursor: int, *, label: str) -> tuple[str, int]:
    cursor = _skip_blank(lines, cursor)
    if cursor >= len(lines) or lines[cursor] != "```text":
        raise _shape_error(f"{label} must contain one text fence")
    cursor += 1
    content: list[str] = []
    while cursor < len(lines) and lines[cursor] != "```":
        content.append(lines[cursor])
        cursor += 1
    if cursor >= len(lines):
        raise _shape_error(f"{label} fence is not closed")
    value = "\n".join(content)
    if not normalize_prompt(value):
        raise JoeSaiAdapterError("source_prompt_invalid", f"{label} must be nonempty")
    cursor += 1
    return value, _skip_blank(lines, cursor)


def _parse_markdown(markdown: str, row: dict[str, Any]) -> tuple[str, str, str, str | None]:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0] != f"# {row['title']}":
        raise _shape_error("Markdown H1 must exactly equal the manifest title")
    cursor = _skip_blank(lines, 1)
    if cursor >= len(lines) or lines[cursor] != "## Best For":
        raise _shape_error("Markdown must place Best For immediately after its H1")
    best_for, cursor = _section_text(lines, cursor + 1, label="Best For")
    if cursor >= len(lines) or lines[cursor] != "## Prompt (EN)":
        raise _shape_error("Markdown must place one Prompt (EN) section after Best For")
    english, cursor = _text_fence(lines, cursor + 1, label="Prompt (EN)")
    if len(re.sub(r"\s+", "", normalize_prompt(english))) < 80:
        raise JoeSaiAdapterError("source_prompt_invalid", "Prompt (EN) is too short")
    if cursor >= len(lines) or lines[cursor] != "## 提示词（中文）":
        raise _shape_error("Markdown must place one Chinese Prompt section after Prompt (EN)")
    chinese, cursor = _text_fence(lines, cursor + 1, label="Chinese Prompt")
    why: str | None = None
    if cursor < len(lines) and lines[cursor] == "## Why It Works":
        why, cursor = _section_text(lines, cursor + 1, label="Why It Works")
    cursor = _skip_blank(lines, cursor)
    if cursor != len(lines):
        raise _shape_error("Markdown contains an unexpected, duplicate, or out-of-order section")
    return english, chinese, best_for, why


def _location(config: SourceConfig, path: str, slug: str, selector: str) -> dict[str, Any]:
    return {
        "source_path": path,
        "source_url": config.raw_url(path),
        "native_id": slug,
        "selector": selector,
    }


def parse_joesai_snapshot(snapshot_root: Path, source_config: SourceConfig) -> tuple[list[ParsedCase], None]:
    """Parse the complete, static JoeSai manifest without heuristic matching."""

    rows = _manifest_rows(snapshot_root)
    _validate_file_sets(snapshot_root, rows)
    cases: list[ParsedCase] = []
    for row in rows:
        slug = str(row["slug"])
        page_path = f"prompts/{row['category']}/{slug}.md"
        english, chinese, best_for, why = _parse_markdown(
            _read_snapshot_text(snapshot_root, page_path, label=f"Markdown page for {slug}"), row
        )
        source_case_key = f"{source_config.source_id}:{slug}"
        prompt_id = f"prompt:sha256:{prompt_sha256(english)}"
        manifest_location = _location(source_config, "data/prompts.json", slug, f"manifest[slug={slug}]")
        case_location = _location(source_config, page_path, slug, f"manifest slug={slug}")
        prompt_location = _location(source_config, page_path, slug, "## Prompt (EN) fenced block")
        image_location = _location(source_config, str(row["example_image"]), slug, "manifest entry example_image")
        asset_ref_id = f"asset-ref:{source_case_key}:output-primary"
        adapter_record = {
            "source_case_key": source_case_key,
            "source_case_locator": case_location,
            "state": "contract_valid",
            "prompt": {
                "prompt_id": prompt_id,
                "raw_text": english,
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
                    "method": "explicit_markdown_block",
                    "status": "strong",
                    "evidence": [manifest_location, prompt_location, image_location],
                }
            ],
            "source_claim": {
                "evidence_status": "unknown",
                "model_raw": None,
                "parameters_raw": None,
            },
            "raw_tags": [str(row["category"])],
            "rights_evidence": {
                "prompt_rights_status": "unknown",
                "asset_rights_status": "unknown",
                "evidence_urls": [],
                "note": "Registry review_required evidence is retained without approval or publication authorization.",
            },
            "extensions": {
                "joesai.source": {
                    "manifest": row,
                    "manifest_location": manifest_location,
                    "best_for_raw": best_for,
                    "prompt_zh_raw": chinese,
                    "why_it_works_raw": why,
                }
            },
        }
        cases.append(
            ParsedCase(
                source_case_key,
                slug,
                (AssetPathBinding(asset_ref_id, str(row["example_image"])),),
                adapter_record,
            )
        )
    cases.sort(key=lambda item: item.source_case_key)
    return cases, None
