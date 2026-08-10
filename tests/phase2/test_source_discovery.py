from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import validate_phase2_source_discovery as validator


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(index: int, source_id: str | None = None) -> dict[str, Any]:
    name = source_id or f"new-source-{index:02d}"
    return {
        "source_id": name,
        "candidate_key": f"owner{index}/repo{index}",
        "repository_id": 10_000 + index,
        "url": f"https://github.com/owner{index}/repo{index}",
        "default_branch": "main",
        "fixed_commit_sha": f"{index + 1:040x}",
        "status": "triaged",
        "classification": "case_source",
        "reason": "fixture candidate",
        "archived": False,
        "pushed_at": "2026-08-01T00:00:00Z",
        "license": "MIT",
        "tree": {"blob_count": 100, "image_blob_count": 60, "text_blob_count": 10},
    }


def _audit(candidate: dict[str, Any], index: int, *, ready: bool) -> dict[str, Any]:
    source_id = candidate["source_id"]
    unique = 100 + index
    sample = min(unique, 50, max(20, __import__("math").ceil(unique * 0.10)))
    record_ids = [f"case-{index}-{item}" for item in range(unique)]
    sample_ids = [f"{record_ids[item]}|images/{record_ids[item]}.jpg" for item in range(sample)] if ready else []
    return {
        "source_id": source_id,
        "candidate_key": candidate["candidate_key"],
        "repository_id": candidate["repository_id"],
        "url": candidate["url"],
        "fixed_commit_sha": candidate["fixed_commit_sha"],
        "family_id": f"family-{source_id}",
        "canonical_source_id": source_id,
        "family_role": "canonical",
        "status": "adapter_ready" if ready else "probation",
        "status_reason": "fixture full audit",
        "structure_type": "structured_prompt_image_gallery",
        "recommended_adapter_strategy": f"fixture_adapter_{index}" if ready else None,
        "metrics": {
            "observed_case_count": unique,
            "exact_prompt_count": unique,
            "paired_output_count": unique,
            "valid_case_count": unique,
            "unique_valid_case_count": unique,
            "pair_rate": 1.0,
            "image_reference_count": unique,
            "broken_asset_count": 0,
            "broken_asset_rate": 0.0,
            "duplicate_count": 0,
            "duplicate_rate": 0.0,
        },
        "maintenance": {
            "latest_substantive_update": "2026-08-01",
            "substantive_update_dates_365": 3 if ready else 1,
            "eligible": ready,
            "evidence_commits": [f"{200 + index:040x}", f"{300 + index:040x}"] if ready else [f"{200 + index:040x}"],
        },
        "rights": {
            "repository_license": "MIT",
            "prompt_policy": "review_required",
            "asset_policy": "review_required",
            "public_eligibility": "review_required",
            "auto_publish": False,
        },
        "quality_sampling": {
            "sample_size": sample if ready else 0,
            "terminal_asset_checks": sample if ready else 0,
            "result": "pass" if ready else "not_run_gate_failed",
            "finding": "fixture quality result",
            "selection_method": "fixture deterministic selection" if ready else "not_run_gate_failed",
            "sample_ids": sample_ids,
            "terminal_results": [
                {"case_id": case_id, "asset_path": case_id.split("|", 1)[1], "asset_sha256": f"{500 + item:064x}", "status": "readable"}
                for item, case_id in enumerate(sample_ids)
            ],
            "sample_ids_sha256": hashlib.sha256("\n".join(sample_ids).encode()).hexdigest() if ready else None,
        },
        "evidence": {
            "tree_blob_count": 200,
            "image_blob_count": unique,
            "case_coverage_method": "fixture full coverage",
            "fixed_source_paths": ["data/cases.json"],
            "maintenance_method": "fixture commit history",
            "record_ids": record_ids,
            "record_ids_sha256": hashlib.sha256("\n".join(record_ids).encode()).hexdigest(),
            "asset_terminal_summary": {
                "checked_reference_count": unique,
                "readable_reference_count": unique,
                "broken_reference_count": 0,
                "method": "fixture fixed-tree resolution",
            },
        },
    }


