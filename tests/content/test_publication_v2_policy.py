"""Pure contract tests for Candidate-v2 publication and takedown matching."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from content.publication_store_v2 import PublicationV2Store
from content.publication_v2 import PublicationV2PolicyError, freeze_candidate, publication_v2_digest
from content.review import build_public_case_candidate
from tests.content.test_review_policy import case_facts, stored_review


def _publishable_candidate() -> dict:
    return build_public_case_candidate(case_facts(), stored_review())


def test_freeze_candidate_preserves_multi_output_authority_and_redacted_input_count() -> None:
    candidate = _publishable_candidate()

    entry = freeze_candidate(candidate)

    assert entry["schema_version"] == "public-case-publication-entry/v2"
    assert entry["public_case_key"] != candidate["candidate_content_digest"]
    assert len(entry["public_case_key"]) == 64
    assert entry["rights_review"]["reviewed_at"] == candidate["rights_review"]["reviewed_at"]
    assert "source_case_version_id" not in entry
    assert "rights_review_batch_id" not in entry
    assert "reviewer" not in repr(entry)
    assert "generation_example_row_id" not in repr(entry)
    assert entry["tags"] == ["multi-output", "studio"]
    assert sum(len(member["public_outputs"]) for member in entry["generation_members"]) == 2
    assert sum(len(member["reference_inputs"]) for member in entry["generation_members"]) == 0
    assert sum(
        output["public_display_role"] == "public_primary"
        for member in entry["generation_members"]
        for output in member["public_outputs"]
    ) == 1
    rendered = str(entry)
    assert "object_key" not in rendered
    assert "object_bucket" not in rendered
    assert publication_v2_digest([entry]) == publication_v2_digest([copy.deepcopy(entry)])


def test_freeze_candidate_rejects_nonpublishable_or_primary_drift() -> None:
    pending = build_public_case_candidate(case_facts(), None)
    with pytest.raises(PublicationV2PolicyError):
        freeze_candidate(pending)

    impossible = _publishable_candidate()
    for member in impossible["generation_members"]:
        member["public_outputs"] = []
    with pytest.raises(PublicationV2PolicyError):
        freeze_candidate(impossible)

    rights_drift = _publishable_candidate()
    rights_drift["generation_members"][0]["public_outputs"][0]["rights"]["asset_rights"] = "blocked"
    with pytest.raises(PublicationV2PolicyError):
        freeze_candidate(rights_drift)



def test_takedown_matching_covers_asset_prompt_case_digest_case_version_and_source() -> None:
    candidate = _publishable_candidate()
    primary = next(
        output
        for member in candidate["generation_members"]
        for output in member["public_outputs"]
        if output["public_display_role"] == "public_primary"
    )
    scopes = [
        ("asset", primary["content_sha256"], "takedown_asset"),
        (
            "prompt",
            f"{candidate['source_case']['source_id']}:{candidate['prompt']['prompt_id']}",
            "takedown_prompt",
        ),
        (
            "case",
            f"{candidate['source_case']['source_id']}:{candidate['source_case']['source_case_key']}",
            "takedown_case",
        ),
        ("source", candidate["source_case"]["source_id"], "takedown_source"),
    ]
    for scope_type, scope_key, expected in scopes:
        assert PublicationV2Store._takedown_reason(
            candidate, {(scope_type, scope_key): {"action": "remove"}}
        ) == expected
        assert PublicationV2Store._takedown_reason(
            candidate, {(scope_type, scope_key): {"action": "restore"}}
        ) is None


def test_publication_builder_has_distinct_quality_exclusion_reason() -> None:
    source = Path(__file__).resolve().parents[2] / "content" / "publication_store_v2.py"
    text = source.read_text(encoding="utf-8")
    assert 'quality = facts.get("quality")' in text
    assert 'reason = f"quality_{quality[\'reason_code\']}"' in text
    migration = (Path(__file__).resolve().parents[2] / "migrations" / "0009_content_quality_exclusions.sql").read_text(
        encoding="utf-8"
    )
    for reason_code in (
        "quality_non_result_capture",
        "quality_prompt_output_mismatch",
        "quality_near_identical_cross_source_render",
        "quality_exact_prompt_output_subset",
    ):
        assert reason_code in migration
    assert "has_quality_exclusion_domain" in text
    assert "self.assert_migrated()" in text


def test_publication_v2_migration_declares_immutable_snapshot_asset_and_takedown_boundaries() -> None:
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[2] / "migrations" / "0006_publication_v2_and_takedown.sql").read_text(
        encoding="utf-8"
    )
    for table in (
        "publication_versions_v2",
        "publication_build_requests_v2",
        "publication_revision_selections_v2",
        "publication_entries_v2",
        "publication_assets_v2",
        "publication_current_v2",
        "publication_outbox_v2",
        "takedown_requests_v2",
        "publication_exclusions_v2",
        "publication_takedown_applications_v2",
    ):
        assert f"content.{table}" in sql
    for trigger in (
        "immutable_publication_revision_selections_v2",
        "immutable_publication_build_requests_v2",
        "immutable_publication_entries_v2",
        "immutable_publication_assets_v2",
        "immutable_publication_outbox_v2",
        "immutable_takedown_requests_v2",
        "immutable_publication_exclusions_v2",
        "immutable_publication_takedown_applications_v2",
    ):
        assert trigger in sql
    assert "publication v2 private asset manifest does not match immutable inventory" in sql
    assert "publication v2 entry is absent from its explicit revision selection" in sql
    assert "takedown request cannot be future dated" in sql
