"""Validate the Phase 2 source discovery/admission report, optionally rechecking GitHub."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import posixpath
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROBATION = {
    "eugeniughelbur-gpt-image-cookbook",
    "freestylefly-awesome-gpt-image-2",
    "fzfzerro-image2skill",
    "mageia-awesome-gpt-image-2-api-and-prompts",
    "pixmind-io-awesome-gpt-image-2-prompts",
    "vigozhao-ai-visual-prompt-cookbook",
    "wuyoscar-gpt-image2-skill",
    "yinxiaowai-awesome-gpt-image-2-vs-nano-banana-2-prompt-gallery",
}
PHASE2_NEW_ACTIVE_SOURCE_ID = "erickkkyt-awesome-gptimage2-prompts"
PHASE1_ACTIVE_CASES = {
    "g0dam-work-prompts": 100,
    "joesai-commercial-prompts": 50,
    "conardli-gpt-image-2-101": 162,
}


class ValidationFailure(RuntimeError):
    """Fail-closed source-admission conclusion."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationFailure(f"{path.name} must contain an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(actual: object, expected: float, label: str) -> None:
    if not isinstance(actual, (int, float)) or isinstance(actual, bool) or abs(float(actual) - expected) > 0.000001:
        raise ValidationFailure(f"{label} is not arithmetically reproducible")


def _candidate_keys_from_phase1(repo_root: Path) -> set[str]:
    payload = _load(repo_root / "reports" / "source-audit-v1.json")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValidationFailure("Phase 1 audit records are unavailable")
    return {
        str(item.get("candidate_key", "")).casefold()
        for item in records
        if isinstance(item, Mapping) and item.get("source_id") != PHASE2_NEW_ACTIVE_SOURCE_ID
    }