def _fixture(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    repo = tmp_path / "repo"
    phase1_records = [{"candidate_key": f"old/record-{index}"} for index in range(8)]
    _write(repo / "reports" / "source-audit-v1.json", {"records": phase1_records})
    _write(repo / "config" / "sources-v1.yaml", {"sources": []})
    probation = sorted(validator.EXPECTED_PROBATION)
    existing = [_candidate(index + 100, source_id) for index, source_id in enumerate(probation)]
    new = [_candidate(index) for index in range(20)]
    audits = [_audit(new[index], index, ready=index < 3) for index in range(8)]
    batch = [
        {
            "rank": index + 1,
            "source_id": audit["source_id"],
            "fixed_commit_sha": audit["fixed_commit_sha"],
            "unique_valid_case_count": audit["metrics"]["unique_valid_case_count"],
            "recommended_adapter_strategy": audit["recommended_adapter_strategy"],
            "public_eligibility": "review_required",
        }
        for index, audit in enumerate(audits[:3])
    ]
    for path in (repo / "reports" / "phase2" / "source-discovery-v1.md", repo / "docs" / "phase2" / "source-expansion-admission-v1.md"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(item["source_id"] for item in batch) + "\n312 internal\n0 real public\nTASK-0019\n", encoding="utf-8")
    payload = {
        "schema_version": "phase2-source-discovery-v1",
        "generated_at": "2026-08-09T00:00:00Z",
        "authority": {
            "phase1_audit_sha256": _sha(repo / "reports" / "source-audit-v1.json"),
            "phase1_registry_sha256": _sha(repo / "config" / "sources-v1.yaml"),
            "phase1_active_sources": 3,
            "phase1_internal_cases": 312,
            "phase1_real_public_cases": 0,
        },
        "thresholds": {
            "minimum_unique_valid_cases": 50,
            "minimum_pair_rate": 0.9,
            "maximum_broken_asset_rate": 0.05,
            "maximum_duplicate_rate": 0.2,
            "latest_substantive_update_days": 180,
            "minimum_substantive_update_dates_365": 2,
        },
        "discovery": {
            "executed_at": "2026-08-09T00:00:00Z",
            "query_runs": [
                {"query_id": f"Q-{index:02d}", "query": f"query {index}", "method": "github_search_api", "total_count": 100, "incomplete_results": False}
                for index in range(1, 6)
            ],
            "existing_probation_refresh": existing,
            "additional_phase1_refresh": [],
            "new_candidates": new,
        },
        "full_audits": audits,
        "adapter_ready_batch": batch,
        "summary": {
            "existing_probation_count": 8,
            "new_candidate_count": 20,
            "full_audit_count": 8,
            "adapter_ready_count": 3,
            "adapter_ready_unique_cases": sum(item["metrics"]["unique_valid_case_count"] for item in audits[:3]),
            "phase1_files_modified": False,
            "real_public_cases": 0,
        },
    }
    return payload, repo


def test_semantic_fixture_closes_discovery_audit_and_handoff(tmp_path: Path) -> None:
    payload, repo = _fixture(tmp_path)
    summary = validator._semantic_validate(payload, repo)
    assert summary == {
        "query_runs": 5,
        "existing_probation": 8,
        "additional_phase1_refresh": 0,
        "new_candidates": 20,
        "full_audits": 8,
        "adapter_ready": 3,
        "adapter_ready_unique_cases": 303,
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload["discovery"]["new_candidates"].pop(), "below 20"),
        (lambda payload: payload["full_audits"][0]["metrics"].update({"pair_rate": 0.5}), "arithmetically reproducible"),
        (lambda payload: payload["full_audits"][0]["maintenance"].update({"eligible": False}), "maintenance evidence"),
        (lambda payload: payload["full_audits"][0]["maintenance"].update({"latest_substantive_update": "2000-01-01"}), "recency threshold"),
        (lambda payload: payload["full_audits"][0]["quality_sampling"].update({"sample_ids_sha256": None}), "sample digest"),
        (lambda payload: payload["full_audits"][0].update({"candidate_key": "missing/upstream"}), "no discovery upstream"),
        (lambda payload: payload["full_audits"][0]["rights"].update({"public_eligibility": "blocked"}), "rights/publication"),
        (lambda payload: payload["adapter_ready_batch"].pop(), "exactly match"),
    ],
)
def test_fail_closed_mutations(tmp_path: Path, mutate: Any, message: str) -> None:
    payload, repo = _fixture(tmp_path)
    mutate(payload)
    with pytest.raises(validator.ValidationFailure, match=message):
        validator._semantic_validate(payload, repo)


def test_phase1_authority_and_repository_identity_drift_are_rejected(tmp_path: Path) -> None:
    payload, repo = _fixture(tmp_path)
    (repo / "config" / "sources-v1.yaml").write_text("changed", encoding="utf-8")
    with pytest.raises(validator.ValidationFailure, match="authority hash changed"):
        validator._semantic_validate(payload, repo)

    payload, repo = _fixture(tmp_path / "second")
    payload["discovery"]["new_candidates"][1]["repository_id"] = payload["discovery"]["new_candidates"][0]["repository_id"]
    with pytest.raises(validator.ValidationFailure, match="identity is duplicated"):
        validator._semantic_validate(payload, repo)


def test_checked_in_report_passes_schema_and_offline_semantics() -> None:
    result = validator.validate(
        validator.REPO_ROOT / "reports" / "phase2" / "source-discovery-v1.json",
        validator.REPO_ROOT / "schemas" / "phase2-source-discovery-v1.schema.json",
        live=False,
        determinism_check=True,
    )
    assert result["status"] == "passed"
    assert result["summary"]["adapter_ready"] >= 3
    assert result["summary"]["new_candidates"] >= 20
