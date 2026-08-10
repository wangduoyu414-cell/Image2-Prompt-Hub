"""Fresh local PostgreSQL, MinIO, and ASGI evidence for the public API slice."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import boto3
import httpx
import psycopg
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.main import create_app
from content.database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings, RightsReview
from inventory.database import DatabaseConfig, DatabaseError, InventoryDatabase


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0014")


class ValidationFailure(RuntimeError):
    """A fail-closed conclusion from this task-owned local integration harness."""


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
            raise ValidationFailure(f"{name} must use the fixed TASK-0014 external runtime path")
        observed[name] = str(actual)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValidationFailure("PYTHONDONTWRITEBYTECODE must equal 1")
    return observed


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _token(length: int = 20) -> str:
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


def _write_env(path: Path, values: Mapping[str, str]) -> None:
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


def _s3_client(*, endpoint_url: str, access_key: str, secret_key: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2, "mode": "standard"}, s3={"addressing_style": "path"}),
    )


def _wait_for_minio(client: Any) -> None:
    deadline = time.monotonic() + 150.0
    while time.monotonic() < deadline:
        try:
            client.list_buckets()
            return
        except BotoCoreError:
            time.sleep(1.0)
        except ClientError:
            time.sleep(1.0)
    raise ValidationFailure("isolated MinIO service did not become ready")


def _sha(value: bytes | str) -> str:
    content = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(content).hexdigest()


def _png(label: str) -> bytes:
    """Generate a valid small PNG above the inventory minimum object-size guard."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    digest = hashlib.sha256(label.encode("utf-8")).digest()
    pixels = b"\x00" + digest[:3]
    metadata = b"Description\x00" + label.encode("utf-8") + (b"-public-api-fixture" * 40)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", metadata)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _put_object(client: Any, *, bucket: str, content_sha256: str, content: bytes, media_type: str = "image/png") -> dict[str, Any]:
    key = f"sha256/{content_sha256[:2]}/{content_sha256}"
    client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=media_type)
    return {
        "content_sha256": content_sha256,
        "object_key": key,
        "object_bucket": bucket,
        "byte_size": len(content),
        "media_type": media_type,
        "integrity_state": "verified",
    }


def _verify_object(client: Any, *, bucket: str, fact: Mapping[str, Any], expected: bytes) -> None:
    response = client.get_object(Bucket=bucket, Key=str(fact["object_key"]))
    body = response["Body"]
    try:
        actual = body.read()
    finally:
        body.close()
    if (
        not isinstance(response.get("ContentLength"), int)
        or response["ContentLength"] != len(expected)
        or str(response.get("ContentType", "")).split(";", 1)[0] != str(fact["media_type"])
        or actual != expected
        or _sha(actual) != str(fact["content_sha256"])
    ):
        raise ValidationFailure("real MinIO object does not match its content-addressed fact")


