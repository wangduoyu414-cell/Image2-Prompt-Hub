"""Registry-driven Dramatiq dispatch and source-isolated workers."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dramatiq
from dramatiq.errors import Retry
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from opentelemetry import trace
import sentry_sdk

from apps.observability import configure_observability
from .operations import OperationsDatabase, SchedulerSourceResult, scheduler_cycle_key
from .pipeline import SyncPipelineError, SyncSettings, run_source
from .database import SyncDatabaseError, SyncDatabaseSettings
from .schedule_policy import AUDIT, REGISTRY, due_source_ids


def _log(event: str, **facts: object) -> None:
    payload = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **facts}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SyncPipelineError("scheduler_config_missing", f"{name} is required")
    return value


def _int_environment(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SyncPipelineError("scheduler_config_invalid", f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SyncPipelineError("scheduler_config_invalid", f"{name} is outside its supported range")
    return value


def _settings() -> SyncSettings:
    return SyncSettings(
        database_url=_required("SYNC_DATABASE_URL"),
        s3_endpoint_url=_required("SYNC_S3_ENDPOINT_URL"),
        s3_bucket=_required("SYNC_S3_BUCKET"),
        s3_access_key_id=_required("SYNC_S3_ACCESS_KEY_ID"),
        s3_secret_access_key=_required("SYNC_S3_SECRET_ACCESS_KEY"),
        git_data_root=Path(_required("SYNC_GIT_DATA_ROOT")),
        package_root=Path(_required("SYNC_PACKAGE_ROOT")),
        evidence_root=Path(_required("SYNC_EVIDENCE_ROOT")),
        s3_region=os.environ.get("SYNC_S3_REGION", "us-east-1"),
    )


def _operations() -> OperationsDatabase:
    return OperationsDatabase(SyncDatabaseSettings(_required("SYNC_DATABASE_URL")))


def _broker() -> RedisBroker | StubBroker:
    url = os.environ.get("SYNC_REDIS_URL", "").strip()
    broker = RedisBroker(url=url) if url else StubBroker()
    dramatiq.set_broker(broker)
    return broker


BROKER = _broker()


@dramatiq.actor(
    queue_name="source-sync",
    max_retries=20,
    min_backoff=15_000,
    max_backoff=300_000,
    time_limit=4 * 60 * 60 * 1000,
)
def run_registered_source(cycle_id: int, source_id: str) -> None:
    configure_observability("image2-sync-worker")
    database = _operations()
    with database.source_lock(source_id) as acquired:
        if not acquired:
            _log("scheduler_source_deferred", cycle_id=cycle_id, source_id=source_id, reason="source_locked")
            raise Retry(message="another worker owns this source", delay=30_000)
            return
        if not database.start_source(cycle_id=cycle_id, source_id=source_id):
            _log("scheduler_source_skipped", cycle_id=cycle_id, source_id=source_id, reason="not_queued_or_stale")
            return
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("sync.run_source") as span:
            span.set_attribute("image2.source_id", source_id)
            try:
                result = run_source(registry_path=REGISTRY, audit_path=AUDIT, source_id=source_id, settings=_settings())
                terminal = "review_required" if result.status == "review_required" else "completed"
                database.finish_source(
                    cycle_id=cycle_id,
                    result=SchedulerSourceResult(
                        source_id=source_id,
                        state=terminal,
                        sync_status=result.status,
                        sync_run_id=result.sync_run_id,
                        error_code=result.error_code,
                        result=result.as_json(),
                    ),
                )
                _log("scheduler_source_finished", cycle_id=cycle_id, source_id=source_id, status=result.status)
            except Exception as exc:
                try:
                    code = getattr(exc, "error_code", "sync_failed")
                    database.finish_source(
                        cycle_id=cycle_id,
                        result=SchedulerSourceResult(
                            source_id=source_id,
                            state="failed",
                            sync_status="failed",
                            sync_run_id=None,
                            error_code=str(code),
                            result={"error_code": str(code)},
                        ),
                    )
                    sentry_sdk.capture_exception(exc)
                    _log("scheduler_source_failed", cycle_id=cycle_id, source_id=source_id, error_code=str(code))
                except Exception as persistence_error:
                    sentry_sdk.capture_exception(persistence_error)
                    _log(
                        "scheduler_source_result_persist_failed",
                        cycle_id=cycle_id,
                        source_id=source_id,
                        error_code=getattr(persistence_error, "error_code", "operations_write_failed"),
                    )
                    raise Retry(message="source terminal result was not persisted", delay=60_000) from persistence_error


def dispatch_cycle(*, now: datetime | None = None, emit_log: bool = False) -> dict[str, Any]:
    started_at = now or datetime.now(timezone.utc)
    database = _operations()
    database.assert_migrated()
    with database.scheduler_lock() as acquired:
        if not acquired:
            return {"status": "busy", "scheduler_cycle_id": None, "source_ids": [], "failed_source_ids": []}
        incomplete = database.incomplete_dispatch()
        if incomplete is not None:
            cycle = incomplete["cycle"]
            source_ids = list(incomplete["source_ids"])
            cycle_id = int(cycle["scheduler_cycle_id"])
            status = "recovering"
        else:
            source_ids = due_source_ids(now=started_at, database=database)
            if not source_ids:
                result = {"status": "idle", "scheduler_cycle_id": None, "source_ids": [], "failed_source_ids": []}
                if emit_log:
                    _log("scheduler_cycle_idle", **result)
                return result
            registry_sha256 = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
            key = scheduler_cycle_key(registry_sha256, started_at)
            cycle = database.begin_cycle(cycle_key=key, registry_sha256=registry_sha256, source_ids=source_ids)
            cycle_id = int(cycle["scheduler_cycle_id"])
            if str(cycle["state"]) != "dispatching":
                return {"status": "existing", "scheduler_cycle_id": cycle_id, "source_ids": source_ids}
            status = "dispatching"
        if isinstance(BROKER, StubBroker):
            raise SyncPipelineError("scheduler_config_missing", "SYNC_REDIS_URL is required to dispatch due sources")
        failed_source_ids: list[str] = []
        cycle_source_ids = [str(item) for item in cycle["eligible_source_ids"]]
        for source_id in source_ids:
            try:
                message = run_registered_source.send(cycle_id, source_id)
                database.bind_message(cycle_id=cycle_id, source_id=source_id, message_id=str(message.message_id))
            except Exception as exc:
                if database.fail_source_dispatch(cycle_id=cycle_id, source_id=source_id, error_code="scheduler_dispatch_failed"):
                    failed_source_ids.append(source_id)
                sentry_sdk.capture_exception(exc)
                _log("scheduler_source_dispatch_failed", cycle_id=cycle_id, source_id=source_id)
        remaining_incomplete = database.incomplete_dispatch()
        if remaining_incomplete is not None and int(remaining_incomplete["cycle"]["scheduler_cycle_id"]) == cycle_id:
            undispatched = list(remaining_incomplete["source_ids"])
            if undispatched:
                result = {
                    "status": "recovering",
                    "scheduler_cycle_id": cycle_id,
                    "source_ids": cycle_source_ids,
                    "failed_source_ids": failed_source_ids,
                    "undispatched_source_ids": undispatched,
                }
                if emit_log:
                    _log("scheduler_cycle_recovery_pending", **result)
                return result
        database.finish_dispatch(cycle_id=cycle_id)
        result_status = "partial_failure" if failed_source_ids else "recovered" if status == "recovering" else "dispatched"
        result = {"status": result_status, "scheduler_cycle_id": cycle_id, "source_ids": cycle_source_ids, "failed_source_ids": failed_source_ids}
        if emit_log:
            _log("scheduler_cycle_dispatched", **result)
        return result


def recover_stale_messages(*, now: datetime | None = None, emit_log: bool = False) -> dict[str, Any]:
    observed_at = now or datetime.now(timezone.utc)
    database = _operations()
    database.assert_migrated()
    if isinstance(BROKER, StubBroker):
        raise SyncPipelineError("scheduler_config_missing", "SYNC_REDIS_URL is required to recover stale source messages")
    stale_seconds = _int_environment("SYNC_MESSAGE_STALE_SECONDS", 5 * 60 * 60, minimum=4 * 60 * 60, maximum=7 * 24 * 60 * 60)
    recovered: list[dict[str, Any]] = []
    with database.scheduler_lock() as acquired:
        if not acquired:
            return {"status": "busy", "recovered": []}
        for row in database.stale_source_results(now=observed_at, stale_seconds=stale_seconds):
            cycle_id, source_id = int(row["scheduler_cycle_id"]), str(row["source_id"])
            message = run_registered_source.send(cycle_id, source_id)
            database.bind_recovery_message(cycle_id=cycle_id, source_id=source_id, message_id=str(message.message_id))
            recovered.append({"scheduler_cycle_id": cycle_id, "source_id": source_id, "previous_state": row["state"]})
    result = {"status": "recovered" if recovered else "idle", "recovered": recovered}
    if emit_log:
        _log("scheduler_messages_recovered", **result)
    return result


def run_forever() -> None:
    _required("SYNC_REDIS_URL")
    configure_observability("image2-sync-scheduler")
    interval = _int_environment("SYNC_INTERVAL_SECONDS", 6 * 60 * 60, minimum=300, maximum=7 * 24 * 60 * 60)
    jitter = _int_environment("SYNC_JITTER_SECONDS", 15 * 60, minimum=0, maximum=60 * 60)
    backoff = 60
    while True:
        try:
            recover_stale_messages(emit_log=True)
            dispatch_cycle(emit_log=True)
            backoff = 60
            delay = interval + random.SystemRandom().randint(0, jitter)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            _log("scheduler_cycle_failed", error_code=getattr(exc, "error_code", "scheduler_failed"))
            delay = min(backoff, 30 * 60)
            backoff = min(backoff * 2, 30 * 60)
        time.sleep(delay)
