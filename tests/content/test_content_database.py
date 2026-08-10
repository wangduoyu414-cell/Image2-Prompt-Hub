from __future__ import annotations

import json
from pathlib import Path

import pytest

from content import cli
from content.database import ContentDatabaseSettings
from scripts import validate_content_core as content_validator


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_content_migration_is_additive_and_declares_immutable_boundaries() -> None:
    sql = (REPO_ROOT / "migrations" / "0003_content_core_publication.sql").read_text(encoding="utf-8")
    database_source = (REPO_ROOT / "content" / "database.py").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS content" in sql
    for table in (
        "canonical_cases",
        "canonical_memberships",
        "taxonomy_assignments",
        "rights_review_events",
        "publication_versions",
        "publication_entries",
        "publication_current",
        "publication_outbox",
    ):
        assert f"content.{table}" in sql
    assert "ALTER TABLE inventory" not in sql
    assert "immutable_rights_review_events" in sql
    assert "one_active_publication_version" in sql
    assert "require_current_active_version" in sql
    assert "rights_review_not_future" in sql
    assert "link_only publication snapshot must not contain a mirrorable object path" in sql
    for json_path in ("$.outputs[*].object_key", "$.outputs[*].object_bucket", "$.inputs[*].object_key", "$.inputs[*].object_bucket"):
        assert json_path in sql
    assert "ON CONFLICT (generation_example_row_id) DO NOTHING" in database_source


def test_content_database_settings_reject_missing_or_non_postgres_dsn() -> None:
    for value in ("", "https://example.test/database"):
        try:
            ContentDatabaseSettings(value).validate()
        except Exception as exc:
            assert getattr(exc, "error_code", None) == "content_config_invalid"
        else:
            raise AssertionError("invalid DSN was accepted")


def test_cli_json_error_does_not_leak_database_credentials(monkeypatch, capsys) -> None:
    monkeypatch.delenv("CONTENT_DATABASE_URL", raising=False)
    assert cli.main(["canonicalize", "--json"]) == 20
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert "CONTENT_DATABASE_URL" in payload["message"]
    assert "postgresql://" not in payload["message"]


def test_content_core_exposes_explicit_revision_selection_and_sync_atomic_completion() -> None:
    source = (REPO_ROOT / "content" / "database.py").read_text(encoding="utf-8")
    migration = (REPO_ROOT / "migrations" / "0004_incremental_sync.sql").read_text(encoding="utf-8")
    assert "build_publication_for_revisions" in source
    assert "publication_public_loss" in source
    assert "activate_publication_for_sync" in source
    assert "after_outbox_before_sync_completion" in source
    assert "result_document=source_sync_runs.result_document || jsonb_build_object" in source
    assert "content.publication_revision_selections" in migration
    assert "publication entry is absent from the explicit revision selection" in migration


def test_content_live_validator_uses_exact_dynamic_repository_migration_manifest(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for index in range(1, 6):
        (migrations / f"{index:04d}_future_slice.sql").write_text(f"-- migration {index}\n", encoding="utf-8")

    expected = content_validator._repository_migration_manifest(migrations)

    assert [item["version"] for item in expected] == [f"{index:04d}_future_slice" for index in range(1, 6)]
    initial = [{**item, "status": "applied"} for item in expected]
    replay = [{**item, "status": "verified_existing"} for item in expected]
    content_validator._assert_migration_results(
        initial, expected, phase="initial apply", allowed_statuses={"applied", "verified_existing"}
    )
    content_validator._assert_migration_results(replay, expected, phase="replay", allowed_statuses={"verified_existing"})


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda rows: rows.pop(), "result count"),
        (lambda rows: rows.__setitem__(-1, {**rows[-1], "version": rows[0]["version"]}), "duplicate version"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "version": "9999_wrong"}), "version mismatch"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "checksum_sha256": "0" * 64}), "checksum mismatch"),
        (lambda rows: rows.__setitem__(0, {**rows[0], "status": "applied"}), "unexpected status"),
    ],
)
def test_content_live_validator_rejects_migration_result_drift(
    tmp_path: Path, mutate, message: str
) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for index in range(1, 5):
        (migrations / f"{index:04d}_slice.sql").write_text(f"-- migration {index}\n", encoding="utf-8")
    expected = content_validator._repository_migration_manifest(migrations)
    actual = [{**item, "status": "verified_existing"} for item in expected]
    mutate(actual)

    with pytest.raises(content_validator.ValidationFailure, match=message):
        content_validator._assert_migration_results(
            actual, expected, phase="replay", allowed_statuses={"verified_existing"}
        )
