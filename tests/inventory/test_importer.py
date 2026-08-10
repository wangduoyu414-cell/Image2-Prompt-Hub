from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

import inventory.importer as importer_module
from ingestion.registry import SourceConfig
from inventory.database import DatabaseConfig, DatabaseError
from inventory.importer import ImportError, ImportSettings, import_package
from inventory.object_store import ObjectFact, ObjectStoreConfig
from inventory.package import ImportPlan


def synthetic_plan(tmp_path: Path) -> ImportPlan:
    config = SourceConfig(
        source_id="g0dam-work-prompts",
        repository_url="https://github.com/g0dam/Awesome-GPT-Image-2-Work-Prompts",
        verified_commit_sha="690c2d6969a65b406b17ba7d41f18695a652c3fe",
        adapter_strategy="g0dam_manifest_json_v1",
        structure_type="structured_manifest_json",
        rights={},
    )
    return ImportPlan(
        package_root=tmp_path / "package",
        source_config=config,
        source_record={"source_id": config.source_id, "repository": {}, "family": {}, "status": "active"},
        manifest={"idempotency_key": config.idempotency_key, "semantic_digest": "a" * 64, "manifest_stable_sha256": "b" * 64, "contract_version": "v1"},
        adapter_output={"records": [{"source_case_key": "g0dam-work-prompts:one"}]},
        generation_documents=(),
        metrics={},
        asset_sources=(),
        source_files=(),
        plan_digest="c" * 64,
    )


def settings(tmp_path: Path) -> ImportSettings:
    return ImportSettings(
        database=DatabaseConfig("postgresql://user:secret@127.0.0.1:5432/test"),
        object_store=ObjectStoreConfig("http://127.0.0.1:9000", "inventory-private-test", "key", "secret"),
        data_root=tmp_path / "external-data",
    )


def test_importer_orders_static_plan_before_boundaries_and_returns_existing(tmp_path, monkeypatch) -> None:
    plan = synthetic_plan(tmp_path)
    events: list[str] = []
    monkeypatch.setattr(importer_module, "build_import_plan", lambda **_kwargs: events.append("plan") or plan)
    monkeypatch.setattr(importer_module, "_verify_and_store_assets", lambda *_args, **_kwargs: events.append("objects") or {})
    class FakeDatabase:
        def __init__(self, *_args) -> None:
            events.append("database")
        def assert_migrated(self) -> None:
            events.append("migrated")
        @contextmanager
        def advisory_lock(self, _key):
            events.append("lock")
            yield
        def existing_is_complete(self, _plan, _objects):
            return True
        def inspect(self, _key):
            return {"counts": {}}
    class FakeStore:
        def __init__(self, *_args) -> None:
            events.append("store")
    monkeypatch.setattr(importer_module, "InventoryDatabase", FakeDatabase)
    monkeypatch.setattr(importer_module, "S3ObjectStore", FakeStore)
    result = import_package(
        package_root=tmp_path / "package",
        registry_path=tmp_path / "registry.json",
        audit_path=tmp_path / "audit.json",
        settings=settings(tmp_path),
    )
    assert result.status == "verified_existing"
    assert events.index("plan") < events.index("database") < events.index("lock") < events.index("objects")


def test_database_failure_is_exposed_without_claiming_ready(tmp_path, monkeypatch) -> None:
    plan = synthetic_plan(tmp_path)
    monkeypatch.setattr(importer_module, "build_import_plan", lambda **_kwargs: plan)
    monkeypatch.setattr(importer_module, "_verify_and_store_assets", lambda *_args, **_kwargs: {})
    class FakeDatabase:
        def __init__(self, *_args) -> None:
            pass
        def assert_migrated(self) -> None:
            pass
        @contextmanager
        def advisory_lock(self, _key):
            yield
        def existing_is_complete(self, _plan, _objects):
            return False
        def insert_ready_plan(self, *_args, **_kwargs) -> None:
            raise DatabaseError("database_write_failed", "rolled back")
    monkeypatch.setattr(importer_module, "InventoryDatabase", FakeDatabase)
    monkeypatch.setattr(importer_module, "S3ObjectStore", lambda *_args: object())
    with pytest.raises(ImportError) as failure:
        import_package(
            package_root=tmp_path / "package",
            registry_path=tmp_path / "registry.json",
            audit_path=tmp_path / "audit.json",
            settings=settings(tmp_path),
        )
    assert failure.value.error_code == "database_write_failed"
