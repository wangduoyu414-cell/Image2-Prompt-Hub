"""Fresh three-source fixed-commit extraction and private inventory validation.

The validator owns only a random, loopback-only Compose project and runtime
directory below TASK-0009.  It never runs code from an upstream checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
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

from ingestion.pipeline import ExtractionError, ExtractionResult, extract
from ingestion.git_snapshot import GitSnapshotError, fixed_snapshot
from ingestion.registry import SourceConfig, load_source_config
from inventory.object_store import ObjectFact, ObjectStoreConfig, S3ObjectStore, object_key_for
from inventory.package import ImportPlan, PackageValidationError
from scripts import validate_joesai_multi_source as shared


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0009")
EXPECTED_SOURCE_GIT_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/source-git-v1")
CONARDLI_FAILURE_POINTS = ("after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace")


class ValidationFailure(RuntimeError):
    """A fail-closed live-validation conclusion."""


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
            raise ValidationFailure(f"{name} must use the fixed TASK-0009 external runtime path")
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


def _source_mirror_path(source_root: Path, source_id: str) -> Path:
    return source_root / "mirrors" / f"{source_id}.git"


def _bounded_git_error_message(value: str) -> str:
    """Keep source-snapshot diagnostics useful without exposing URL userinfo."""

    normalized = " ".join(value.split())
    redacted = re.sub(r"(https?://)[^/\s'\"@]+@", r"\1<redacted>@", normalized)
    return redacted[:1_000]


def _assert_no_temporary_worktrees(source_root: Path, source_ids: Sequence[str]) -> None:
    for source_id in source_ids:
        worktrees = source_root / "worktrees" / source_id
        if worktrees.exists() and any(worktrees.glob("run-*")):
            raise ValidationFailure(f"{source_id} retained a temporary source-cache worktree")


def _remove_empty_worktree_directories(source_root: Path, source_ids: Sequence[str]) -> None:
    """Remove only empty temporary-worktree directories owned by this run.

    Mirrors/config/hooks are the cache's only persistent state.  ``fixed_snapshot``
    correctly removes each detached ``run-*`` worktree, but Git's parent
    directories are also temporary.  We never recurse or remove a non-empty
    directory: such state is either a residue or belongs to another owner and
    therefore fails closed.
    """

    root = source_root / "worktrees"
    for source_id in source_ids:
        worktrees = root / source_id
        if worktrees.is_symlink():
            raise ValidationFailure(f"{source_id} source-cache worktree path must not be a symlink")
        if worktrees.exists():
            if any(worktrees.iterdir()):
                raise ValidationFailure(f"{source_id} retained non-empty source-cache worktree state")
            worktrees.rmdir()
    if root.is_symlink():
        raise ValidationFailure("source-cache worktree root must not be a symlink")
    if root.exists():
        if any(root.iterdir()):
            raise ValidationFailure("source cache retained non-empty temporary worktree state")
        root.rmdir()


def _prewarm_source_mirror(config: SourceConfig, source_root: Path) -> None:
    """Freshly verify a persistent source mirror before any extraction/import.

    ``fixed_snapshot`` remains the sole owner of Git fetch, fixed-commit,
    safe-tree, and detached-worktree behavior. This wrapper selects the
    external persistent root, extends only the prewarm timeout, reports a
    stable diagnostic, and removes a partial mirror only when this invocation
    created that mirror path.
    """

    mirror_path = _source_mirror_path(source_root, config.source_id)
    mirror_existed_before = mirror_path.exists()
    try:
        with fixed_snapshot(config, source_root, workspace_root=REPO_ROOT, timeout_seconds=900):
            pass
    except GitSnapshotError as exc:
        cleanup_detail = "existing_mirror_retained" if mirror_existed_before else "no_new_mirror_created"
        if not mirror_existed_before and mirror_path.exists():
            try:
                shared._remove_tree(mirror_path)
            except OSError as cleanup_exc:
                cleanup_detail = f"new_incomplete_mirror_cleanup_failed={_bounded_git_error_message(str(cleanup_exc))}"
            else:
                cleanup_detail = "new_incomplete_mirror_removed"
        raise ValidationFailure(
            "source snapshot prewarm failed "
            f"source_id={config.source_id} "
            f"git_error_code={exc.error_code} "
            f"git_error={_bounded_git_error_message(str(exc))} "
            f"cache_cleanup={cleanup_detail}"
        ) from exc
    _assert_no_temporary_worktrees(source_root, (config.source_id,))
    _remove_empty_worktree_directories(source_root, (config.source_id,))


def _prewarm_source_mirrors(registry: Path, source_ids: Sequence[str], source_root: Path) -> list[str]:
    prewarmed: list[str] = []
    for source_id in source_ids:
        _prewarm_source_mirror(load_source_config(registry, source_id), source_root)
        prewarmed.append(source_id)
    _assert_no_temporary_worktrees(source_root, prewarmed)
    _remove_empty_worktree_directories(source_root, prewarmed)
    return prewarmed


def _source_cache_evidence(source_root: Path, prewarmed_source_ids: Sequence[str]) -> dict[str, Any]:
    _assert_no_temporary_worktrees(source_root, prewarmed_source_ids)
    _remove_empty_worktree_directories(source_root, prewarmed_source_ids)
    retained = [
        source_id
        for source_id in prewarmed_source_ids
        if _source_mirror_path(source_root, source_id).is_dir()
    ]
    if retained != list(prewarmed_source_ids):
        raise ValidationFailure("persistent source mirror cache is incomplete after prewarm")
    return {
        "persistent_source_git_root": str(source_root),
        "prewarmed_source_ids": list(prewarmed_source_ids),
        "retained_mirror_source_ids": retained,
        "temporary_worktrees_cleaned": True,
    }


def _verify_conardli_failure_and_concurrency(
    *, registry: Path, audit: Path, data_root: Path, output_root: Path, source_id: str
) -> dict[str, Any]:
    published = extract(
        registry_path=registry,
        audit_path=audit,
        source_id=source_id,
        data_root=data_root,
        output_root=output_root / "failure-baseline",
    )
    before = shared._file_hashes(published.output_path)
    failures: dict[str, str] = {}
    for point in CONARDLI_FAILURE_POINTS:
        try:
            extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=output_root / "failure-baseline",
                failure_point=point,
            )
        except ExtractionError as exc:
            expected = f"injected_{point}"
            if exc.error_code != expected:
                raise ValidationFailure(f"ConardLi failure injection {point} returned the wrong error") from exc
            failures[point] = expected
        else:
            raise ValidationFailure(f"ConardLi failure injection {point} unexpectedly succeeded")
        if shared._file_hashes(published.output_path) != before:
            raise ValidationFailure(f"ConardLi failure injection {point} changed the prior published package")

    concurrent_output = output_root / "concurrent"
    holder: dict[str, object] = {}

    def first_run() -> None:
        try:
            holder["result"] = extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=concurrent_output,
                lock_hold_seconds=0.75,
            )
        except BaseException as exc:  # retain the original failure for the parent assertion
            holder["error"] = exc

    thread = threading.Thread(target=first_run, name="task0009-conardli-extraction-holder")
    thread.start()
    deadline = time.monotonic() + 15.0
    while not list((concurrent_output / ".locks").glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        extract(
            registry_path=registry,
            audit_path=audit,
            source_id=source_id,
            data_root=data_root,
            output_root=concurrent_output,
        )
    except ExtractionError as exc:
        if exc.error_code != "run_locked":
            raise ValidationFailure("ConardLi concurrent extraction returned the wrong error") from exc
    else:
        raise ValidationFailure("ConardLi concurrent extraction did not fail fast for the lock")
    thread.join(timeout=300)
    if thread.is_alive() or "error" in holder:
        raise ValidationFailure("ConardLi concurrent extraction holder did not finish cleanly")
    result = holder.get("result")
    if not isinstance(result, ExtractionResult) or result.status != "published":
        raise ValidationFailure("ConardLi concurrent extraction holder was not the sole publisher")
    shared._assert_extraction_cleanup(data_root, concurrent_output, source_id)
    return {"failure_codes": failures, "concurrent_second_status": "run_locked"}


def _assert_expected_source_files(plans: dict[str, ImportPlan]) -> None:
    expected = {
        "g0dam-work-prompts": 101,
        "joesai-commercial-prompts": 101,
        "conardli-gpt-image-2-101": 326,
    }
    if set(plans) != set(expected):
        raise ValidationFailure("three-source plans do not use the expected source identities")
    for source_id, count in expected.items():
        if len(plans[source_id].source_files) != count:
            raise ValidationFailure(f"{source_id} source-file plan does not close at {count}")


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
            claimed = count if source_id == "g0dam-work-prompts" else 0
            unknown = 0 if source_id == "g0dam-work-prompts" else count
            if int(row["source_claims"]) != claimed or int(row["unknown_claims"]) != unknown:
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
        if len(snapshots) != len(expected_cases):
            raise ValidationFailure("inventory registry snapshots do not close for all three sources")
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


def _object_facts(plans: Sequence[ImportPlan], bucket: str) -> dict[str, ObjectFact]:
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
    return objects


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime_environment = _runtime_environment()
    if args.runs != 2:
        raise ValidationFailure("TASK-0009 requires exactly two independent extraction runs per source")
    if not args.failure_injection or not args.concurrency:
        raise ValidationFailure("TASK-0009 requires ConardLi failure injection and concurrency validation")
    if (args.g0dam_expected_cases, args.joesai_expected_cases, args.conardli_expected_cases) != (100, 50, 162):
        raise ValidationFailure("TASK-0009 fixed case counts must remain 100, 50, and 162")
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0009 runtime root")
    source_root = _must_be_external(EXPECTED_SOURCE_GIT_ROOT, REPO_ROOT.resolve(), "source Git cache root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="live-three-pilot-sources-", dir=runtime_root))
    project = f"task0009{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_ok = False
    source_ids: list[str] = []
    try:
        registry = Path(args.registry).resolve()
        audit = Path(args.audit).resolve()
        extraction_specs = (
            (args.g0dam_source_id, args.g0dam_expected_commit, args.g0dam_expected_cases, args.g0dam_expected_aggregate, "g0dam-extraction-package/v1", "g0dam-extraction-metrics/v1"),
            (args.joesai_source_id, args.joesai_expected_commit, args.joesai_expected_cases, args.joesai_expected_aggregate, "extraction-package/v1", "extraction-metrics/v1"),
            (args.conardli_source_id, args.conardli_expected_commit, args.conardli_expected_cases, args.conardli_expected_aggregate, "extraction-package/v1", "extraction-metrics/v1"),
        )
        plans: dict[str, ImportPlan] = {}
        packages: dict[str, Path] = {}
        extraction_evidence: dict[str, dict[str, Any]] = {}
        source_ids = [source_id for source_id, *_unused in extraction_specs]
        prewarmed_source_ids = _prewarm_source_mirrors(registry, source_ids, source_root)
        for source_id, commit, case_count, aggregate, package_schema, metrics_schema in extraction_specs:
            plan, package, evidence = shared._extract_source_twice(
                source_id=source_id,
                registry=registry,
                audit=audit,
                data_root=source_root,
                output_root=run_root / f"{source_id}-extraction",
                expected_commit=commit,
                expected_cases=case_count,
                expected_aggregate=aggregate,
                expected_package_schema=package_schema,
                expected_metrics_schema=metrics_schema,
            )
            plans[source_id] = plan
            packages[source_id] = package
            extraction_evidence[source_id] = evidence
        _assert_expected_source_files(plans)
        conardli_failure = _verify_conardli_failure_and_concurrency(
            registry=registry,
            audit=audit,
            data_root=source_root,
            output_root=run_root / "conardli-failure-concurrency",
            source_id=args.conardli_source_id,
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
        shared._write_compose_env(env_file, compose_values)
        database_url = f"postgresql://{quote(postgres_user)}:{quote(postgres_password)}@127.0.0.1:{postgres_port}/inventorytest"
        endpoint = f"http://127.0.0.1:{s3_port}"
        bucket = "inventory-private-three-source"
        environment = shared._runtime_env(database_url, endpoint, bucket, s3_access_key, s3_secret_key)
        compose_started = True
        shared._compose(["up", "-d"], env_file=env_file, project=project, timeout=900)
        shared._wait_for_services(database_url, endpoint, s3_access_key, s3_secret_key)
        for label in ("initial", "repeat"):
            code, payload = shared._run_inventory(
                ["migrate", "--migrations-dir", str(REPO_ROOT / "migrations")], environment
            )
            if code != 0 or payload.get("status") != "migrated":
                raise ValidationFailure(f"{label} inventory migration failed")

        imports: dict[str, dict[str, Any]] = {}
        for source_id, plan in plans.items():
            code, payload = shared._run_inventory(
                shared._import_argv(registry, audit, packages[source_id], source_root), environment
            )
            if code != 0 or payload.get("status") != "imported" or not isinstance(payload.get("summary"), dict):
                raise ValidationFailure(f"initial {source_id} inventory import failed")
            if payload["summary"].get("counts") != shared._expected_run_counts(plan):
                raise ValidationFailure(f"{source_id} per-run inventory counts do not close")
            imports[source_id] = payload

        ordered_plans = tuple(plans[source_id] for source_id, *_rest in extraction_specs)
        expected_global = shared._expected_global_counts(ordered_plans)
        if expected_global["source_files"] != 528 or expected_global["source_cases"] != 312:
            raise ValidationFailure("three-source expected global counts do not close at 528 source files and 312 cases")
        if shared._database_counts(database_url) != expected_global:
            raise ValidationFailure("three-source global database counts do not close")
        per_run = {source_id: shared._inspect(environment, plan.idempotency_key) for source_id, plan in plans.items()}
        for source_id, plan in plans.items():
            if per_run[source_id].get("counts") != shared._expected_run_counts(plan):
                raise ValidationFailure(f"{source_id} inspection was contaminated by another source")

        objects = _object_facts(ordered_plans, bucket)
        store = S3ObjectStore(ObjectStoreConfig(endpoint, bucket, s3_access_key, s3_secret_key))
        store.ensure_private_bucket()
        downloaded = store.download_hashes(objects)
        if len(downloaded) != len(objects) or set(downloaded.values()) != set(objects):
            raise ValidationFailure("all cross-source immutable objects were not download-hash verified")
        expected_cases = {
            args.g0dam_source_id: args.g0dam_expected_cases,
            args.joesai_source_id: args.joesai_expected_cases,
            args.conardli_source_id: args.conardli_expected_cases,
        }
        _assert_rights_and_publication(database_url, expected_cases)
        before_counts = shared._database_counts(database_url)
        before_keys = shared._object_keys(endpoint, bucket, s3_access_key, s3_secret_key)
        replays: dict[str, str] = {}
        for source_id, package in packages.items():
            code, payload = shared._run_inventory(
                shared._import_argv(registry, audit, package, source_root), environment
            )
            if code != 0 or payload.get("status") != "verified_existing":
                raise ValidationFailure(f"{source_id} inventory replay was not verified_existing")
            replays[source_id] = str(payload["status"])
        if shared._database_counts(database_url) != before_counts or shared._object_keys(endpoint, bucket, s3_access_key, s3_secret_key) != before_keys:
            raise ValidationFailure("three-source inventory replay grew global database or object state")
        for source_id in plans:
            shared._assert_extraction_cleanup(source_root, run_root / f"{source_id}-extraction" / "first", source_id)

        source_cache = _source_cache_evidence(source_root, prewarmed_source_ids)

        return {
            "status": "passed",
            "environment": runtime_environment,
            "docker": {
                "postgres_image": shared.POSTGRES_IMAGE,
                "legacy_s3_image": shared.MINIO_IMAGE,
                "loopback_only": True,
            },
            "extractions": extraction_evidence,
            "fresh_mirror_sources": prewarmed_source_ids,
            "source_snapshot_cache": source_cache,
            "conardli_failure_and_concurrency": conardli_failure,
            "per_run_counts": {source_id: summary["counts"] for source_id, summary in per_run.items()},
            "global_database_counts": expected_global,
            "object_download_hash_count": len(downloaded),
            "replay_statuses": replays,
            "rights_publication_fail_closed": True,
            "gates": {"GATE-001": "passed", "GATE-002": "passed", "GATE-003": "passed", "GATE-004": "passed"},
            "temporary_runtime_cleaned": True,
            "compose_cleanup": True,
        }
    finally:
        if compose_started:
            cleanup_ok = shared._cleanup_compose(env_file, project)
        shared._remove_tree(run_root)
        _assert_no_temporary_worktrees(source_root, source_ids)
        _remove_empty_worktree_directories(source_root, source_ids)
        if compose_started and not cleanup_ok:
            raise ValidationFailure("isolated Compose cleanup did not complete")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated TASK-0009 three-source PostgreSQL/S3/Git validator.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    for prefix in ("g0dam", "joesai", "conardli"):
        parser.add_argument(f"--{prefix}-source-id", required=True)
        parser.add_argument(f"--{prefix}-expected-commit", required=True)
        parser.add_argument(f"--{prefix}-expected-cases", type=int, required=True)
        parser.add_argument(f"--{prefix}-expected-aggregate", required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--failure-injection", action="store_true")
    parser.add_argument("--concurrency", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(args)
    except (
        ValidationFailure,
        shared.ValidationFailure,
        ExtractionError,
        PackageValidationError,
        subprocess.TimeoutExpired,
        OSError,
    ) as exc:
        payload = {"status": "failed", "error": str(exc), "error_type": type(exc).__name__}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
