"""Read-only operational checks, deduplicated alerts, and webhook delivery."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import sentry_sdk

from apps.observability import configure_observability
from .database import SyncDatabaseError, SyncDatabaseSettings
from .operations import OperationsDatabase, alert_fingerprint
from .schedule_policy import eligible_source_ids


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SyncDatabaseError("monitor_config_missing", f"{name} is required")
    return value


def _seconds(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise SyncDatabaseError("monitor_config_invalid", f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SyncDatabaseError("monitor_config_invalid", f"{name} is outside its supported range")
    return value


def _public_origin() -> str:
    value = _required("IMAGE2_PUBLIC_ORIGIN").rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise SyncDatabaseError("monitor_config_invalid", "public origin must be an absolute HTTP(S) URL")
    return value


def _json_request(url: str, *, timeout: int = 10) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "image2-operations-monitor/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise OSError("health endpoint did not return 200")
        value = json.loads(response.read(1024 * 1024).decode("utf-8"))
    if not isinstance(value, dict):
        raise OSError("health endpoint returned a non-object")
    return value


def _asset_request(url: str, *, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "image/*", "User-Agent": "image2-operations-monitor/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        content_length = response.headers.get("Content-Length")
        body = response.read(1)
        if response.status != 200 or not content_type.startswith("image/") or not body:
            raise OSError("public asset did not return valid image bytes")
    return {"content_type": content_type, "content_length": content_length}


def _alert(code: str, severity: str, subject: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "fingerprint": alert_fingerprint(code, subject),
        "alert_code": code,
        "severity": severity,
        "subject_key": subject,
        "details": details,
    }


def collect_alerts(snapshot: dict[str, Any], *, now: datetime, public_origin: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    http: dict[str, Any] = {}
    try:
        ready = _json_request(f"{public_origin}/readyz")
        http["ready"] = ready
        if ready.get("status") != "ready":
            alerts.append(_alert("service_unready", "critical", "public-origin", {"status": ready.get("status")}))
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        alerts.append(_alert("service_unreachable", "critical", "public-origin", {"error": type(exc).__name__}))
    publication_has_cases = False
    try:
        publication = _json_request(f"{public_origin}/backend-v2/publication")
        http["publication"] = publication
        if publication.get("state") not in {"no_current", "active"}:
            alerts.append(_alert("publication_invalid", "critical", "publication-v2", {"state": publication.get("state")}))
        if publication.get("state") == "active" and int(publication.get("case_count", 0)) > 0:
            publication_has_cases = True
            listing = _json_request(f"{public_origin}/backend-v2/cases?page=1&page_size=1")
            cases = listing.get("cases")
            primary = cases[0].get("primary_output") if isinstance(cases, list) and cases and isinstance(cases[0], dict) else None
            content_sha256 = primary.get("content_sha256") if isinstance(primary, dict) else None
            if not isinstance(content_sha256, str):
                raise OSError("active publication has no sample primary asset")
            http["sample_asset"] = _asset_request(f"{public_origin}/backend-v2/assets/{content_sha256}")
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        code = "public_asset_invalid" if publication_has_cases else "publication_unreachable"
        alerts.append(_alert(code, "critical", "publication-v2", {"error": type(exc).__name__}))

    cadence = _seconds("MONITOR_SYNC_STALE_SECONDS", 20 * 60, minimum=15 * 60, maximum=14 * 24 * 60 * 60)
    runtime = snapshot.get("scheduler_runtime")
    if not isinstance(runtime, dict):
        alerts.append(_alert("scheduler_never_ran", "warning", "scheduler", {}))
    else:
        heartbeat = runtime.get("last_heartbeat_at")
        if not isinstance(heartbeat, datetime) or now - heartbeat > timedelta(seconds=cadence):
            details = {"last_heartbeat_at": heartbeat.isoformat()} if isinstance(heartbeat, datetime) else {}
            alerts.append(_alert("scheduler_stale", "critical", "scheduler", details))
        if runtime.get("last_status") == "error":
            details = runtime.get("details") if isinstance(runtime.get("details"), dict) else {}
            alerts.append(_alert("scheduler_error", "critical", "scheduler", details))
    cycle = snapshot.get("cycle")
    if isinstance(cycle, dict):
        if cycle.get("state") == "partial_failure":
            alerts.append(_alert("scheduler_cycle_failed", "critical", str(cycle.get("cycle_key")), {"state": cycle.get("state")}))

    for result in snapshot.get("active_source_results", []):
        if not isinstance(result, dict) or result.get("state") not in {"queued", "running"}:
            continue
        reference = result.get("started_at") or result.get("queued_at")
        if isinstance(reference, datetime) and now - reference > timedelta(hours=4):
            alerts.append(_alert("source_worker_stuck", "critical", str(result.get("source_id")), {"state": result.get("state")}))

    latest = {str(row.get("source_id")): row for row in snapshot.get("latest_sync_runs", []) if isinstance(row, dict)}
    for source_id in eligible_source_ids():
        row = latest.get(source_id)
        if row is None:
            alerts.append(_alert("source_never_synced", "warning", source_id, {}))
            continue
        state = row.get("state")
        if state == "failed":
            alerts.append(_alert("source_sync_failed", "critical", source_id, {"error_code": row.get("error_code")}))
        elif state == "review_required":
            result_document = row.get("result_document") if isinstance(row.get("result_document"), dict) else {}
            quality_gate = result_document.get("quality_gate") if isinstance(result_document.get("quality_gate"), dict) else {}
            reasons = quality_gate.get("reasons") if isinstance(quality_gate.get("reasons"), list) else []
            code = "source_count_drop" if row.get("reason_code") == "quality_gate" and any(
                "count" in str(reason) or "removal" in str(reason) for reason in reasons
            ) else "source_review_required"
            alerts.append(_alert(code, "critical", source_id, {"reason_code": row.get("reason_code"), "reasons": reasons}))
        elif state not in {"completed", "no_change"}:
            alerts.append(_alert("source_sync_incomplete", "critical", source_id, {"state": state}))
    return alerts, http


def _send_webhook(url: str, alerts: list[dict[str, Any]], now: datetime) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise SyncDatabaseError("monitor_webhook_invalid", "alert webhook must be public HTTPS without URL credentials")
    payload = json.dumps({"event": "image2_operations_alerts", "observed_at": now.isoformat(), "alerts": alerts}, sort_keys=True).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise OSError("alert webhook rejected the notification")


def run_once(*, emit: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    database = OperationsDatabase(SyncDatabaseSettings(_required("SYNC_DATABASE_URL")))
    database.assert_migrated()
    snapshot = database.snapshot()
    alerts, http = collect_alerts(snapshot, now=now, public_origin=_public_origin())
    pending = database.observe_alerts(alerts, now=now)
    webhook = os.environ.get("IMAGE2_ALERT_WEBHOOK_URL", "").strip()
    if pending and webhook:
        _send_webhook(webhook, pending, now)
        database.mark_notified(fingerprints=[str(item["fingerprint"]) for item in pending], now=now)
    result = {
        "status": "alerting" if alerts else "healthy",
        "observed_at": now.isoformat(),
        "alert_count": len(alerts),
        "new_notification_count": len(pending) if webhook else 0,
        "alerts": alerts,
        "http": http,
    }
    if emit:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str), flush=True)
    if alerts and os.environ.get("MONITOR_FAIL_ON_ALERT", "false").casefold() == "true":
        raise SyncDatabaseError("monitor_alerts_active", "operational alerts are active")
    return result


def run_forever() -> None:
    configure_observability("image2-operations-monitor")
    interval = _seconds("MONITOR_INTERVAL_SECONDS", 5 * 60, minimum=60, maximum=60 * 60)
    while True:
        try:
            run_once(emit=True)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            print(json.dumps({"status": "failed", "error_code": getattr(exc, "error_code", "monitor_failed")}), flush=True)
        time.sleep(interval)
