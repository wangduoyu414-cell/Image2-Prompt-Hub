"""Bounded operational status projection for authenticated administration."""

from __future__ import annotations

import hashlib
import json
import psycopg
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from .database import SyncDatabaseSettings
from .operations import OperationsDatabase
from .schedule_policy import REGISTRY, eligible_source_ids


def _review_queue_summary(database_url: str) -> dict[str, Any]:
    from content.database import ContentDatabaseSettings
    from content.review_store import RightsReviewStore

    store = RightsReviewStore(ContentDatabaseSettings(database_url))
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (project.source_id) project.source_id, revision.revision_sha
            FROM inventory.source_adapter_runs AS run
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id=run.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
            WHERE run.state='ready'
            ORDER BY project.source_id, run.source_adapter_run_id DESC
            """
        ).fetchall()
    selected = {str(row["source_id"]): str(row["revision_sha"]) for row in rows}
    if not selected:
        return {
            "subject_count": 0,
            "output_count": 0,
            "state_counts": {name: 0 for name in ("pending", "review_required", "publishable", "internal_only", "blocked")},
        }
    queue = store.list_queue(revision_selection=selected, limit=1, offset=0)
    return {
        "subject_count": queue["subject_count"],
        "output_count": queue["output_count"],
        "state_counts": queue["state_counts"],
    }


def operations_status(*, database_url: str, registry_path: Path = REGISTRY) -> dict[str, Any]:
    database = OperationsDatabase(SyncDatabaseSettings(database_url))
    database.assert_migrated()
    snapshot = database.snapshot()
    latest_runs = {str(row.get("source_id")): row for row in snapshot["latest_sync_runs"]}
    latest_results = database.last_source_activity()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    sources: list[dict[str, Any]] = []
    for row in sorted(payload.get("sources", []), key=lambda item: str(item.get("source_id"))):
        source_id = str(row.get("source_id", ""))
        ingestion = row.get("ingestion") if isinstance(row.get("ingestion"), dict) else {}
        sync = row.get("sync") if isinstance(row.get("sync"), dict) else {}
        run = latest_runs.get(source_id, {})
        activity = latest_results.get(source_id, {})
        repository = row.get("repository") if isinstance(row.get("repository"), dict) else {}
        sources.append(
            {
                "source_id": source_id,
                "status": row.get("status"),
                "ingestion_mode": ingestion.get("mode"),
                "sync_enabled": sync.get("enabled"),
                "cadence_seconds": sync.get("cadence_seconds"),
                "jitter_seconds": sync.get("jitter_seconds"),
                "registered_revision_sha": repository.get("verified_commit_sha"),
                "latest_candidate_revision_sha": run.get("candidate_revision_sha"),
                "latest_sync_state": run.get("state"),
                "latest_sync_reason_code": run.get("reason_code"),
                "latest_sync_error_code": run.get("error_code"),
                "latest_sync_updated_at": run.get("updated_at"),
                "latest_scheduler_state": activity.get("state"),
                "latest_scheduler_finished_at": activity.get("finished_at"),
                "eligible": source_id in eligible_source_ids(registry_path),
            }
        )
    cycle = snapshot.get("cycle")
    if isinstance(cycle, dict):
        cycle = {
            key: cycle.get(key)
            for key in (
                "scheduler_cycle_id", "cycle_key", "state", "source_count", "queued_count",
                "completed_count", "review_required_count", "failed_count", "started_at", "finished_at", "updated_at",
            )
        }
    alerts = [
        {
            "alert_code": item.get("alert_code"),
            "severity": item.get("severity"),
            "subject_key": item.get("subject_key"),
            "first_seen_at": item.get("first_seen_at"),
            "last_seen_at": item.get("last_seen_at"),
            "notification_count": item.get("notification_count"),
            "details": item.get("details"),
        }
        for item in snapshot.get("open_alerts", [])
    ]
    return {
        "status": "ready",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "eligible_source_count": len(eligible_source_ids(registry_path)),
        "sources": sources,
        "latest_cycle": cycle,
        "open_alerts": alerts,
        "review_queue": _review_queue_summary(database_url),
    }
