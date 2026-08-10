"""Environment-sensitive, fixed-commit validator for TASK-0003.

The validator intentionally writes its mirror, detached worktrees, temporary
packages, locks, and test output only below the externally configured runtime
root.  It reads the historical TASK-0001 evidence but never mutates it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.pipeline import ExtractionError, extract, verify_published_package
from ingestion.registry import load_source_config


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0003")
EXPECTED_AGGREGATE = "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0"
METRIC_KEYS = (
    "observed_case_count",
    "exact_prompt_count",
    "paired_output_count",
    "valid_case_count",
    "unique_valid_case_count",
    "broken_asset_count",
    "pair_rate",
    "case_fingerprint_aggregate_sha256",
)
FAILURE_POINTS = (
    "after_adapter",
    "after_assets",
    "before_manifest",
    "before_publish",
    "before_replace",
)


class ValidationFailure(RuntimeError):
    """A failed observable required by the live integration contract."""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot read JSON {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(128 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _remove_tree(path: Path) -> None:
    """Remove validator-owned external state, including Git's read-only objects."""
    if not path.exists():
        return

    def onerror(function: object, item: str, _exception: object) -> None:
        os.chmod(item, stat.S_IREAD | stat.S_IWRITE)
        if callable(function):
            function(item)  # type: ignore[misc]

    shutil.rmtree(path, onerror=onerror)


