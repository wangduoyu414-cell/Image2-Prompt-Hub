"""Live, isolated PostgreSQL/S3/Git evidence for TASK-0005.

The legacy MinIO container is deliberately confined to a random loopback port,
random credentials, and a unique Compose project. It is a test fixture only;
the inventory application itself uses only the standard boto3 S3 API.
"""

from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from urllib.parse import quote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import boto3
import psycopg
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ingestion.pipeline import extract
from ingestion.pipeline import ExtractionError
from inventory.package import PackageValidationError
from inventory.database import advisory_key
from inventory.object_store import ObjectFact, ObjectStoreConfig, ObjectStoreError, S3ObjectStore, _policy_allows_public_access, object_key_for
from inventory.package import build_import_plan


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0005")
POSTGRES_IMAGE = "postgres:18.4@sha256:3a82e1f56c8f0f5616a11103ac3d47e632c3938698946a7ad26da0df1334744a"
MINIO_IMAGE = "minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
FAILURE_POINTS = ("after_lock", "after_first_object", "after_all_objects", "mid_database", "before_commit")
PUBLIC_GRANTEE_URIS = {
    "http://acs.amazonaws.com/groups/global/AllUsers",
    "http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
}


class ValidationFailure(RuntimeError):
    pass


def _s3_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


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
            raise ValidationFailure(f"{name} must use the fixed TASK-0005 external runtime path")
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


def _run_inventory(argv: list[str], environment: dict[str, str], *, timeout: int = 900) -> tuple[int, dict[str, Any]]:
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


