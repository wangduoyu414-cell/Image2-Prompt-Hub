"""Real fixed-commit two-source extraction and private inventory validation.

This validator is intentionally self-contained at the orchestration boundary:
it consumes the existing generic extraction and inventory implementations but
creates only a random loopback Compose project and external runtime artifacts.
It never executes code from either upstream repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import boto3
import psycopg
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ingestion.pipeline import ExtractionError, ExtractionResult, extract, verify_published_package
from inventory.object_store import ObjectFact, ObjectStoreConfig, S3ObjectStore, object_key_for
from inventory.package import ImportPlan, PackageValidationError, build_import_plan


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0006")
POSTGRES_IMAGE = "postgres:18.4@sha256:3a82e1f56c8f0f5616a11103ac3d47e632c3938698946a7ad26da0df1334744a"
MINIO_IMAGE = "minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
JOESAI_FAILURE_POINTS = ("after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace")
TABLES = (
    "source_projects",
    "source_revisions",
    "source_files",
    "source_adapter_runs",
    "source_parse_errors",
    "source_cases",
    "source_case_versions",
    "prompt_records",
    "assets",
    "asset_sources",
    "generation_examples",
    "generation_inputs",
    "generation_outputs",
    "pairing_evidence",
    "rights_records",
)


class ValidationFailure(RuntimeError):
    pass


def _remove_tree(path: Path) -> None:
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
        raise ValidationFailure(f"{label} must be outside the workspace")
    return resolved


def _runtime_environment() -> dict[str, str]:
    workspace = REPO_ROOT.resolve()
    runtime = EXPECTED_RUNTIME_ROOT.resolve(strict=False)
    expected = {
        "UV_PROJECT_ENVIRONMENT": runtime / "venv",
        "UV_CACHE_DIR": runtime / "uv-cache",
        "TMP": runtime / "tmp",
        "TEMP": runtime / "tmp",
    }
    observed: dict[str, str] = {}
    for name, required in expected.items():
        raw = os.environ.get(name)
        if not raw:
            raise ValidationFailure(f"{name} is required")
        actual = _must_be_external(Path(raw), workspace, name)
        if actual != required.resolve(strict=False):
            raise ValidationFailure(f"{name} must use the fixed TASK-0006 external runtime path")
        observed[name] = str(actual)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValidationFailure("PYTHONDONTWRITEBYTECODE must equal 1")
    return observed


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _random_token(length: int = 24) -> str:
    return secrets.token_urlsafe(length).replace("-", "a").replace("_", "b")


def _compose(command: list[str], *, env_file: Path, project: str, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", "compose", "-f", str(REPO_ROOT / "compose.yaml"), "--env-file", str(env_file), "-p", project, *command],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise ValidationFailure("isolated Compose operation failed")
    return completed


def _write_compose_env(path: Path, values: dict[str, str]) -> None:
    safe_keys = {
        "INVENTORY_POSTGRES_DB",
        "INVENTORY_POSTGRES_USER",
        "INVENTORY_POSTGRES_PASSWORD",
        "INVENTORY_POSTGRES_PORT",
        "INVENTORY_S3_ACCESS_KEY",
        "INVENTORY_S3_SECRET_KEY",
        "INVENTORY_S3_PORT",
    }
    if set(values) != safe_keys:
        raise ValidationFailure("Compose environment keys differ from the isolated test contract")
    path.write_text("".join(f"{key}={values[key]}\n" for key in sorted(values)), encoding="utf-8")


def _wait_for_services(database_url: str, endpoint: str, access_key: str, secret_key: str) -> None:
    deadline = time.monotonic() + 150.0
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=3) as conn:
                conn.execute("SELECT 1").fetchone()
            client.list_buckets()
            return
        except (psycopg.Error, ClientError, BotoCoreError, OSError):
            time.sleep(1.0)
    raise ValidationFailure("isolated PostgreSQL/S3 services did not become ready")


def _runtime_env(database_url: str, endpoint: str, bucket: str, access_key: str, secret_key: str) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "INVENTORY_DATABASE_URL": database_url,
            "INVENTORY_S3_ENDPOINT_URL": endpoint,
            "INVENTORY_S3_BUCKET": bucket,
            "INVENTORY_S3_ACCESS_KEY": access_key,
            "INVENTORY_S3_SECRET_KEY": secret_key,
            "INVENTORY_S3_REGION": "us-east-1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def _run_inventory(argv: list[str], environment: dict[str, str], *, timeout: int = 1200) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "inventory", *argv, "--json"],
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValidationFailure("inventory CLI did not produce one JSON result") from exc
    if not isinstance(payload, dict):
        raise ValidationFailure("inventory CLI produced a non-object result")
    return completed.returncode, payload


def _file_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _assert_extraction_cleanup(data_root: Path, output_root: Path, source_id: str) -> None:
    temporary = output_root / ".temporary"
    if temporary.exists() and any(temporary.glob("candidate-*")):
        raise ValidationFailure(f"{source_id} extraction retained a candidate directory")
    locks = output_root / ".locks"
    if locks.exists() and any(locks.glob("*.lock")):
        raise ValidationFailure(f"{source_id} extraction retained an idempotency lock")
    worktrees = data_root / "worktrees" / source_id
    if worktrees.exists() and any(worktrees.glob("run-*")):
        raise ValidationFailure(f"{source_id} extraction retained a temporary Git worktree")


def _expect_package(
    result: ExtractionResult,
    *,
    registry: Path,
    audit: Path,
    expected_source_id: str,
    expected_commit: str,
    expected_cases: int,
    expected_aggregate: str,
    expected_package_schema: str,
    expected_metrics_schema: str,
) -> ImportPlan:
    manifest = verify_published_package(result.output_path, result.idempotency_key)
    plan = build_import_plan(package_root=result.output_path, registry_path=registry, audit_path=audit)
    if (
        plan.source_config.source_id != expected_source_id
        or plan.revision_sha != expected_commit
        or len(plan.adapter_output["records"]) != expected_cases
        or len(plan.generation_documents) != expected_cases
    ):
        raise ValidationFailure(f"{expected_source_id} package identity or record closure failed")
    if manifest.get("schema_version") != expected_package_schema or plan.metrics.get("schema_version") != expected_metrics_schema:
        raise ValidationFailure(f"{expected_source_id} package/metrics schema compatibility failed")
    if plan.metrics.get("case_fingerprint_aggregate_sha256") != expected_aggregate:
        raise ValidationFailure(f"{expected_source_id} fixed aggregate differs from the audit")
    for name in ("observed_case_count", "exact_prompt_count", "paired_output_count", "valid_case_count", "unique_valid_case_count"):
        if plan.metrics.get(name) != expected_cases:
            raise ValidationFailure(f"{expected_source_id} metric {name} does not close")
    if plan.metrics.get("broken_asset_count") != 0 or plan.metrics.get("pair_rate") != 1.0:
        raise ValidationFailure(f"{expected_source_id} quality metrics are not fail-closed")
    if any(path.suffix != ".json" for path in result.output_path.rglob("*") if path.is_file()):
        raise ValidationFailure(f"{expected_source_id} package stored non-JSON bytes")
    return plan


def _extract_source_twice(
    *,
    source_id: str,
    registry: Path,
    audit: Path,
    data_root: Path,
    output_root: Path,
    expected_commit: str,
    expected_cases: int,
    expected_aggregate: str,
    expected_package_schema: str,
    expected_metrics_schema: str,
) -> tuple[ImportPlan, Path, dict[str, Any]]:
    first_output = output_root / "first"
    second_output = output_root / "second"
    first = extract(
        registry_path=registry,
        audit_path=audit,
        source_id=source_id,
        data_root=data_root,
        output_root=first_output,
    )
    second = extract(
        registry_path=registry,
        audit_path=audit,
        source_id=source_id,
        data_root=data_root,
        output_root=second_output,
    )
    if first.status != "published" or second.status != "published":
        raise ValidationFailure(f"{source_id} independent fixed-commit extractions did not publish")
    first_hashes = _file_hashes(first.output_path)
    if first_hashes != _file_hashes(second.output_path) or first.semantic_digest != second.semantic_digest:
        raise ValidationFailure(f"{source_id} independent extractions are not deterministic")
    replay = extract(
        registry_path=registry,
        audit_path=audit,
        source_id=source_id,
        data_root=data_root,
        output_root=first_output,
    )
    if replay.status != "verified_existing" or _file_hashes(replay.output_path) != first_hashes:
        raise ValidationFailure(f"{source_id} same-key package replay is not verified_existing")
    plan = _expect_package(
        first,
        registry=registry,
        audit=audit,
        expected_source_id=source_id,
        expected_commit=expected_commit,
        expected_cases=expected_cases,
        expected_aggregate=expected_aggregate,
        expected_package_schema=expected_package_schema,
        expected_metrics_schema=expected_metrics_schema,
    )
    _assert_extraction_cleanup(data_root, first_output, source_id)
    _assert_extraction_cleanup(data_root, second_output, source_id)
    return plan, first.output_path, {
        "commit": expected_commit,
        "case_count": expected_cases,
        "manifest_stable_sha256": plan.manifest["manifest_stable_sha256"],
        "semantic_digest": plan.semantic_digest,
        "package_schema": expected_package_schema,
        "metrics_schema": expected_metrics_schema,
        "independent_second_status": second.status,
        "same_key_replay_status": replay.status,
    }


def _verify_joesai_failure_and_concurrency(
    *, registry: Path, audit: Path, data_root: Path, output_root: Path
) -> dict[str, Any]:
    published = extract(
        registry_path=registry,
        audit_path=audit,
        source_id="joesai-commercial-prompts",
        data_root=data_root,
        output_root=output_root / "failure-baseline",
    )
    before = _file_hashes(published.output_path)
    failures: dict[str, str] = {}
    for point in JOESAI_FAILURE_POINTS:
        try:
            extract(
                registry_path=registry,
                audit_path=audit,
                source_id="joesai-commercial-prompts",
                data_root=data_root,
                output_root=output_root / "failure-baseline",
                failure_point=point,
            )
        except ExtractionError as exc:
            expected = f"injected_{point}"
            if exc.error_code != expected:
                raise ValidationFailure(f"JoeSai failure injection {point} returned the wrong error") from exc
            failures[point] = expected
        else:
            raise ValidationFailure(f"JoeSai failure injection {point} unexpectedly succeeded")
        if _file_hashes(published.output_path) != before:
            raise ValidationFailure(f"JoeSai failure injection {point} changed the prior published package")

    concurrent_output = output_root / "concurrent"
    holder: dict[str, object] = {}

    def first_run() -> None:
        try:
            holder["result"] = extract(
                registry_path=registry,
                audit_path=audit,
                source_id="joesai-commercial-prompts",
                data_root=data_root,
                output_root=concurrent_output,
                lock_hold_seconds=0.75,
            )
        except BaseException as exc:  # propagated below as the original cause
            holder["error"] = exc

    thread = threading.Thread(target=first_run, name="task0006-joesai-extraction-holder")
    thread.start()
    deadline = time.monotonic() + 15.0
    while not list((concurrent_output / ".locks").glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        extract(
            registry_path=registry,
            audit_path=audit,
            source_id="joesai-commercial-prompts",
            data_root=data_root,
            output_root=concurrent_output,
        )
    except ExtractionError as exc:
        if exc.error_code != "run_locked":
            raise ValidationFailure("JoeSai concurrent extraction returned the wrong error") from exc
    else:
        raise ValidationFailure("JoeSai concurrent extraction did not fail fast for the lock")
    thread.join(timeout=300)
    if thread.is_alive() or "error" in holder:
        raise ValidationFailure("JoeSai concurrent extraction holder did not finish cleanly")
    result = holder.get("result")
    if not isinstance(result, ExtractionResult) or result.status != "published":
        raise ValidationFailure("JoeSai concurrent extraction holder was not the sole publisher")
    _assert_extraction_cleanup(data_root, concurrent_output, "joesai-commercial-prompts")
    return {"failure_codes": failures, "concurrent_second_status": "run_locked"}


def _database_counts(database_url: str) -> dict[str, int]:
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        return {
            table: int(conn.execute(f"SELECT count(*) AS count FROM inventory.{table}").fetchone()["count"])
            for table in TABLES
        }


def _object_keys(endpoint: str, bucket: str, access_key: str, secret_key: str) -> set[str]:
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    result: set[str] = set()
    continuation: str | None = None
    while True:
        args: dict[str, Any] = {"Bucket": bucket}
        if continuation is not None:
            args["ContinuationToken"] = continuation
        response = client.list_objects_v2(**args)
        result.update(str(item["Key"]) for item in response.get("Contents", []) if isinstance(item, dict) and "Key" in item)
        if response.get("IsTruncated") is not True:
            return result
        continuation = response.get("NextContinuationToken")
        if not isinstance(continuation, str) or not continuation:
            raise ValidationFailure("S3 object listing returned an invalid continuation token")


def _expected_run_counts(plan: ImportPlan) -> dict[str, int]:
    cases = len(plan.adapter_output["records"])
    assets = {source.content_sha256 for source in plan.asset_sources}
    generations = sum(len(document["generation_examples"]) for document in plan.generation_documents)
    inputs = sum(
        len(generation["input_asset_ids"])
        for document in plan.generation_documents
        for generation in document["generation_examples"]
    )
    outputs = sum(
        len(generation["output_asset_ids"])
        for document in plan.generation_documents
        for generation in document["generation_examples"]
    )
    return {
        "source_projects": 1,
        "source_revisions": 1,
        "source_files": len(plan.source_files),
        "source_adapter_runs": 1,
        "source_parse_errors": 0,
        "source_cases": cases,
        "source_case_versions": cases,
        "prompt_records": cases,
        "assets": len(assets),
        "asset_sources": len(plan.asset_sources),
        "generation_examples": generations,
        "generation_inputs": inputs,
        "generation_outputs": outputs,
        "pairing_evidence": generations,
        "rights_records": cases,
    }


def _expected_global_counts(plans: Sequence[ImportPlan]) -> dict[str, int]:
    cases = sum(len(plan.adapter_output["records"]) for plan in plans)
    hashes = {source.content_sha256 for plan in plans for source in plan.asset_sources}
    generations = sum(
        len(document["generation_examples"])
        for plan in plans
        for document in plan.generation_documents
    )
    inputs = sum(
        len(generation["input_asset_ids"])
        for plan in plans
        for document in plan.generation_documents
        for generation in document["generation_examples"]
    )
    outputs = sum(
        len(generation["output_asset_ids"])
        for plan in plans
        for document in plan.generation_documents
        for generation in document["generation_examples"]
    )
    return {
        "source_projects": len(plans),
        "source_revisions": len(plans),
        "source_files": sum(len(plan.source_files) for plan in plans),
        "source_adapter_runs": len(plans),
        "source_parse_errors": 0,
        "source_cases": cases,
        "source_case_versions": cases,
        "prompt_records": cases,
        "assets": len(hashes),
        "asset_sources": sum(len(plan.asset_sources) for plan in plans),
        "generation_examples": generations,
        "generation_inputs": inputs,
        "generation_outputs": outputs,
        "pairing_evidence": generations,
        "rights_records": cases,
    }


def _import_argv(registry: Path, audit: Path, package_root: Path, data_root: Path) -> list[str]:
    return [
        "import-package",
        "--registry",
        str(registry),
        "--audit",
        str(audit),
        "--package-root",
        str(package_root),
        "--data-root",
        str(data_root),
    ]


def _inspect(environment: dict[str, str], idempotency_key: str) -> dict[str, Any]:
    code, payload = _run_inventory(["inspect", "--idempotency-key", idempotency_key], environment)
    if code != 0 or payload.get("status") != "ready" or not isinstance(payload.get("summary"), dict):
        raise ValidationFailure("per-run inventory inspect did not return a ready summary")
    return payload["summary"]


def _assert_rights_and_publication(database_url: str, expected_cases: dict[str, int]) -> None:
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        rows = conn.execute(
            """
            SELECT p.source_id,
                   count(*) AS total,
                   count(*) FILTER (WHERE g.source_claim->>'evidence_status' = 'unknown') AS unknown_claims,
                   count(*) FILTER (WHERE g.source_claim->>'evidence_status' = 'source_claimed') AS source_claims
            FROM inventory.generation_examples AS g
            JOIN inventory.source_case_versions AS v ON v.source_case_version_id = g.source_case_version_id
            JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id = v.source_adapter_run_id
            JOIN inventory.source_revisions AS r ON r.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS p ON p.source_project_id = r.source_project_id
            GROUP BY p.source_id
            """
        ).fetchall()
        by_source = {str(row["source_id"]): row for row in rows}
        for source_id, count in expected_cases.items():
            row = by_source.get(source_id)
            if row is None or int(row["total"]) != count:
                raise ValidationFailure("source claim domain is incomplete")
            expected_claims = count if source_id == "g0dam-work-prompts" else 0
            expected_unknown = count if source_id == "joesai-commercial-prompts" else 0
            if int(row["source_claims"]) != expected_claims or int(row["unknown_claims"]) != expected_unknown:
                raise ValidationFailure("source claims were changed across source boundaries")
        rights = conn.execute(
            """
            SELECT count(*) AS count
            FROM inventory.rights_records
            WHERE prompt_rights_status <> 'unknown' OR asset_rights_status <> 'unknown'
            """
        ).fetchone()
        if int(rights["count"]) != 0:
            raise ValidationFailure("inventory upgraded review_required rights evidence")
        snapshots = conn.execute(
            """
            SELECT p.source_id, run.registry_snapshot
            FROM inventory.source_adapter_runs AS run
            JOIN inventory.source_revisions AS r ON r.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS p ON p.source_project_id = r.source_project_id
            """
        ).fetchall()
        if len(snapshots) != 2:
            raise ValidationFailure("inventory registry snapshots do not close for both sources")
        for row in snapshots:
            snapshot = row["registry_snapshot"]
            publication = snapshot.get("publication") if isinstance(snapshot, dict) else None
            rights_snapshot = snapshot.get("rights") if isinstance(snapshot, dict) else None
            if (
                not isinstance(publication, dict)
                or publication.get("auto_publish") is not False
                or not isinstance(rights_snapshot, dict)
                or rights_snapshot.get("prompt_policy") != "review_required"
                or rights_snapshot.get("asset_policy") != "review_required"
            ):
                raise ValidationFailure("registry snapshot elevated rights or publication policy")
        forbidden = conn.execute(
            """
            SELECT count(*) AS count
            FROM information_schema.columns
            WHERE table_schema = 'inventory'
              AND lower(column_name) IN ('publication', 'visibility', 'auto_publish', 'mirror_allowed')
            """
        ).fetchone()
        if int(forbidden["count"]) != 0:
            raise ValidationFailure("inventory contains a forbidden publication decision field")


def _cleanup_compose(env_file: Path, project: str) -> bool:
    try:
        _compose(["down", "-v", "--remove-orphans"], env_file=env_file, project=project, timeout=180)
        containers = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"],
            capture_output=True,
            text=True,
            check=False,
        )
        volumes = subprocess.run(
            ["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return not containers.stdout.strip() and not volumes.stdout.strip()
    except (OSError, subprocess.SubprocessError, ValidationFailure):
        return False


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime_environment = _runtime_environment()
    if args.runs != 2:
        raise ValidationFailure("TASK-0006 requires exactly two independent extraction runs per source")
    if not args.failure_injection or not args.concurrency:
        raise ValidationFailure("TASK-0006 requires JoeSai failure injection and concurrency validation")
    if (args.g0dam_expected_cases, args.joesai_expected_cases) != (100, 50):
        raise ValidationFailure("TASK-0006 fixed case counts must remain 100 g0dam and 50 JoeSai")
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0006 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="live-joesai-multi-source-", dir=runtime_root))
    project = f"task0006{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_ok = False
    try:
        registry = Path(args.registry).resolve()
        audit = Path(args.audit).resolve()
        extraction_data = run_root / "extraction-git"
        g0dam_plan, g0dam_package, g0dam_evidence = _extract_source_twice(
            source_id=args.g0dam_source_id,
            registry=registry,
            audit=audit,
            data_root=extraction_data,
            output_root=run_root / "g0dam-extraction",
            expected_commit=args.g0dam_expected_commit,
            expected_cases=args.g0dam_expected_cases,
            expected_aggregate=args.g0dam_expected_aggregate,
            expected_package_schema="g0dam-extraction-package/v1",
            expected_metrics_schema="g0dam-extraction-metrics/v1",
        )
        joesai_plan, joesai_package, joesai_evidence = _extract_source_twice(
            source_id=args.joesai_source_id,
            registry=registry,
            audit=audit,
            data_root=extraction_data,
            output_root=run_root / "joesai-extraction",
            expected_commit=args.joesai_expected_commit,
            expected_cases=args.joesai_expected_cases,
            expected_aggregate=args.joesai_expected_aggregate,
            expected_package_schema="extraction-package/v1",
            expected_metrics_schema="extraction-metrics/v1",
        )
        joesai_failure = _verify_joesai_failure_and_concurrency(
            registry=registry,
            audit=audit,
            data_root=extraction_data,
            output_root=run_root / "joesai-failure-concurrency",
        )

        postgres_port = _free_loopback_port()
        s3_port = _free_loopback_port()
        postgres_user = "u" + _random_token(12)
        postgres_password = _random_token(24)
        s3_access_key = "a" + _random_token(12)
        s3_secret_key = _random_token(24)
        compose_values = {
            "INVENTORY_POSTGRES_DB": "inventorytest",
            "INVENTORY_POSTGRES_USER": postgres_user,
            "INVENTORY_POSTGRES_PASSWORD": postgres_password,
            "INVENTORY_POSTGRES_PORT": str(postgres_port),
            "INVENTORY_S3_ACCESS_KEY": s3_access_key,
            "INVENTORY_S3_SECRET_KEY": s3_secret_key,
            "INVENTORY_S3_PORT": str(s3_port),
        }
        _write_compose_env(env_file, compose_values)
        database_url = f"postgresql://{quote(postgres_user)}:{quote(postgres_password)}@127.0.0.1:{postgres_port}/inventorytest"
        endpoint = f"http://127.0.0.1:{s3_port}"
        bucket = "inventory-private-multi-source"
        environment = _runtime_env(database_url, endpoint, bucket, s3_access_key, s3_secret_key)
        compose_started = True
        _compose(["up", "-d"], env_file=env_file, project=project, timeout=900)
        _wait_for_services(database_url, endpoint, s3_access_key, s3_secret_key)
        for label in ("initial", "repeat"):
            code, payload = _run_inventory(["migrate", "--migrations-dir", str(REPO_ROOT / "migrations")], environment)
            if code != 0 or payload.get("status") != "migrated":
                raise ValidationFailure(f"{label} inventory migration failed")

        imports: dict[str, dict[str, Any]] = {}
        for source_id, plan, package_root in (
            (args.g0dam_source_id, g0dam_plan, g0dam_package),
            (args.joesai_source_id, joesai_plan, joesai_package),
        ):
            code, payload = _run_inventory(
                _import_argv(registry, audit, package_root, run_root / "import-git"), environment
            )
            if code != 0 or payload.get("status") != "imported" or not isinstance(payload.get("summary"), dict):
                raise ValidationFailure(f"initial {source_id} inventory import failed")
            if payload["summary"].get("counts") != _expected_run_counts(plan):
                raise ValidationFailure(f"{source_id} per-run inventory counts do not close")
            imports[source_id] = payload

        plans = (g0dam_plan, joesai_plan)
        expected_global = _expected_global_counts(plans)
        if _database_counts(database_url) != expected_global:
            raise ValidationFailure("two-source global database counts do not close")
        per_run = {
            source_id: _inspect(environment, plan.idempotency_key)
            for source_id, plan in ((args.g0dam_source_id, g0dam_plan), (args.joesai_source_id, joesai_plan))
        }
        for source_id, plan in ((args.g0dam_source_id, g0dam_plan), (args.joesai_source_id, joesai_plan)):
            if per_run[source_id].get("counts") != _expected_run_counts(plan):
                raise ValidationFailure(f"{source_id} inspection was contaminated by the other source")

        objects: dict[str, ObjectFact] = {}
        for plan in plans:
            for asset_source in plan.asset_sources:
                fact = ObjectFact(
                    asset_source.content_sha256,
                    object_key_for(asset_source.content_sha256),
                    bucket,
                    asset_source.byte_size,
                    asset_source.media_type,
                    "content_verified",
                )
                existing = objects.setdefault(asset_source.content_sha256, fact)
                if existing != fact:
                    raise ValidationFailure("identical source hash has contradictory immutable object facts")
        store = S3ObjectStore(ObjectStoreConfig(endpoint, bucket, s3_access_key, s3_secret_key))
        store.ensure_private_bucket()
        downloaded = store.download_hashes(objects)
        if len(downloaded) != len(objects) or set(downloaded.values()) != set(objects):
            raise ValidationFailure("all cross-source immutable objects were not download-hash verified")
        _assert_rights_and_publication(
            database_url,
            {args.g0dam_source_id: args.g0dam_expected_cases, args.joesai_source_id: args.joesai_expected_cases},
        )
        before_counts = _database_counts(database_url)
        before_keys = _object_keys(endpoint, bucket, s3_access_key, s3_secret_key)
        replays: dict[str, str] = {}
        for source_id, package_root in ((args.g0dam_source_id, g0dam_package), (args.joesai_source_id, joesai_package)):
            code, payload = _run_inventory(
                _import_argv(registry, audit, package_root, run_root / "import-git"), environment
            )
            if code != 0 or payload.get("status") != "verified_existing":
                raise ValidationFailure(f"{source_id} inventory replay was not verified_existing")
            replays[source_id] = str(payload["status"])
        if _database_counts(database_url) != before_counts or _object_keys(endpoint, bucket, s3_access_key, s3_secret_key) != before_keys:
            raise ValidationFailure("two-source inventory replay grew global database or object state")
        _assert_extraction_cleanup(extraction_data, run_root / "g0dam-extraction" / "first", args.g0dam_source_id)
        _assert_extraction_cleanup(extraction_data, run_root / "joesai-extraction" / "first", args.joesai_source_id)

        return {
            "status": "passed",
            "environment": runtime_environment,
            "docker": {
                "postgres_image": POSTGRES_IMAGE,
                "legacy_s3_image": MINIO_IMAGE,
                "loopback_only": True,
            },
            "extractions": {
                args.g0dam_source_id: g0dam_evidence,
                args.joesai_source_id: joesai_evidence,
            },
            "joesai_failure_and_concurrency": joesai_failure,
            "per_run_counts": {source_id: summary["counts"] for source_id, summary in per_run.items()},
            "global_database_counts": expected_global,
            "object_download_hash_count": len(downloaded),
            "replay_statuses": replays,
            "rights_publication_fail_closed": True,
            "gates": {
                "GATE-001": "passed",
                "GATE-002": "passed",
                "GATE-003": "passed",
                "GATE-004": "passed",
            },
            "temporary_runtime_cleaned": True,
            "compose_cleanup": True,
        }
    finally:
        if compose_started:
            cleanup_ok = _cleanup_compose(env_file, project)
        _remove_tree(run_root)
        if compose_started and not cleanup_ok:
            raise ValidationFailure("isolated Compose cleanup did not complete")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated TASK-0006 two-source PostgreSQL/S3/Git validator.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--g0dam-source-id", required=True)
    parser.add_argument("--g0dam-expected-commit", required=True)
    parser.add_argument("--g0dam-expected-cases", type=int, required=True)
    parser.add_argument("--g0dam-expected-aggregate", required=True)
    parser.add_argument("--joesai-source-id", required=True)
    parser.add_argument("--joesai-expected-commit", required=True)
    parser.add_argument("--joesai-expected-cases", type=int, required=True)
    parser.add_argument("--joesai-expected-aggregate", required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--failure-injection", action="store_true")
    parser.add_argument("--concurrency", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(args)
    except (ValidationFailure, ExtractionError, PackageValidationError, subprocess.TimeoutExpired, OSError) as exc:
        payload = {"status": "failed", "error": str(exc), "error_type": type(exc).__name__}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
