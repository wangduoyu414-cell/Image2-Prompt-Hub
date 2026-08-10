from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from content import cli
from content.review_store import submission_from_mapping


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_review_v2_migration_is_additive_immutable_and_domain_closed() -> None:
    sql = (REPO_ROOT / "migrations" / "0005_rights_review_queue_and_public_case_v2.sql").read_text(
        encoding="utf-8"
    )
    for token in (
        "content.rights_review_batches_v2",
        "content.rights_review_output_decisions_v2",
        "idempotency_key text NOT NULL UNIQUE",
        "expected_latest_batch_id",
        "one_public_primary_per_review_batch_v2",
        "pg_advisory_xact_lock",
        "rights review output decision crosses source case versions",
        "rights review batch must cover the exact source case output set",
        "DEFERRABLE INITIALLY DEFERRED",
        "immutable_rights_review_batches_v2",
        "immutable_rights_review_output_decisions_v2",
        "serialize_ready_run_against_review_v2",
        "rights review target is not the latest ready source revision",
        "review_note text NOT NULL",
    ):
        assert token in sql
    assert "ALTER TABLE inventory." not in sql
    assert "DROP TABLE" not in sql


def test_latest_review_queue_selection_uses_persisted_inventory_run_order() -> None:
    source = (REPO_ROOT / "content" / "review_store.py").read_text(encoding="utf-8")
    assert "run.completed_at" not in source
    assert "run.source_adapter_run_id DESC" in source
    assert "inventory.generation_inputs" in source
    assert "inventory.rights_records" in source
    assert "candidate_run.source_adapter_run_id" in source
    assert "image2-ready-review-project-v2" in source


def test_submission_mapping_requires_explicit_complete_fields() -> None:
    value = {
        "source_case_version_id": 4,
        "idempotency_key": "case-4-review-1",
        "expected_latest_batch_id": None,
        "repository_license": "MIT",
        "prompt_rights": "approved",
        "author": "Author",
        "original_url": "https://example.invalid/original",
        "evidence_url": "https://example.invalid/evidence",
        "reviewer": "reviewer",
        "reviewed_at": "2026-08-09T12:00:00Z",
        "review_note": "explicit evidence note",
        "output_decisions": [
            {
                "generation_output_id": 8,
                "asset_rights": "approved",
                "display_policy": "link_only",
                "public_display_role": "public_primary",
            }
        ],
    }
    submission = submission_from_mapping(value)
    assert submission.source_case_version_id == 4
    assert submission.reviewed_at == datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    assert submission.output_decisions[0].generation_output_id == 8


def test_review_cli_routes_explicit_commands_without_legacy_publication_writes(monkeypatch, tmp_path, capsys) -> None:
    calls: list[tuple[str, object]] = []

    class FakeStore:
        def list_queue(self, **kwargs):
            calls.append(("list", kwargs))
            return {"subject_count": 0, "items": []}

        def inspect_subject(self, value):
            calls.append(("subject", value))
            return {"state": "pending"}

        def submit_review(self, value):
            calls.append(("submit", value.source_case_version_id))
            return {"status": "recorded"}

        def inspect_batch(self, value):
            calls.append(("batch", value))
            return {"rights_review_batch_id": value}

        def preview_candidate(self, value):
            calls.append(("preview", value))
            return {"schema_version": "public-case-candidate/v2"}

    monkeypatch.setattr(cli, "_review_store", lambda: FakeStore())
    assert cli.main(["list-rights-review-queue", "--limit", "5", "--json"]) == 0
    assert cli.main(["inspect-rights-review-subject", "--source-case-version-id", "2", "--json"]) == 0
    payload = {
        "source_case_version_id": 2,
        "idempotency_key": "case-2-review-1",
        "expected_latest_batch_id": None,
        "repository_license": "MIT",
        "prompt_rights": "approved",
        "author": "Author",
        "original_url": "https://example.invalid/original",
        "evidence_url": "https://example.invalid/evidence",
        "reviewer": "reviewer",
        "reviewed_at": "2026-08-09T12:00:00Z",
        "output_decisions": [
            {
                "generation_output_id": 9,
                "asset_rights": "approved",
                "display_policy": "link_only",
                "public_display_role": "public_primary",
            }
        ],
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["submit-rights-review", "--input-json", str(path), "--json"]) == 0
    assert cli.main(["inspect-rights-review-batch", "--batch-id", "3", "--json"]) == 0
    assert cli.main(["preview-public-case-v2", "--source-case-version-id", "2", "--json"]) == 0
    assert [item[0] for item in calls] == ["list", "subject", "submit", "batch", "preview"]
    output = capsys.readouterr().out
    assert "CONTENT_DATABASE_URL" not in output
