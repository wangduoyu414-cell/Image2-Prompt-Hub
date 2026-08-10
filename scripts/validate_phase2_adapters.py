#!/usr/bin/env python3
"""Validate the six-source fixed-Commit ingestion, inventory, sync, and zero-public boundary."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from urllib.parse import quote, urlparse

import psycopg
import psycopg.rows
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.main import create_app
from ingestion.pipeline import ExtractionError, ExtractionResult, extract
from ingestion.registry import RegistryError, load_source_config
from inventory.object_store import ObjectFact, ObjectStoreConfig, S3ObjectStore, object_key_for
from inventory.package import ImportPlan, build_import_plan
from scripts import validate_joesai_multi_source as shared
from scripts import validate_three_pilot_sources as three_source
from sync.pipeline import SyncPipelineError, SyncSettings, run_source


RUNTIME_ROOT = Path(r"C:/Users/admin/AppData/Local/i2t19")
SOURCE_GIT_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/source-git-v1")
SOURCE_SPECS = (
    ("g0dam-work-prompts", "690c2d6969a65b406b17ba7d41f18695a652c3fe", 100, 100, "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0"),
    ("joesai-commercial-prompts", "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b", 50, 50, "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293"),
    ("conardli-gpt-image-2-101", "971b67dc8cbca8cf6eb32e196fea04bddd6abe99", 162, 162, "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573"),
    ("freestylefly-awesome-gpt-image-2", "76fcd0e6b3961ef2b041547aac654f1efd1ef270", 517, 517, "ce4adddbfb74f88d0b2aee58e5ebe0f9de646eaf8dfcc5a34bcfbbd1f3e11a92"),
    ("erickkkyt-awesome-gptimage2-prompts", "1b5ec5f4f3409d2bf4cd2a4741070ce6c1429c6a", 572, 877, "a2e80796bb546f17dd5d48a0776a0144d6a9333e23a5534b10864862b5327551"),
    ("vigozhao-ai-visual-prompt-cookbook", "9fa17042b392db28bb495f7208d37f1b9c416368", 112, 224, "fb1c44c484a07b07b9756ff0186cb93f37bfb4024432339bd138591ea64db3f6"),
)
EXPECTED_CASES = {source_id: cases for source_id, _commit, cases, _generations, _aggregate in SOURCE_SPECS}
EXPECTED_GENERATIONS = {
    source_id: generations for source_id, _commit, _cases, generations, _aggregate in SOURCE_SPECS
}
EXPECTED_AGGREGATES = {
    source_id: aggregate for source_id, _commit, _cases, _generations, aggregate in SOURCE_SPECS
}


class ValidationFailure(RuntimeError):
    pass


def _external(path: Path, label: str) -> Path:
    target = path.resolve(strict=False)
    workspace = REPO_ROOT.resolve()
    if target == workspace or workspace in target.parents:
        raise ValidationFailure(f"{label} must remain outside the workspace")
    return target


def _run(command: list[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None, timeout: int = 900) -> str:
    completed = subprocess.run(
        command,
        cwd=str(cwd or REPO_ROOT),
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2000:]
        raise ValidationFailure(f"command failed ({command[0]}): {detail}")
    return completed.stdout.strip()


def _registry() -> dict[str, Any]:
    payload = json.loads((REPO_ROOT / "config" / "sources-v1.yaml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationFailure("source registry is malformed")
    return payload


def _source_rows() -> dict[str, dict[str, Any]]:
    rows = _registry().get("sources")
    if not isinstance(rows, list):
        raise ValidationFailure("source registry rows are missing")
    return {str(row["source_id"]): row for row in rows if isinstance(row, dict) and isinstance(row.get("source_id"), str)}


def _assert_authority() -> dict[str, Any]:
    registry = REPO_ROOT / "config" / "sources-v1.yaml"
    audit = REPO_ROOT / "reports" / "source-audit-v1.json"
    command = [
        sys.executable,
        "-B",
        str(REPO_ROOT / "scripts" / "validate_source_registry.py"),
        "--audit",
        str(audit),
        "--registry",
        str(registry),
        "--audit-schema",
        str(REPO_ROOT / "schemas" / "source-audit-v1.schema.json"),
        "--registry-schema",
        str(REPO_ROOT / "schemas" / "source-registry-v1.schema.json"),
        "--self-test",
        "--determinism-check",
        "--json",
    ]
    result = json.loads(_run(command, timeout=120))
    if result.get("ok") is not True or result.get("summary", {}).get("active_sources") != 6:
        raise ValidationFailure("six-source audit/registry authority did not validate")
    return result


def _repo_parts(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parts) != 2:
        raise ValidationFailure("registered repository URL is not one GitHub owner/repository pair")
    return parts[0], parts[1]


def _git(command: list[str], *, cwd: Path | None = None, timeout: int = 900) -> str:
    return _run(["git", *command], cwd=cwd, env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}, timeout=timeout)


def _build_fixed_http_repositories(http_root: Path, source_root: Path) -> list[dict[str, str]]:
    rows = _source_rows()
    evidence: list[dict[str, str]] = []
    for source_id, commit, _cases, _generations, _aggregate in SOURCE_SPECS:
        row = rows[source_id]
        repository = row["repository"]
        owner, name = _repo_parts(str(repository["url"]))
        source_mirror = source_root / "mirrors" / f"{source_id}.git"
        if not source_mirror.is_dir():
            raise ValidationFailure(f"prewarmed source mirror is missing: {source_id}")
        target = http_root / owner / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--bare", str(source_mirror), str(target)])
        branch = str(repository["default_branch"])
        _git(["update-ref", f"refs/heads/{branch}", commit], cwd=target)
        _git(["symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=target)
        _git(["update-server-info"], cwd=target)
        actual = _git(["rev-parse", f"refs/heads/{branch}"], cwd=target)
        if actual != commit:
            raise ValidationFailure(f"fixed HTTP repository did not bind the expected Commit: {source_id}")
        evidence.append({"source_id": source_id, "default_branch": branch, "commit": actual})
    return evidence


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def _http_server(root: Path) -> Iterator[str]:
    from functools import partial
    port = three_source._free_loopback_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(_QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, name="task0019-fixed-git-http", daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=15)
        if thread.is_alive():
            raise ValidationFailure("fixed Git HTTP server did not stop")


def _write_git_rewrite(data_root: Path, base_url: str) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "git-global.config").write_text(
        f'[url "{base_url}"]\n\tinsteadOf = https://github.com/\n', encoding="utf-8"
    )


def _packages_by_source(package_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for manifest_path in sorted((package_root / "packages").glob("package-*/manifest.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_id = payload.get("source_id") if isinstance(payload, dict) else None
        if not isinstance(source_id, str) or source_id in result:
            raise ValidationFailure("published package source identity is missing or duplicated")
        result[source_id] = manifest_path.parent
    if set(result) != set(EXPECTED_CASES):
        raise ValidationFailure("published package set does not equal the six active sources")
    return result


def _object_facts(plans: Sequence[ImportPlan], bucket: str) -> dict[str, ObjectFact]:
    objects: dict[str, ObjectFact] = {}
    for plan in plans:
        for asset in plan.asset_sources:
            fact = ObjectFact(
                asset.content_sha256,
                object_key_for(asset.content_sha256),
                bucket,
                asset.byte_size,
                asset.media_type,
                "content_verified",
            )
            if objects.setdefault(asset.content_sha256, fact) != fact:
                raise ValidationFailure("same content hash has contradictory object facts")
    return objects


def _assert_database_semantics(database_url: str, expected_global: dict[str, int]) -> dict[str, Any]:
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        rows = conn.execute(
            """
            SELECT p.source_id,
                   count(*) AS generations,
                   count(*) FILTER (WHERE g.source_claim->>'evidence_status' = 'source_claimed') AS claimed,
                   count(*) FILTER (WHERE g.source_claim->>'evidence_status' = 'unknown') AS unknown_claims
            FROM inventory.generation_examples AS g
            JOIN inventory.source_case_versions AS v ON v.source_case_version_id = g.source_case_version_id
            JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id = v.source_adapter_run_id
            JOIN inventory.source_revisions AS r ON r.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS p ON p.source_project_id = r.source_project_id
            GROUP BY p.source_id
            """
        ).fetchall()
        by_source = {str(row["source_id"]): row for row in rows}
        for source_id, expected in EXPECTED_GENERATIONS.items():
            row = by_source.get(source_id)
            if row is None or int(row["generations"]) != expected:
                raise ValidationFailure(f"generation count does not close for {source_id}")
            expected_claimed = expected if source_id in {"g0dam-work-prompts", "erickkkyt-awesome-gptimage2-prompts"} else 0
            if int(row["claimed"]) != expected_claimed or int(row["unknown_claims"]) != expected - expected_claimed:
                raise ValidationFailure(f"source claim semantics changed for {source_id}")
        rights = conn.execute(
            "SELECT count(*) AS total, count(*) FILTER (WHERE prompt_rights_status <> 'unknown' OR asset_rights_status <> 'unknown') AS elevated FROM inventory.rights_records"
        ).fetchone()
        if int(rights["total"]) != 1513 or int(rights["elevated"]) != 0:
            raise ValidationFailure("rights records do not remain unknown/fail-closed for all internal cases")
        snapshots = conn.execute(
            """
            SELECT p.source_id, run.registry_snapshot
            FROM inventory.source_adapter_runs AS run
            JOIN inventory.source_revisions AS r ON r.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS p ON p.source_project_id = r.source_project_id
            """
        ).fetchall()
        if len(snapshots) != 6:
            raise ValidationFailure("registry snapshots do not close for six source runs")
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
                raise ValidationFailure("registry snapshot weakened rights/publication policy")
        current = conn.execute(
            """
            SELECT v.publication_version_id, v.included_count,
                   (SELECT count(*) FROM content.publication_entries e WHERE e.publication_version_id=v.publication_version_id) AS entry_count
            FROM content.publication_current c
            JOIN content.publication_versions v ON v.publication_version_id=c.publication_version_id
            WHERE c.singleton=true
            """
        ).fetchone()
        if current is None or int(current["included_count"]) != 0 or int(current["entry_count"]) != 0:
            raise ValidationFailure("current Publication Version is not the required real zero-public state")
    if expected_global.get("source_cases") != 1513 or expected_global.get("prompt_records") != 1513:
        raise ValidationFailure("global internal case/prompt counts do not close at 1513")
    if expected_global.get("generation_examples") != 1930 or expected_global.get("generation_outputs") != 1930:
        raise ValidationFailure("global generation/output counts do not close at 1930")
    return {"per_source_generations": EXPECTED_GENERATIONS, "rights_records": 1513, "current_public_cases": 0}


def _assert_api_zero(database_url: str, endpoint: str, access_key: str, secret_key: str) -> dict[str, Any]:
    previous = {key: os.environ.get(key) for key in (
        "PUBLIC_API_DATABASE_URL", "PUBLIC_API_S3_ENDPOINT_URL", "PUBLIC_API_S3_ACCESS_KEY_ID", "PUBLIC_API_S3_SECRET_ACCESS_KEY"
    )}
    os.environ.update(
        {
            "PUBLIC_API_DATABASE_URL": database_url,
            "PUBLIC_API_S3_ENDPOINT_URL": endpoint,
            "PUBLIC_API_S3_ACCESS_KEY_ID": access_key,
            "PUBLIC_API_S3_SECRET_ACCESS_KEY": secret_key,
        }
    )
    try:
        with TestClient(create_app()) as client:
            ready = client.get("/readyz")
            listing = client.get("/api/v1/cases")
            publication = client.get("/api/v1/publication")
            missing = client.get("/api/v1/cases/not-public")
        if ready.status_code != 200 or listing.status_code != 200 or publication.status_code != 200 or missing.status_code != 404:
            raise ValidationFailure("Public API zero-public responses returned unexpected statuses")
        body = listing.json()
        if body.get("total") != 0 or body.get("cases") != [] or publication.json().get("case_count") != 0:
            raise ValidationFailure("Public API exposed internal unapproved cases")
        return {"ready": ready.json(), "list_total": 0, "publication_case_count": 0, "missing_detail_status": 404}
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _assert_disable_isolation(run_root: Path) -> dict[str, Any]:
    registry = _registry()
    target = next(row for row in registry["sources"] if row["source_id"] == "erickkkyt-awesome-gptimage2-prompts")
    target["sync"]["enabled"] = False
    disabled_path = run_root / "disabled-source-registry.json"
    disabled_path.write_text(json.dumps(registry, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    try:
        load_source_config(disabled_path, "erickkkyt-awesome-gptimage2-prompts")
    except RegistryError:
        pass
    else:
        raise ValidationFailure("disabled source remained executable")
    surviving = load_source_config(disabled_path, "freestylefly-awesome-gpt-image-2")
    return {"disabled_source": "erickkkyt-awesome-gptimage2-prompts", "surviving_source": surviving.source_id}


def _assert_extraction_failure_and_concurrency(
    *, registry: Path, audit: Path, data_root: Path, output_root: Path, source_id: str
) -> dict[str, Any]:
    published = extract(
        registry_path=registry, audit_path=audit, source_id=source_id, data_root=data_root, output_root=output_root / "baseline"
    )
    before = shared._file_hashes(published.output_path)
    failures: dict[str, str] = {}
    for point in ("after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace"):
        try:
            extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=output_root / "baseline",
                failure_point=point,
            )
        except ExtractionError as exc:
            if exc.error_code != f"injected_{point}":
                raise ValidationFailure(f"failure injection returned the wrong code: {point}") from exc
            failures[point] = exc.error_code
        else:
            raise ValidationFailure(f"failure injection unexpectedly succeeded: {point}")
        if shared._file_hashes(published.output_path) != before:
            raise ValidationFailure("failure injection changed the prior published package")
    concurrent_root = output_root / "concurrent"
    holder: dict[str, object] = {}

    def first() -> None:
        try:
            holder["result"] = extract(
                registry_path=registry,
                audit_path=audit,
                source_id=source_id,
                data_root=data_root,
                output_root=concurrent_root,
                lock_hold_seconds=0.75,
            )
        except BaseException as exc:
            holder["error"] = exc

    thread = threading.Thread(target=first, name="task0019-extraction-holder")
    thread.start()
    deadline = time.monotonic() + 30
    while not list((concurrent_root / ".locks").glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        extract(
            registry_path=registry, audit_path=audit, source_id=source_id, data_root=data_root, output_root=concurrent_root
        )
    except ExtractionError as exc:
        if exc.error_code != "run_locked":
            raise ValidationFailure("concurrent extraction returned the wrong error") from exc
    else:
        raise ValidationFailure("concurrent extraction did not fail fast")
    thread.join(timeout=600)
    result = holder.get("result")
    if thread.is_alive() or "error" in holder or not isinstance(result, ExtractionResult) or result.status != "published":
        raise ValidationFailure("concurrent extraction holder did not finish as sole publisher")
    return {"failure_codes": failures, "concurrent_second_status": "run_locked"}


def _run_child_validator(script: str, timeout: int, run_root: Path) -> dict[str, Any]:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if script == "validate_content_core.py":
        runtime = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0013")
        environment.update(
            {
                "UV_PROJECT_ENVIRONMENT": str(runtime / "venv"),
                "UV_CACHE_DIR": str(runtime / "uv-cache"),
                "TMP": str(runtime / "tmp"),
                "TEMP": str(runtime / "tmp"),
            }
        )
    elif script == "validate_public_api.py":
        runtime = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0014")
        environment.update(
            {
                "UV_PROJECT_ENVIRONMENT": str(runtime / "venv"),
                "UV_CACHE_DIR": str(runtime / "uv-cache"),
                "TMP": str(runtime / "tmp"),
                "TEMP": str(runtime / "tmp"),
            }
        )
    elif script == "validate_public_web.py":
        runtime = run_root / "w"
        environment.update(
            {
                "IMAGE2_WEB_RUNTIME_ROOT": str(runtime),
                "IMAGE2_WEB_EVIDENCE_DIR": str(runtime / "browser-evidence"),
            }
        )
    try:
        stdout = _run(
            [sys.executable, "-B", str(REPO_ROOT / "scripts" / script), "--json"],
            env=environment,
            timeout=timeout,
        )
    except ValidationFailure as exc:
        raise ValidationFailure(f"child validator failed ({script}): {exc}") from exc
    payload = json.loads(stdout)
    if payload.get("status") != "passed":
        raise ValidationFailure(f"child validator did not pass: {script}")
    return {"status": "passed", "validator": script, "gates": payload.get("gates")}


def run(
    *,
    integration_callback: Callable[[str, str, str, str, Path], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    runtime_root = _external(RUNTIME_ROOT, "TASK-0019 runtime root")
    source_root = _external(SOURCE_GIT_ROOT, "persistent source Git root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="r-", dir=runtime_root))
    project = f"task0019{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_ok = False
    source_ids = [item[0] for item in SOURCE_SPECS]
    try:
        authority = _assert_authority()
        registry_path = REPO_ROOT / "config" / "sources-v1.yaml"
        audit_path = REPO_ROOT / "reports" / "source-audit-v1.json"
        prewarmed = three_source._prewarm_source_mirrors(registry_path, source_ids, source_root)
        fixed_repositories = _build_fixed_http_repositories(run_root / "h", source_root)
        with _http_server(run_root / "h") as base_url:
            sync_git_root = run_root / "g"
            _write_git_rewrite(sync_git_root, base_url)
            postgres_port = three_source._free_loopback_port()
            s3_port = three_source._free_loopback_port()
            postgres_user = "u" + uuid.uuid4().hex[:12]
            postgres_password = uuid.uuid4().hex + uuid.uuid4().hex[:8]
            access_key = "a" + uuid.uuid4().hex[:12]
            secret_key = uuid.uuid4().hex + uuid.uuid4().hex[:8]
            shared._write_compose_env(
                env_file,
                {
                    "INVENTORY_POSTGRES_DB": "inventorytest",
                    "INVENTORY_POSTGRES_USER": postgres_user,
                    "INVENTORY_POSTGRES_PASSWORD": postgres_password,
                    "INVENTORY_POSTGRES_PORT": str(postgres_port),
                    "INVENTORY_S3_ACCESS_KEY": access_key,
                    "INVENTORY_S3_SECRET_KEY": secret_key,
                    "INVENTORY_S3_PORT": str(s3_port),
                },
            )
            database_url = f"postgresql://{quote(postgres_user)}:{quote(postgres_password)}@127.0.0.1:{postgres_port}/inventorytest"
            endpoint = f"http://127.0.0.1:{s3_port}"
            bucket = "inventory-private-phase2-six-source"
            environment = shared._runtime_env(database_url, endpoint, bucket, access_key, secret_key)
            compose_started = True
            shared._compose(["up", "-d"], env_file=env_file, project=project, timeout=900)
            shared._wait_for_services(database_url, endpoint, access_key, secret_key)
            for _label in ("initial", "repeat"):
                code, payload = shared._run_inventory(
                    ["migrate", "--migrations-dir", str(REPO_ROOT / "migrations")], environment
                )
                if code != 0 or payload.get("status") != "migrated":
                    raise ValidationFailure("database migration/replay failed")
            settings = SyncSettings(
                database_url=database_url,
                s3_endpoint_url=endpoint,
                s3_bucket=bucket,
                s3_access_key_id=access_key,
                s3_secret_access_key=secret_key,
                git_data_root=sync_git_root,
                package_root=run_root / "p",
                evidence_root=run_root / "e",
            )
            first_results: dict[str, dict[str, Any]] = {}
            failure_recovery: dict[str, Any] = {}
            for source_id, commit, _cases, _generations, _aggregate in SOURCE_SPECS:
                if source_id == "erickkkyt-awesome-gptimage2-prompts":
                    try:
                        run_source(
                            registry_path=registry_path,
                            audit_path=audit_path,
                            source_id=source_id,
                            settings=settings,
                            failure_point="after_extract",
                        )
                    except SyncPipelineError as exc:
                        if exc.error_code != "injected_after_extract":
                            raise ValidationFailure(
                                f"sync failure injection returned the wrong error: {exc.error_code}"
                            ) from exc
                        failure_recovery["initial_error"] = exc.error_code
                    else:
                        raise ValidationFailure("sync failure injection unexpectedly succeeded")
                result = run_source(
                    registry_path=registry_path,
                    audit_path=audit_path,
                    source_id=source_id,
                    settings=settings,
                )
                if result.status != "completed" or result.candidate_revision_sha != commit or result.quality_gate.get("status") != "passed":
                    raise ValidationFailure(f"initial sync did not complete at the fixed Commit: {source_id}")
                first_results[source_id] = result.as_json()
                if source_id == "erickkkyt-awesome-gptimage2-prompts":
                    failure_recovery["recovered_status"] = result.status
            replays: dict[str, str] = {}
            for source_id, commit, _cases, _generations, _aggregate in SOURCE_SPECS:
                replay = run_source(
                    registry_path=registry_path,
                    audit_path=audit_path,
                    source_id=source_id,
                    settings=settings,
                )
                if replay.status != "no_change" or replay.candidate_revision_sha != commit:
                    raise ValidationFailure(f"same-Commit sync replay was not no_change: {source_id}")
                replays[source_id] = replay.status
            package_paths = _packages_by_source(settings.package_root)
            plans = {
                source_id: build_import_plan(
                    package_root=package_paths[source_id], registry_path=registry_path, audit_path=audit_path
                )
                for source_id in source_ids
            }
            for source_id, plan in plans.items():
                if len(plan.adapter_output["records"]) != EXPECTED_CASES[source_id]:
                    raise ValidationFailure(f"package case count does not close: {source_id}")
                if sum(len(doc["generation_examples"]) for doc in plan.generation_documents) != EXPECTED_GENERATIONS[source_id]:
                    raise ValidationFailure(f"package generation count does not close: {source_id}")
                if plan.metrics.get("case_fingerprint_aggregate_sha256") != EXPECTED_AGGREGATES[source_id]:
                    raise ValidationFailure(f"package aggregate does not close: {source_id}")
            ordered_plans = tuple(plans[source_id] for source_id in source_ids)
            expected_global = shared._expected_global_counts(ordered_plans)
            observed_global = shared._database_counts(database_url)
            if observed_global != expected_global:
                raise ValidationFailure(
                    "six-source global database counts do not close: "
                    + json.dumps({"expected": expected_global, "observed": observed_global}, sort_keys=True)
                )
            semantics = _assert_database_semantics(database_url, expected_global)
            store = S3ObjectStore(ObjectStoreConfig(endpoint, bucket, access_key, secret_key))
            store.ensure_private_bucket()
            objects = _object_facts(ordered_plans, bucket)
            downloaded = store.download_hashes(objects)
            if len(downloaded) != len(objects) or set(downloaded.values()) != set(objects):
                raise ValidationFailure("all immutable object hashes were not reverified")
            api = _assert_api_zero(database_url, endpoint, access_key, secret_key)
            integration = (
                dict(integration_callback(database_url, endpoint, access_key, secret_key, run_root))
                if integration_callback is not None
                else None
            )
            isolation = _assert_disable_isolation(run_root)
            failure_concurrency = _assert_extraction_failure_and_concurrency(
                registry=registry_path,
                audit=audit_path,
                data_root=sync_git_root,
                output_root=run_root / "vigo-failure-concurrency",
                source_id="vigozhao-ai-visual-prompt-cookbook",
            )
            for source_id in source_ids:
                shared._assert_extraction_cleanup(sync_git_root, settings.package_root, source_id)
            source_cache = three_source._source_cache_evidence(source_root, prewarmed)
        compose_cleanup_before_children = shared._cleanup_compose(env_file, project)
        compose_started = False
        cleanup_ok = compose_cleanup_before_children
        if not compose_cleanup_before_children:
            raise ValidationFailure("six-source Compose cleanup did not complete")
        child_validators = {
            "content": _run_child_validator("validate_content_core.py", 1800, run_root),
            "api": _run_child_validator("validate_public_api.py", 1800, run_root),
            "web": _run_child_validator("validate_public_web.py", 1800, run_root),
        }
        result = {
            "status": "passed",
            "authority": authority["summary"],
            "fixed_http_repositories": fixed_repositories,
            "source_snapshot_cache": source_cache,
            "initial_sync": first_results,
            "same_commit_replays": replays,
            "sync_failure_recovery": failure_recovery,
            "per_source": {
                source_id: {
                    "cases": EXPECTED_CASES[source_id],
                    "generation_examples": EXPECTED_GENERATIONS[source_id],
                    "aggregate": EXPECTED_AGGREGATES[source_id],
                    "source_files": len(plans[source_id].source_files),
                }
                for source_id in source_ids
            },
            "global_database_counts": expected_global,
            "object_hashes_reverified": len(downloaded),
            "database_semantics": semantics,
            "public_api_zero": api,
            "source_disable_isolation": isolation,
            "failure_and_concurrency": failure_concurrency,
            "child_validators": child_validators,
            "compose_cleanup": True,
            "temporary_runtime_cleaned": True,
            "gates": {f"GATE-{index:03d}": "passed" for index in range(1, 6)},
        }
        if integration is not None:
            result["integration_callback"] = integration
        return result
    finally:
        if compose_started:
            cleanup_ok = shared._cleanup_compose(env_file, project)
        shared._remove_tree(run_root)
        three_source._assert_no_temporary_worktrees(source_root, source_ids)
        three_source._remove_empty_worktree_directories(source_root, source_ids)
        if compose_started and not cleanup_ok:
            raise ValidationFailure("task-owned Compose cleanup did not complete")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "PASS: Phase 2 adapters and six-source closure")
        return 0
    except Exception as exc:
        payload = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:2000]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {payload['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
