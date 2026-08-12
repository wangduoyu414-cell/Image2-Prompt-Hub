from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from content.review import (
    OutputReviewDecision,
    ReviewPolicyError,
    ReviewSubmission,
    build_public_case_candidate,
    effective_review_state,
    submission_digest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def case_facts() -> dict:
    return {
        "source_case_version_id": 7,
        "public_tags": ["studio", "multi-output"],
        "source": {
            "source_id": "source-a",
            "repository_id": "github:1",
            "revision_sha": "a" * 40,
            "source_case_key": "source-a:case-1",
        },
        "prompt": {
            "prompt_id": "prompt:1",
            "raw_text": "Create one explicit multi-output design.",
            "language": "en",
            "source_path": "prompts/case.json",
            "source_url": "https://example.invalid/blob/a/prompts/case.json",
        },
        "generations": [
            {
                "generation_example_row_id": 11,
                "generation_example_id": "generation:1",
                "source_claim": {
                    "evidence_status": "source_claimed",
                    "model_raw": "gpt-image-2",
                    "parameters_raw": {"size": "1024x1024"},
                },
                "outputs": [
                    {
                        "generation_output_id": 101,
                        "ordinal": 0,
                        "source_role": "output_primary",
                        "content_sha256": "1" * 64,
                        "media_type": "image/jpeg",
                        "byte_size": 1024,
                        "source_path": "assets/one.jpg",
                        "source_url": "https://example.invalid/blob/a/assets/one.jpg",
                        "source_location": {"source_path": "assets/one.jpg"},
                    }
                ],
            },
            {
                "generation_example_row_id": 12,
                "generation_example_id": "generation:2",
                "source_claim": {
                    "evidence_status": "source_claimed",
                    "model_raw": "gpt-image-2",
                    "parameters_raw": None,
                },
                "outputs": [
                    {
                        "generation_output_id": 102,
                        "ordinal": 0,
                        "source_role": "output_secondary",
                        "content_sha256": "2" * 64,
                        "media_type": "image/webp",
                        "byte_size": 2048,
                        "source_path": "assets/two.webp",
                        "source_url": "https://example.invalid/blob/a/assets/two.webp",
                        "source_location": {"source_path": "assets/two.webp"},
                    }
                ],
            },
        ],
    }


def submission() -> ReviewSubmission:
    return ReviewSubmission(
        source_case_version_id=7,
        idempotency_key="review-case-1-v1",
        expected_latest_batch_id=None,
        repository_license="MIT",
        prompt_rights="approved",
        author="Example Author",
        original_url="https://example.invalid/original",
        evidence_url="https://example.invalid/evidence",
        reviewer="reviewer@example.invalid",
        reviewed_at=datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc),
        output_decisions=(
            OutputReviewDecision(101, "approved", "attribution_required", "public_primary"),
            OutputReviewDecision(102, "approved", "link_only", "public_gallery"),
        ),
        review_note="explicit review evidence note",
    )


def stored_review() -> dict:
    document = submission().normalized(
        expected_output_ids=[101, 102], now=datetime(2026, 8, 9, 13, 0, tzinfo=timezone.utc)
    )
    return {**document, "rights_review_batch_id": 5, "request_digest": submission_digest(document)}


def test_review_submission_requires_exact_output_coverage_and_explicit_roles() -> None:
    normalized = submission().normalized(
        expected_output_ids=[101, 102], now=datetime(2026, 8, 9, 13, 0, tzinfo=timezone.utc)
    )
    assert [item["generation_output_id"] for item in normalized["output_decisions"]] == [101, 102]
    assert submission_digest(normalized) == submission_digest(copy.deepcopy(normalized))

    missing = copy.deepcopy(submission())
    object.__setattr__(missing, "output_decisions", missing.output_decisions[:1])
    with pytest.raises(ReviewPolicyError, match="exact source-case output set"):
        missing.normalized(expected_output_ids=[101, 102])

    bad_role = OutputReviewDecision(101, "internal_only", "internal_only", "public_primary")
    with pytest.raises(ReviewPolicyError, match="public output roles require approved"):
        bad_role.normalized()

    missing_note = copy.deepcopy(submission())
    object.__setattr__(missing_note, "review_note", None)
    with pytest.raises(ReviewPolicyError, match="review_note must be explicit"):
        missing_note.normalized(expected_output_ids=[101, 102])


