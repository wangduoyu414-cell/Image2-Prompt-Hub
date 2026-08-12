from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import validate_phase1_closure as closure


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(path: str, root: str, base: Path) -> dict[str, str]:
    return {"root": root, "path": path, "sha256": _sha(base / path)}


def _report_fixture(repo_root: Path, run_root: Path, task_id: str, *, status: str = "complete") -> dict[str, Any]:
    receipt_path = run_root / "receipts" / "receipt.json"
    _write_json(receipt_path, {"status": "passed", "exit_code": 0})
    review_path = run_root / "review.json"
    _write_json(review_path, {"status": "passed", "authorize_complete": True, "blocking_findings": 0})
    hygiene_path = run_root / "hygiene.json"
    _write_json(hygiene_path, {"ok": True, "receipt": {"status": "passed"}})
    return {
        "card_id": task_id,
        "execution_status": status,
        "verification_status": "passed",
        "remaining_blockers": [],
        "validation_receipts": [{"status": "passed", "exit_code": 0, "receipt_ref": _ref("receipts/receipt.json", "run", run_root)}],
        "independent_review": {"status": "passed", "authorize_complete": True, "blocking_findings": 0, "receipt_ref": _ref("review.json", "run", run_root)},
        "repository_hygiene": {"status": "passed", "validator_ref": _ref("hygiene.json", "run", run_root)},
    }


def test_complete_report_rejects_missing_status_and_hash_drift(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run_root = tmp_path / "run"
    report = _report_fixture(repo_root, run_root, "TASK-X")
    _write_json(run_root / "completion-report.json", report)

    assert closure._verify_run_evidence(report, run_root=run_root, repo_root=repo_root, task_id="TASK-X") == "embedded_verification_status"

    missing = dict(report)
    missing["execution_status"] = "blocked"
    with pytest.raises(closure.ValidationFailure, match="not complete"):
        closure._verify_run_evidence(missing, run_root=run_root, repo_root=repo_root, task_id="TASK-X")

    (run_root / "receipts" / "receipt.json").write_text('{"status":"failed"}', encoding="utf-8")
    with pytest.raises(closure.ValidationFailure, match="hash does not match"):
        closure._verify_run_evidence(report, run_root=run_root, repo_root=repo_root, task_id="TASK-X")


def test_current_applicability_requires_existing_current_deliverables(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    tracked = repo_root / "tracked.txt"
    tracked.write_text("current", encoding="utf-8")
    old = {"task_id": "TASK-OLD", "report": {"changed_files": [], "evidence": [{"root": "repo", "path": "tracked.txt", "sha256": "0" * 64}]}}
    owner = {"task_id": "TASK-NEW", "report": {"changed_files": ["tracked.txt"], "evidence": [{"root": "repo", "path": "tracked.txt", "sha256": _sha(tracked)}]}}
    records = {task_id: {"task_id": task_id, "report": record["report"]} for task_id, record in {"TASK-OLD": old, "TASK-NEW": owner}.items()}
    original = closure.CANONICAL_TASKS
    try:
        closure.CANONICAL_TASKS = ("TASK-OLD", "TASK-NEW")
        assert closure._current_applicability(records, repo_root) == [
            {"path": "tracked.txt", "owner": "fresh_phase1_regression_and_live"}
        ]
        tracked.unlink()
        with pytest.raises(closure.ValidationFailure, match="deliverable is missing"):
            closure._current_applicability(records, repo_root)
    finally:
        closure.CANONICAL_TASKS = original


def test_supersession_and_zero_public_semantics_reject_misreporting() -> None:
    closure._validate_supersession_entry(
        historical_task="TASK-0015",
        historical_status="RESULT_UNKNOWN",
        expected_historical_status="RESULT_UNKNOWN",
        recovery_task="TASK-0015R",
        recovery_status="COMPLETE",
    )
    with pytest.raises(closure.ValidationFailure, match="historical status"):
        closure._validate_supersession_entry(
            historical_task="TASK-0015",
            historical_status="COMPLETE",
            expected_historical_status="RESULT_UNKNOWN",
            recovery_task="TASK-0015R",
            recovery_status="COMPLETE",
        )
    assert closure._validate_internal_public_counts(
        formal_sources=3, internal_generation_examples=312, real_public_cases=0
    )["real_public_cases"] == 0
    with pytest.raises(closure.ValidationFailure, match="count semantics"):
        closure._validate_internal_public_counts(formal_sources=3, internal_generation_examples=312, real_public_cases=312)


def test_source_payload_rejects_312_as_public_or_incomplete_fixed_counts() -> None:
    assert sum(item["cases"] for item in closure.EXPECTED_SOURCES.values()) == 312
    assert len(closure.EXPECTED_SOURCES) == 3
    bad = dict(closure.EXPECTED_SOURCES)
    bad["g0dam-work-prompts"] = {**bad["g0dam-work-prompts"], "cases": 99}
    assert sum(item["cases"] for item in bad.values()) != 312


def test_phase1_closure_documents_keep_internal_public_and_deployment_states_distinct() -> None:
    design = (Path(__file__).resolve().parents[2] / "1.md").read_text(encoding="utf-8")
    closure_doc = (Path(__file__).resolve().parents[2] / "docs" / "phase1" / "phase1-closure-v1.md").read_text(encoding="utf-8")
    for phrase in (
            "文档版本：v1.6",
            "Phase 2 七来源内部接入、案例级审核基础、Chaos 固定历史导入和认证审核后台已完成",
        "312",
        "1513",
        "1930",
        "0 real public",
    ):
        assert phrase in design
    for phrase in ("3", "312", "0 real public", "未部署", "TASK-0017R"):
        assert phrase in closure_doc
