from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.source_lifecycle import transition_document
from scripts.validate_source_registry import load_json, validate_documents
from apps.observability import JsonLogFormatter, configure_observability
from sync.database import SyncDatabaseError
from sync.pipeline import SyncPipelineError
from sync.monitor import collect_alerts
from sync.operations import OperationsDatabase, alert_fingerprint, scheduler_cycle_key
from sync.schedule_policy import due_source_ids, eligible_source_ids
from sync import scheduler


REPO_ROOT = Path(__file__).resolve().parents[2]


class ActivityDatabase:
    def __init__(self, rows: dict[str, dict[str, object]]) -> None:
        self.rows = rows

    def last_source_activity(self) -> dict[str, dict[str, object]]:
        return self.rows


def test_scheduler_only_selects_six_continuous_sources_and_excludes_chaos() -> None:
    ids = eligible_source_ids(REPO_ROOT / "config" / "sources-v2.yaml")
    assert len(ids) == 6
    assert "chaosrealmsai-gpt-image-2-gallery" not in ids


def test_due_policy_honors_per_source_cadence_and_failure_retry() -> None:
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    ids = eligible_source_ids(REPO_ROOT / "config" / "sources-v2.yaml")
    rows = {source_id: {"state": "completed", "finished_at": now - timedelta(hours=7)} for source_id in ids}
    due = due_source_ids(now=now, registry_path=REPO_ROOT / "config" / "sources-v2.yaml", database=ActivityDatabase(rows))  # type: ignore[arg-type]
    assert due == ["g0dam-work-prompts"]
    rows["joesai-commercial-prompts"] = {"state": "failed", "finished_at": now - timedelta(minutes=31)}
    assert "joesai-commercial-prompts" in due_source_ids(now=now, registry_path=REPO_ROOT / "config" / "sources-v2.yaml", database=ActivityDatabase(rows))  # type: ignore[arg-type]
    rows["g0dam-work-prompts"] = {"state": "running", "started_at": now - timedelta(days=1)}
    assert "g0dam-work-prompts" not in due_source_ids(now=now, registry_path=REPO_ROOT / "config" / "sources-v2.yaml", database=ActivityDatabase(rows))  # type: ignore[arg-type]


def test_cycle_and_alert_fingerprints_are_stable_and_time_requires_timezone() -> None:
    now = datetime(2026, 8, 12, 1, 2, tzinfo=timezone.utc)
    assert scheduler_cycle_key("a" * 64, now) == scheduler_cycle_key("a" * 64, now.replace(second=59))
    assert alert_fingerprint("failed", "source") == alert_fingerprint("failed", "source")
    assert alert_fingerprint("failed", "source") != alert_fingerprint("failed", "other")
    with pytest.raises(SyncDatabaseError):
        scheduler_cycle_key("a" * 64, datetime(2026, 8, 12))
    with pytest.raises(SyncPipelineError, match="timezone"):
        due_source_ids(
            now=datetime(2026, 8, 12),
            registry_path=REPO_ROOT / "config" / "sources-v2.yaml",
            database=ActivityDatabase({}),  # type: ignore[arg-type]
        )


def test_monitor_reports_scheduler_source_and_stuck_worker_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    monkeypatch.setenv("MONITOR_SYNC_STALE_SECONDS", "3600")
    monkeypatch.setattr("sync.monitor._json_request", lambda url: {"status": "ready"} if url.endswith("readyz") else {"state": "no_current", "case_count": 0})
    monkeypatch.setattr("sync.monitor.eligible_source_ids", lambda: ["source-a", "source-b"])
    alerts, http = collect_alerts(
        {
            "cycle": {"cycle_key": "cycle", "state": "partial_failure", "updated_at": now - timedelta(hours=2)},
            "source_results": [{"source_id": "source-a", "state": "running", "started_at": now - timedelta(hours=5)}],
            "latest_sync_runs": [{"source_id": "source-a", "state": "failed", "error_code": "git_failed"}],
        },
        now=now,
        public_origin="https://example.com",
    )
    codes = {item["alert_code"] for item in alerts}
    assert {"scheduler_stale", "scheduler_cycle_failed", "source_worker_stuck", "source_sync_failed", "source_never_synced"} <= codes
    assert http["publication"]["state"] == "no_current"