def _seed_inventory(database_url: str, *, assets: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Seed five local synthetic examples without network source extraction."""

    specs = (
        ("old", "A superseded publication case.", "old-output", "old-author", True),
        ("exact-a", "Create a precise glass sculpture under soft studio light.", "shared-output", "Author A", True),
        ("exact-b", "Create a precise glass sculpture under soft studio light.", "shared-output", "Author B", True),
        ("different-output", "Create a precise glass sculpture at sunset.", "different-output", "Author C", True),
        ("link-only", "A link-only historic artwork.", "link-output", "Author D", False),
    )
    rows: dict[str, int] = {}
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.transaction():
            project = conn.execute(
                "INSERT INTO inventory.source_projects(source_id, repository_id) VALUES (%s, %s) RETURNING source_project_id",
                ("public-api-seed", "local/public-api-seed"),
            ).fetchone()
            if not project:
                raise ValidationFailure("synthetic source project could not be seeded")
            project_id = int(project["source_project_id"])
            revision = conn.execute(
                "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s, %s) RETURNING source_revision_id",
                (project_id, "e" * 40),
            ).fetchone()
            if not revision:
                raise ValidationFailure("synthetic source revision could not be seeded")
            revision_id = int(revision["source_revision_id"])
            run = conn.execute(
                """
                INSERT INTO inventory.source_adapter_runs
                  (source_revision_id, adapter_id, adapter_version, contract_version, package_idempotency_key,
                   manifest_stable_sha256, semantic_digest, coverage, metrics, manifest, registry_snapshot, state)
                VALUES (%s, 'public-api-seed', 'v1', 'public-api-seed/v1', 'public-api-seed:fixed',
                        %s, %s, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, %s::jsonb, 'ready')
                RETURNING source_adapter_run_id
                """,
                (revision_id, _sha("public-api-manifest"), _sha("public-api-semantic"), json.dumps({"repository": {"repository_id": "local/public-api-seed"}})),
            ).fetchone()
            if not run:
                raise ValidationFailure("synthetic adapter run could not be seeded")
            run_id = int(run["source_adapter_run_id"])
            for fact in assets.values():
                conn.execute(
                    """
                    INSERT INTO inventory.assets(content_sha256, object_key, object_bucket, byte_size, media_type, integrity_state)
                    VALUES (%s, %s, %s, %s, %s, 'verified')
                    """,
                    (
                        fact["content_sha256"],
                        fact["object_key"],
                        fact["object_bucket"],
                        fact["byte_size"],
                        fact["media_type"],
                    ),
                )
            shared_input_hash = str(assets["shared-input"]["content_sha256"])
            for index, (case_key, prompt_text, output_name, author, has_reference) in enumerate(specs):
                source_path = f"synthetic/{case_key}.json"
                source_url = f"https://synthetic.invalid/{case_key}.json"
                source_file = conn.execute(
                    "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s, %s, %s) RETURNING source_file_id",
                    (revision_id, source_path, source_url),
                ).fetchone()
                source_case = conn.execute(
                    "INSERT INTO inventory.source_cases(source_project_id, source_case_key) VALUES (%s, %s) RETURNING source_case_id",
                    (project_id, case_key),
                ).fetchone()
                if not source_file or not source_case:
                    raise ValidationFailure("synthetic case source rows could not be seeded")
                source_file_id = int(source_file["source_file_id"])
                case_version = conn.execute(
                    """
                    INSERT INTO inventory.source_case_versions
                      (source_case_id, source_revision_id, source_adapter_run_id, source_file_id, source_locator, adapter_record, generation_document, contract_state)
                    VALUES (%s, %s, %s, %s, %s::jsonb, '{}'::jsonb, '{}'::jsonb, 'contract_valid')
                    RETURNING source_case_version_id
                    """,
                    (
                        int(source_case["source_case_id"]),
                        revision_id,
                        run_id,
                        source_file_id,
                        json.dumps({"source_path": source_path, "source_url": source_url}),
                    ),
                ).fetchone()
                if not case_version:
                    raise ValidationFailure("synthetic case version could not be seeded")
                case_version_id = int(case_version["source_case_version_id"])
                prompt = conn.execute(
                    """
                    INSERT INTO inventory.prompt_records
                      (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                    VALUES (%s, 'original', %s, 'en', %s, %s::jsonb, %s)
                    RETURNING prompt_record_id
                    """,
                    (
                        case_version_id,
                        prompt_text,
                        source_file_id,
                        json.dumps({"source_path": source_path, "source_url": source_url}),
                        _sha(prompt_text),
                    ),
                ).fetchone()
                if not prompt:
                    raise ValidationFailure("synthetic prompt could not be seeded")
                prompt_id = int(prompt["prompt_record_id"])
                if has_reference:
                    input_source = conn.execute(
                        """
                        INSERT INTO inventory.asset_sources
                          (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                        VALUES (%s, %s, %s, %s, 'input_reference', %s::jsonb)
                        RETURNING asset_source_id
                        """,
                        (
                            case_version_id,
                            f"input-{index}",
                            source_file_id,
                            shared_input_hash,
                            json.dumps({"source_path": source_path, "source_url": source_url}),
                        ),
                    ).fetchone()
                else:
                    input_source = None
                output_hash = str(assets[output_name]["content_sha256"])
                output_source = conn.execute(
                    """
                    INSERT INTO inventory.asset_sources
                      (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                    VALUES (%s, %s, %s, %s, 'output_primary', %s::jsonb)
                    RETURNING asset_source_id
                    """,
                    (
                        case_version_id,
                        f"output-{index}",
                        source_file_id,
                        output_hash,
                        json.dumps({"source_path": source_path, "source_url": source_url}),
                    ),
                ).fetchone()
                if not output_source:
                    raise ValidationFailure("synthetic output source could not be seeded")
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
                        json.dumps(
                            {
                                "evidence_status": "source_claimed",
                                "model_raw": "gpt-image-2",
                                "parameters_raw": {"size": "1024x1024"},
                            }
                        ),
                    ),
                ).fetchone()
                if not generation:
                    raise ValidationFailure("synthetic generation could not be seeded")
                generation_id = int(generation["generation_example_row_id"])
                if input_source:
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
                    (generation_id, json.dumps(["synthetic local API validation case"])),
                )
                conn.execute(
                    """
                    INSERT INTO inventory.rights_records(source_case_version_id, prompt_rights_status, asset_rights_status, evidence_urls, note)
                    VALUES (%s, 'unknown', 'unknown', '[]'::jsonb, 'inventory evidence stays unknown')
                    """,
                    (case_version_id,),
                )
                rows[case_key] = generation_id
    return rows


def _canonical_keys(database_url: str, generation_rows: Mapping[str, int]) -> dict[str, str]:
    values: dict[str, str] = {}
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        for name, row_id in generation_rows.items():
            row = conn.execute(
                """
                SELECT c.canonical_key
                FROM content.canonical_memberships AS membership
                JOIN content.canonical_cases AS c ON c.canonical_case_id=membership.canonical_case_id
                WHERE membership.generation_example_row_id=%s
                """,
                (row_id,),
            ).fetchone()
            if not row:
                raise ValidationFailure("canonical case could not be resolved for a synthetic member")
            values[name] = str(row["canonical_key"])
    return values


def _canonical_id(database_url: str, generation_row_id: int) -> int:
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        row = conn.execute(
            "SELECT canonical_case_id FROM content.canonical_memberships WHERE generation_example_row_id=%s",
            (generation_row_id,),
        ).fetchone()
    if not row:
        raise ValidationFailure("synthetic canonical membership could not be resolved")
    return int(row["canonical_case_id"])


def _review(database: ContentDatabase, *, generation_row_id: int, policy: str, author: str, offset: int) -> None:
    database.record_rights_review(
        RightsReview(
            generation_example_row_id=generation_row_id,
            repository_license="CC-BY-4.0",
            prompt_rights="approved",
            asset_rights="approved",
            author=author,
            original_url=f"https://synthetic.invalid/original/{generation_row_id}",
            evidence_url="https://synthetic.invalid/license",
            reviewer="synthetic-human-reviewer",
            reviewed_at=datetime.now(timezone.utc) - timedelta(minutes=10 - offset),
            display_policy=policy,
            review_note="Synthetic local Compose validation only.",
        )
    )


async def _request(app: Any, method: str, url: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://public-api.local") as client:
        return await client.request(method, url)


def _assert_json(response: httpx.Response, *, expected_status: int) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise ValidationFailure("ASGI HTTP response status did not meet the public API contract")
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ValidationFailure("ASGI HTTP response was not JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationFailure("ASGI HTTP JSON response was not an object")
    return payload


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


def _set_public_environment(values: Mapping[str, str]) -> dict[str, str | None]:
    names = (
        "PUBLIC_API_DATABASE_URL",
        "PUBLIC_API_S3_ENDPOINT_URL",
        "PUBLIC_API_S3_ACCESS_KEY_ID",
        "PUBLIC_API_S3_SECRET_ACCESS_KEY",
        "PUBLIC_API_S3_REGION",
    )
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update(values)
    return previous


def _restore_public_environment(previous: Mapping[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def run() -> dict[str, Any]:
    environment = _runtime_environment()
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0014 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="live-public-api-", dir=runtime_root))
    project = f"task0014{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    public_environment: dict[str, str | None] | None = None
    cleanup_ok = False
    try:
        postgres_port = _free_loopback_port()
        s3_port = _free_loopback_port()
        values = {
            "INVENTORY_POSTGRES_DB": "publicapi",
            "INVENTORY_POSTGRES_USER": "u" + _token(12),
            "INVENTORY_POSTGRES_PASSWORD": _token(24),
            "INVENTORY_POSTGRES_PORT": str(postgres_port),
            "INVENTORY_S3_ACCESS_KEY": "a" + _token(12),
            "INVENTORY_S3_SECRET_KEY": _token(24),
            "INVENTORY_S3_PORT": str(s3_port),
        }
        _write_env(env_file, values)
        database_url = (
            f"postgresql://{quote(values['INVENTORY_POSTGRES_USER'])}:{quote(values['INVENTORY_POSTGRES_PASSWORD'])}"
            f"@127.0.0.1:{postgres_port}/{values['INVENTORY_POSTGRES_DB']}"
        )
        endpoint_url = f"http://127.0.0.1:{s3_port}"
        compose_started = True
        _compose(["up", "-d", "postgres", "minio"], env_file=env_file, project=project, timeout=360)
        _wait_for_postgres(database_url)
        client = _s3_client(
            endpoint_url=endpoint_url,
            access_key=values["INVENTORY_S3_ACCESS_KEY"],
            secret_key=values["INVENTORY_S3_SECRET_KEY"],
        )
        _wait_for_minio(client)
        bucket = f"publicapi{uuid.uuid4().hex[:18]}"
        client.create_bucket(Bucket=bucket)
        asset_bytes = {
            "shared-input": _png("shared-input"),
            "shared-output": _png("shared-output"),
            "different-output": _png("different-output"),
            "link-output": _png("link-output"),
            "old-output": _png("old-output"),
        }
        assets = {
            name: _put_object(client, bucket=bucket, content_sha256=_sha(content), content=content)
            for name, content in asset_bytes.items()
        }
        for name, fact in assets.items():
            _verify_object(client, bucket=bucket, fact=fact, expected=asset_bytes[name])

        inventory = InventoryDatabase(DatabaseConfig(database_url))
        expected_migrations = _repository_migration_manifest(REPO_ROOT / "migrations")
        migration_first = inventory.apply_migrations(REPO_ROOT / "migrations")
        _assert_migration_results(
            migration_first,
            expected_migrations,
            phase="initial apply",
            allowed_statuses={"applied", "verified_existing"},
        )
        migration_replay = inventory.apply_migrations(REPO_ROOT / "migrations")
        _assert_migration_results(
            migration_replay,
            expected_migrations,
            phase="replay",
            allowed_statuses={"verified_existing"},
        )
        generation_rows = _seed_inventory(database_url, assets=assets)
        database = ContentDatabase(ContentDatabaseSettings(database_url))
        database.assert_migrated()
        canonical = database.canonicalize()
        if canonical["ready_generation_examples"] != 5 or canonical["created_memberships"] != 5:
            raise ValidationFailure("synthetic inventory did not canonically close all five examples")
        keys = _canonical_keys(database_url, generation_rows)
        if keys["exact-a"] != keys["exact-b"] or len(set(keys.values())) != 4:
            raise ValidationFailure("exact duplicate and different-output canonical boundaries are incorrect")
        for case_name, tag in (("old", "old"), ("exact-a", "studio"), ("different-output", "sunset"), ("link-only", "history")):
            database.record_taxonomy_assignment(
                canonical_case_id=_canonical_id(database_url, generation_rows[case_name]),
                taxonomy_version="public-api-taxonomy/v1",
                classifier_version="synthetic-human/v1",
                tag_value=tag,
                tag_source="editor",
                confidence=1.0,
                evidence={"source": "synthetic local validator"},
            )

        public_environment = _set_public_environment(
            {
                "PUBLIC_API_DATABASE_URL": database_url,
                "PUBLIC_API_S3_ENDPOINT_URL": endpoint_url,
                "PUBLIC_API_S3_ACCESS_KEY_ID": values["INVENTORY_S3_ACCESS_KEY"],
                "PUBLIC_API_S3_SECRET_ACCESS_KEY": values["INVENTORY_S3_SECRET_KEY"],
                "PUBLIC_API_S3_REGION": "us-east-1",
            }
        )
        app = create_app()
        health = asyncio.run(_request(app, "GET", "/healthz"))
        if health.status_code != 200:
            raise ValidationFailure("health endpoint did not remain process-only")
        no_current = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/publication")), expected_status=200)
        no_current_cases = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/cases")), expected_status=200)
        ready_empty = _assert_json(asyncio.run(_request(app, "GET", "/readyz")), expected_status=200)
        if (
            no_current != {"state": "no_current", "publication": None, "case_count": 0}
            or no_current_cases["total"] != 0
            or no_current_cases["cases"] != []
            or ready_empty.get("state") != "no_current"
        ):
            raise ValidationFailure("empty current publication did not remain a stable public directory")

        _review(database, generation_row_id=generation_rows["old"], policy="mirror_allowed", author="Old Author", offset=0)
        old_version = database.build_publication()
        database.activate_publication(int(old_version["publication_version_id"]))
        old_visible = _assert_json(asyncio.run(_request(app, "GET", f"/api/v1/cases/{keys['old']}")), expected_status=200)
        if old_visible.get("member_count") != 1:
            raise ValidationFailure("first active immutable version was not visible through the API")

        for offset, (case_name, policy, author) in enumerate(
            (
                ("old", "blocked", "Old Author"),
                ("exact-a", "mirror_allowed", "Author A"),
                ("exact-b", "attribution_required", "Author B"),
                ("different-output", "mirror_allowed", "Author C"),
                ("link-only", "link_only", "Author D"),
            ),
            start=1,
        ):
            _review(database, generation_row_id=generation_rows[case_name], policy=policy, author=author, offset=offset)
        loss_candidate = database.build_publication()
        if loss_candidate["included_count"] != 4:
            raise ValidationFailure("public-loss candidate did not include the expected reviewed members")
        try:
            database.activate_publication(int(loss_candidate["publication_version_id"]))
        except ContentDatabaseError as exc:
            if exc.error_code != "publication_public_loss":
                raise ValidationFailure("public-loss guard returned the wrong failure") from exc
        else:
            raise ValidationFailure("public-loss candidate replaced the current publication")
        retained_old = _assert_json(asyncio.run(_request(app, "GET", f"/api/v1/cases/{keys['old']}")), expected_status=200)
        if retained_old.get("member_count") != 1:
            raise ValidationFailure("public-loss guard did not retain the previous current case")

        _review(database, generation_row_id=generation_rows["old"], policy="mirror_allowed", author="Old Author", offset=6)
        current_version = database.build_publication()
        if current_version["included_count"] != 5:
            raise ValidationFailure("replacement immutable publication did not preserve all public members")
        database.activate_publication(int(current_version["publication_version_id"]))

        publication = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/publication")), expected_status=200)
        cases = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/cases?page=1&page_size=2")), expected_status=200)
        detail = _assert_json(asyncio.run(_request(app, "GET", f"/api/v1/cases/{keys['exact-a']}")), expected_status=200)
        search = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/cases?q=author%20b")), expected_status=200)
        tagged = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/cases?tag=sunset&has_reference=true")), expected_status=200)
        link_filtered = _assert_json(asyncio.run(_request(app, "GET", "/api/v1/cases?display_policy=link_only")), expected_status=200)
        if (
            publication.get("state") != "active"
            or publication.get("case_count") != 4
            or cases.get("total") != 4
            or len(cases.get("cases", [])) != 2
            or detail.get("member_count") != 2
            or [member["source"]["source_id"] for member in detail.get("members", [])] != ["public-api-seed", "public-api-seed"]
            or search.get("total") != 1
            or tagged.get("total") != 1
            or link_filtered.get("total") != 1
        ):
            raise ValidationFailure("current Canonical Case grouping, query, filter, or detail contract failed")
        facets = cases.get("facets", {})
        tag_counts = {entry["value"]: entry["count"] for entry in facets.get("tags", [])}
        reference_counts = {entry["value"]: entry["count"] for entry in facets.get("has_reference", [])}
        if (
            tag_counts.get("history") != 1
            or tag_counts.get("studio") != 1
            or tag_counts.get("sunset") != 1
            or tag_counts.get("exact_generation_facts") != 4
            or reference_counts != {False: 1, True: 3}
        ):
            raise ValidationFailure("facets counted duplicate memberships instead of Canonical Cases")
        public_serialized = json.dumps({"publication": publication, "cases": cases, "detail": detail}, sort_keys=True)
        forbidden = (
            "object_bucket",
            "object_key",
            "generation_example_row_id",
            "prompt_record_id",
            values["INVENTORY_POSTGRES_PASSWORD"],
            values["INVENTORY_S3_SECRET_KEY"],
            database_url,
            bucket,
        )
        if any(item in public_serialized for item in forbidden):
            raise ValidationFailure("public JSON exposed a protected locator, internal row, or secret")

        shared_hash = str(assets["shared-output"]["content_sha256"])
        delivered = asyncio.run(_request(app, "GET", f"/api/v1/assets/{shared_hash}"))
        if (
            delivered.status_code != 200
            or delivered.content != asset_bytes["shared-output"]
            or delivered.headers.get("content-type") != "image/png"
            or delivered.headers.get("etag") != f'"{shared_hash}"'
            or delivered.headers.get("content-length") != str(len(asset_bytes["shared-output"]))
            or delivered.headers.get("cache-control") != "public, max-age=31536000, immutable"
        ):
            raise ValidationFailure("authorized current MinIO image delivery did not verify bytes and cache headers")

        client.delete_object(Bucket=bucket, Key=str(assets["link-output"]["object_key"]))
        for content_sha256 in (
            str(assets["link-output"]["content_sha256"]),
            "f" * 64,
        ):
            denied = asyncio.run(_request(app, "GET", f"/api/v1/assets/{content_sha256}"))
            if denied.status_code != 404 or denied.json().get("error", {}).get("code") != "asset_not_found":
                raise ValidationFailure("link-only or unknown asset reached private storage")

        corrupt = bytes([asset_bytes["shared-output"][0] ^ 1]) + asset_bytes["shared-output"][1:]
        client.put_object(
            Bucket=bucket,
            Key=str(assets["shared-output"]["object_key"]),
            Body=corrupt,
            ContentType="image/png",
        )
        hash_failure = asyncio.run(_request(app, "GET", f"/api/v1/assets/{shared_hash}"))
        if hash_failure.status_code != 502 or hash_failure.json().get("error", {}).get("code") != "asset_integrity_failed":
            raise ValidationFailure("wrong current object hash did not fail closed")
        client.put_object(
            Bucket=bucket,
            Key=str(assets["shared-output"]["object_key"]),
            Body=asset_bytes["shared-output"][:-1],
            ContentType="image/png",
        )
        length_failure = asyncio.run(_request(app, "GET", f"/api/v1/assets/{shared_hash}"))
        if length_failure.status_code != 502 or length_failure.json().get("error", {}).get("code") != "asset_integrity_failed":
            raise ValidationFailure("wrong current object length did not fail closed")
        different_hash = str(assets["different-output"]["content_sha256"])
        client.put_object(
            Bucket=bucket,
            Key=str(assets["different-output"]["object_key"]),
            Body=asset_bytes["different-output"],
            ContentType="text/html",
        )
        media_failure = asyncio.run(_request(app, "GET", f"/api/v1/assets/{different_hash}"))
        if media_failure.status_code != 502 or media_failure.json().get("error", {}).get("code") != "asset_integrity_failed":
            raise ValidationFailure("wrong current object media type did not fail closed")

        invalid = asyncio.run(_request(app, "GET", "/api/v1/cases?page=0"))
        if invalid.status_code != 422 or invalid.json().get("error", {}).get("code") != "invalid_request":
            raise ValidationFailure("invalid request did not produce the stable 422 error envelope")
        openapi = _assert_json(asyncio.run(_request(app, "GET", "/openapi.json")), expected_status=200)
        if any(not set(item).issubset({"get", "head"}) for item in openapi.get("paths", {}).values()):
            raise ValidationFailure("OpenAPI exposed a non-read-only public operation")

        return {
            "status": "passed",
            "environment": environment,
            "compose": {"loopback_only": True, "services": ["postgres", "minio"]},
            "migrations": {"first": migration_first, "replay": migration_replay},
            "synthetic_seed": {
                "generation_examples": 5,
                "current_entries": 5,
                "current_canonical_cases": 4,
                "exact_duplicate_memberships": 2,
                "real_minio_objects_hash_verified": len(assets),
            },
            "http": {
                "empty_directory": True,
                "current_pointer_switch": True,
                "canonical_dedupe_and_member_detail": True,
                "search_filter_facets": True,
                "authorized_image_headers_and_bytes": True,
                "public_loss_guard": True,
                "link_only_unknown_no_storage_read": True,
                "hash_and_media_integrity_fail_closed": True,
                "openapi_read_only": True,
            },
            "cleanup": {"runtime": True, "compose": True},
            "gates": {"GATE-001": "passed", "GATE-002": "passed"},
        }
    finally:
        if public_environment is not None:
            _restore_public_environment(public_environment)
        if compose_started:
            cleanup = _compose(["down", "-v", "--remove-orphans"], env_file=env_file, project=project, check=False, timeout=300)
            cleanup_ok = cleanup.returncode == 0
        if run_root.exists():
            shutil.rmtree(run_root)
        if run_root.exists():
            raise ValidationFailure("temporary API runtime directory was not removed")
        if compose_started:
            _assert_no_orphans(project)
        if compose_started and not cleanup_ok:
            raise ValidationFailure("isolated PostgreSQL and MinIO Compose cleanup did not complete")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the local public API PostgreSQL and MinIO integration.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run()
    except Exception as exc:
        payload = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": "public API validator failed without emitting private runtime details",
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "failed")
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
