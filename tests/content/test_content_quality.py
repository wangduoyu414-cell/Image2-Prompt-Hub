from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from content.quality import (
    ContentQualityError,
    assert_quality_submission_compatible,
    content_quality_decision,
    load_content_quality_ledger,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_quality_ledger_is_schema_valid_unique_and_fixed_fact_bound() -> None:
    load_content_quality_ledger.cache_clear()
    decisions = load_content_quality_ledger()
    assert len(decisions) == 24
    assert sum(item.verdict == "blocked" for item in decisions) == 5
    assert sum(item.verdict == "duplicate_only" for item in decisions) == 19
    payload = json.loads((REPO_ROOT / "config" / "content-quality-v1.json").read_text(encoding="utf-8"))
    assert payload["scope"]["reviewed_exact_prompt_group_count"] == 29
    assert payload["scope"]["reviewed_source_case_count"] == 69
    assert payload["scope"]["reviewed_output_reference_count"] == 78


def test_quality_decision_fails_closed_when_prompt_or_output_authority_drifts() -> None:
    decision = next(item for item in load_content_quality_ledger() if item.source_case_key.endswith(":145"))
    with pytest.raises(ContentQualityError, match="no longer matches"):
        content_quality_decision(
            source_id=decision.source_id,
            revision_sha=decision.revision_sha,
            source_case_key=decision.source_case_key,
            raw_prompt="different prompt",
            output_content_sha256=decision.output_content_sha256,
        )


def test_quality_block_cannot_be_contradicted_by_public_rights_submission() -> None:
    decision = next(item for item in load_content_quality_ledger() if item.source_case_key.endswith(":145"))
    facts = {
        "source": {
            "source_id": "freestylefly-awesome-gpt-image-2",
            "revision_sha": "76fcd0e6b3961ef2b041547aac654f1efd1ef270",
            "source_case_key": "freestylefly-awesome-gpt-image-2:145",
        },
        "prompt": {
            "raw_text": "placeholder"
        },
        "generations": [{"outputs": [{"content_sha256": "2b090f2eb2a95d4bcd99f5d3a1b0609b5cedd889a668aaf37afefe184a3abb15"}]}],
    }
    review = {
        "prompt_rights": "approved",
        "output_decisions": [{"public_display_role": "public_primary"}],
    }
    from unittest.mock import patch

    with patch("content.quality.content_quality_decision", return_value=decision):
        with pytest.raises(ContentQualityError, match="cannot receive a public approval"):
            assert_quality_submission_compatible(copy.deepcopy(facts), review)
