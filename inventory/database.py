"""PostgreSQL migration, advisory-lock, transaction, and inspect boundary."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .object_store import ObjectFact
from .package import AssetSourcePlan, ImportPlan


class DatabaseError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str

    def validate(self) -> None:
        if not isinstance(self.dsn, str) or not self.dsn:
            raise DatabaseError("database_config_invalid", "PostgreSQL connection configuration is required")
        lowered = self.dsn.lower()
        if not (lowered.startswith("postgresql://") or lowered.startswith("postgres://")):
            raise DatabaseError("database_config_invalid", "PostgreSQL connection must use a postgresql URL")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def advisory_key(idempotency_key: str) -> int:
    if not isinstance(idempotency_key, str) or not idempotency_key:
        raise DatabaseError("database_identity_invalid", "idempotency key is required for advisory locking")
    return int.from_bytes(hashlib.sha256(idempotency_key.encode("utf-8")).digest()[:8], "big", signed=True)


def _migration_files(migrations_dir: Path) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        match = re.fullmatch(r"(\d{4}_[a-z0-9_]+)\.sql", path.name)
        if not match:
            raise DatabaseError("migration_invalid", "migration filenames must use NNNN_lowercase_name.sql")
        candidates.append((match.group(1), path))
    if not candidates:
        raise DatabaseError("migration_invalid", "no SQL migrations were found")
    return candidates


def _migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InventoryDatabase:
    def __init__(self, config: DatabaseConfig) -> None:
        config.validate()
        self.config = config

    def _connect(self, *, autocommit: bool) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self.config.dsn, autocommit=autocommit, row_factory=dict_row)
        except psycopg.Error as exc:
            raise DatabaseError("database_unavailable", "unable to connect to configured PostgreSQL") from exc

    def apply_migrations(self, migrations_dir: Path | str) -> list[dict[str, str]]:
        directory = Path(migrations_dir).resolve()
        migrations = _migration_files(directory)
        conn = self._connect(autocommit=False)
        applied: list[dict[str, str]] = []
        try:
            with conn.transaction():
                conn.execute("CREATE SCHEMA IF NOT EXISTS inventory")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS inventory.schema_migrations (
                        version text PRIMARY KEY,
                        checksum_sha256 char(64) NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                rows = conn.execute("SELECT version, checksum_sha256 FROM inventory.schema_migrations").fetchall()
                existing = {str(row["version"]): str(row["checksum_sha256"]) for row in rows}
                for version, path in migrations:
                    checksum = _migration_checksum(path)
                    known = existing.get(version)
                    if known is not None:
                        if known != checksum:
                            raise DatabaseError("migration_drift", "applied migration checksum differs from repository SQL")
                        applied.append({"version": version, "checksum_sha256": checksum, "status": "verified_existing"})
                        continue
                    try:
                        conn.execute(path.read_text(encoding="utf-8"))
                        conn.execute(
                            "INSERT INTO inventory.schema_migrations(version, checksum_sha256) VALUES (%s, %s)",
                            (version, checksum),
                        )
                    except psycopg.Error as exc:
                        raise DatabaseError("migration_failed", "repository migration could not be applied") from exc
                    applied.append({"version": version, "checksum_sha256": checksum, "status": "applied"})
            return applied
        finally:
            conn.close()

    def assert_migrated(self) -> None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT to_regclass('inventory.source_adapter_runs') AS table_name,
                       EXISTS (
                           SELECT 1
                           FROM information_schema.columns
                           WHERE table_schema = 'inventory'
                             AND table_name = 'source_adapter_runs'
                             AND column_name = 'registry_snapshot'
                       ) AS has_registry_snapshot
                """
            ).fetchone()
            if (
                not row
                or row.get("table_name") != "inventory.source_adapter_runs"
                or row.get("has_registry_snapshot") is not True
            ):
                raise DatabaseError("schema_not_migrated", "inventory migration has not been applied")
        except psycopg.Error as exc:
            raise DatabaseError("schema_not_migrated", "inventory migration has not been applied") from exc
        finally:
            conn.close()

    @contextmanager
    def advisory_lock(self, idempotency_key: str) -> Iterator[None]:
        key = advisory_key(idempotency_key)
        conn = self._connect(autocommit=True)
        acquired = False
        try:
            row = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
            acquired = bool(row and row.get("acquired"))
            if not acquired:
                raise DatabaseError("import_locked", "another importer owns the package advisory lock")
            yield
        except psycopg.Error as exc:
            raise DatabaseError("database_lock_failed", "PostgreSQL advisory lock operation failed") from exc
        finally:
            if acquired:
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
                except psycopg.Error:
                    pass
            conn.close()

    def _source_project(self, conn: psycopg.Connection[Any], plan: ImportPlan) -> int:
        repository = plan.source_record.get("repository") if isinstance(plan.source_record.get("repository"), dict) else {}
        row = conn.execute(
            """
            INSERT INTO inventory.source_projects
              (source_id, repository_id)
            VALUES (%s, %s)
            ON CONFLICT (source_id) DO NOTHING
            RETURNING source_project_id
            """,
            (
                plan.source_id,
                str(repository.get("repository_id", "")),
            ),
        ).fetchone()
        if row:
            return int(row["source_project_id"])
        existing = conn.execute(
            "SELECT source_project_id, repository_id FROM inventory.source_projects WHERE source_id = %s",
            (plan.source_id,),
        ).fetchone()
        if not existing or str(existing["repository_id"]) != str(repository.get("repository_id", "")):
            raise DatabaseError("source_conflict", "existing source project differs from registry identity")
        return int(existing["source_project_id"])

    def _source_revision(self, conn: psycopg.Connection[Any], source_project_id: int, plan: ImportPlan) -> int:
        row = conn.execute(
            """
            INSERT INTO inventory.source_revisions(source_project_id, revision_sha)
            VALUES (%s, %s)
            ON CONFLICT (source_project_id, revision_sha) DO NOTHING
            RETURNING source_revision_id
            """,
            (source_project_id, plan.revision_sha),
        ).fetchone()
        if row:
            return int(row["source_revision_id"])
        existing = conn.execute(
            "SELECT source_revision_id FROM inventory.source_revisions WHERE source_project_id = %s AND revision_sha = %s",
            (source_project_id, plan.revision_sha),
        ).fetchone()
        if not existing:
            raise DatabaseError("database_internal", "source revision could not be resolved")
        return int(existing["source_revision_id"])

    def _source_files(self, conn: psycopg.Connection[Any], revision_id: int, plan: ImportPlan) -> dict[tuple[str, str], int]:
        result: dict[tuple[str, str], int] = {}
        for item in plan.source_files:
            source_path = item["source_path"]
            source_url = item["source_url"]
            row = conn.execute(
                """
                INSERT INTO inventory.source_files(source_revision_id, source_path, source_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_revision_id, source_path, source_url) DO NOTHING
                RETURNING source_file_id
                """,
                (revision_id, source_path, source_url),
            ).fetchone()
            if row:
                result[(source_path, source_url)] = int(row["source_file_id"])
                continue
            existing = conn.execute(
                "SELECT source_file_id FROM inventory.source_files WHERE source_revision_id=%s AND source_path=%s AND source_url=%s",
                (revision_id, source_path, source_url),
            ).fetchone()
            if not existing:
                raise DatabaseError("database_internal", "source file could not be resolved")
            result[(source_path, source_url)] = int(existing["source_file_id"])
        return result

    @staticmethod
    def _location_key(location: dict[str, Any]) -> tuple[str, str]:
        return str(location["source_path"]), str(location["source_url"])

    def _insert_assets(self, conn: psycopg.Connection[Any], objects: dict[str, ObjectFact]) -> None:
        for content_hash, fact in sorted(objects.items()):
            row = conn.execute(
                """
                INSERT INTO inventory.assets(content_sha256, object_key, object_bucket, byte_size, media_type, integrity_state)
                VALUES (%s, %s, %s, %s, %s, 'verified')
                ON CONFLICT (content_sha256) DO NOTHING
                RETURNING content_sha256
                """,
                (content_hash, fact.object_key, fact.bucket, fact.byte_size, fact.media_type),
            ).fetchone()
            if row:
                continue
            existing = conn.execute(
                "SELECT object_key, object_bucket, byte_size, media_type, integrity_state FROM inventory.assets WHERE content_sha256=%s",
                (content_hash,),
            ).fetchone()
            if not existing or (
                str(existing["object_key"]) != fact.object_key
                or str(existing["object_bucket"]) != fact.bucket
                or int(existing["byte_size"]) != fact.byte_size
                or str(existing["media_type"]) != fact.media_type
                or str(existing["integrity_state"]) != "verified"
            ):
                raise DatabaseError("asset_conflict", "existing database asset differs from verified content address")

    def _existing_run(self, conn: psycopg.Connection[Any], plan: ImportPlan) -> dict[str, Any] | None:
        return conn.execute(
            """
            SELECT source_adapter_run_id, manifest_stable_sha256, semantic_digest, state, registry_snapshot
            FROM inventory.source_adapter_runs
            WHERE package_idempotency_key = %s
            """,
            (plan.idempotency_key,),
        ).fetchone()

    def existing_is_complete(self, plan: ImportPlan, objects: dict[str, ObjectFact]) -> bool:
        conn = self._connect(autocommit=True)
        try:
            run = self._existing_run(conn, plan)
            if run is None:
                return False
            if (
                str(run["manifest_stable_sha256"]) != str(plan.manifest["manifest_stable_sha256"])
                or str(run["semantic_digest"]) != plan.semantic_digest
                or str(run["state"]) != "ready"
                or run["registry_snapshot"] != plan.source_record
            ):
                raise DatabaseError("package_conflict", "existing package idempotency key differs from the import plan")
            summary = self.inspect(plan.idempotency_key, connection=conn)
            expected_cases = len(plan.adapter_output["records"])
            expected_generations = sum(len(document["generation_examples"]) for document in plan.generation_documents)
            expected_outputs = sum(len(generation["output_asset_ids"]) for document in plan.generation_documents for generation in document["generation_examples"])
            expected_inputs = sum(len(generation["input_asset_ids"]) for document in plan.generation_documents for generation in document["generation_examples"])
            expected = {
                "source_files": len(plan.source_files),
                "source_cases": expected_cases,
                "source_case_versions": expected_cases,
                "prompt_records": expected_cases,
                "assets": len(objects),
                "asset_sources": len(plan.asset_sources),
                "generation_examples": expected_generations,
                "generation_inputs": expected_inputs,
                "generation_outputs": expected_outputs,
                "pairing_evidence": expected_generations,
                "rights_records": expected_cases,
                "source_parse_errors": 0,
            }
            if any(summary["counts"].get(key) != value for key, value in expected.items()):
                raise DatabaseError("package_conflict", "existing ready inventory has incomplete or mismatched evidence counts")
            return True
        finally:
            conn.close()

    def insert_ready_plan(
        self,
        plan: ImportPlan,
        objects: dict[str, ObjectFact],
        *,
        failure_point: str | None = None,
    ) -> None:
        conn = self._connect(autocommit=False)
        try:
            with conn.transaction():
                source_project_id = self._source_project(conn, plan)
                revision_id = self._source_revision(conn, source_project_id, plan)
                files = self._source_files(conn, revision_id, plan)
                run_row = conn.execute(
                    """
                    INSERT INTO inventory.source_adapter_runs
                      (source_revision_id, adapter_id, adapter_version, contract_version,
                       package_idempotency_key, manifest_stable_sha256, semantic_digest,
                       coverage, metrics, manifest, registry_snapshot, state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, 'ready')
                    RETURNING source_adapter_run_id
                    """,
                    (
                        revision_id,
                        plan.adapter_output["adapter_id"],
                        plan.adapter_output["adapter_version"],
                        plan.manifest["contract_version"],
                        plan.idempotency_key,
                        plan.manifest["manifest_stable_sha256"],
                        plan.semantic_digest,
                        _canonical_json(plan.adapter_output["coverage"]),
                        _canonical_json(plan.metrics),
                        _canonical_json(plan.manifest),
                        _canonical_json(plan.source_record),
                    ),
                ).fetchone()
                if not run_row:
                    raise DatabaseError("database_internal", "ready adapter run could not be created")
                run_id = int(run_row["source_adapter_run_id"])
                self._insert_assets(conn, objects)
                documents_by_case: dict[str, list[dict[str, Any]]] = {}
                for document in plan.generation_documents:
                    documents_by_case.setdefault(str(document["source_case_key"]), []).append(document)
                case_version_ids: dict[str, int] = {}
                prompt_ids: dict[tuple[str, str], int] = {}
                asset_source_ids: dict[tuple[str, str], int] = {}
                sources_by_case: dict[str, list[AssetSourcePlan]] = {}
                for source in plan.asset_sources:
                    sources_by_case.setdefault(source.source_case_key, []).append(source)
                for index, record in enumerate(plan.adapter_output["records"]):
                    case_key = str(record["source_case_key"])
                    case_row = conn.execute(
                        """
                        INSERT INTO inventory.source_cases(source_project_id, source_case_key)
                        VALUES (%s, %s)
                        ON CONFLICT (source_project_id, source_case_key) DO NOTHING
                        RETURNING source_case_id
                        """,
                        (source_project_id, case_key),
                    ).fetchone()
                    if case_row:
                        case_id = int(case_row["source_case_id"])
                    else:
                        existing_case = conn.execute(
                            "SELECT source_case_id FROM inventory.source_cases WHERE source_project_id=%s AND source_case_key=%s",
                            (source_project_id, case_key),
                        ).fetchone()
                        if not existing_case:
                            raise DatabaseError("database_internal", "source case could not be resolved")
                        case_id = int(existing_case["source_case_id"])
                    locator = record["source_case_locator"]
                    case_file_id = files[self._location_key(locator)]
                    documents = documents_by_case.get(case_key, [])
                    generation_json: Any = documents[0] if len(documents) == 1 else {"documents": documents}
                    version_row = conn.execute(
                        """
                        INSERT INTO inventory.source_case_versions
                          (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                           source_locator, adapter_record, generation_document, contract_state)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 'contract_valid')
                        RETURNING source_case_version_id
                        """,
                        (
                            case_id,
                            revision_id,
                            run_id,
                            case_file_id,
                            _canonical_json(locator),
                            _canonical_json(record),
                            _canonical_json(generation_json),
                        ),
                    ).fetchone()
                    if not version_row:
                        raise DatabaseError("database_internal", "source case version could not be created")
                    version_id = int(version_row["source_case_version_id"])
                    case_version_ids[case_key] = version_id
                    prompt = record["prompt"]
                    prompt_row = conn.execute(
                        """
                        INSERT INTO inventory.prompt_records
                          (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                        RETURNING prompt_record_id
                        """,
                        (
                            version_id,
                            prompt["prompt_id"],
                            prompt["raw_text"],
                            prompt["language"],
                            files[self._location_key(prompt["source_location"])],
                            _canonical_json(prompt["source_location"]),
                            hashlib.sha256(prompt["raw_text"].encode("utf-8")).hexdigest(),
                        ),
                    ).fetchone()
                    if not prompt_row:
                        raise DatabaseError("database_internal", "prompt record could not be created")
                    prompt_ids[(case_key, str(prompt["prompt_id"]))] = int(prompt_row["prompt_record_id"])
                    for asset_source in sources_by_case.get(case_key, []):
                        row = conn.execute(
                            """
                            INSERT INTO inventory.asset_sources
                              (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                            RETURNING asset_source_id
                            """,
                            (
                                version_id,
                                asset_source.asset_ref_id,
                                files[self._location_key(asset_source.source_location)],
                                asset_source.content_sha256,
                                asset_source.role,
                                _canonical_json(asset_source.source_location),
                            ),
                        ).fetchone()
                        if not row:
                            raise DatabaseError("database_internal", "asset source could not be created")
                        asset_source_ids[(case_key, asset_source.asset_ref_id)] = int(row["asset_source_id"])
                    if failure_point == "mid_database" and index == 0:
                        raise DatabaseError("injected_mid_database", "controlled failure during database transaction")

                for document in plan.generation_documents:
                    case_key = str(document["source_case_key"])
                    version_id = case_version_ids[case_key]
                    asset_ids: dict[str, tuple[str, str]] = {}
                    for asset in document["assets"]:
                        asset_hash = str(asset["content_sha256"])
                        matching = next(
                            (
                                source
                                for source in sources_by_case.get(case_key, [])
                                if source.content_sha256 == asset_hash and source.source_location == asset["source_location"]
                            ),
                            None,
                        )
                        if matching is None:
                            raise DatabaseError("reference_mapping_invalid", "Generation Example asset does not map to an asset source")
                        asset_ids[str(asset["asset_id"])] = (matching.asset_ref_id, asset_hash)
                    rights = document["rights_evidence"]
                    conn.execute(
                        """
                        INSERT INTO inventory.rights_records
                          (source_case_version_id, prompt_rights_status, asset_rights_status, evidence_urls, note)
                        VALUES (%s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (source_case_version_id) DO NOTHING
                        """,
                        (
                            version_id,
                            rights["prompt_rights_status"],
                            rights["asset_rights_status"],
                            _canonical_json(rights["evidence_urls"]),
                            rights.get("note"),
                        ),
                    )
                    for generation in document["generation_examples"]:
                        prompt_id = str(generation["prompt_id"])
                        prompt_record_id = prompt_ids.get((case_key, prompt_id))
                        if prompt_record_id is None:
                            raise DatabaseError("reference_mapping_invalid", "Generation entry does not map to a case prompt")
                        row = conn.execute(
                            """
                            INSERT INTO inventory.generation_examples
                              (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                            VALUES (%s, %s, %s, %s::jsonb, 'contract_valid')
                            RETURNING generation_example_row_id
                            """,
                            (generation["generation_example_id"], version_id, prompt_record_id, _canonical_json(generation["generation_claim"])),
                        ).fetchone()
                        if not row:
                            raise DatabaseError("database_internal", "generation example could not be created")
                        generation_row_id = int(row["generation_example_row_id"])
                        for ordinal, asset_id in enumerate(generation["input_asset_ids"]):
                            ref_id, _ = asset_ids[str(asset_id)]
                            conn.execute(
                                "INSERT INTO inventory.generation_inputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                                (generation_row_id, ordinal, asset_source_ids[(case_key, ref_id)]),
                            )
                        for ordinal, asset_id in enumerate(generation["output_asset_ids"]):
                            ref_id, _ = asset_ids[str(asset_id)]
                            conn.execute(
                                "INSERT INTO inventory.generation_outputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                                (generation_row_id, ordinal, asset_source_ids[(case_key, ref_id)]),
                            )
                        pairing = generation["pairing"]
                        conn.execute(
                            """
                            INSERT INTO inventory.pairing_evidence(generation_example_row_id, ordinal, method, status, evidence)
                            VALUES (%s, 0, %s, %s, %s::jsonb)
                            """,
                            (generation_row_id, pairing["method"], pairing["status"], _canonical_json(pairing["evidence"])),
                        )
                self._assert_transaction_closure(conn, run_id, plan, objects)
                if failure_point == "before_commit":
                    raise DatabaseError("injected_before_commit", "controlled failure immediately before transaction commit")
        except DatabaseError:
            raise
        except psycopg.Error as exc:
            raise DatabaseError("database_write_failed", "inventory transaction failed and was rolled back") from exc
        finally:
            conn.close()

    def _assert_transaction_closure(
        self, conn: psycopg.Connection[Any], run_id: int, plan: ImportPlan, objects: dict[str, ObjectFact]
    ) -> None:
        expected_cases = len(plan.adapter_output["records"])
        expected_generations = sum(len(document["generation_examples"]) for document in plan.generation_documents)
        expected_outputs = sum(len(generation["output_asset_ids"]) for document in plan.generation_documents for generation in document["generation_examples"])
        expected_inputs = sum(len(generation["input_asset_ids"]) for document in plan.generation_documents for generation in document["generation_examples"])
        checks = {
            "source_case_versions": (
                "SELECT count(*) AS count FROM inventory.source_case_versions WHERE source_adapter_run_id=%s",
                expected_cases,
            ),
            "prompt_records": (
                "SELECT count(*) AS count FROM inventory.prompt_records p JOIN inventory.source_case_versions v ON v.source_case_version_id=p.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_cases,
            ),
            "asset_sources": (
                "SELECT count(*) AS count FROM inventory.asset_sources s JOIN inventory.source_case_versions v ON v.source_case_version_id=s.source_case_version_id WHERE v.source_adapter_run_id=%s",
                len(plan.asset_sources),
            ),
            "generation_examples": (
                "SELECT count(*) AS count FROM inventory.generation_examples g JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_generations,
            ),
            "generation_inputs": (
                "SELECT count(*) AS count FROM inventory.generation_inputs i JOIN inventory.generation_examples g ON g.generation_example_row_id=i.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_inputs,
            ),
            "generation_outputs": (
                "SELECT count(*) AS count FROM inventory.generation_outputs o JOIN inventory.generation_examples g ON g.generation_example_row_id=o.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_outputs,
            ),
            "pairing_evidence": (
                "SELECT count(*) AS count FROM inventory.pairing_evidence e JOIN inventory.generation_examples g ON g.generation_example_row_id=e.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_generations,
            ),
            "rights_records": (
                "SELECT count(*) AS count FROM inventory.rights_records r JOIN inventory.source_case_versions v ON v.source_case_version_id=r.source_case_version_id WHERE v.source_adapter_run_id=%s",
                expected_cases,
            ),
        }
        for label, (query, expected) in checks.items():
            row = conn.execute(query, (run_id,)).fetchone()
            if not row or int(row["count"]) != expected:
                raise DatabaseError("transaction_closure_failed", f"inventory transaction count did not close: {label}")
        missing_outputs = conn.execute(
            """
            SELECT count(*) AS count
            FROM inventory.generation_examples g
            JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id
            LEFT JOIN inventory.generation_outputs o ON o.generation_example_row_id=g.generation_example_row_id
            WHERE v.source_adapter_run_id=%s
            GROUP BY g.generation_example_row_id
            HAVING count(o.generation_output_id)=0
            """,
            (run_id,),
        ).fetchall()
        if missing_outputs:
            raise DatabaseError("transaction_closure_failed", "ready inventory has a Generation Example without an output")
        asset_count = conn.execute(
            "SELECT count(*) AS count FROM inventory.assets WHERE content_sha256 = ANY(%s)",
            (list(objects),),
        ).fetchone()
        if not asset_count or int(asset_count["count"]) != len(objects):
            raise DatabaseError("transaction_closure_failed", "verified object assets are not closed in the database")

    def inspect(self, idempotency_key: str, *, connection: psycopg.Connection[Any] | None = None) -> dict[str, Any]:
        own_connection = connection is None
        conn = connection or self._connect(autocommit=True)
        try:
            run = conn.execute(
                """
                SELECT r.source_adapter_run_id, r.package_idempotency_key, r.manifest_stable_sha256, r.semantic_digest,
                       r.adapter_id, r.adapter_version, r.contract_version, r.state, r.metrics,
                       p.source_id, v.revision_sha
                FROM inventory.source_adapter_runs r
                JOIN inventory.source_revisions v ON v.source_revision_id=r.source_revision_id
                JOIN inventory.source_projects p ON p.source_project_id=v.source_project_id
                WHERE r.package_idempotency_key=%s
                """,
                (idempotency_key,),
            ).fetchone()
            if not run or str(run["state"]) != "ready":
                raise DatabaseError("inventory_not_ready", "no ready inventory run exists for the requested package")
            run_id = int(run["source_adapter_run_id"])
            count_queries = {
                "source_projects": "SELECT count(*) AS count FROM inventory.source_projects p JOIN inventory.source_revisions v ON v.source_project_id=p.source_project_id JOIN inventory.source_adapter_runs r ON r.source_revision_id=v.source_revision_id WHERE r.source_adapter_run_id=%s",
                "source_revisions": "SELECT count(*) AS count FROM inventory.source_revisions v JOIN inventory.source_adapter_runs r ON r.source_revision_id=v.source_revision_id WHERE r.source_adapter_run_id=%s",
                "source_files": "SELECT count(*) AS count FROM inventory.source_files f JOIN inventory.source_adapter_runs r ON r.source_revision_id=f.source_revision_id WHERE r.source_adapter_run_id=%s",
                "source_adapter_runs": "SELECT 1 AS count",
                "source_parse_errors": "SELECT count(*) AS count FROM inventory.source_parse_errors WHERE source_adapter_run_id=%s",
                "source_cases": "SELECT count(*) AS count FROM inventory.source_cases c JOIN inventory.source_case_versions v ON v.source_case_id=c.source_case_id WHERE v.source_adapter_run_id=%s",
                "source_case_versions": "SELECT count(*) AS count FROM inventory.source_case_versions WHERE source_adapter_run_id=%s",
                "prompt_records": "SELECT count(*) AS count FROM inventory.prompt_records p JOIN inventory.source_case_versions v ON v.source_case_version_id=p.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "assets": "SELECT count(DISTINCT s.content_sha256) AS count FROM inventory.asset_sources s JOIN inventory.source_case_versions v ON v.source_case_version_id=s.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "asset_sources": "SELECT count(*) AS count FROM inventory.asset_sources s JOIN inventory.source_case_versions v ON v.source_case_version_id=s.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "generation_examples": "SELECT count(*) AS count FROM inventory.generation_examples g JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "generation_inputs": "SELECT count(*) AS count FROM inventory.generation_inputs i JOIN inventory.generation_examples g ON g.generation_example_row_id=i.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "generation_outputs": "SELECT count(*) AS count FROM inventory.generation_outputs o JOIN inventory.generation_examples g ON g.generation_example_row_id=o.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "pairing_evidence": "SELECT count(*) AS count FROM inventory.pairing_evidence e JOIN inventory.generation_examples g ON g.generation_example_row_id=e.generation_example_row_id JOIN inventory.source_case_versions v ON v.source_case_version_id=g.source_case_version_id WHERE v.source_adapter_run_id=%s",
                "rights_records": "SELECT count(*) AS count FROM inventory.rights_records x JOIN inventory.source_case_versions v ON v.source_case_version_id=x.source_case_version_id WHERE v.source_adapter_run_id=%s",
            }
            counts: dict[str, int] = {}
            for key, query in count_queries.items():
                row = conn.execute(query, () if key == "source_adapter_runs" else (run_id,)).fetchone()
                counts[key] = int(row["count"]) if row else 0
            identities = conn.execute(
                """
                SELECT c.source_case_key, p.prompt_id, s.content_sha256, g.generation_example_id
                FROM inventory.source_case_versions v
                JOIN inventory.source_cases c ON c.source_case_id=v.source_case_id
                JOIN inventory.prompt_records p ON p.source_case_version_id=v.source_case_version_id
                JOIN inventory.asset_sources s ON s.source_case_version_id=v.source_case_version_id
                JOIN inventory.generation_examples g ON g.source_case_version_id=v.source_case_version_id
                WHERE v.source_adapter_run_id=%s
                ORDER BY c.source_case_key, p.prompt_id, s.content_sha256, g.generation_example_id
                """,
                (run_id,),
            ).fetchall()
            digest = hashlib.sha256(_canonical_json(identities).encode("utf-8")).hexdigest()
            return {
                "schema_version": "inventory-inspect/v1",
                "state": "ready",
                "source_id": str(run["source_id"]),
                "revision_sha": str(run["revision_sha"]),
                "idempotency_key": str(run["package_idempotency_key"]),
                "manifest_stable_sha256": str(run["manifest_stable_sha256"]),
                "semantic_digest": str(run["semantic_digest"]),
                "adapter_id": str(run["adapter_id"]),
                "adapter_version": str(run["adapter_version"]),
                "contract_version": str(run["contract_version"]),
                "counts": counts,
                "natural_key_digest": digest,
                "metrics": run["metrics"],
            }
        except psycopg.Error as exc:
            raise DatabaseError("database_inspect_failed", "inventory inspect query failed") from exc
        finally:
            if own_connection:
                conn.close()
