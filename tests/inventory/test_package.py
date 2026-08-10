from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import inventory.package as package_module
from inventory.importer import ImportError, ImportSettings, import_package
from inventory.object_store import ObjectStoreConfig
from inventory.database import DatabaseConfig
from inventory.package import PackageValidationError, build_import_plan
from ingestion.registry import load_source_config


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "adapters" / "g0dam-work-prompts" / "690c2d6969a65b406b17ba7d41f18695a652c3fe"
JOESAI_FIXTURE_ROOT = (
    REPO_ROOT
    / "fixtures"
    / "adapters"
    / "joesai-commercial-prompts"
    / "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b"
)


def stable_manifest_hash(manifest: dict) -> str:
    copy = dict(manifest)
    copy.pop("manifest_stable_sha256", None)
    return hashlib.sha256(json.dumps(copy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create_fixture_package(tmp_path: Path) -> Path:
    root = tmp_path / "published-package"
    (root / "generation-examples").mkdir(parents=True)
    shutil.copy2(FIXTURE_ROOT / "expected-adapter-output.json", root / "adapter-output.json")
    shutil.copy2(FIXTURE_ROOT / "expected-metrics.json", root / "metrics.json")
    generations = json.loads((FIXTURE_ROOT / "expected-generation-examples.json").read_text(encoding="utf-8"))
    (root / "generation-examples" / "case-fixture.json").write_text(json.dumps(generations[0], ensure_ascii=False), encoding="utf-8")
    files = []
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        files.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "byte_size": path.stat().st_size})
    manifest = {
        "schema_version": "g0dam-extraction-package/v1",
        "package_state": "published",
        "idempotency_key": "g0dam-work-prompts:690c2d6969a65b406b17ba7d41f18695a652c3fe:g0dam_manifest_json_v1:content-contract-v1",
        "source_id": "g0dam-work-prompts",
        "revision_sha": "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "adapter_version": "1.0.0",
        "contract_version": "v1",
        "semantic_digest": json.loads((FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))["semantic_digest"],
        "files": files,
    }
    manifest["manifest_stable_sha256"] = stable_manifest_hash(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root


def fixture_audit_metrics() -> dict:
    return json.loads((FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))


def create_joesai_fixture_package(tmp_path: Path) -> Path:
    root = tmp_path / "joesai-published-package"
    (root / "generation-examples").mkdir(parents=True)
    shutil.copy2(JOESAI_FIXTURE_ROOT / "expected-adapter-output.json", root / "adapter-output.json")
    shutil.copy2(JOESAI_FIXTURE_ROOT / "expected-metrics.json", root / "metrics.json")
    generations = json.loads((JOESAI_FIXTURE_ROOT / "expected-generation-examples.json").read_text(encoding="utf-8"))
    for index, generation in enumerate(generations):
        (root / "generation-examples" / f"case-{index:02d}.json").write_text(
            json.dumps(generation, ensure_ascii=False), encoding="utf-8"
        )
    files = []
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        files.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "byte_size": path.stat().st_size})
    source = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "joesai-commercial-prompts")
    metrics = json.loads((JOESAI_FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "extraction-package/v1",
        "package_state": "published",
        "idempotency_key": source.idempotency_key,
        "source_id": source.source_id,
        "revision_sha": source.verified_commit_sha,
        "adapter_version": "1.0.0",
        "contract_version": "v1",
        "semantic_digest": metrics["semantic_digest"],
        "files": files,
    }
    manifest["manifest_stable_sha256"] = stable_manifest_hash(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return root


def test_package_plan_preserves_raw_contract_and_requires_complete_file_set(tmp_path, monkeypatch) -> None:
    root = create_fixture_package(tmp_path)
    monkeypatch.setattr(package_module, "_audit_metrics", lambda *_args: fixture_audit_metrics())
    plan = build_import_plan(
        package_root=root,
        registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
        audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
    )
    assert plan.plan_digest
    assert len(plan.adapter_output["records"]) == 1
    assert plan.generation_documents[0]["prompts"][0]["raw_text"] == plan.adapter_output["records"][0]["prompt"]["raw_text"]
    assert plan.asset_sources[0].content_sha256 == plan.generation_documents[0]["assets"][0]["content_sha256"]
    (root / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PackageValidationError) as failure:
        build_import_plan(
            package_root=root,
            registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
            audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
        )
    assert failure.value.error_code == "package_manifest_invalid"


def test_invalid_package_stops_before_database_or_object_factories(tmp_path, monkeypatch) -> None:
    root = create_fixture_package(tmp_path)
    (root / "adapter-output.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(package_module, "_audit_metrics", lambda *_args: fixture_audit_metrics())
    class UnexpectedBoundary:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("external boundary must not be created for invalid package")
    import inventory.importer as importer_module
    monkeypatch.setattr(importer_module, "InventoryDatabase", UnexpectedBoundary)
    monkeypatch.setattr(importer_module, "S3ObjectStore", UnexpectedBoundary)
    settings = ImportSettings(
        database=DatabaseConfig("postgresql://user:secret@127.0.0.1:5432/test"),
        object_store=ObjectStoreConfig("http://127.0.0.1:9000", "inventory-private-test", "key", "secret"),
        data_root=tmp_path / "external-data",
    )
    with pytest.raises(ImportError) as failure:
        import_package(
            package_root=root,
            registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
            audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
            settings=settings,
        )
    assert failure.value.error_code == "package_manifest_invalid"


def test_package_plan_accepts_explicit_neutral_joesai_schema(tmp_path, monkeypatch) -> None:
    root = create_joesai_fixture_package(tmp_path)
    fixture_metrics = json.loads((JOESAI_FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(package_module, "_audit_metrics", lambda *_args: fixture_metrics)
    plan = build_import_plan(
        package_root=root,
        registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
        audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
    )
    assert plan.source_config.source_id == "joesai-commercial-prompts"
    assert plan.manifest["schema_version"] == "extraction-package/v1"
    assert plan.metrics["schema_version"] == "extraction-metrics/v1"
    assert len(plan.adapter_output["records"]) == 3
    assert len(plan.generation_documents) == 3