def test_candidate_v2_preserves_source_roles_and_redacts_hidden_outputs() -> None:
    review = stored_review()
    candidate = build_public_case_candidate(case_facts(), review)
    schema = __import__("json").loads(
        (REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(candidate)
    assert candidate["state"] == "publishable"
    assert sum(len(member["public_outputs"]) for member in candidate["generation_members"]) == 2
    assert sum(len(member["hidden_outputs"]) for member in candidate["generation_members"]) == 0
    roles = [
        (output["source_role"], output["public_display_role"])
        for member in candidate["generation_members"]
        for output in member["public_outputs"]
    ]
    assert roles == [("output_primary", "public_primary"), ("output_secondary", "public_gallery")]
    assert candidate["generation_members"][0]["source_claim"] == {
        "evidence_status": "source_claimed",
        "model_raw": "gpt-image-2",
    }
    assert candidate["tags"] == ["multi-output", "studio"]
    assert "object_key" not in repr(candidate)

    hidden_review = copy.deepcopy(review)
    hidden_review["output_decisions"][0]["public_display_role"] = "hidden"
    hidden_review["output_decisions"][1]["public_display_role"] = "public_primary"
    hidden = build_public_case_candidate(case_facts(), hidden_review)
    assert hidden["state"] == "publishable"
    assert sum(len(member["public_outputs"]) for member in hidden["generation_members"]) == 1
    assert sum(len(member["hidden_outputs"]) for member in hidden["generation_members"]) == 1
    only = hidden["generation_members"][1]["public_outputs"][0]
    assert only["source_role"] == "output_secondary"
    assert only["public_display_role"] == "public_primary"


def test_public_identity_scheme_guard_does_not_match_scheme_text_inside_a_normal_id() -> None:
    facts = case_facts()
    facts["generations"][0]["generation_example_id"] = "generation:topic/profile:01-primary"
    candidate = build_public_case_candidate(facts, stored_review())
    schema = __import__("json").loads(
        (REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(candidate)
    assert any(
        member["generation_example_id"].endswith("profile:01-primary")
        for member in candidate["generation_members"]
    )


def test_candidate_states_and_forbidden_locator_fail_closed() -> None:
    assert build_public_case_candidate(case_facts(), None)["state"] == "pending"
    review = stored_review()
    review["prompt_rights"] = "blocked"
    assert effective_review_state(review) == "blocked"
    blocked = build_public_case_candidate(case_facts(), review)
    assert blocked["state"] == "blocked"
    assert all(member["public_outputs"] == [] for member in blocked["generation_members"])

    facts = case_facts()
    facts["generations"][0]["outputs"][0]["object_key"] = "sha256/private"
    with pytest.raises(ReviewPolicyError, match="forbidden"):
        build_public_case_candidate(facts, stored_review())

    claim_facts = case_facts()
    claim_facts["generations"][0]["source_claim"]["parameters_raw"] = {
        "object_locator": "private://bucket/key"
    }
    with pytest.raises(ReviewPolicyError, match="forbidden"):
        build_public_case_candidate(claim_facts, stored_review())

    impossible = build_public_case_candidate(case_facts(), None)
    impossible["state"] = "publishable"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(
            __import__("json").loads(
                (REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
            )
        ).validate(impossible)

    blocked_schema = build_public_case_candidate(case_facts(), stored_review())
    blocked_schema["rights_review"]["prompt_rights"] = "blocked"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(
            __import__("json").loads(
                (REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
            )
        ).validate(blocked_schema)

    url_review = stored_review()
    url_review["original_url"] = "s3://private-bucket/secret-object"
    with pytest.raises(ReviewPolicyError, match="private object locator"):
        build_public_case_candidate(case_facts(), url_review)

    presigned_review = stored_review()
    presigned_review["original_url"] = (
        "https://private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret"
    )
    with pytest.raises(ReviewPolicyError):
        build_public_case_candidate(case_facts(), presigned_review)

    for field in ("native_id", "selector"):
        metadata_facts = case_facts()
        metadata_facts["generations"][0]["outputs"][0]["source_location"][field] = presigned_review[
            "original_url"
        ]
        with pytest.raises(ReviewPolicyError, match="public metadata text"):
            build_public_case_candidate(metadata_facts, stored_review())

    scheme_facts = case_facts()
    scheme_facts["generations"][0]["outputs"][0]["source_location"]["native_id"] = (
        "s3:private-bucket/secret-object"
    )
    with pytest.raises(ReviewPolicyError, match="public metadata text"):
        build_public_case_candidate(scheme_facts, stored_review())

    model_facts = case_facts()
    model_facts["generations"][0]["source_claim"]["model_raw"] = presigned_review["original_url"]
    with pytest.raises(ReviewPolicyError, match="public metadata text"):
        build_public_case_candidate(model_facts, stored_review())

    numeric_ip_review = stored_review()
    numeric_ip_review["original_url"] = "https://0x7f.0.0.1/internal"
    with pytest.raises(ReviewPolicyError, match="numeric IP"):
        build_public_case_candidate(case_facts(), numeric_ip_review)

    identity_targets = (
        ("source_id", lambda facts: facts["source"], "source_id"),
        ("repository_id", lambda facts: facts["source"], "repository_id"),
        ("source_case_key", lambda facts: facts["source"], "source_case_key"),
        ("prompt_id", lambda facts: facts["prompt"], "prompt_id"),
        ("generation_example_id", lambda facts: facts["generations"][0], "generation_example_id"),
    )
    unsafe_identity_values = (
        presigned_review["original_url"],
        "https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "http:0x7f.0.0.1/internal",
        "blob:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "filesystem:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "view-source:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
    )
    for _label, owner, key in identity_targets:
        for unsafe_value in unsafe_identity_values:
            identity_facts = case_facts()
            owner(identity_facts)[key] = unsafe_value
            with pytest.raises(ReviewPolicyError, match="public identifier"):
                build_public_case_candidate(identity_facts, stored_review())
    for key in ("repository_license", "author", "reviewer"):
        for unsafe_value in unsafe_identity_values:
            identity_review = stored_review()
            identity_review[key] = unsafe_value
            with pytest.raises(ReviewPolicyError, match="public identifier"):
                build_public_case_candidate(case_facts(), identity_review)

    schema = jsonschema.Draft202012Validator(
        __import__("json").loads(
            (REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8")
        )
    )
    publishable = build_public_case_candidate(case_facts(), stored_review())
    mutations = []
    presigned = copy.deepcopy(publishable)
    presigned["rights_review"]["original_url"] = presigned_review["original_url"]
    mutations.append(presigned)
    ipv6 = copy.deepcopy(publishable)
    ipv6["generation_members"][0]["public_outputs"][0]["source_location"]["source_url"] = "https://[fd00::1]/object"
    mutations.append(ipv6)
    traversal = copy.deepcopy(publishable)
    traversal["generation_members"][0]["public_outputs"][0]["source_path"] = "dir\\..\\private"
    mutations.append(traversal)
    pending_public = build_public_case_candidate(case_facts(), None)
    pending_public["generation_members"][0]["public_outputs"] = copy.deepcopy(
        publishable["generation_members"][0]["public_outputs"]
    )
    mutations.append(pending_public)
    bad_time = copy.deepcopy(publishable)
    bad_time["rights_review"]["reviewed_at"] = "yesterday"
    mutations.append(bad_time)
    drive_path = copy.deepcopy(publishable)
    drive_path["generation_members"][0]["public_outputs"][0]["source_path"] = "C:/private/object.png"
    mutations.append(drive_path)
    drive_relative_path = copy.deepcopy(publishable)
    drive_relative_path["generation_members"][0]["public_outputs"][0]["source_path"] = (
        "C:private/object.png"
    )
    mutations.append(drive_relative_path)
    scheme_source_path = copy.deepcopy(publishable)
    scheme_source_path["generation_members"][0]["public_outputs"][0]["source_path"] = (
        "s3:private-bucket/secret-object"
    )
    mutations.append(scheme_source_path)
    spaced_scheme_source_path = copy.deepcopy(publishable)
    spaced_scheme_source_path["generation_members"][0]["public_outputs"][0]["source_path"] = (
        " s3:private-bucket/secret-object"
    )
    mutations.append(spaced_scheme_source_path)
    for field in ("native_id", "selector"):
        metadata_url = copy.deepcopy(publishable)
        metadata_url["generation_members"][0]["public_outputs"][0]["source_location"][field] = presigned_review[
            "original_url"
        ]
        mutations.append(metadata_url)
    model_url = copy.deepcopy(publishable)
    model_url["generation_members"][0]["source_claim"]["model_raw"] = presigned_review["original_url"]
    mutations.append(model_url)
    scheme_metadata = copy.deepcopy(publishable)
    scheme_metadata["generation_members"][0]["public_outputs"][0]["source_location"]["native_id"] = (
        "s3:private-bucket/secret-object"
    )
    mutations.append(scheme_metadata)
    spaced_scheme_metadata = copy.deepcopy(publishable)
    spaced_scheme_metadata["generation_members"][0]["public_outputs"][0]["source_location"]["native_id"] = (
        " s3:private-bucket/secret-object"
    )
    mutations.append(spaced_scheme_metadata)
    hidden_extra_primaries = copy.deepcopy(publishable)
    original_member = next(
        member
        for member in hidden_extra_primaries["generation_members"]
        if any(output["public_display_role"] == "public_primary" for output in member["public_outputs"])
    )
    extra_member = copy.deepcopy(original_member)
    extra_member["generation_example_row_id"] += 100000
    extra_member["generation_example_id"] += "-duplicate-primary-member"
    first_extra_output = extra_member["public_outputs"][0]
    first_extra_output["generation_output_id"] += 100000
    second_extra_output = copy.deepcopy(first_extra_output)
    second_extra_output["generation_output_id"] += 1
    second_extra_output["ordinal"] += 1
    first_extra_output["public_display_role"] = "public_primary"
    second_extra_output["public_display_role"] = "public_primary"
    extra_member["public_outputs"] = [first_extra_output, second_extra_output]
    hidden_extra_primaries["generation_members"].append(extra_member)
    mutations.append(hidden_extra_primaries)
    numeric_ip = copy.deepcopy(publishable)
    numeric_ip["rights_review"]["original_url"] = numeric_ip_review["original_url"]
    mutations.append(numeric_ip)
    identity_paths = (
        ("source_id", lambda candidate: candidate["source_case"], "source_id"),
        ("repository_id", lambda candidate: candidate["source_case"], "repository_id"),
        ("source_case_key", lambda candidate: candidate["source_case"], "source_case_key"),
        ("prompt_id", lambda candidate: candidate["prompt"], "prompt_id"),
        ("generation_example_id", lambda candidate: candidate["generation_members"][0], "generation_example_id"),
    )
    for _label, owner, key in identity_paths:
        identity_url = copy.deepcopy(publishable)
        owner(identity_url)[key] = presigned_review["original_url"]
        mutations.append(identity_url)
    for key in ("repository_license", "author", "reviewer"):
        identity_url = copy.deepcopy(publishable)
        identity_url["rights_review"][key] = presigned_review["original_url"]
        mutations.append(identity_url)
    for unsafe_value in unsafe_identity_values[1:]:
        opaque_identity = copy.deepcopy(publishable)
        opaque_identity["source_case"]["source_case_key"] = unsafe_value
        mutations.append(opaque_identity)
        opaque_review_identity = copy.deepcopy(publishable)
        opaque_review_identity["rights_review"]["reviewer"] = unsafe_value
        mutations.append(opaque_review_identity)
    credential_marker_identity = copy.deepcopy(publishable)
    credential_marker_identity["source_case"]["source_case_key"] = "case-x-amz-credential=AKIA_TEST"
    mutations.append(credential_marker_identity)
    embedded_custom_locator = copy.deepcopy(publishable)
    embedded_custom_locator["source_case"]["source_case_key"] = (
        "identity-prefix custom://remote-locator/secret"
    )
    mutations.append(embedded_custom_locator)
    for mutation in mutations:
        with pytest.raises(jsonschema.ValidationError):
            schema.validate(mutation)


def test_candidate_digest_is_stable_and_review_semantics_change_it() -> None:
    first = build_public_case_candidate(case_facts(), stored_review())
    second = build_public_case_candidate(copy.deepcopy(case_facts()), copy.deepcopy(stored_review()))
    assert first == second
    different_batch = stored_review()
    different_batch["rights_review_batch_id"] = 999
    assert build_public_case_candidate(case_facts(), different_batch)["candidate_content_digest"] == first[
        "candidate_content_digest"
    ]
    changed_review = stored_review()
    changed_review["output_decisions"][1]["public_display_role"] = "hidden"
    changed = build_public_case_candidate(case_facts(), changed_review)
    assert changed["candidate_content_digest"] != first["candidate_content_digest"]
