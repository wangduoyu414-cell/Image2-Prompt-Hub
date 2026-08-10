"""Build and validate the Phase 2 high-quality new-source admission v2 evidence."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.internal_preview.repository import SOURCE_IDS, _build_index, _cache_key
from ingestion.assets import AssetError, read_asset
from ingestion.registry import load_source_config


SCHEMA_VERSION = "phase2-source-expansion-admission-v2"
NORMALIZATION_VERSION = "exact-overlap-v1-nfkc-casefold-whitespace"
WITHIN_SOURCE_DEDUPE_VERSION = "within-source-exact-v2-prompt-cross-record-url-image"
LINT_VERSION = "source-quality-lint-v2-risk-patterns-and-low-information"
CURRENT_DATA_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/source-git-v1")
CURRENT_CACHE = Path(r"C:/Users/admin/.codex/runtime/image2/internal-preview/index-v1.json")
EXPECTED_CANDIDATES = {
    "ecomimagelab-ecommerce-gpt-image-prompts": {
        "repo": "ecomimagelab/ecommerce-gpt-image-prompts",
        "default_branch": "main",
        "strategy": "ecomimagelab_prompt_variants_v1",
        "source_path": "data/prompts.json",
        "repo_id": 1306555302,
        "family_role": "canonical_repository",
    },
    "hiapiai-awesome-gpt-image-2-prompts": {
        "repo": "HiAPIAI/awesome-gpt-image-2-prompts",
        "default_branch": "main",
        "strategy": "hiapiai_prompt_items_with_variants_v1",
        "source_path": "data/prompts.json",
        "repo_id": 1225309835,
        "family_role": "canonical_repository",
    },
    "imaginevid-awesome-gpt-image-2-prompts-and-skills": {
        "repo": "imagineVid/Awesome-gpt-image-2-prompts-and-skills",
        "default_branch": "main",
        "strategy": "imaginevid_remote_media_manifest_v1",
        "source_path": "data/prompts.json",
        "repo_id": 1296504164,
        "family_role": "canonical_repository",
    },
}
THRESHOLDS = {
    "minimum_unique_valid_cases": 50,
    "minimum_pair_rate": 0.90,
    "maximum_broken_asset_rate": 0.05,
    "maximum_duplicate_rate": 0.20,
    "latest_substantive_update_days": 180,
    "minimum_substantive_update_dates_365": 2,
}
RISK_PATTERNS: dict[str, tuple[str, ...]] = {
    "adult_or_sexualized": (
        " nude ", " naked ", " lingerie ", " cleavage ", " seductive ", " sexy ", " erotic ",
        "裸", "性感", "爆乳", "内衣", "诱惑",
    ),
    "public_figure_or_celebrity": (
        "sam altman", "donald trump", "trump", "kim jong", "elon musk", "taylor swift", "刘亦菲",
        "ceo of openai",
    ),
    "identity_or_official_document": (
        "passport", "driver's license", "drivers license", "national id", "identity card", "citizenship card",
        "身份证", "护照", "驾驶证", "证件",
    ),
    "watermark_or_attribution_removal": ("remove watermark", "without watermark", "去水印", "移除水印"),
    "third_party_ip_or_character": (
        "pokemon", "pokémon", "disney", "ghibli", "mario", "naruto", "one piece", "dragon ball",
        "marvel", "dc comics", "harry potter", "minecraft", "原神", "宝可梦", "吉卜力",
    ),
    "platform_or_brand_replication": (
        "iphone", "ios", "instagram", "tiktok", "douyin", "xiaohongshu", "小红书", "抖音",
        "wechat", "微信", "twitter", " x page ", "notion", "chatgpt", "shopify", "tmall", "shopee",
    ),
}
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ValidationFailure(RuntimeError):
    """Fail-closed v2 admission conclusion."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot load JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValidationFailure(f"{path.name} must contain one object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _hash_lines(values: Iterable[str]) -> str:
    return _sha256_bytes("\n".join(values).encode("utf-8"))


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValidationFailure(f"{label} is not a valid date-time") from exc
    if parsed.tzinfo is None:
        raise ValidationFailure(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _normalize_prompt(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _normalize_source_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.casefold().removeprefix("www.")
    if host in {"twitter.com", "mobile.twitter.com"}:
        host = "x.com"
    path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"
    if host == "github.com" and len([part for part in path.split("/") if part]) == 2:
        return None
    if host == "x.com":
        match = re.fullmatch(r"/([^/]+)/status/(\d+)", path, re.I)
        if match:
            path = f"/{match.group(1).casefold()}/status/{match.group(2)}"
    return urllib.parse.urlunsplit(("https", host, path, "", ""))


def _safe_rel(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.startswith(("/", "\\")):
        raise ValidationFailure(f"{label} must be a nonempty repository-relative path")
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not pure.parts or any(part in {"..", ""} for part in pure.parts) or ":" in pure.parts[0]:
        raise ValidationFailure(f"{label} escapes the repository")
    return str(pure)


def _risk_flags(prompt: str) -> list[str]:
    haystack = f" {_normalize_prompt(prompt)} "
    flags = [name for name, needles in RISK_PATTERNS.items() if any(needle in haystack for needle in needles)]
    if len(_normalize_prompt(prompt)) < 80 or len(prompt.split()) < 15:
        flags.append("low_information_prompt")
    return sorted(set(flags))


def _expected_sample_size(unique_valid: int) -> int:
    return min(unique_valid, 60, max(30, math.ceil(unique_valid * 0.15))) if unique_valid else 0


def _unique_valid_cases(cases: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    prompt_hashes: set[str] = set()
    source_url_records: dict[str, str] = {}
    image_records: dict[str, str] = {}
    for item in sorted(cases, key=lambda value: str(value["case_id"])):
        prompt_hash = str(item.get("prompt_sha256") or "")
        record_id = str(item.get("source_record_id") or item["case_id"])
        source_url = item.get("source_url_key")
        fixed_images = sorted(
            str(output["content_sha256"])
            for output in item.get("outputs", [])
            if output.get("authority") == "fixed_local" and output.get("content_sha256")
        )
        cross_record_url_duplicate = (
            isinstance(source_url, str)
            and source_url in source_url_records
            and source_url_records[source_url] != record_id
        )
        cross_record_image_duplicate = any(
            image_hash in image_records and image_records[image_hash] != record_id for image_hash in fixed_images
        )
        if (
            not item.get("strong_pairing")
            or not item.get("outputs")
            or not prompt_hash
            or prompt_hash in prompt_hashes
            or cross_record_url_duplicate
            or cross_record_image_duplicate
        ):
            continue
        prompt_hashes.add(prompt_hash)
        if isinstance(source_url, str):
            source_url_records.setdefault(source_url, record_id)
        for image_hash in fixed_images:
            image_records.setdefault(image_hash, record_id)
        selected.append(item)
    return selected


def _select_quality_sample(
    cases: Sequence[Mapping[str, Any]],
    size: int,
    overlap_groups: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    if size <= 0:
        return []
    by_id = {str(item["case_id"]): item for item in cases}
    selected: list[str] = []

    def add(case_id: str) -> None:
        if case_id in by_id and case_id not in selected and len(selected) < size:
            selected.append(case_id)

    groups: dict[str, list[str]] = defaultdict(list)
    for item in cases:
        groups[str(item.get("category") or "uncategorized")].append(str(item["case_id"]))
    for category in sorted(groups):
        values = sorted(groups[category])
        add(values[0])
    for flag in sorted(RISK_PATTERNS) + ["low_information_prompt"]:
        values = sorted(str(item["case_id"]) for item in cases if flag in item.get("risk_flags", []))
        if values:
            add(values[0])
    for name in sorted(overlap_groups or {}):
        values = sorted(str(value) for value in (overlap_groups or {})[name] if str(value) in by_id)
        if values:
            add(values[0])
            add(values[len(values) // 2])
            add(values[-1])
    multi = sorted(str(item["case_id"]) for item in cases if len(item.get("outputs", [])) > 1)
    if multi:
        add(multi[0])
        add(multi[-1])
    lengths = sorted((int(item["prompt_length"]), str(item["case_id"])) for item in cases)
    if lengths:
        add(lengths[0][1])
        add(lengths[len(lengths) // 2][1])
        add(lengths[-1][1])
    for category in sorted(groups):
        values = sorted(groups[category])
        add(values[len(values) // 2])
        add(values[-1])
    remaining = sorted(
        (str(item["case_id"]) for item in cases if str(item["case_id"]) not in selected),
        key=lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest(),
    )
    for case_id in remaining:
        add(case_id)
    return selected


def _run(command: Sequence[str], *, cwd: Path, timeout: int = 900) -> str:
    completed = subprocess.run(
        list(command), cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"},
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise ValidationFailure(f"command failed ({command[0]}): {detail}")
    return completed.stdout.strip()


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def retry_readonly(function: Any, target: str, _error: Any) -> None:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)

    last: OSError | None = None
    for attempt in range(5):
        try:
            shutil.rmtree(path, onerror=retry_readonly)
        except OSError as exc:
            last = exc
        if not path.exists():
            return
        time.sleep(0.25 * (attempt + 1))
    raise ValidationFailure(f"temporary runtime cleanup failed: {type(last).__name__ if last else 'unknown'}")


def _git(snapshot: Path, *args: str, timeout: int = 900) -> str:
    return _run(["git", *args], cwd=snapshot, timeout=timeout)


def _github_json(url: str, attempts: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "image2-task0021-validator/1"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.load(response)
            if not isinstance(value, dict):
                raise ValidationFailure("GitHub returned a non-object")
            return value
        except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
    raise ValidationFailure(f"GitHub boundary did not complete: {type(last).__name__}")


def _clone_fixed(repo: str, sha: str, target: Path) -> Path:
    if target.exists():
        _remove_tree(target)
    _run(["git", "clone", "--quiet", "--filter=blob:none", f"https://github.com/{repo}.git", str(target)], cwd=target.parent, timeout=1200)
    _git(target, "checkout", "--quiet", "--detach", sha, timeout=1200)
    if _git(target, "rev-parse", "HEAD") != sha:
        raise ValidationFailure(f"fixed checkout did not bind {repo}@{sha}")
    return target


def _content_history(snapshot: Path, paths: Sequence[str], as_of: dt.date) -> dict[str, Any]:
    raw = _git(snapshot, "log", "--format=%H%x09%aI", "--", *paths)
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        rows.append({"commit_sha": parts[0], "committed_at": parts[1]})
    if not rows:
        raise ValidationFailure("substantive content history is empty")
    dates = sorted({row["committed_at"][:10] for row in rows})
    lower_bound = as_of - dt.timedelta(days=365)
    recent_dates = [value for value in dates if lower_bound <= dt.date.fromisoformat(value) <= as_of]
    return {
        "latest_substantive_update": max(dates),
        "first_substantive_update": min(dates),
        "substantive_update_dates_365": len(recent_dates),
        "substantive_dates_365": recent_dates,
        "substantive_dates": dates,
        "evidence_commits": [row["commit_sha"] for row in rows[:20]],
    }


def _repository_tree(snapshot: Path) -> dict[str, Any]:
    manifest = _git(snapshot, "ls-tree", "-r", "--full-tree", "HEAD")
    rows = manifest.splitlines() if manifest else []
    return {
        "git_tree_sha": _git(snapshot, "rev-parse", "HEAD^{tree}"),
        "tree_entry_count": len(rows),
        "tree_manifest_sha256": _sha256_bytes((manifest + "\n").encode("utf-8")),
    }


def _asset_fact(snapshot: Path, path: str) -> dict[str, Any]:
    try:
        fact = read_asset(snapshot, path)
    except AssetError as exc:
        raise ValidationFailure(f"asset validation failed for {path}: {exc.error_code}") from exc
    return {
        "locator": fact.source_path,
        "authority": "fixed_local",
        "content_sha256": fact.content_sha256,
        "byte_size": fact.byte_size,
        "media_type": fact.media_type,
    }


def _repository_file_facts(snapshot: Path, paths: Sequence[str]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    root = snapshot.resolve()
    for raw in paths:
        relative = _safe_rel(raw, "repository evidence path")
        path = snapshot / relative
        resolved = path.resolve()
        if path.is_symlink() or not path.is_file() or (resolved != root and root not in resolved.parents):
            raise ValidationFailure(f"repository evidence file is unavailable or unsafe: {relative}")
        content = path.read_bytes()
        if not content:
            raise ValidationFailure(f"repository evidence file is empty: {relative}")
        facts.append({"path": relative, "byte_size": len(content), "sha256": _sha256_bytes(content)})
    return sorted(facts, key=lambda value: value["path"])


def _base_case(
    *,
    case_id: str,
    source_record_id: str,
    category: str,
    prompt: str,
    source_url: object,
    source_path: str,
    input_assets: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    pairing_evidence: str,
) -> dict[str, Any]:
    normalized = _normalize_prompt(prompt)
    if not normalized:
        raise ValidationFailure(f"{case_id} has an empty prompt")
    return {
        "case_id": case_id,
        "source_record_id": source_record_id,
        "category": category or "uncategorized",
        "source_path": source_path,
        "prompt_sha256": _sha256_bytes(normalized.encode("utf-8")),
        "prompt_length": len(prompt),
        "source_url_key": _normalize_source_url(source_url),
        "input_assets": input_assets,
        "outputs": outputs,
        "pairing_evidence": pairing_evidence,
        "risk_flags": _risk_flags(prompt),
        "strong_pairing": True,
    }


def _parse_ecom(snapshot: Path) -> dict[str, Any]:
    payload = _load(snapshot / "data" / "prompts.json")
    records = payload.get("prompts")
    if payload.get("schemaVersion") != 2 or not isinstance(records, list):
        raise ValidationFailure("ecomimagelab data/prompts.json is not schema v2")
    per_files = sorted((snapshot / "data" / "prompts").glob("*.json"))
    if len(per_files) != len(records):
        raise ValidationFailure("ecomimagelab aggregate/per-record coverage diverges")
    by_id = {str(item.get("id")): item for item in records if isinstance(item, dict)}
    if len(by_id) != len(records):
        raise ValidationFailure("ecomimagelab record IDs are duplicated")
    for path in per_files:
        item = _load(path)
        expected = by_id.get(str(item.get("id")))
        if expected != item:
            raise ValidationFailure(f"ecomimagelab aggregate record differs from {path.name}")
        expected_name = f"{item['id']}-{item['slug']}.json"
        if path.name != expected_name:
            raise ValidationFailure(f"ecomimagelab record filename is unstable: {path.name}")

    cases: list[dict[str, Any]] = []
    referenced: set[str] = set()
    for item in records:
        variants = item.get("variants")
        if item.get("model") != "gpt-image-2" or not isinstance(variants, list) or not variants:
            raise ValidationFailure(f"ecomimagelab record is not a GPT Image 2 variant set: {item.get('id')}")
        record_path = f"data/prompts/{item['id']}-{item['slug']}.json"
        variant_ids: set[str] = set()
        for variant in variants:
            variant_id = str(variant.get("id"))
            if not variant_id or variant_id in variant_ids:
                raise ValidationFailure(f"ecomimagelab variant ID is invalid: {item['id']}")
            variant_ids.add(variant_id)
            sample = variant.get("sample")
            if not isinstance(sample, Mapping):
                raise ValidationFailure(f"ecomimagelab sample is missing: {item['id']}:{variant_id}")
            output_path = _safe_rel(sample.get("after"), f"{item['id']}:{variant_id}.sample.after")
            output = _asset_fact(snapshot, output_path)
            referenced.add(output_path)
            before = sample.get("before")
            input_assets: list[dict[str, Any]] = []
            if before is not None:
                before_path = _safe_rel(before, f"{item['id']}:{variant_id}.sample.before")
                input_assets.append(_asset_fact(snapshot, before_path))
                referenced.add(before_path)
            cases.append(
                _base_case(
                    case_id=f"{item['id']}:{variant_id}",
                    source_record_id=str(item["id"]),
                    category=str(item.get("category") or "uncategorized"),
                    prompt=str(variant.get("prompt") or ""),
                    source_url=(item.get("source") or {}).get("url") if isinstance(item.get("source"), Mapping) else None,
                    source_path=record_path,
                    input_assets=input_assets,
                    outputs=[output],
                    pairing_evidence="data/prompts.json variant.sample.after explicit relation",
                )
            )
    raster = sorted(
        path.relative_to(snapshot).as_posix()
        for path in (snapshot / "assets").rglob("*")
        if path.is_file() and path.suffix.casefold() in RASTER_SUFFIXES
    )
    known_auxiliary = {"assets/cover.png"}
    orphans = sorted(set(raster) - referenced - known_auxiliary)
    asset_terminal_results = [_asset_fact(snapshot, path) for path in raster]
    return {
        "source_record_count": len(records),
        "cases": sorted(cases, key=lambda item: item["case_id"]),
        "repository_raster_count": len(raster),
        "orphan_assets": orphans,
        "auxiliary_assets": sorted(known_auxiliary & set(raster)),
        "asset_terminal_results": asset_terminal_results,
        "history_paths": ["data/prompts.json", "data/prompts", "assets/prompts"],
        "license": "CC-BY-4.0",
        "rights_evidence": _repository_file_facts(snapshot, ["LICENSE", "README.md", "data/prompts.json"]),
        "provenance_summary": "repository-authored source claims with per-variant CC-BY-4.0 provenance; project review fields remain non-authoritative",
    }


def _parse_hiapi(snapshot: Path) -> dict[str, Any]:
    payload = _load(snapshot / "data" / "prompts.json")
    items = payload.get("items")
    if payload.get("model") != "gpt-image-2" or not isinstance(items, list):
        raise ValidationFailure("HiAPIAI data/prompts.json is malformed")
    cases: list[dict[str, Any]] = []
    referenced: set[str] = set()
    item_ids: set[str] = set()
    raster = sorted(
        path.relative_to(snapshot).as_posix()
        for path in (snapshot / "images").rglob("*")
        if path.is_file() and path.suffix.casefold() in RASTER_SUFFIXES
    )
    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in item_ids:
            raise ValidationFailure("HiAPIAI item IDs are missing or duplicated")
        item_ids.add(item_id)
        variants = item.get("prompt_variants")
        rows = variants if isinstance(variants, list) and variants else [None]
        for index, variant in enumerate(rows):
            if variant is None:
                prompt = str(item.get("prompt") or "")
                image = item.get("image")
                case_id = item_id
                pairing_evidence = "data/prompts.json item.image plus same-directory case contract"
            else:
                prompt = str(variant.get("prompt") or "")
                image = variant.get("image")
                case_id = f"{item_id}:variant-{index + 1}"
                pairing_evidence = f"data/prompts.json prompt_variants[{index}].image explicit relation"
            path = _safe_rel(image, f"{case_id}.image")
            output_paths = [path]
            if variant is None:
                parent = PurePosixPath(path).parent
                primary_name = PurePosixPath(path).name
                if re.fullmatch(r"output\.(?:png|jpe?g|webp|gif)", primary_name, re.I):
                    output_paths = sorted(
                        value
                        for value in raster
                        if PurePosixPath(value).parent == parent
                        and re.fullmatch(r"output(?:_[1-9][0-9]*)?\.(?:png|jpe?g|webp|gif)", PurePosixPath(value).name, re.I)
                    )
                if path not in output_paths:
                    raise ValidationFailure(f"HiAPIAI manifest image is missing from its case directory: {case_id}")
            outputs = [_asset_fact(snapshot, value) for value in output_paths]
            referenced.update(output_paths)
            cases.append(
                _base_case(
                    case_id=case_id,
                    source_record_id=item_id,
                    category=str(item.get("category") or "uncategorized"),
                    prompt=prompt,
                    source_url=item.get("source_url"),
                    source_path="data/prompts.json",
                    input_assets=[],
                    outputs=outputs,
                    pairing_evidence=pairing_evidence,
                )
            )
    orphans = sorted(set(raster) - referenced)
    auxiliary = sorted(
        path.relative_to(snapshot).as_posix()
        for path in (snapshot / "images").glob("cover*.svg")
        if path.is_file()
    )
    return {
        "source_record_count": len(items),
        "cases": sorted(cases, key=lambda item: item["case_id"]),
        "repository_raster_count": len(raster),
        "orphan_assets": orphans,
        "auxiliary_assets": auxiliary,
        "asset_terminal_results": [_asset_fact(snapshot, path) for path in raster],
        "history_paths": ["data/prompts.json", "images"],
        "license": "CC-BY-4.0-layered",
        "rights_evidence": _repository_file_facts(snapshot, ["LICENSE", "NOTICE.md", "data/prompts.json"]),
        "provenance_summary": "attribution-preserving index; HiAPI CC-BY grant excludes third-party prompts, images, names, brands, and platform rights",
    }


def _parse_imagine(snapshot: Path) -> dict[str, Any]:
    raw = json.loads((snapshot / "data" / "prompts.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValidationFailure("imagineVid data/prompts.json must be a list")
    cases: list[dict[str, Any]] = []
    ids: set[int] = set()
    urls: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping) or item.get("model") != "gpt-image-2":
            raise ValidationFailure("imagineVid contains a malformed/non-GPT Image 2 record")
        identifier = item.get("id")
        if not isinstance(identifier, int) or identifier <= 0 or identifier in ids:
            raise ValidationFailure("imagineVid prompt IDs are invalid or duplicated")
        ids.add(identifier)
        media = item.get("sourceMedia")
        if not isinstance(media, list) or not media:
            raise ValidationFailure(f"imagineVid sourceMedia is missing: {identifier}")
        outputs: list[dict[str, Any]] = []
        for url in media:
            if not isinstance(url, str) or not url.startswith("https://pbs.twimg.com/") or url in urls:
                raise ValidationFailure(f"imagineVid remote media URL is invalid/duplicated: {identifier}")
            urls.add(url)
            outputs.append({"locator": url, "authority": "remote_observation", "content_sha256": None, "byte_size": None, "media_type": None})
        source_url = item.get("sourceLink")
        source_meta = item.get("sourceMeta")
        author = item.get("author")
        if (
            _normalize_source_url(source_url) is None
            or not isinstance(source_meta, Mapping)
            or source_meta.get("source") != "twitterapi.io"
            or source_meta.get("model_evidence") != "gpt-image-2"
            or not isinstance(author, Mapping)
            or not author.get("name")
        ):
            raise ValidationFailure(f"imagineVid provenance is incomplete: {identifier}")
        cases.append(
            _base_case(
                case_id=f"imagine-{identifier:03d}",
                source_record_id=str(identifier),
                category=str(((item.get("imageCategories") or {}).get("workflows") or [{}])[0].get("slug") or "uncategorized"),
                prompt=str(item.get("content") or ""),
                source_url=source_url,
                source_path="data/prompts.json",
                input_assets=[],
                outputs=outputs,
                pairing_evidence="data/prompts.json sourceMedia explicit ordered relation; bytes remain observational",
            )
        )
    raster = sorted(
        path.relative_to(snapshot).as_posix()
        for path in (snapshot / "public").rglob("*")
        if path.is_file() and path.suffix.casefold() in RASTER_SUFFIXES
    )
    return {
        "source_record_count": len(raw),
        "cases": sorted(cases, key=lambda item: item["case_id"]),
        "repository_raster_count": len(raster),
        "orphan_assets": [],
        "auxiliary_assets": raster,
        "asset_terminal_results": [_asset_fact(snapshot, path) for path in raster],
        "history_paths": ["data/prompts.json"],
        "license": "CC-BY-4.0-with-third-party-rights-limitations",
        "rights_evidence": _repository_file_facts(snapshot, ["LICENSE", "README.md", "data/prompts.json"]),
        "provenance_summary": "source-backed X posts with author/model evidence; Twitter-hosted media remain volatile third-party observations",
    }


def _parse_candidate(source_id: str, snapshot: Path) -> dict[str, Any]:
    if source_id == "ecomimagelab-ecommerce-gpt-image-prompts":
        return _parse_ecom(snapshot)
    if source_id == "hiapiai-awesome-gpt-image-2-prompts":
        return _parse_hiapi(snapshot)
    if source_id == "imaginevid-awesome-gpt-image-2-prompts-and-skills":
        return _parse_imagine(snapshot)
    raise ValidationFailure(f"unsupported candidate: {source_id}")


def _observe_remote_one(case_id: str, url: str, observed_at: str) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 image2-task0021/1"})
            with urllib.request.urlopen(request, timeout=45) as response:
                content = response.read(25 * 1024 * 1024 + 1)
                if len(content) > 25 * 1024 * 1024:
                    raise ValidationFailure("remote media exceeds the 25 MiB observation limit")
                return {
                    "case_id": case_id,
                    "url": url,
                    "observed_at": observed_at,
                    "status": int(getattr(response, "status", 200)),
                    "media_type": str(response.headers.get_content_type()),
                    "byte_size": len(content),
                    "observed_bytes_sha256": _sha256_bytes(content),
                    "error": None,
                }
        except (OSError, urllib.error.HTTPError, urllib.error.URLError, ValidationFailure) as exc:
            last = exc
            if attempt == 0:
                time.sleep(1)
    return {
        "case_id": case_id,
        "url": url,
        "observed_at": observed_at,
        "status": None,
        "media_type": None,
        "byte_size": None,
        "observed_bytes_sha256": None,
        "error": type(last).__name__,
    }


def _observe_remote(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    observed_at = _utc_now()
    jobs = [(str(case["case_id"]), str(output["locator"])) for case in cases for output in case["outputs"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        rows = list(executor.map(lambda item: _observe_remote_one(item[0], item[1], observed_at), jobs))
    return sorted(rows, key=lambda item: (item["case_id"], item["url"]))


def _remote_observation_ok(item: Mapping[str, Any]) -> bool:
    return (
        item.get("status") == 200
        and item.get("media_type") in {"image/jpeg", "image/png", "image/webp", "image/gif"}
        and isinstance(item.get("byte_size"), int)
        and int(item["byte_size"]) > 0
        and isinstance(item.get("observed_bytes_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", str(item["observed_bytes_sha256"])) is not None
    )


def _fixed_core_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(candidate))
    evidence = value.get("evidence")
    if isinstance(evidence, dict):
        evidence.pop("remote_observations", None)
        evidence.pop("remote_observations_sha256", None)
    metrics = value.get("metrics")
    if isinstance(metrics, dict) and int(metrics.get("remote_output_reference_count") or 0) > 0:
        metrics.pop("broken_asset_count", None)
        metrics.pop("broken_asset_rate", None)
    identity = value.get("identity")
    if isinstance(identity, dict):
        identity.pop("pushed_at", None)
    value.pop("fixed_core_digest", None)
    return value


def _fixed_core_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(payload))
    value.pop("generated_at", None)
    value.pop("canonical_digest", None)
    value["candidates"] = [_fixed_core_candidate(item) for item in value.get("candidates", [])]
    return value


def _current_index(*, rebuild: bool, data_root: Path = CURRENT_DATA_ROOT, cache_path: Path = CURRENT_CACHE) -> dict[str, Any]:
    registry = REPO_ROOT / "config" / "sources-v1.yaml"
    audit = REPO_ROOT / "reports" / "source-audit-v1.json"
    configs = tuple(load_source_config(registry, source_id) for source_id in SOURCE_IDS)
    cache_key = _cache_key(registry, audit, configs)
    if rebuild:
        if not data_root.is_dir():
            raise ValidationFailure(f"prewarmed six-source mirror root is unavailable: {data_root}")
        payload = _build_index(repo=REPO_ROOT, registry_path=registry, audit_path=audit, data_root=data_root, configs=configs, cache_key=cache_key)
    else:
        payload = _load(cache_path)
    if payload.get("cache_key") != cache_key or payload.get("case_count") != 1513 or payload.get("output_count") != 1930:
        raise ValidationFailure("current six-source production index does not match the validated 1513/1930 baseline")
    cases = payload.get("cases")
    assets = payload.get("assets")
    if not isinstance(cases, list) or not isinstance(assets, dict):
        raise ValidationFailure("current six-source production index is malformed")
    return payload


def _current_exact_sets(payload: Mapping[str, Any]) -> dict[str, set[str]]:
    prompts = {
        _sha256_bytes(_normalize_prompt(str(item["prompt"])).encode("utf-8"))
        for item in payload["cases"]
        if _normalize_prompt(str(item.get("prompt") or ""))
    }
    urls = {value for item in payload["cases"] if (value := _normalize_source_url(item.get("source_url"))) is not None}
    images = {
        str(output["content_sha256"])
        for item in payload["cases"]
        for output in item.get("outputs", [])
        if isinstance(output, Mapping) and isinstance(output.get("content_sha256"), str)
    }
    return {"prompt": prompts, "source_url": urls, "image": images}


def _candidate_metrics(parsed: Mapping[str, Any], remote_observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cases = parsed["cases"]
    valid_cases = [item for item in cases if item["strong_pairing"] and item["outputs"]]
    unique_cases = _unique_valid_cases(valid_cases)
    duplicate_count = len(valid_cases) - len(unique_cases)
    outputs = [output for item in cases for output in item["outputs"]]
    local = [output for output in outputs if output["authority"] == "fixed_local"]
    remote = [output for output in outputs if output["authority"] == "remote_observation"]
    broken = sum(1 for item in remote_observations if not _remote_observation_ok(item)) if remote else 0
    valid = len(valid_cases)
    unique = len(unique_cases)
    return {
        "source_record_count": int(parsed["source_record_count"]),
        "observed_case_count": len(cases),
        "exact_prompt_count": sum(1 for item in cases if item["prompt_sha256"]),
        "output_reference_count": len(outputs),
        "local_output_reference_count": len(local),
        "remote_output_reference_count": len(remote),
        "repository_raster_count": int(parsed["repository_raster_count"]),
        "orphan_raster_count": len(parsed["orphan_assets"]),
        "broken_asset_count": broken,
        "valid_case_count": valid,
        "unique_valid_case_count": unique,
        "pair_rate": round(valid / len(cases), 8) if cases else 0.0,
        "broken_asset_rate": round(broken / len(outputs), 8) if outputs else 1.0,
        "duplicate_count": duplicate_count,
        "duplicate_rate": round(duplicate_count / valid, 8) if valid else 1.0,
        "within_source_dedupe_version": WITHIN_SOURCE_DEDUPE_VERSION,
    }


def _contribution(cases: Sequence[Mapping[str, Any]], current: Mapping[str, set[str]]) -> dict[str, Any]:
    unique_cases = _unique_valid_cases(cases)
    source_hits = sorted(str(item["case_id"]) for item in unique_cases if item.get("source_url_key") in current["source_url"])
    prompt_hits = sorted(str(item["case_id"]) for item in unique_cases if item.get("prompt_sha256") in current["prompt"])
    image_hits = sorted(
        str(item["case_id"])
        for item in unique_cases
        if any(output.get("authority") == "fixed_local" and output.get("content_sha256") in current["image"] for output in item["outputs"])
    )
    overlaps = set(source_hits) | set(prompt_hits) | set(image_hits)
    unique_ids = sorted(str(item["case_id"]) for item in unique_cases if str(item["case_id"]) not in overlaps)
    return {
        "normalization_version": NORMALIZATION_VERSION,
        "current_source_url_overlap_count": len(source_hits),
        "current_source_url_overlap_case_ids": source_hits,
        "current_prompt_overlap_count": len(prompt_hits),
        "current_prompt_overlap_case_ids": prompt_hits,
        "current_image_overlap_count": len(image_hits),
        "current_image_overlap_case_ids": image_hits,
        "unique_exact_contribution_count": len(unique_ids),
        "unique_exact_contribution_case_ids_sha256": _hash_lines(unique_ids),
    }


def _lint_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for item in cases:
        for flag in item.get("risk_flags", []):
            groups[str(flag)].append(str(item["case_id"]))
    return {key: {"count": len(values), "case_ids": sorted(values)} for key, values in sorted(groups.items())}


def _quality_block(
    cases: Sequence[Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
    contribution: Mapping[str, Any],
) -> dict[str, Any]:
    unique_cases = _unique_valid_cases(cases)
    overlap_groups = {
        "source_url": contribution["current_source_url_overlap_case_ids"],
        "prompt": contribution["current_prompt_overlap_case_ids"],
        "image": contribution["current_image_overlap_case_ids"],
    }
    sample_ids = _select_quality_sample(unique_cases, _expected_sample_size(len(unique_cases)), overlap_groups)
    sample_reviews: list[dict[str, Any]] = []
    by_id = {str(item["case_id"]): item for item in cases}
    for case_id in sample_ids:
        review = reviews.get(case_id)
        if not isinstance(review, Mapping):
            raise ValidationFailure(f"quality review is missing for {case_id}")
        result = str(review.get("result"))
        if result not in {"pass", "fail"}:
            raise ValidationFailure(f"quality review result is invalid for {case_id}")
        sample_reviews.append(
            {
                "case_id": case_id,
                "result": result,
                "prompt_complete": bool(review.get("prompt_complete")),
                "image_readable": bool(review.get("image_readable")),
                "semantic_match": bool(review.get("semantic_match")),
                "visual_quality": _normalize_visual_quality(review.get("visual_quality")),
                "notes": str(review.get("notes") or ""),
                "risk_flags": list(by_id[case_id].get("risk_flags", [])),
            }
        )
    passed = all(
        item["result"] == "pass"
        and item["prompt_complete"]
        and item["image_readable"]
        and item["semantic_match"]
        and item["visual_quality"] in {"high", "acceptable"}
        for item in sample_reviews
    )
    sampled_cases = [by_id[case_id] for case_id in sample_ids]
    source_categories = sorted({str(item["category"]) for item in unique_cases})
    sampled_categories = sorted({str(item["category"]) for item in sampled_cases})
    source_risk_flags = sorted({str(flag) for item in unique_cases for flag in item.get("risk_flags", [])})
    sampled_risk_flags = sorted({str(flag) for item in sampled_cases for flag in item.get("risk_flags", [])})
    source_multi_output_count = sum(1 for item in unique_cases if len(item.get("outputs", [])) > 1)
    sampled_multi_output_count = sum(1 for item in sampled_cases if len(item.get("outputs", [])) > 1)
    overlap_sample_counts = {
        name: len(set(values) & set(sample_ids)) for name, values in sorted(overlap_groups.items())
    }
    if source_categories != sampled_categories:
        raise ValidationFailure("quality sample does not cover every candidate category")
    if source_risk_flags != sampled_risk_flags:
        raise ValidationFailure("quality sample does not cover every machine-risk cluster")
    if source_multi_output_count and not sampled_multi_output_count:
        raise ValidationFailure("quality sample does not cover multi-output cases")
    if any(values and overlap_sample_counts[name] == 0 for name, values in overlap_groups.items()):
        raise ValidationFailure("quality sample does not cover every nonempty exact-overlap cluster")
    return {
        "result": "pass" if passed else "fail",
        "sample_size": len(sample_ids),
        "selection_method": "all-category/all-risk/exact-overlap/multi-output/length boundary coverage followed by stable SHA-256 fill",
        "sample_ids": sample_ids,
        "sample_ids_sha256": _hash_lines(sample_ids),
        "lint_version": LINT_VERSION,
        "lint_flags": _lint_summary(cases),
        "coverage": {
            "source_categories": source_categories,
            "sampled_categories": sampled_categories,
            "source_risk_flags": source_risk_flags,
            "sampled_risk_flags": sampled_risk_flags,
            "source_multi_output_case_count": source_multi_output_count,
            "sampled_multi_output_case_count": sampled_multi_output_count,
            "exact_overlap_sample_counts": overlap_sample_counts,
        },
        "reviews": sample_reviews,
        "finding": "deterministic sample passed Prompt/image semantic quality checks" if passed else "one or more deterministic sample items failed quality review",
    }


def _load_quality_reviews(path: Path) -> dict[str, dict[str, Mapping[str, Any]]]:
    payload = _load(path)
    result: dict[str, dict[str, Mapping[str, Any]]] = {}
    for source_id, value in payload.items():
        if not isinstance(value, Mapping):
            raise ValidationFailure(f"quality review source block is malformed: {source_id}")
        result[source_id] = {str(key): item for key, item in value.items() if isinstance(item, Mapping)}
    return result


def _normalize_visual_quality(value: object) -> str:
    normalized = str(value or "unknown").strip().casefold()
    aliases = {"excellent": "high", "good": "acceptable", "medium": "acceptable"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"high", "acceptable", "low", "unknown"} else "unknown"


def _build_candidate(
    *,
    source_id: str,
    snapshot: Path,
    current_sets: Mapping[str, set[str]],
    quality_reviews: Mapping[str, Mapping[str, Any]],
    generated_at: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    spec = EXPECTED_CANDIDATES[source_id]
    sha = _git(snapshot, "rev-parse", "HEAD")
    tree = _repository_tree(snapshot)
    parsed = _parse_candidate(source_id, snapshot)
    remote_observations = _observe_remote(parsed["cases"]) if source_id.startswith("imaginevid-") else []
    metrics = _candidate_metrics(parsed, remote_observations)
    generated = _parse_utc(generated_at, "generated_at")
    history = _content_history(snapshot, parsed["history_paths"], generated.date())
    latest = dt.date.fromisoformat(history["latest_substantive_update"])
    first = dt.date.fromisoformat(history["first_substantive_update"])
    age_days = (generated.date() - latest).days
    history["evaluated_on"] = generated.date().isoformat()
    history["latest_update_age_days"] = age_days
    history["maturity_span_days"] = (latest - first).days
    history["eligible"] = (
        age_days <= THRESHOLDS["latest_substantive_update_days"]
        and history["substantive_update_dates_365"] >= THRESHOLDS["minimum_substantive_update_dates_365"]
    )
    contribution = _contribution(parsed["cases"], current_sets)
    quality = _quality_block(parsed["cases"], quality_reviews, contribution)
    local_authority = metrics["remote_output_reference_count"] == 0
    ready = (
        not bool(metadata["archived"])
        and local_authority
        and metrics["unique_valid_case_count"] >= THRESHOLDS["minimum_unique_valid_cases"]
        and metrics["pair_rate"] >= THRESHOLDS["minimum_pair_rate"]
        and metrics["broken_asset_rate"] <= THRESHOLDS["maximum_broken_asset_rate"]
        and metrics["duplicate_rate"] <= THRESHOLDS["maximum_duplicate_rate"]
        and history["eligible"]
        and quality["result"] == "pass"
        and contribution["unique_exact_contribution_count"] > 0
    )
    status = "adapter_ready" if ready else "probation"
    failed_quality_ids = sorted(
        review["case_id"] for review in quality["reviews"] if review["result"] == "fail"
    )
    failure_reasons: list[str] = []
    if bool(metadata["archived"]):
        failure_reasons.append("repository is archived")
    if not local_authority:
        failure_reasons.append("remote media has no immutable snapshot authority")
    if metrics["unique_valid_case_count"] < THRESHOLDS["minimum_unique_valid_cases"]:
        failure_reasons.append("unique valid case count is below 50")
    if metrics["pair_rate"] < THRESHOLDS["minimum_pair_rate"]:
        failure_reasons.append("strong-pair rate is below 0.90")
    if metrics["broken_asset_rate"] > THRESHOLDS["maximum_broken_asset_rate"]:
        failure_reasons.append("broken-asset rate exceeds 0.05")
    if metrics["duplicate_rate"] > THRESHOLDS["maximum_duplicate_rate"]:
        failure_reasons.append("within-source duplicate rate exceeds 0.20")
    if not history["eligible"]:
        failure_reasons.append("maintenance recency/maturity gate failed")
    if quality["result"] != "pass":
        failure_reasons.append(f"quality sample failed: {', '.join(failed_quality_ids)}")
    if contribution["unique_exact_contribution_count"] <= 0:
        failure_reasons.append("no independent exact contribution remains")
    reason = (
        "fixed local assets, complete strong pairing, maintenance, quality, rights, and independent-contribution gates passed"
        if ready
        else "; ".join(failure_reasons)
    )
    candidate = {
        "source_id": source_id,
        "candidate_key": spec["repo"].casefold(),
        "identity": {
            "repository_id": int(metadata["id"]),
            "url": f"https://github.com/{spec['repo']}",
            "default_branch": str(metadata["default_branch"]),
            "fixed_commit_sha": sha,
            **tree,
            "archived": bool(metadata["archived"]),
            "pushed_at": str(metadata["pushed_at"]),
        },
        "lineage": {
            "family_id": source_id,
            "family_role": spec["family_role"],
            "derived_from": [],
        },
        "status": status,
        "status_reason": reason,
        "recommended_adapter_strategy": spec["strategy"] if ready else None,
        "structure": {
            "record_source_path": spec["source_path"],
            "strategy": spec["strategy"],
            "local_asset_authority": local_authority,
            "remote_asset_authority": False,
            "source_record_count": parsed["source_record_count"],
        },
        "metrics": metrics,
        "maintenance": history,
        "rights": {
            "repository_license": parsed["license"],
            "prompt_policy": "review_required",
            "asset_policy": "review_required",
            "public_eligibility": "review_required",
            "auto_publish": False,
            "evidence_files": parsed["rights_evidence"],
            "provenance_summary": parsed["provenance_summary"],
        },
        "quality": quality,
        "contribution": contribution,
        "evidence": {
            "case_ledger": parsed["cases"],
            "case_ledger_sha256": _digest(parsed["cases"]),
            "orphan_assets": parsed["orphan_assets"],
            "orphan_assets_sha256": _hash_lines(parsed["orphan_assets"]),
            "auxiliary_assets": parsed["auxiliary_assets"],
            "asset_terminal_results": parsed["asset_terminal_results"],
            "asset_terminal_results_sha256": _digest(parsed["asset_terminal_results"]),
            "remote_observations": remote_observations,
            "remote_observations_sha256": _digest(remote_observations),
        },
    }
    candidate["fixed_core_digest"] = _digest(_fixed_core_candidate(candidate))
    return candidate


def build_report(
    *,
    snapshot_root: Path,
    current_index_path: Path,
    quality_review_path: Path,
) -> dict[str, Any]:
    generated_at = _utc_now()
    current = _current_index(rebuild=False, cache_path=current_index_path)
    current_sets = _current_exact_sets(current)
    quality = _load_quality_reviews(quality_review_path)
    candidates: list[dict[str, Any]] = []
    for source_id, spec in EXPECTED_CANDIDATES.items():
        snapshot = snapshot_root / {
            "ecomimagelab-ecommerce-gpt-image-prompts": "ecomimagelab",
            "hiapiai-awesome-gpt-image-2-prompts": "hiapiai",
            "imaginevid-awesome-gpt-image-2-prompts-and-skills": "imaginevid",
        }[source_id]
        metadata = _github_json(f"https://api.github.com/repos/{spec['repo']}")
        if (
            int(metadata.get("id", -1)) != spec["repo_id"]
            or metadata.get("default_branch") != spec["default_branch"]
        ):
            raise ValidationFailure(f"repository identity changed: {source_id}")
        branch_head = _github_json(
            f"https://api.github.com/repos/{spec['repo']}/commits/{spec['default_branch']}"
        )
        if branch_head.get("sha") != _git(snapshot, "rev-parse", "HEAD"):
            raise ValidationFailure(f"candidate snapshot is no longer the current default-branch head: {source_id}")
        candidates.append(
            _build_candidate(
                source_id=source_id,
                snapshot=snapshot,
                current_sets=current_sets,
                quality_reviews=quality.get(source_id, {}),
                generated_at=generated_at,
                metadata=metadata,
            )
        )
    candidates.sort(key=lambda item: item["source_id"])
    ready = sorted(
        (item for item in candidates if item["status"] == "adapter_ready"),
        key=lambda item: (-int(item["contribution"]["unique_exact_contribution_count"]), item["source_id"]),
    )
    batch = [
        {
            "rank": index + 1,
            "source_id": item["source_id"],
            "fixed_commit_sha": item["identity"]["fixed_commit_sha"],
            "unique_valid_case_count": item["metrics"]["unique_valid_case_count"],
            "unique_exact_contribution_count": item["contribution"]["unique_exact_contribution_count"],
            "recommended_adapter_strategy": item["recommended_adapter_strategy"],
            "case_scope": {
                "source_record_count": item["metrics"]["source_record_count"],
                "observed_case_count": item["metrics"]["observed_case_count"],
                "output_reference_count": item["metrics"]["output_reference_count"],
            },
            "known_exclusions": {
                "orphan_assets": item["evidence"]["orphan_assets"],
                "quality_failed_case_ids": [
                    review["case_id"] for review in item["quality"]["reviews"] if review["result"] == "fail"
                ],
            },
            "public_eligibility": "review_required",
        }
        for index, item in enumerate(ready)
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "authority": {
            "source_audit_sha256": _sha256_file(REPO_ROOT / "reports" / "source-audit-v1.json"),
            "source_registry_sha256": _sha256_file(REPO_ROOT / "config" / "sources-v1.yaml"),
            "phase2_discovery_v1_sha256": _sha256_file(REPO_ROOT / "reports" / "phase2" / "source-discovery-v1.json"),
            "inventory_contract_sha256": _sha256_file(REPO_ROOT / "docs" / "inventory" / "internal-inventory-v1.md"),
            "phase2_activation_v1_sha256": _sha256_file(REPO_ROOT / "docs" / "phase2" / "phase2-adapter-activation-v1.md"),
            "active_source_count": 6,
            "current_case_count": 1513,
            "current_output_count": 1930,
            "current_source_file_count": 2260,
            "current_deduplicated_asset_object_count": 1885,
            "current_public_cases": 0,
            "current_index_cache_key": current["cache_key"],
            "current_index_core_sha256": _digest({"cases": current["cases"], "assets": current["assets"]}),
        },
        "thresholds": THRESHOLDS,
        "candidates": candidates,
        "adapter_ready_batch": batch,
        "summary": {
            "candidate_count": len(candidates),
            "adapter_ready_count": len(batch),
            "adapter_ready_unique_cases": sum(int(item["unique_valid_case_count"]) for item in batch),
            "adapter_ready_unique_exact_contribution": sum(int(item["unique_exact_contribution_count"]) for item in batch),
            "current_case_count": 1513,
            "current_output_count": 1930,
            "current_source_file_count": 2260,
            "current_deduplicated_asset_object_count": 1885,
            "real_public_cases": 0,
            "protected_scope_modified": False,
        },
    }
    payload["canonical_digest"] = _digest(_fixed_core_payload(payload))
    return payload


def _validate_metrics(source_id: str, metrics: Mapping[str, Any]) -> None:
    if metrics["within_source_dedupe_version"] != WITHIN_SOURCE_DEDUPE_VERSION:
        raise ValidationFailure(f"{source_id} within-source dedupe version changed")
    observed = int(metrics["observed_case_count"])
    prompts = int(metrics["exact_prompt_count"])
    outputs = int(metrics["output_reference_count"])
    local = int(metrics["local_output_reference_count"])
    remote = int(metrics["remote_output_reference_count"])
    broken = int(metrics["broken_asset_count"])
    valid = int(metrics["valid_case_count"])
    unique = int(metrics["unique_valid_case_count"])
    duplicates = int(metrics["duplicate_count"])
    if min(observed, prompts, outputs, local, remote, broken, valid, unique, duplicates) < 0:
        raise ValidationFailure(f"{source_id} metrics contain negative values")
    if outputs != local + remote or not (unique <= valid <= observed and prompts == observed):
        raise ValidationFailure(f"{source_id} metrics do not close")
    if duplicates != valid - unique or broken > outputs:
        raise ValidationFailure(f"{source_id} duplicate/broken metrics do not close")
    expected_pair = valid / observed if observed else 0.0
    expected_broken = broken / outputs if outputs else 1.0
    expected_duplicate = duplicates / valid if valid else 1.0
    for actual, expected, label in (
        (metrics["pair_rate"], expected_pair, "pair_rate"),
        (metrics["broken_asset_rate"], expected_broken, "broken_asset_rate"),
        (metrics["duplicate_rate"], expected_duplicate, "duplicate_rate"),
    ):
        if abs(float(actual) - expected) > 0.000001:
            raise ValidationFailure(f"{source_id}.{label} is not arithmetically reproducible")


def _semantic_validate(payload: dict[str, Any], repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    if payload["authority"]["source_audit_sha256"] != _sha256_file(repo_root / "reports" / "source-audit-v1.json"):
        raise ValidationFailure("source audit authority hash changed")
    if payload["authority"]["source_registry_sha256"] != _sha256_file(repo_root / "config" / "sources-v1.yaml"):
        raise ValidationFailure("source registry authority hash changed")
    if payload["authority"]["phase2_discovery_v1_sha256"] != _sha256_file(repo_root / "reports" / "phase2" / "source-discovery-v1.json"):
        raise ValidationFailure("Phase 2 v1 authority hash changed")
    if payload["authority"]["inventory_contract_sha256"] != _sha256_file(repo_root / "docs" / "inventory" / "internal-inventory-v1.md"):
        raise ValidationFailure("inventory v1 authority hash changed")
    if payload["authority"]["phase2_activation_v1_sha256"] != _sha256_file(repo_root / "docs" / "phase2" / "phase2-adapter-activation-v1.md"):
        raise ValidationFailure("Phase 2 activation v1 authority hash changed")
    authority = payload["authority"]
    if (
        authority["active_source_count"] != 6
        or authority["current_case_count"] != 1513
        or authority["current_output_count"] != 1930
        or authority["current_source_file_count"] != 2260
        or authority["current_deduplicated_asset_object_count"] != 1885
        or authority["current_public_cases"] != 0
    ):
        raise ValidationFailure("current six-source authority does not close at 1513/1930/2260/1885/0-public")
    if payload["thresholds"] != THRESHOLDS:
        raise ValidationFailure("admission thresholds changed")
    candidates = payload["candidates"]
    by_id = {item["source_id"]: item for item in candidates}
    if set(by_id) != set(EXPECTED_CANDIDATES) or len(by_id) != len(candidates):
        raise ValidationFailure("candidate set must contain exactly the three authorized repositories")
    generated_at = _parse_utc(payload["generated_at"], "generated_at")
    for source_id, item in by_id.items():
        spec = EXPECTED_CANDIDATES[source_id]
        identity = item["identity"]
        if (
            identity["repository_id"] != spec["repo_id"]
            or identity["url"] != f"https://github.com/{spec['repo']}"
            or identity["default_branch"] != spec["default_branch"]
        ):
            raise ValidationFailure(f"{source_id} repository identity diverged")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", identity["fixed_commit_sha"])
            or not re.fullmatch(r"[0-9a-f]{40}", identity["git_tree_sha"])
            or not re.fullmatch(r"[0-9a-f]{64}", identity["tree_manifest_sha256"])
            or identity["tree_entry_count"] <= 0
        ):
            raise ValidationFailure(f"{source_id} fixed Commit/tree identity is invalid")
        if item["lineage"] != {"family_id": source_id, "family_role": spec["family_role"], "derived_from": []}:
            raise ValidationFailure(f"{source_id} canonical/derived lineage judgment changed")
        _validate_metrics(source_id, item["metrics"])
        evidence = item["evidence"]
        ledger = evidence["case_ledger"]
        if len(ledger) != item["metrics"]["observed_case_count"] or evidence["case_ledger_sha256"] != _digest(ledger):
            raise ValidationFailure(f"{source_id} full case ledger does not close")
        ids = [row["case_id"] for row in ledger]
        if len(ids) != len(set(ids)) or ids != sorted(ids):
            raise ValidationFailure(f"{source_id} case IDs are duplicated or nondeterministic")
        if evidence["orphan_assets_sha256"] != _hash_lines(evidence["orphan_assets"]):
            raise ValidationFailure(f"{source_id} orphan ledger digest is invalid")
        if item["metrics"]["orphan_raster_count"] != len(evidence["orphan_assets"]):
            raise ValidationFailure(f"{source_id} orphan metric does not match its ledger")
        terminal_results = evidence["asset_terminal_results"]
        if evidence["asset_terminal_results_sha256"] != _digest(terminal_results):
            raise ValidationFailure(f"{source_id} local asset terminal-result digest is invalid")
        terminal_by_path = {row["locator"]: row for row in terminal_results}
        if len(terminal_by_path) != len(terminal_results) or len(terminal_results) != item["metrics"]["repository_raster_count"]:
            raise ValidationFailure(f"{source_id} local raster terminal coverage is incomplete")
        if any(
            row.get("authority") != "fixed_local"
            or not row.get("content_sha256")
            or not row.get("byte_size")
            or not str(row.get("media_type") or "").startswith("image/")
            for row in terminal_results
        ):
            raise ValidationFailure(f"{source_id} local raster terminal result is invalid")
        ledger_outputs = [output for row in ledger for output in row["outputs"]]
        ledger_inputs = [asset for row in ledger for asset in row["input_assets"]]
        ledger_local = [output for output in ledger_outputs if output["authority"] == "fixed_local"]
        ledger_remote = [output for output in ledger_outputs if output["authority"] == "remote_observation"]
        if (
            len(ledger_outputs) != item["metrics"]["output_reference_count"]
            or len(ledger_local) != item["metrics"]["local_output_reference_count"]
            or len(ledger_remote) != item["metrics"]["remote_output_reference_count"]
        ):
            raise ValidationFailure(f"{source_id} output authority counts do not match its ledger")
        if any(output.get("content_sha256") is None for output in ledger_local):
            raise ValidationFailure(f"{source_id} fixed local output lacks a content digest")
        if any(asset.get("authority") != "fixed_local" or asset.get("content_sha256") is None for asset in ledger_inputs):
            raise ValidationFailure(f"{source_id} fixed local input lacks a content digest")
        if any(output.get("content_sha256") is not None for output in ledger_remote):
            raise ValidationFailure(f"{source_id} remote output leaked an authoritative content digest")
        referenced_rasters = {row["locator"] for row in ledger_local + ledger_inputs}
        orphan_rasters = set(evidence["orphan_assets"])
        auxiliary_rasters = set(evidence["auxiliary_assets"]) & set(terminal_by_path)
        if referenced_rasters & orphan_rasters or (referenced_rasters | orphan_rasters | auxiliary_rasters) != set(terminal_by_path):
            raise ValidationFailure(f"{source_id} referenced/orphan/auxiliary raster coverage does not close")
        quality = item["quality"]
        expected_sample = _expected_sample_size(item["metrics"]["unique_valid_case_count"])
        if quality["sample_size"] != expected_sample or len(quality["sample_ids"]) != expected_sample:
            raise ValidationFailure(f"{source_id} quality sample size is invalid")
        if quality["sample_ids_sha256"] != _hash_lines(quality["sample_ids"]):
            raise ValidationFailure(f"{source_id} quality sample digest is invalid")
        unique_ledger = _unique_valid_cases(ledger)
        contribution = item["contribution"]
        overlap_groups = {
            "source_url": contribution["current_source_url_overlap_case_ids"],
            "prompt": contribution["current_prompt_overlap_case_ids"],
            "image": contribution["current_image_overlap_case_ids"],
        }
        if quality["sample_ids"] != _select_quality_sample(unique_ledger, expected_sample, overlap_groups):
            raise ValidationFailure(f"{source_id} quality sample selection is not deterministic")
        if [review["case_id"] for review in quality["reviews"]] != quality["sample_ids"]:
            raise ValidationFailure(f"{source_id} quality reviews do not match the deterministic sample")
        if quality["lint_flags"] != _lint_summary(ledger):
            raise ValidationFailure(f"{source_id} quality lint summary does not match its full ledger")
        if quality["lint_version"] != LINT_VERSION:
            raise ValidationFailure(f"{source_id} quality lint version changed")
        reviews_pass = all(
            review["result"] == "pass"
            and review["prompt_complete"]
            and review["image_readable"]
            and review["semantic_match"]
            and review["visual_quality"] in {"high", "acceptable"}
            for review in quality["reviews"]
        )
        if (quality["result"] == "pass") != reviews_pass:
            raise ValidationFailure(f"{source_id} aggregate quality result does not match sample reviews")
        sampled_cases = [next(row for row in unique_ledger if row["case_id"] == case_id) for case_id in quality["sample_ids"]]
        expected_coverage = {
            "source_categories": sorted({str(row["category"]) for row in unique_ledger}),
            "sampled_categories": sorted({str(row["category"]) for row in sampled_cases}),
            "source_risk_flags": sorted({str(flag) for row in unique_ledger for flag in row.get("risk_flags", [])}),
            "sampled_risk_flags": sorted({str(flag) for row in sampled_cases for flag in row.get("risk_flags", [])}),
            "source_multi_output_case_count": sum(1 for row in unique_ledger if len(row.get("outputs", [])) > 1),
            "sampled_multi_output_case_count": sum(1 for row in sampled_cases if len(row.get("outputs", [])) > 1),
            "exact_overlap_sample_counts": {
                name: len(set(values) & set(quality["sample_ids"])) for name, values in sorted(overlap_groups.items())
            },
        }
        if quality["coverage"] != expected_coverage:
            raise ValidationFailure(f"{source_id} quality coverage summary is not reproducible")
        if expected_coverage["source_categories"] != expected_coverage["sampled_categories"]:
            raise ValidationFailure(f"{source_id} quality sample misses candidate categories")
        if expected_coverage["source_risk_flags"] != expected_coverage["sampled_risk_flags"]:
            raise ValidationFailure(f"{source_id} quality sample misses machine-risk clusters")
        if expected_coverage["source_multi_output_case_count"] and not expected_coverage["sampled_multi_output_case_count"]:
            raise ValidationFailure(f"{source_id} quality sample misses multi-output cases")
        if any(values and expected_coverage["exact_overlap_sample_counts"][name] == 0 for name, values in overlap_groups.items()):
            raise ValidationFailure(f"{source_id} quality sample misses an exact-overlap cluster")
        overlap_ids = (
            set(contribution["current_source_url_overlap_case_ids"])
            | set(contribution["current_prompt_overlap_case_ids"])
            | set(contribution["current_image_overlap_case_ids"])
        )
        if contribution["normalization_version"] != NORMALIZATION_VERSION:
            raise ValidationFailure(f"{source_id} normalization version changed")
        for prefix in ("current_source_url", "current_prompt", "current_image"):
            if contribution[f"{prefix}_overlap_count"] != len(contribution[f"{prefix}_overlap_case_ids"]):
                raise ValidationFailure(f"{source_id} {prefix} overlap count does not match its members")
        if contribution["unique_exact_contribution_count"] != item["metrics"]["unique_valid_case_count"] - len(overlap_ids):
            raise ValidationFailure(f"{source_id} unique exact contribution does not close")
        unique_ids = sorted(str(row["case_id"]) for row in unique_ledger if str(row["case_id"]) not in overlap_ids)
        if contribution["unique_exact_contribution_case_ids_sha256"] != _hash_lines(unique_ids):
            raise ValidationFailure(f"{source_id} unique exact contribution digest is invalid")
        maintenance = item["maintenance"]
        latest = dt.date.fromisoformat(maintenance["latest_substantive_update"])
        evaluated_on = dt.date.fromisoformat(maintenance["evaluated_on"])
        if evaluated_on != generated_at.date() or maintenance["latest_update_age_days"] != (evaluated_on - latest).days:
            raise ValidationFailure(f"{source_id} maintenance age is not reproducible")
        expected_recent_dates = sorted(
            value
            for value in maintenance["substantive_dates"]
            if evaluated_on - dt.timedelta(days=365) <= dt.date.fromisoformat(value) <= evaluated_on
        )
        if (
            maintenance["substantive_dates_365"] != expected_recent_dates
            or maintenance["substantive_update_dates_365"] != len(expected_recent_dates)
        ):
            raise ValidationFailure(f"{source_id} 365-day substantive update evidence is not reproducible")
        expected_eligible = (
            maintenance["latest_update_age_days"] <= THRESHOLDS["latest_substantive_update_days"]
            and maintenance["substantive_update_dates_365"] >= THRESHOLDS["minimum_substantive_update_dates_365"]
        )
        if maintenance["eligible"] != expected_eligible:
            raise ValidationFailure(f"{source_id} maintenance eligibility is not reproducible")
        if item["rights"]["auto_publish"] is not False or item["rights"]["public_eligibility"] != "review_required":
            raise ValidationFailure(f"{source_id} rights/publication boundary weakened")
        rights_evidence = item["rights"]["evidence_files"]
        if (
            rights_evidence != sorted(rights_evidence, key=lambda value: value["path"])
            or len({value["path"] for value in rights_evidence}) != len(rights_evidence)
            or any(
                value["byte_size"] <= 0 or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
                for value in rights_evidence
            )
        ):
            raise ValidationFailure(f"{source_id} rights evidence files are invalid")
        remote = item["metrics"]["remote_output_reference_count"]
        observations = evidence["remote_observations"]
        if evidence["remote_observations_sha256"] != _digest(observations):
            raise ValidationFailure(f"{source_id} remote observation digest is invalid")
        if remote:
            if source_id != "imaginevid-awesome-gpt-image-2-prompts-and-skills" or len(observations) != remote:
                raise ValidationFailure("remote observations are incomplete or assigned to the wrong source")
            if item["structure"]["local_asset_authority"] or item["status"] == "adapter_ready":
                raise ValidationFailure("imagineVid cannot be adapter_ready without immutable local assets")
            if contribution["current_image_overlap_count"] != 0:
                raise ValidationFailure("remote bytes may not participate in authoritative image overlap")
            expected_remote_members = sorted(
                (row["case_id"], output["locator"])
                for row in ledger
                for output in row["outputs"]
                if output["authority"] == "remote_observation"
            )
            observed_remote_members = sorted((row["case_id"], row["url"]) for row in observations)
            if observed_remote_members != expected_remote_members:
                raise ValidationFailure("remote observations do not exactly cover the fixed URL ledger")
            observed_broken = sum(1 for row in observations if not _remote_observation_ok(row))
            if item["metrics"]["broken_asset_count"] != observed_broken:
                raise ValidationFailure("remote broken-asset metric does not match its observation-time receipt")
        elif observations:
            raise ValidationFailure(f"{source_id} unexpectedly contains volatile remote observations")
        ready = item["status"] == "adapter_ready"
        passes = (
            not identity["archived"]
            and item["structure"]["local_asset_authority"]
            and item["metrics"]["unique_valid_case_count"] >= THRESHOLDS["minimum_unique_valid_cases"]
            and item["metrics"]["pair_rate"] >= THRESHOLDS["minimum_pair_rate"]
            and item["metrics"]["broken_asset_rate"] <= THRESHOLDS["maximum_broken_asset_rate"]
            and item["metrics"]["duplicate_rate"] <= THRESHOLDS["maximum_duplicate_rate"]
            and maintenance["eligible"]
            and quality["result"] == "pass"
            and contribution["unique_exact_contribution_count"] > 0
        )
        if ready != passes or (ready and item["recommended_adapter_strategy"] != spec["strategy"]):
            raise ValidationFailure(f"{source_id} adapter-ready decision does not match the frozen gates")
        if item["fixed_core_digest"] != _digest(_fixed_core_candidate(item)):
            raise ValidationFailure(f"{source_id} fixed-core digest is invalid")
    ready_items = sorted(
        (item for item in candidates if item["status"] == "adapter_ready"),
        key=lambda item: (-item["contribution"]["unique_exact_contribution_count"], item["source_id"]),
    )
    expected_batch = [
        {
            "rank": index + 1,
            "source_id": item["source_id"],
            "fixed_commit_sha": item["identity"]["fixed_commit_sha"],
            "unique_valid_case_count": item["metrics"]["unique_valid_case_count"],
            "unique_exact_contribution_count": item["contribution"]["unique_exact_contribution_count"],
            "recommended_adapter_strategy": item["recommended_adapter_strategy"],
            "case_scope": {
                "source_record_count": item["metrics"]["source_record_count"],
                "observed_case_count": item["metrics"]["observed_case_count"],
                "output_reference_count": item["metrics"]["output_reference_count"],
            },
            "known_exclusions": {
                "orphan_assets": item["evidence"]["orphan_assets"],
                "quality_failed_case_ids": [
                    review["case_id"] for review in item["quality"]["reviews"] if review["result"] == "fail"
                ],
            },
            "public_eligibility": "review_required",
        }
        for index, item in enumerate(ready_items)
    ]
    if payload["adapter_ready_batch"] != expected_batch:
        raise ValidationFailure("adapter-ready batch does not exactly match passing candidates")
    summary = payload["summary"]
    if (
        summary["candidate_count"] != 3
        or summary["adapter_ready_count"] != len(expected_batch)
        or summary["adapter_ready_unique_cases"] != sum(item["unique_valid_case_count"] for item in expected_batch)
        or summary["adapter_ready_unique_exact_contribution"] != sum(item["unique_exact_contribution_count"] for item in expected_batch)
        or summary["current_case_count"] != 1513
        or summary["current_output_count"] != 1930
        or summary["current_source_file_count"] != 2260
        or summary["current_deduplicated_asset_object_count"] != 1885
        or summary["real_public_cases"] != 0
        or summary["protected_scope_modified"] is not False
    ):
        raise ValidationFailure("summary does not close")
    if payload["canonical_digest"] != _digest(_fixed_core_payload(payload)):
        raise ValidationFailure("fixed-core canonical digest is invalid")
    report_text = (repo_root / "reports" / "phase2" / "source-expansion-admission-v2.md").read_text(encoding="utf-8")
    handoff_text = (repo_root / "docs" / "phase2" / "source-expansion-admission-v2.md").read_text(encoding="utf-8")
    design_text = (repo_root / "1.md").read_text(encoding="utf-8")
    for source_id in EXPECTED_CANDIDATES:
        if source_id not in report_text or source_id not in handoff_text:
            raise ValidationFailure(f"cross-file candidate reference is missing: {source_id}")
    for value in ("1513", "1930", "2260", "1885", "0 real public"):
        if value not in report_text or value not in handoff_text:
            raise ValidationFailure(f"cross-file protected baseline is missing: {value}")
    if "source-expansion-admission-v2" not in design_text or "TASK-0021" not in design_text:
        raise ValidationFailure("1.md does not record the v2 admission status/handoff")
    return {
        "candidate_count": 3,
        "adapter_ready_count": len(expected_batch),
        "adapter_ready_sources": [item["source_id"] for item in expected_batch],
        "adapter_ready_unique_cases": summary["adapter_ready_unique_cases"],
        "adapter_ready_unique_exact_contribution": summary["adapter_ready_unique_exact_contribution"],
        "current_case_count": 1513,
        "current_output_count": 1930,
        "real_public_cases": 0,
    }


def _live_validate(payload: Mapping[str, Any]) -> dict[str, Any]:
    runtime_parent = Path(os.environ.get("IMAGE2_TASK0021_RUNTIME_ROOT", tempfile.gettempdir())).resolve()
    if runtime_parent == REPO_ROOT.resolve() or REPO_ROOT.resolve() in runtime_parent.parents:
        raise ValidationFailure("TASK-0021 runtime root must remain outside the workspace")
    run_root = Path(tempfile.mkdtemp(prefix="image2-task0021-live-", dir=runtime_parent))
    result: dict[str, Any] | None = None
    try:
        current = _current_index(rebuild=True)
        if _digest({"cases": current["cases"], "assets": current["assets"]}) != payload["authority"]["current_index_core_sha256"]:
            raise ValidationFailure("live six-source production index differs from the v2 authority")
        current_sets = _current_exact_sets(current)
        live_rows: list[dict[str, Any]] = []
        for item in payload["candidates"]:
            source_id = item["source_id"]
            spec = EXPECTED_CANDIDATES[source_id]
            metadata = _github_json(f"https://api.github.com/repos/{spec['repo']}")
            if (
                int(metadata.get("id", -1)) != item["identity"]["repository_id"]
                or metadata.get("default_branch") != item["identity"]["default_branch"]
                or bool(metadata.get("archived")) != item["identity"]["archived"]
            ):
                raise ValidationFailure(f"live repository identity changed: {source_id}")
            commit = _github_json(f"https://api.github.com/repos/{spec['repo']}/commits/{item['identity']['fixed_commit_sha']}")
            if commit.get("sha") != item["identity"]["fixed_commit_sha"]:
                raise ValidationFailure(f"live fixed Commit is unavailable: {source_id}")
            snapshot = _clone_fixed(spec["repo"], item["identity"]["fixed_commit_sha"], run_root / source_id)
            tree = _repository_tree(snapshot)
            if any(tree[key] != item["identity"][key] for key in tree):
                raise ValidationFailure(f"live fixed tree identity changed: {source_id}")
            parsed = _parse_candidate(source_id, snapshot)
            remote = _observe_remote(parsed["cases"]) if source_id.startswith("imaginevid-") else []
            metrics = _candidate_metrics(parsed, remote)
            stable_metric_keys = {
                "source_record_count", "observed_case_count", "exact_prompt_count", "output_reference_count",
                "local_output_reference_count", "remote_output_reference_count", "repository_raster_count",
                "orphan_raster_count", "valid_case_count", "unique_valid_case_count", "pair_rate", "duplicate_count", "duplicate_rate",
                "within_source_dedupe_version",
            }
            for key in stable_metric_keys:
                if metrics[key] != item["metrics"][key]:
                    raise ValidationFailure(f"live fixed snapshot metric changed: {source_id}.{key}")
            if (
                parsed["cases"] != item["evidence"]["case_ledger"]
                or parsed["orphan_assets"] != item["evidence"]["orphan_assets"]
                or parsed["asset_terminal_results"] != item["evidence"]["asset_terminal_results"]
                or parsed["rights_evidence"] != item["rights"]["evidence_files"]
            ):
                raise ValidationFailure(f"live fixed snapshot ledger changed: {source_id}")
            contribution = _contribution(parsed["cases"], current_sets)
            if contribution != item["contribution"]:
                raise ValidationFailure(f"live exact contribution changed: {source_id}")
            overlap_groups = {
                "source_url": contribution["current_source_url_overlap_case_ids"],
                "prompt": contribution["current_prompt_overlap_case_ids"],
                "image": contribution["current_image_overlap_case_ids"],
            }
            expected_sample = _select_quality_sample(
                _unique_valid_cases(parsed["cases"]), item["quality"]["sample_size"], overlap_groups
            )
            if expected_sample != item["quality"]["sample_ids"]:
                raise ValidationFailure(f"live deterministic quality sample changed: {source_id}")
            evaluated_on = dt.date.fromisoformat(item["maintenance"]["evaluated_on"])
            history = _content_history(snapshot, parsed["history_paths"], evaluated_on)
            for key in (
                "latest_substantive_update", "first_substantive_update", "substantive_update_dates_365",
                "substantive_dates_365", "substantive_dates", "evidence_commits",
            ):
                if history[key] != item["maintenance"][key]:
                    raise ValidationFailure(f"live fixed maintenance evidence changed: {source_id}.{key}")
            live_rows.append(
                {
                    "source_id": source_id,
                    "fixed_commit_sha": item["identity"]["fixed_commit_sha"],
                    "observed_case_count": metrics["observed_case_count"],
                    "output_reference_count": metrics["output_reference_count"],
                    "remote_observation_count": len(remote),
                    "remote_observation_failures": sum(1 for row in remote if not _remote_observation_ok(row)),
                }
            )
        result = {
            "current_case_count": current["case_count"],
            "current_output_count": current["output_count"],
            "current_source_file_count": 2260,
            "current_deduplicated_asset_object_count": 1885,
            "candidates": live_rows,
            "temporary_runtime_cleaned": True,
        }
    finally:
        _remove_tree(run_root)
    if result is None:
        raise ValidationFailure("TASK-0021 live validation did not produce a result")
    return result


def validate(
    audit_path: Path,
    schema_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    live: bool = False,
    determinism_check: bool = False,
) -> dict[str, Any]:
    payload = _load(audit_path)
    schema = _load(schema_path)
    issues = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload), key=lambda item: list(item.path))
    if issues:
        detail = "; ".join(f"{'.'.join(map(str, item.path)) or '<root>'}: {item.message}" for item in issues[:8])
        raise ValidationFailure(f"Schema validation failed: {detail}")
    summary = _semantic_validate(payload, repo_root)
    if determinism_check:
        second = _semantic_validate(json.loads(json.dumps(payload)), repo_root)
        if summary != second or payload["canonical_digest"] != _digest(_fixed_core_payload(payload)):
            raise ValidationFailure("fixed-core determinism check changed the semantic result")
    live_summary = _live_validate(payload) if live else None
    return {
        "status": "passed",
        "audit_sha256": _sha256_file(audit_path),
        "canonical_digest": payload["canonical_digest"],
        "summary": summary,
        "live": live_summary,
    }


def _render_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 2 高质量新来源准入审计 v2",
        "",
        f"> 机器权威：`source-expansion-admission-v2.json`；生成时间：`{payload['generated_at']}`。",
        "",
        "## 结论",
        "",
        "本轮只审计三个新候选，不修改 registry、Adapter、Canonical、库存或公开状态。当前基线保持 6 active、1513 cases、1930 outputs、2260 source files、1885 deduplicated asset objects、0 real public。",
        "",
        "| 来源 | fixed Commit / tree | records / cases / outputs | exact-new | 状态 |",
        "|---|---|---:|---:|---|",
    ]
    for item in payload["candidates"]:
        metrics = item["metrics"]
        lines.append(
            f"| `{item['source_id']}` | `{item['identity']['fixed_commit_sha']}` / `{item['identity']['git_tree_sha']}` | {metrics['source_record_count']} / {metrics['observed_case_count']} / {metrics['output_reference_count']} | {item['contribution']['unique_exact_contribution_count']} | `{item['status']}` |"
        )
    lines.extend(["", "## 质量、来源与资产边界", ""])
    for item in payload["candidates"]:
        flags = sum(value["count"] for value in item["quality"]["lint_flags"].values())
        failed_ids = sorted(review["case_id"] for review in item["quality"]["reviews"] if review["result"] == "fail")
        observations = item["evidence"]["remote_observations"]
        observation_ok = sum(1 for row in observations if _remote_observation_ok(row))
        lines.extend(
            [
                f"### `{item['source_id']}`",
                "",
                f"- 结构：`{item['structure']['strategy']}`；质量样本 {item['quality']['sample_size']}，结论 `{item['quality']['result']}`。",
                f"- 样本覆盖：{len(item['quality']['coverage']['sampled_categories'])}/{len(item['quality']['coverage']['source_categories'])} 类别，{len(item['quality']['coverage']['sampled_risk_flags'])}/{len(item['quality']['coverage']['source_risk_flags'])} 风险簇；失败案例：{', '.join(f'`{value}`' for value in failed_ids) if failed_ids else '无'}。",
                f"- 全量风险/低信息 flag 事件：{flags}；这些是审核线索，不代表自动删除或公开批准。",
                f"- 资产：{len(item['evidence']['asset_terminal_results'])}/{item['metrics']['repository_raster_count']} 本地 raster 完成魔数/大小/SHA-256 终端校验；local outputs {item['metrics']['local_output_reference_count']}，remote outputs {item['metrics']['remote_output_reference_count']}，orphan rasters {item['metrics']['orphan_raster_count']}。",
                f"- 维护：最近实质更新 `{item['maintenance']['latest_substantive_update']}`；过去 365 天 {item['maintenance']['substantive_update_dates_365']} 个不同更新日；成熟跨度 {item['maintenance']['maturity_span_days']} 天。",
                f"- 独立贡献 overlap：source URL {item['contribution']['current_source_url_overlap_count']}、Prompt {item['contribution']['current_prompt_overlap_count']}、fixed image {item['contribution']['current_image_overlap_count']}。",
                f"- 远程观测：{observation_ok}/{len(observations)} 通过当前 HTTP/图片终端检查；该值不属于 fixed-core authority。" if observations else "- 远程观测：无；图片权威来自 fixed Commit 本地文件。",
                f"- Rights：Prompt/asset 均 `review_required`，`auto_publish=false`。",
                f"- 结论：{item['status_reason']}。",
                "",
            ]
        )
    lines.extend(
        [
            "## Adapter handoff",
            "",
            "只有 JSON `adapter_ready_batch` 中的 fixed Commit 可以进入下一张 Adapter 卡。imagineVid 的远程图片观测是时点证据，不是 immutable asset authority。",
            "",
            "本任务不做 Mageia remediation、历史大库导入或 Canonical/近似去重。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_handoff(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 2 高质量新来源准入 v2 与 Adapter Handoff",
        "",
        "## 当前保护基线",
        "",
        "当前仍为 6 active、1513 internal Source Cases、1930 outputs、2260 source files、1885 deduplicated asset objects、0 real public。`source-expansion-admission-v2` 不修改 registry、库存、Canonical、Candidate v2 或 Public API/Web v1。",
        "",
        "## 唯一允许的第二批 Adapter 输入",
        "",
        "| Rank | source_id | fixed Commit | strategy | scope records/cases/outputs | valid / exact-new |",
        "|---:|---|---|---|---:|---:|",
    ]
    for item in payload["adapter_ready_batch"]:
        lines.append(
            f"| {item['rank']} | `{item['source_id']}` | `{item['fixed_commit_sha']}` | `{item['recommended_adapter_strategy']}` | {item['case_scope']['source_record_count']} / {item['case_scope']['observed_case_count']} / {item['case_scope']['output_reference_count']} | {item['unique_valid_case_count']} / {item['unique_exact_contribution_count']} |"
        )
    if not payload["adapter_ready_batch"]:
        lines.append("| — | — | — | — | 0 / 0 / 0 | 0 / 0 |")
    for item in payload["adapter_ready_batch"]:
        exclusions = item["known_exclusions"]
        lines.extend(
            [
                "",
                f"- `{item['source_id']}` known exclusions：orphan assets {len(exclusions['orphan_assets'])}；quality-failed cases {len(exclusions['quality_failed_case_ids'])}。",
            ]
        )
    lines.extend(["", "## 候选边界", ""])
    for item in payload["candidates"]:
        failed_ids = sorted(review["case_id"] for review in item["quality"]["reviews"] if review["result"] == "fail")
        lines.append(
            f"- `{item['source_id']}`：`{item['status']}`；{item['status_reason']}；"
            f"quality-failed {len(failed_ids)}，orphan rasters {item['metrics']['orphan_raster_count']}，"
            f"remote outputs {item['metrics']['remote_output_reference_count']}。"
        )
    lines.extend(
        [
            "",
            "## 后续 Adapter 必须保持",
            "",
            "- 只消费本文件列出的 fixed Commit、strategy 和明确 source scope。",
            "- 全量覆盖 case/output/orphan，未知字段、缺图、弱配对、重复 ID 和越界路径 fail closed。",
            "- Prompt/asset 继续 `review_required`，`auto_publish=false`；准入不等于 active 或 public。",
            "- exact-overlap 只用于来源贡献审计，不写 Canonical Case，不做语义/视觉自动合并。",
            "- imagineVid 在独立 immutable snapshot 任务完成前不得进入 Adapter 激活。",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_build_outputs(payload: Mapping[str, Any], audit: Path, report: Path, handoff: Path) -> None:
    for path in (audit, report, handoff):
        path.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    report.write_text(_render_report(payload), encoding="utf-8")
    handoff.write_text(_render_handoff(payload), encoding="utf-8")


def _emit_sample_queue(snapshot_root: Path, current_index_path: Path, output: Path) -> None:
    result: dict[str, Any] = {}
    current_sets = _current_exact_sets(_current_index(rebuild=False, cache_path=current_index_path))
    for source_id in EXPECTED_CANDIDATES:
        folder = {
            "ecomimagelab-ecommerce-gpt-image-prompts": "ecomimagelab",
            "hiapiai-awesome-gpt-image-2-prompts": "hiapiai",
            "imaginevid-awesome-gpt-image-2-prompts-and-skills": "imaginevid",
        }[source_id]
        parsed = _parse_candidate(source_id, snapshot_root / folder)
        unique_cases = _unique_valid_cases(parsed["cases"])
        contribution = _contribution(parsed["cases"], current_sets)
        overlap_groups = {
            "source_url": contribution["current_source_url_overlap_case_ids"],
            "prompt": contribution["current_prompt_overlap_case_ids"],
            "image": contribution["current_image_overlap_case_ids"],
        }
        sample_ids = _select_quality_sample(unique_cases, _expected_sample_size(len(unique_cases)), overlap_groups)
        by_id = {item["case_id"]: item for item in parsed["cases"]}
        result[source_id] = {
            case_id: {
                "category": by_id[case_id]["category"],
                "prompt_length": by_id[case_id]["prompt_length"],
                "risk_flags": by_id[case_id]["risk_flags"],
                "asset_locator": by_id[case_id]["outputs"][0]["locator"],
                "result": "pending",
                "prompt_complete": False,
                "image_readable": False,
                "semantic_match": False,
                "visual_quality": "unknown",
                "notes": "",
            }
            for case_id in sample_ids
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=REPO_ROOT / "reports" / "phase2" / "source-expansion-admission-v2.json")
    parser.add_argument("--schema", type=Path, default=REPO_ROOT / "schemas" / "phase2-source-expansion-admission-v2.schema.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--determinism-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--current-index", type=Path, default=CURRENT_CACHE)
    parser.add_argument("--quality-review", type=Path)
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "reports" / "phase2" / "source-expansion-admission-v2.md")
    parser.add_argument("--handoff", type=Path, default=REPO_ROOT / "docs" / "phase2" / "source-expansion-admission-v2.md")
    parser.add_argument("--emit-sample-queue", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.emit_sample_queue is not None:
            if args.snapshot_root is None:
                raise ValidationFailure("--emit-sample-queue requires --snapshot-root")
            _emit_sample_queue(args.snapshot_root, args.current_index, args.emit_sample_queue)
            result: dict[str, Any] = {"status": "sample_queue_written", "output": str(args.emit_sample_queue)}
        elif args.build:
            if args.snapshot_root is None or args.quality_review is None:
                raise ValidationFailure("--build requires --snapshot-root and --quality-review")
            payload = build_report(snapshot_root=args.snapshot_root, current_index_path=args.current_index, quality_review_path=args.quality_review)
            _write_build_outputs(payload, args.audit, args.report, args.handoff)
            result = {"status": "built", "audit": str(args.audit), "canonical_digest": payload["canonical_digest"]}
        else:
            result = validate(args.audit, args.schema, live=args.live, determinism_check=args.determinism_check)
    except (OSError, ValueError, ValidationFailure) as exc:
        payload = {"status": "failed", "error": type(exc).__name__, "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else f"PASS: {result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