def _must_be_external(path: Path, workspace: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if resolved == workspace or workspace in resolved.parents:
        raise ValidationFailure(f"{label} must be outside the workspace: {resolved}")
    return resolved


def _require_runtime_environment(workspace: Path) -> dict[str, str]:
    expected_root = EXPECTED_RUNTIME_ROOT.resolve(strict=False)
    observed: dict[str, str] = {}
    required = {
        "UV_PROJECT_ENVIRONMENT": expected_root / "venv",
        "UV_CACHE_DIR": expected_root / "uv-cache",
    }
    for name, expected in required.items():
        raw = os.environ.get(name)
        if not raw:
            raise ValidationFailure(f"{name} is required")
        actual = _must_be_external(Path(raw), workspace, name)
        if actual != expected.resolve(strict=False):
            raise ValidationFailure(f"{name} must equal {expected}, got {actual}")
        observed[name] = str(actual)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValidationFailure("PYTHONDONTWRITEBYTECODE must equal 1")
    for name in ("TMP", "TEMP"):
        raw = os.environ.get(name)
        if not raw:
            raise ValidationFailure(f"{name} is required to keep temporary state outside the workspace")
        actual = _must_be_external(Path(raw), workspace, name)
        if actual != expected_root and expected_root not in actual.parents:
            raise ValidationFailure(f"{name} must be within {expected_root}, got {actual}")
        observed[name] = str(actual)
    return observed


def _audit_record(audit: dict[str, Any], source_id: str, expected_commit: str) -> dict[str, Any]:
    records = audit.get("records")
    if not isinstance(records, list):
        raise ValidationFailure("audit.records must be an array")
    matches = [record for record in records if isinstance(record, dict) and record.get("source_id") == source_id]
    if len(matches) != 1:
        raise ValidationFailure("audit must contain exactly one target source record")
    record = matches[0]
    repository = record.get("repository")
    metrics = record.get("metrics")
    if not isinstance(repository, dict) or repository.get("verified_commit_sha") != expected_commit:
        raise ValidationFailure("audit source commit differs from the frozen Commit")
    if not isinstance(metrics, dict):
        raise ValidationFailure("audit target record has no metrics")
    return metrics


def _prior_evidence_metrics(root: Path, source_id: str, expected_commit: str) -> tuple[dict[str, Any], str]:
    candidates: list[tuple[dict[str, Any], Path]] = []
    for path in sorted(root.rglob("active-candidate-full-metrics.json")):
        payload = _json(path)
        audits = payload.get("audits") if isinstance(payload, dict) else None
        if not isinstance(audits, list):
            continue
        for item in audits:
            if not isinstance(item, dict) or item.get("source_id") != source_id:
                continue
            maintenance = item.get("maintenance_evidence")
            metrics = item.get("metrics")
            if isinstance(maintenance, dict) and maintenance.get("evidence_commit_sha") == expected_commit and isinstance(metrics, dict):
                candidates.append((metrics, path))
    if len(candidates) != 1:
        raise ValidationFailure("TASK-0001 evidence must provide exactly one matching full-metrics record")
    metrics, path = candidates[0]
    return metrics, path.relative_to(root).as_posix()


def _expected_metrics(audit_metrics: dict[str, Any], prior_metrics: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "observed_case_count": 100,
        "exact_prompt_count": 100,
        "paired_output_count": 100,
        "valid_case_count": 100,
        "unique_valid_case_count": 100,
        "broken_asset_count": 0,
        "pair_rate": 1.0,
        "case_fingerprint_aggregate_sha256": EXPECTED_AGGREGATE,
    }
    for name, value in expected.items():
        if audit_metrics.get(name) != value or prior_metrics.get(name) != value:
            raise ValidationFailure(f"TASK-0001/audit expected metric mismatch for {name}")
    return expected


def _package_summary(result: Any, expected: dict[str, Any]) -> dict[str, Any]:
    manifest = verify_published_package(result.output_path, result.idempotency_key)
    adapter_output = _json(result.output_path / "adapter-output.json")
    metrics = _json(result.output_path / "metrics.json")
    examples_dir = result.output_path / "generation-examples"
    example_paths = sorted(examples_dir.glob("*.json"))
    if not isinstance(adapter_output, dict) or not isinstance(metrics, dict):
        raise ValidationFailure("published package documents must be JSON objects")
    if adapter_output.get("parse_errors") != []:
        raise ValidationFailure("live adapter output contains parse errors")
    records = adapter_output.get("records")
    if not isinstance(records, list) or len(records) != 100:
        raise ValidationFailure("live adapter output must contain 100 records")
    if len(example_paths) != 100:
        raise ValidationFailure("live package must contain 100 Generation Examples")
    for name, value in expected.items():
        if metrics.get(name) != value:
            raise ValidationFailure(f"live metrics mismatch for {name}: {metrics.get(name)!r}")
    if result.metrics != metrics:
        raise ValidationFailure("returned metrics differ from published metrics")
    if result.semantic_digest != manifest.get("semantic_digest") or result.semantic_digest != metrics.get("semantic_digest"):
        raise ValidationFailure("result, manifest, and metrics semantic digests must agree")
    if any(path.suffix != ".json" for path in result.output_path.rglob("*") if path.is_file()):
        raise ValidationFailure("published package must not contain image bytes or other non-JSON files")
    for record in records:
        if not isinstance(record, dict):
            raise ValidationFailure("adapter output contains a non-object record")
        references = record.get("asset_references")
        if not isinstance(references, list) or len(references) != 1 or references[0].get("resolution_state") != "resolved":
            raise ValidationFailure("every live record needs one resolved output asset")
    return {
        "status": result.status,
        "semantic_digest": result.semantic_digest,
        "manifest_stable_sha256": manifest.get("manifest_stable_sha256"),
        "manifest": manifest,
        "metrics": {name: metrics.get(name) for name in METRIC_KEYS},
        "file_hashes": _file_hashes(result.output_path),
        "generation_example_count": len(example_paths),
        "states": list(result.states),
    }


def _run_failure_and_concurrency_checks(
    *,
    registry: Path,
    audit: Path,
    source_id: str,
    data_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    output_root = run_root / "fault-output"
    published = extract(
        registry_path=registry,
        audit_path=audit,
        source_id=source_id,
        data_root=data_root,
        output_root=output_root,
    )
    before_hashes = _file_hashes(published.output_path)
    failures: dict[str, str] = {}
    for point in FAILURE_POINTS:
        try:
            extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=output_root,
                failure_point=point,
            )
        except ExtractionError as exc:
            if not exc.error_code.startswith("injected_"):
                raise ValidationFailure(f"{point} produced unexpected error code {exc.error_code}") from exc
            failures[point] = exc.error_code
        else:
            raise ValidationFailure(f"failure injection {point} unexpectedly succeeded")
        if _file_hashes(published.output_path) != before_hashes:
            raise ValidationFailure(f"failure injection {point} altered the previous published package")
        temporary = output_root / ".temporary"
        if temporary.exists() and any(temporary.glob("candidate-*")):
            raise ValidationFailure(f"failure injection {point} left a candidate package")
    concurrency_root = run_root / "concurrency-output"
    holder: dict[str, Any] = {}

    def first_run() -> None:
        try:
            holder["result"] = extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=concurrency_root,
                lock_hold_seconds=0.5,
            )
        except BaseException as exc:  # report the original extraction failure after the join
            holder["error"] = exc

    thread = threading.Thread(target=first_run, name="task-0003-lock-holder")
    thread.start()
    deadline = time.monotonic() + 15.0
    while not list((concurrency_root / ".locks").glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.02)
    if not list((concurrency_root / ".locks").glob("*.lock")):
        raise ValidationFailure("concurrent lock holder did not acquire the same-key lock")
    try:
        extract(
            registry_path=registry,
            audit_path=audit,
            source_id=source_id,
            data_root=data_root,
            output_root=concurrency_root,
        )
    except ExtractionError as exc:
        if exc.error_code != "run_locked":
            raise ValidationFailure(f"concurrent extraction returned {exc.error_code}, expected run_locked") from exc
        concurrent_code = exc.error_code
    else:
        raise ValidationFailure("concurrent same-key extraction unexpectedly acquired a second writer")
    thread.join(timeout=180.0)
    if thread.is_alive():
        raise ValidationFailure("lock holder did not terminate within the bounded wait")
    if "error" in holder:
        raise ValidationFailure(f"lock holder failed: {holder['error']}")
    holder_result = holder.get("result")
    if holder_result is None or holder_result.status != "published":
        raise ValidationFailure("lock holder did not become the sole published writer")
    if any((concurrency_root / ".locks").glob("*.lock")):
        raise ValidationFailure("concurrency lock was not released")
    return {
        "failure_codes": failures,
        "previous_package_hashes_unchanged": True,
        "candidate_cleanup": True,
        "concurrent_second_result": concurrent_code,
        "single_writer_status": holder_result.status,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = REPO_ROOT
    registry = Path(args.registry).resolve()
    audit = Path(args.audit).resolve()
    evidence_root = Path(args.prior_source_evidence_root).resolve()
    runtime_environment = _require_runtime_environment(workspace)
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, workspace, "TASK-0003 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    if args.runs != 2:
        raise ValidationFailure("TASK-0003 live validation requires exactly two full extraction runs")
    if not args.failure_injection:
        raise ValidationFailure("TASK-0003 live validation requires --failure-injection")
    config = load_source_config(registry, args.source_id)
    if config.verified_commit_sha != args.expected_commit:
        raise ValidationFailure("registry fixed Commit differs from --expected-commit")
    audit_metrics = _audit_record(_json(audit), args.source_id, args.expected_commit)
    prior_metrics, prior_metrics_path = _prior_evidence_metrics(evidence_root, args.source_id, args.expected_commit)
    expected = _expected_metrics(audit_metrics, prior_metrics)
    run_root = Path(tempfile.mkdtemp(prefix="live-g0dam-", dir=runtime_root))
    try:
        data_root = run_root / "data"
        runs: list[dict[str, Any]] = []
        for index in range(args.runs):
            result = extract(
                registry_path=registry,
                audit_path=audit,
                source_id=args.source_id,
                data_root=data_root,
                output_root=run_root / f"output-{index + 1}",
            )
            if result.status != "published":
                raise ValidationFailure(f"fresh full run {index + 1} did not publish: {result.status}")
            runs.append(_package_summary(result, expected))
        first, second = runs
        if first["semantic_digest"] != second["semantic_digest"]:
            raise ValidationFailure("two full runs produced different semantic digests")
        if first["manifest"] != second["manifest"] or first["file_hashes"] != second["file_hashes"]:
            raise ValidationFailure("two full runs produced different stable manifests or files")
        fault_and_concurrency = _run_failure_and_concurrency_checks(
            registry=registry,
            audit=audit,
            source_id=args.source_id,
            data_root=data_root,
            run_root=run_root,
        )
        return {
            "status": "passed",
            "source_id": args.source_id,
            "commit": args.expected_commit,
            "environment": runtime_environment,
            "prior_metrics_path": prior_metrics_path,
            "runs": [
                {
                    "status": item["status"],
                    "semantic_digest": item["semantic_digest"],
                    "manifest_stable_sha256": item["manifest_stable_sha256"],
                    "metrics": item["metrics"],
                    "generation_example_count": item["generation_example_count"],
                }
                for item in runs
            ],
            "fault_and_concurrency": fault_and_concurrency,
            "gates": {
                "GATE-001": "passed",
                "GATE-002": "passed",
                "GATE-003": "passed",
                "GATE-004": "passed",
            },
            "temporary_runtime_cleaned": True,
        }
    finally:
        _remove_tree(run_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the TASK-0003 live fixed-commit g0dam extraction.")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--prior-source-evidence-root", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--runs", required=True, type=int)
    parser.add_argument("--failure-injection", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(args)
    except (ValidationFailure, ExtractionError) as exc:
        payload = {"status": "failed", "error": str(exc), "error_type": type(exc).__name__}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"failed: {payload['error']}")
        return 1
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
