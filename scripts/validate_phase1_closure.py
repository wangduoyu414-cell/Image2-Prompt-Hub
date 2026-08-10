"""Read-only Phase 1 evidence closure with fresh local consumer validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT_ENV = "IMAGE2_PHASE1_TASK_STATE_ROOT"
RUNTIME_ROOT_ENV = "IMAGE2_PHASE1_RUNTIME_ROOT"
DEFAULT_STATE_ROOT = Path(r"C:/Users/admin/.codex/task-state/image2")
DEFAULT_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0017R")
MIGRATION_NAME = re.compile(r"(\d{4}_[a-z0-9_]+)\.sql")

CANONICAL_TASKS = (
    "TASK-0001",
    "TASK-0002",
    "TASK-0003",
    "TASK-0004",
    "TASK-0005",
    "TASK-0007",
    "TASK-0012R",
    "TASK-0013",
    "TASK-0014",
    "TASK-0015R",
    "TASK-0016",
    "TASK-0017A",
)
HISTORICAL_SUPERSESSION = {
    "TASK-0006": ("BLOCKED", "TASK-0007"),
    "TASK-0008": ("BLOCKED", "TASK-0012R"),
    "TASK-0009": ("BLOCKED", "TASK-0012R"),
    "TASK-0010": ("BLOCKED", "TASK-0012R"),
    "TASK-0011": ("BLOCKED", "TASK-0012R"),
    "TASK-0012": ("BLOCKED", "TASK-0012R"),
    "TASK-0015": ("RESULT_UNKNOWN", "TASK-0015R"),
    "TASK-0017": ("BLOCKED", "TASK-0017R"),
}
CURRENT_RECOVERY_TASK = "TASK-0017R"
CLOSURE_OWNED_PATHS = {
    "1.md",
    "scripts/validate_phase1_closure.py",
    "tests/phase1/test_phase1_closure.py",
    "docs/phase1/phase1-closure-v1.md",
}
EXPECTED_SOURCES = {
    "g0dam-work-prompts": {
        "commit": "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "cases": 100,
        "aggregate": "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0",
    },
    "joesai-commercial-prompts": {
        "commit": "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b",
        "cases": 50,
        "aggregate": "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293",
    },
    "conardli-gpt-image-2-101": {
        "commit": "971b67dc8cbca8cf6eb32e196fea04bddd6abe99",
        "cases": 162,
        "aggregate": "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573",
    },
}

class ValidationFailure(RuntimeError):
    """Fail-closed conclusion for the Phase 1 closure boundary."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"invalid required JSON evidence: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValidationFailure(f"required JSON evidence is not an object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValidationFailure(f"required evidence is unreadable: {path.name}") from exc


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationFailure(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationFailure(f"{label} must be an array")
    return value


def _safe_relative_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValidationFailure(f"{label} must be a non-empty relative path")
    relative = Path(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationFailure(f"{label} escapes its evidence root")
    return relative


def _external_root(value: Path, label: str) -> Path:
    resolved = value.expanduser().resolve(strict=False)
    workspace = REPO_ROOT.resolve()
    if resolved == workspace or workspace in resolved.parents:
        raise ValidationFailure(f"{label} must be outside the workspace")
    return resolved


def _state_root() -> Path:
    raw = os.environ.get(STATE_ROOT_ENV) or os.environ.get("CODEX_TASK_STATE_ROOT")
    return _external_root(Path(raw) if raw else DEFAULT_STATE_ROOT, "Phase 1 task-state root")


def _runtime_root() -> Path:
    raw = os.environ.get(RUNTIME_ROOT_ENV)
    root = _external_root(Path(raw) if raw else DEFAULT_RUNTIME_ROOT, "Phase 1 runtime root")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _find_task_roots(state_root: Path, task_id: str) -> list[Path]:
    roots: list[Path] = []
    for root in sorted(state_root.glob(f"{task_id}-*")):
        state_path = root / "run-state.json"
        if not root.is_dir() or not state_path.is_file():
            continue
        state = _load_json(state_path)
        if state.get("task_id") == task_id:
            roots.append(root)
    return roots


def _single_task_root(state_root: Path, task_id: str) -> Path:
    roots = _find_task_roots(state_root, task_id)
    if len(roots) != 1:
        raise ValidationFailure(f"{task_id} must have exactly one canonical task run")
    return roots[0]


def _resolve_reference(reference: Mapping[str, Any], *, run_root: Path, repo_root: Path, label: str) -> Path:
    root_name = reference.get("root")
    relative = _safe_relative_path(reference.get("path"), f"{label}.path")
    if root_name == "run":
        base = run_root.resolve()
    elif root_name == "repo":
        base = repo_root.resolve()
    else:
        raise ValidationFailure(f"{label}.root is not trusted")
    resolved = (base / relative).resolve(strict=False)
    if resolved != base and base not in resolved.parents:
        raise ValidationFailure(f"{label} escapes its trusted root")
    if not resolved.is_file():
        raise ValidationFailure(f"{label} is missing")
    expected = reference.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or _sha256(resolved) != expected.lower():
        raise ValidationFailure(f"{label} hash does not match")
    return resolved


def _all_repo_references(value: object) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get("root") == "repo" and {"path", "sha256"}.issubset(value):
            found.append(value)
        for nested in value.values():
            found.extend(_all_repo_references(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_all_repo_references(nested))
    return found


def _verify_run_evidence(report: Mapping[str, Any], *, run_root: Path, repo_root: Path, task_id: str) -> str:
    if report.get("card_id") != task_id:
        raise ValidationFailure(f"{task_id} Completion Report card identity does not match")
    if report.get("execution_status") != "complete" or report.get("verification_status") != "passed":
        raise ValidationFailure(f"{task_id} Completion Report is not complete and verified")
    if report.get("remaining_blockers") != []:
        raise ValidationFailure(f"{task_id} Completion Report still has blockers")

    receipts = _require_list(report.get("validation_receipts"), f"{task_id}.validation_receipts")
    if not receipts:
        raise ValidationFailure(f"{task_id} Completion Report has no validation receipts")
    for index, entry in enumerate(receipts):
        receipt_entry = _require_mapping(entry, f"{task_id}.validation_receipts[{index}]")
        if receipt_entry.get("status") != "passed" or receipt_entry.get("exit_code") != 0:
            raise ValidationFailure(f"{task_id} Completion Report cites a non-passing validator")
        receipt_path = _resolve_reference(
            _require_mapping(receipt_entry.get("receipt_ref"), f"{task_id}.receipt_ref"),
            run_root=run_root,
            repo_root=repo_root,
            label=f"{task_id}.receipt_ref",
        )
        receipt = _load_json(receipt_path)
        if receipt.get("status") != "passed" or receipt.get("exit_code") != 0:
            raise ValidationFailure(f"{task_id} receipt is not a passed terminal result")

    review = _require_mapping(report.get("independent_review"), f"{task_id}.independent_review")
    if review.get("status") != "passed" or review.get("authorize_complete") is not True or review.get("blocking_findings") != 0:
        raise ValidationFailure(f"{task_id} independent review is not a clean pass")
    review_path = _resolve_reference(
        _require_mapping(review.get("receipt_ref"), f"{task_id}.independent_review.receipt_ref"),
        run_root=run_root,
        repo_root=repo_root,
        label=f"{task_id}.independent_review.receipt_ref",
    )
    review_receipt = _load_json(review_path)
    if review_receipt.get("status") != "passed" or review_receipt.get("blocking_findings") != 0:
        raise ValidationFailure(f"{task_id} semantic review receipt is not a clean pass")

    hygiene = _require_mapping(report.get("repository_hygiene"), f"{task_id}.repository_hygiene")
    if hygiene.get("status") != "passed":
        raise ValidationFailure(f"{task_id} repository hygiene did not pass")
    hygiene_path = _resolve_reference(
        _require_mapping(hygiene.get("validator_ref"), f"{task_id}.repository_hygiene.validator_ref"),
        run_root=run_root,
        repo_root=repo_root,
        label=f"{task_id}.repository_hygiene.validator_ref",
    )
    hygiene_result = _load_json(hygiene_path)
    receipt = _require_mapping(hygiene_result.get("receipt"), f"{task_id}.repository_hygiene.receipt")
    if hygiene_result.get("ok") is not True or receipt.get("status") != "passed":
        raise ValidationFailure(f"{task_id} repository hygiene receipt is not a pass")

    report_validation = run_root / "completion-report-validation.json"
    if report_validation.is_file():
        validation = _load_json(report_validation)
        if validation.get("ok") is not True or validation.get("errors") not in ([], None):
            raise ValidationFailure(f"{task_id} stored Completion Report validation did not pass")
        return "stored_validation"
    return "embedded_verification_status"


def _load_complete_record(state_root: Path, repo_root: Path, task_id: str) -> dict[str, Any]:
    run_root = _single_task_root(state_root, task_id)
    state = _load_json(run_root / "run-state.json")
    if state.get("status") != "COMPLETE" or state.get("stage") != "FINALIZE":
        raise ValidationFailure(f"{task_id} canonical run is not COMPLETE/FINALIZE")
    report_path = run_root / "completion-report.json"
    if not report_path.is_file():
        raise ValidationFailure(f"{task_id} canonical Completion Report is missing")
    report = _load_json(report_path)
    validation_mode = _verify_run_evidence(report, run_root=run_root, repo_root=repo_root, task_id=task_id)
    return {
        "task_id": task_id,
        "run_root": run_root,
        "state": state,
        "report": report,
        "report_path": report_path,
        "report_sha256": _sha256(report_path),
        "report_validation": validation_mode,
    }


def _current_reference_hash(repo_root: Path, relative: Path) -> str:
    path = (repo_root / relative).resolve(strict=False)
    root = repo_root.resolve()
    if path != root and root not in path.parents:
        raise ValidationFailure("report reference escapes current workspace")
    if not path.is_file():
        raise ValidationFailure(f"current report deliverable is missing: {relative.as_posix()}")
    return _sha256(path)


def _current_applicability(records: Mapping[str, Mapping[str, Any]], repo_root: Path) -> list[dict[str, str]]:
    substitutions: list[dict[str, str]] = []
    for task_id in CANONICAL_TASKS:
        report = records[task_id]["report"]
        for ref in _all_repo_references(report):
            relative = _safe_relative_path(ref.get("path"), f"{task_id}.repo_ref.path")
            relative_text = relative.as_posix()
            expected_hash = ref.get("sha256")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise ValidationFailure(f"{task_id} repository reference has no valid hash")
            actual_hash = _current_reference_hash(repo_root, relative)
            if actual_hash == expected_hash.lower():
                continue
            if relative_text.startswith("tasks/"):
                raise ValidationFailure(f"{task_id} report task-card authority has changed")
            owner = CURRENT_RECOVERY_TASK if relative_text in CLOSURE_OWNED_PATHS else "fresh_phase1_regression_and_live"
            substitutions.append({"path": relative_text, "owner": owner})
    return [{"path": path, "owner": owner} for path, owner in sorted({(item["path"], item["owner"]) for item in substitutions})]


def _supersession_audit(state_root: Path, records: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for historical_task, (expected_status, recovery_task) in HISTORICAL_SUPERSESSION.items():
        root = _single_task_root(state_root, historical_task)
        state = _load_json(root / "run-state.json")
        if recovery_task == CURRENT_RECOVERY_TASK:
            recovery_root = _single_task_root(state_root, recovery_task)
            recovery_state = _load_json(recovery_root / "run-state.json")
            if recovery_state.get("status") not in {"ACTIVE", "COMPLETE"}:
                raise ValidationFailure("TASK-0017R recovery run is not available to close the historical blocker")
            recovery_status = str(recovery_state.get("status"))
        else:
            recovery_status = str(records[recovery_task]["state"].get("status"))
        _validate_supersession_entry(
            historical_task=historical_task,
            historical_status=state.get("status"),
            expected_historical_status=expected_status,
            recovery_task=recovery_task,
            recovery_status=recovery_status,
        )
        results.append(
            {
                "historical_task": historical_task,
                "historical_status": expected_status,
                "recovery_task": recovery_task,
                "recovery_status": recovery_status,
            }
        )
    return results


def _validate_supersession_entry(
    *,
    historical_task: str,
    historical_status: object,
    expected_historical_status: str,
    recovery_task: str,
    recovery_status: str,
) -> None:
    if historical_status != expected_historical_status:
        raise ValidationFailure(f"{historical_task} historical status does not preserve its recorded outcome")
    expected_target = HISTORICAL_SUPERSESSION.get(historical_task, (None, None))[1]
    if recovery_task != expected_target:
        raise ValidationFailure(f"{historical_task} supersession target is not authoritative")
    accepted = {"ACTIVE", "COMPLETE"} if recovery_task == CURRENT_RECOVERY_TASK else {"COMPLETE"}
    if recovery_status not in accepted:
        raise ValidationFailure(f"{historical_task} recovery task is not available")


def _receipt_payload(record: Mapping[str, Any], validator_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    report = _require_mapping(record["report"], "record.report")
    for entry in _require_list(report.get("validation_receipts"), "record.validation_receipts"):
        candidate = _require_mapping(entry, "record.validation_receipt")
        if candidate.get("name") != validator_name:
            continue
        receipt_path = _resolve_reference(
            _require_mapping(candidate.get("receipt_ref"), "record.receipt_ref"),
            run_root=Path(record["run_root"]),
            repo_root=REPO_ROOT,
            label=f"{validator_name}.receipt_ref",
        )
        receipt = _load_json(receipt_path)
        if receipt.get("status") != "passed" or receipt.get("exit_code") != 0:
            raise ValidationFailure(f"{validator_name} is not a passed terminal receipt")
        stdout_ref = receipt.get("stdout_reference")
        if not isinstance(stdout_ref, Mapping):
            raise ValidationFailure(f"{validator_name} is missing bounded stdout evidence")
        stdout_path = _resolve_reference(
            stdout_ref,
            run_root=Path(record["run_root"]),
            repo_root=REPO_ROOT,
            label=f"{validator_name}.stdout_reference",
        )
        return receipt, _load_json(stdout_path)
    raise ValidationFailure(f"required historical validator is missing: {validator_name}")


def _expect_boolean(value: object, label: str) -> None:
    if value is not True:
        raise ValidationFailure(f"{label} must be true")


def _source_audit(record: Mapping[str, Any]) -> dict[str, Any]:
    receipt, payload = _receipt_payload(record, "three-source-cache-recovery-live")
    if payload.get("status") != "passed":
        raise ValidationFailure("TASK-0012R source validator payload did not pass")
    extractions = _require_mapping(payload.get("extractions"), "source.extractions")
    per_run = _require_mapping(payload.get("per_run_counts"), "source.per_run_counts")
    argv = receipt.get("argv")
    if not isinstance(argv, list):
        raise ValidationFailure("TASK-0012R source receipt command is missing")
    command_text = " ".join(str(item) for item in argv)
    for source_id, expected in EXPECTED_SOURCES.items():
        extraction = _require_mapping(extractions.get(source_id), f"source.extractions.{source_id}")
        counts = _require_mapping(per_run.get(source_id), f"source.per_run_counts.{source_id}")
        if extraction.get("commit") != expected["commit"] or extraction.get("case_count") != expected["cases"]:
            raise ValidationFailure(f"{source_id} fixed source identity/count does not close")
        if extraction.get("independent_second_status") != "published" or extraction.get("same_key_replay_status") != "verified_existing":
            raise ValidationFailure(f"{source_id} did not prove two runs and replay")
        if counts.get("generation_examples") != expected["cases"]:
            raise ValidationFailure(f"{source_id} internal generation count does not close")
        if expected["aggregate"] not in command_text:
            raise ValidationFailure(f"{source_id} fixed aggregate is absent from its fresh source command")
    global_counts = _require_mapping(payload.get("global_database_counts"), "source.global_database_counts")
    if global_counts.get("source_files") != 528 or global_counts.get("source_cases") != 312 or global_counts.get("generation_examples") != 312:
        raise ValidationFailure("TASK-0012R global 528/312 source closure does not hold")
    if payload.get("object_download_hash_count") != 312:
        raise ValidationFailure("TASK-0012R did not download-hash all 312 immutable objects")
    if payload.get("replay_statuses") != {source_id: "verified_existing" for source_id in EXPECTED_SOURCES}:
        raise ValidationFailure("TASK-0012R inventory replay closure does not hold")
    _expect_boolean(payload.get("rights_publication_fail_closed"), "source rights/publication fail-closed")
    _expect_boolean(payload.get("temporary_runtime_cleaned"), "source temporary runtime cleanup")
    _expect_boolean(payload.get("compose_cleanup"), "source Compose cleanup")
    cache = _require_mapping(payload.get("source_snapshot_cache"), "source.snapshot_cache")
    source_ids = list(EXPECTED_SOURCES)
    if cache.get("prewarmed_source_ids") != source_ids or cache.get("retained_mirror_source_ids") != source_ids:
        raise ValidationFailure("TASK-0012R persistent source mirror evidence is incomplete")
    _expect_boolean(cache.get("temporary_worktrees_cleaned"), "source temporary worktree cleanup")
    concurrency = _require_mapping(payload.get("conardli_failure_and_concurrency"), "source.concurrency")
    if concurrency.get("concurrent_second_status") != "run_locked" or len(_require_mapping(concurrency.get("failure_codes"), "source.failure_codes")) != 5:
        raise ValidationFailure("TASK-0012R failure/concurrency evidence is incomplete")
    return {
        "sources": {source_id: {"commit": expected["commit"], "cases": expected["cases"]} for source_id, expected in EXPECTED_SOURCES.items()},
        "source_files": 528,
        "internal_generation_examples": 312,
        "download_hashes": 312,
        "two_runs_replay_rights_cleanup": True,
    }


def _sync_audit(record: Mapping[str, Any]) -> dict[str, Any]:
    _receipt, payload = _receipt_payload(record, "incremental-sync-live")
    if payload.get("status") != "passed":
        raise ValidationFailure("TASK-0016 sync payload did not pass")
    sources = _require_mapping(payload.get("sources"), "sync.sources")
    if set(sources) != set(EXPECTED_SOURCES):
        raise ValidationFailure("TASK-0016 did not prove all three source sync chains")
    for source_id, source in sources.items():
        facts = _require_mapping(source, f"sync.sources.{source_id}")
        if facts.get("baseline_status") != "completed" or facts.get("first_update_status") != "completed" or facts.get("no_change") != "no_change":
            raise ValidationFailure(f"TASK-0016 sync state is incomplete for {source_id}")
    recovery = _require_mapping(payload.get("g0dam_recovery"), "sync.g0dam_recovery")
    for field in ("concurrency_rejected_second_writer", "git_import_build_activation_failures_preserved_current", "public_loss_blocked", "rights_not_inherited", "tombstone_recorded"):
        _expect_boolean(recovery.get(field), f"sync {field}")
    _expect_boolean(payload.get("object_reuse_and_new_object_once"), "sync object reuse")
    if payload.get("object_download_hash_count") != 9:
        raise ValidationFailure("TASK-0016 object download-hash evidence is incomplete")
    _expect_boolean(payload.get("temporary_runtime_cleaned"), "sync temporary runtime cleanup")
    _expect_boolean(payload.get("compose_cleanup"), "sync Compose cleanup")
    return {
        "adapter_sources": sorted(sources),
        "state_matrix": "baseline/update/no_change",
        "concurrency_rights_public_loss": True,
        "object_download_hashes": 9,
        "cleanup": True,
    }


def _repository_migration_manifest() -> list[dict[str, str]]:
    migrations: list[dict[str, str]] = []
    for path in sorted((REPO_ROOT / "migrations").glob("*.sql")):
        match = MIGRATION_NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            raise ValidationFailure("repository migration manifest is invalid")
        migrations.append({"version": match.group(1), "checksum_sha256": _sha256(path)})
    if not migrations:
        raise ValidationFailure("repository migration manifest is empty")
    return migrations


def _validate_live_migrations(payload: Mapping[str, Any], label: str, expected: Sequence[Mapping[str, str]]) -> list[str]:
    migrations = _require_mapping(payload.get("migrations"), f"{label}.migrations")
    selected: list[str] = []
    for phase, allowed in (("first", {"applied", "verified_existing"}), ("replay", {"verified_existing"})):
        actual = _require_list(migrations.get(phase), f"{label}.migrations.{phase}")
        if len(actual) != len(expected):
            raise ValidationFailure(f"{label} {phase} migration count does not match repository manifest")
        for index, (entry, authority) in enumerate(zip(actual, expected, strict=True)):
            actual_entry = _require_mapping(entry, f"{label}.migrations.{phase}[{index}]")
            if actual_entry.get("version") != authority["version"] or actual_entry.get("checksum_sha256") != authority["checksum_sha256"]:
                raise ValidationFailure(f"{label} {phase} migration manifest mismatch")
            if actual_entry.get("status") not in allowed:
                raise ValidationFailure(f"{label} {phase} migration status is not accepted")
            if phase == "replay":
                selected.append(str(actual_entry["version"]))
    return selected


def _run_json_child(label: str, command: list[str], environment: Mapping[str, str], timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, cwd=str(REPO_ROOT), env=dict(environment), capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValidationFailure(f"{label} child validator timed out") from exc
    except OSError as exc:
        raise ValidationFailure(f"{label} child validator could not start") from exc
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f"{label} child validator did not emit one JSON object") from exc
    if not isinstance(payload, dict):
        raise ValidationFailure(f"{label} child validator emitted a non-object result")
    if completed.returncode != 0 or payload.get("status") != "passed":
        error_type = payload.get("error_type")
        if not isinstance(error_type, str) or not error_type:
            error_type = "child_failure"
        raise ValidationFailure(f"{label} child validator failed with {error_type}")
    return payload


def _validator_environment(runtime_task: str) -> dict[str, str]:
    root = Path(r"C:/Users/admin/.codex/runtime/image2") / runtime_task
    return {
        **os.environ,
        "UV_PROJECT_ENVIRONMENT": str(root / "venv"),
        "UV_CACHE_DIR": str(root / "uv-cache"),
        "TMP": str(root / "tmp"),
        "TEMP": str(root / "tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _remove_owned_runtime(path: Path, parent: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_parent = parent.resolve(strict=False)
    if resolved_parent not in resolved_path.parents:
        raise ValidationFailure("Phase 1 browser cleanup target is outside its owned runtime root")
    if resolved_path.exists():
        shutil.rmtree(resolved_path)
    return not resolved_path.exists()


def _child_live_audit() -> dict[str, Any]:
    expected_migrations = _repository_migration_manifest()
    content = _run_json_child(
        "Content Core",
        ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_content_core.py", "--json"],
        _validator_environment("TASK-0013"),
        600,
    )
    content_versions = _validate_live_migrations(content, "Content Core", expected_migrations)
    if content.get("default_zero_publication", {}).get("included_count") != 0:
        raise ValidationFailure("Content Core default publication is not zero-public")
    for field in ("future_review_rejected", "immutable_guards", "temporary_runtime_cleaned", "compose_cleanup"):
        _expect_boolean(content.get(field), f"Content Core {field}")

    api = _run_json_child(
        "Public API",
        ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_public_api.py", "--json"],
        _validator_environment("TASK-0014"),
        600,
    )
    api_versions = _validate_live_migrations(api, "Public API", expected_migrations)
    cleanup = _require_mapping(api.get("cleanup"), "Public API cleanup")
    _expect_boolean(cleanup.get("runtime"), "Public API runtime cleanup")
    _expect_boolean(cleanup.get("compose"), "Public API Compose cleanup")
    http = _require_mapping(api.get("http"), "Public API http")
    for field in ("current_pointer_switch", "public_loss_guard", "authorized_image_headers_and_bytes", "link_only_unknown_no_storage_read", "hash_and_media_integrity_fail_closed", "openapi_read_only"):
        _expect_boolean(http.get(field), f"Public API {field}")

    base = _runtime_root()
    web_runtime = base / f"phase1-web-{uuid.uuid4().hex}"
    web_runtime.mkdir(parents=True, exist_ok=False)
    web_cleanup = False
    try:
        web_environment = {
            **os.environ,
            "IMAGE2_WEB_RUNTIME_ROOT": str(web_runtime),
            "IMAGE2_WEB_EVIDENCE_DIR": str(web_runtime / "browser-evidence"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        web = _run_json_child(
            "Public Web",
            ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_public_web.py", "--json"],
            web_environment,
            900,
        )
        if web.get("topology") != "synthetic API -> production Next -> local Chromium":
            raise ValidationFailure("Public Web topology evidence is not the required production browser path")
        browser = _require_mapping(web.get("browser"), "Public Web browser")
        for field in ("copy_exact", "copy_denial_safe", "link_only_asset_request", "authorized_asset_request", "mobile_keyboard"):
            expected_value = False if field == "link_only_asset_request" else True
            if browser.get(field) is not expected_value:
                raise ValidationFailure(f"Public Web {field} did not close")
        if browser.get("status") != "passed" or browser.get("screenshots") != 5:
            raise ValidationFailure("Public Web browser evidence is incomplete")
        api_evidence = _require_mapping(web.get("api"), "Public Web api")
        if api_evidence.get("canonical_cases") != 2 or api_evidence.get("link_only_asset_request") is not False or api_evidence.get("authorized_asset_request") is not True:
            raise ValidationFailure("Public Web API-only asset boundary did not close")
    finally:
        web_cleanup = _remove_owned_runtime(web_runtime, base)
    if not web_cleanup:
        raise ValidationFailure("Public Web owned runtime cleanup did not complete")

    return {
        "migration_versions": content_versions,
        "content_core": {"zero_default_publication": True, "cleanup": True},
        "public_api": {"current_only_assets": True, "public_loss_guard": True, "cleanup": True},
        "public_web": {"copy_exact": True, "link_only_no_asset_request": True, "browser_runtime_cleaned": True},
    }


def _docker_cleanup_audit() -> dict[str, bool]:
    try:
        containers = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}} {{.Labels}}"], capture_output=True, text=True, check=False, timeout=60
        )
        volumes = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}} {{.Labels}}"], capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationFailure("Docker cleanup audit could not run") from exc
    if containers.returncode != 0 or volumes.returncode != 0:
        raise ValidationFailure("Docker cleanup audit did not complete")
    prefixes = ("task0013", "task0014", "phase1-web", "live-content-core", "live-public-api", "public-web")
    if any(any(prefix in line for prefix in prefixes) for line in containers.stdout.splitlines()):
        raise ValidationFailure("Phase 1 child Compose container residue remains")
    if any(any(prefix in line for prefix in prefixes) for line in volumes.stdout.splitlines()):
        raise ValidationFailure("Phase 1 child Compose volume residue remains")
    return {"compose_containers": True, "compose_volumes": True, "browser_runtime": True}


def _documentation_audit() -> dict[str, str]:
    design = (REPO_ROOT / "1.md").read_text(encoding="utf-8")
    closure = (REPO_ROOT / "docs" / "phase1" / "phase1-closure-v1.md").read_text(encoding="utf-8")
    for phrase in ("文档版本：v1.1", "更新日期：2026-08-08", "文档状态：Phase 1 已完成；Phase 2 待启动", "312", "0 real public"):
        if phrase not in design:
            raise ValidationFailure("1.md does not state the verified Phase 1 status")
    for phrase in ("3", "312", "0 real public", "未部署", "TASK-0017R"):
        if phrase not in closure:
            raise ValidationFailure("Phase 1 closure document is incomplete")
    return {"design_document": "v1.1 Phase 1 complete", "closure_document": "current evidence documented"}


def _validate_internal_public_counts(*, formal_sources: int, internal_generation_examples: int, real_public_cases: int) -> dict[str, Any]:
    if formal_sources != 3 or internal_generation_examples != 312 or real_public_cases != 0:
        raise ValidationFailure("Phase 1 internal/public count semantics do not close")
    return {
        "formal_sources": formal_sources,
        "internal_generation_examples": internal_generation_examples,
        "real_human_rights_approvals": 0,
        "real_public_cases": real_public_cases,
        "meaning": "312 internal Generation Examples are not public cases",
    }


def audit_phase1(*, state_root: Path | None = None, repo_root: Path = REPO_ROOT, run_children: bool = True) -> dict[str, Any]:
    """Return the machine closure result or raise without changing historical evidence."""

    root = _external_root(state_root or _state_root(), "Phase 1 task-state root")
    if not root.is_dir():
        raise ValidationFailure("Phase 1 task-state root is unavailable")
    records = {task_id: _load_complete_record(root, repo_root, task_id) for task_id in CANONICAL_TASKS}
    substitutions = _current_applicability(records, repo_root)
    supersession = _supersession_audit(root, records)
    source = _source_audit(records["TASK-0012R"])
    sync = _sync_audit(records["TASK-0016"])
    live = _child_live_audit() if run_children else {"skipped": "unit_test"}
    documentation = _documentation_audit()
    cleanup = _docker_cleanup_audit() if run_children else {"skipped": "unit_test"}
    return {
        "status": "passed",
        "canonical_reports": [
            {"task_id": task_id, "report_sha256": str(records[task_id]["report_sha256"]), "validation": str(records[task_id]["report_validation"])}
            for task_id in CANONICAL_TASKS
        ],
        "current_applicability": {"status": "passed", "successor_owners": substitutions},
        "supersession": supersession,
        "source_evidence": source,
        "sync_evidence": sync,
        "internal_public_counts": _validate_internal_public_counts(
            formal_sources=len(EXPECTED_SOURCES), internal_generation_examples=int(source["internal_generation_examples"]), real_public_cases=0
        ),
        "live_consumers": live,
        "documentation": documentation,
        "cleanup": cleanup,
        "deployment": "not_deployed",
        "gates": {"GATE-001": "passed", "GATE-002": "passed", "GATE-003": "passed"},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit and fresh-validate the Phase 1 closure.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = audit_phase1()
    except (ValidationFailure, OSError, subprocess.TimeoutExpired) as exc:
        payload = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
