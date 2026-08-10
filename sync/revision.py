"""Run-scoped candidate authority, stable case diffs, and quality gates."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ingestion.registry import RegistryError, SourceConfig, ensure_external_root, load_source_config, repo_root


class RevisionError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SyncSource:
    config: SourceConfig
    default_branch: str
    minimum_valid_cases: int
    minimum_pair_rate: float
    static_registry_sha256: str
    static_audit_sha256: str


@dataclass(frozen=True)
class RevisionAuthority:
    source_id: str
    candidate_revision_sha: str
    registry_path: Path
    extraction_audit_path: Path
    import_audit_path: Path | None
    evidence: dict[str, Any]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevisionError("authority_invalid", "static source authority cannot be read") from exc
    if not isinstance(value, dict):
        raise RevisionError("authority_invalid", "static source authority must be a JSON object")
    return value


def _source_record(registry: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    sources = registry.get("sources")
    matches = [item for item in sources if isinstance(item, dict) and item.get("source_id") == source_id] if isinstance(sources, list) else []
    if len(matches) != 1:
        raise RevisionError("authority_invalid", "static registry does not identify exactly one source")
    return matches[0]


def _audit_record(audit: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    records = audit.get("records")
    matches = [item for item in records if isinstance(item, dict) and item.get("source_id") == source_id] if isinstance(records, list) else []
    if len(matches) != 1:
        raise RevisionError("authority_invalid", "static audit does not identify exactly one source")
    return matches[0]


def load_sync_source(registry_path: Path | str, audit_path: Path | str, source_id: str) -> SyncSource:
    registry_file = Path(registry_path).resolve()
    audit_file = Path(audit_path).resolve()
    try:
        config = load_source_config(registry_file, source_id)
    except RegistryError as exc:
        raise RevisionError(exc.error_code, str(exc)) from exc
    registry = _load_json(registry_file)
    audit = _load_json(audit_file)
    source = _source_record(registry, source_id)
    audit_record = _audit_record(audit, source_id)
    repository = source.get("repository")
    admission = source.get("admission")
    if not isinstance(repository, dict) or not isinstance(admission, dict):
        raise RevisionError("authority_invalid", "source sync policy is malformed")
    default_branch = repository.get("default_branch")
    minimum_valid_cases = admission.get("minimum_valid_cases")
    minimum_pair_rate = admission.get("minimum_pair_rate")
    audit_repository = audit_record.get("repository")
    if (
        not isinstance(default_branch, str)
        or not isinstance(minimum_valid_cases, int)
        or minimum_valid_cases <= 0
        or not isinstance(minimum_pair_rate, (int, float))
        or not 0 <= float(minimum_pair_rate) <= 1
        or not isinstance(audit_repository, dict)
        or audit_repository.get("verified_commit_sha") != config.verified_commit_sha
    ):
        raise RevisionError("authority_invalid", "static source and audit authority disagree")
    return SyncSource(
        config=config,
        default_branch=default_branch,
        minimum_valid_cases=minimum_valid_cases,
        minimum_pair_rate=float(minimum_pair_rate),
        static_registry_sha256=_sha256_file(registry_file),
        static_audit_sha256=_sha256_file(audit_file),
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _effective_registry(static_registry: dict[str, Any], source_id: str, candidate_sha: str) -> dict[str, Any]:
    registry = copy.deepcopy(static_registry)
    source = _source_record(registry, source_id)
    repository = source.get("repository")
    audit_ref = source.get("audit_ref")
    if not isinstance(repository, dict) or not isinstance(audit_ref, dict):
        raise RevisionError("authority_invalid", "static source cannot form a candidate authority")
    repository["verified_commit_sha"] = candidate_sha
    audit_ref["verified_commit_sha"] = candidate_sha
    return registry


def _effective_audit(
    static_audit: dict[str, Any],
    source_id: str,
    candidate_sha: str,
    candidate_metrics: Mapping[str, Any] | None,
) -> dict[str, Any]:
    audit = copy.deepcopy(static_audit)
    record = _audit_record(audit, source_id)
    repository = record.get("repository")
    if not isinstance(repository, dict):
        raise RevisionError("authority_invalid", "static audit cannot form a candidate authority")
    repository["verified_commit_sha"] = candidate_sha
    if candidate_metrics is not None:
        record["metrics"] = copy.deepcopy(dict(candidate_metrics))
    return audit


def create_revision_authority(
    *,
    registry_path: Path | str,
    audit_path: Path | str,
    source: SyncSource,
    candidate_revision_sha: str,
    evidence_root: Path | str,
    candidate_metrics: Mapping[str, Any] | None = None,
) -> RevisionAuthority:
    """Materialize only run-scoped effective authority outside the workspace."""

    root = ensure_external_root(evidence_root, workspace_root=repo_root())
    static_registry = _load_json(Path(registry_path).resolve())
    static_audit = _load_json(Path(audit_path).resolve())
    authority_dir = root / "authority" / source.config.source_id / candidate_revision_sha
    registry = _effective_registry(static_registry, source.config.source_id, candidate_revision_sha)
    extraction_audit = _effective_audit(static_audit, source.config.source_id, candidate_revision_sha, None)
    registry_file = authority_dir / "effective-registry.json"
    extraction_audit_file = authority_dir / "effective-audit-for-extraction.json"
    _atomic_json(registry_file, registry)
    _atomic_json(extraction_audit_file, extraction_audit)
    import_audit_file: Path | None = None
    if candidate_metrics is not None:
        import_audit_file = authority_dir / "effective-audit-for-import.json"
        _atomic_json(
            import_audit_file,
            _effective_audit(static_audit, source.config.source_id, candidate_revision_sha, candidate_metrics),
        )
    evidence = {
        "source_id": source.config.source_id,
        "baseline_revision_sha": source.config.verified_commit_sha,
        "candidate_revision_sha": candidate_revision_sha,
        "default_branch": source.default_branch,
        "static_registry_sha256": source.static_registry_sha256,
        "static_audit_sha256": source.static_audit_sha256,
        "minimum_valid_cases": source.minimum_valid_cases,
        "minimum_pair_rate": source.minimum_pair_rate,
        "effective_registry_sha256": _sha256_file(registry_file),
        "effective_extraction_audit_sha256": _sha256_file(extraction_audit_file),
        "effective_import_audit_sha256": _sha256_file(import_audit_file) if import_audit_file else None,
    }
    return RevisionAuthority(
        source_id=source.config.source_id,
        candidate_revision_sha=candidate_revision_sha,
        registry_path=registry_file,
        extraction_audit_path=extraction_audit_file,
        import_audit_path=import_audit_file,
        evidence=evidence,
    )


def _document_list(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    documents = value.get("documents")
    if isinstance(documents, list):
        return [dict(item) for item in documents if isinstance(item, Mapping)]
    return [dict(value)] if value else []


def _semantic_generation_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a Generation Example document onto revision-stable business facts.

    A full contract document contains provenance locations and its enclosing
    revision SHA.  Those facts must remain immutable in inventory, but they do
    not make a case *modified*: every unchanged case would otherwise change
    whenever a new Commit updates its raw GitHub URL.  Keep identifiers,
    prompt text, resolved hashes, claims, and pairing strength only.
    """

    prompts = document.get("prompts") if isinstance(document.get("prompts"), list) else []
    assets = document.get("assets") if isinstance(document.get("assets"), list) else []
    examples = document.get("generation_examples") if isinstance(document.get("generation_examples"), list) else []
    return {
        "prompts": sorted(
            [
                {
                    "prompt_id": item.get("prompt_id"),
                    "raw_text": item.get("raw_text"),
                    "language": item.get("language"),
                }
                for item in prompts
                if isinstance(item, Mapping)
            ],
            key=lambda item: str(item["prompt_id"]),
        ),
        "assets": sorted(
            [
                {
                    "asset_id": item.get("asset_id"),
                    "role": item.get("role"),
                    "content_sha256": item.get("content_sha256"),
                }
                for item in assets
                if isinstance(item, Mapping)
            ],
            key=lambda item: str(item["asset_id"]),
        ),
        "generation_examples": sorted(
            [
                {
                    "generation_example_id": item.get("generation_example_id"),
                    "prompt_id": item.get("prompt_id"),
                    "input_asset_ids": item.get("input_asset_ids"),
                    "output_asset_ids": item.get("output_asset_ids"),
                    "generation_claim": item.get("generation_claim"),
                    "pairing": {
                        "method": item.get("pairing", {}).get("method") if isinstance(item.get("pairing"), Mapping) else None,
                        "status": item.get("pairing", {}).get("status") if isinstance(item.get("pairing"), Mapping) else None,
                    },
                }
                for item in examples
                if isinstance(item, Mapping)
            ],
            key=lambda item: str(item["generation_example_id"]),
        ),
    }


