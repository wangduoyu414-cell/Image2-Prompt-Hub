"""Build and fail-closed validate the four-role Phase 2 admission v3 evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from scripts import validate_phase2_source_expansion_admission as v2

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "phase2-source-expansion-admission-v3"
RUNTIME_ROOT = Path(os.environ.get("IMAGE2_TASK0022_RUNTIME_ROOT", r"C:/Users/admin/.codex/runtime/image2/task-0022"))
SOURCE_SPECS = {
    "goku-openlab-gpt-image-2-prompts-datasets": {"folder": "goku", "revision": "c4e79e9e11b3e754ec64f6400c7f94de6a5f103d", "role": "full", "mode": "continuous", "status": "continuous_ready", "url": "https://huggingface.co/datasets/Goku-OpenLab/gpt-image-2-prompts-datasets", "provider_id": "6a467d6d7239e0c7f8f23621", "branch": "main", "family_role": "aggregator", "strategy": "goku_hf_lfs_metadata_v1", "tree_manifest_sha256": "0acc235b6d5ca21d28276c8b904126722f7d97080314072d9a1a160fed618b71", "entry_count": 28296},
    "chaosrealmsai-gpt-image-2-gallery": {"folder": "chaos", "revision": "5296db8c996e38776c83a0bc8c64f848dcd512b3", "role": "full", "mode": "fixed_history", "status": "fixed_history_ready", "url": "https://github.com/ChaosRealmsAI/gpt-image-2-gallery", "provider_id": "1219036815", "branch": "main", "family_role": "canonical", "strategy": "chaos_meta_three_webp_v1", "tree_manifest_sha256": "cef3ba3807ba81e5cd0647dad87bcf5e85edf0718d3b584a09d055b41bd6c705", "entry_count": 16788},
    "youmind-openlab-gpt-image-2-prompts-search": {"folder": "youmind", "revision": "08861ab6db5d772e311f5661cfb0a3ae06e10bb1", "role": "comparator", "mode": "reserve", "status": "comparator_only", "url": "https://github.com/YouMind-OpenLab/gpt-image-2-prompts-search", "provider_id": "1218575008", "branch": "main", "family_role": "reserve", "strategy": "youmind_reference_comparator_v1", "tree_manifest_sha256": "ebde0f4e4d2cc8268cd8295da62a95035c9903c062837467d5cd7cbf57b6c2b9", "entry_count": 27},
    "tigerowo-awesome-gpt-image-2-prompts": {"folder": "tigerowo", "revision": "60e9c65baecfd6d6d51ac4e4d87f146af834bb64", "role": "excluded_control", "mode": "excluded", "status": "excluded", "url": "https://github.com/tigerowo/awesome-gpt-image-2-prompts", "provider_id": "1284712193", "branch": "main", "family_role": "backup", "strategy": "tigerowo_exclusion_control_v1", "tree_manifest_sha256": "197095aa014e00d5f57374ea8682df064c15ae201380f6e7db7ccb94b0cac7cd", "entry_count": 1326},
}
GOKU_METADATA_LFS_OID = "45295247269b84b54b053007c36682d3fc344599d69e0f18fedfb0b3088d281f"
GOKU_METADATA_BYTE_SIZE = 116_859_730
V3_LINT_VERSION = "source-quality-lint-v3-multilingual-risk-and-provenance"
V3_RISK_PATTERNS: dict[str, tuple[str, ...]] = {
    "brand_or_logo": ("ferrari", "openai", "spacex", "claude", "claudecode", "xiaomi", "小米", "tamiya", "levi's", "levis", "nike", "adidas", "gucci", "coca-cola", "苹果", "品牌", "ロゴ"),
    "public_figure_or_celebrity": ("sam altman", "cristiano ronaldo", "c罗", "cr7", "mbappé", "mbappe", "neymar", "haaland", "哈兰德", "messi", "梅西", "donald trump", "elon musk", "taylor swift", "名人", "著名人", "prominente"),
    "watermark_removal_or_transparency": ("remove watermark", "without watermark", "watermark removal", "transparent background", "cutout", "去水印", "透明背景", "抠图", "透過背景", "透かし", "wasserzeichen", "freisteller"),
    "adult_or_sexualized": ("nude", "naked", "lingerie", "sexy", "erotic", "裸体", "色情", "内衣", "ヌード", "erotisch"),
    "weapon_or_gore": ("gun", "rifle", "pistol", "weapon", "blood", "gore", "尸体", "枪", "武器", "血腥", "銃", "血", "waffe", "blut"),
    "minor_or_young_person": ("minor", "child", "children", "teenage", "schoolgirl", "underage", "未成年人", "儿童", "小学生", "未成年", "子供", "minderjähr"),
    "identity_or_official_document": ("passport", "driver's license", "drivers license", "national id", "identity card", "身份证", "护照", "驾驶证", "身分証", "パスポート", "ausweis", "reisepass"),
    "third_party_ip_or_character": ("fifa", "minions", "gta", "grand theft auto", "breaking bad", "the walking dead", "money heist", "squid game", "pokemon", "disney", "marvel", "minecraft", "原神", "ポケモン", "スターウォーズ"),
    "suspicious_garbled_or_watermark": ("ai watermark", "乱码", "garbled", "mojibake", "???", "�", "文字化け"),
}

ValidationFailure = v2.ValidationFailure
_normalize_prompt = v2._normalize_prompt
_normalize_source_url = v2._normalize_source_url
_risk_flags = v2._risk_flags
_select_quality_sample = v2._select_quality_sample
_current_exact_sets = v2._current_exact_sets
_contribution = v2._contribution

def _digest(value: Any) -> str: return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def _hash_lines(values: Sequence[str]) -> str: return hashlib.sha256("\n".join(values).encode()).hexdigest()
def _load(path: Path) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValidationFailure(f"cannot load JSON: {path}") from exc
def _sha_file(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _safe_rel(value: object, label: str) -> str: return v2._safe_rel(value, label)

def _v3_risk_flags(value: str) -> list[str]:
    text = value.casefold()
    def contains(term: str) -> bool:
        folded = term.casefold()
        if folded.isascii() and re.search(r"[a-z0-9]", folded):
            return re.search(rf"(?<![a-z0-9]){re.escape(folded)}(?![a-z0-9])", text) is not None
        return folded in text
    flags = [name for name, terms in V3_RISK_PATTERNS.items() if any(contains(term) for term in terms)]
    normalized = _normalize_prompt(value)
    latin_words = re.findall(r"[a-z]+", normalized)
    letters = [char for char in normalized if char.isalpha()]
    latin_ratio = sum(char.isascii() for char in letters) / max(1, len(letters))
    if len(normalized) < 80 or (latin_ratio >= 0.70 and len(latin_words) < 15): flags.append("low_information")
    return sorted(set(flags))

def _metadata_text(value: object) -> str:
    if isinstance(value, str): return value
    if isinstance(value, Mapping): return "\n".join(_metadata_text(item) for item in value.values())
    if isinstance(value, list): return "\n".join(_metadata_text(item) for item in value)
    return ""

def _fixed_asset(snapshot: Path, raw: str) -> dict[str, Any]:
    relative = _safe_rel(raw, "asset path")
    path = snapshot / relative
    if not path.is_file(): raise ValidationFailure(f"missing asset: {relative}")
    data = path.read_bytes()
    if not data: raise ValidationFailure(f"empty asset: {relative}")
    magic = data[:12].hex()
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise ValidationFailure(f"unsupported image magic: {relative}")
    return {"path": relative, "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "magic": magic}

def _hf_tree(snapshot: Path) -> list[dict[str, Any]]:
    """Load the immutable Hub tree cache; it is the LFS authority, never metadata alone."""
    path = snapshot / "hf-tree.json"
    if not path.is_file():
        raise ValidationFailure("Goku fixed HF tree manifest is missing")
    value = _load(path)
    if isinstance(value, dict) and value.get("revision") not in {None, SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]["revision"]}:
        raise ValidationFailure("Goku HF tree revision drift")
    rows = value.get("files", value.get("siblings", value.get("entries"))) if isinstance(value, dict) else value
    if not isinstance(rows, list): raise ValidationFailure("Goku HF tree manifest rows are missing")
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict): raise ValidationFailure("Goku HF tree row is invalid")
        raw_path = row.get("path", row.get("rfilename"))
        if not isinstance(row.get("lfs"), dict):
            continue
        lfs = row["lfs"]
        oid, size = lfs.get("oid"), lfs.get("size", row.get("size"))
        if not isinstance(raw_path, str) or not isinstance(oid, str) or len(oid) != 64 or not isinstance(size, int) or size < 1:
            raise ValidationFailure("Goku HF tree row lacks path/LFS OID/size")
        result.append({"path": _safe_rel(raw_path, "HF tree path"), "lfs_oid": oid, "byte_size": size, "authority": "hf_lfs"})
    if len({x["path"] for x in result}) != len(result): raise ValidationFailure("Goku HF tree paths are duplicated")
    return sorted(result, key=lambda x: x["path"])

def _git_authority(snapshot: Path, source_id: str) -> dict[str, Any]:
    spec = SOURCE_SPECS[source_id]
    def run(*args: str) -> str:
        value = subprocess.run(["git", *args], cwd=snapshot, check=False, capture_output=True, text=True)
        if value.returncode: raise ValidationFailure(f"git authority failed: {args[0]}")
        return value.stdout.strip()
    head, remote = run("rev-parse", "HEAD"), run("config", "--get", "remote.origin.url")
    if head != spec["revision"] or remote.rstrip("/").removesuffix(".git") != spec["url"]: raise ValidationFailure(f"{source_id} fixed git authority drift")
    # Avoid ``-l``: partial clones would otherwise fetch every blob merely to
    # obtain sizes. Tree entry mode/OID/path are sufficient fixed authority.
    manifest = run("ls-tree", "-r", "--full-tree", spec["revision"])
    lines = [line for line in manifest.splitlines() if line]
    blobs = [line for line in lines if line.startswith("100") or line.startswith("120")]
    digest = hashlib.sha256((manifest + "\n").encode()).hexdigest()
    if len(lines) != spec["entry_count"] or digest != spec["tree_manifest_sha256"]: raise ValidationFailure(f"{source_id} fixed git tree drift")
    return {"kind": "git", "revision": head, "remote_url": spec["url"], "entry_count": len(lines), "blob_count": len(blobs), "tree_manifest_sha256": digest, "commit_date": run("show", "-s", "--format=%cI", head)}

def _goku_authority(snapshot: Path) -> dict[str, Any]:
    raw = _load(snapshot / "hf-tree.json")
    if not isinstance(raw, dict) or raw.get("revision") != SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]["revision"] or raw.get("repository") not in {None, "Goku-OpenLab/gpt-image-2-prompts-datasets"}: raise ValidationFailure("Goku HF authority revision/repository drift")
    files = raw.get("files")
    if not isinstance(files, list): raise ValidationFailure("Goku HF authority files missing")
    canonical, images, lfs = [], 0, 0
    metadata = None
    for row in files:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("size"), int): raise ValidationFailure("Goku HF authority row invalid")
        fact = row.get("lfs") if isinstance(row.get("lfs"), dict) else {}
        oid = fact.get("oid", row.get("oid")); lfs_size = fact.get("size", "")
        canonical.append(f"{row['path']}|{oid}|{row['size']}|{lfs_size}")
        images += row["path"].lower().endswith((".jpg", ".jpeg", ".png", ".webp")); lfs += isinstance(row.get("lfs"), dict)
        if row["path"] == "metadata.jsonl": metadata = {"oid": fact.get("oid"), "size": fact.get("size")}
    digest = hashlib.sha256("\n".join(sorted(canonical)).encode()).hexdigest()
    spec = SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]
    if len(files) != spec["entry_count"] or images != 28293 or lfs != 28294 or metadata != {"oid": GOKU_METADATA_LFS_OID, "size": GOKU_METADATA_BYTE_SIZE} or digest != spec["tree_manifest_sha256"]: raise ValidationFailure("Goku HF fixed tree counts or metadata authority drift")
    return {"kind": "hf", "repository": "Goku-OpenLab/gpt-image-2-prompts-datasets", "revision": raw["revision"], "file_count": len(files), "image_count": images, "lfs_count": lfs, "metadata_oid": metadata["oid"], "metadata_size": metadata["size"], "tree_manifest_sha256": digest}

def _reasoned_filter(cases: list[dict[str, Any]], *, family_hashes: set[str], current: Mapping[str, set[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply deterministic hard exclusions before within-source uniqueness."""
    retained: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    seen_prompts: set[str] = set()
    seen_urls: set[str] = set()
    seen_images: set[str] = set()
    for case in sorted(cases, key=lambda x: x["case_id"]):
        reasons: list[str] = []
        if case.get("terminal_reason"): reasons.append(str(case["terminal_reason"]))
        elif not case.get("source_url_key"): reasons.append("missing_source")
        if not case.get("outputs") and not case.get("terminal_reason") and not case.get("missing_authority_asset"): reasons.append("missing_asset")
        if case.get("reference_dependency"): reasons.append("risk:reference_dependency")
        reasons.extend(f"risk:{flag}" for flag in case.get("risk_flags", []))
        if reasons:
            exclusions.extend({"case_id": case["case_id"], "reason": reason} for reason in sorted(set(reasons)))
            continue
        image_keys = {str(o.get("sha256") or o.get("lfs_oid") or "") for o in case["outputs"]}
        reason = None
        if case["prompt_sha256"] in seen_prompts or case["source_url_key"] in seen_urls or image_keys & seen_images: reason = "within_source_duplicate"
        elif case["prompt_sha256"] in family_hashes: reason = "youmind_family_duplicate"
        elif case["prompt_sha256"] in current["prompt"] or case["source_url_key"] in current["source_url"]: reason = "current_exact_duplicate"
        if reason: exclusions.append({"case_id": case["case_id"], "reason": reason})
        else:
            retained.append(case); seen_prompts.add(case["prompt_sha256"]); seen_urls.add(case["source_url_key"]); seen_images.update(image_keys)
    return retained, exclusions