def _validate_post_activation_authority(payload: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    try:
        audit = _load(repo_root / "reports" / "source-audit-v1.json")
        registry = _load(repo_root / "config" / "sources-v1.yaml")
    except (OSError, json.JSONDecodeError, ValidationFailure) as exc:
        raise ValidationFailure("Phase 1 authority hash changed without a valid post-admission authority") from exc
    records = audit.get("records")
    sources = registry.get("sources")
    if not isinstance(records, list) or not isinstance(sources, list):
        raise ValidationFailure("post-admission source authority is malformed")
    audit_by_id = {str(item.get("source_id")): item for item in records if isinstance(item, Mapping)}
    source_by_id = {str(item.get("source_id")): item for item in sources if isinstance(item, Mapping)}
    active_ids = {source_id for source_id, item in source_by_id.items() if item.get("status") == "active"}
    ready = payload.get("adapter_ready_batch")
    if not isinstance(ready, list):
        raise ValidationFailure("adapter-ready batch is unavailable for post-admission authority")
    ready_ids = {str(item.get("source_id")) for item in ready if isinstance(item, Mapping)}
    if active_ids != set(PHASE1_ACTIVE_CASES) | ready_ids:
        raise ValidationFailure("current active source set is not the Phase 1 sources plus the admitted batch")
    if sum(PHASE1_ACTIVE_CASES.values()) != int(payload["authority"]["phase1_internal_cases"]):
        raise ValidationFailure("Phase 1 internal case baseline no longer closes")
    for source_id, expected_cases in PHASE1_ACTIVE_CASES.items():
        record = audit_by_id.get(source_id)
        metrics = record.get("metrics") if isinstance(record, Mapping) else None
        if not isinstance(metrics, Mapping) or metrics.get("unique_valid_case_count") != expected_cases:
            raise ValidationFailure(f"Phase 1 active source count changed after admission: {source_id}")
    for item in ready:
        if not isinstance(item, Mapping):
            raise ValidationFailure("adapter-ready item is malformed")
        source_id = str(item["source_id"])
        source = source_by_id.get(source_id)
        record = audit_by_id.get(source_id)
        if not isinstance(source, Mapping) or not isinstance(record, Mapping):
            raise ValidationFailure(f"admitted source is missing from current authority: {source_id}")
        repository = source.get("repository")
        content = source.get("content")
        rights = source.get("rights")
        publication = source.get("publication")
        audit_repository = record.get("repository")
        audit_content = record.get("content")
        if (
            not isinstance(repository, Mapping)
            or repository.get("verified_commit_sha") != item.get("fixed_commit_sha")
            or not isinstance(audit_repository, Mapping)
            or audit_repository.get("verified_commit_sha") != item.get("fixed_commit_sha")
            or not isinstance(content, Mapping)
            or content.get("adapter_strategy") != item.get("recommended_adapter_strategy")
            or not isinstance(audit_content, Mapping)
            or audit_content.get("adapter_strategy") != item.get("recommended_adapter_strategy")
            or not isinstance(rights, Mapping)
            or rights.get("prompt_policy") != "review_required"
            or rights.get("asset_policy") != "review_required"
            or not isinstance(publication, Mapping)
            or publication.get("auto_publish") is not False
            or record.get("recommended_status") != "active"
        ):
            raise ValidationFailure(f"admitted source authority diverges from TASK-0018: {source_id}")
    return {"state": "post_admission_superset", "active_sources": len(active_ids), "phase1_internal_cases": 312}


def _validate_metrics(source_id: str, metrics: Mapping[str, Any]) -> None:
    observed = int(metrics.get("observed_case_count", -1))
    prompts = int(metrics.get("exact_prompt_count", -1))
    paired = int(metrics.get("paired_output_count", -1))
    valid = int(metrics.get("valid_case_count", -1))
    unique = int(metrics.get("unique_valid_case_count", -1))
    image_refs = int(metrics.get("image_reference_count", -1))
    broken = int(metrics.get("broken_asset_count", -1))
    duplicates = int(metrics.get("duplicate_count", -1))
    if min(observed, prompts, paired, valid, unique, image_refs, broken, duplicates) < 0:
        raise ValidationFailure(f"{source_id} has negative metrics")
    if not (unique <= valid <= paired <= observed and valid <= prompts):
        raise ValidationFailure(f"{source_id} metric counts do not form a valid coverage chain")
    if broken > image_refs or duplicates != valid - unique:
        raise ValidationFailure(f"{source_id} asset or duplicate counts do not close")
    _close(metrics.get("pair_rate"), valid / observed if observed else 0.0, f"{source_id}.pair_rate")
    _close(metrics.get("broken_asset_rate"), broken / image_refs if image_refs else 1.0, f"{source_id}.broken_asset_rate")
    _close(metrics.get("duplicate_rate"), duplicates / valid if valid else 1.0, f"{source_id}.duplicate_rate")


def _expected_sample_size(unique_valid: int) -> int:
    return min(unique_valid, 50, max(20, math.ceil(unique_valid * 0.10))) if unique_valid else 0


def _hash_lines(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _parse_utc(value: str, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationFailure(f"{label} is not a valid date-time") from exc
    if parsed.tzinfo is None:
        raise ValidationFailure(f"{label} must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def _validate_coverage_evidence(source_id: str, item: Mapping[str, Any]) -> None:
    metrics = item["metrics"]
    evidence = item["evidence"]
    record_ids = [str(value) for value in evidence["record_ids"]]
    if len(record_ids) != int(metrics["observed_case_count"]):
        raise ValidationFailure(f"{source_id} record ledger does not cover every observed case")
    if evidence["record_ids_sha256"] != _hash_lines(record_ids):
        raise ValidationFailure(f"{source_id} record ledger digest is incorrect")
    terminal = evidence["asset_terminal_summary"]
    checked = int(terminal["checked_reference_count"])
    readable = int(terminal["readable_reference_count"])
    broken = int(terminal["broken_reference_count"])
    if checked != int(metrics["image_reference_count"]) or broken != int(metrics["broken_asset_count"]) or readable + broken != checked:
        raise ValidationFailure(f"{source_id} asset terminal summary does not close")


def _validate_quality_evidence(source_id: str, quality: Mapping[str, Any], expected_sample: int) -> None:
    sample_ids = [str(value) for value in quality["sample_ids"]]
    terminals = quality["terminal_results"]
    if quality["result"] == "pass":
        if quality["sample_size"] != expected_sample or quality["terminal_asset_checks"] != expected_sample:
            raise ValidationFailure(f"{source_id} passing quality sample has the wrong size")
        if len(sample_ids) != expected_sample or len(set(sample_ids)) != expected_sample:
            raise ValidationFailure(f"{source_id} quality sample IDs are incomplete or duplicated")
        if quality["sample_ids_sha256"] != _hash_lines(sample_ids):
            raise ValidationFailure(f"{source_id} quality sample digest is incorrect")
        terminal_ids = [str(item["case_id"]) for item in terminals]
        if terminal_ids != sample_ids or len(terminals) != expected_sample:
            raise ValidationFailure(f"{source_id} quality terminal results do not match its sample")
    elif sample_ids or terminals or quality["sample_size"] != 0 or quality["terminal_asset_checks"] != 0 or quality["sample_ids_sha256"] is not None:
        raise ValidationFailure(f"{source_id} failed-gate quality evidence must be empty")


def _semantic_validate(payload: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    authority = payload["authority"]
    audit_matches = authority["phase1_audit_sha256"] == _sha256(repo_root / "reports" / "source-audit-v1.json")
    registry_matches = authority["phase1_registry_sha256"] == _sha256(repo_root / "config" / "sources-v1.yaml")
    authority_state = (
        {"state": "historical_phase1_hashes", "active_sources": 3, "phase1_internal_cases": 312}
        if audit_matches and registry_matches
        else _validate_post_activation_authority(payload, repo_root)
    )

    generated_at = _parse_utc(payload["generated_at"], "generated_at")
    discovery = payload["discovery"]
    executed_at = _parse_utc(discovery["executed_at"], "discovery.executed_at")
    if executed_at > generated_at or generated_at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValidationFailure("discovery/report timestamps are not chronologically credible")
    query_ids = [item["query_id"] for item in discovery["query_runs"]]
    if len(query_ids) != len(set(query_ids)) or len(query_ids) < 5:
        raise ValidationFailure("query coverage is missing or duplicated")
    if any(item["incomplete_results"] is not False for item in discovery["query_runs"]):
        raise ValidationFailure("an incomplete search result cannot close discovery")

    refreshed = discovery["existing_probation_refresh"]
    refreshed_ids = {item["source_id"] for item in refreshed}
    if refreshed_ids != EXPECTED_PROBATION or len(refreshed) != len(EXPECTED_PROBATION):
        raise ValidationFailure("the eight Phase 1 probation sources are not exactly refreshed")

    additional = discovery["additional_phase1_refresh"]
    phase1_keys = _candidate_keys_from_phase1(repo_root)
    additional_keys = [item["candidate_key"].casefold() for item in additional]
    if any(key not in phase1_keys for key in additional_keys) or len(additional_keys) != len(set(additional_keys)):
        raise ValidationFailure("additional Phase 1 refresh records are not a unique Phase 1 subset")
    new_candidates = discovery["new_candidates"]
    new_keys = [item["candidate_key"].casefold() for item in new_candidates]
    if len(new_candidates) < 20 or len(new_keys) != len(set(new_keys)):
        raise ValidationFailure("new candidate coverage is below 20 or contains duplicates")
    if phase1_keys.intersection(new_keys):
        raise ValidationFailure("a Phase 1 candidate is misreported as new")
    all_candidates = refreshed + additional + new_candidates
    candidate_by_key = {item["candidate_key"].casefold(): item for item in all_candidates}
    if len(candidate_by_key) != len(all_candidates):
        raise ValidationFailure("candidate identity is duplicated across discovery layers")
    repository_ids = [item["repository_id"] for item in all_candidates if item["repository_id"] is not None]
    if len(repository_ids) != len(set(repository_ids)):
        raise ValidationFailure("repository identity is duplicated across candidates")

    full_audits = payload["full_audits"]
    if len(full_audits) < 8:
        raise ValidationFailure("fewer than eight sources have full audits")
    audit_by_id = {item["source_id"]: item for item in full_audits}
    if len(audit_by_id) != len(full_audits):
        raise ValidationFailure("full audit source_id is duplicated")

    ready: list[dict[str, Any]] = []
    thresholds = payload["thresholds"]
    family_canonical: dict[str, str] = {}
    for item in full_audits:
        source_id = item["source_id"]
        candidate = candidate_by_key.get(item["candidate_key"].casefold())
        if candidate is None:
            raise ValidationFailure(f"{source_id} has no discovery upstream record")
        for field in ("repository_id", "url", "fixed_commit_sha"):
            if candidate[field] != item[field]:
                raise ValidationFailure(f"{source_id} full audit diverges from its discovery upstream")
        metrics = item["metrics"]
        _validate_metrics(source_id, metrics)
        _validate_coverage_evidence(source_id, item)
        status = item["status"]
        quality = item["quality_sampling"]
        expected_sample = _expected_sample_size(int(metrics["unique_valid_case_count"]))
        _validate_quality_evidence(source_id, quality, expected_sample)
        family_id = item["family_id"]
        canonical_id = item["canonical_source_id"]
        if item["family_role"] == "canonical":
            if canonical_id != source_id:
                raise ValidationFailure(f"{source_id} canonical family mapping is inconsistent")
            prior = family_canonical.setdefault(family_id, source_id)
            if prior != source_id:
                raise ValidationFailure(f"{family_id} has multiple canonical sources")
        elif canonical_id is not None and canonical_id == source_id:
            raise ValidationFailure(f"{source_id} non-canonical family role self-claims authority")
        if status == "adapter_ready":
            if item["family_role"] != "canonical":
                raise ValidationFailure(f"{source_id} is adapter_ready without canonical family authority")
            if int(metrics["unique_valid_case_count"]) < thresholds["minimum_unique_valid_cases"]:
                raise ValidationFailure(f"{source_id} is adapter_ready below the case threshold")
            if float(metrics["pair_rate"]) < thresholds["minimum_pair_rate"]:
                raise ValidationFailure(f"{source_id} is adapter_ready below the pairing threshold")
            if float(metrics["broken_asset_rate"]) > thresholds["maximum_broken_asset_rate"]:
                raise ValidationFailure(f"{source_id} is adapter_ready above the broken-asset threshold")
            if float(metrics["duplicate_rate"]) > thresholds["maximum_duplicate_rate"]:
                raise ValidationFailure(f"{source_id} is adapter_ready above the duplicate threshold")
            maintenance = item["maintenance"]
            latest_value = maintenance["latest_substantive_update"]
            try:
                latest = dt.date.fromisoformat(str(latest_value))
            except ValueError as exc:
                raise ValidationFailure(f"{source_id} has invalid maintenance date") from exc
            age_days = (executed_at.date() - latest).days
            if age_days < 0 or age_days > thresholds["latest_substantive_update_days"]:
                raise ValidationFailure(f"{source_id} is adapter_ready outside the maintenance recency threshold")
            if maintenance["eligible"] is not True or maintenance["substantive_update_dates_365"] < thresholds["minimum_substantive_update_dates_365"]:
                raise ValidationFailure(f"{source_id} is adapter_ready without maintenance evidence")
            if quality["result"] != "pass":
                raise ValidationFailure(f"{source_id} is adapter_ready without its complete quality sample")
            rights = item["rights"]
            if rights["public_eligibility"] != "review_required" or rights["auto_publish"] is not False:
                raise ValidationFailure(f"{source_id} weakens the rights/publication boundary")
            if not item["recommended_adapter_strategy"]:
                raise ValidationFailure(f"{source_id} has no deterministic adapter handoff")
            ready.append(item)
        elif quality["result"] == "pass" and quality["sample_size"] != expected_sample:
            raise ValidationFailure(f"{source_id} passing quality sample has the wrong size")

    if len(ready) < 3:
        raise ValidationFailure("fewer than three sources are adapter_ready")
    batch = payload["adapter_ready_batch"]
    batch_ids = [item["source_id"] for item in batch]
    ready_ids = {item["source_id"] for item in ready}
    if set(batch_ids) != ready_ids or len(batch_ids) != len(ready_ids):
        raise ValidationFailure("adapter_ready_batch does not exactly match full-audit status")
    if [item["rank"] for item in batch] != list(range(1, len(batch) + 1)):
        raise ValidationFailure("adapter_ready_batch ranks are not contiguous")
    for item in batch:
        audit = audit_by_id[item["source_id"]]
        if item["fixed_commit_sha"] != audit["fixed_commit_sha"] or item["unique_valid_case_count"] != audit["metrics"]["unique_valid_case_count"]:
            raise ValidationFailure("adapter_ready_batch diverges from its full audit")
        if item["recommended_adapter_strategy"] != audit["recommended_adapter_strategy"]:
            raise ValidationFailure("adapter_ready_batch adapter strategy diverges from its full audit")

    summary = payload["summary"]
    if summary["new_candidate_count"] != len(new_candidates) or summary["full_audit_count"] != len(full_audits) or summary["adapter_ready_count"] != len(ready):
        raise ValidationFailure("summary counts diverge from records")
    if summary["adapter_ready_unique_cases"] != sum(item["metrics"]["unique_valid_case_count"] for item in ready):
        raise ValidationFailure("adapter-ready case aggregate is incorrect")

    markdown = (repo_root / "reports" / "phase2" / "source-discovery-v1.md").read_text(encoding="utf-8")
    handoff = (repo_root / "docs" / "phase2" / "source-expansion-admission-v1.md").read_text(encoding="utf-8")
    for source_id in batch_ids:
        if source_id not in markdown or source_id not in handoff:
            raise ValidationFailure(f"{source_id} is missing from a consumer document")
    for phrase in ("312 internal", "0 real public", "TASK-0019"):
        if phrase not in handoff:
            raise ValidationFailure(f"handoff document is missing required boundary: {phrase}")
    result = {
        "query_runs": len(query_ids),
        "existing_probation": len(refreshed),
        "additional_phase1_refresh": len(additional),
        "new_candidates": len(new_candidates),
        "full_audits": len(full_audits),
        "adapter_ready": len(ready),
        "adapter_ready_unique_cases": summary["adapter_ready_unique_cases"],
    }
    if authority_state["state"] != "historical_phase1_hashes":
        result["authority_state"] = authority_state
    return result


def _github_json(url: str, attempts: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "image2-phase2-validator/1"})
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


def _raw_bytes(repo: str, sha: str, path: str, attempts: int = 3) -> bytes:
    quoted = "/".join(urllib.parse.quote(part) for part in path.split("/"))
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quoted}"
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "image2-phase2-validator/1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
    raise ValidationFailure(f"fixed raw asset did not complete for {path}: {type(last).__name__}")


def _tree(repo: str, sha: str) -> dict[str, dict[str, Any]]:
    payload = _github_json(f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1")
    if payload.get("truncated") is not False or not isinstance(payload.get("tree"), list):
        raise ValidationFailure(f"{repo} fixed tree is unavailable or truncated")
    return {str(item["path"]): item for item in payload["tree"] if item.get("type") == "blob"}


def _generic_records(repo: str, sha: str) -> list[dict[str, Any]]:
    text = _raw_bytes(repo, sha, "README.md").decode("utf-8", errors="replace")
    starts = list(re.finditer(r"(?m)^###\s+(.+)$", text))
    rows: list[dict[str, Any]] = []
    skipped = {"📖 Description", "📝 Prompt", "🖼️ Generated Images", "📌 Details", "🏷️ Browse by Category", "🚀 Raycast Integration"}
    for index, match in enumerate(starts):
        title = re.sub(r"[*`#]", "", match.group(1)).strip()
        if title in skipped:
            continue
        block = text[match.end() : starts[index + 1].start() if index + 1 < len(starts) else len(text)]
        prompt_match = re.search(r"```[^\n]*\n(.*?)\n```", block, re.S)
        image_values = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", block) + re.findall(r"<img[^>]+src=[\"']([^\"']+)", block, re.I)
        paths = []
        for value in image_values:
            clean = value.split("?", 1)[0]
            paths.append("external:" + clean if clean.startswith(("http://", "https://")) else posixpath.normpath(clean.lstrip("./")))
        if prompt_match or paths:
            rows.append({"id": f"section-{index:04d}-{title[:40]}", "prompt": prompt_match.group(1).strip() if prompt_match else "", "images": paths})
    return rows


def _records(source_id: str, repo: str, sha: str, blobs: Mapping[str, Any]) -> list[dict[str, Any]]:
    if source_id == "freestylefly-awesome-gpt-image-2":
        payload = json.loads(_raw_bytes(repo, sha, "data/cases.json"))
        rows = []
        for item in payload["cases"]:
            path = str(item.get("image", "")).lstrip("/")
            if path.startswith("images/"):
                path = "data/" + path
            rows.append({"id": str(item["id"]), "prompt": item.get("prompt", ""), "images": [path]})
        return rows
    if source_id == "erickkkyt-awesome-gptimage2-prompts":
        payload = json.loads(_raw_bytes(repo, sha, "prompts/prompts.json"))
        return [{"id": str(item.get("id") or item.get("index")), "prompt": item.get("prompt", ""), "images": item.get("images") or [item.get("image")]} for item in payload]
    if source_id == "vigozhao-ai-visual-prompt-cookbook":
        rows = []
        for path in sorted(value for value in blobs if re.fullmatch(r"styles/[^/]+/style\.json", value)):
            value = json.loads(_raw_bytes(repo, sha, path))
            folder = posixpath.dirname(path)
            rows.append({"id": value.get("style_slug") or posixpath.basename(folder), "prompt": json.dumps(value.get("prompt_template"), ensure_ascii=False, sort_keys=True), "images": [f"{folder}/preview-16x9.jpg", f"{folder}/preview-9x16.jpg"]})
        return rows
    if source_id == "pixmind-io-awesome-gpt-image-2-prompts":
        rows = []
        for readme in sorted(value for value in blobs if re.fullmatch(r"prompts/[^/]+/README\.md", value)):
            text = _raw_bytes(repo, sha, readme).decode("utf-8")
            starts = list(re.finditer(r"(?m)^##\s+(\d+)\.\s+(.+)$", text))
            for index, match in enumerate(starts):
                block = text[match.end() : starts[index + 1].start() if index + 1 < len(starts) else len(text)]
                prompt_match = re.search(r"```[^\n]*\n(.*?)\n```", block, re.S)
                image_match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", block)
                image = posixpath.normpath(posixpath.join(posixpath.dirname(readme), image_match.group(1))) if image_match else ""
                rows.append({"id": f"{posixpath.basename(posixpath.dirname(readme))}-{match.group(1)}", "prompt": prompt_match.group(1).strip() if prompt_match else "", "images": [image] if image else []})
        return rows
    if source_id == "mageia-awesome-gpt-image-2-api-and-prompts":
        rows = []
        for readme in sorted(value for value in blobs if re.fullmatch(r"cases/[a-z-]+\.md", value)):
            text = _raw_bytes(repo, sha, readme).decode("utf-8", errors="replace")
            starts = list(re.finditer(r"(?m)^###\s+Case\s+(\d+):\s+(.+)$", text))
            for index, match in enumerate(starts):
                block = text[match.end() : starts[index + 1].start() if index + 1 < len(starts) else len(text)]
                prompt_match = re.search(r"\*\*Prompt:\*\*\s*\n\s*```(?:\w+)?\s*\n(.*?)\n```", block, re.S)
                paths = []
                for url in re.findall(r"<img[^>]+src=[\"']([^\"']+)", block, re.I):
                    if "/main/" in url:
                        paths.append(url.split("/main/", 1)[1].split("?", 1)[0])
                rows.append({"id": match.group(1), "prompt": prompt_match.group(1).strip() if prompt_match else "", "images": sorted(set(paths))})
        return rows
    return _generic_records(repo, sha)


def _recomputed_metrics(records: list[dict[str, Any]], blobs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observed = len(records)
    prompts = sum(bool(str(row.get("prompt", "")).strip()) for row in records)
    paired = 0
    broken = 0
    refs = 0
    fingerprints = []
    for row in records:
        paths = [str(path) for path in row.get("images", []) if path]
        refs += len(paths)
        existing = [path for path in paths if path in blobs]
        broken += len(paths) - len(existing)
        if str(row.get("prompt", "")).strip() and existing:
            paired += 1
            fingerprints.append(hashlib.sha256((str(row["prompt"]).strip() + "\0" + "\0".join(str(blobs[path]["sha"]) for path in existing)).encode()).hexdigest())
    unique = len(set(fingerprints))
    return {
        "observed_case_count": observed, "exact_prompt_count": prompts, "paired_output_count": paired, "valid_case_count": paired,
        "unique_valid_case_count": unique, "pair_rate": round(paired / observed, 6) if observed else 0.0,
        "image_reference_count": refs, "broken_asset_count": broken, "broken_asset_rate": round(broken / refs, 6) if refs else 1.0,
        "duplicate_count": paired - unique, "duplicate_rate": round((paired - unique) / paired, 6) if paired else 1.0,
    }


def _deterministic_sample(values: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if size >= len(values):
        return list(values)
    return [values[round(index * (len(values) - 1) / (size - 1))] for index in range(size)]


def _live_validate(payload: dict[str, Any]) -> dict[str, Any]:
    checked = []
    candidates = payload["discovery"]["existing_probation_refresh"] + payload["discovery"]["additional_phase1_refresh"] + payload["discovery"]["new_candidates"]
    triaged = [item for item in candidates if item["status"] == "triaged"]
    for item in triaged:
        parts = urllib.parse.urlparse(str(item["url"])).path.strip("/").split("/")
        if len(parts) != 2:
            raise ValidationFailure(f"{item['source_id']} has a non-repository GitHub URL")
        owner_repo = "/".join(parts)
        metadata = _github_json(f"https://api.github.com/repos/{owner_repo}")
        if metadata.get("id") != item["repository_id"] or metadata.get("archived") is True or metadata.get("default_branch") != item["default_branch"]:
            raise ValidationFailure(f"{item['source_id']} repository identity is unavailable or archived")
        commit = _github_json(f"https://api.github.com/repos/{owner_repo}/commits/{item['fixed_commit_sha']}")
        if commit.get("sha") != item["fixed_commit_sha"]:
            raise ValidationFailure(f"{item['source_id']} fixed Commit is unavailable")
        checked.append({"source_id": item["source_id"], "repository_id": metadata["id"], "default_branch": metadata["default_branch"], "fixed_commit_sha": commit["sha"]})

    recomputed = []
    for item in payload["full_audits"]:
        owner_repo = urllib.parse.urlparse(item["url"]).path.strip("/")
        blobs = _tree(owner_repo, item["fixed_commit_sha"])
        records = _records(item["source_id"], owner_repo, item["fixed_commit_sha"], blobs)
        actual_metrics = _recomputed_metrics(records, blobs)
        for key, expected in item["metrics"].items():
            if isinstance(expected, float):
                _close(actual_metrics[key], expected, f"live.{item['source_id']}.{key}")
            elif actual_metrics[key] != expected:
                raise ValidationFailure(f"live.{item['source_id']}.{key} does not match fixed Commit")
        record_ids = [str(row["id"]) for row in records]
        if record_ids != item["evidence"]["record_ids"]:
            raise ValidationFailure(f"live.{item['source_id']} case ledger does not match fixed Commit")
        quality = item["quality_sampling"]
        if quality["result"] == "pass":
            local_records = [row for row in records if row.get("images") and not str(row["images"][0]).startswith("external:")]
            selected = _deterministic_sample(local_records, quality["sample_size"])
            sample_ids = [f"{row['id']}|{row['images'][0]}" for row in selected]
            if sample_ids != quality["sample_ids"]:
                raise ValidationFailure(f"live.{item['source_id']} quality sample selection is not reproducible")
            for row, terminal in zip(selected, quality["terminal_results"]):
                content = _raw_bytes(owner_repo, item["fixed_commit_sha"], str(row["images"][0]))
                if hashlib.sha256(content).hexdigest() != terminal["asset_sha256"]:
                    raise ValidationFailure(f"live.{item['source_id']} sampled asset digest changed")
        recomputed.append({"source_id": item["source_id"], "observed_case_count": actual_metrics["observed_case_count"], "quality_assets_checked": quality["terminal_asset_checks"]})
    return {"triaged_checked": checked, "triaged_count": len(checked), "full_audits_recomputed": recomputed, "full_audit_count": len(recomputed)}


def validate(audit_path: Path, schema_path: Path, *, repo_root: Path = REPO_ROOT, live: bool = False, determinism_check: bool = False) -> dict[str, Any]:
    payload = _load(audit_path)
    schema = _load(schema_path)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "$"
        raise ValidationFailure(f"schema validation failed at {location}: {errors[0].message}")
    summary = _semantic_validate(payload, repo_root)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if determinism_check:
        repeated = _semantic_validate(json.loads(canonical), repo_root)
        if repeated != summary:
            raise ValidationFailure("determinism check changed the semantic summary")
    live_summary = _live_validate(payload) if live else None
    return {"status": "passed", "audit_sha256": _sha256(audit_path), "canonical_digest": digest, "summary": summary, "live": live_summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--determinism-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate(args.audit, args.schema, live=args.live, determinism_check=args.determinism_check)
    except (OSError, json.JSONDecodeError, ValidationFailure) as exc:
        result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"FAIL: {result['error']}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("PASS: Phase 2 source discovery/admission report is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
