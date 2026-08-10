"""Fresh local PostgreSQL evidence for the fail-closed Content Core slice."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
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

import psycopg

from content.database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings
from inventory.database import DatabaseConfig, InventoryDatabase


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0013")
POSTGRES_IMAGE = "postgres:18.4@sha256:3a82e1f56c8f0f5616a11103ac3d47e632c3938698946a7ad26da0df1334744a"


class ValidationFailure(RuntimeError):
    """A fail-closed live validation conclusion."""


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
            raise ValidationFailure(f"{name} must use the fixed TASK-0013 external runtime path")
        observed[name] = str(actual)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValidationFailure("PYTHONDONTWRITEBYTECODE must equal 1")
    return observed


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _token(length: int = 24) -> str:
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
        raise ValidationFailure("isolated PostgreSQL Compose operation failed")
    return completed


def _write_env(path: Path, values: dict[str, str]) -> None:
    required = {
        "INVENTORY_POSTGRES_DB",
        "INVENTORY_POSTGRES_USER",
        "INVENTORY_POSTGRES_PASSWORD",
        "INVENTORY_POSTGRES_PORT",
        "INVENTORY_S3_ACCESS_KEY",
        "INVENTORY_S3_SECRET_KEY",
        "INVENTORY_S3_PORT",
    }
    if set(values) != required:
        raise ValidationFailure("isolated Compose environment differs from the task contract")
    path.write_text("".join(f"{key}={values[key]}\n" for key in sorted(values)), encoding="utf-8")


def _repository_migration_manifest(migrations_dir: Path) -> list[dict[str, str]]:
    """Return the exact ordered migration authority used by the live database."""

    expected: list[dict[str, str]] = []
    seen_versions: set[str] = set()
    for path in sorted(migrations_dir.glob("*.sql")):
        match = re.fullmatch(r"(\d{4}_[a-z0-9_]+)\.sql", path.name)
        if match is None or not path.is_file():
            raise ValidationFailure("repository migration manifest contains an invalid SQL filename")
        version = match.group(1)
        if version in seen_versions:
            raise ValidationFailure(f"repository migration manifest duplicates version {version}")
        seen_versions.add(version)
        expected.append({"version": version, "checksum_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not expected:
        raise ValidationFailure("repository migration manifest is empty")
    return expected


def _assert_migration_results(
    results: Sequence[dict[str, str]],
    expected: Sequence[dict[str, str]],
    *,
    phase: str,
    allowed_statuses: set[str],
) -> None:
    """Fail closed unless every persisted migration exactly matches repository authority."""

    if len(results) != len(expected):
        raise ValidationFailure(f"{phase} migration result count does not match repository manifest")
    seen_versions: set[str] = set()
    for index, (actual, authority) in enumerate(zip(results, expected, strict=True)):
        version = actual.get("version")
        if not isinstance(version, str):
            raise ValidationFailure(f"{phase} migration result {index} has no valid version")
        if version in seen_versions:
            raise ValidationFailure(f"{phase} migration results duplicate version {version}")
        seen_versions.add(version)
        if version != authority["version"]:
            raise ValidationFailure(f"{phase} migration version mismatch at index {index}")
        if actual.get("checksum_sha256") != authority["checksum_sha256"]:
            raise ValidationFailure(f"{phase} migration checksum mismatch for {version}")
        status = actual.get("status")
        if status not in allowed_statuses:
            raise ValidationFailure(f"{phase} migration {version} has unexpected status {status!r}")


def _wait_for_postgres(database_url: str) -> None:
    deadline = time.monotonic() + 150.0
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=3) as conn:
                conn.execute("SELECT 1").fetchone()
            return
        except psycopg.Error:
            time.sleep(1.0)
    raise ValidationFailure("isolated PostgreSQL service did not become ready")


def _run_content(argv: list[str], environment: dict[str, str]) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "content", *argv, "--json"],
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValidationFailure("Content Core CLI did not produce one JSON result") from exc
    if not isinstance(payload, dict):
        raise ValidationFailure("Content Core CLI produced a non-object result")
    return completed.returncode, payload


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _seed_inventory(database_url: str) -> dict[str, int]:
    """Create four immutable representative examples directly, without Git or S3."""

    generation_rows: dict[str, int] = {}
    canonical_rows: dict[str, int] = {}
    hashes = {label: _sha(label) for label in ("input-shared", "output-shared", "output-different", "output-blocked")}
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.transaction():
            project = conn.execute(
                "INSERT INTO inventory.source_projects(source_id, repository_id) VALUES (%s, %s) RETURNING source_project_id",
                ("content-core-seed", "local/content-core-seed"),
            ).fetchone()
            if not project:
                raise ValidationFailure("representative source project could not be seeded")
            project_id = int(project["source_project_id"])
            revision = conn.execute(
                "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s, %s) RETURNING source_revision_id",
                (project_id, "f" * 40),
            ).fetchone()
            if not revision:
                raise ValidationFailure("representative source revision could not be seeded")
            revision_id = int(revision["source_revision_id"])
            run = conn.execute(
                """
                INSERT INTO inventory.source_adapter_runs
                  (source_revision_id, adapter_id, adapter_version, contract_version, package_idempotency_key,
                   manifest_stable_sha256, semantic_digest, coverage, metrics, manifest, registry_snapshot, state)
                VALUES (%s, 'content-seed', 'v1', 'content-contract-v1', 'content-seed:fixed', %s, %s,
                        '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, %s::jsonb, 'ready')
                RETURNING source_adapter_run_id
                """,
                (revision_id, _sha("manifest"), _sha("semantic"), json.dumps({"repository": {"repository_id": "local/content-core-seed"}})),
            ).fetchone()
            if not run:
                raise ValidationFailure("representative adapter run could not be seeded")
            run_id = int(run["source_adapter_run_id"])
            for label, content_hash in hashes.items():
                conn.execute(
                    """
                    INSERT INTO inventory.assets(content_sha256, object_key, object_bucket, byte_size, media_type, integrity_state)
                    VALUES (%s, %s, 'private-seed', 2048, 'image/png', 'verified')
                    """,
                    (content_hash, f"sha256/{content_hash[:2]}/{content_hash}"),
                )
            cases = (
                ("exact-a", hashes["output-shared"]),
                ("exact-b", hashes["output-shared"]),
                ("different-output", hashes["output-different"]),
                ("blocked-output", hashes["output-blocked"]),
            )
            for ordinal, (case_key, output_hash) in enumerate(cases):
                source_path = f"seed/{case_key}.json"
                source_url = f"https://seed.invalid/{case_key}.json"
                source_file = conn.execute(
                    "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s, %s, %s) RETURNING source_file_id",
                    (revision_id, source_path, source_url),
                ).fetchone()
                source_case = conn.execute(
                    "INSERT INTO inventory.source_cases(source_project_id, source_case_key) VALUES (%s, %s) RETURNING source_case_id",
                    (project_id, case_key),
                ).fetchone()
                if not source_file or not source_case:
                    raise ValidationFailure("representative case source rows could not be seeded")
                source_file_id = int(source_file["source_file_id"])
                case_version = conn.execute(
                    """
                    INSERT INTO inventory.source_case_versions
                      (source_case_id, source_revision_id, source_adapter_run_id, source_file_id, source_locator, adapter_record, generation_document, contract_state)
                    VALUES (%s, %s, %s, %s, %s::jsonb, '{}'::jsonb, '{}'::jsonb, 'contract_valid')
                    RETURNING source_case_version_id
                    """,
                    (int(source_case["source_case_id"]), revision_id, run_id, source_file_id, json.dumps({"source_path": source_path})),
                ).fetchone()
                if not case_version:
                    raise ValidationFailure("representative case version could not be seeded")
                case_version_id = int(case_version["source_case_version_id"])
                raw_prompt = "Create a precise glass sculpture under soft studio light."
                prompt = conn.execute(
                    """
                    INSERT INTO inventory.prompt_records
                      (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                    VALUES (%s, 'original', %s, 'en', %s, %s::jsonb, %s)
                    RETURNING prompt_record_id
                    """,
                    (case_version_id, raw_prompt, source_file_id, json.dumps({"source_path": source_path, "source_url": source_url}), _sha(raw_prompt)),
                ).fetchone()
                if not prompt:
                    raise ValidationFailure("representative prompt could not be seeded")
                prompt_id = int(prompt["prompt_record_id"])
                input_source = conn.execute(
                    """
                    INSERT INTO inventory.asset_sources
                      (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                    VALUES (%s, %s, %s, %s, 'input_reference', %s::jsonb)
                    RETURNING asset_source_id
                    """,
                    (case_version_id, f"input-{ordinal}", source_file_id, hashes["input-shared"], json.dumps({"source_path": source_path, "source_url": source_url})),
                ).fetchone()
                output_source = conn.execute(
                    """
                    INSERT INTO inventory.asset_sources
                      (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                    VALUES (%s, %s, %s, %s, 'output_primary', %s::jsonb)
                    RETURNING asset_source_id
                    """,
                    (case_version_id, f"output-{ordinal}", source_file_id, output_hash, json.dumps({"source_path": source_path, "source_url": source_url})),
                ).fetchone()
                generation = conn.execute(
                    """
                    INSERT INTO inventory.generation_examples
                      (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                    VALUES (%s, %s, %s, %s::jsonb, 'contract_valid')
                    RETURNING generation_example_row_id
                    """,
                    (
                        f"generation:{case_key}:output-primary",
                        case_version_id,
                        prompt_id,
                        json.dumps({"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": {"size": "1024x1024"}}),
                    ),
                ).fetchone()
                if not input_source or not output_source or not generation:
                    raise ValidationFailure("representative generation rows could not be seeded")
                generation_id = int(generation["generation_example_row_id"])
                conn.execute(
                    "INSERT INTO inventory.generation_inputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, 0, %s)",
                    (generation_id, int(input_source["asset_source_id"])),
                )
                conn.execute(
                    "INSERT INTO inventory.generation_outputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, 0, %s)",
                    (generation_id, int(output_source["asset_source_id"])),
                )
                conn.execute(
                    """
                    INSERT INTO inventory.pairing_evidence(generation_example_row_id, ordinal, method, status, evidence)
                    VALUES (%s, 0, 'explicit_structured_reference', 'strong', %s::jsonb)
                    """,
                    (generation_id, json.dumps(["representative fixed local case"])),
                )
                conn.execute(
                    """
                    INSERT INTO inventory.rights_records(source_case_version_id, prompt_rights_status, asset_rights_status, evidence_urls, note)
                    VALUES (%s, 'unknown', 'unknown', '[]'::jsonb, 'inventory evidence remains unknown')
                    """,
                    (case_version_id,),
                )
                generation_rows[case_key] = generation_id
    return generation_rows


def _inventory_counts(database_url: str) -> dict[str, int]:
    tables = ("source_projects", "source_revisions", "source_files", "source_adapter_runs", "source_cases", "source_case_versions", "prompt_records", "assets", "asset_sources", "generation_examples", "generation_inputs", "generation_outputs", "pairing_evidence", "rights_records")
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        return {table: int(conn.execute(f"SELECT count(*) AS count FROM inventory.{table}").fetchone()["count"]) for table in tables}


def _content_query(database_url: str, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def _assert_no_orphans(project: str) -> None:
    checks = (
        ["docker", "ps", "-a", "--format", "{{.Names}} {{.Labels}}"],
        ["docker", "network", "ls", "--format", "{{.Name}}"],
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
    )
    for command in checks:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode != 0 or any(project.lower() in line.lower() for line in completed.stdout.splitlines()):
            raise ValidationFailure("isolated Compose cleanup left a task-owned resource")


def _assert_immutable_guards(database_url: str, *, active_version_id: int, generation_example_row_id: int) -> None:
    """Exercise database triggers without mutating any durable representative fact."""

    statements = (
        ("UPDATE content.canonical_memberships SET canonical_case_id=canonical_case_id WHERE generation_example_row_id=%s", (generation_example_row_id,)),
        ("UPDATE content.rights_review_events SET reviewer=reviewer WHERE generation_example_row_id=%s", (generation_example_row_id,)),
        ("UPDATE content.publication_entries SET snapshot=snapshot WHERE publication_version_id=%s", (active_version_id,)),
        ("DELETE FROM content.publication_versions WHERE publication_version_id=%s", (active_version_id,)),
    )
    with psycopg.connect(database_url, autocommit=True) as conn:
        for statement, parameters in statements:
            try:
                conn.execute(statement, parameters)
            except psycopg.Error:
                continue
            raise ValidationFailure("Content Core immutable database trigger permitted a mutation")


def _assert_future_review_rejected(database_url: str, *, generation_example_row_id: int) -> None:
    """The database itself must reject a forged future human-review timestamp."""

    with psycopg.connect(database_url, autocommit=True) as conn:
        try:
            conn.execute(
                """
                INSERT INTO content.rights_review_events
                  (generation_example_row_id, repository_license, prompt_rights, asset_rights, author,
                   original_url, evidence_url, reviewer, reviewed_at, display_policy)
                VALUES (%s, 'CC-BY-4.0', 'approved', 'approved', 'Representative Author',
                        'https://seed.invalid/original', 'https://seed.invalid/license', 'human-reviewer',
                        statement_timestamp() + interval '1 day', 'mirror_allowed')
                """,
                (generation_example_row_id,),
            )
        except psycopg.Error:
            return
    raise ValidationFailure("future-dated rights review event was accepted")


def _assert_link_only_storage_paths_rejected(
    database_url: str, *, canonical_case_id: int, generation_example_row_id: int
) -> None:
    """Exercise the database guard independently of the Python snapshot helper."""

    invalid_paths = (
        ("outputs", "object_key"),
        ("outputs", "object_bucket"),
        ("inputs", "object_key"),
        ("inputs", "object_bucket"),
    )
    with psycopg.connect(database_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
        for collection, field in invalid_paths:
            version = conn.execute(
                "INSERT INTO content.publication_versions(state) VALUES ('building') RETURNING publication_version_id"
            ).fetchone()
            if not version:
                raise ValidationFailure("link_only database guard test could not create a building version")
            version_id = int(version["publication_version_id"])
            snapshot = {
                "rights": {"display_policy": "link_only"},
                "outputs": [],
                "inputs": [],
            }
            snapshot[collection].append({field: "private-storage-reference"})
            try:
                conn.execute(
                    """
                    INSERT INTO content.publication_entries
                      (publication_version_id, canonical_case_id, generation_example_row_id, snapshot, snapshot_digest)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (version_id, canonical_case_id, generation_example_row_id, json.dumps(snapshot), _sha(f"{collection}:{field}")),
                )
            except psycopg.Error:
                pass
            else:
                raise ValidationFailure("link_only database guard allowed a mirrorable input or output storage reference")
            finally:
                conn.execute("DELETE FROM content.publication_versions WHERE publication_version_id=%s", (version_id,))


def _assert_concurrent_canonicalization(database_url: str) -> None:
    """Run production canonicalization concurrently against the same immutable rows."""

    workers = 4
    start = threading.Barrier(workers)

    def canonicalize_once() -> dict[str, int]:
        start.wait(timeout=30)
        return ContentDatabase(ContentDatabaseSettings(database_url)).canonicalize()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        outcomes = [future.result(timeout=90) for future in [executor.submit(canonicalize_once) for _ in range(workers)]]
    if sum(item["created_memberships"] for item in outcomes) != 4:
        raise ValidationFailure("concurrent canonicalization did not create exactly one membership for each representative Generation Example")


def run() -> dict[str, Any]:
    environment = _runtime_environment()
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0013 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="live-content-core-", dir=runtime_root))
    project = f"task0013{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_ok = False
    try:
        postgres_port = _free_loopback_port()
        values = {
            "INVENTORY_POSTGRES_DB": "contentcore",
            "INVENTORY_POSTGRES_USER": "u" + _token(12),
            "INVENTORY_POSTGRES_PASSWORD": _token(24),
            "INVENTORY_POSTGRES_PORT": str(postgres_port),
            "INVENTORY_S3_ACCESS_KEY": "a" + _token(12),
            "INVENTORY_S3_SECRET_KEY": _token(24),
            "INVENTORY_S3_PORT": str(_free_loopback_port()),
        }
        _write_env(env_file, values)
        database_url = f"postgresql://{quote(values['INVENTORY_POSTGRES_USER'])}:{quote(values['INVENTORY_POSTGRES_PASSWORD'])}@127.0.0.1:{postgres_port}/contentcore"
        compose_started = True
        _compose(["up", "-d", "postgres"], env_file=env_file, project=project, timeout=300)
        _wait_for_postgres(database_url)
        inventory_database = InventoryDatabase(DatabaseConfig(database_url))
        expected_migrations = _repository_migration_manifest(REPO_ROOT / "migrations")
        first_migration = inventory_database.apply_migrations(REPO_ROOT / "migrations")
        _assert_migration_results(
            first_migration,
            expected_migrations,
            phase="initial apply",
            allowed_statuses={"applied", "verified_existing"},
        )
        second_migration = inventory_database.apply_migrations(REPO_ROOT / "migrations")
        _assert_migration_results(
            second_migration,
            expected_migrations,
            phase="replay",
            allowed_statuses={"verified_existing"},
        )
        generation_rows = _seed_inventory(database_url)
        inventory_before = _inventory_counts(database_url)
        _assert_future_review_rejected(database_url, generation_example_row_id=generation_rows["exact-a"])
        cli_environment = dict(os.environ)
        cli_environment.update({"CONTENT_DATABASE_URL": database_url, "PYTHONDONTWRITEBYTECODE": "1"})
        _assert_concurrent_canonicalization(database_url)
        code, payload = _run_content(["canonicalize"], cli_environment)
        if code != 0 or payload.get("status") != "ok" or payload.get("result", {}).get("ready_generation_examples") != 4:
            raise ValidationFailure("Content Core canonicalize CLI failed")
        database = ContentDatabase(ContentDatabaseSettings(database_url))
        database.assert_migrated()
        counts = database.debug_counts()
        if counts["canonical_cases"] != 3 or counts["canonical_memberships"] != 4:
            raise ValidationFailure("exact canonicalization did not preserve duplicate and different-output memberships")
        exact_case = _content_query(
            database_url,
            "SELECT canonical_case_id FROM content.canonical_memberships WHERE generation_example_row_id=%s",
            (generation_rows["exact-a"],),
        )
        if len(exact_case) != 1:
            raise ValidationFailure("exact duplicate Canonical Case could not be resolved")
        _assert_link_only_storage_paths_rejected(
            database_url,
            canonical_case_id=int(exact_case[0]["canonical_case_id"]),
            generation_example_row_id=generation_rows["exact-a"],
        )
        exact_memberships = _content_query(
            database_url,
            "SELECT count(*) AS count FROM content.canonical_memberships WHERE canonical_case_id=(SELECT canonical_case_id FROM content.canonical_memberships WHERE generation_example_row_id=%s)",
            (generation_rows["exact-a"],),
        )
        if int(exact_memberships[0]["count"]) != 2:
            raise ValidationFailure("exact duplicate Canonical Case did not retain both memberships")
        code, default_build = _run_content(["build-publication"], cli_environment)
        if (
            code != 0
            or default_build.get("result", {}).get("included_count") != 0
            or default_build.get("result", {}).get("excluded_count") != 4
        ):
            raise ValidationFailure("default no-review publication was not an explicit zero-entry version")
        default_version = int(default_build["result"]["publication_version_id"])
        code, default_activation = _run_content(["activate-publication", "--version-id", str(default_version)], cli_environment)
        if code != 0 or default_activation.get("result", {}).get("state") != "active":
            raise ValidationFailure("zero-entry publication could not be atomically activated")
        review_specs = (
            ("exact-a", "mirror_allowed"),
            ("exact-b", "attribution_required"),
            ("different-output", "link_only"),
            ("blocked-output", "mirror_allowed"),
        )
        for offset, (case_key, policy) in enumerate(review_specs):
            code, review_payload = _run_content(
                [
                    "record-rights-review",
                    "--generation-example-row-id",
                    str(generation_rows[case_key]),
                    "--repository-license",
                    "CC-BY-4.0",
                    "--prompt-rights",
                    "approved",
                    "--asset-rights",
                    "approved",
                    "--author",
                    "Representative Author",
                    "--original-url",
                    f"https://seed.invalid/original/{case_key}",
                    "--evidence-url",
                    "https://seed.invalid/license",
                    "--reviewer",
                    "human-reviewer",
                    "--reviewed-at",
                    f"2026-01-01T00:00:0{offset}+00:00",
                    "--display-policy",
                    policy,
                ],
                cli_environment,
            )
            if code != 0 or review_payload.get("status") != "ok":
                raise ValidationFailure("explicit rights review CLI failed")
        blocked_case = _content_query(
            database_url,
            "SELECT canonical_case_id FROM content.canonical_memberships WHERE generation_example_row_id=%s",
            (generation_rows["blocked-output"],),
        )
        database.record_taxonomy_assignment(
            canonical_case_id=int(blocked_case[0]["canonical_case_id"]),
            taxonomy_version="content-taxonomy-v1",
            classifier_version="human-block-v1",
            tag_value="blocked-by-representative-policy",
            tag_source="blocked",
            confidence=1.0,
            evidence={"reviewer": "human-reviewer", "reason": "representative blocked tag"},
        )
        code, first_build = _run_content(["build-publication"], cli_environment)
        if (
            code != 0
            or first_build.get("result", {}).get("included_count") != 3
            or first_build.get("result", {}).get("excluded_count") != 1
            or first_build.get("result", {}).get("reason_counts", {}).get("blocked_taxonomy") != 1
        ):
            raise ValidationFailure("explicit-rights publication gate did not include/exclude the expected representative rows")
        first_version = int(first_build["result"]["publication_version_id"])
        code, activation = _run_content(["activate-publication", "--version-id", str(first_version)], cli_environment)
        if code != 0 or activation.get("result", {}).get("previous_publication_version_id") != default_version:
            raise ValidationFailure("publication activation did not atomically replace the prior active version")
        code, inspected = _run_content(["inspect-publication"], cli_environment)
        entries = inspected.get("result", {}).get("entries", [])
        if code != 0 or len(entries) != 3 or any(
            "object_key" in output or "object_bucket" in output
            for entry in entries
            if entry.get("rights", {}).get("display_policy") == "link_only"
            for output in entry.get("outputs", []) + entry.get("inputs", [])
        ):
            raise ValidationFailure("current snapshot leaked a mirrorable path for link_only content")
        if any(
            not {"ordinal", "role", "source_path", "source_url", "source_location"}.issubset(asset)
            for entry in entries
            for asset in entry.get("outputs", []) + entry.get("inputs", [])
        ):
            raise ValidationFailure("current snapshot omitted immutable asset role, ordinal, or source-location provenance")
        code, repeat_build = _run_content(["build-publication"], cli_environment)
        if code != 0 or repeat_build.get("result", {}).get("content_digest") != first_build.get("result", {}).get("content_digest"):
            raise ValidationFailure("repeated publication build did not produce the same content digest")
        repeat_version = int(repeat_build["result"]["publication_version_id"])
        code, _ = _run_content(["activate-publication", "--version-id", str(repeat_version)], cli_environment)
        if code != 0:
            raise ValidationFailure("repeat publication version could not be activated")
        pointer_before_failure = _content_query(database_url, "SELECT publication_version_id FROM content.publication_current")
        versions_before_failure = database.debug_counts()["publication_versions"]
        outbox_before_failure = database.debug_counts()["publication_outbox"]
        code, failed_build = _run_content(["build-publication", "--failure-point", "before_ready"], cli_environment)
        if code == 0 or failed_build.get("error_code") != "injected_publication_build_failure":
            raise ValidationFailure("publication build failure injection was not surfaced")
        if database.debug_counts()["publication_versions"] != versions_before_failure:
            raise ValidationFailure("failed publication build left a visible version")
        code, pending_build = _run_content(["build-publication"], cli_environment)
        pending_version = int(pending_build.get("result", {}).get("publication_version_id", 0))
        code, failed_activation = _run_content(
            ["activate-publication", "--version-id", str(pending_version), "--failure-point", "after_pointer_before_outbox"], cli_environment
        )
        if code == 0 or failed_activation.get("error_code") != "injected_publication_activation_failure":
            raise ValidationFailure("publication activation failure injection was not surfaced")
        pointer_after_failure = _content_query(database_url, "SELECT publication_version_id FROM content.publication_current")
        if pointer_after_failure != pointer_before_failure or database.debug_counts()["publication_outbox"] != outbox_before_failure:
            raise ValidationFailure("failed activation changed current pointer or outbox")
        code, rollback = _run_content(["rollback-publication", "--version-id", str(first_version)], cli_environment)
        if code != 0 or rollback.get("result", {}).get("event_type") != "publication_rolled_back":
            raise ValidationFailure("atomic rollback to completed history failed")
        _assert_immutable_guards(
            database_url, active_version_id=first_version, generation_example_row_id=generation_rows["exact-a"]
        )
        inventory_after = _inventory_counts(database_url)
        if inventory_after != inventory_before:
            raise ValidationFailure("Content Core mutated immutable inventory evidence")
        final_counts = database.debug_counts()
        if final_counts["publication_current"] != 1 or final_counts["publication_outbox"] != 4:
            raise ValidationFailure("publication pointer or outbox did not close after activate/failure/rollback")
        return {
            "status": "passed",
            "environment": environment,
            "docker": {"postgres_image": POSTGRES_IMAGE, "loopback_only": True, "services_started": ["postgres"]},
            "migrations": {"first": first_migration, "replay": second_migration},
            "seed": {"generation_examples": 4, "exact_duplicate_memberships": 2, "different_output_canonical_cases": 3},
            "default_zero_publication": {"version_id": default_version, "included_count": 0},
            "explicit_rights_publication": {"version_id": first_version, "included_count": 3, "content_digest": first_build["result"]["content_digest"]},
            "repeat_publication": {"version_id": repeat_version, "same_digest": True},
            "failure_retention": {"build_rolled_back": True, "activation_pointer_and_outbox_unchanged": True},
            "rollback": {"target_version_id": first_version, "succeeded": True},
            "immutable_guards": True,
            "future_review_rejected": True,
            "link_only_storage_paths_rejected": True,
            "concurrent_canonicalization": True,
            "asset_provenance_snapshot_complete": True,
            "final_content_counts": final_counts,
            "inventory_unchanged": True,
            "gates": {"GATE-001": "passed", "GATE-002": "passed"},
            "temporary_runtime_cleaned": True,
            "compose_cleanup": True,
        }
    finally:
        if compose_started:
            cleanup = _compose(["down", "-v", "--remove-orphans"], env_file=env_file, project=project, check=False, timeout=300)
            cleanup_ok = cleanup.returncode == 0
        if run_root.exists():
            shutil.rmtree(run_root)
        if run_root.exists():
            raise ValidationFailure("isolated Content Core runtime directory was not removed")
        if compose_started:
            _assert_no_orphans(project)
        if compose_started and not cleanup_ok:
            raise ValidationFailure("isolated PostgreSQL Compose cleanup did not complete")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the local PostgreSQL Content Core lifecycle.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run()
    except (ValidationFailure, ContentDatabaseError, psycopg.Error, OSError, subprocess.TimeoutExpired) as exc:
        payload = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
