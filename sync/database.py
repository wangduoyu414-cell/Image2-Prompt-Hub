"""PostgreSQL state for one-source incremental synchronization runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row


class SyncDatabaseError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SyncDatabaseSettings:
    database_url: str

    def validate(self) -> None:
        if not isinstance(self.database_url, str) or not self.database_url:
            raise SyncDatabaseError("sync_config_invalid", "PostgreSQL connection configuration is required")
        if not self.database_url.lower().startswith(("postgresql://", "postgres://")):
            raise SyncDatabaseError("sync_config_invalid", "PostgreSQL connection must use a postgresql URL")


def stable_sync_key(source_id: str, candidate_revision_sha: str) -> str:
    payload = f"incremental-sync/v1:{source_id}:{candidate_revision_sha}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _advisory_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:8], "big", signed=True)


def _json(value: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(value or {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, Mapping) else {}


class SyncDatabase:
    """Owns mutable run state and immutable remove/restore tombstone events."""

    def __init__(self, settings: SyncDatabaseSettings) -> None:
        settings.validate()
        self.settings = settings

    def _connect(self, *, autocommit: bool = False) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self.settings.database_url, autocommit=autocommit, row_factory=dict_row)
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_database_unavailable", "unable to connect to configured PostgreSQL") from exc

    def assert_migrated(self) -> None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT to_regclass('sync.source_sync_runs') AS runs,
                       to_regclass('sync.case_tombstone_events') AS tombstones,
                       to_regclass('content.publication_revision_selections') AS selections
                """
            ).fetchone()
            if not row or any(row[name] is None for name in ("runs", "tombstones", "selections")):
                raise SyncDatabaseError("sync_schema_not_migrated", "incremental sync migration has not been applied")
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_schema_not_migrated", "incremental sync migration has not been applied") from exc
        finally:
            conn.close()

    @contextmanager
    def advisory_lock(self, idempotency_key: str) -> Iterator[None]:
        conn = self._connect(autocommit=True)
        acquired = False
        try:
            row = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (_advisory_key(idempotency_key),)).fetchone()
            acquired = bool(row and row.get("acquired"))
            if not acquired:
                raise SyncDatabaseError("sync_locked", "another writer owns this source candidate")
            yield
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_lock_failed", "PostgreSQL sync advisory lock operation failed") from exc
        finally:
            if acquired:
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (_advisory_key(idempotency_key),))
                except psycopg.Error:
                    pass
            conn.close()

    @staticmethod
    def _run_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        for key in ("authority", "diff_document", "metrics", "result_document"):
            payload[key] = _object(payload.get(key))
        for key in ("created_at", "updated_at", "completed_at"):
            value = payload.get(key)
            payload[key] = value.isoformat() if hasattr(value, "isoformat") else value
        return payload

    def get_run(self, source_id: str, candidate_revision_sha: str) -> dict[str, Any] | None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                "SELECT * FROM sync.source_sync_runs WHERE source_id=%s AND candidate_revision_sha=%s",
                (source_id, candidate_revision_sha),
            ).fetchone()
            return self._run_payload(row) if row else None
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to read sync run state") from exc
        finally:
            conn.close()

    def begin_run(
        self,
        *,
        source_id: str,
        previous_revision_sha: str | None,
        candidate_revision_sha: str,
        authority: Mapping[str, Any],
    ) -> dict[str, Any]:
        key = stable_sync_key(source_id, candidate_revision_sha)
        conn = self._connect()
        try:
            with conn.transaction():
                inserted = conn.execute(
                    """
                    INSERT INTO sync.source_sync_runs
                      (source_id, previous_revision_sha, candidate_revision_sha, idempotency_key, state, authority)
                    VALUES (%s, %s, %s, %s, 'detected', %s::jsonb)
                    ON CONFLICT (source_id, candidate_revision_sha) DO NOTHING
                    RETURNING *
                    """,
                    (source_id, previous_revision_sha, candidate_revision_sha, key, _json(authority)),
                ).fetchone()
                if inserted:
                    return self._run_payload(inserted)
                existing = conn.execute(
                    "SELECT * FROM sync.source_sync_runs WHERE source_id=%s AND candidate_revision_sha=%s FOR UPDATE",
                    (source_id, candidate_revision_sha),
                ).fetchone()
                if not existing or str(existing["idempotency_key"]) != key:
                    raise SyncDatabaseError("sync_idempotency_conflict", "existing source candidate run differs from its stable key")
                return self._run_payload(existing)
        except SyncDatabaseError:
            raise
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_write_failed", "unable to create or read the sync run") from exc
        finally:
            conn.close()

    def update_run(
        self,
        sync_run_id: int,
        *,
        state: str,
        diff_document: Mapping[str, Any] | None = None,
        metrics: Mapping[str, Any] | None = None,
        package_idempotency_key: str | None = None,
        source_adapter_run_id: int | None = None,
        publication_version_id: int | None = None,
        reason_code: str | None = None,
        error_code: str | None = None,
        result_document: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = self._connect()
        try:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE sync.source_sync_runs
                    SET state=%s,
                        diff_document=COALESCE(%s::jsonb, diff_document),
                        metrics=COALESCE(%s::jsonb, metrics),
                        package_idempotency_key=COALESCE(%s, package_idempotency_key),
                        source_adapter_run_id=COALESCE(%s, source_adapter_run_id),
                        publication_version_id=COALESCE(%s, publication_version_id),
                        reason_code=%s,
                        error_code=%s,
                        result_document=COALESCE(%s::jsonb, result_document)
                    WHERE sync_run_id=%s
                    RETURNING *
                    """,
                    (
                        state,
                        _json(diff_document) if diff_document is not None else None,
                        _json(metrics) if metrics is not None else None,
                        package_idempotency_key,
                        source_adapter_run_id,
                        publication_version_id,
                        reason_code,
                        error_code,
                        _json(result_document) if result_document is not None else None,
                        sync_run_id,
                    ),
                ).fetchone()
                if not row:
                    raise SyncDatabaseError("sync_run_missing", "sync run does not exist")
                return self._run_payload(row)
        except SyncDatabaseError:
            raise
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_write_failed", "unable to update sync run state") from exc
        finally:
            conn.close()

    def latest_ready_inventory(self, source_id: str) -> dict[str, Any] | None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT project.source_id, revision.revision_sha, run.source_adapter_run_id, run.metrics,
                       run.package_idempotency_key
                FROM inventory.source_adapter_runs AS run
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=run.source_revision_id
                JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
                WHERE project.source_id=%s AND run.state='ready'
                ORDER BY run.source_adapter_run_id DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["metrics"] = _object(result.get("metrics"))
            return result
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to read prior ready inventory") from exc
        finally:
            conn.close()

    def adapter_run_id_for_package(self, package_idempotency_key: str) -> int:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT source_adapter_run_id
                FROM inventory.source_adapter_runs
                WHERE package_idempotency_key=%s AND state='ready'
                """,
                (package_idempotency_key,),
            ).fetchone()
            if not row:
                raise SyncDatabaseError("sync_inventory_missing", "imported package has no ready inventory run")
            return int(row["source_adapter_run_id"])
        except SyncDatabaseError:
            raise
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to resolve imported inventory run") from exc
        finally:
            conn.close()

    def revision_case_documents(self, source_id: str, revision_sha: str) -> list[dict[str, Any]]:
        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT source_case.source_case_key, case_version.adapter_record, case_version.generation_document
                FROM inventory.source_case_versions AS case_version
                JOIN inventory.source_cases AS source_case ON source_case.source_case_id=case_version.source_case_id
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=case_version.source_revision_id
                JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
                JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id=case_version.source_adapter_run_id
                WHERE project.source_id=%s AND revision.revision_sha=%s AND run.state='ready'
                ORDER BY source_case.source_case_key
                """,
                (source_id, revision_sha),
            ).fetchall()
            return [
                {
                    "source_case_key": str(row["source_case_key"]),
                    "adapter_record": _object(row["adapter_record"]),
                    "generation_document": _object(row["generation_document"]),
                }
                for row in rows
            ]
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to read prior source case evidence") from exc
        finally:
            conn.close()

    def record_tombstone_events(
        self,
        *,
        sync_run_id: int,
        source_id: str,
        previous_revision_sha: str | None,
        candidate_revision_sha: str,
        removed_case_keys: list[str],
        added_case_keys: list[str],
    ) -> dict[str, int]:
        conn = self._connect()
        try:
            with conn.transaction():
                removed = 0
                restored = 0
                for case_key in sorted(set(removed_case_keys)):
                    row = conn.execute(
                        """
                        INSERT INTO sync.case_tombstone_events
                          (sync_run_id, source_id, source_case_key, previous_revision_sha, candidate_revision_sha, event_type, evidence)
                        VALUES (%s, %s, %s, %s, %s, 'removed', %s::jsonb)
                        ON CONFLICT (sync_run_id, source_case_key, event_type) DO NOTHING
                        RETURNING case_tombstone_event_id
                        """,
                        (sync_run_id, source_id, case_key, previous_revision_sha, candidate_revision_sha, _json({"reason": "case_absent_from_candidate"})),
                    ).fetchone()
                    removed += 1 if row else 0
                for case_key in sorted(set(added_case_keys)):
                    prior = conn.execute(
                        """
                        SELECT 1 FROM sync.case_tombstone_events
                        WHERE source_id=%s AND source_case_key=%s AND event_type='removed'
                        LIMIT 1
                        """,
                        (source_id, case_key),
                    ).fetchone()
                    if not prior:
                        continue
                    row = conn.execute(
                        """
                        INSERT INTO sync.case_tombstone_events
                          (sync_run_id, source_id, source_case_key, previous_revision_sha, candidate_revision_sha, event_type, evidence)
                        VALUES (%s, %s, %s, %s, %s, 'restored', %s::jsonb)
                        ON CONFLICT (sync_run_id, source_case_key, event_type) DO NOTHING
                        RETURNING case_tombstone_event_id
                        """,
                        (sync_run_id, source_id, case_key, previous_revision_sha, candidate_revision_sha, _json({"reason": "case_identity_reappeared"})),
                    ).fetchone()
                    restored += 1 if row else 0
                return {"removed_events": removed, "restored_events": restored}
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_tombstone_failed", "unable to record immutable tombstone events") from exc
        finally:
            conn.close()

    def publication_selection(self, *, source_id: str, candidate_revision_sha: str) -> dict[str, str]:
        """Build an explicit selection from current frozen state, then override one candidate."""

        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT project.source_id, revision.revision_sha
                FROM content.publication_current AS current
                JOIN content.publication_revision_selections AS selection
                  ON selection.publication_version_id=current.publication_version_id
                JOIN inventory.source_projects AS project ON project.source_project_id=selection.source_project_id
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=selection.source_revision_id
                WHERE current.singleton=true
                ORDER BY project.source_id
                """
            ).fetchall()
            selection = {str(row["source_id"]): str(row["revision_sha"]) for row in rows}
            if not selection:
                fallback = conn.execute(
                    """
                    SELECT DISTINCT ON (run.source_id) run.source_id, run.candidate_revision_sha
                    FROM sync.source_sync_runs AS run
                    WHERE run.state='completed' AND run.source_adapter_run_id IS NOT NULL
                    ORDER BY run.source_id, run.completed_at DESC NULLS LAST, run.sync_run_id DESC
                    """
                ).fetchall()
                selection = {str(row["source_id"]): str(row["candidate_revision_sha"]) for row in fallback}
            selection[source_id] = candidate_revision_sha
            return dict(sorted(selection.items()))
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to resolve explicit publication selection") from exc
        finally:
            conn.close()

    def inspect_source(self, source_id: str) -> dict[str, Any]:
        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT * FROM sync.source_sync_runs
                WHERE source_id=%s
                ORDER BY sync_run_id DESC
                """,
                (source_id,),
            ).fetchall()
            return {"source_id": source_id, "runs": [self._run_payload(row) for row in rows]}
        except psycopg.Error as exc:
            raise SyncDatabaseError("sync_read_failed", "unable to inspect source sync runs") from exc
        finally:
            conn.close()
