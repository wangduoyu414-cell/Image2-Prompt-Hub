"""The sole package → snapshot → object-store → database orchestration owner."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.assets import AssetError, read_asset, resolve_asset_path
from ingestion.git_snapshot import GitSnapshotError, fixed_snapshot
from ingestion.registry import RegistryError, ensure_external_root, repo_root

from .database import DatabaseConfig, DatabaseError, InventoryDatabase
from .object_store import ObjectFact, ObjectStoreConfig, ObjectStoreError, S3ObjectStore
from .package import AssetSourcePlan, ImportPlan, PackageValidationError, build_import_plan


class ImportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class ImportSettings:
    database: DatabaseConfig
    object_store: ObjectStoreConfig
    data_root: Path

    def external_data_root(self) -> Path:
        try:
            return ensure_external_root(self.data_root, workspace_root=repo_root())
        except RegistryError as exc:
            raise ImportError("runtime_root_unsafe", "Git runtime data root must be outside the workspace") from exc


@dataclass(frozen=True)
class ImportResult:
    status: str
    source_id: str
    revision_sha: str
    idempotency_key: str
    semantic_digest: str
    plan_digest: str
    object_count: int
    summary: dict[str, Any]
    states: tuple[str, ...]


def _controlled_failure(point: str | None, expected: str, code: str) -> None:
    if point == expected:
        raise ImportError(code, f"controlled failure at {expected}")


def _verify_and_store_assets(
    plan: ImportPlan,
    *,
    data_root: Path,
    store: S3ObjectStore,
    failure_point: str | None,
) -> dict[str, ObjectFact]:
    """Verify each source asset while its detached fixed snapshot remains available."""
    verified_objects: dict[str, ObjectFact] = {}
    try:
        with fixed_snapshot(plan.source_config, data_root, workspace_root=repo_root()) as snapshot:
            for index, asset_source in enumerate(plan.asset_sources):
                source_path = str(asset_source.source_location["source_path"])
                fact = read_asset(snapshot.root, source_path)
                resolved_source_path = resolve_asset_path(snapshot.root, source_path)
                if (
                    fact.content_sha256 != asset_source.content_sha256
                    or fact.byte_size != asset_source.byte_size
                    or fact.media_type != asset_source.media_type
                ):
                    raise ImportError("source_asset_mismatch", "fixed snapshot asset facts differ from package evidence")
                if fact.content_sha256 in verified_objects:
                    continue
                object_fact = store.ensure_object(
                    source_path=resolved_source_path,
                    content_sha256=fact.content_sha256,
                    byte_size=fact.byte_size,
                    media_type=fact.media_type,
                )
                verified_objects[fact.content_sha256] = object_fact
                if index == 0:
                    _controlled_failure(failure_point, "after_first_object", "injected_after_first_object")
            if len(verified_objects) != len({item.content_sha256 for item in plan.asset_sources}):
                raise ImportError("source_asset_mismatch", "not every planned content hash was verified")
    except ImportError:
        raise
    except (GitSnapshotError, AssetError) as exc:
        code = getattr(exc, "error_code", "snapshot_failed")
        raise ImportError(code, "fixed snapshot or repository asset verification failed") from exc
    except ObjectStoreError as exc:
        raise ImportError(exc.error_code, str(exc)) from exc
    return verified_objects


def import_package(
    *,
    package_root: Path | str,
    registry_path: Path | str,
    audit_path: Path | str,
    settings: ImportSettings,
    failure_point: str | None = None,
    lock_hold_seconds: float = 0.0,
) -> ImportResult:
    """Import one fully validated published package without partial ready inventory."""
    try:
        plan = build_import_plan(package_root=package_root, registry_path=registry_path, audit_path=audit_path)
        data_root = settings.external_data_root()
        database = InventoryDatabase(settings.database)
        store = S3ObjectStore(settings.object_store)
    except PackageValidationError as exc:
        raise ImportError(exc.error_code, str(exc)) from exc
    except (DatabaseError, ObjectStoreError) as exc:
        raise ImportError(exc.error_code, str(exc)) from exc
    states: list[str] = ["package_verified", "source_verified"]
    try:
        database.assert_migrated()
        with database.advisory_lock(plan.idempotency_key):
            states.append("lock_acquired")
            if lock_hold_seconds > 0:
                time.sleep(lock_hold_seconds)
            _controlled_failure(failure_point, "after_lock", "injected_after_lock")
            objects = _verify_and_store_assets(
                plan,
                data_root=data_root,
                store=store,
                failure_point=failure_point,
            )
            states.extend(["snapshot_verified", "assets_verified", "objects_ready"])
            _controlled_failure(failure_point, "after_all_objects", "injected_after_all_objects")
            if database.existing_is_complete(plan, objects):
                summary = database.inspect(plan.idempotency_key)
                states.append("verified_existing")
                return ImportResult(
                    status="verified_existing",
                    source_id=plan.source_id,
                    revision_sha=plan.revision_sha,
                    idempotency_key=plan.idempotency_key,
                    semantic_digest=plan.semantic_digest,
                    plan_digest=plan.plan_digest,
                    object_count=len(objects),
                    summary=summary,
                    states=tuple(states),
                )
            states.append("database_transaction")
            database.insert_ready_plan(plan, objects, failure_point=failure_point)
            summary = database.inspect(plan.idempotency_key)
            states.append("inventory_ready")
            return ImportResult(
                status="imported",
                source_id=plan.source_id,
                revision_sha=plan.revision_sha,
                idempotency_key=plan.idempotency_key,
                semantic_digest=plan.semantic_digest,
                plan_digest=plan.plan_digest,
                object_count=len(objects),
                summary=summary,
                states=tuple(states),
            )
    except ImportError:
        raise
    except DatabaseError as exc:
        raise ImportError(exc.error_code, str(exc)) from exc