def case_fingerprint(adapter_record: Mapping[str, Any], generation_document: Mapping[str, Any]) -> str:
    """Hash only semantic case facts; paths, source URLs, and timestamps do not affect it."""

    prompt = adapter_record.get("prompt") if isinstance(adapter_record.get("prompt"), Mapping) else {}
    refs = adapter_record.get("asset_references") if isinstance(adapter_record.get("asset_references"), list) else []
    strong_pairings = adapter_record.get("pairings") if isinstance(adapter_record.get("pairings"), list) else []
    payload = {
        "source_case_key": adapter_record.get("source_case_key"),
        "raw_prompt": prompt.get("raw_text"),
        "assets": sorted(
            [
                {"role": item.get("role"), "content_sha256": item.get("content_sha256")}
                for item in refs
                if isinstance(item, Mapping) and item.get("resolution_state") == "resolved"
            ],
            key=lambda item: (str(item["role"]), str(item["content_sha256"])),
        ),
        "source_claim": adapter_record.get("source_claim"),
        "strong_pairings": sorted(
            [
                {"prompt_id": item.get("prompt_id"), "asset_ref_id": item.get("asset_ref_id"), "method": item.get("method")}
                for item in strong_pairings
                if isinstance(item, Mapping) and item.get("status") == "strong"
            ],
            key=lambda item: (str(item["prompt_id"]), str(item["asset_ref_id"]), str(item["method"])),
        ),
        "generation_documents": [_semantic_generation_document(document) for document in _document_list(generation_document)],
    }
    return _sha256_bytes(_canonical(payload).encode("utf-8"))