def test_monitor_distinguishes_count_drop_and_public_asset_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    monkeypatch.setattr("sync.monitor.eligible_source_ids", lambda: ["source-a"])
    monkeypatch.setattr(
        "sync.monitor._json_request",
        lambda url: {"status": "ready"} if url.endswith("readyz") else
        {"state": "active", "case_count": 1} if url.endswith("publication") else
        {"cases": [{"primary_output": {"content_sha256": "a" * 64}}]},
    )
    monkeypatch.setattr("sync.monitor._asset_request", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("unavailable")))
    alerts, _ = collect_alerts(
        {
            "cycle": {"cycle_key": "cycle", "state": "completed", "updated_at": now},
            "source_results": [],
            "latest_sync_runs": [{
                "source_id": "source-a",
                "state": "review_required",
                "reason_code": "quality_gate",
                "result_document": {"quality_gate": {"reasons": ["case_count_decrease"]}},
            }],
        },
        now=now,
        public_origin="https://example.com",
    )
    assert {item["alert_code"] for item in alerts} == {"public_asset_invalid", "source_count_drop"}


def test_lifecycle_transitions_pause_and_reactivate_only_continuous_sources() -> None:
    registry = json.loads((REPO_ROOT / "config" / "sources-v2.yaml").read_text(encoding="utf-8"))
    paused, receipt = transition_document(registry, source_id="g0dam-work-prompts", target="paused")
    source = next(item for item in paused["sources"] if item["source_id"] == "g0dam-work-prompts")
    assert receipt["from_status"] == "active" and source["sync"]["enabled"] is False
    active, _ = transition_document(paused, source_id="g0dam-work-prompts", target="active")
    source = next(item for item in active["sources"] if item["source_id"] == "g0dam-work-prompts")
    assert source["sync"]["enabled"] is True
    chaos_paused, _ = transition_document(registry, source_id="chaosrealmsai-gpt-image-2-gallery", target="paused")
    chaos = next(item for item in chaos_paused["sources"] if item["source_id"] == "chaosrealmsai-gpt-image-2-gallery")
    assert chaos["sync"]["enabled"] is False
    chaos_active, _ = transition_document(chaos_paused, source_id="chaosrealmsai-gpt-image-2-gallery", target="active")
    chaos = next(item for item in chaos_active["sources"] if item["source_id"] == "chaosrealmsai-gpt-image-2-gallery")
    assert chaos["sync"]["enabled"] is False
    audit = load_json(REPO_ROOT / "reports" / "source-audit-v2.json")
    schemas = (
        load_json(REPO_ROOT / "schemas" / "source-audit-v2.schema.json"),
        load_json(REPO_ROOT / "schemas" / "source-registry-v2.schema.json"),
    )
    assert validate_documents(audit, paused, *schemas)["ok"]


def test_operations_migration_defines_durable_cycles_results_and_alerts() -> None:
    sql = (REPO_ROOT / "migrations" / "0007_operations_runtime.sql").read_text(encoding="utf-8")
    for table in ("sync.scheduler_cycles", "sync.scheduler_source_results", "sync.alert_deliveries"):
        assert table in sql
    assert "UNIQUE (scheduler_cycle_id, source_id)" in sql
    assert "UNIQUE (fingerprint)" in sql


def test_alert_recurrence_reopens_the_same_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    rows: dict[str, dict[str, object]] = {}
    class Cursor:
        def __init__(self, row: dict[str, object] | None = None, many: list[dict[str, object]] | None = None) -> None:
            self.row = row
            self.many = many or []

        def fetchone(self) -> dict[str, object] | None:
            return self.row

        def fetchall(self) -> list[dict[str, object]]:
            return self.many

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def transaction(self): return self
        def execute(self, sql: str, parameters=()):
            if "INSERT INTO sync.alert_deliveries" in sql:
                fingerprint = str(parameters[0])
                previous = rows.get(fingerprint)
                should_notify = previous is None or previous["state"] == "resolved"
                rows[fingerprint] = {"fingerprint": fingerprint, "state": "open", "should_notify": should_notify}
                return Cursor(rows[fingerprint])
            if "SELECT alert_delivery_id" in sql:
                return Cursor(many=[{"alert_delivery_id": index + 1, "fingerprint": key} for index, key in enumerate(rows)])
            if "UPDATE sync.alert_deliveries SET state='resolved'" in sql:
                fingerprint = list(rows)[int(parameters[1]) - 1]
                rows[fingerprint]["state"] = "resolved"
            return Cursor()

    database = object.__new__(OperationsDatabase)
    monkeypatch.setattr(database, "_connect", lambda **_: Connection())
    fingerprint = alert_fingerprint("source_failed", "source-a")
    alert = {"fingerprint": fingerprint, "alert_code": "source_failed", "severity": "critical", "subject_key": "source-a", "details": {}}
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    assert database.observe_alerts([alert], now=now) == [alert]
    assert database.observe_alerts([alert], now=now) == []
    database.observe_alerts([], now=now)
    assert database.observe_alerts([alert], now=now) == [alert]


