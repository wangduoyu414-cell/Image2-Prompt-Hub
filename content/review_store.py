"""PostgreSQL persistence and queue projection for case-level rights review v2."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .database import ContentDatabaseError, ContentDatabaseSettings
from .review import (
    OutputReviewDecision,
    ReviewPolicyError,
    ReviewSubmission,
    build_public_case_candidate,
    effective_review_state,
    submission_digest,
)


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _mapping(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    parsed = _json_value(value)
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes)):
        return []
    return [dict(item) for item in parsed if isinstance(item, Mapping)]


class RightsReviewStore:
    """Owns review-v2 transactions without changing legacy publication state."""

    def __init__(self, settings: ContentDatabaseSettings) -> None:
        settings.validate()
        self.settings = settings

    def _connect(self, *, autocommit: bool = False) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self.settings.database_url, autocommit=autocommit, row_factory=dict_row)
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_database_unavailable", "unable to connect to configured PostgreSQL") from exc

    @contextmanager
    def _transaction(self) -> Iterator[psycopg.Connection[Any]]:
        conn = self._connect()
        try:
            with conn.transaction():
                yield conn
        except ContentDatabaseError:
            raise
        except ReviewPolicyError as exc:
            raise ContentDatabaseError("rights_review_v2_invalid", str(exc)) from exc
        except psycopg.Error as exc:
            if exc.sqlstate == "40001":
                raise ContentDatabaseError(
                    "rights_review_v2_stale", "expected latest review batch does not match current review authority"
                ) from exc
            if isinstance(exc.sqlstate, str) and exc.sqlstate.startswith("23"):
                raise ContentDatabaseError("rights_review_v2_invalid", "rights review violates its persisted domain") from exc
            raise ContentDatabaseError(
                "rights_review_v2_database_failed", "rights review transaction failed and was rolled back"
            ) from exc
        finally:
            conn.close()

    def assert_migrated(self) -> None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT to_regclass('content.rights_review_batches_v2') AS batches,
                       to_regclass('content.rights_review_output_decisions_v2') AS decisions
                """
            ).fetchone()
            if not row or row["batches"] is None or row["decisions"] is None:
                raise ContentDatabaseError("content_schema_not_migrated", "rights review v2 migration has not been applied")
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_schema_not_migrated", "rights review v2 migration has not been applied") from exc
        finally:
            conn.close()

    @staticmethod
    def _normalize_selection(revision_selection: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(revision_selection, Mapping) or not revision_selection:
            raise ContentDatabaseError("rights_review_v2_selection_invalid", "revision selection must be nonempty")
        result: dict[str, str] = {}
        for raw_source_id, raw_sha in revision_selection.items():
            source_id = str(raw_source_id).strip()
            revision_sha = str(raw_sha).strip()
            if not source_id or COMMIT_SHA.fullmatch(revision_sha) is None:
                raise ContentDatabaseError("rights_review_v2_selection_invalid", "revision selection is malformed")
            if source_id in result:
                raise ContentDatabaseError("rights_review_v2_selection_invalid", "revision selection is duplicated")
            result[source_id] = revision_sha
        return dict(sorted(result.items()))

    @classmethod
    def _selection_predicate(
        cls, revision_selection: Mapping[str, str], *, project_alias: str = "project", revision_alias: str = "revision"
    ) -> tuple[str, tuple[str, ...]]:
        selected = cls._normalize_selection(revision_selection)
        predicates = [f"({project_alias}.source_id=%s AND {revision_alias}.revision_sha=%s)" for _ in selected]
        values: list[str] = []
        for source_id, sha in selected.items():
            values.extend((source_id, sha))
        return "(" + " OR ".join(predicates) + ")", tuple(values)

    def latest_ready_revision_selection(self) -> dict[str, str]:
        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (project.source_id) project.source_id, revision.revision_sha
                FROM inventory.source_adapter_runs AS run
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=run.source_revision_id
                JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
                WHERE run.state='ready'
                ORDER BY project.source_id, run.source_adapter_run_id DESC
                """
            ).fetchall()
            selection = {str(row["source_id"]): str(row["revision_sha"]) for row in rows}
            return self._normalize_selection(selection)
        except psycopg.Error as exc:
            raise ContentDatabaseError("rights_review_v2_read_failed", "unable to resolve latest ready revisions") from exc
        finally:
            conn.close()

    @staticmethod
    def _review_from_row(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if row is None or row.get("rights_review_batch_id") is None:
            return None
        return {
            "rights_review_batch_id": int(row["rights_review_batch_id"]),
            "source_case_version_id": int(row["source_case_version_id"]),
            "idempotency_key": str(row["idempotency_key"]),
            "request_digest": str(row["request_digest"]),
            "expected_latest_batch_id": int(row["expected_latest_batch_id"])
            if row.get("expected_latest_batch_id") is not None
            else None,
            "repository_license": str(row["repository_license"]),
            "prompt_rights": str(row["prompt_rights"]),
            "author": str(row["author"]),
            "original_url": str(row["original_url"]),
            "evidence_url": str(row["evidence_url"]),
            "reviewer": str(row["reviewer"]),
            "reviewed_at": row["reviewed_at"].isoformat() if isinstance(row.get("reviewed_at"), datetime) else str(row["reviewed_at"]),
            "review_note": str(row["review_note"]) if row.get("review_note") is not None else None,
            "output_decisions": sorted(_list(row.get("output_decisions")), key=lambda item: int(item["generation_output_id"])),
        }

    @staticmethod
    def _latest_review(conn: psycopg.Connection[Any], source_case_version_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT batch.*,
                   COALESCE(decisions.items, '[]'::jsonb) AS output_decisions
            FROM content.rights_review_batches_v2 AS batch
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'generation_output_id', decision.generation_output_id,
                        'asset_rights', decision.asset_rights,
                        'display_policy', decision.display_policy,
                        'public_display_role', decision.public_display_role,
                        'decision_note', decision.decision_note
                    ) ORDER BY decision.generation_output_id
                ) AS items
                FROM content.rights_review_output_decisions_v2 AS decision
                WHERE decision.rights_review_batch_id=batch.rights_review_batch_id
            ) AS decisions ON true
            WHERE batch.source_case_version_id=%s
            ORDER BY batch.reviewed_at DESC, batch.rights_review_batch_id DESC
            LIMIT 1
            """,
            (source_case_version_id,),
        ).fetchone()
        return RightsReviewStore._review_from_row(row)

    @staticmethod
    def _project_id(conn: psycopg.Connection[Any], source_case_version_id: int) -> int | None:
        row = conn.execute(
            """
            SELECT revision.source_project_id
            FROM inventory.source_case_versions AS version
            JOIN inventory.source_revisions AS revision
              ON revision.source_revision_id=version.source_revision_id
            WHERE version.source_case_version_id=%s
            """,
            (source_case_version_id,),
        ).fetchone()
        return int(row["source_project_id"]) if row else None

    @staticmethod
    def _output_ids(
        conn: psycopg.Connection[Any], source_case_version_id: int, *, require_latest: bool = True
    ) -> list[int]:
        latest_clause = """
              AND run.source_adapter_run_id=(
                  SELECT max(candidate_run.source_adapter_run_id)
                  FROM inventory.source_adapter_runs AS candidate_run
                  JOIN inventory.source_revisions AS candidate_revision
                    ON candidate_revision.source_revision_id=candidate_run.source_revision_id
                  WHERE candidate_run.state='ready'
                    AND candidate_revision.source_project_id=project.source_project_id
              )
        """ if require_latest else ""
        rows = conn.execute(
            f"""
            SELECT output.generation_output_id
            FROM inventory.generation_examples AS generation
            JOIN inventory.source_case_versions AS version
              ON version.source_case_version_id=generation.source_case_version_id
            JOIN inventory.source_adapter_runs AS run
              ON run.source_adapter_run_id=version.source_adapter_run_id
            JOIN inventory.source_revisions AS revision
              ON revision.source_revision_id=version.source_revision_id
            JOIN inventory.source_projects AS project
              ON project.source_project_id=revision.source_project_id
            JOIN inventory.generation_outputs AS output
              ON output.generation_example_row_id=generation.generation_example_row_id
            WHERE version.source_case_version_id=%s
              AND version.contract_state='contract_valid'
              AND generation.contract_state='contract_valid'
              AND run.state='ready'
              {latest_clause}
            ORDER BY output.generation_output_id
            """,
            (source_case_version_id,),
        ).fetchall()
        return [int(row["generation_output_id"]) for row in rows]

    def submit_review(self, submission: ReviewSubmission) -> dict[str, Any]:
        with self._transaction() as conn:
            project_id = self._project_id(conn, submission.source_case_version_id)
            if project_id is None:
                raise ContentDatabaseError(
                    "rights_review_v2_target_missing", "rights review target is not one source case version"
                )
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('image2-ready-review-project-v2:' || %s::text, 0))",
                (project_id,),
            )
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('image2-rights-review-v2:' || %s::text, 0))",
                (submission.source_case_version_id,),
            )
            key = submission.idempotency_key.strip() if isinstance(submission.idempotency_key, str) else ""
            if not key or len(key) > 200:
                raise ContentDatabaseError("rights_review_v2_invalid", "idempotency key is malformed")
            existing = conn.execute(
                "SELECT rights_review_batch_id, source_case_version_id, request_digest FROM content.rights_review_batches_v2 WHERE idempotency_key=%s",
                (key,),
            ).fetchone()
            if existing:
                historical_ids = self._output_ids(conn, submission.source_case_version_id, require_latest=False)
                if not historical_ids or int(existing["source_case_version_id"]) != submission.source_case_version_id:
                    raise ContentDatabaseError(
                        "rights_review_v2_idempotency_conflict",
                        "idempotency key is already bound to a different review target",
                    )
                normalized = submission.normalized(
                    expected_output_ids=historical_ids, now=datetime.now(timezone.utc)
                )
                digest = submission_digest(normalized)
                if str(existing["request_digest"]) != digest:
                    raise ContentDatabaseError(
                        "rights_review_v2_idempotency_conflict", "idempotency key is already bound to different review facts"
                    )
                review = self.inspect_batch(int(existing["rights_review_batch_id"]), connection=conn)
                return {"status": "verified_existing", "review": review}
            output_ids = self._output_ids(conn, submission.source_case_version_id, require_latest=True)
            if not output_ids:
                raise ContentDatabaseError(
                    "rights_review_v2_target_missing", "rights review target is not the latest ready source case version"
                )
            normalized = submission.normalized(expected_output_ids=output_ids, now=datetime.now(timezone.utc))
            digest = submission_digest(normalized)
            latest = self._latest_review(conn, submission.source_case_version_id)
            latest_id = int(latest["rights_review_batch_id"]) if latest is not None else None
            if latest_id != normalized["expected_latest_batch_id"]:
                raise ContentDatabaseError(
                    "rights_review_v2_stale", "expected latest review batch does not match current review authority"
                )
            batch = conn.execute(
                """
                INSERT INTO content.rights_review_batches_v2
                  (source_case_version_id, idempotency_key, request_digest, expected_latest_batch_id,
                   repository_license, prompt_rights, author, original_url, evidence_url, reviewer,
                   reviewed_at, review_note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING rights_review_batch_id
                """,
                (
                    normalized["source_case_version_id"],
                    normalized["idempotency_key"],
                    digest,
                    normalized["expected_latest_batch_id"],
                    normalized["repository_license"],
                    normalized["prompt_rights"],
                    normalized["author"],
                    normalized["original_url"],
                    normalized["evidence_url"],
                    normalized["reviewer"],
                    normalized["reviewed_at"],
                    normalized["review_note"],
                ),
            ).fetchone()
            if not batch:
                raise ContentDatabaseError("rights_review_v2_database_failed", "review batch could not be created")
            batch_id = int(batch["rights_review_batch_id"])
            for decision in normalized["output_decisions"]:
                conn.execute(
                    """
                    INSERT INTO content.rights_review_output_decisions_v2
                      (rights_review_batch_id, generation_output_id, asset_rights, display_policy,
                       public_display_role, decision_note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        batch_id,
                        decision["generation_output_id"],
                        decision["asset_rights"],
                        decision["display_policy"],
                        decision["public_display_role"],
                        decision["decision_note"],
                    ),
                )
            return {"status": "recorded", "review": self.inspect_batch(batch_id, connection=conn)}

    def inspect_batch(
        self, batch_id: int, *, connection: psycopg.Connection[Any] | None = None
    ) -> dict[str, Any]:
        if not isinstance(batch_id, int) or isinstance(batch_id, bool) or batch_id <= 0:
            raise ContentDatabaseError("rights_review_v2_invalid", "review batch id must be positive")
        owns_connection = connection is None
        conn = connection or self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT batch.*,
                       COALESCE(decisions.items, '[]'::jsonb) AS output_decisions
                FROM content.rights_review_batches_v2 AS batch
                LEFT JOIN LATERAL (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'generation_output_id', decision.generation_output_id,
                            'asset_rights', decision.asset_rights,
                            'display_policy', decision.display_policy,
                            'public_display_role', decision.public_display_role,
                            'decision_note', decision.decision_note
                        ) ORDER BY decision.generation_output_id
                    ) AS items
                    FROM content.rights_review_output_decisions_v2 AS decision
                    WHERE decision.rights_review_batch_id=batch.rights_review_batch_id
                ) AS decisions ON true
                WHERE batch.rights_review_batch_id=%s
                """,
                (batch_id,),
            ).fetchone()
            review = self._review_from_row(row)
            if review is None:
                raise ContentDatabaseError("rights_review_v2_batch_missing", "rights review batch does not exist")
            return {**review, "state": effective_review_state(review)}
        except ContentDatabaseError:
            raise
        except psycopg.Error as exc:
            raise ContentDatabaseError("rights_review_v2_read_failed", "unable to inspect rights review batch") from exc
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def _case_facts(conn: psycopg.Connection[Any], source_case_version_id: int) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT version.source_case_version_id, version.adapter_record, project.source_id, project.repository_id,
                   revision.revision_sha, source_case.source_case_key,
                   prompt.prompt_id, prompt.raw_text, prompt.language,
                   prompt_file.source_path, prompt_file.source_url
            FROM inventory.source_case_versions AS version
            JOIN inventory.source_cases AS source_case ON source_case.source_case_id=version.source_case_id
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id=version.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
            JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id=version.source_adapter_run_id
            JOIN inventory.prompt_records AS prompt ON prompt.source_case_version_id=version.source_case_version_id
            JOIN inventory.source_files AS prompt_file ON prompt_file.source_file_id=prompt.source_file_id
            WHERE version.source_case_version_id=%s AND version.contract_state='contract_valid' AND run.state='ready'
            """,
            (source_case_version_id,),
        ).fetchone()
        if not row:
            raise ContentDatabaseError("rights_review_v2_target_missing", "source case version is not ready")
        rights_row = conn.execute(
            """
            SELECT rights_record_id, prompt_rights_status, asset_rights_status, evidence_urls, note
            FROM inventory.rights_records
            WHERE source_case_version_id=%s
            """,
            (source_case_version_id,),
        ).fetchone()
        if not rights_row:
            raise ContentDatabaseError("rights_review_v2_target_missing", "source case version has no rights evidence")
        generations = []
        generation_rows = conn.execute(
            """
            SELECT generation.generation_example_row_id, generation.generation_example_id, generation.source_claim
            FROM inventory.generation_examples AS generation
            WHERE generation.source_case_version_id=%s AND generation.contract_state='contract_valid'
            ORDER BY generation.generation_example_id
            """,
            (source_case_version_id,),
        ).fetchall()
        for generation in generation_rows:
            inputs = conn.execute(
                """
                SELECT input.generation_input_id, input.ordinal, source.role AS source_role,
                       asset.content_sha256, asset.media_type, asset.byte_size,
                       source_file.source_path, source_file.source_url, source.source_location
                FROM inventory.generation_inputs AS input
                JOIN inventory.asset_sources AS source ON source.asset_source_id=input.asset_source_id
                JOIN inventory.assets AS asset ON asset.content_sha256=source.content_sha256
                JOIN inventory.source_files AS source_file ON source_file.source_file_id=source.source_file_id
                WHERE input.generation_example_row_id=%s
                ORDER BY input.ordinal, input.generation_input_id
                """,
                (generation["generation_example_row_id"],),
            ).fetchall()
            outputs = conn.execute(
                """
                SELECT output.generation_output_id, output.ordinal, source.role AS source_role,
                       asset.content_sha256, asset.media_type, asset.byte_size,
                       source_file.source_path, source_file.source_url, source.source_location
                FROM inventory.generation_outputs AS output
                JOIN inventory.asset_sources AS source ON source.asset_source_id=output.asset_source_id
                JOIN inventory.assets AS asset ON asset.content_sha256=source.content_sha256
                JOIN inventory.source_files AS source_file ON source_file.source_file_id=source.source_file_id
                WHERE output.generation_example_row_id=%s
                ORDER BY output.ordinal, output.generation_output_id
                """,
                (generation["generation_example_row_id"],),
            ).fetchall()
            generations.append(
                {
                    "generation_example_row_id": int(generation["generation_example_row_id"]),
                    "generation_example_id": str(generation["generation_example_id"]),
                    "source_claim": _mapping(generation["source_claim"]),
                    "inputs": [
                        {
                            **dict(item),
                            "generation_input_id": int(item["generation_input_id"]),
                            "ordinal": int(item["ordinal"]),
                            "byte_size": int(item["byte_size"]),
                            "source_location": _mapping(item["source_location"]),
                        }
                        for item in inputs
                    ],
                    "outputs": [
                        {**dict(output), "generation_output_id": int(output["generation_output_id"]), "ordinal": int(output["ordinal"]), "byte_size": int(output["byte_size"]), "source_location": _mapping(output["source_location"])}
                        for output in outputs
                    ],
                }
            )
        return {
            "source_case_version_id": int(row["source_case_version_id"]),
            "public_tags": [str(value) for value in _mapping(row["adapter_record"]).get("raw_tags", []) if isinstance(value, str)],
            "source": {
                "source_id": str(row["source_id"]),
                "repository_id": str(row["repository_id"]),
                "revision_sha": str(row["revision_sha"]),
                "source_case_key": str(row["source_case_key"]),
            },
            "prompt": {
                "prompt_id": str(row["prompt_id"]),
                "raw_text": str(row["raw_text"]),
                "language": str(row["language"]),
                "source_path": str(row["source_path"]),
                "source_url": str(row["source_url"]),
            },
            "existing_rights_evidence": {
                "rights_record_id": int(rights_row["rights_record_id"]),
                "prompt_rights_status": str(rights_row["prompt_rights_status"]),
                "asset_rights_status": str(rights_row["asset_rights_status"]),
                "evidence_urls": _json_value(rights_row["evidence_urls"]),
                "note": str(rights_row["note"]) if rights_row.get("note") is not None else None,
            },
            "generations": generations,
        }

    def inspect_subject(self, source_case_version_id: int) -> dict[str, Any]:
        conn = self._connect(autocommit=True)
        try:
            facts = self._case_facts(conn, source_case_version_id)
            review = self._latest_review(conn, source_case_version_id)
            return {
                "state": effective_review_state(review),
                "case_facts": facts,
                "latest_review": review,
            }
        except ContentDatabaseError:
            raise
        except psycopg.Error as exc:
            raise ContentDatabaseError("rights_review_v2_read_failed", "unable to inspect rights review subject") from exc
        finally:
            conn.close()

    def preview_candidate(self, source_case_version_id: int) -> dict[str, Any]:
        subject = self.inspect_subject(source_case_version_id)
        try:
            return build_public_case_candidate(subject["case_facts"], subject["latest_review"])
        except ReviewPolicyError as exc:
            raise ContentDatabaseError("rights_review_v2_candidate_invalid", str(exc)) from exc

    def list_queue(
        self,
        *,
        revision_selection: Mapping[str, str] | None = None,
        state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        if state is not None and state not in {"pending", "review_required", "publishable", "internal_only", "blocked"}:
            raise ContentDatabaseError("rights_review_v2_invalid", "queue state filter is unsupported")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 500:
            raise ContentDatabaseError("rights_review_v2_invalid", "queue limit must be between 1 and 500")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ContentDatabaseError("rights_review_v2_invalid", "queue offset must be nonnegative")
        selected = self._normalize_selection(revision_selection or self.latest_ready_revision_selection())
        predicate, params = self._selection_predicate(selected)
        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                f"""
                SELECT version.source_case_version_id, project.source_id, revision.revision_sha,
                       source_case.source_case_key, prompt.raw_text,
                       output_count.count AS output_count,
                       latest.rights_review_batch_id, latest.prompt_rights,
                       COALESCE(latest.output_decisions, '[]'::jsonb) AS output_decisions
                FROM inventory.source_case_versions AS version
                JOIN inventory.source_cases AS source_case ON source_case.source_case_id=version.source_case_id
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=version.source_revision_id
                JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
                JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id=version.source_adapter_run_id
                JOIN inventory.prompt_records AS prompt ON prompt.source_case_version_id=version.source_case_version_id
                JOIN LATERAL (
                    SELECT count(*)::integer AS count
                    FROM inventory.generation_examples AS generation
                    JOIN inventory.generation_outputs AS output
                      ON output.generation_example_row_id=generation.generation_example_row_id
                    WHERE generation.source_case_version_id=version.source_case_version_id
                ) AS output_count ON true
                LEFT JOIN LATERAL (
                    SELECT batch.rights_review_batch_id, batch.prompt_rights,
                           COALESCE(decisions.items, '[]'::jsonb) AS output_decisions
                    FROM content.rights_review_batches_v2 AS batch
                    LEFT JOIN LATERAL (
                        SELECT jsonb_agg(jsonb_build_object(
                            'generation_output_id', decision.generation_output_id,
                            'asset_rights', decision.asset_rights,
                            'display_policy', decision.display_policy,
                            'public_display_role', decision.public_display_role,
                            'decision_note', decision.decision_note
                        ) ORDER BY decision.generation_output_id) AS items
                        FROM content.rights_review_output_decisions_v2 AS decision
                        WHERE decision.rights_review_batch_id=batch.rights_review_batch_id
                    ) AS decisions ON true
                    WHERE batch.source_case_version_id=version.source_case_version_id
                    ORDER BY batch.reviewed_at DESC, batch.rights_review_batch_id DESC
                    LIMIT 1
                ) AS latest ON true
                WHERE version.contract_state='contract_valid' AND run.state='ready' AND {predicate}
                ORDER BY project.source_id, source_case.source_case_key
                """,
                params,
            ).fetchall()
            items = []
            state_counts = {name: 0 for name in ("pending", "review_required", "publishable", "internal_only", "blocked")}
            total_outputs = 0
            for row in rows:
                review = None
                if row.get("rights_review_batch_id") is not None:
                    review = {
                        "prompt_rights": str(row["prompt_rights"]),
                        "output_decisions": _list(row["output_decisions"]),
                    }
                item_state = effective_review_state(review)
                state_counts[item_state] += 1
                total_outputs += int(row["output_count"])
                if state is not None and item_state != state:
                    continue
                items.append(
                    {
                        "source_case_version_id": int(row["source_case_version_id"]),
                        "source_id": str(row["source_id"]),
                        "revision_sha": str(row["revision_sha"]),
                        "source_case_key": str(row["source_case_key"]),
                        "prompt_preview": str(row["raw_text"])[:280],
                        "output_count": int(row["output_count"]),
                        "state": item_state,
                        "latest_batch_id": int(row["rights_review_batch_id"])
                        if row.get("rights_review_batch_id") is not None
                        else None,
                    }
                )
            return {
                "revision_selection": selected,
                "subject_count": len(rows),
                "output_count": total_outputs,
                "state_counts": state_counts,
                "filtered_count": len(items),
                "limit": limit,
                "offset": offset,
                "items": items[offset : offset + limit],
            }
        except ContentDatabaseError:
            raise
        except psycopg.Error as exc:
            raise ContentDatabaseError("rights_review_v2_read_failed", "unable to list rights review queue") from exc
        finally:
            conn.close()

    def debug_counts(self) -> dict[str, int]:
        conn = self._connect(autocommit=True)
        try:
            return {
                "rights_review_batches_v2": int(
                    conn.execute("SELECT count(*) AS count FROM content.rights_review_batches_v2").fetchone()["count"]
                ),
                "rights_review_output_decisions_v2": int(
                    conn.execute("SELECT count(*) AS count FROM content.rights_review_output_decisions_v2").fetchone()["count"]
                ),
            }
        finally:
            conn.close()


def submission_from_mapping(value: Mapping[str, Any]) -> ReviewSubmission:
    try:
        reviewed_at = datetime.fromisoformat(str(value["reviewed_at"]).replace("Z", "+00:00"))
        decisions = tuple(
            OutputReviewDecision(
                generation_output_id=int(item["generation_output_id"]),
                asset_rights=str(item["asset_rights"]),
                display_policy=str(item["display_policy"]),
                public_display_role=str(item["public_display_role"]),
                decision_note=str(item["decision_note"]) if item.get("decision_note") is not None else None,
            )
            for item in value["output_decisions"]
        )
        expected = value.get("expected_latest_batch_id")
        return ReviewSubmission(
            source_case_version_id=int(value["source_case_version_id"]),
            idempotency_key=str(value["idempotency_key"]),
            expected_latest_batch_id=int(expected) if expected is not None else None,
            repository_license=str(value["repository_license"]),
            prompt_rights=str(value["prompt_rights"]),
            author=str(value["author"]),
            original_url=str(value["original_url"]),
            evidence_url=str(value["evidence_url"]),
            reviewer=str(value["reviewer"]),
            reviewed_at=reviewed_at,
            output_decisions=decisions,
            review_note=str(value["review_note"]) if value.get("review_note") is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ContentDatabaseError("rights_review_v2_invalid", "review submission JSON is malformed") from exc
