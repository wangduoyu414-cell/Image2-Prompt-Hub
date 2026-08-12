"""Durable scheduler/alert state without queue authority leakage."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .database import SyncDatabaseError, SyncDatabaseSettings


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def scheduler_cycle_key(registry_sha256: str, started_at: datetime) -> str:
    if started_at.tzinfo is None:
        raise SyncDatabaseError("scheduler_time_invalid", "scheduler time must include a timezone")
    bucket = started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M")
    return hashlib.sha256(f"scheduler/v1:{registry_sha256}:{bucket}".encode()).hexdigest()


def alert_fingerprint(alert_code: str, subject_key: str) -> str:
    return hashlib.sha256(f"operations-alert/v1:{alert_code}:{subject_key}".encode()).hexdigest()


@dataclass(frozen=True)
class SchedulerSourceResult:
    source_id: str
    state: str
    sync_status: str | None
    sync_run_id: int | None
    error_code: str | None
    result: Mapping[str, Any]


class OperationsDatabase:
    def __init__(self, settings: SyncDatabaseSettings) -> None:
        settings.validate()
        self.settings = settings

    def _connect(self, *, autocommit: bool = False) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self.settings.database_url, autocommit=autocommit, row_factory=dict_row)
        except psycopg.Error as exc:
            raise SyncDatabaseError("operations_database_unavailable", "operations database is unavailable") from exc

    def assert_migrated(self) -> None:
        with self._connect(autocommit=True) as conn:
            row = conn.execute(
                """
                SELECT to_regclass('sync.scheduler_cycles') AS cycles,
                       to_regclass('sync.scheduler_source_results') AS results,
                       to_regclass('sync.alert_deliveries') AS alerts
                """
            ).fetchone()
        if not row or any(row.get(name) is None for name in ("cycles", "results", "alerts")):
            raise SyncDatabaseError("operations_schema_not_migrated", "operations migration has not been applied")

    @contextmanager
    def source_lock(self, source_id: str):  # type: ignore[no-untyped-def]
        key = int.from_bytes(hashlib.sha256(f"scheduler-source/v1:{source_id}".encode()).digest()[:8], "big", signed=True)
        conn = self._connect(autocommit=True)
        acquired = False
        try:
            row = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
            acquired = bool(row and row.get("acquired"))
            yield acquired
        finally:
            if acquired:
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
                except psycopg.Error:
                    pass
            conn.close()

    @contextmanager
    def scheduler_lock(self):  # type: ignore[no-untyped-def]
        key = int.from_bytes(hashlib.sha256(b"scheduler-dispatch/v1").digest()[:8], "big", signed=True)
        conn = self._connect(autocommit=True)
        acquired = False
        try:
            row = conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()
            acquired = bool(row and row.get("acquired"))
            yield acquired
        finally:
            if acquired:
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
                except psycopg.Error:
                    pass
            conn.close()

    def begin_cycle(self, *, cycle_key: str, registry_sha256: str, source_ids: Iterable[str]) -> dict[str, Any]:
        eligible = sorted(set(source_ids))
        with self._connect() as conn, conn.transaction():
            row = conn.execute(
                """
                INSERT INTO sync.scheduler_cycles
                  (cycle_key, state, registry_sha256, eligible_source_ids, source_count)
                VALUES (%s, 'dispatching', %s, %s::jsonb, %s)
                ON CONFLICT (cycle_key) DO NOTHING
                RETURNING *
                """,
                (cycle_key, registry_sha256, _json(eligible), len(eligible)),
            ).fetchone()
            created = row is not None
            if row is None:
                row = conn.execute("SELECT * FROM sync.scheduler_cycles WHERE cycle_key=%s FOR UPDATE", (cycle_key,)).fetchone()
            if row is None or list(row["eligible_source_ids"]) != eligible or str(row["registry_sha256"]) != registry_sha256:
                raise SyncDatabaseError("scheduler_cycle_conflict", "existing scheduler cycle differs from its authority")
            cycle_id = int(row["scheduler_cycle_id"])
            if created:
                conn.executemany(
                    """
                    INSERT INTO sync.scheduler_source_results
                      (scheduler_cycle_id, source_id, state)
                    VALUES (%s, %s, 'queued')
                    """,
                    [(cycle_id, source_id) for source_id in eligible],
                )
                row = conn.execute(
                    """
                    UPDATE sync.scheduler_cycles SET queued_count=source_count
                    WHERE scheduler_cycle_id=%s RETURNING *
                    """,
                    (cycle_id,),
                ).fetchone()
            else:
                existing = conn.execute(
                    "SELECT source_id FROM sync.scheduler_source_results WHERE scheduler_cycle_id=%s ORDER BY source_id",
                    (cycle_id,),
                ).fetchall()
                if [str(item["source_id"]) for item in existing] != eligible:
                    raise SyncDatabaseError("scheduler_cycle_conflict", "existing scheduler cycle source ledger differs")
            if row is None:
                raise SyncDatabaseError("scheduler_cycle_conflict", "scheduler cycle is unavailable")
            return dict(row)

    def bind_message(self, *, cycle_id: int, source_id: str, message_id: str) -> None:
        with self._connect() as conn, conn.transaction():
            row = conn.execute(
                """
                UPDATE sync.scheduler_source_results
                SET message_id=%s
                WHERE scheduler_cycle_id=%s AND source_id=%s AND state='queued'
                RETURNING scheduler_source_result_id
                """,
                (message_id, cycle_id, source_id),
            ).fetchone()
            if row is None:
                raise SyncDatabaseError("scheduler_result_conflict", "queued scheduler source result is unavailable")

    def incomplete_dispatch(self) -> dict[str, Any] | None:
        with self._connect(autocommit=True) as conn:
            cycle = conn.execute(
                "SELECT * FROM sync.scheduler_cycles WHERE state='dispatching' ORDER BY scheduler_cycle_id LIMIT 1"
            ).fetchone()
            if cycle is None:
                return None
            rows = conn.execute(
                """
                SELECT source_id FROM sync.scheduler_source_results
                WHERE scheduler_cycle_id=%s AND state='queued' AND message_id IS NULL
                ORDER BY source_id
                """,
                (cycle["scheduler_cycle_id"],),
            ).fetchall()
        return {"cycle": dict(cycle), "source_ids": [str(row["source_id"]) for row in rows]}

    def stale_source_results(self, *, now: datetime, stale_seconds: int) -> list[dict[str, Any]]:
        if now.tzinfo is None:
            raise SyncDatabaseError("scheduler_time_invalid", "scheduler recovery time must include a timezone")
        with self._connect(autocommit=True) as conn:
            rows = conn.execute(
                """
                SELECT result.scheduler_cycle_id, result.source_id, result.state
                FROM sync.scheduler_source_results AS result
                JOIN sync.scheduler_cycles AS cycle USING (scheduler_cycle_id)
                WHERE cycle.state='dispatched'
                  AND result.state IN ('queued','running')
                  AND result.updated_at <= %s - (%s * interval '1 second')
                ORDER BY result.scheduler_source_result_id
                """,
                (now, stale_seconds),
            ).fetchall()
        return [dict(row) for row in rows]

    def bind_recovery_message(self, *, cycle_id: int, source_id: str, message_id: str) -> None:
        with self._connect() as conn, conn.transaction():
            row = conn.execute(
                """
                UPDATE sync.scheduler_source_results
                SET message_id=%s
                WHERE scheduler_cycle_id=%s AND source_id=%s AND state IN ('queued','running')
                RETURNING scheduler_source_result_id
                """,
                (message_id, cycle_id, source_id),
            ).fetchone()
            if row is None:
                raise SyncDatabaseError("scheduler_result_conflict", "recoverable scheduler result is unavailable")

    def last_source_activity(self) -> dict[str, dict[str, Any]]:
        with self._connect(autocommit=True) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (source_id) source_id, state, queued_at, started_at, finished_at,
                       sync_status, error_code
                FROM sync.scheduler_source_results
                ORDER BY source_id, scheduler_source_result_id DESC
                """
            ).fetchall()
        return {str(row["source_id"]): dict(row) for row in rows}

    def start_source(self, *, cycle_id: int, source_id: str) -> bool:
        with self._connect() as conn, conn.transaction():
            row = conn.execute(
                """
                UPDATE sync.scheduler_source_results
                SET state='running', started_at=COALESCE(started_at, now())
                WHERE scheduler_cycle_id=%s AND source_id=%s
                  AND state IN ('queued','running')
                RETURNING scheduler_source_result_id
                """,
                (cycle_id, source_id),
            ).fetchone()
            return row is not None

    def finish_source(self, *, cycle_id: int, result: SchedulerSourceResult) -> None:
        if result.state not in {"completed", "review_required", "failed"}:
            raise SyncDatabaseError("scheduler_result_invalid", "scheduler source result state is invalid")
        with self._connect() as conn, conn.transaction():
            cycle = conn.execute(
                "SELECT scheduler_cycle_id FROM sync.scheduler_cycles WHERE scheduler_cycle_id=%s FOR UPDATE",
                (cycle_id,),
            ).fetchone()
            if cycle is None:
                raise SyncDatabaseError("scheduler_cycle_conflict", "scheduler cycle is unavailable")
            updated = conn.execute(
                """
                UPDATE sync.scheduler_source_results
                SET state=%s, sync_status=%s, sync_run_id=%s, error_code=%s,
                    result_document=%s::jsonb, finished_at=now()
                WHERE scheduler_cycle_id=%s AND source_id=%s AND state='running'
                RETURNING scheduler_source_result_id
                """,
                (
                    result.state,
                    result.sync_status,
                    result.sync_run_id,
                    result.error_code,
                    _json(dict(result.result)),
                    cycle_id,
                    result.source_id,
                ),
            ).fetchone()
            if updated is None:
                raise SyncDatabaseError("scheduler_result_conflict", "scheduler source result is not running")
            counts = conn.execute(
                """
                SELECT count(*) FILTER (WHERE state='completed') AS completed,
                       count(*) FILTER (WHERE state='review_required') AS review_required,
                       count(*) FILTER (WHERE state='failed') AS failed,
                       count(*) FILTER (WHERE state IN ('queued','running')) AS pending
                FROM sync.scheduler_source_results WHERE scheduler_cycle_id=%s
                """,
                (cycle_id,),
            ).fetchone()
            if counts is None:
                raise SyncDatabaseError("scheduler_result_conflict", "scheduler cycle result counts are unavailable")
            pending = int(counts["pending"])
            failed = int(counts["failed"])
            review_required = int(counts["review_required"])
            state = "dispatched" if pending else "partial_failure" if failed or review_required else "completed"
            conn.execute(
                """
                UPDATE sync.scheduler_cycles
                SET state=%s, completed_count=%s, review_required_count=%s, failed_count=%s,
                    finished_at=CASE WHEN %s=0 THEN now() ELSE NULL END
                WHERE scheduler_cycle_id=%s
                """,
                (state, int(counts["completed"]), review_required, failed, pending, cycle_id),
            )

    def fail_source_dispatch(self, *, cycle_id: int, source_id: str, error_code: str) -> bool:
        with self._connect() as conn, conn.transaction():
            cycle = conn.execute(
                "SELECT scheduler_cycle_id FROM sync.scheduler_cycles WHERE scheduler_cycle_id=%s FOR UPDATE",
                (cycle_id,),
            ).fetchone()
            if cycle is None:
                raise SyncDatabaseError("scheduler_cycle_conflict", "scheduler cycle is unavailable")
            row = conn.execute(
                """
                UPDATE sync.scheduler_source_results
                SET state='failed', sync_status='failed', error_code=%s,
                    result_document=%s::jsonb, finished_at=now()
                WHERE scheduler_cycle_id=%s AND source_id=%s AND state='queued'
                  AND message_id IS NOT NULL
                RETURNING scheduler_source_result_id
                """,
                (error_code, _json({"error_code": error_code}), cycle_id, source_id),
            ).fetchone()
            return row is not None

    def finish_dispatch(self, *, cycle_id: int) -> None:
        with self._connect() as conn, conn.transaction():
            cycle = conn.execute(
                "SELECT scheduler_cycle_id FROM sync.scheduler_cycles WHERE scheduler_cycle_id=%s FOR UPDATE",
                (cycle_id,),
            ).fetchone()
            if cycle is None:
                raise SyncDatabaseError("scheduler_cycle_conflict", "scheduler cycle is unavailable")
            counts = conn.execute(
                """
                SELECT count(*) FILTER (WHERE state IN ('queued','running')) AS pending,
                       count(*) FILTER (WHERE state='failed') AS failed
                FROM sync.scheduler_source_results WHERE scheduler_cycle_id=%s
                """,
                (cycle_id,),
            ).fetchone()
            if counts is None:
                raise SyncDatabaseError("scheduler_cycle_conflict", "scheduler dispatch counts are unavailable")
            pending, failed = int(counts["pending"]), int(counts["failed"])
            state = "dispatched" if pending else "partial_failure" if failed else "completed"
            conn.execute(
                """
                UPDATE sync.scheduler_cycles
                SET state=%s, failed_count=%s,
                    finished_at=CASE WHEN %s=0 THEN now() ELSE NULL END
                WHERE scheduler_cycle_id=%s
                """,
                (state, failed, pending, cycle_id),
            )

    def snapshot(self) -> dict[str, Any]:
        with self._connect(autocommit=True) as conn:
            cycle = conn.execute("SELECT * FROM sync.scheduler_cycles ORDER BY scheduler_cycle_id DESC LIMIT 1").fetchone()
            results = []
            if cycle:
                results = conn.execute(
                    "SELECT * FROM sync.scheduler_source_results WHERE scheduler_cycle_id=%s ORDER BY source_id",
                    (cycle["scheduler_cycle_id"],),
                ).fetchall()
            runs = conn.execute(
                """
                SELECT DISTINCT ON (source_id) source_id, state, reason_code, error_code, updated_at,
                       candidate_revision_sha, metrics, diff_document, result_document
                FROM sync.source_sync_runs
                ORDER BY source_id, updated_at DESC, sync_run_id DESC
                """
            ).fetchall()
            open_alerts = conn.execute(
                "SELECT * FROM sync.alert_deliveries WHERE state='open' ORDER BY severity DESC, last_seen_at DESC"
            ).fetchall()
        return {
            "cycle": dict(cycle) if cycle else None,
            "source_results": [dict(row) for row in results],
            "latest_sync_runs": [dict(row) for row in runs],
            "open_alerts": [dict(row) for row in open_alerts],
        }

    def observe_alerts(self, alerts: Iterable[Mapping[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
        observed = [dict(item) for item in alerts]
        fingerprints = {str(item["fingerprint"]) for item in observed}
        notifications: list[dict[str, Any]] = []
        with self._connect() as conn, conn.transaction():
            for item in observed:
                row = conn.execute(
                    """
                    INSERT INTO sync.alert_deliveries
                      (fingerprint, alert_code, severity, subject_key, state, first_seen_at, last_seen_at, details)
                    VALUES (%s, %s, %s, %s, 'open', %s, %s, %s::jsonb)
                    ON CONFLICT (fingerprint) DO UPDATE
                    SET state='open',
                        first_seen_at=CASE WHEN sync.alert_deliveries.state='resolved' THEN EXCLUDED.first_seen_at ELSE sync.alert_deliveries.first_seen_at END,
                        last_seen_at=EXCLUDED.last_seen_at,
                        last_notified_at=CASE WHEN sync.alert_deliveries.state='resolved' THEN NULL ELSE sync.alert_deliveries.last_notified_at END,
                        severity=EXCLUDED.severity,
                        details=EXCLUDED.details
                    RETURNING *, (last_notified_at IS NULL) AS should_notify
                    """,
                    (
                        item["fingerprint"], item["alert_code"], item["severity"], item["subject_key"],
                        now, now, _json(item["details"]),
                    ),
                ).fetchone()
                if row and row["should_notify"]:
                    notifications.append(dict(item))
            rows = conn.execute("SELECT alert_delivery_id, fingerprint FROM sync.alert_deliveries WHERE state='open'").fetchall()
            for row in rows:
                if str(row["fingerprint"]) not in fingerprints:
                    conn.execute(
                        """
                        UPDATE sync.alert_deliveries SET state='resolved', last_seen_at=%s
                        WHERE alert_delivery_id=%s
                        """,
                        (now, row["alert_delivery_id"]),
                    )
        return notifications

    def mark_notified(self, *, fingerprints: Iterable[str], now: datetime) -> None:
        values = sorted(set(fingerprints))
        if not values:
            return
        with self._connect() as conn, conn.transaction():
            conn.execute(
                """
                UPDATE sync.alert_deliveries
                SET last_notified_at=%s, notification_count=notification_count+1
                WHERE state='open' AND fingerprint=ANY(%s)
                """,
                (now, values),
            )
