"""Pure registry/cadence policy shared by scheduler, monitor, and admin."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ingestion.registry import load_source_config

from .operations import OperationsDatabase
from .pipeline import SyncPipelineError


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY = REPO_ROOT / "config" / "sources-v2.yaml"
AUDIT = REPO_ROOT / "reports" / "source-audit-v2.json"


def eligible_source_ids(registry_path: Path = REGISTRY) -> list[str]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncPipelineError("scheduler_registry_invalid", "source registry cannot be read") from exc
    rows = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SyncPipelineError("scheduler_registry_invalid", "source registry has no sources array")
    result: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = row.get("source_id")
        ingestion = row.get("ingestion")
        sync = row.get("sync")
        if (
            row.get("status") == "active"
            and isinstance(source_id, str)
            and isinstance(ingestion, dict)
            and ingestion.get("mode") == "continuous"
            and ingestion.get("one_shot_import_only") is False
            and isinstance(sync, dict)
            and sync.get("enabled") is True
        ):
            load_source_config(registry_path, source_id)
            result.append(source_id)
    if len(result) != len(set(result)):
        raise SyncPipelineError("scheduler_registry_invalid", "eligible source ids are not unique")
    return sorted(result)


def due_source_ids(*, now: datetime, registry_path: Path = REGISTRY, database: OperationsDatabase) -> list[str]:
    if now.tzinfo is None:
        raise SyncPipelineError("scheduler_time_invalid", "scheduler time must include a timezone")
    latest = database.last_source_activity()
    result: list[str] = []
    for source_id in eligible_source_ids(registry_path):
        config = load_source_config(registry_path, source_id)
        row = latest.get(source_id)
        if row is None:
            result.append(source_id)
            continue
        reference = row.get("finished_at") or row.get("started_at") or row.get("queued_at")
        if not isinstance(reference, datetime):
            result.append(source_id)
            continue
        if reference.tzinfo is None:
            raise SyncPipelineError("scheduler_time_invalid", "stored scheduler activity must include a timezone")
        cadence = config.sync_cadence_seconds
        state = str(row.get("state"))
        if state == "failed":
            cadence = min(cadence, 30 * 60)
        elif state in {"queued", "running"}:
            continue
        elif config.sync_jitter_seconds:
            payload = f"{source_id}:{reference.astimezone(timezone.utc).isoformat()}".encode()
            cadence += int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % (config.sync_jitter_seconds + 1)
        if now - reference >= timedelta(seconds=cadence):
            result.append(source_id)
    return result