def _case(case_id: str, record_id: str, category: str, prompt: str, source_url: object, source_path: str, outputs: list[dict[str, Any]], *, risk_text: str | None = None) -> dict[str, Any]:
    normalized = _normalize_prompt(prompt)
    if not normalized: raise ValidationFailure(f"empty prompt: {case_id}")
    v2_flags = [flag for flag in _risk_flags(prompt) if flag != "low_information_prompt"]
    metadata_flags = set(_v3_risk_flags(risk_text or prompt)) - {"low_information"}
    # Completeness is a property of the authoritative raw prompt. A long
    # translated title/tag bundle must not make a one-line raw prompt eligible.
    flags = sorted(set(v2_flags) | metadata_flags | set(_v3_risk_flags(prompt)))
    return {"case_id": case_id, "source_record_id": record_id, "category": category or "uncategorized", "source_path": source_path, "prompt": prompt, "prompt_sha256": hashlib.sha256(normalized.encode()).hexdigest(), "prompt_length": len(prompt), "source_url_key": _normalize_source_url(source_url), "outputs": outputs, "risk_flags": flags, "strong_pairing": bool(outputs)}

def _terminal_case(case_id: str, category: str, source_path: str, source_url: object, reason: str) -> dict[str, Any]:
    return {"case_id": case_id, "source_record_id": case_id, "category": category or "uncategorized", "source_path": source_path, "prompt": "", "prompt_sha256": None, "prompt_length": 0, "source_url_key": _normalize_source_url(source_url), "outputs": [], "risk_flags": [], "strong_pairing": False, "terminal_reason": reason}

