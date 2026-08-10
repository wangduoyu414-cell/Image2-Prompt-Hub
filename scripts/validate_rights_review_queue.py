#!/usr/bin/env python3
"""Validate the six-source rights-review queue and non-activating Candidate v2 contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema
import psycopg
import psycopg.rows
from psycopg.types.json import Jsonb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content.database import ContentDatabaseError, ContentDatabaseSettings
from content.review import (
    OutputReviewDecision,
    ReviewPolicyError,
    ReviewSubmission,
    build_public_case_candidate,
)
from content.review_store import RightsReviewStore
from scripts import validate_phase2_adapters as phase2


class ValidationFailure(RuntimeError):
    pass


def _expect_error(error_code: str, callback: Any) -> str:
    try:
        callback()
    except ContentDatabaseError as exc:
        if exc.error_code != error_code:
            raise ValidationFailure(
                f"expected {error_code}, received {exc.error_code}"
            ) from exc
        return exc.error_code
    raise ValidationFailure(f"operation unexpectedly succeeded; expected {error_code}")


def _output_ids(subject: Mapping[str, Any]) -> list[int]:
    return [
        int(output["generation_output_id"])
        for generation in subject["case_facts"]["generations"]
        for output in generation["outputs"]
    ]


def _submission(
    subject: Mapping[str, Any],
    *,
    key: str,
    expected_latest_batch_id: int | None,
    reviewed_at: datetime,
    hide_one: bool = False,
    reviewer: str = "task-0020r-validator",
) -> ReviewSubmission:
    output_ids = _output_ids(subject)
    decisions: list[OutputReviewDecision] = []
    for index, output_id in enumerate(output_ids):
        hidden = hide_one and index == len(output_ids) - 1 and len(output_ids) > 1
        decisions.append(
            OutputReviewDecision(
                generation_output_id=output_id,
                asset_rights="internal_only" if hidden else "approved",
                display_policy="internal_only" if hidden else "mirror_allowed",
                public_display_role="hidden" if hidden else ("public_primary" if index == 0 else "public_gallery"),
                decision_note="synthetic validation decision",
            )
        )
    return ReviewSubmission(
        source_case_version_id=int(subject["case_facts"]["source_case_version_id"]),
        idempotency_key=key,
        expected_latest_batch_id=expected_latest_batch_id,
        repository_license="synthetic-validation-only",
        prompt_rights="approved",
        author="source-author-placeholder",
        original_url="https://example.invalid/source",
        evidence_url="https://example.invalid/evidence",
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        output_decisions=tuple(decisions),
        review_note="isolated validator data; never publication authority",
    )


def _run_cli(database_url: str, arguments: Sequence[str], *, expected_exit: int = 0) -> dict[str, Any]:
    environment = {**os.environ, "CONTENT_DATABASE_URL": database_url, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "content", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != expected_exit:
        raise ValidationFailure(
            f"review CLI returned {completed.returncode}, expected {expected_exit}: "
            f"{(completed.stderr or completed.stdout)[-1000:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationFailure("review v2 CLI is not JSON-only") from exc
    serialized = json.dumps(payload, sort_keys=True)
    for forbidden in (database_url, "secret_access_key", "object_key", "object_bucket", "object_locator"):
        if forbidden in serialized:
            raise ValidationFailure("review v2 CLI leaked a credential or private object locator")
    return payload


def _submission_payload(submission: ReviewSubmission, subject: Mapping[str, Any]) -> dict[str, Any]:
    return submission.normalized(expected_output_ids=_output_ids(subject), now=datetime.now(timezone.utc))


def _all_queue_items(store: RightsReviewStore) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    first = store.list_queue(limit=500)
    items = list(first["items"])
    for offset in range(500, int(first["subject_count"]), 500):
        items.extend(store.list_queue(limit=500, offset=offset)["items"])
    if len(items) != int(first["subject_count"]):
        raise ValidationFailure("rights-review queue pagination did not cover every subject")
    return first, items


def _assert_database_guards(
    database_url: str,
    store: RightsReviewStore,
    untouched_subject: Mapping[str, Any],
    batch_id: int,
    foreign_output_id: int,
) -> dict[str, Any]:
    before = store.debug_counts()
    case_version_id = int(untouched_subject["case_facts"]["source_case_version_id"])
    try:
        with psycopg.connect(database_url) as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO content.rights_review_batches_v2
                      (source_case_version_id, idempotency_key, request_digest, expected_latest_batch_id,
                       repository_license, prompt_rights, author, original_url, evidence_url, reviewer, reviewed_at, review_note)
                    VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        case_version_id,
                        "incomplete-" + uuid.uuid4().hex,
                        "0" * 64,
                        "synthetic-validation-only",
                        "approved",
                        "source-author-placeholder",
                        "https://example.invalid/source",
                        "https://example.invalid/evidence",
                        "task-0020r-validator",
                        datetime.now(timezone.utc),
                        "synthetic incomplete batch",
                    ),
                )
    except psycopg.Error:
        pass
    else:
        raise ValidationFailure("deferred completeness guard accepted an incomplete review batch")
    if store.debug_counts() != before:
        raise ValidationFailure("failed incomplete review transaction left persisted rows")

    with psycopg.connect(database_url) as conn:
        decision_id = int(
            conn.execute(
                "SELECT rights_review_output_decision_id FROM content.rights_review_output_decisions_v2 WHERE rights_review_batch_id=%s ORDER BY rights_review_output_decision_id LIMIT 1",
                (batch_id,),
            ).fetchone()[0]
        )
    mutation_errors: list[str] = []
    for statement, row_id in (
        ("UPDATE content.rights_review_batches_v2 SET reviewer=reviewer WHERE rights_review_batch_id=%s", batch_id),
        ("DELETE FROM content.rights_review_batches_v2 WHERE rights_review_batch_id=%s", batch_id),
        (
            "UPDATE content.rights_review_output_decisions_v2 SET decision_note=decision_note WHERE rights_review_output_decision_id=%s",
            decision_id,
        ),
        (
            "DELETE FROM content.rights_review_output_decisions_v2 WHERE rights_review_output_decision_id=%s",
            decision_id,
        ),
    ):
        try:
            with psycopg.connect(database_url) as conn:
                conn.execute(statement, (row_id,))
        except psycopg.Error as exc:
            mutation_errors.append(type(exc).__name__)
        else:
            raise ValidationFailure("append-only review persistence accepted update/delete")

    before_cross_case = store.debug_counts()
    try:
        with psycopg.connect(database_url) as conn:
            with conn.transaction():
                inserted = conn.execute(
                    """
                    INSERT INTO content.rights_review_batches_v2
                      (source_case_version_id, idempotency_key, request_digest, expected_latest_batch_id,
                       repository_license, prompt_rights, author, original_url, evidence_url, reviewer, reviewed_at, review_note)
                    VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING rights_review_batch_id
                    """,
                    (
                        case_version_id,
                        "cross-case-" + uuid.uuid4().hex,
                        "1" * 64,
                        "synthetic-validation-only",
                        "approved",
                        "source-author-placeholder",
                        "https://example.invalid/source",
                        "https://example.invalid/evidence",
                        "task-0020r-validator",
                        datetime.now(timezone.utc),
                        "synthetic cross-case batch",
                    ),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO content.rights_review_output_decisions_v2
                      (rights_review_batch_id, generation_output_id, asset_rights, display_policy, public_display_role)
                    VALUES (%s, %s, 'approved', 'mirror_allowed', 'public_primary')
                    """,
                    (int(inserted[0]), foreign_output_id),
                )
    except psycopg.Error:
        pass
    else:
        raise ValidationFailure("database accepted a cross-case output decision")
    if store.debug_counts() != before_cross_case:
        raise ValidationFailure("cross-case database rejection left persisted rows")
    return {
        "incomplete_batch_rolled_back": True,
        "cross_case_rolled_back": True,
        "immutable_rejections": mutation_errors,
    }


