"""Stable JSON CLI for one registered incremental source at a time."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from .pipeline import SyncPipelineError, SyncSettings, inspect_source, run_source


REPO_ROOT = Path(__file__).resolve().parents[1]


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SyncPipelineError("sync_config_missing", f"{name} is required")
    return value


def _settings_from_environment() -> SyncSettings:
    return SyncSettings(
        database_url=_required_environment("SYNC_DATABASE_URL"),
        s3_endpoint_url=_required_environment("SYNC_S3_ENDPOINT_URL"),
        s3_bucket=_required_environment("SYNC_S3_BUCKET"),
        s3_access_key_id=_required_environment("SYNC_S3_ACCESS_KEY_ID"),
        s3_secret_access_key=_required_environment("SYNC_S3_SECRET_ACCESS_KEY"),
        git_data_root=Path(_required_environment("SYNC_GIT_DATA_ROOT")),
        package_root=Path(_required_environment("SYNC_PACKAGE_ROOT")),
        evidence_root=Path(_required_environment("SYNC_EVIDENCE_ROOT")),
    )


def _emit(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(payload.get("status", "failed"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run one safe registered source Commit update.")
    subcommands = result.add_subparsers(dest="command", required=True)
    for name in ("run-source", "inspect-source"):
        command = subcommands.add_parser(name)
        command.add_argument("--source-id", required=True)
        command.add_argument("--json", action="store_true")
    run = subcommands.choices["run-source"]
    run.add_argument("--registry", default=str(REPO_ROOT / "config" / "sources-v1.yaml"))
    run.add_argument("--audit", default=str(REPO_ROOT / "reports" / "source-audit-v1.json"))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inspect-source":
            payload = {"status": "inspected", "result": inspect_source(source_id=args.source_id, database_url=_required_environment("SYNC_DATABASE_URL"))}
        else:
            payload = run_source(
                registry_path=Path(args.registry),
                audit_path=Path(args.audit),
                source_id=args.source_id,
                settings=_settings_from_environment(),
            ).as_json()
        _emit(payload, as_json=args.json)
        return 0
    except SyncPipelineError as exc:
        _emit({"status": "failed", "error_code": exc.error_code, "message": "incremental sync did not complete"}, as_json=args.json)
        return 20
    except Exception:
        _emit({"status": "failed", "error_code": "sync_failed", "message": "incremental sync did not complete"}, as_json=args.json)
        return 20
