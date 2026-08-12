"""Static and live acceptance for scheduler durability and liveness controls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sync.database import SyncDatabaseSettings
from sync.operations import OperationsDatabase, SchedulerSourceResult


class ValidationFailure(RuntimeError):
    pass


def _static_checks() -> dict[str, Any]:
    heartbeat = (REPO_ROOT / "migrations" / "0008_scheduler_heartbeat.sql").read_text(encoding="utf-8")
    operations = (REPO_ROOT / "sync" / "operations.py").read_text(encoding="utf-8")
    scheduler = (REPO_ROOT / "sync" / "scheduler.py").read_text(encoding="utf-8")
    monitor = (REPO_ROOT / "sync" / "monitor.py").read_text(encoding="utf-8")
    required = {
        "heartbeat_table": "CREATE TABLE IF NOT EXISTS sync.scheduler_runtime" in heartbeat,
        "heartbeat_upsert": "INSERT INTO sync.scheduler_runtime" in operations,
        "dispatch_race_binding": "message_id IS NULL OR message_id=%s" in operations,
        "dispatch_state_fence": "cycle_state if pending and cycle_state == \"dispatching\"" in operations,
        "active_work_projection": '"active_source_results"' in operations,
        "scheduler_heartbeat": 'database.heartbeat(status="starting"' in scheduler,
        "heartbeat_monitor": 'snapshot.get("scheduler_runtime")' in monitor,
    }
    missing = sorted(name for name, present in required.items() if not present)
    if missing:
        raise ValidationFailure(f"operations runtime controls are missing: {', '.join(missing)}")
    return required


def _live_checks(database_url: str) -> dict[str, Any]:
    database = OperationsDatabase(SyncDatabaseSettings(database_url))
    database.assert_migrated()
    now = datetime.now(timezone.utc)
    marker = f"operations-validator-{now.strftime('%Y%m%d%H%M%S%f')}"
    with database._connect(autocommit=True) as conn:  # noqa: SLF001 - live acceptance owns a disposable database
        row = conn.execute(
            """
            SELECT (SELECT count(*) FROM sync.scheduler_cycles) AS cycles,
                   (SELECT count(*) FROM sync.scheduler_source_results) AS results,
                   (SELECT count(*) FROM sync.scheduler_runtime) AS runtime
            """
        ).fetchone()
    if row is None or any(int(row[name]) != 0 for name in ("cycles", "results", "runtime")):
        raise ValidationFailure("live operations validation requires empty disposable operational tables")
    cycle_id: int | None = None
    try:
        cycle = database.begin_cycle(cycle_key=marker, registry_sha256="a" * 64, source_ids=["validator-a", "validator-b"])
        cycle_id = int(cycle["scheduler_cycle_id"])

        # Simulate a worker that starts and finishes before the scheduler binds
        # its queue message. Another pending row must keep recovery visible.
        if not database.start_source(cycle_id=cycle_id, source_id="validator-a"):
            raise ValidationFailure("validator worker could not start")
        database.finish_source(
            cycle_id=cycle_id,
            result=SchedulerSourceResult(
                source_id="validator-a", state="completed", sync_status="completed", sync_run_id=None,
                error_code=None, result={"validator": True},
            ),
        )
        database.bind_message(cycle_id=cycle_id, source_id="validator-a", message_id="validator-message-a")
        incomplete = database.incomplete_dispatch()
        if incomplete is None or int(incomplete["cycle"]["scheduler_cycle_id"]) != cycle_id:
            raise ValidationFailure("dispatching cycle was lost during worker-first ordering")
        if incomplete["source_ids"] != ["validator-b"]:
            raise ValidationFailure("unfinished dispatch ledger is not exact")

        database.bind_message(cycle_id=cycle_id, source_id="validator-b", message_id="validator-message-b")
        if not database.start_source(cycle_id=cycle_id, source_id="validator-b"):
            raise ValidationFailure("second validator worker could not start")
        database.finish_source(
            cycle_id=cycle_id,
            result=SchedulerSourceResult(
                source_id="validator-b", state="review_required", sync_status="review_required", sync_run_id=None,
                error_code=None, result={"validator": True},
            ),
        )
        database.finish_dispatch(cycle_id=cycle_id)
        heartbeat_at = now - timedelta(seconds=1)
        database.heartbeat(status="idle", observed_at=heartbeat_at, details={"validator": True})
        snapshot = database.snapshot()
        latest = snapshot.get("cycle")
        runtime = snapshot.get("scheduler_runtime")
        if not isinstance(latest, dict) or int(latest["scheduler_cycle_id"]) != cycle_id:
            raise ValidationFailure("validator cycle is not the latest durable cycle")
        expected_counts = {"state": "partial_failure", "completed_count": 1, "review_required_count": 1, "failed_count": 0}
        if any(latest.get(key) != value for key, value in expected_counts.items()):
            raise ValidationFailure("terminal cycle counts do not match worker results")
        if any(int(row["scheduler_cycle_id"]) == cycle_id for row in snapshot.get("active_source_results", [])):
            raise ValidationFailure("terminal validator cycle left active work")
        if not isinstance(runtime, dict) or runtime.get("last_status") != "idle" or runtime.get("details") != {"validator": True}:
            raise ValidationFailure("scheduler heartbeat did not persist exactly")
        return {"scheduler_cycle_id": cycle_id, **expected_counts, "heartbeat_status": runtime["last_status"]}
    finally:
        with database._connect() as conn, conn.transaction():  # noqa: SLF001 - remove validator-owned disposable facts
            if cycle_id is not None:
                conn.execute("DELETE FROM sync.scheduler_cycles WHERE scheduler_cycle_id=%s", (cycle_id,))
            conn.execute(
                "DELETE FROM sync.scheduler_runtime WHERE runtime_key='primary' AND details=%s::jsonb",
                (json.dumps({"validator": True}, sort_keys=True),),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("SYNC_DATABASE_URL"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result: dict[str, Any] = {"status": "passed", "static": _static_checks()}
        if args.database_url:
            result["live"] = _live_checks(args.database_url)
        else:
            result["live"] = "not_requested"
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(result["error"], file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True) if args.json else "operations runtime validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
