from __future__ import annotations

from copy import deepcopy

import pytest

from content.publication import (
    PublicationPolicyError,
    canonical_key,
    evaluate_publication_gate,
    make_publication_snapshot,
    publication_content_digest,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def approved_facts(*, display_policy: str = "mirror_allowed") -> dict[str, object]:
    return {
        "canonical_case_id": 7,
        "canonical_key": HASH_A,
        "generation_example_row_id": 42,
        "generation_example_id": "generation:case:output-primary",
        "prompt_record_id": 19,
        "raw_prompt": "Make a precise product image\n",
        "source_claim": {"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": {"size": "1024x1024"}},
        "source": {
            "source_id": "source-a",
            "repository_id": "example/source-a",
            "revision_sha": "f" * 40,
            "source_path": "prompts/case.json",
            "source_url": "https://example.test/source-a/blob/f/prompts/case.json",
        },
        "pairing_status": "strong",
        "outputs": [
            {
                "ordinal": 0,
                "role": "output_primary",
                "content_sha256": HASH_B,
                "object_key": "sha256/bb/output.png",
                "object_bucket": "private",
                "byte_size": 2048,
                "media_type": "image/png",
                "integrity_state": "verified",
                "source_path": "assets/output.png",
                "source_url": "https://example.test/source-a/output.png",
                "source_location": {"source_path": "assets/output.png", "source_url": "https://example.test/source-a/output.png"},
            }
        ],
        "inputs": [
            {
                "ordinal": 0,
                "role": "reference",
                "content_sha256": HASH_C,
                "object_key": "sha256/cc/input.png",
                "object_bucket": "private",
                "byte_size": 2048,
                "media_type": "image/png",
                "integrity_state": "verified",
                "source_path": "assets/input.png",
                "source_url": "https://example.test/source-a/input.png",
                "source_location": {"source_path": "assets/input.png", "source_url": "https://example.test/source-a/input.png"},
            }
        ],
        "taxonomy": [{"tag_source": "system_facet", "tag_value": "exact_generation_facts", "confidence": 1.0}],
        "rights_review": {
            "rights_review_event_id": 3,
            "repository_license": "CC-BY-4.0",
            "prompt_rights": "approved",
            "asset_rights": "approved",
            "author": "Example Author",
            "original_url": "https://example.test/original",
            "evidence_url": "https://example.test/license",
            "reviewer": "human-reviewer",
            "reviewed_at": "2026-08-08T00:00:00+00:00",
            "display_policy": display_policy,
        },
    }


def test_exact_canonical_key_preserves_different_outputs_inputs_and_claims() -> None:
    base = canonical_key(
        raw_prompt="A prompt\r\n",
        input_hashes=[HASH_A],
        output_hashes=[HASH_B],
        source_claim={"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": None},
    )
    assert base == canonical_key(
        raw_prompt="A prompt\n",
        input_hashes=[HASH_A],
        output_hashes=[HASH_B],
        source_claim={"parameters_raw": None, "model_raw": "gpt-image-2", "evidence_status": "source_claimed"},
    )
    assert base != canonical_key(
        raw_prompt="A prompt",
        input_hashes=[HASH_A],
        output_hashes=[HASH_C],
        source_claim={"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": None},
    )
    assert base != canonical_key(
        raw_prompt="A prompt",
        input_hashes=[HASH_C],
        output_hashes=[HASH_B],
        source_claim={"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": None},
    )
    assert base != canonical_key(
        raw_prompt="A prompt",
        input_hashes=[HASH_A],
        output_hashes=[HASH_B],
        source_claim={"evidence_status": "source_claimed", "model_raw": "another-model", "parameters_raw": None},
    )


def test_canonical_key_rejects_missing_prompt_or_non_object_claim() -> None:
    with pytest.raises(PublicationPolicyError, match="non-empty prompt"):
        canonical_key(raw_prompt=" \n", input_hashes=[], output_hashes=[HASH_A], source_claim={})
    with pytest.raises(PublicationPolicyError, match="object source claim"):
        canonical_key(raw_prompt="prompt", input_hashes=[], output_hashes=[HASH_A], source_claim=[])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda facts: facts.update({"rights_review": None}), "rights_review_missing"),
        (lambda facts: facts["rights_review"].update({"display_policy": "internal_only"}), "display_policy_not_public"),  # type: ignore[index]
        (lambda facts: facts["rights_review"].update({"asset_rights": "unknown"}), "rights_not_approved"),  # type: ignore[index]
        (lambda facts: facts.update({"pairing_status": "ambiguous"}), "pairing_not_strong"),
        (lambda facts: facts.update({"outputs": []}), "output_primary_missing"),
        (lambda facts: facts["inputs"][0].update({"integrity_state": "unverified"}), "asset_unverified"),  # type: ignore[index]
        (lambda facts: facts.update({"taxonomy": [{"tag_source": "blocked"}]}), "blocked_taxonomy"),
        (lambda facts: facts.update({"source_claim": {"evidence_status": "source_claimed", "model_raw": None}}), "model_claim_invalid"),
    ],
)
def test_publication_gate_is_fail_closed_with_stable_reason_codes(change, reason: str) -> None:
    facts = approved_facts()
    change(facts)
    decision = evaluate_publication_gate(facts)
    assert not decision.included
    assert reason in decision.reason_codes


def test_link_only_snapshot_has_no_mirrorable_object_path() -> None:
    snapshot = make_publication_snapshot(approved_facts(display_policy="link_only"))
    assert snapshot["rights"]["display_policy"] == "link_only"
    assert all("object_key" not in asset and "object_bucket" not in asset for asset in snapshot["outputs"] + snapshot["inputs"])


def test_snapshot_is_immutable_input_and_digest_is_order_independent() -> None:
    first = make_publication_snapshot(approved_facts())
    second_facts = approved_facts()
    second_facts["generation_example_row_id"] = 43
    second_facts["generation_example_id"] = "generation:case:second-output"
    second_facts["canonical_key"] = HASH_B
    second_facts["outputs"][0]["content_sha256"] = HASH_C  # type: ignore[index]
    second = make_publication_snapshot(second_facts)
    original = deepcopy(first)
    assert publication_content_digest([{"snapshot": first}, {"snapshot": second}]) == publication_content_digest(
        [{"snapshot": second}, {"snapshot": first}]
    )
    assert first == original
    assert first["outputs"][0]["ordinal"] == 0
    assert first["outputs"][0]["role"] == "output_primary"
    assert first["inputs"][0]["source_path"] == "assets/input.png"
    assert first["inputs"][0]["source_location"] == {
        "source_path": "assets/input.png",
        "source_url": "https://example.test/source-a/input.png",
    }
