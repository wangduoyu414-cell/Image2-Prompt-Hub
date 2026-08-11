from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.registry import SourceConfig
from inventory.fixed_history import FixedHistoryImportError, import_fixed_history
from inventory.importer import ImportSettings
from inventory.database import DatabaseConfig
from inventory.object_store import ObjectStoreConfig


def test_fixed_history_orchestrator_rejects_continuous_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    continuous = SourceConfig(
        source_id="continuous-source",
        repository_url="https://github.com/example/source",
        verified_commit_sha="a" * 40,
        adapter_strategy="g0dam_manifest_json_v1",
        structure_type="structured_manifest_json",
        rights={},
    )
    monkeypatch.setattr("inventory.fixed_history.load_source_config", lambda *_: continuous)
    settings = ImportSettings(
        database=DatabaseConfig("postgresql://user:pass@127.0.0.1:5432/db"),
        object_store=ObjectStoreConfig("http://127.0.0.1:9000", "bucket", "key", "secret"),
        data_root=tmp_path / "git",
    )
    with pytest.raises(FixedHistoryImportError) as failure:
        import_fixed_history(
            registry_path=tmp_path / "registry.json",
            audit_path=tmp_path / "audit.json",
            source_id="continuous-source",
            git_data_root=tmp_path / "git",
            package_root=tmp_path / "packages",
            settings=settings,
        )
    assert failure.value.error_code == "fixed_history_policy_invalid"