def _create_synthetic_new_revision(
    database_url: str,
    old_case_version_id: int,
    *,
    lock_hold_seconds: float = 0.0,
    run_inserted_event: threading.Event | None = None,
) -> dict[str, Any]:
    revision_sha = hashlib.sha1(uuid.uuid4().bytes).hexdigest()
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as conn:
        with conn.transaction():
            version = conn.execute(
                "SELECT * FROM inventory.source_case_versions WHERE source_case_version_id=%s",
                (old_case_version_id,),
            ).fetchone()
            if not version:
                raise ValidationFailure("synthetic revision base case is missing")
            revision = conn.execute(
                "SELECT * FROM inventory.source_revisions WHERE source_revision_id=%s",
                (version["source_revision_id"],),
            ).fetchone()
            project = conn.execute(
                "SELECT * FROM inventory.source_projects WHERE source_project_id=%s",
                (revision["source_project_id"],),
            ).fetchone()
            old_run = conn.execute(
                "SELECT * FROM inventory.source_adapter_runs WHERE source_adapter_run_id=%s",
                (version["source_adapter_run_id"],),
            ).fetchone()
            prompt = conn.execute(
                "SELECT * FROM inventory.prompt_records WHERE source_case_version_id=%s",
                (old_case_version_id,),
            ).fetchone()
            rights = conn.execute(
                "SELECT * FROM inventory.rights_records WHERE source_case_version_id=%s",
                (old_case_version_id,),
            ).fetchone()
            generations = conn.execute(
                "SELECT * FROM inventory.generation_examples WHERE source_case_version_id=%s ORDER BY generation_example_row_id",
                (old_case_version_id,),
            ).fetchall()
            if not prompt or not rights or not generations:
                raise ValidationFailure("synthetic revision base facts are incomplete")

            new_revision_id = int(
                conn.execute(
                    "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s, %s) RETURNING source_revision_id",
                    (revision["source_project_id"], revision_sha),
                ).fetchone()["source_revision_id"]
            )
            referenced_file_ids = {int(version["source_file_id"]), int(prompt["source_file_id"])}
            asset_rows = conn.execute(
                "SELECT * FROM inventory.asset_sources WHERE source_case_version_id=%s ORDER BY asset_source_id",
                (old_case_version_id,),
            ).fetchall()
            referenced_file_ids.update(int(row["source_file_id"]) for row in asset_rows)
            file_map: dict[int, int] = {}
            for old_file_id in sorted(referenced_file_ids):
                source_file = conn.execute(
                    "SELECT * FROM inventory.source_files WHERE source_file_id=%s", (old_file_id,)
                ).fetchone()
                new_url = str(source_file["source_url"]).replace(str(revision["revision_sha"]), revision_sha)
                file_map[old_file_id] = int(
                    conn.execute(
                        "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s, %s, %s) RETURNING source_file_id",
                        (new_revision_id, source_file["source_path"], new_url),
                    ).fetchone()["source_file_id"]
                )
            new_run_id = int(
                conn.execute(
                    """
                    INSERT INTO inventory.source_adapter_runs
                      (source_revision_id, adapter_id, adapter_version, contract_version,
                       package_idempotency_key, manifest_stable_sha256, semantic_digest,
                       coverage, metrics, manifest, registry_snapshot, state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ready')
                    RETURNING source_adapter_run_id
                    """,
                    (
                        new_revision_id,
                        old_run["adapter_id"],
                        old_run["adapter_version"],
                        old_run["contract_version"],
                        str(old_run["package_idempotency_key"]) + ":synthetic:" + revision_sha,
                        hashlib.sha256(("manifest:" + revision_sha).encode()).hexdigest(),
                        hashlib.sha256(("semantic:" + revision_sha).encode()).hexdigest(),
                        Jsonb(old_run["coverage"]),
                        Jsonb(old_run["metrics"]),
                        Jsonb(old_run["manifest"]),
                        Jsonb(old_run["registry_snapshot"]),
                    ),
                ).fetchone()["source_adapter_run_id"]
            )
            if run_inserted_event is not None:
                run_inserted_event.set()
            if lock_hold_seconds > 0:
                conn.execute("SELECT pg_sleep(%s)", (lock_hold_seconds,))
            new_version_id = int(
                conn.execute(
                    """
                    INSERT INTO inventory.source_case_versions
                      (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                       source_locator, adapter_record, generation_document, contract_state)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'contract_valid')
                    RETURNING source_case_version_id
                    """,
                    (
                        version["source_case_id"],
                        new_revision_id,
                        new_run_id,
                        file_map[int(version["source_file_id"])],
                        Jsonb(version["source_locator"]),
                        Jsonb(version["adapter_record"]),
                        Jsonb(version["generation_document"]),
                    ),
                ).fetchone()["source_case_version_id"]
            )
            new_prompt_id = int(
                conn.execute(
                    """
                    INSERT INTO inventory.prompt_records
                      (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING prompt_record_id
                    """,
                    (
                        new_version_id,
                        prompt["prompt_id"],
                        prompt["raw_text"],
                        prompt["language"],
                        file_map[int(prompt["source_file_id"])],
                        Jsonb(prompt["source_location"]),
                        prompt["raw_text_sha256"],
                    ),
                ).fetchone()["prompt_record_id"]
            )
            conn.execute(
                """
                INSERT INTO inventory.rights_records
                  (source_case_version_id, prompt_rights_status, asset_rights_status, evidence_urls, note)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    new_version_id,
                    rights["prompt_rights_status"],
                    rights["asset_rights_status"],
                    Jsonb(rights["evidence_urls"]),
                    rights["note"],
                ),
            )
            asset_map: dict[int, int] = {}
            for asset in asset_rows:
                asset_map[int(asset["asset_source_id"])] = int(
                    conn.execute(
                        """
                        INSERT INTO inventory.asset_sources
                          (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING asset_source_id
                        """,
                        (
                            new_version_id,
                            asset["asset_ref_id"],
                            file_map[int(asset["source_file_id"])],
                            asset["content_sha256"],
                            asset["role"],
                            Jsonb(asset["source_location"]),
                        ),
                    ).fetchone()["asset_source_id"]
                )
            for generation in generations:
                new_generation_id = int(
                    conn.execute(
                        """
                        INSERT INTO inventory.generation_examples
                          (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                        VALUES (%s, %s, %s, %s, 'contract_valid')
                        RETURNING generation_example_row_id
                        """,
                        (
                            generation["generation_example_id"],
                            new_version_id,
                            new_prompt_id,
                            Jsonb(generation["source_claim"]),
                        ),
                    ).fetchone()["generation_example_row_id"]
                )
                for table, id_column in (("generation_inputs", "generation_input_id"), ("generation_outputs", "generation_output_id")):
                    rows = conn.execute(
                        f"SELECT * FROM inventory.{table} WHERE generation_example_row_id=%s ORDER BY ordinal, {id_column}",
                        (generation["generation_example_row_id"],),
                    ).fetchall()
                    for item in rows:
                        conn.execute(
                            f"INSERT INTO inventory.{table}(generation_example_row_id, ordinal, asset_source_id) VALUES (%s, %s, %s)",
                            (new_generation_id, item["ordinal"], asset_map[int(item["asset_source_id"])]),
                        )
                pairing_rows = conn.execute(
                    "SELECT * FROM inventory.pairing_evidence WHERE generation_example_row_id=%s ORDER BY ordinal",
                    (generation["generation_example_row_id"],),
                ).fetchall()
                for pairing in pairing_rows:
                    conn.execute(
                        "INSERT INTO inventory.pairing_evidence(generation_example_row_id, ordinal, method, status, evidence) VALUES (%s, %s, %s, %s, %s)",
                        (
                            new_generation_id,
                            pairing["ordinal"],
                            pairing["method"],
                            pairing["status"],
                            Jsonb(pairing["evidence"]),
                        ),
                    )
    return {
        "source_id": str(project["source_id"]),
        "revision_sha": revision_sha,
        "source_case_version_id": new_version_id,
    }


def _integration(
    database_url: str,
    _endpoint: str,
    _access_key: str,
    _secret_key: str,
    run_root: Path,
) -> Mapping[str, Any]:
    store = RightsReviewStore(ContentDatabaseSettings(database_url))
    store.assert_migrated()
    queue, queue_items = _all_queue_items(store)
    expected_states = {
        "pending": 1513,
        "review_required": 0,
        "publishable": 0,
        "internal_only": 0,
        "blocked": 0,
    }
    if queue["subject_count"] != 1513 or queue["output_count"] != 1930 or queue["state_counts"] != expected_states:
        raise ValidationFailure("initial rights-review queue does not close at 1513 subjects / 1930 outputs")
    single_item = next((item for item in queue_items if item["output_count"] == 1), None)
    erick_item = next(
        (item for item in queue_items if item["source_id"] == "erickkkyt-awesome-gptimage2-prompts" and item["output_count"] > 1),
        None,
    )
    vigo_item = next(
        (item for item in queue_items if item["source_id"] == "vigozhao-ai-visual-prompt-cookbook" and item["output_count"] > 1),
        None,
    )
    selected_ids = {
        int(item["source_case_version_id"])
        for item in (single_item, erick_item, vigo_item)
        if item is not None
    }
    untouched_item = next(
        (item for item in queue_items if int(item["source_case_version_id"]) not in selected_ids),
        None,
    )
    if single_item is None or erick_item is None or vigo_item is None or untouched_item is None:
        raise ValidationFailure("queue did not expose single, Erick, Vigo, and untouched review subjects")

    single = store.inspect_subject(int(single_item["source_case_version_id"]))
    erick = store.inspect_subject(int(erick_item["source_case_version_id"]))
    untouched = store.inspect_subject(int(untouched_item["source_case_version_id"]))
    for subject in (single, erick, untouched):
        if "existing_rights_evidence" not in subject["case_facts"] or any(
            "inputs" not in generation for generation in subject["case_facts"]["generations"]
        ):
            raise ValidationFailure("review subject omitted input or existing rights evidence")
    cli_subject = _run_cli(
        database_url,
        ["inspect-rights-review-subject", "--source-case-version-id", str(vigo_item["source_case_version_id"])],
    )
    vigo = cli_subject.get("result")
    if not isinstance(vigo, Mapping) or "existing_rights_evidence" not in vigo.get("case_facts", {}):
        raise ValidationFailure("real inspect-subject CLI omitted existing rights evidence")
    if any("inputs" not in generation for generation in vigo["case_facts"]["generations"]):
        raise ValidationFailure("real inspect-subject CLI omitted generation inputs")

    now = datetime.now(timezone.utc) - timedelta(seconds=4)
    single_submission = _submission(
        single, key="single-" + uuid.uuid4().hex, expected_latest_batch_id=None, reviewed_at=now
    )
    single_result = store.submit_review(single_submission)
    if single_result["status"] != "recorded" or single_result["review"]["state"] != "publishable":
        raise ValidationFailure("single-output review did not become publishable")
    replay = store.submit_review(single_submission)
    if replay["status"] != "verified_existing" or replay["review"] != single_result["review"]:
        raise ValidationFailure("same idempotency key and facts did not verify the existing batch")
    conflict = _submission(
        single,
        key=single_submission.idempotency_key,
        expected_latest_batch_id=None,
        reviewed_at=now,
        reviewer="different-reviewer",
    )
    idempotency_error = _expect_error("rights_review_v2_idempotency_conflict", lambda: store.submit_review(conflict))
    stale = _submission(single, key="stale-" + uuid.uuid4().hex, expected_latest_batch_id=None, reviewed_at=now)
    stale_error = _expect_error("rights_review_v2_stale", lambda: store.submit_review(stale))

    erick_submission = _submission(
        erick, key="erick-" + uuid.uuid4().hex, expected_latest_batch_id=None, reviewed_at=now, hide_one=True
    )
    erick_result = store.submit_review(erick_submission)
    erick_candidate = store.preview_candidate(int(erick_item["source_case_version_id"]))
    schema = json.loads((REPO_ROOT / "schemas" / "public-case-candidate-v2.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(erick_candidate)

    cli_root = run_root / "review-cli"
    cli_root.mkdir(parents=True, exist_ok=True)
    vigo_submission = _submission(
        vigo, key="vigo-" + uuid.uuid4().hex, expected_latest_batch_id=None, reviewed_at=now, hide_one=True
    )
    submission_path = cli_root / "vigo-review.json"
    submission_path.write_text(
        json.dumps(_submission_payload(vigo_submission, vigo), ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    cli_submit = _run_cli(database_url, ["submit-rights-review", "--input-json", str(submission_path)])
    vigo_result = cli_submit.get("result")
    if not isinstance(vigo_result, Mapping) or vigo_result.get("status") != "recorded":
        raise ValidationFailure("real submit-review CLI did not record the Vigo batch")
    vigo_batch_id = int(vigo_result["review"]["rights_review_batch_id"])
    cli_batch = _run_cli(database_url, ["inspect-rights-review-batch", "--batch-id", str(vigo_batch_id)])
    if cli_batch.get("result", {}).get("state") != "publishable":
        raise ValidationFailure("real inspect-batch CLI did not return the effective state")
    cli_preview = _run_cli(
        database_url,
        ["preview-public-case-v2", "--source-case-version-id", str(vigo_item["source_case_version_id"])],
    )
    vigo_candidate = cli_preview.get("result")
    if not isinstance(vigo_candidate, Mapping):
        raise ValidationFailure("real preview CLI did not return Candidate v2")
    validator.validate(vigo_candidate)
    missing_cli = _run_cli(
        database_url, ["inspect-rights-review-batch", "--batch-id", "999999999"], expected_exit=92
    )
    if missing_cli.get("error_code") != "rights_review_v2_batch_missing":
        raise ValidationFailure("real CLI missing-batch error contract drifted")
    parser_cli = _run_cli(database_url, ["inspect-rights-review-subject"], expected_exit=90)
    if parser_cli.get("error_code") != "rights_review_v2_invalid":
        raise ValidationFailure("real CLI parser error is not structured JSON")

    candidates = {"erick": (erick, erick_candidate), "vigo": (vigo, vigo_candidate)}
    for label, (subject, candidate) in candidates.items():
        output_count = len(_output_ids(subject))
        public_count = sum(len(member["public_outputs"]) for member in candidate["generation_members"])
        hidden_count = sum(len(member["hidden_outputs"]) for member in candidate["generation_members"])
        primary_count = sum(
            output["public_display_role"] == "public_primary"
            for member in candidate["generation_members"]
            for output in member["public_outputs"]
        )
        if (
            candidate["state"] != "publishable"
            or public_count != output_count - 1
            or hidden_count != 1
            or primary_count != 1
        ):
            raise ValidationFailure(f"{label} Candidate v2 role/redaction projection is incorrect")
        hidden_id = _output_ids(subject)[-1]
        public_ids = {
            int(output["generation_output_id"])
            for member in candidate["generation_members"]
            for output in member["public_outputs"]
        }
        candidate_text = json.dumps(candidate, sort_keys=True)
        if hidden_id in public_ids or any(
            key in candidate_text
            for key in ("object_key", "object_bucket", "object_locator", "storage_locator", "parameters_raw")
        ):
            raise ValidationFailure(f"{label} Candidate v2 leaked hidden/private facts")

    poisoned_facts = copy.deepcopy(erick["case_facts"])
    poisoned_facts["generations"][0]["source_claim"]["parameters_raw"] = {
        "object_locator": "private://bucket/key"
    }
    try:
        build_public_case_candidate(poisoned_facts, erick_result["review"])
    except ReviewPolicyError:
        locator_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted source-claim object locator injection")
    poisoned_review = copy.deepcopy(erick_result["review"])
    poisoned_review["original_url"] = "s3://private-bucket/secret-object"
    try:
        build_public_case_candidate(erick["case_facts"], poisoned_review)
    except ReviewPolicyError:
        url_locator_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted review URL object locator injection")
    presigned_url = (
        "https://private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret"
    )
    presigned_review = copy.deepcopy(erick_result["review"])
    presigned_review["original_url"] = presigned_url
    try:
        build_public_case_candidate(erick["case_facts"], presigned_review)
    except ReviewPolicyError:
        presigned_url_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted a presigned object-store URL")
    rejected_metadata_fields: list[str] = []
    for field in ("native_id", "selector"):
        poisoned_metadata_facts = copy.deepcopy(erick["case_facts"])
        poisoned_metadata_facts["generations"][0]["outputs"][0]["source_location"][field] = presigned_url
        try:
            build_public_case_candidate(poisoned_metadata_facts, erick_result["review"])
        except ReviewPolicyError:
            rejected_metadata_fields.append(field)
        else:
            raise ValidationFailure(f"Candidate policy accepted a presigned URL in source_location.{field}")
    poisoned_model_facts = copy.deepcopy(erick["case_facts"])
    poisoned_model_facts["generations"][0]["source_claim"]["model_raw"] = presigned_url
    try:
        build_public_case_candidate(poisoned_model_facts, erick_result["review"])
    except ReviewPolicyError:
        rejected_metadata_fields.append("model_raw")
    else:
        raise ValidationFailure("Candidate policy accepted a presigned URL in source_claim.model_raw")
    scheme_metadata_facts = copy.deepcopy(erick["case_facts"])
    scheme_metadata_facts["generations"][0]["outputs"][0]["source_location"]["native_id"] = (
        "s3:private-bucket/secret-object"
    )
    try:
        build_public_case_candidate(scheme_metadata_facts, erick_result["review"])
    except ReviewPolicyError:
        scheme_metadata_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted a scheme-form storage locator in public metadata")
    rejected_identity_fields: list[str] = []
    identity_targets = (
        ("source_id", lambda facts: facts["source"], "source_id"),
        ("repository_id", lambda facts: facts["source"], "repository_id"),
        ("source_case_key", lambda facts: facts["source"], "source_case_key"),
        ("prompt_id", lambda facts: facts["prompt"], "prompt_id"),
        ("generation_example_id", lambda facts: facts["generations"][0], "generation_example_id"),
    )
    for label, owner, key in identity_targets:
        poisoned_identity_facts = copy.deepcopy(erick["case_facts"])
        owner(poisoned_identity_facts)[key] = presigned_url
        try:
            build_public_case_candidate(poisoned_identity_facts, erick_result["review"])
        except ReviewPolicyError:
            rejected_identity_fields.append(label)
        else:
            raise ValidationFailure(f"Candidate policy accepted a presigned URL in {label}")
    opaque_identity_values = (
        "https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "http:0x7f.0.0.1/internal",
        "blob:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "filesystem:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
        "view-source:https:private-bucket.s3.amazonaws.com/key?X-Amz-Credential=AKIA_TEST&X-Amz-Signature=secret",
    )
    rejected_opaque_identity_fields: list[str] = []
    for label, owner, key in identity_targets:
        for unsafe_value in opaque_identity_values:
            opaque_identity_facts = copy.deepcopy(erick["case_facts"])
            owner(opaque_identity_facts)[key] = unsafe_value
            try:
                build_public_case_candidate(opaque_identity_facts, erick_result["review"])
            except ReviewPolicyError:
                rejected_opaque_identity_fields.append(f"{label}:{unsafe_value.split(':', 1)[0]}")
            else:
                raise ValidationFailure(f"Candidate policy accepted an opaque URL in {label}")
    for key in ("repository_license", "author", "reviewer"):
        for unsafe_value in opaque_identity_values:
            opaque_identity_review = copy.deepcopy(erick_result["review"])
            opaque_identity_review[key] = unsafe_value
            try:
                build_public_case_candidate(erick["case_facts"], opaque_identity_review)
            except ReviewPolicyError:
                rejected_opaque_identity_fields.append(f"{key}:{unsafe_value.split(':', 1)[0]}")
            else:
                raise ValidationFailure(f"Candidate policy accepted an opaque URL in review {key}")
    numeric_ip_url = "https://0x7f.0.0.1/internal"
    numeric_ip_review = copy.deepcopy(erick_result["review"])
    numeric_ip_review["original_url"] = numeric_ip_url
    try:
        build_public_case_candidate(erick["case_facts"], numeric_ip_review)
    except ReviewPolicyError:
        numeric_ip_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted a noncanonical numeric IP URL")
    poisoned_url_facts = copy.deepcopy(erick["case_facts"])
    poisoned_url_facts["prompt"]["source_url"] = "s3://private-bucket/secret-object"
    try:
        build_public_case_candidate(poisoned_url_facts, erick_result["review"])
    except ReviewPolicyError:
        source_url_locator_injection = "rejected"
    else:
        raise ValidationFailure("Candidate policy accepted source URL object locator injection")
    impossible = copy.deepcopy(erick_candidate)
    impossible["rights_review"] = None
    for member in impossible["generation_members"]:
        member["public_outputs"] = []
    try:
        validator.validate(impossible)
    except jsonschema.ValidationError:
        impossible_schema = "rejected"
    else:
        raise ValidationFailure("Candidate schema accepted an impossible publishable document")
    blocked_prompt = copy.deepcopy(erick_candidate)
    blocked_prompt["rights_review"]["prompt_rights"] = "blocked"
    try:
        validator.validate(blocked_prompt)
    except jsonschema.ValidationError:
        blocked_prompt_schema = "rejected"
    else:
        raise ValidationFailure("Candidate schema accepted publishable state with blocked Prompt rights")
    schema_mutations: dict[str, dict[str, Any]] = {}
    schema_mutations["presigned_url"] = copy.deepcopy(erick_candidate)
    schema_mutations["presigned_url"]["rights_review"]["original_url"] = presigned_url
    schema_mutations["private_ipv6"] = copy.deepcopy(erick_candidate)
    schema_mutations["private_ipv6"]["generation_members"][0]["public_outputs"][0]["source_location"][
        "source_url"
    ] = "https://[fd00::1]/object"
    schema_mutations["windows_traversal"] = copy.deepcopy(erick_candidate)
    schema_mutations["windows_traversal"]["generation_members"][0]["public_outputs"][0][
        "source_path"
    ] = "dir\\..\\private"
    schema_mutations["pending_public"] = build_public_case_candidate(erick["case_facts"], None)
    schema_mutations["pending_public"]["generation_members"][0]["public_outputs"] = copy.deepcopy(
        erick_candidate["generation_members"][0]["public_outputs"]
    )
    schema_mutations["bad_reviewed_at"] = copy.deepcopy(erick_candidate)
    schema_mutations["bad_reviewed_at"]["rights_review"]["reviewed_at"] = "yesterday"
    schema_mutations["windows_drive_path"] = copy.deepcopy(erick_candidate)
    schema_mutations["windows_drive_path"]["generation_members"][0]["public_outputs"][0][
        "source_path"
    ] = "C:/private/object.png"
    schema_mutations["windows_drive_relative_path"] = copy.deepcopy(erick_candidate)
    schema_mutations["windows_drive_relative_path"]["generation_members"][0]["public_outputs"][0][
        "source_path"
    ] = "C:private/object.png"
    schema_mutations["scheme_source_path"] = copy.deepcopy(erick_candidate)
    schema_mutations["scheme_source_path"]["generation_members"][0]["public_outputs"][0][
        "source_path"
    ] = "s3:private-bucket/secret-object"
    schema_mutations["spaced_scheme_source_path"] = copy.deepcopy(erick_candidate)
    schema_mutations["spaced_scheme_source_path"]["generation_members"][0]["public_outputs"][0][
        "source_path"
    ] = " s3:private-bucket/secret-object"
    for field in ("native_id", "selector"):
        schema_mutations[f"presigned_{field}"] = copy.deepcopy(erick_candidate)
        schema_mutations[f"presigned_{field}"]["generation_members"][0]["public_outputs"][0][
            "source_location"
        ][field] = presigned_url
    schema_mutations["presigned_model_raw"] = copy.deepcopy(erick_candidate)
    schema_mutations["presigned_model_raw"]["generation_members"][0]["source_claim"]["model_raw"] = presigned_url
    schema_mutations["numeric_ip_url"] = copy.deepcopy(erick_candidate)
    schema_mutations["numeric_ip_url"]["rights_review"]["original_url"] = numeric_ip_url
    schema_mutations["scheme_metadata"] = copy.deepcopy(erick_candidate)
    schema_mutations["scheme_metadata"]["generation_members"][0]["public_outputs"][0]["source_location"][
        "native_id"
    ] = "s3:private-bucket/secret-object"
    schema_mutations["spaced_scheme_metadata"] = copy.deepcopy(erick_candidate)
    schema_mutations["spaced_scheme_metadata"]["generation_members"][0]["public_outputs"][0][
        "source_location"
    ]["native_id"] = " s3:private-bucket/secret-object"
    schema_mutations["hidden_extra_primaries"] = copy.deepcopy(erick_candidate)
    original_primary_member = next(
        member
        for member in schema_mutations["hidden_extra_primaries"]["generation_members"]
        if any(output["public_display_role"] == "public_primary" for output in member["public_outputs"])
    )
    extra_primary_member = copy.deepcopy(original_primary_member)
    extra_primary_member["generation_example_row_id"] += 100000
    extra_primary_member["generation_example_id"] += "-duplicate-primary-member"
    first_extra_primary = extra_primary_member["public_outputs"][0]
    first_extra_primary["generation_output_id"] += 100000
    second_extra_primary = copy.deepcopy(first_extra_primary)
    second_extra_primary["generation_output_id"] += 1
    second_extra_primary["ordinal"] += 1
    first_extra_primary["public_display_role"] = "public_primary"
    second_extra_primary["public_display_role"] = "public_primary"
    extra_primary_member["public_outputs"] = [first_extra_primary, second_extra_primary]
    schema_mutations["hidden_extra_primaries"]["generation_members"].append(extra_primary_member)
    identity_paths = (
        ("source_id", lambda candidate: candidate["source_case"], "source_id"),
        ("repository_id", lambda candidate: candidate["source_case"], "repository_id"),
        ("source_case_key", lambda candidate: candidate["source_case"], "source_case_key"),
        ("prompt_id", lambda candidate: candidate["prompt"], "prompt_id"),
        ("generation_example_id", lambda candidate: candidate["generation_members"][0], "generation_example_id"),
    )
    for label, owner, key in identity_paths:
        schema_mutations[f"presigned_{label}"] = copy.deepcopy(erick_candidate)
        owner(schema_mutations[f"presigned_{label}"])[key] = presigned_url
    for key in ("repository_license", "author", "reviewer"):
        schema_mutations[f"presigned_review_{key}"] = copy.deepcopy(erick_candidate)
        schema_mutations[f"presigned_review_{key}"]["rights_review"][key] = presigned_url
    for scheme, unsafe_value in zip(
        ("https", "http", "blob", "filesystem", "view_source"), opaque_identity_values, strict=True
    ):
        schema_mutations[f"opaque_{scheme}_identity"] = copy.deepcopy(erick_candidate)
        schema_mutations[f"opaque_{scheme}_identity"]["source_case"]["source_case_key"] = unsafe_value
        schema_mutations[f"opaque_{scheme}_review_identity"] = copy.deepcopy(erick_candidate)
        schema_mutations[f"opaque_{scheme}_review_identity"]["rights_review"]["reviewer"] = unsafe_value
    schema_mutations["credential_marker_identity"] = copy.deepcopy(erick_candidate)
    schema_mutations["credential_marker_identity"]["source_case"]["source_case_key"] = (
        "case-x-amz-credential=AKIA_TEST"
    )
    schema_mutations["embedded_custom_locator_identity"] = copy.deepcopy(erick_candidate)
    schema_mutations["embedded_custom_locator_identity"]["source_case"]["source_case_key"] = (
        "identity-prefix custom://remote-locator/secret"
    )
    rejected_schema_mutations: list[str] = []
    for label, mutation in schema_mutations.items():
        try:
            validator.validate(mutation)
        except jsonschema.ValidationError:
            rejected_schema_mutations.append(label)
        else:
            raise ValidationFailure(f"Candidate schema accepted unsafe mutation: {label}")
    nonpublishable_review = copy.deepcopy(erick_result["review"])
    nonpublishable_review["prompt_rights"] = "blocked"
    nonpublishable = build_public_case_candidate(erick["case_facts"], nonpublishable_review)
    validator.validate(nonpublishable)
    if any(member["public_outputs"] for member in nonpublishable["generation_members"]):
        raise ValidationFailure("nonpublishable Candidate retained public output locators")
    digest_review = copy.deepcopy(erick_result["review"])
    digest_review["rights_review_batch_id"] = int(digest_review["rights_review_batch_id"]) + 100000
    if build_public_case_candidate(erick["case_facts"], digest_review)["candidate_content_digest"] != erick_candidate[
        "candidate_content_digest"
    ]:
        raise ValidationFailure("Candidate digest changes with database-generated batch identity")

    current_batch = int(single_result["review"]["rights_review_batch_id"])
    concurrent_results: list[tuple[str, str]] = []
    result_lock = threading.Lock()

    def writer(index: int) -> None:
        submission = _submission(
            single,
            key=f"concurrent-{index}-" + uuid.uuid4().hex,
            expected_latest_batch_id=current_batch,
            reviewed_at=now + timedelta(seconds=1),
        )
        try:
            status = str(store.submit_review(submission)["status"])
        except ContentDatabaseError as exc:
            status = exc.error_code
        with result_lock:
            concurrent_results.append((str(index), status))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, index) for index in range(2)]
        for future in futures:
            future.result(timeout=60)
    statuses = sorted(status for _index, status in concurrent_results)
    if statuses != ["recorded", "rights_review_v2_stale"]:
        raise ValidationFailure(f"concurrent writers did not close as one winner/one stale: {statuses}")
    latest_single = store.inspect_subject(int(single_item["source_case_version_id"]))["latest_review"]

    malformed = ReviewSubmission(
        **{
            **single_submission.__dict__,
            "idempotency_key": "partial-" + uuid.uuid4().hex,
            "expected_latest_batch_id": latest_single["rights_review_batch_id"],
            "output_decisions": (),
        }
    )
    before_partial = store.debug_counts()
    partial_error = _expect_error("rights_review_v2_invalid", lambda: store.submit_review(malformed))
    future_error = _expect_error(
        "rights_review_v2_invalid",
        lambda: store.submit_review(
            _submission(
                single,
                key="future-" + uuid.uuid4().hex,
                expected_latest_batch_id=int(latest_single["rights_review_batch_id"]),
                reviewed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        ),
    )
    backward_error = _expect_error(
        "rights_review_v2_invalid",
        lambda: store.submit_review(
            _submission(
                single,
                key="backward-" + uuid.uuid4().hex,
                expected_latest_batch_id=int(latest_single["rights_review_batch_id"]),
                reviewed_at=now - timedelta(days=1),
            )
        ),
    )
    if store.debug_counts() != before_partial:
        raise ValidationFailure("invalid partial/time submissions changed persisted review counts")

    database_guards = _assert_database_guards(
        database_url,
        store,
        untouched,
        int(erick_result["review"]["rights_review_batch_id"]),
        _output_ids(single)[0],
    )
    final_queue = store.list_queue(limit=1)
    if final_queue["state_counts"]["publishable"] != 3 or final_queue["state_counts"]["pending"] != 1510:
        raise ValidationFailure("effective queue states did not reflect the three reviewed source cases")
    cli_queue = _run_cli(database_url, ["list-rights-review-queue", "--limit", "1"])
    if cli_queue.get("result", {}).get("subject_count") != 1513:
        raise ValidationFailure("real list queue CLI did not expose all six-source subjects")

    revision_started = threading.Event()
    revision_holder: dict[str, Any] = {}

    def revision_writer() -> None:
        try:
            revision_holder["result"] = _create_synthetic_new_revision(
                database_url,
                int(single_item["source_case_version_id"]),
                lock_hold_seconds=0.75,
                run_inserted_event=revision_started,
            )
        except BaseException as exc:
            revision_holder["error"] = exc

    revision_thread = threading.Thread(target=revision_writer, name="task0020r-ready-revision-writer")
    revision_thread.start()
    if not revision_started.wait(timeout=30):
        raise ValidationFailure("synthetic ready revision did not acquire the shared project fence")
    race_error = _expect_error(
        "rights_review_v2_target_missing",
        lambda: store.submit_review(
            _submission(
                single,
                key="revision-race-" + uuid.uuid4().hex,
                expected_latest_batch_id=int(latest_single["rights_review_batch_id"]),
                reviewed_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
        ),
    )
    revision_thread.join(timeout=60)
    if revision_thread.is_alive() or "error" in revision_holder or not isinstance(revision_holder.get("result"), Mapping):
        raise ValidationFailure("synthetic ready revision did not finish after the shared project fence test")
    revision = dict(revision_holder["result"])
    latest_selection = store.latest_ready_revision_selection()
    if latest_selection.get(revision["source_id"]) != revision["revision_sha"]:
        raise ValidationFailure("latest revision selection did not move to the synthetic ready revision")
    revised_queue = store.list_queue(revision_selection=latest_selection, limit=500)
    revised_item = next(
        (
            item
            for item in revised_queue["items"]
            if int(item["source_case_version_id"]) == int(revision["source_case_version_id"])
        ),
        None,
    )
    if revised_item is None or revised_item["state"] != "pending" or revised_item["latest_batch_id"] is not None:
        raise ValidationFailure("new source-case revision inherited an old review instead of returning to pending")
    historical_replay = store.submit_review(single_submission)
    if historical_replay["status"] != "verified_existing" or historical_replay["review"] != single_result["review"]:
        raise ValidationFailure("exact idempotent replay failed after source revision supersession")
    historical_submit_error = _expect_error(
        "rights_review_v2_target_missing",
        lambda: store.submit_review(
            _submission(
                single,
                key="historical-" + uuid.uuid4().hex,
                expected_latest_batch_id=int(latest_single["rights_review_batch_id"]),
                reviewed_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
        ),
    )

    with psycopg.connect(database_url) as conn:
        legacy = conn.execute("SELECT count(*) FROM content.rights_review_events").fetchone()[0]
        current = conn.execute(
            """
            SELECT version.included_count
            FROM content.publication_current AS current
            JOIN content.publication_versions AS version
              ON version.publication_version_id=current.publication_version_id
            WHERE current.singleton=true
            """
        ).fetchone()
    if int(legacy) != 0 or current is None or int(current[0]) != 0:
        raise ValidationFailure("review v2 changed legacy review events or current Publication v1")
    return {
        "initial_queue": {"subject_count": 1513, "output_count": 1930, "pending": 1513},
        "representative_subjects": {
            "single_output_source": single_item["source_id"],
            "erick_output_count": len(_output_ids(erick)),
            "vigo_output_count": len(_output_ids(vigo)),
            "review_context_includes_inputs_and_rights": True,
        },
        "idempotency": {"replay": "verified_existing", "conflict": idempotency_error},
        "stale_expected_latest": stale_error,
        "concurrency": statuses,
        "invalid_submissions": {
            "partial": partial_error,
            "future": future_error,
            "backward": backward_error,
        },
        "database_guards": database_guards,
        "candidate_v2": {
            "erick_digest": erick_candidate["candidate_content_digest"],
            "vigo_digest": vigo_candidate["candidate_content_digest"],
            "locator_injection": locator_injection,
            "url_locator_injection": url_locator_injection,
            "presigned_url_injection": presigned_url_injection,
            "rejected_metadata_fields": rejected_metadata_fields,
            "numeric_ip_injection": numeric_ip_injection,
            "scheme_metadata_injection": scheme_metadata_injection,
            "rejected_identity_fields": rejected_identity_fields,
            "rejected_opaque_identity_fields": rejected_opaque_identity_fields,
            "source_url_locator_injection": source_url_locator_injection,
            "impossible_schema": impossible_schema,
            "blocked_prompt_schema": blocked_prompt_schema,
            "schema_mutations_rejected": sorted(rejected_schema_mutations),
            "nonpublishable_outputs_redacted": True,
            "batch_id_excluded_from_digest": True,
        },
        "revision_isolation": {
            "new_revision_state": "pending",
            "old_review_inherited": False,
            "concurrent_old_submit": race_error,
            "historical_exact_replay": "verified_existing",
            "historical_submit": historical_submit_error,
        },
        "final_review_counts": store.debug_counts(),
        "legacy_v1": {"rights_review_events": 0, "current_public_cases": 0},
        "real_cli_commands": [
            "list",
            "inspect-subject",
            "submit",
            "inspect-batch",
            "preview",
            "missing-error",
            "parser-error",
        ],
    }


def run() -> dict[str, Any]:
    payload = phase2.run(integration_callback=_integration)
    integration = payload.get("integration_callback")
    if not isinstance(integration, Mapping):
        raise ValidationFailure("Phase 2 validator did not return review integration evidence")
    return {
        "status": "passed",
        "six_source": {
            "global_database_counts": payload["global_database_counts"],
            "database_semantics": payload["database_semantics"],
            "public_api_zero": payload["public_api_zero"],
        },
        "rights_review": dict(integration),
        "legacy_child_validators": payload["child_validators"],
        "compose_cleanup": payload["compose_cleanup"],
        "temporary_runtime_cleaned": payload["temporary_runtime_cleaned"],
        "gates": {f"GATE-{index:03d}": "passed" for index in range(1, 5)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "PASS: rights review queue")
        return 0
    except Exception as exc:
        payload = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:2000]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {payload['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