def fingerprint_map(case_documents: list[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in case_documents:
        key = item.get("source_case_key")
        adapter = item.get("adapter_record")
        generation = item.get("generation_document")
        if not isinstance(key, str) or not isinstance(adapter, Mapping) or not isinstance(generation, Mapping):
            raise RevisionError("diff_invalid", "case evidence is incomplete")
        if key in result:
            raise RevisionError("diff_invalid", "source case identity is duplicated")
        result[key] = case_fingerprint(adapter, generation)
    return dict(sorted(result.items()))


def stable_set_diff(previous: Mapping[str, str], candidate: Mapping[str, str]) -> dict[str, Any]:
    previous_keys = set(previous)
    candidate_keys = set(candidate)
    added = sorted(candidate_keys - previous_keys)
    removed = sorted(previous_keys - candidate_keys)
    shared = previous_keys & candidate_keys
    modified = sorted(key for key in shared if previous[key] != candidate[key])
    unchanged = sorted(key for key in shared if previous[key] == candidate[key])
    return {
        "added": added,
        "modified": modified,
        "removed": removed,
        "unchanged": unchanged,
        "counts": {"added": len(added), "modified": len(modified), "removed": len(removed), "unchanged": len(unchanged)},
        "candidate_fingerprints": dict(sorted(candidate.items())),
    }


def evaluate_quality_gate(
    *,
    candidate_metrics: Mapping[str, Any],
    previous_metrics: Mapping[str, Any] | None,
    diff: Mapping[str, Any],
    source: SyncSource,
) -> dict[str, Any]:
    valid_cases = candidate_metrics.get("valid_case_count")
    pair_rate = candidate_metrics.get("pair_rate")
    broken_assets = candidate_metrics.get("broken_asset_count")
    reasons: list[str] = []
    if not isinstance(valid_cases, int) or valid_cases < source.minimum_valid_cases:
        reasons.append("minimum_valid_cases")
    if not isinstance(pair_rate, (int, float)) or float(pair_rate) < source.minimum_pair_rate:
        reasons.append("minimum_pair_rate")
    if broken_assets != 0:
        reasons.append("broken_assets")
    previous_count = previous_metrics.get("valid_case_count") if isinstance(previous_metrics, Mapping) else None
    if isinstance(previous_count, int) and isinstance(valid_cases, int) and valid_cases < previous_count:
        reasons.append("case_count_decrease")
    removed = diff.get("removed")
    if isinstance(removed, list) and removed:
        reasons.append("removed_cases")
    return {
        "status": "passed" if not reasons else "review_required",
        "reasons": reasons,
        "minimum_valid_cases": source.minimum_valid_cases,
        "minimum_pair_rate": source.minimum_pair_rate,
        "candidate_valid_cases": valid_cases,
        "candidate_pair_rate": pair_rate,
        "candidate_broken_asset_count": broken_assets,
        "previous_valid_cases": previous_count,
        "automatic_case_decrease_threshold": 0,
    }
