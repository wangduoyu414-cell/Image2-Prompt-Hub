from __future__ import annotations

from pathlib import Path

import pytest

from sync.cli import parser
from sync.database import SyncDatabaseError, SyncDatabaseSettings, stable_sync_key


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_sync_idempotency_key_is_stable_per_source_candidate_only() -> None:
    candidate = "a" * 40
    assert stable_sync_key("source-a", candidate) == stable_sync_key("source-a", candidate)
    assert stable_sync_key("source-a", candidate) != stable_sync_key("source-b", candidate)
    assert len(stable_sync_key("source-a", candidate)) == 64


def test_sync_database_settings_reject_non_postgres_urls() -> None:
    for value in ("", "https://example.invalid/database"):
        with pytest.raises(SyncDatabaseError) as failure:
            SyncDatabaseSettings(value).validate()
        assert failure.value.error_code == "sync_config_invalid"


def test_sync_cli_declares_one_source_json_commands() -> None:
    parsed = parser().parse_args(["run-source", "--source-id", "g0dam-work-prompts", "--json"])
    assert parsed.command == "run-source"
    assert parsed.source_id == "g0dam-work-prompts"
    assert parsed.json is True
    inspected = parser().parse_args(["inspect-source", "--source-id", "g0dam-work-prompts", "--json"])
    assert inspected.command == "inspect-source"


def test_incremental_migration_declares_run_tombstone_selection_and_atomic_boundaries() -> None:
    sql = (REPO_ROOT / "migrations" / "0004_incremental_sync.sql").read_text(encoding="utf-8")
    for table in ("sync.source_sync_runs", "sync.case_tombstone_events", "content.publication_revision_selections"):
        assert table in sql
    assert "UNIQUE (source_id, candidate_revision_sha)" in sql
    assert "event_type IN ('removed', 'restored')" in sql
    assert "publication entry is absent from the explicit revision selection" in sql
    assert "immutable_case_tombstone_events" in sql
