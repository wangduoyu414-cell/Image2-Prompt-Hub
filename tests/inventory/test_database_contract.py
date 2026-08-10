from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from inventory.database import DatabaseConfig, InventoryDatabase, advisory_key


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_migration_declares_required_source_evidence_tables_and_immutability() -> None:
    sql = (REPO_ROOT / "migrations" / "0001_internal_inventory.sql").read_text(encoding="utf-8")
    for table in (
        "schema_migrations",
        "source_projects",
        "source_revisions",
        "source_files",
        "source_adapter_runs",
        "source_parse_errors",
        "source_cases",
        "source_case_versions",
        "prompt_records",
        "assets",
        "asset_sources",
        "generation_examples",
        "generation_inputs",
        "generation_outputs",
        "pairing_evidence",
        "rights_records",
    ):
        assert f"inventory.{table}" in sql
        assert f"immutable_{table}" in sql or table == "schema_migrations"
    assert "require_same_case_asset_source" in sql
    assert "mirror_allowed" not in sql
    assert "public_acl" not in sql
    assert "publication" not in sql


def test_hardening_migration_moves_registry_snapshot_and_enforces_domains() -> None:
    sql = (REPO_ROOT / "migrations" / "0002_inventory_security_integrity.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN registry_snapshot jsonb" in sql
    assert "SET registry_snapshot = project.registry_record" in sql
    assert "DROP COLUMN registry_record" in sql
    assert "DROP COLUMN repository_url" in sql
    assert "DROP CONSTRAINT IF EXISTS generation_examples_generation_example_id_key" in sql
    assert "UNIQUE (source_case_version_id, generation_example_id)" in sql
    for trigger in (
        "source_case_versions_domain",
        "prompt_records_source_file_revision",
        "asset_sources_source_file_revision",
        "generation_examples_prompt_domain",
    ):
        assert trigger in sql
    assert "require_case_version_domain" in sql
    assert "require_child_source_file_revision" in sql
    assert "require_generation_prompt_domain" in sql


def test_source_project_comparison_uses_only_stable_repository_identity() -> None:
    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

    class FakeConnection:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...]]] = []

        def execute(self, sql, params=()):
            self.calls.append((str(sql), tuple(params)))
            if "INSERT INTO inventory.source_projects" in sql:
                return Result(None)
            return Result({"source_project_id": 17, "repository_id": "g0dam/Awesome-GPT-Image-2-Work-Prompts"})

    plan = SimpleNamespace(
        source_id="g0dam-work-prompts",
        source_record={
            "repository": {
                "repository_id": "g0dam/Awesome-GPT-Image-2-Work-Prompts",
                "url": "https://github.com/g0dam/Awesome-GPT-Image-2-Work-Prompts-renamed",
                "verified_commit_sha": "f" * 40,
            },
            "status": "retired",
            "rights": {"notice": "changed"},
        },
    )
    connection = FakeConnection()
    database = InventoryDatabase(DatabaseConfig("postgresql://user:secret@127.0.0.1:5432/test"))

    assert database._source_project(connection, plan) == 17
    insert_sql, insert_params = connection.calls[0]
    assert "repository_url" not in insert_sql
    assert "registry_record" not in insert_sql
    assert insert_params == ("g0dam-work-prompts", "g0dam/Awesome-GPT-Image-2-Work-Prompts")


def test_advisory_key_is_stable_signed_bigint_and_not_plain_identity() -> None:
    key = "g0dam-work-prompts:690c2d6969a65b406b17ba7d41f18695a652c3fe:g0dam_manifest_json_v1:content-contract-v1"
    assert advisory_key(key) == advisory_key(key)
    assert -(2**63) <= advisory_key(key) < 2**63
    assert advisory_key(key) != int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=False)