def _database_counts(database_url: str) -> dict[str, int]:
    tables = (
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
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        return {
            table: int(conn.execute(f"SELECT count(*) AS count FROM inventory.{table}").fetchone()["count"])
            for table in tables
        }


def _expect_empty_database(database_url: str) -> None:
    counts = _database_counts(database_url)
    if any(counts.values()):
        raise ValidationFailure("failure injection left visible inventory rows")


def _wait_for_advisory_lock(database_url: str, idempotency_key: str) -> None:
    key = advisory_key(idempotency_key)
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        with psycopg.connect(database_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
            if row and row["acquired"] is False:
                return
            if row and row["acquired"]:
                conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
        time.sleep(0.1)
    raise ValidationFailure("concurrency holder did not acquire the package advisory lock")


def _s3_client(endpoint: str, access_key: str, secret_key: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def _assert_private_acl(response: Any, *, label: str) -> None:
    if _acl_is_public(response):
        raise ValidationFailure(f"isolated S3 {label} has a public ACL")


def _acl_is_public(response: Any) -> bool:
    grants = response.get("Grants", []) if isinstance(response, dict) else []
    for grant in grants:
        grantee = grant.get("Grantee", {}) if isinstance(grant, dict) else {}
        if isinstance(grantee, dict) and grantee.get("URI") in PUBLIC_GRANTEE_URIS:
            return True
    return False


def _assert_private_bucket(client: Any, bucket: str) -> None:
    _assert_private_acl(client.get_bucket_acl(Bucket=bucket), label="bucket")
    try:
        raw_policy = client.get_bucket_policy(Bucket=bucket)
    except ClientError as exc:
        if _s3_error_code(exc) not in {"404", "NoSuchBucketPolicy", "NoSuchBucketPolicyException", "NoSuchKey", "NotFound"}:
            raise ValidationFailure("isolated S3 bucket policy could not be verified") from exc
    except (BotoCoreError, AttributeError) as exc:
        raise ValidationFailure("isolated S3 bucket policy could not be verified") from exc
    else:
        policy_text = raw_policy.get("Policy") if isinstance(raw_policy, dict) else None
        if not isinstance(policy_text, str):
            raise ValidationFailure("isolated S3 bucket policy is public or unverifiable")
        try:
            if _policy_allows_public_access(json.loads(policy_text)):
                raise ValidationFailure("isolated S3 bucket policy is public or unverifiable")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValidationFailure("isolated S3 bucket policy is public or unverifiable") from exc
    try:
        status = client.get_bucket_policy_status(Bucket=bucket)
    except ClientError as exc:
        return
    except (BotoCoreError, AttributeError):
        return
    policy = status.get("PolicyStatus") if isinstance(status, dict) else None
    if isinstance(policy, dict) and policy.get("IsPublic") is True:
        raise ValidationFailure("isolated S3 bucket policy is public or unverifiable")


def _assert_private_object_acl(client: Any, bucket: str, key: str) -> None:
    _assert_private_acl(client.get_object_acl(Bucket=bucket, Key=key), label="object")


def _verify_networked_public_object_acl_probe(run_root: Path) -> dict[str, Any]:
    """Exercise the production existing-object ACL path over loopback HTTP.

    The fixed legacy MinIO image implements ACL reads but rejects ACL mutation.
    This deliberately minimal protocol probe supplies only the S3 calls the
    production client makes before it rejects an existing public object ACL.
    It is a real boto3 HTTP exchange, not a client fake or a MinIO capability
    claim, and is always shut down with the validator runtime.
    """

    bucket = "inventory-private-acl-probe"
    payload = b"task0005-networked-acl-probe" * 32
    digest = hashlib.sha256(payload).hexdigest()
    key = object_key_for(digest)
    source_path = run_root / "networked-acl-probe.bin"
    source_path.write_bytes(payload)
    routes: list[str] = []
    private_acl = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<AccessControlPolicy xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">
  <Owner><ID>probe-owner</ID><DisplayName>probe-owner</DisplayName></Owner>
  <AccessControlList>
    <Grant><Grantee xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:type=\"CanonicalUser\"><ID>probe-owner</ID></Grantee><Permission>FULL_CONTROL</Permission></Grant>
  </AccessControlList>
</AccessControlPolicy>"""
    public_acl = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<AccessControlPolicy xmlns=\"http://s3.amazonaws.com/doc/2006-03-01/\">
  <Owner><ID>probe-owner</ID><DisplayName>probe-owner</DisplayName></Owner>
  <AccessControlList>
    <Grant><Grantee xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:type=\"CanonicalUser\"><ID>probe-owner</ID></Grantee><Permission>FULL_CONTROL</Permission></Grant>
    <Grant><Grantee xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:type=\"Group\"><URI>http://acs.amazonaws.com/groups/global/AllUsers</URI></Grantee><Permission>READ</Permission></Grant>
  </AccessControlList>
</AccessControlPolicy>"""

    class ProbeHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _write(self, status: int, *, payload: bytes = b"", headers: dict[str, str] | None = None) -> None:
            response_headers = dict(headers or {})
            content_length = response_headers.pop("Content-Length", str(len(payload)))
            self.send_response(status)
            for name, value in response_headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", content_length)
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD" and payload:
                self.wfile.write(payload)

        def _error(self, code: str) -> None:
            body = (
                '<?xml version="1.0" encoding="UTF-8"?><Error>'
                f"<Code>{code}</Code><Message>{code}</Message>"
                "<RequestId>probe</RequestId><HostId>probe</HostId></Error>"
            ).encode("utf-8")
            self._write(404, payload=body, headers={"Content-Type": "application/xml"})

        def do_HEAD(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path == f"/{bucket}":
                routes.append("head_bucket")
                self._write(200)
                return
            if parsed.path == f"/{bucket}/{key}":
                routes.append("head_object")
                self._write(
                    200,
                    headers={
                        "Content-Length": str(len(payload)),
                        "Content-Type": "image/png",
                        "x-amz-meta-sha256": digest,
                    },
                )
                return
            self._error("NoSuchKey")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            query_tokens = set(filter(None, parsed.query.split("&")))
            if parsed.path == f"/{bucket}" and "policy" in query_tokens:
                routes.append("get_bucket_policy")
                self._error("NoSuchBucketPolicy")
                return
            if parsed.path == f"/{bucket}" and "policyStatus" in query_tokens:
                routes.append("get_bucket_policy_status")
                self._error("NoSuchBucketPolicy")
                return
            if parsed.path == f"/{bucket}" and "acl" in query_tokens:
                routes.append("get_bucket_acl")
                self._write(200, payload=private_acl, headers={"Content-Type": "application/xml"})
                return
            if parsed.path == f"/{bucket}/{key}" and "acl" in query_tokens:
                routes.append("get_object_acl")
                self._write(200, payload=public_acl, headers={"Content-Type": "application/xml"})
                return
            self._error("NoSuchKey")

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="task0005-s3-acl-probe", daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        try:
            S3ObjectStore(ObjectStoreConfig(endpoint, bucket, "probe-access", "probe-secret")).ensure_object(
                source_path=source_path,
                content_sha256=digest,
                byte_size=len(payload),
                media_type="image/png",
            )
        except ObjectStoreError as exc:
            if exc.error_code != "object_acl_public":
                raise ValidationFailure("networked S3 ACL probe returned the wrong production error") from exc
        else:
            raise ValidationFailure("networked S3 ACL probe did not reject a public existing object ACL")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    if thread.is_alive():
        raise ValidationFailure("networked S3 ACL probe did not shut down")
    required_routes = {"head_bucket", "get_bucket_policy", "get_bucket_acl", "head_object", "get_object_acl"}
    observed_routes = set(routes)
    if not required_routes.issubset(observed_routes):
        raise ValidationFailure("networked S3 ACL probe did not observe every required production protocol call")
    return {
        "status": "object_acl_public",
        "loopback_only": True,
        "routes": sorted(observed_routes),
    }


def _expect_database_rejection(conn: psycopg.Connection[Any], statement: str, params: tuple[Any, ...], label: str) -> None:
    conn.execute("SAVEPOINT expected_domain_rejection")
    try:
        conn.execute(statement, params)
    except psycopg.Error:
        conn.execute("ROLLBACK TO SAVEPOINT expected_domain_rejection")
        conn.execute("RELEASE SAVEPOINT expected_domain_rejection")
        return
    conn.execute("RELEASE SAVEPOINT expected_domain_rejection")
    raise ValidationFailure(f"database accepted prohibited cross-domain relation: {label}")


def _verify_database_domains(database_url: str, plan: Any) -> dict[str, Any]:
    """Exercise database-enforced boundary checks without persisting test rows."""

    with psycopg.connect(database_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
        primary = conn.execute(
            """
            SELECT p.source_project_id, p.source_id, p.repository_id,
                   r.source_revision_id, run.source_adapter_run_id, run.registry_snapshot
            FROM inventory.source_adapter_runs AS run
            JOIN inventory.source_revisions AS r ON r.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS p ON p.source_project_id = r.source_project_id
            WHERE run.package_idempotency_key = %s
            """,
            (plan.idempotency_key,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT v.source_case_version_id, v.source_case_id, v.source_revision_id,
                   v.source_adapter_run_id, v.source_file_id,
                   p.prompt_record_id, p.prompt_id, p.raw_text, p.language,
                   p.source_location AS prompt_location, p.raw_text_sha256,
                   a.asset_source_id, a.asset_ref_id, a.content_sha256, a.role,
                   a.source_location AS asset_location,
                   g.generation_example_row_id, g.generation_example_id
            FROM inventory.source_case_versions AS v
            JOIN inventory.prompt_records AS p ON p.source_case_version_id = v.source_case_version_id
            JOIN inventory.asset_sources AS a ON a.source_case_version_id = v.source_case_version_id
            JOIN inventory.generation_examples AS g ON g.source_case_version_id = v.source_case_version_id
            WHERE v.source_adapter_run_id = %s
            ORDER BY v.source_case_version_id
            LIMIT 2
            """,
            (primary["source_adapter_run_id"],),
        ).fetchall()
        if not primary or len(rows) != 2 or not isinstance(primary["registry_snapshot"], dict):
            raise ValidationFailure("primary inventory lacks domain-test identities or registry snapshot")

        primary_snapshot = primary["registry_snapshot"]
        future_snapshot = json.loads(json.dumps(primary_snapshot, ensure_ascii=False))
        future_revision_sha = "f" * 40
        future_repository = future_snapshot.setdefault("repository", {})
        future_repository["verified_commit_sha"] = future_revision_sha
        future_repository["url"] = "https://github.com/g0dam/Awesome-GPT-Image-2-Work-Prompts-future"
        future_snapshot["status"] = "historical-test"
        future_snapshot["rights"] = {"evidence": "changed-for-transactional-domain-test"}

        conn.execute("BEGIN")
        try:
            foreign_project = conn.execute(
                "INSERT INTO inventory.source_projects(source_id, repository_id) VALUES (%s, %s) RETURNING source_project_id",
                ("task0005-foreign-project", "task0005/foreign-project"),
            ).fetchone()
            foreign_revision = conn.execute(
                "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s, %s) RETURNING source_revision_id",
                (foreign_project["source_project_id"], "e" * 40),
            ).fetchone()
            foreign_file = conn.execute(
                "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s, %s, %s) RETURNING source_file_id",
                (foreign_revision["source_revision_id"], "future.json", "https://example.invalid/future.json"),
            ).fetchone()
            foreign_run = conn.execute(
                """
                INSERT INTO inventory.source_adapter_runs
                  (source_revision_id, adapter_id, adapter_version, contract_version,
                   package_idempotency_key, manifest_stable_sha256, semantic_digest,
                   coverage, metrics, manifest, registry_snapshot, state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, 'ready')
                RETURNING source_adapter_run_id
                """,
                (
                    foreign_revision["source_revision_id"],
                    "task0005-test",
                    "1.0.0",
                    "v1",
                    "task0005:foreign:run",
                    "a" * 64,
                    "b" * 64,
                    "{}",
                    "{}",
                    "{}",
                    json.dumps({"source_id": "task0005-foreign-project"}, ensure_ascii=False),
                ),
            ).fetchone()

            future_revision = conn.execute(
                "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s, %s) RETURNING source_revision_id",
                (primary["source_project_id"], future_revision_sha),
            ).fetchone()
            future_file = conn.execute(
                "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s, %s, %s) RETURNING source_file_id",
                (future_revision["source_revision_id"], "future.json", "https://example.invalid/primary-future.json"),
            ).fetchone()
            future_run = conn.execute(
                """
                INSERT INTO inventory.source_adapter_runs
                  (source_revision_id, adapter_id, adapter_version, contract_version,
                   package_idempotency_key, manifest_stable_sha256, semantic_digest,
                   coverage, metrics, manifest, registry_snapshot, state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, 'ready')
                RETURNING source_adapter_run_id, registry_snapshot
                """,
                (
                    future_revision["source_revision_id"],
                    "task0005-test",
                    "1.0.0",
                    "v1",
                    "task0005:future:run",
                    "c" * 64,
                    "d" * 64,
                    "{}",
                    "{}",
                    "{}",
                    json.dumps(future_snapshot, ensure_ascii=False),
                ),
            ).fetchone()
            unchanged_snapshot = conn.execute(
                "SELECT registry_snapshot FROM inventory.source_adapter_runs WHERE source_adapter_run_id = %s",
                (primary["source_adapter_run_id"],),
            ).fetchone()
            same_project_count = conn.execute(
                "SELECT count(*) AS count FROM inventory.source_projects WHERE source_id = %s AND repository_id = %s",
                (primary["source_id"], primary["repository_id"]),
            ).fetchone()
            if (
                future_run["registry_snapshot"] != future_snapshot
                or unchanged_snapshot["registry_snapshot"] != primary_snapshot
                or int(same_project_count["count"]) != 1
            ):
                raise ValidationFailure("future revision did not preserve stable project identity and independent registry snapshots")

            first, second = rows
            case_version_values = ("{}", "{}", "{}")
            future_case_version = conn.execute(
                """
                INSERT INTO inventory.source_case_versions
                  (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                   source_locator, adapter_record, generation_document, contract_state)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'contract_valid')
                RETURNING source_case_version_id
                """,
                (
                    first["source_case_id"],
                    future_revision["source_revision_id"],
                    future_run["source_adapter_run_id"],
                    future_file["source_file_id"],
                    *case_version_values,
                ),
            ).fetchone()
            future_prompt = conn.execute(
                """
                INSERT INTO inventory.prompt_records
                  (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING prompt_record_id
                """,
                (
                    future_case_version["source_case_version_id"],
                    first["prompt_id"],
                    first["raw_text"],
                    first["language"],
                    future_file["source_file_id"],
                    json.dumps(first["prompt_location"], ensure_ascii=False),
                    first["raw_text_sha256"],
                ),
            ).fetchone()
            future_asset_source = conn.execute(
                """
                INSERT INTO inventory.asset_sources
                  (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING asset_source_id
                """,
                (
                    future_case_version["source_case_version_id"],
                    first["asset_ref_id"],
                    future_file["source_file_id"],
                    first["content_sha256"],
                    first["role"],
                    json.dumps(first["asset_location"], ensure_ascii=False),
                ),
            ).fetchone()
            future_generation = conn.execute(
                """
                INSERT INTO inventory.generation_examples
                  (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                VALUES (%s, %s, %s, %s::jsonb, 'contract_valid')
                RETURNING generation_example_row_id
                """,
                (
                    first["generation_example_id"],
                    future_case_version["source_case_version_id"],
                    future_prompt["prompt_record_id"],
                    "{}",
                ),
            ).fetchone()
            conn.execute(
                "INSERT INTO inventory.generation_outputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                (future_generation["generation_example_row_id"], 1, future_asset_source["asset_source_id"]),
            )
            same_generation_count = conn.execute(
                """
                SELECT count(*) AS count
                FROM inventory.generation_examples
                WHERE generation_example_id = %s
                  AND source_case_version_id IN (%s, %s)
                """,
                (
                    first["generation_example_id"],
                    first["source_case_version_id"],
                    future_case_version["source_case_version_id"],
                ),
            ).fetchone()
            if int(same_generation_count["count"]) != 2:
                raise ValidationFailure("identical generation example IDs did not coexist across case revisions")
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.source_case_versions
                  (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                   source_locator, adapter_record, generation_document, contract_state)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'contract_valid')
                """,
                (
                    first["source_case_id"],
                    foreign_revision["source_revision_id"],
                    foreign_run["source_adapter_run_id"],
                    foreign_file["source_file_id"],
                    *case_version_values,
                ),
                "cross_project_case_revision",
            )
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.source_case_versions
                  (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                   source_locator, adapter_record, generation_document, contract_state)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'contract_valid')
                """,
                (
                    first["source_case_id"],
                    first["source_revision_id"],
                    future_run["source_adapter_run_id"],
                    first["source_file_id"],
                    *case_version_values,
                ),
                "cross_revision_adapter_run",
            )
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.source_case_versions
                  (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                   source_locator, adapter_record, generation_document, contract_state)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'contract_valid')
                """,
                (
                    first["source_case_id"],
                    first["source_revision_id"],
                    first["source_adapter_run_id"],
                    future_file["source_file_id"],
                    *case_version_values,
                ),
                "cross_revision_source_file",
            )
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.prompt_records
                  (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (first["source_case_version_id"], "task0005-cross-file-prompt", "test", "en", future_file["source_file_id"], "{}", "0" * 64),
                "cross_revision_prompt_source_file",
            )
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.asset_sources
                  (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    first["source_case_version_id"],
                    "task0005-cross-file-asset",
                    future_file["source_file_id"],
                    first["content_sha256"],
                    "output_primary",
                    "{}",
                ),
                "cross_revision_asset_source_file",
            )
            _expect_database_rejection(
                conn,
                """
                INSERT INTO inventory.generation_examples
                  (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                VALUES (%s, %s, %s, %s::jsonb, 'contract_valid')
                """,
                ("task0005-cross-case-generation", first["source_case_version_id"], second["prompt_record_id"], "{}"),
                "generation_foreign_prompt",
            )
            _expect_database_rejection(
                conn,
                "INSERT INTO inventory.generation_inputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                (first["generation_example_row_id"], 0, second["asset_source_id"]),
                "generation_foreign_input_asset",
            )
            _expect_database_rejection(
                conn,
                "INSERT INTO inventory.generation_outputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                (first["generation_example_row_id"], 1, second["asset_source_id"]),
                "generation_foreign_output_asset",
            )
        finally:
            conn.execute("ROLLBACK")

    return {
        "rejections": [
            "cross_project_case_revision",
            "cross_revision_adapter_run",
            "cross_revision_source_file",
            "cross_revision_prompt_source_file",
            "cross_revision_asset_source_file",
            "generation_foreign_prompt",
            "generation_foreign_input_asset",
            "generation_foreign_output_asset",
        ],
        "future_revision_registry_snapshot": True,
        "generation_id_reused_across_revisions": True,
    }


def _cleanup_compose(env_file: Path, project: str) -> bool:
    try:
        _compose(["down", "-v", "--remove-orphans"], env_file=env_file, project=project, check=True, timeout=180)
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
        if containers.stdout.strip() or volumes.stdout.strip():
            raise ValidationFailure("isolated Compose resources were not fully removed")
        return True
    except (OSError, subprocess.SubprocessError, ValidationFailure):
        return False


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime_env = _runtime_environment()
    if args.runs != 2:
        raise ValidationFailure("TASK-0005 requires exactly two idempotent import runs")
    if not args.failure_injection or not args.concurrency:
        raise ValidationFailure("TASK-0005 requires failure injection and concurrency validation")
    if args.expected_cases != 100:
        raise ValidationFailure("TASK-0005 expected-cases must be 100")
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0005 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="live-inventory-", dir=runtime_root))
    project = f"task0005{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_ok = False
    try:
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
        primary_bucket = "inventory-private-primary"
        environment = _runtime_env(database_url, endpoint, primary_bucket, s3_access_key, s3_secret_key)
        compose_started = True
        _compose(["up", "-d"], env_file=env_file, project=project, timeout=900)
        _wait_for_services(database_url, endpoint, s3_access_key, s3_secret_key)
        migrate_code, migrate_payload = _run_inventory(["migrate", "--migrations-dir", str(REPO_ROOT / "migrations")], environment)
        if migrate_code != 0 or migrate_payload.get("status") != "migrated":
            raise ValidationFailure("initial inventory migration failed")
        repeat_code, repeat_payload = _run_inventory(["migrate", "--migrations-dir", str(REPO_ROOT / "migrations")], environment)
        if repeat_code != 0 or repeat_payload.get("status") != "migrated":
            raise ValidationFailure("repeat inventory migration failed")
        drift_dir = run_root / "migration-drift"
        drift_dir.mkdir()
        drift_path = drift_dir / "0001_internal_inventory.sql"
        drift_path.write_text(
            (REPO_ROOT / "migrations" / "0001_internal_inventory.sql").read_text(encoding="utf-8") + "\n-- controlled checksum drift\n",
            encoding="utf-8",
        )
        drift_code, drift_payload = _run_inventory(["migrate", "--migrations-dir", str(drift_dir)], environment)
        if drift_code == 0 or drift_payload.get("error_code") != "migration_drift":
            raise ValidationFailure("applied migration checksum drift was not rejected")

        extraction = extract(
            registry_path=Path(args.registry),
            audit_path=Path(args.audit),
            source_id=args.source_id,
            data_root=run_root / "git-data",
            output_root=run_root / "extraction-output",
        )
        if extraction.status != "published":
            raise ValidationFailure("fresh TASK-0003 package generation did not publish")
        package_root = extraction.output_path
        plan = build_import_plan(package_root=package_root, registry_path=Path(args.registry), audit_path=Path(args.audit))
        if plan.revision_sha != args.expected_commit:
            raise ValidationFailure("fresh package Commit differs from the expected fixed Commit")
        if plan.metrics.get("observed_case_count") != args.expected_cases or plan.metrics.get("case_fingerprint_aggregate_sha256") != args.expected_aggregate:
            raise ValidationFailure("fresh package metrics differ from TASK-0001 fixed evidence")

        conflict_bucket = "inventory-private-conflict"
        conflict_env = _runtime_env(database_url, endpoint, conflict_bucket, s3_access_key, s3_secret_key)
        conflict_client = _s3_client(endpoint, s3_access_key, s3_secret_key)
        conflict_client.create_bucket(Bucket=conflict_bucket)
        first_asset = plan.asset_sources[0]
        conflict_client.put_object(
            Bucket=conflict_bucket,
            Key=object_key_for(first_asset.content_sha256),
            Body=b"not-the-expected-original" * 64,
            ContentType=first_asset.media_type,
            Metadata={"sha256": first_asset.content_sha256},
        )
        conflict_code, conflict_payload = _run_inventory(
            [
                "import-package",
                "--registry",
                str(args.registry),
                "--audit",
                str(args.audit),
                "--package-root",
                str(package_root),
                "--data-root",
                str(run_root / "import-git-data"),
            ],
            conflict_env,
            timeout=1200,
        )
        if conflict_code == 0 or conflict_payload.get("error_code") != "object_conflict":
            raise ValidationFailure("preexisting conflicting object was not rejected fail-closed")
        _expect_empty_database(database_url)

        failure_codes: dict[str, str] = {}
        for point in FAILURE_POINTS:
            code, payload = _run_inventory(
                [
                    "import-package",
                    "--registry",
                    str(args.registry),
                    "--audit",
                    str(args.audit),
                    "--package-root",
                    str(package_root),
                    "--data-root",
                    str(run_root / "import-git-data"),
                    "--failure-point",
                    point,
                ],
                environment,
                timeout=1200,
            )
            expected_code = f"injected_{point}"
            if code == 0 or payload.get("error_code") != expected_code:
                raise ValidationFailure(f"failure injection {point} did not report its stable error code")
            _expect_empty_database(database_url)
            failure_codes[point] = expected_code

        first_code, first_payload = _run_inventory(
            [
                "import-package",
                "--registry",
                str(args.registry),
                "--audit",
                str(args.audit),
                "--package-root",
                str(package_root),
                "--data-root",
                str(run_root / "import-git-data"),
            ],
            environment,
            timeout=1200,
        )
        if first_code != 0 or first_payload.get("status") != "imported":
            raise ValidationFailure("first full inventory import failed")
        summary = first_payload.get("summary")
        if not isinstance(summary, dict):
            raise ValidationFailure("first import did not return a stable inventory summary")
        expected_counts = {
            "source_projects": 1,
            "source_revisions": 1,
            "source_files": 101,
            "source_adapter_runs": 1,
            "source_parse_errors": 0,
            "source_cases": 100,
            "source_case_versions": 100,
            "prompt_records": 100,
            "assets": 100,
            "asset_sources": 100,
            "generation_examples": 100,
            "generation_inputs": 0,
            "generation_outputs": 100,
            "pairing_evidence": 100,
            "rights_records": 100,
        }
        if summary.get("counts") != expected_counts:
            raise ValidationFailure("first import database evidence counts do not close")
        if summary.get("revision_sha") != args.expected_commit or summary.get("metrics", {}).get("case_fingerprint_aggregate_sha256") != args.expected_aggregate:
            raise ValidationFailure("stable inspect summary differs from expected source evidence")
        with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
            rights = conn.execute(
                "SELECT count(*) AS count FROM inventory.rights_records WHERE prompt_rights_status <> 'unknown' OR asset_rights_status <> 'unknown'"
            ).fetchone()
            claims = conn.execute(
                "SELECT count(*) AS count FROM inventory.generation_examples WHERE source_claim->>'evidence_status' <> 'source_claimed'"
            ).fetchone()
            raw_mismatch = conn.execute(
                """
                SELECT count(*) AS count
                FROM inventory.source_case_versions v
                JOIN inventory.prompt_records p ON p.source_case_version_id=v.source_case_version_id
                WHERE p.raw_text <> v.adapter_record->'prompt'->>'raw_text'
                """
            ).fetchone()
            if int(rights["count"]) != 0 or int(claims["count"]) != 0 or int(raw_mismatch["count"]) != 0:
                raise ValidationFailure("inventory upgraded rights or source-claimed model evidence")
        with psycopg.connect(database_url, autocommit=True) as conn:
            try:
                conn.execute("UPDATE inventory.prompt_records SET raw_text = raw_text")
            except psycopg.Error:
                pass
            else:
                raise ValidationFailure("immutable evidence trigger allowed a prompt update")
            try:
                conn.execute("DELETE FROM inventory.rights_records")
            except psycopg.Error:
                pass
            else:
                raise ValidationFailure("immutable evidence trigger allowed a rights-record delete")

        objects: dict[str, ObjectFact] = {}
        for asset_source in plan.asset_sources:
            objects.setdefault(
                asset_source.content_sha256,
                ObjectFact(
                    asset_source.content_sha256,
                    object_key_for(asset_source.content_sha256),
                    primary_bucket,
                    asset_source.byte_size,
                    asset_source.media_type,
                    "content_verified",
                ),
            )
        store = S3ObjectStore(ObjectStoreConfig(endpoint, primary_bucket, s3_access_key, s3_secret_key))
        downloaded = store.download_hashes(objects)
        if len(downloaded) != 100:
            raise ValidationFailure("live validation did not download-hash all 100 private originals")
        primary_client = _s3_client(endpoint, s3_access_key, s3_secret_key)
        _assert_private_bucket(primary_client, primary_bucket)
        for fact in objects.values():
            _assert_private_object_acl(primary_client, primary_bucket, fact.object_key)

        domain_evidence = _verify_database_domains(database_url, plan)
        security_rejections: dict[str, str] = {}
        acl_write_capability: dict[str, str] = {}
        import_argv = [
            "import-package",
            "--registry",
            str(args.registry),
            "--audit",
            str(args.audit),
            "--package-root",
            str(package_root),
            "--data-root",
            str(run_root / "import-git-data"),
        ]
        public_policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{primary_bucket}/*",
                    }
                ],
            },
            separators=(",", ":"),
        )
        primary_client.put_bucket_policy(Bucket=primary_bucket, Policy=public_policy)
        try:
            code, payload = _run_inventory(import_argv, environment, timeout=1200)
            if code == 0 or payload.get("error_code") != "bucket_policy_public":
                raise ValidationFailure("public bucket policy was not rejected fail-closed")
            security_rejections["public_bucket_policy"] = "bucket_policy_public"
        finally:
            primary_client.delete_bucket_policy(Bucket=primary_bucket)
        _assert_private_bucket(primary_client, primary_bucket)

        # The fixed legacy MinIO image exposes a private default ACL through
        # GetBucketAcl but returns NotImplemented for PutBucketAcl. That exact
        # capability was observed in this formal task; production fail-closed
        # handling remains covered by the offline fake and the live default
        # ACL read above, without repeatedly attempting the unsupported call.
        acl_write_capability["bucket_acl_injection"] = "unsupported_by_legacy_s3"
        _assert_private_bucket(primary_client, primary_bucket)

        networked_acl_probe = _verify_networked_public_object_acl_probe(run_root)
        security_rejections["public_existing_object_acl"] = str(networked_acl_probe["status"])

        second_code, second_payload = _run_inventory(
            [
                "import-package",
                "--registry",
                str(args.registry),
                "--audit",
                str(args.audit),
                "--package-root",
                str(package_root),
                "--data-root",
                str(run_root / "import-git-data"),
            ],
            environment,
            timeout=1200,
        )
        if second_code != 0 or second_payload.get("status") != "verified_existing" or second_payload.get("summary") != summary:
            raise ValidationFailure("idempotent import did not return the exact stable existing summary")

        holder = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "inventory",
                "import-package",
                "--registry",
                str(args.registry),
                "--audit",
                str(args.audit),
                "--package-root",
                str(package_root),
                "--data-root",
                str(run_root / "import-git-data"),
                "--lock-hold-seconds",
                "4",
                "--json",
            ],
            cwd=str(REPO_ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for_advisory_lock(database_url, plan.idempotency_key)
            locked_code, locked_payload = _run_inventory(
                [
                    "import-package",
                    "--registry",
                    str(args.registry),
                    "--audit",
                    str(args.audit),
                    "--package-root",
                    str(package_root),
                    "--data-root",
                    str(run_root / "import-git-data"),
                ],
                environment,
                timeout=300,
            )
            if locked_code == 0 or locked_payload.get("error_code") != "import_locked":
                raise ValidationFailure("concurrent second writer did not receive import_locked")
        finally:
            holder_stdout, _holder_stderr = holder.communicate(timeout=1200)
        try:
            holder_payload = json.loads(holder_stdout.strip())
        except json.JSONDecodeError as exc:
            raise ValidationFailure("concurrency holder did not emit a JSON result") from exc
        if holder.returncode != 0 or holder_payload.get("status") != "verified_existing":
            raise ValidationFailure("concurrency holder did not remain the sole successful lock owner")

        return {
            "status": "passed",
            "source_id": args.source_id,
            "commit": args.expected_commit,
            "environment": runtime_env,
            "docker": {
                "postgres_image": POSTGRES_IMAGE,
                "legacy_s3_image": MINIO_IMAGE,
                "loopback_only": True,
            },
            "package": {
                "manifest_stable_sha256": plan.manifest["manifest_stable_sha256"],
                "semantic_digest": plan.semantic_digest,
                "case_fingerprint_aggregate_sha256": plan.metrics["case_fingerprint_aggregate_sha256"],
            },
            "database_counts": expected_counts,
            "object_download_hash_count": len(downloaded),
            "failure_codes": failure_codes,
            "object_conflict_rejected": True,
            "security_rejections": security_rejections,
            "acl_write_capability": acl_write_capability,
            "networked_object_acl_probe": networked_acl_probe,
            "database_domain_rejections": domain_evidence["rejections"],
            "future_revision_registry_snapshot": domain_evidence["future_revision_registry_snapshot"],
            "generation_id_reused_across_revisions": domain_evidence["generation_id_reused_across_revisions"],
            "idempotent_second_status": second_payload["status"],
            "concurrent_second_status": "import_locked",
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
    parser = argparse.ArgumentParser(description="Run the isolated TASK-0005 PostgreSQL/S3/Git validator.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-cases", type=int, required=True)
    parser.add_argument("--expected-aggregate", required=True)
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--failure-injection", action="store_true")
    parser.add_argument("--concurrency", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run(args)
    except (ValidationFailure, PackageValidationError, ExtractionError, subprocess.TimeoutExpired, OSError) as exc:
        payload = {"status": "failed", "error": str(exc), "error_type": type(exc).__name__}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print("failed")
        return 1
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