def _parse_goku(snapshot: Path, *, family_hashes: set[str] | None = None, current: Mapping[str, set[str]] | None = None) -> dict[str, Any]:
    metadata = snapshot / "metadata.jsonl"
    if not metadata.is_file(): raise ValidationFailure("Goku metadata.jsonl is missing")
    tree = _hf_tree(snapshot)
    by_path = {row["path"]: row for row in tree}
    metadata_row = by_path.get("metadata.jsonl")
    if not metadata_row or metadata_row["lfs_oid"] != GOKU_METADATA_LFS_OID or _sha_file(metadata) != GOKU_METADATA_LFS_OID:
        raise ValidationFailure("Goku metadata fixed LFS OID mismatch")
    raw_cases, exclusions, referenced, all_referenced = [], [], set(), set()
    raw_metadata = metadata.read_text(encoding="utf-8")
    decoder, offset, number = json.JSONDecoder(strict=False), 0, 0
    while offset < len(raw_metadata):
        while offset < len(raw_metadata) and raw_metadata[offset].isspace(): offset += 1
        if offset >= len(raw_metadata): break
        number += 1
        try: row, offset = decoder.raw_decode(raw_metadata, offset)
        except json.JSONDecodeError as exc: raise ValidationFailure(f"Goku metadata record {number} is invalid") from exc
        if not isinstance(row, dict): raise ValidationFailure(f"Goku metadata record {number} is not an object")
        record_id = str(row.get("id", number))
        observed_image_paths = row.get("media", {}).get("images")
        if isinstance(observed_image_paths, list):
            for value in observed_image_paths:
                relative = _safe_rel(value, "Goku image path")
                if relative in by_path: all_referenced.add(relative)
        if row.get("model_info", {}).get("name") != "gpt-image-2": continue
        image_paths = observed_image_paths
        prompt = row.get("raw_p")
        if not isinstance(image_paths, list) or not image_paths or not isinstance(prompt, str):
            raw_cases.append(_terminal_case(record_id, str(row.get("category", "uncategorized")), "metadata.jsonl", row.get("sourceLink"), "missing_prompt_or_media")); continue
        outputs = []
        missing_object = False
        for value in image_paths:
            relative = _safe_rel(value, "Goku image path")
            fact = by_path.get(relative)
            if fact is None:
                outputs = []; missing_object = True; break
            referenced.add(relative); outputs.append(fact)
        case = _case(record_id, record_id, str(row.get("category", "uncategorized")), prompt, row.get("sourceLink"), "metadata.jsonl", outputs, risk_text=_metadata_text({"raw_p": prompt, "slug": row.get("slug"), "i18n": row.get("i18n"), "tags": row.get("tags"), "title": row.get("title")}))
        reference_text = _metadata_text({"prompt": prompt, "i18n": row.get("i18n"), "slug": row.get("slug")}).casefold()
        reference_signal = re.search(r"\b(?:attached|uploaded|reference)\s+(?:image|photo|picture)s?\b|\buse\s+(?:the\s+)?(?:attached|uploaded|reference)\b|参考图|上传图片|根据.{0,12}(?:图片|图像)|添付画像|参照画像", reference_text)
        case["model_evidence"] = "model_info.name=gpt-image-2"; case["reference_dependency"] = bool(row.get("reference_images") or row.get("input_images") or reference_signal); case["missing_authority_asset"] = missing_object
        if missing_object: case["terminal_reason"] = "missing_lfs_object"
        raw_cases.append(case)
    current = current or {"prompt": set(), "source_url": set(), "image": set()}
    filtered, hard_exclusions = _reasoned_filter(raw_cases, family_hashes=family_hashes or set(), current=current)
    exclusions.extend(hard_exclusions)
    image_assets = [row for row in tree if row["path"] != "metadata.jsonl" and row["path"].lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    referred = set(referenced)
    classifications = {"subset_ref": sorted(referred), "out_of_scope": sorted(x["path"] for x in image_assets if x["path"] in all_referenced and x["path"] not in referred), "global_orphan": sorted(x["path"] for x in image_assets if x["path"] not in all_referenced)}
    manifest_path = snapshot / "asset-manifest.json"
    if manifest_path.is_file():
        manifest = _load(manifest_path); rows = manifest.get("assets") if isinstance(manifest, dict) else None
        if not isinstance(rows, list): raise ValidationFailure("Goku asset manifest assets are missing")
        manifest_by_path = {str(x.get("path")): x for x in rows if isinstance(x, dict)}
        if len(manifest_by_path) != len(image_assets): raise ValidationFailure("Goku asset manifest count disagrees with HF tree")
        for item in image_assets:
            cached = manifest_by_path.get(item["path"])
            expected_label = "candidate_reference" if item["path"] in referred else "out_of_scope_model_reference" if item["path"] in all_referenced else "global_orphan"
            if not cached or cached.get("lfs_oid") != item["lfs_oid"] or cached.get("byte_size") != item["byte_size"] or cached.get("classification") != expected_label:
                raise ValidationFailure("Goku asset manifest disagrees with recomputed HF tree/reference classification")
    return {"raw_case_ledger": raw_cases, "case_ledger": filtered, "asset_ledger": image_assets, "orphan_ledger": classifications["global_orphan"], "asset_classifications": classifications, "exclusion_ledger": sorted(exclusions, key=lambda x: (x["case_id"], x["reason"])), "metadata_lfs_oid": GOKU_METADATA_LFS_OID, "metadata_sha256": _sha_file(metadata)}

def _parse_chaos(snapshot: Path, *, current: Mapping[str, set[str]] | None = None) -> dict[str, Any]:
    index = _load(snapshot / "works" / "index.json")
    rows = index.get("images") if isinstance(index, dict) else None
    if not isinstance(rows, list): raise ValidationFailure("Chaos works/index.json.images is missing")
    raw_cases, exclusions, referenced = [], [], set()
    for item in rows:
        if not isinstance(item, dict): raise ValidationFailure("Chaos index image is not an object")
        meta_path = _safe_rel(item.get("meta_path"), "Chaos meta_path")
        meta = _load(snapshot / meta_path)
        deps = meta.get("generation", {}).get("depends_on", [])
        refs = meta.get("refs", []) or meta.get("generation", {}).get("ref_urls", [])
        prompt = meta.get("prompt") if isinstance(meta.get("prompt"), str) else ""
        folder = Path(meta_path).parent.as_posix()
        expected = [f"{folder}/image.w{width}.webp" for width in (400, 1600, 2400)]
        referenced.update(expected)
        facts = []
        try:
            for output in expected:
                fact = _fixed_asset(snapshot, output); fact["authority"] = "fixed_local"; facts.append(fact)
        except ValidationFailure:
            facts = []
        if deps or refs:
            if prompt:
                raw_cases.append(_case(str(item.get("id")), str(item.get("id")), str(item.get("topic_slug", "uncategorized")), prompt, f"https://github.com/ChaosRealmsAI/gpt-image-2-gallery/blob/{SOURCE_SPECS['chaosrealmsai-gpt-image-2-gallery']['revision']}/{meta_path}", meta_path, facts, risk_text=_metadata_text(meta)))
            else:
                raw_cases.append(_terminal_case(str(item.get("id")), str(item.get("topic_slug", "uncategorized")), meta_path, f"https://github.com/ChaosRealmsAI/gpt-image-2-gallery/blob/{SOURCE_SPECS['chaosrealmsai-gpt-image-2-gallery']['revision']}/{meta_path}", "missing_prompt"))
                raw_cases[-1]["outputs"] = facts
                raw_cases[-1]["strong_pairing"] = bool(facts)
            raw_cases[-1]["reference_dependency"] = True
            continue
        if not prompt:
            raw_cases.append(_terminal_case(str(item.get("id")), str(item.get("topic_slug", "uncategorized")), meta_path, f"https://github.com/ChaosRealmsAI/gpt-image-2-gallery/blob/{SOURCE_SPECS['chaosrealmsai-gpt-image-2-gallery']['revision']}/{meta_path}", "missing_prompt")); raw_cases[-1]["outputs"] = facts; raw_cases[-1]["strong_pairing"] = bool(facts); continue
        if not facts:
            raw_cases.append(_case(str(item.get("id")), str(item.get("id")), str(item.get("topic_slug", "uncategorized")), prompt, f"https://github.com/ChaosRealmsAI/gpt-image-2-gallery/blob/{SOURCE_SPECS['chaosrealmsai-gpt-image-2-gallery']['revision']}/{meta_path}", meta_path, [], risk_text=_metadata_text(meta))); raw_cases[-1]["terminal_reason"] = "missing_asset"; continue
        referenced.update(x["path"] for x in facts)
        case = _case(str(item.get("id")), str(item.get("id")), str(item.get("topic_slug", "uncategorized")), meta["prompt"], f"https://github.com/ChaosRealmsAI/gpt-image-2-gallery/blob/{SOURCE_SPECS['chaosrealmsai-gpt-image-2-gallery']['revision']}/{meta_path}", meta_path, facts, risk_text=_metadata_text(meta))
        case["reference_dependency"] = False
        raw_cases.append(case)
    all_assets = []
    for path in sorted(snapshot.rglob("*.webp")):
        all_assets.append(_fixed_asset(snapshot, path.relative_to(snapshot).as_posix()))
    current = current or {"prompt": set(), "source_url": set(), "image": set()}
    filtered, hard_exclusions = _reasoned_filter(raw_cases, family_hashes=set(), current=current)
    exclusions.extend(hard_exclusions)
    return {"raw_case_ledger": sorted(raw_cases, key=lambda x: x["case_id"]), "case_ledger": filtered, "asset_ledger": all_assets, "orphan_ledger": sorted(x["path"] for x in all_assets if x["path"] not in referenced), "exclusion_ledger": sorted(exclusions, key=lambda x: (x.get("case_id", x.get("record_id", "")), x["reason"]))}

def _parse_youmind(snapshot: Path) -> dict[str, Any]:
    manifest = _load(snapshot / "references" / "manifest.json")
    categories = manifest.get("categories") if isinstance(manifest, dict) else None
    if not isinstance(categories, list): raise ValidationFailure("YouMind manifest categories are missing")
    records, hashes, references, all_media = [], set(), 0, []
    for category in categories:
        if not isinstance(category, dict): raise ValidationFailure("YouMind category is invalid")
        category_file = _safe_rel(category.get("file"), "YouMind category file")
        category_slug = str(category.get("slug", Path(category_file).stem))
        data = _load(snapshot / "references" / category_file)
        if not isinstance(data, list): raise ValidationFailure("YouMind category payload is not an array")
        for row_index, row in enumerate(data):
            if not isinstance(row, dict) or not isinstance(row.get("id"), int) or not isinstance(row.get("content"), str): raise ValidationFailure("YouMind record is invalid")
            media = row.get("sourceMedia")
            if not isinstance(media, list) or any(not isinstance(value, str) or not value.startswith("https://cms-assets.youmind.com/") for value in media): raise ValidationFailure("YouMind sourceMedia is not a fixed-revision CMS HTTPS observation")
            digest = hashlib.sha256(_normalize_prompt(row["content"]).encode()).hexdigest()
            author_exposed = any(bool(row.get(key)) for key in ("author", "creator", "sourceAuthor", "user", "handle"))
            original_post_exposed = any(bool(row.get(key)) for key in ("sourceLink", "sourceUrl", "originalUrl", "tweetUrl", "postUrl"))
            records.append({"category": category_slug, "category_file": category_file, "row_index": row_index, "id": row["id"], "prompt_sha256": digest, "need_reference_images": bool(row.get("needReferenceImages")), "source_media": media, "author_attribution_exposed": author_exposed, "original_post_exposed": original_post_exposed})
            hashes.add(digest); references += bool(row.get("needReferenceImages")); all_media.extend(media)
    records.sort(key=lambda x: (x["id"], x["category"], x["row_index"]))
    return {"total": len(records), "unique_ids": len({r["id"] for r in records}), "unique_prompt_hashes": len(hashes), "need_reference_images": references, "rows_with_source_media": sum(bool(r["source_media"]) for r in records), "source_media_reference_count": len(all_media), "unique_source_media_urls": len(set(all_media)), "cms_https_reference_count": sum(value.startswith("https://cms-assets.youmind.com/") for value in all_media), "author_attribution_rows": sum(r["author_attribution_exposed"] for r in records), "original_post_rows": sum(r["original_post_exposed"] for r in records), "remote_asset_authority": "observation_only", "source_media_urls_sha256": _hash_lines(sorted(all_media)), "records": records}

def _parse_tigerowo(snapshot: Path) -> dict[str, Any]:
    data = _load(snapshot / "data" / "ingested_tweets.json")
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list): raise ValidationFailure("tigerowo records are missing")
    bad = {"missing_tweet_url": 0, "missing_image_dir": 0, "missing_case_anchor": 0, "missing_category": 0}
    for row in records:
        if not isinstance(row, dict): raise ValidationFailure("tigerowo record is invalid")
        for field, key in (("tweet_url", "missing_tweet_url"), ("image_dir", "missing_image_dir"), ("case_anchor", "missing_case_anchor"), ("category", "missing_category")):
            bad[key] += not bool(row.get(field))
    audit = _load(REPO_ROOT / "reports" / "source-audit-v1.json")
    audit_rows = audit.get("records") if isinstance(audit, dict) else None
    matched = next((row for row in audit_rows or [] if isinstance(row, dict) and row.get("source_id") == "tigerowo-awesome-gpt-image-2-prompts"), None)
    if not matched or matched.get("audit_scope") != "family_mapping" or matched.get("recommended_status") != "blocked": raise ValidationFailure("source-audit v1 family mapping blocked record is missing")
    images = [p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    readme = (snapshot / "README.md").read_text(encoding="utf-8")
    folded = readme.casefold()
    backup_claim = "evolinkai" in folded and ("backup" in folded or "备份" in readme)
    return {"record_count": len(records), "image_count": len(images), "missing_fields": bad, "readme_backup_claim": backup_claim, "family_mapping": "blocked"}

def _parse_source(source_id: str, snapshot: Path) -> dict[str, Any]:
    return {"goku-openlab-gpt-image-2-prompts-datasets": _parse_goku, "chaosrealmsai-gpt-image-2-gallery": _parse_chaos, "youmind-openlab-gpt-image-2-prompts-search": _parse_youmind, "tigerowo-awesome-gpt-image-2-prompts": _parse_tigerowo}[source_id](snapshot)

def _fixed_core(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(payload))
    value.pop("generated_at", None)
    value.pop("canonical_digest", None)
    return value

def _current_baseline(*, rebuild: bool = False) -> tuple[dict[str, Any], dict[str, set[str]]]:
    current = v2._current_index(rebuild=rebuild)
    v2_report = _load(REPO_ROOT / "reports" / "phase2" / "source-expansion-admission-v2.json")
    authority = v2_report.get("authority", {})
    asset_hashes = {str(item.get("content_sha256")) for item in current.get("assets", {}).values() if isinstance(item, Mapping) and item.get("content_sha256")}
    if (authority.get("active_source_count"), current.get("case_count"), current.get("output_count"), len(asset_hashes), authority.get("current_source_file_count"), authority.get("current_public_cases"), v2_report.get("adapter_ready_batch")) != (6, 1513, 1930, 1885, 2260, 0, []):
        raise ValidationFailure("current baseline or v2 empty batch drifted")
    core = {"cases": current["cases"], "assets": current["assets"]}
    protected_paths = ("config/sources-v1.yaml", "reports/source-audit-v1.json", "reports/phase2/source-expansion-admission-v2.json", "reports/phase2/source-expansion-admission-v2.md", "schemas/phase2-source-expansion-admission-v2.schema.json", "scripts/validate_phase2_source_expansion_admission.py", "tests/phase2/test_source_expansion_admission.py", "docs/phase2/source-expansion-admission-v2.md")
    protected = {name: _sha_file(REPO_ROOT / name) for name in protected_paths}
    return {"active_source_count": 6, "current_case_count": 1513, "current_output_count": 1930, "current_deduplicated_asset_object_count": 1885, "current_source_file_count": 2260, "current_public_cases": 0, "current_index_core_sha256": _digest(core), "protected_prompt_hashes_sha256": _hash_lines(sorted(_current_exact_sets(current)["prompt"])), "v2_admission_sha256": protected["reports/phase2/source-expansion-admission-v2.json"], "protected_files": protected}, _current_exact_sets(current)

def _review_asset_checks(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted(({"path": str(output["path"]), "byte_size": int(output["byte_size"]), "sha256": str(output.get("sha256") or output.get("lfs_oid")), "decoded": True} for output in case.get("outputs", [])), key=lambda item: item["path"])


def _normalized_asset_checks(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return sorted(({"path": str(check.get("path")), "byte_size": check.get("byte_size"), "sha256": str(check.get("sha256")), "decoded": check.get("decoded")} for check in value if isinstance(check, Mapping)), key=lambda check: check["path"])


def _verified_sample_manifest(snapshot_root: Path, reviews: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    declared = []
    for source_id in ("goku-openlab-gpt-image-2-prompts-datasets", "chaosrealmsai-gpt-image-2-gallery"):
        source_reviews = reviews.get(source_id, {})
        if isinstance(source_reviews, Mapping) and isinstance(source_reviews.get("_sample_manifest_sha256"), str):
            declared.append(str(source_reviews["_sample_manifest_sha256"]))
    if not declared:
        return None
    if len(set(declared)) != 1 or re.fullmatch(r"[0-9a-f]{64}", declared[0]) is None:
        raise ValidationFailure("quality reviews disagree on sample manifest authority")
    path = snapshot_root / "samples-final-v3" / "sample-manifest.json"
    manifest = _load(path)
    items = manifest.get("items") if isinstance(manifest, Mapping) else None
    if manifest.get("schema_version") != 1 or manifest.get("revision") != SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]["revision"] or not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
        raise ValidationFailure("quality sample manifest items are invalid")
    digest = hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if manifest.get("manifest_sha256") != digest or declared[0] != digest or manifest.get("item_count") != len(items):
        raise ValidationFailure("quality sample manifest digest/count authority drift")
    expected_assets = 0
    seen: set[tuple[str, str, str, str]] = set()
    root = snapshot_root.resolve()
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationFailure("Pillow is required to verify decoded quality evidence") from exc
    for item in items:
        raw_source_id, raw_kind, raw_case_id, raw_reason = item.get("source_id"), item.get("kind"), item.get("case_id"), item.get("reason", "")
        if not isinstance(raw_source_id, str) or not isinstance(raw_kind, str) or not isinstance(raw_case_id, str) or not raw_case_id or not isinstance(raw_reason, str):
            raise ValidationFailure("quality sample manifest identity is invalid")
        source_id, kind, case_id, reason = raw_source_id, raw_kind, raw_case_id, raw_reason
        if source_id not in {"goku-openlab-gpt-image-2-prompts-datasets", "chaosrealmsai-gpt-image-2-gallery"} or kind not in {"admission", "exclusion"}:
            raise ValidationFailure("quality sample manifest identity is invalid")
        key = (source_id, kind, case_id, reason if kind == "exclusion" else "")
        if key in seen: raise ValidationFailure("quality sample manifest item is duplicated")
        seen.add(key)
        checks = item.get("asset_checks")
        if not isinstance(checks, list): raise ValidationFailure("quality sample asset checks are missing")
        expected_assets += len(checks)
        for check in checks:
            if not isinstance(check, Mapping) or check.get("decoded") is not True or not isinstance(check.get("local_path"), str): raise ValidationFailure("quality sample asset check is invalid")
            local = Path(str(check["local_path"])).resolve()
            if not local.is_relative_to(root) or not local.is_file(): raise ValidationFailure("quality sample asset left canonical runtime root or is missing")
            data = local.read_bytes()
            if len(data) != check.get("byte_size") or hashlib.sha256(data).hexdigest() != check.get("sha256"): raise ValidationFailure("quality sample asset authority mismatch")
            try:
                with Image.open(local) as image: image.verify()
            except Exception as exc:
                raise ValidationFailure("quality sample asset no longer decodes") from exc
    if manifest.get("decoded_asset_count") != expected_assets:
        raise ValidationFailure("quality sample decoded asset count drift")
    return [dict(item) for item in items]


def _quality(cases: list[dict[str, Any]], reviews: Mapping[str, Any], exclusions: list[dict[str, Any]], raw_cases: list[dict[str, Any]] | None = None, sample_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    size = v2._expected_sample_size(len(cases))
    ids = _select_quality_sample(cases, size)
    rows = {str(key): value for key, value in reviews.items() if isinstance(value, Mapping)}
    missing = [case_id for case_id in ids if case_id not in rows]
    manifest_sha256 = reviews.get("_sample_manifest_sha256")
    passed = not missing and isinstance(manifest_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is not None
    cases_by_id = {str(case["case_id"]): case for case in cases}
    result_rows = []
    manifest_admission = {str(item.get("case_id")): _normalized_asset_checks(item.get("asset_checks")) for item in (sample_items or []) if item.get("kind") == "admission"}
    for case_id in ids:
        item = dict(rows.get(case_id, {})); item["case_id"] = case_id
        observed_checks = _normalized_asset_checks(item.get("asset_checks"))
        expected_checks = _review_asset_checks(cases_by_id[case_id])
        manifest_checks = manifest_admission.get(case_id, expected_checks if sample_items is None else None)
        okay = item.get("result") == "pass" and item.get("prompt_complete") is True and item.get("image_readable") is True and item.get("semantic_match") is True and item.get("visual_quality") in {"high", "acceptable"} and observed_checks == expected_checks and manifest_checks == expected_checks
        passed &= okay; result_rows.append(item)
    reason_ids: dict[str, list[str]] = {}
    for item in exclusions: reason_ids.setdefault(str(item["reason"]), []).append(str(item["case_id"]))
    exclusion_sample = {reason: sorted(values, key=lambda x: hashlib.sha256(x.encode()).hexdigest())[0] for reason, values in sorted(reason_ids.items())}
    exclusion_input = reviews.get("_exclusions", {})
    exclusion_reviews, missing_exclusion = [], []
    if not isinstance(exclusion_input, Mapping): exclusion_input = {}
    raw_by_id = {str(case["case_id"]): case for case in (raw_cases or cases)}
    manifest_exclusion = {(str(item.get("reason")), str(item.get("case_id"))): _normalized_asset_checks(item.get("asset_checks")) for item in (sample_items or []) if item.get("kind") == "exclusion"}
    if sample_items is not None:
        passed &= set(manifest_admission) == set(ids)
        passed &= set(manifest_exclusion) == {(reason, case_id) for reason, case_id in exclusion_sample.items()}
    for reason, case_id in exclusion_sample.items():
        review = exclusion_input.get(reason)
        observed_checks = _normalized_asset_checks(review.get("asset_checks")) if isinstance(review, Mapping) else []
        expected_checks = _review_asset_checks(raw_by_id.get(case_id, {}))
        manifest_checks = manifest_exclusion.get((reason, case_id), expected_checks if sample_items is None else None)
        if not isinstance(review, Mapping) or review.get("case_id") != case_id or review.get("result") != "confirmed" or review.get("reason_confirmed") is not True or observed_checks != expected_checks or manifest_checks != expected_checks:
            missing_exclusion.append({"reason": reason, "case_id": case_id})
        else: exclusion_reviews.append(dict(review))
    passed = passed and not missing_exclusion
    return {"result": "pass" if passed else "fail", "sample_manifest_sha256": manifest_sha256, "sample_size": size, "sample_ids": ids, "sample_ids_sha256": _hash_lines(ids), "reviews": result_rows, "missing_review_ids": missing, "exclusion_sample_ids": exclusion_sample, "exclusion_reviews": exclusion_reviews, "missing_exclusion_reviews": missing_exclusion, "exclusion_reviews_sha256": _digest(exclusion_reviews), "selection_method": "v2 deterministic category/risk/overlap/length selection", "coverage": {"source_categories": sorted({x["category"] for x in cases}), "sampled_categories": sorted({x["category"] for x in cases if x["case_id"] in ids}), "source_risk_flags": sorted({r for x in cases for r in x["risk_flags"]}), "sampled_risk_flags": sorted({r for x in cases if x["case_id"] in ids for r in x["risk_flags"]})}}

def _metrics(parsed: Mapping[str, Any], quality: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw, kept, assets, exclusions = parsed.get("raw_case_ledger", []), parsed.get("case_ledger", []), parsed.get("asset_ledger", []), parsed.get("exclusion_ledger", [])
    excluded_by_reason = {reason: {str(item["case_id"]) for item in exclusions if item["reason"] == reason} for reason in {str(item["reason"]) for item in exclusions}}
    raw_by_id = {str(item["case_id"]): item for item in raw}
    parseable_ids = {case_id for case_id, item in raw_by_id.items() if item.get("prompt_sha256")}
    paired_ids = {case_id for case_id in parseable_ids if raw_by_id[case_id].get("outputs")}
    authority_ids = {case_id for case_id in paired_ids if raw_by_id[case_id].get("source_url_key")}
    risk_ids = {case_id for reason, case_ids in excluded_by_reason.items() if reason.startswith("risk:") for case_id in case_ids}
    safety_ids = authority_ids - risk_ids
    within_source_ids = safety_ids - excluded_by_reason.get("within_source_duplicate", set())
    within_family_ids = within_source_ids - excluded_by_reason.get("youmind_family_duplicate", set())
    current_ids = within_family_ids - excluded_by_reason.get("current_exact_duplicate", set())
    kept_ids = {str(item["case_id"]) for item in kept}
    if current_ids != kept_ids: raise ValidationFailure("waterfall stages do not reconcile with filtered case ledger")
    stages = {"raw": len(raw_by_id), "parseable": len(parseable_ids), "authority_valid": len(authority_ids), "safety_eligible": len(safety_ids), "within_source_unique": len(within_source_ids), "within_family_unique": len(within_family_ids), "current_exact_new": len(current_ids), "quality_valid": len(kept_ids) if quality and quality.get("result") == "pass" else 0}
    reason_counts = {reason: sum(1 for value in exclusions if value["reason"] == reason) for reason in sorted({item["reason"] for item in exclusions})}
    broken_ids = excluded_by_reason.get("missing_asset", set()) | excluded_by_reason.get("missing_lfs_object", set())
    return {"stages": stages, "pair_rate": len(paired_ids) / max(1, len(parseable_ids)), "broken_authoritative_asset_count": len(broken_ids), "broken_authoritative_asset_rate": len(broken_ids) / max(1, len(parseable_ids)), "within_source_duplicate_rate": len(excluded_by_reason.get("within_source_duplicate", set())) / max(1, len(safety_ids)), "exclusion_reason_counts": reason_counts, "raw_case_count": len(raw_by_id), "filtered_case_count": len(kept_ids), "asset_count": len(assets), "orphan_asset_count": len(parsed.get("orphan_ledger", [])), "excluded_case_count": len(set().union(*excluded_by_reason.values())) if excluded_by_reason else 0, "exclusion_count": len(exclusions), "case_ledger_sha256": _digest(kept), "asset_ledger_sha256": _digest(assets), "orphan_ledger_sha256": _digest(parsed.get("orphan_ledger", [])), "exclusion_ledger_sha256": _digest(exclusions), "lint_version": V3_LINT_VERSION}

def _maintenance(snapshot: Path, source_id: str, parsed: Mapping[str, Any], authority: Mapping[str, Any]) -> dict[str, Any]:
    if source_id == "chaosrealmsai-gpt-image-2-gallery":
        exclusions = parsed.get("exclusion_ledger", [])
        missing = {str(item.get("case_id")) for item in exclusions if item.get("reason") == "missing_asset"}
        complete = authority.get("revision") == SOURCE_SPECS[source_id]["revision"] and len(parsed.get("raw_case_ledger", [])) == 3798 and len(parsed.get("asset_ledger", [])) == 11559 and len(parsed.get("orphan_ledger", [])) == 168 and len(missing) == 1 and len({x.get("case_id") for x in parsed.get("raw_case_ledger", [])}) == 3798
        return {"kind": "fixed_history", "fixed_snapshot_complete": complete, "sync_eligible": False, "one_shot_import_only": True, "raw_case_count": len(parsed.get("raw_case_ledger", [])), "asset_count": len(parsed.get("asset_ledger", [])), "orphan_count": len(parsed.get("orphan_ledger", [])), "missing_asset_case_count": len(missing), "authority_tree_manifest_sha256": authority.get("tree_manifest_sha256")}
    path = snapshot / "content-history.json"
    if not path.is_file(): return {"kind": "continuous", "continuous_eligible": False, "sync_eligible": False, "reason": "fixed content history evidence unavailable"}
    history = _load(path); dates = history.get("substantive_dates") if isinstance(history, dict) else None; snapshots = history.get("snapshots") if isinstance(history, dict) else None
    if not isinstance(dates, list) or not isinstance(snapshots, list) or not snapshots: raise ValidationFailure("Goku content history evidence is invalid")
    latest = snapshots[-1]
    expected = {key: authority.get(key) for key in ("revision", "file_count", "image_count", "lfs_count", "metadata_oid", "metadata_size", "tree_manifest_sha256")}
    if not isinstance(latest, Mapping) or any(latest.get(key) != value for key, value in expected.items()): raise ValidationFailure("Goku content history latest snapshot differs from fixed authority")
    parsed_dates = sorted({dt.date.fromisoformat(str(value)) for value in dates})
    today = dt.date.today(); recent = [value for value in parsed_dates if value >= today - dt.timedelta(days=365)]
    latest_date = max(parsed_dates) if parsed_dates else None
    eligible = bool(latest_date and (today - latest_date).days <= 180 and len(recent) >= 2)
    return {"kind": "continuous", "substantive_dates": [value.isoformat() for value in parsed_dates], "snapshots": snapshots, "history_sha256": _digest(snapshots), "continuous_eligible": eligible, "sync_eligible": eligible, "timestamp_only_refreshes_excluded": True}

def _eligible(evidence: Mapping[str, Any], source_id: str) -> bool:
    metrics, maintenance = evidence.get("metrics", {}), evidence.get("maintenance", {})
    stages = metrics.get("stages", {}) if isinstance(metrics, Mapping) else {}
    pair_rate = metrics.get("pair_rate", 0) if isinstance(metrics, Mapping) else 0
    base = len(evidence.get("case_ledger", [])) >= 50 and evidence.get("quality", {}).get("result") == "pass" and pair_rate >= .90 and metrics.get("broken_authoritative_asset_rate", 1) <= .05 and metrics.get("within_source_duplicate_rate", 1) <= .20 and stages.get("current_exact_new", 0) > 0
    if source_id == "goku-openlab-gpt-image-2-prompts-datasets":
        return base and maintenance.get("continuous_eligible") is True and maintenance.get("sync_eligible") is True
    return base and maintenance.get("fixed_snapshot_complete") is True and maintenance.get("sync_eligible") is False and maintenance.get("one_shot_import_only") is True

def _semantic_validate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION: raise ValidationFailure("wrong schema version")
    expected_authority, _ = _current_baseline(rebuild=False)
    if payload.get("authority") != expected_authority: raise ValidationFailure("current baseline or protected hashes differ from authority")
    sources = payload.get("sources")
    if not isinstance(sources, list) or len(sources) != 4: raise ValidationFailure("requires exactly four roles")
    found = {row.get("source_id"): row for row in sources if isinstance(row, dict)}
    if set(found) != set(SOURCE_SPECS): raise ValidationFailure("source IDs must exactly match v3 four-role contract")
    for source_id, spec in SOURCE_SPECS.items():
        row = found[source_id]
        for key in ("revision", "role", "mode"):
            if row.get(key) != spec[key]: raise ValidationFailure(f"{source_id} wrong {key}")
        identity, lineage = row.get("identity", {}), row.get("lineage", {})
        if identity.get("canonical_url") != spec["url"] or identity.get("provider_id") != spec["provider_id"] or identity.get("default_branch") != spec["branch"] or identity.get("fixed_revision") != spec["revision"] or lineage.get("family_role") != spec["family_role"]: raise ValidationFailure(f"{source_id} identity or family contract drift")
        rights = row.get("rights", {})
        if rights.get("prompt_policy") != "review_required" or rights.get("asset_policy") != "review_required" or rights.get("auto_publish") is not False: raise ValidationFailure("rights/publication must remain review_required and non-publishing")
        if row.get("fixed_core_digest") != _digest({k: v for k, v in row.items() if k != "fixed_core_digest"}): raise ValidationFailure(f"{source_id} fixed-core digest mismatch")
        if spec["role"] == "full":
            evidence = row.get("evidence", {})
            for key in ("raw_case_ledger", "case_ledger", "asset_ledger", "orphan_ledger", "exclusion_ledger", "quality", "metrics", "authority", "maintenance"):
                if key not in evidence: raise ValidationFailure(f"{source_id} lacks full ledger evidence: {key}")
            authority = evidence["authority"]
            if source_id.startswith("goku-"):
                required = {"kind": "hf", "repository": "Goku-OpenLab/gpt-image-2-prompts-datasets", "revision": spec["revision"], "file_count": spec["entry_count"], "image_count": 28293, "lfs_count": 28294, "metadata_oid": GOKU_METADATA_LFS_OID, "metadata_size": GOKU_METADATA_BYTE_SIZE, "tree_manifest_sha256": spec["tree_manifest_sha256"]}
            else:
                required = {"kind": "git", "revision": spec["revision"], "remote_url": spec["url"], "entry_count": spec["entry_count"], "blob_count": spec["entry_count"], "tree_manifest_sha256": spec["tree_manifest_sha256"]}
            if not isinstance(authority, Mapping) or any(authority.get(key) != value for key, value in required.items()) or not isinstance(authority.get("tree_manifest_sha256"), str) or len(authority["tree_manifest_sha256"]) != 64: raise ValidationFailure(f"{source_id} authority invariant drift")
            maintenance = evidence["maintenance"]
            if source_id.startswith("goku-"):
                snapshots = maintenance.get("snapshots") if isinstance(maintenance, Mapping) else None
                if not isinstance(snapshots, list) or not snapshots or snapshots[-1].get("tree_manifest_sha256") != authority.get("tree_manifest_sha256") or snapshots[-1].get("revision") != spec["revision"]: raise ValidationFailure("Goku maintenance/history authority drift")
            elif not isinstance(maintenance, Mapping) or maintenance.get("authority_tree_manifest_sha256") != authority.get("tree_manifest_sha256") or maintenance.get("sync_eligible") is not False or maintenance.get("one_shot_import_only") is not True: raise ValidationFailure("Chaos fixed-history maintenance drift")
            if evidence["quality"].get("result") == "pass" and not evidence["quality"].get("sample_ids"):
                raise ValidationFailure(f"{source_id} quality closure is empty")
            expected_status = spec["status"] if _eligible(evidence, source_id) else "blocked"
            if row.get("status") != expected_status: raise ValidationFailure(f"{source_id} status does not follow waterfall")
        else:
            if row.get("status") != spec["status"]: raise ValidationFailure(f"{source_id} control status drift")
            container = row.get("evidence", {}).get("comparator_ledger" if spec["role"] == "comparator" else "control_record", {})
            source_authority = container.get("authority") if isinstance(container, Mapping) else None
            required = {"kind": "git", "revision": spec["revision"], "remote_url": spec["url"], "entry_count": spec["entry_count"], "blob_count": spec["entry_count"], "tree_manifest_sha256": spec["tree_manifest_sha256"]}
            if not isinstance(source_authority, Mapping) or any(source_authority.get(key) != value for key, value in required.items()) or not isinstance(source_authority.get("tree_manifest_sha256"), str) or len(source_authority["tree_manifest_sha256"]) != 64: raise ValidationFailure(f"{source_id} control authority drift")
            if spec["role"] == "comparator":
                records = container.get("records") if isinstance(container, Mapping) else None
                if not isinstance(records, list) or any(not isinstance(item, Mapping) for item in records): raise ValidationFailure("YouMind comparator records are invalid")
                media = [str(value) for record in records for value in record.get("source_media", [])]
                computed = {"total": len(records), "unique_ids": len({record.get("id") for record in records}), "unique_prompt_hashes": len({record.get("prompt_sha256") for record in records}), "need_reference_images": sum(record.get("need_reference_images") is True for record in records), "rows_with_source_media": sum(bool(record.get("source_media")) for record in records), "source_media_reference_count": len(media), "unique_source_media_urls": len(set(media)), "cms_https_reference_count": sum(value.startswith("https://cms-assets.youmind.com/") for value in media), "author_attribution_rows": sum(record.get("author_attribution_exposed") is True for record in records), "original_post_rows": sum(record.get("original_post_exposed") is True for record in records), "source_media_urls_sha256": _hash_lines(sorted(media))}
                if any(container.get(key) != value for key, value in computed.items()) or container.get("remote_asset_authority") != "observation_only": raise ValidationFailure("YouMind comparator media/attribution summary drift")
                goku_hashes = {item.get("prompt_sha256") for item in found["goku-openlab-gpt-image-2-prompts-datasets"]["evidence"]["raw_case_ledger"] if item.get("prompt_sha256")}
                expected_overlap = sorted(goku_hashes & {record.get("prompt_sha256") for record in records})
                if container.get("goku_prompt_overlap_hashes") != expected_overlap: raise ValidationFailure("Goku/YouMind family overlap drift")
                comparator_core = {key: value for key, value in container.items() if key != "digest"}
                if container.get("digest") != _digest(comparator_core): raise ValidationFailure("YouMind comparator digest mismatch")
            elif container.get("readme_backup_claim") is not True:
                raise ValidationFailure("tigerowo EvoLink backup lineage claim drift")
    batch = payload.get("adapter_ready_batch", [])
    allowed = {"goku-openlab-gpt-image-2-prompts-datasets": "continuous", "chaosrealmsai-gpt-image-2-gallery": "fixed_history"}
    if not isinstance(batch, list) or len({x.get("source_id") for x in batch if isinstance(x, dict)}) != len(batch): raise ValidationFailure("batch duplicate or malformed")
    for item in batch:
        if not isinstance(item, dict) or item.get("source_id") not in allowed or item.get("mode") != allowed[item["source_id"]] or item.get("revision") != SOURCE_SPECS[item["source_id"]]["revision"]: raise ValidationFailure("control/comparator role escalation or wrong adapter mode")
        source = found[item["source_id"]]; evidence = source["evidence"]
        if item.get("case_scope") != {"case_count": len(evidence.get("case_ledger", [])), "case_ledger_sha256": evidence.get("metrics", {}).get("case_ledger_sha256")} or item.get("structure_strategy") != source["structure"]["strategy"] or item.get("family_role") != source["lineage"]["family_role"] or item.get("exclusions") != evidence.get("exclusion_ledger", []): raise ValidationFailure("batch scope/strategy/family/exclusions drift")
    if payload.get("canonical_digest") != _digest(_fixed_core(payload)): raise ValidationFailure("canonical digest mismatch")
    eligible = [source_id for source_id in allowed if found[source_id].get("status") in {"continuous_ready", "fixed_history_ready"}]
    if [item["source_id"] for item in batch] != eligible: raise ValidationFailure("batch must exactly equal eligible full-source waterfall")
    return {"source_count": 4, "adapter_ready_count": len(batch), "adapter_ready_sources": [x["source_id"] for x in batch]}

def validate(audit_path: Path, schema_path: Path, *, determinism_check: bool = False, live: bool = False, quality_review: Path | None = None) -> dict[str, Any]:
    payload, schema = _load(audit_path), _load(schema_path)
    issues = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload))
    if issues: raise ValidationFailure("Schema validation failed: " + issues[0].message)
    summary = _semantic_validate(payload)
    if determinism_check and _semantic_validate(json.loads(json.dumps(payload))) != summary: raise ValidationFailure("determinism check changed semantic result")
    if live:
        if quality_review is None: raise ValidationFailure("--live requires --quality-review to rebuild fixed inputs")
        rebuilt = build_report(RUNTIME_ROOT, quality_review=quality_review, rebuild_current=True)
        if _fixed_core(rebuilt) != _fixed_core(payload): raise ValidationFailure("live fixed inputs differ from checked-in fixed core")
    return {"status": "passed", "canonical_digest": payload["canonical_digest"], "summary": summary}

def _source_row(source_id: str, evidence: dict[str, Any], *, status: str | None = None) -> dict[str, Any]:
    spec = SOURCE_SPECS[source_id]
    if spec["role"] == "comparator":
        evidence = {"case_ledger": [], "asset_ledger": [], "orphan_ledger": [], "exclusion_ledger": [], "comparator_ledger": evidence}
    elif spec["role"] == "excluded_control":
        evidence = {"case_ledger": [], "asset_ledger": [], "orphan_ledger": [], "exclusion_ledger": [], "control_record": evidence}
    row = {"source_id": source_id, "role": spec["role"], "revision": spec["revision"], "mode": spec["mode"], "status": status or spec["status"], "identity": {"canonical_url": spec["url"], "provider_id": spec["provider_id"], "default_branch": spec["branch"], "fixed_revision": spec["revision"]}, "lineage": {"family_id": "family-gpt-image-2-openlab" if source_id.startswith(("goku-", "youmind-")) else f"family-{source_id}", "canonical_source_id": "goku-openlab-gpt-image-2-prompts-datasets" if source_id.startswith(("goku-", "youmind-")) else source_id, "family_role": spec["family_role"]}, "structure": {"strategy": spec["strategy"]}, "rights": {"prompt_policy": "review_required", "asset_policy": "review_required", "auto_publish": False}, "evidence": evidence}
    row["fixed_core_digest"] = _digest(row); return row

def build_report(snapshot_root: Path = RUNTIME_ROOT, *, quality_review: Path | None = None, rebuild_current: bool = False) -> dict[str, Any]:
    if quality_review is None: raise ValidationFailure("--build requires --quality-review")
    reviews = _load(quality_review)
    if not isinstance(reviews, dict): raise ValidationFailure("quality review must be an object")
    sample_items = _verified_sample_manifest(snapshot_root, reviews)
    authority, current = _current_baseline(rebuild=rebuild_current)
    youmind = _parse_youmind(snapshot_root / "youmind")
    family_hashes = {x["prompt_sha256"] for x in youmind["records"]}
    goku = _parse_goku(snapshot_root / "goku", family_hashes=family_hashes, current=current)
    chaos = _parse_chaos(snapshot_root / "chaos", current=current)
    for source_id, parsed in (("goku-openlab-gpt-image-2-prompts-datasets", goku), ("chaosrealmsai-gpt-image-2-gallery", chaos)):
        source_reviews = reviews.get(source_id, {})
        if not isinstance(source_reviews, Mapping): raise ValidationFailure(f"{source_id} quality review is invalid")
        source_sample_items = [item for item in sample_items or [] if item.get("source_id") == source_id] if sample_items is not None else None
        parsed["quality"] = _quality(parsed["case_ledger"], source_reviews, parsed["exclusion_ledger"], parsed["raw_case_ledger"], source_sample_items); parsed["metrics"] = _metrics(parsed, parsed["quality"])
        parsed["authority"] = _goku_authority(snapshot_root / "goku") if source_id.startswith("goku-") else _git_authority(snapshot_root / "chaos", source_id)
        parsed["maintenance"] = _maintenance(snapshot_root / SOURCE_SPECS[source_id]["folder"], source_id, parsed, parsed["authority"])
        parsed["contribution"] = _contribution(parsed["case_ledger"], current)
    youmind["goku_prompt_overlap_hashes"] = sorted(family_hashes & {x["prompt_sha256"] for x in goku["raw_case_ledger"]})
    youmind["authority"] = _git_authority(snapshot_root / "youmind", "youmind-openlab-gpt-image-2-prompts-search")
    youmind["digest"] = _digest(youmind)
    tiger = _parse_tigerowo(snapshot_root / "tigerowo")
    tiger["authority"] = _git_authority(snapshot_root / "tigerowo", "tigerowo-awesome-gpt-image-2-prompts")
    candidates = {"goku-openlab-gpt-image-2-prompts-datasets": goku, "chaosrealmsai-gpt-image-2-gallery": chaos, "youmind-openlab-gpt-image-2-prompts-search": youmind, "tigerowo-awesome-gpt-image-2-prompts": tiger}
    sources = []
    for source_id, evidence in candidates.items():
        spec = SOURCE_SPECS[source_id]
        if spec["role"] == "full":
            status = spec["status"] if _eligible(evidence, source_id) else "blocked"
        else: status = spec["status"]
        sources.append(_source_row(source_id, evidence, status=status))
    batch = [{"source_id": item["source_id"], "revision": item["revision"], "mode": item["mode"], "case_scope": {"case_count": len(item["evidence"].get("case_ledger", [])), "case_ledger_sha256": item["evidence"].get("metrics", {}).get("case_ledger_sha256")}, "structure_strategy": item["structure"]["strategy"], "family_role": item["lineage"]["family_role"], "exclusions": item["evidence"].get("exclusion_ledger", [])} for item in sources if item["status"] in {"continuous_ready", "fixed_history_ready"}]
    payload = {"schema_version": SCHEMA_VERSION, "generated_at": v2._utc_now(), "authority": authority, "sources": sources, "adapter_ready_batch": batch, "summary": {"source_count": 4, "protected_scope_modified": False, "auto_publish": False}}
    payload["canonical_digest"] = _digest(_fixed_core(payload)); return payload

def _emit_sample_queue(payload: Mapping[str, Any], output: Path) -> None:
    queue = {"admission": [], "exclusion": []}
    for source in payload["sources"]:
        evidence = source["evidence"]
        target = "admission" if source["role"] == "full" else "exclusion"
        cases = {x["case_id"]: x for x in evidence.get("case_ledger", [])}
        for case_id in _select_quality_sample(list(cases.values()), min(60, len(cases))):
            case = cases[case_id]; primary = (case.get("outputs") or [{}])[0]
            queue[target].append({"source_id": source["source_id"], "case_id": case_id, "prompt": case.get("prompt", ""), "prompt_sha256": case.get("prompt_sha256"), "primary_asset_locator": primary.get("path"), "primary_asset_authority": primary.get("authority"), "outputs": case.get("outputs", []), "reason": "admission_sample" if target == "admission" else source["role"], "result": "pending"})
        if source["role"] == "full":
            raw_cases = {x["case_id"]: x for x in evidence.get("raw_case_ledger", [])}
            for reason, case_id in sorted(evidence.get("quality", {}).get("exclusion_sample_ids", {}).items()):
                case = raw_cases.get(case_id, {})
                queue["exclusion"].append({"source_id": source["source_id"], "case_id": case_id, "prompt": case.get("prompt", ""), "prompt_sha256": case.get("prompt_sha256"), "outputs": case.get("outputs", []), "reason": reason, "result": "pending"})
        if source["role"] != "full": queue["exclusion"].append({"source_id": source["source_id"], "reason": source["role"], "result": "excluded"})
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(queue, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def _render_report(payload: Mapping[str, Any]) -> str:
    authority = payload["authority"]
    full = [row for row in payload["sources"] if row["role"] == "full"]
    ready = [item["source_id"] for item in payload["adapter_ready_batch"]]
    lines = [
        "# Phase 2 大规模来源准入审计 v3",
        "",
        "## 最终结论",
        "",
        f"本轮固定审计了 2 个完整候选、1 个家族对照源和 1 个排除控制源。最终 `adapter_ready_batch` 包含 {len(ready)} 个来源：" + ("、".join(f"`{value}`" for value in ready) if ready else "空") + "。",
        "",
        "该结论只形成后续 Adapter/一次性导入的只读 handoff；没有修改 Source Registry、Adapter、库存、Canonical、Candidate、Publication、API 或网页，也没有公开任何第三方案例。",
        "",
        "## 当前生产边界",
        "",
        "| active 来源 | internal cases | outputs | 去重资产对象 | source files | real public |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {authority['active_source_count']} | {authority['current_case_count']} | {authority['current_output_count']} | {authority['current_deduplicated_asset_object_count']} | {authority['current_source_file_count']} | {authority['current_public_cases']} |",
        "",
        "以上基线由现有生产解析路径重建；TASK-0021 v2 仍为空批次，全部受保护文件摘要未漂移。",
        "",
        "## 四来源角色与固定权威",
        "",
        "| 来源 | 审计角色 | 家族角色 | mode | fixed revision | 状态 |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["sources"]:
        lines.append(f"| `{row['source_id']}` | `{row['role']}` | `{row['lineage']['family_role']}` | `{row['mode']}` | `{row['revision']}` | `{row['status']}` |")
    youmind = next(row for row in payload["sources"] if row["source_id"] == "youmind-openlab-gpt-image-2-prompts-search")["evidence"]["comparator_ledger"]
    lines.extend([
        "",
        "Goku 与 YouMind 属于同一 OpenLab/Atlas 聚合家族边界：保留各自 provenance，但按标准化 Prompt SHA-256 去重，不把聚合、对照和上游重复计为独立贡献。tigerowo 仅保存 EvoLink backup/排除证据，不建立完整准入账，也不能进入 handoff。",
        "",
        f"YouMind fixed revision 共 {youmind['total']} 条分类记录、{youmind['unique_ids']} 个唯一 ID、{youmind['source_media_reference_count']} 个 CMS 图片引用（{youmind['unique_source_media_urls']} 个唯一 URL）；{youmind['need_reference_images']} 条声明需要参考图。全部图片只作为 `observation_only` 的 CMS HTTPS 对照，作者归因行={youmind['author_attribution_rows']}、原帖链接行={youmind['original_post_rows']}，因此不能作为独立权利或固定资产来源。",
        "",
        "## 完整候选漏斗",
        "",
        "| 来源 | raw | parseable | authority-valid | safety-eligible | within-source unique | within-family unique | current exact-new | quality-valid |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in full:
        stages = row["evidence"]["metrics"]["stages"]
        lines.append(f"| `{row['source_id']}` | {stages['raw']} | {stages['parseable']} | {stages['authority_valid']} | {stages['safety_eligible']} | {stages['within_source_unique']} | {stages['within_family_unique']} | {stages['current_exact_new']} | {stages['quality_valid']} |")
    lines.extend(["", "计数来自完整 case/asset/orphan/exclusion ledgers；filtered 子集不删除 raw 事实，每一条排除均保留 case ID、原因与确定性摘要。", "", "## 资产、质量与维护证据", ""])
    for row in full:
        evidence, metrics, quality = row["evidence"], row["evidence"]["metrics"], row["evidence"]["quality"]
        failed_ids = [str(item.get("case_id")) for item in quality.get("reviews", []) if item.get("result") != "pass" or item.get("prompt_complete") is not True or item.get("image_readable") is not True or item.get("semantic_match") is not True or item.get("visual_quality") not in {"high", "acceptable"}]
        exclusion_count = len(quality.get("exclusion_sample_ids", {}))
        lines.extend([
            f"### `{row['source_id']}`",
            "",
            f"- 固定权威：`{evidence['authority']['kind']}`；tree manifest `{evidence['authority']['tree_manifest_sha256']}`。",
            f"- 资产账：{metrics['asset_count']} 个资产条目，{metrics['orphan_asset_count']} 个 orphan；strong pair rate={metrics['pair_rate']:.4f}，broken authoritative asset rate={metrics['broken_authoritative_asset_rate']:.4f}。",
            f"- 质量证据：确定性准入样本 {quality['sample_size']} 个，排除原因样本 {exclusion_count} 类，样本 manifest `{quality.get('sample_manifest_sha256')}`；结果 `{quality['result']}`。",
        ])
        if failed_ids:
            lines.append(f"- 未通过的准入样本：{len(failed_ids)} 个（`" + "`, `".join(failed_ids) + "`）。")
        if quality.get("missing_review_ids") or quality.get("missing_exclusion_reviews"):
            lines.append(f"- 证据缺口：缺准入复核 {len(quality.get('missing_review_ids', []))} 个，缺/不一致排除复核 {len(quality.get('missing_exclusion_reviews', []))} 个。")
        if row["mode"] == "continuous":
            maintenance = evidence["maintenance"]
            lines.append(f"- 维护判定：实质更新日期 {', '.join(maintenance.get('substantive_dates', [])) or '无'}；`continuous_eligible={str(maintenance.get('continuous_eligible')).lower()}`。")
        else:
            maintenance = evidence["maintenance"]
            lines.append(f"- 固定历史判定：`fixed_snapshot_complete={str(maintenance.get('fixed_snapshot_complete')).lower()}`、`sync_eligible=false`、`one_shot_import_only=true`。")
        lines.append(f"- 最终状态：`{row['status']}`。")
        lines.append("")
    lines.extend([
        "## 权利与消费边界",
        "",
        "- 所有 Prompt 与图片均保持 `review_required`，`auto_publish=false`；仓库或 dataset license 只作为上游声明，不等于真实公开授权。",
        "- Git 图片以 fixed revision 下安全相对路径、文件 bytes、媒体魔数和 SHA-256 为权威；Goku 图片以 fixed HF revision 的 LFS path/OID/size 为全量权威，只有质量样本被实际下载、哈希、解码和人工查看。",
        "- YouMind CMS/远程图只用于对照边界，不被写成 immutable asset authority；tigerowo 不产生可准入案例。",
        "- 本轮只做 exact URL、Prompt SHA-256 与固定资产摘要去重，不执行语义近似自动合并。",
        "",
        "## Adapter handoff",
        "",
    ])
    if payload["adapter_ready_batch"]:
        for item in payload["adapter_ready_batch"]:
            lines.append(f"- `{item['source_id']}`：`{item['mode']}`，revision `{item['revision']}`，case scope {item['case_scope']['case_count']}，case ledger `{item['case_scope']['case_ledger_sha256']}`，structure `{item['structure_strategy']}`，family role `{item['family_role']}`，排除记录 {len(item['exclusions'])} 条。")
    else:
        lines.append("- 空批次；不得从 blocked/comparator/control 来源直接编写 Adapter。")
    lines.extend(["", "下一任务只能消费 JSON `adapter_ready_batch` 的 fixed revision、mode、case scope、structure strategy、family role 和完整 exclusions；不得重新按 HEAD、README 数量或 Stars 选源。"])
    return "\n".join(lines) + "\n"

def _render_handoff(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 2 来源准入 v3 Adapter Handoff",
        "",
        "本文件是 TASK-0022 的只读消费合同。它不表示来源已 active、已导入库存、已进入 scheduler 或已公开。",
        "",
        "| source_id | fixed revision | mode | case count | case ledger SHA-256 | structure strategy | family role | exclusions |",
        "|---|---|---|---:|---|---|---|---:|",
    ]
    for item in payload["adapter_ready_batch"]:
        lines.append(f"| `{item['source_id']}` | `{item['revision']}` | `{item['mode']}` | {item['case_scope']['case_count']} | `{item['case_scope']['case_ledger_sha256']}` | `{item['structure_strategy']}` | `{item['family_role']}` | {len(item['exclusions'])} |")
    if not payload["adapter_ready_batch"]: lines.append("| — | — | 空 batch | 0 | — | — | — | 0 |")
    lines.extend([
        "",
        "## 消费约束",
        "",
        "- 只允许消费 `reports/phase2/source-expansion-admission-v3.json` 中完全相同的 `adapter_ready_batch`；完整 exclusion ledger 以该 JSON 为准。",
        "- `continuous` 只适用于 Goku；`fixed_history` 只适用于 Chaos，且固定历史必须 `sync_eligible=false`、`one_shot_import_only=true`。",
        "- 不得跟随 moving HEAD，不得用 README 数量替换 case scope，不得自行加入 YouMind 或 tigerowo。",
        "- 导入后仍需独立完成 Adapter、库存事务、rights review 和 public consumer 任务；所有内容继续 `review_required`、`auto_publish=false`。",
        "- 当前生产基线仍是 6 active、1513 cases、1930 outputs、1885 去重资产、2260 source files、0 real public。",
        "",
    ])
    return "\n".join(lines)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=REPO_ROOT / "reports/phase2/source-expansion-admission-v3.json")
    parser.add_argument("--schema", type=Path, default=REPO_ROOT / "schemas/phase2-source-expansion-admission-v3.schema.json")
    parser.add_argument("--build", action="store_true"); parser.add_argument("--live", action="store_true"); parser.add_argument("--determinism-check", action="store_true"); parser.add_argument("--json", action="store_true"); parser.add_argument("--emit-sample-queue", type=Path); parser.add_argument("--snapshot-root", type=Path, default=RUNTIME_ROOT); parser.add_argument("--quality-review", type=Path, default=RUNTIME_ROOT / "quality-review.json"); parser.add_argument("--report", type=Path, default=REPO_ROOT / "reports/phase2/source-expansion-admission-v3.md"); parser.add_argument("--handoff", type=Path, default=REPO_ROOT / "docs/phase2/source-expansion-admission-v3.md")
    args = parser.parse_args(argv)
    try:
        if args.build:
            payload = build_report(args.snapshot_root, quality_review=args.quality_review);
            for path, text in ((args.audit, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"), (args.report, _render_report(payload)), (args.handoff, _render_handoff(payload))): path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
            result = {"status": "built", "audit": str(args.audit)}
        elif args.emit_sample_queue:
            _emit_sample_queue(_load(args.audit), args.emit_sample_queue); result = {"status": "sample_queue_written", "output": str(args.emit_sample_queue)}
        else: result = validate(args.audit, args.schema, determinism_check=args.determinism_check, live=args.live, quality_review=args.quality_review)
    except (OSError, ValueError, ValidationFailure) as exc:
        result = {"status": "failed", "error": type(exc).__name__, "message": str(exc)}; print(json.dumps(result, ensure_ascii=False) if args.json else f"FAIL: {exc}"); return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else f"PASS: {result['status']}"); return 0
if __name__ == "__main__": raise SystemExit(main())
