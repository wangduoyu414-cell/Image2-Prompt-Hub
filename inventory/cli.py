"""CLI boundary for the private internal inventory slice."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from .database import DatabaseConfig, DatabaseError, InventoryDatabase
from .fixed_history import FixedHistoryImportError, import_fixed_history
from .importer import ImportError, ImportSettings, import_package
from .object_store import ObjectStoreConfig, ObjectStoreError


EXIT_CODES = {
    "package_manifest_invalid": 20,
    "package_contract_invalid": 21,
    "package_commit_mismatch": 22,
    "package_conflict": 23,
    "fixed_history_policy_invalid": 24,
    "source_asset_mismatch": 30,
    "object_endpoint_insecure": 39,
    "object_conflict": 40,
    "object_upload_failed": 41,
    "object_download_failed": 42,
    "bucket_policy_public": 43,
    "bucket_policy_unverifiable": 44,
    "bucket_acl_public": 45,
    "bucket_acl_unverifiable": 46,
    "object_acl_public": 47,
    "object_acl_unverifiable": 48,
    "migration_drift": 50,
    "migration_failed": 51,
    "schema_not_migrated": 52,
    "import_locked": 60,
    "database_unavailable": 70,
    "database_write_failed": 71,
    "inventory_not_ready": 72,
    "injected_after_lock": 80,
    "injected_after_first_object": 81,
    "injected_after_all_objects": 82,
    "injected_mid_database": 83,
    "injected_before_commit": 84,
}


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImportError("runtime_config_missing", f"required runtime setting is missing: {name}")
    return value


def _settings(data_root: Path) -> ImportSettings:
    return ImportSettings(
        database=DatabaseConfig(_required_env("INVENTORY_DATABASE_URL")),
        object_store=ObjectStoreConfig(
            endpoint_url=_required_env("INVENTORY_S3_ENDPOINT_URL"),
            bucket=_required_env("INVENTORY_S3_BUCKET"),
            access_key=_required_env("INVENTORY_S3_ACCESS_KEY"),
            secret_key=_required_env("INVENTORY_S3_SECRET_KEY"),
            region=os.environ.get("INVENTORY_S3_REGION", "us-east-1"),
        ),
        data_root=data_root,
    )


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(payload.get("status", "unknown"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the private Source/Evidence inventory.")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="apply immutable repository SQL migrations")
    migrate.add_argument("--migrations-dir", type=Path, default=Path("migrations"))
    migrate.add_argument("--json", action="store_true")

    importing = commands.add_parser("import-package", help="validate and import one published extraction package")
    importing.add_argument("--registry", type=Path, required=True)
    importing.add_argument("--audit", type=Path, required=True)
    importing.add_argument("--package-root", type=Path, required=True)
    importing.add_argument("--data-root", type=Path, required=True)
    importing.add_argument(
        "--failure-point",
        choices=["after_lock", "after_first_object", "after_all_objects", "mid_database", "before_commit"],
    )
    importing.add_argument("--lock-hold-seconds", type=float, default=0.0)
    importing.add_argument("--json", action="store_true")

    fixed_history = commands.add_parser(
        "import-fixed-history",
        help="extract, import, and canonicalize one authorized fixed-history source without publishing it",
    )
    fixed_history.add_argument("--registry", type=Path, default=Path("config/sources-v2.yaml"))
    fixed_history.add_argument("--audit", type=Path, default=Path("reports/source-audit-v2.json"))
    fixed_history.add_argument("--source-id", required=True)
    fixed_history.add_argument("--git-data-root", type=Path, required=True)
    fixed_history.add_argument("--package-root", type=Path, required=True)
    fixed_history.add_argument("--json", action="store_true")

    inspect = commands.add_parser("inspect", help="read a stable ready-inventory summary")
    inspect.add_argument("--idempotency-key", required=True)
    inspect.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "migrate":
            database = InventoryDatabase(DatabaseConfig(_required_env("INVENTORY_DATABASE_URL")))
            applied = database.apply_migrations(args.migrations_dir)
            _emit({"status": "migrated", "migrations": applied}, args.json)
            return 0
        if args.command == "import-package":
            result = import_package(
                package_root=args.package_root,
                registry_path=args.registry,
                audit_path=args.audit,
                settings=_settings(args.data_root),
                failure_point=args.failure_point,
                lock_hold_seconds=args.lock_hold_seconds,
            )
            _emit(
                {
                    "status": result.status,
                    "source_id": result.source_id,
                    "revision_sha": result.revision_sha,
                    "idempotency_key": result.idempotency_key,
                    "semantic_digest": result.semantic_digest,
                    "plan_digest": result.plan_digest,
                    "object_count": result.object_count,
                    "summary": result.summary,
                    "states": list(result.states),
                },
                args.json,
            )
            return 0
        if args.command == "import-fixed-history":
            result = import_fixed_history(
                registry_path=args.registry,
                audit_path=args.audit,
                source_id=args.source_id,
                git_data_root=args.git_data_root,
                package_root=args.package_root,
                settings=_settings(args.git_data_root),
            )
            _emit(
                {
                    "status": result.status,
                    "source_id": result.source_id,
                    "revision_sha": result.revision_sha,
                    "package_path": str(result.package_path),
                    "extraction_status": result.extraction_status,
                    "inventory_status": result.inventory_status,
                    "idempotency_key": result.idempotency_key,
                    "semantic_digest": result.semantic_digest,
                    "object_count": result.object_count,
                    "inventory_summary": result.inventory_summary,
                    "canonicalization": result.canonicalization,
                    "publication_changed": False,
                },
                args.json,
            )
            return 0
        if args.command == "inspect":
            database = InventoryDatabase(DatabaseConfig(_required_env("INVENTORY_DATABASE_URL")))
            _emit({"status": "ready", "summary": database.inspect(args.idempotency_key)}, args.json)
            return 0
        raise AssertionError("unrecognized argparse command")
    except (FixedHistoryImportError, ImportError, DatabaseError, ObjectStoreError) as exc:
        code = getattr(exc, "error_code", "internal_error")
        _emit({"status": "failed", "error_code": code, "message": str(exc)}, getattr(args, "json", False))
        return EXIT_CODES.get(code, 1)