def test_dispatch_cycle_is_idle_without_writing_or_broker_use(monkeypatch: pytest.MonkeyPatch) -> None:
    class Database:
        migrated = False

        def assert_migrated(self) -> None:
            self.migrated = True

        def scheduler_lock(self):
            class Lock:
                def __enter__(self): return True
                def __exit__(self, *_args): return False
            return Lock()

        def incomplete_dispatch(self): return None

    monkeypatch.setattr(scheduler, "due_source_ids", lambda **_: [])
    database = Database()
    monkeypatch.setattr(scheduler, "_operations", lambda: database)
    assert scheduler.dispatch_cycle(now=datetime(2026, 8, 12, tzinfo=timezone.utc))["status"] == "idle"
    assert database.migrated is True


def test_dispatch_cycle_recovers_an_incomplete_ledger_before_computing_new_due_work(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[int, str]] = []
    bound: list[tuple[int, str, str]] = []

    class Message:
        message_id = "message-1"

    class Actor:
        @staticmethod
        def send(cycle_id: int, source_id: str) -> Message:
            sent.append((cycle_id, source_id))
            return Message()

    class Database:
        remaining = True
        def assert_migrated(self): pass
        def scheduler_lock(self):
            class Lock:
                def __enter__(self): return True
                def __exit__(self, *_args): return False
            return Lock()
        def incomplete_dispatch(self):
            if self.remaining:
                return {"cycle": {"scheduler_cycle_id": 9, "eligible_source_ids": ["source-a"]}, "source_ids": ["source-a"]}
            return None
        def bind_message(self, *, cycle_id: int, source_id: str, message_id: str):
            bound.append((cycle_id, source_id, message_id)); self.remaining = False
        def fail_source_dispatch(self, **_kwargs): return False
        def finish_dispatch(self, *, cycle_id: int): assert cycle_id == 9

    database = Database()
    monkeypatch.setattr(scheduler, "_operations", lambda: database)
    monkeypatch.setattr(scheduler, "BROKER", object())
    monkeypatch.setattr(scheduler, "run_registered_source", Actor())
    monkeypatch.setattr(scheduler, "due_source_ids", lambda **_: pytest.fail("new cadence must not run before recovery"))
    result = scheduler.dispatch_cycle(now=datetime(2026, 8, 12, tzinfo=timezone.utc))
    assert result["status"] == "recovered"
    assert sent == [(9, "source-a")]
    assert bound == [(9, "source-a", "message-1")]


def test_worker_retries_when_terminal_failure_cannot_be_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    class Database:
        def source_lock(self, _source_id: str):
            class Lock:
                def __enter__(self): return True
                def __exit__(self, *_args): return False
            return Lock()
        def start_source(self, **_kwargs): return True
        def finish_source(self, **_kwargs): raise SyncDatabaseError("operations_database_unavailable", "down")

    monkeypatch.setattr(scheduler, "_operations", lambda: Database())
    monkeypatch.setattr(scheduler, "_settings", lambda: object())
    monkeypatch.setattr(scheduler, "run_source", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("sync failed")))
    monkeypatch.setattr(scheduler, "configure_observability", lambda *_args, **_kwargs: None)
    with pytest.raises(scheduler.Retry, match="not persisted"):
        scheduler.run_registered_source.fn(7, "source-a")


def test_observability_rejects_credentialed_otlp_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://user:secret@example.com")
    with pytest.raises(ValueError, match="without credentials"):
        configure_observability("test-service")
    assert '"message": "hello"' in JsonLogFormatter().format(__import__("logging").LogRecord("test", 20, "", 1, "hello", (), None))


def test_observability_does_not_instrument_without_an_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    import apps.observability as observability

    class State:
        pass

    class App:
        state = State()

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_CONSOLE_EXPORTER", raising=False)
    monkeypatch.setattr(observability, "_CONFIGURED", False)
    monkeypatch.setattr(
        observability.FastAPIInstrumentor,
        "instrument_app",
        lambda *_args, **_kwargs: pytest.fail("must not instrument"),
    )
    observability.configure_observability("test-service", app=App())  # type: ignore[arg-type]
