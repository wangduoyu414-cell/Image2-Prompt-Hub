"""PostgreSQL Content Core: exact grouping, explicit review, and atomic publication."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .publication import (
    PUBLIC_DISPLAY_POLICIES,
    PublicationPolicyError,
    canonical_key,
    evaluate_publication_gate,
    json_digest,
    make_publication_snapshot,
    publication_content_digest,
    stable_json,
)


class ContentDatabaseError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ContentDatabaseSettings:
    database_url: str

    def validate(self) -> None:
        if not isinstance(self.database_url, str) or not self.database_url:
            raise ContentDatabaseError("content_config_invalid", "PostgreSQL connection configuration is required")
        if not self.database_url.lower().startswith(("postgresql://", "postgres://")):
            raise ContentDatabaseError("content_config_invalid", "PostgreSQL connection must use a postgresql URL")


@dataclass(frozen=True)
class RightsReview:
    generation_example_row_id: int
    repository_license: str
    prompt_rights: str
    asset_rights: str
    author: str
    original_url: str
    evidence_url: str
    reviewer: str
    reviewed_at: datetime
    display_policy: str
    review_note: str | None = None


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


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentDatabaseError("rights_review_invalid", f"{label} is required for an explicit human review")
    return value.strip()


class ContentDatabase:
    """Owns mutable content decisions without changing immutable inventory evidence."""

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
        except PublicationPolicyError as exc:
            raise ContentDatabaseError("content_policy_invalid", str(exc)) from exc
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_database_write_failed", "Content Core transaction failed and was rolled back") from exc
        finally:
            conn.close()

    def assert_migrated(self) -> None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT to_regclass('content.publication_versions') AS publication_versions,
                       to_regclass('content.rights_review_events') AS rights_review_events,
                       to_regclass('content.canonical_memberships') AS canonical_memberships,
                       to_regclass('content.publication_revision_selections') AS publication_revision_selections
                """
            ).fetchone()
            if not row or any(
                row[name] is None
                for name in (
                    "publication_versions",
                    "rights_review_events",
                    "canonical_memberships",
                    "publication_revision_selections",
                )
            ):
                raise ContentDatabaseError("content_schema_not_migrated", "Content Core migration has not been applied")
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_schema_not_migrated", "Content Core migration has not been applied") from exc
        finally:
            conn.close()

    def _canonicalization_rows(
        self,
        conn: psycopg.Connection[Any],
        revision_selection: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        selection_sql, selection_params = self._selection_predicate(revision_selection, source_alias="project", revision_alias="revision")
        rows = conn.execute(
            """
            SELECT g.generation_example_row_id,
                   p.raw_text,
                   g.source_claim,
                   COALESCE(inputs.assets, '[]'::jsonb) AS inputs,
                   COALESCE(outputs.assets, '[]'::jsonb) AS outputs
            FROM inventory.generation_examples AS g
            JOIN inventory.source_case_versions AS v ON v.source_case_version_id = g.source_case_version_id
            JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id = v.source_adapter_run_id
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id = v.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id = revision.source_project_id
            JOIN inventory.prompt_records AS p ON p.prompt_record_id = g.prompt_record_id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(jsonb_build_object('ordinal', i.ordinal, 'content_sha256', source.content_sha256) ORDER BY i.ordinal) AS assets
                FROM inventory.generation_inputs AS i
                JOIN inventory.asset_sources AS source ON source.asset_source_id = i.asset_source_id
                WHERE i.generation_example_row_id = g.generation_example_row_id
            ) AS inputs ON true
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(jsonb_build_object('ordinal', o.ordinal, 'content_sha256', source.content_sha256) ORDER BY o.ordinal) AS assets
                FROM inventory.generation_outputs AS o
                JOIN inventory.asset_sources AS source ON source.asset_source_id = o.asset_source_id
                WHERE o.generation_example_row_id = g.generation_example_row_id
            ) AS outputs ON true
            WHERE g.contract_state = 'contract_valid' AND run.state = 'ready'
            """
            + selection_sql
            + """
            ORDER BY g.generation_example_row_id
            """,
            selection_params,
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_revision_selection(revision_selection: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(revision_selection, Mapping) or not revision_selection:
            raise ContentDatabaseError("publication_selection_invalid", "an explicit nonempty source revision selection is required")
        normalized: dict[str, str] = {}
        for raw_source_id, raw_revision in revision_selection.items():
            source_id = str(raw_source_id).strip()
            revision_sha = str(raw_revision).strip()
            if not source_id or not COMMIT_SHA.fullmatch(revision_sha):
                raise ContentDatabaseError("publication_selection_invalid", "source revision selection is malformed")
            if source_id in normalized:
                raise ContentDatabaseError("publication_selection_invalid", "source revision selection is duplicated")
            normalized[source_id] = revision_sha
        return dict(sorted(normalized.items()))

    @classmethod
    def _selection_predicate(
        cls,
        revision_selection: Mapping[str, str] | None,
        *,
        source_alias: str,
        revision_alias: str,
    ) -> tuple[str, tuple[str, ...]]:
        if revision_selection is None:
            return "", ()
        normalized = cls._normalize_revision_selection(revision_selection)
        predicates = [f"({source_alias}.source_id=%s AND {revision_alias}.revision_sha=%s)" for _ in normalized]
        values: list[str] = []
        for source_id, revision_sha in normalized.items():
            values.extend((source_id, revision_sha))
        return " AND (" + " OR ".join(predicates) + ")", tuple(values)

    def _canonicalize(self, revision_selection: Mapping[str, str] | None = None) -> dict[str, int]:
        """Assign every ready Generation Example to exactly one exact-only group."""

        created_cases = 0
        created_memberships = 0
        facets_recorded = 0
        ready_generation_examples = 0
        with self._transaction() as conn:
            rows = self._canonicalization_rows(conn, revision_selection)
            ready_generation_examples = len(rows)
            for row in rows:
                inputs = _list(row["inputs"])
                outputs = _list(row["outputs"])
                key = canonical_key(
                    raw_prompt=str(row["raw_text"]),
                    input_hashes=[str(asset["content_sha256"]) for asset in inputs],
                    output_hashes=[str(asset["content_sha256"]) for asset in outputs],
                    source_claim=_mapping(row["source_claim"]),
                )
                inserted = conn.execute(
                    "INSERT INTO content.canonical_cases(canonical_key) VALUES (%s) ON CONFLICT (canonical_key) DO NOTHING RETURNING canonical_case_id",
                    (key,),
                ).fetchone()
                if inserted:
                    canonical_case_id = int(inserted["canonical_case_id"])
                    created_cases += 1
                else:
                    existing = conn.execute(
                        "SELECT canonical_case_id FROM content.canonical_cases WHERE canonical_key=%s", (key,)
                    ).fetchone()
                    if not existing:
                        raise ContentDatabaseError("content_internal_error", "canonical case could not be resolved")
                    canonical_case_id = int(existing["canonical_case_id"])
                generation_id = int(row["generation_example_row_id"])
                membership = conn.execute(
                    """
                    INSERT INTO content.canonical_memberships(canonical_case_id, generation_example_row_id)
                    VALUES (%s, %s)
                    ON CONFLICT (generation_example_row_id) DO NOTHING
                    RETURNING canonical_case_id
                    """,
                    (canonical_case_id, generation_id),
                ).fetchone()
                if membership:
                    created_memberships += 1
                else:
                    membership = conn.execute(
                        "SELECT canonical_case_id FROM content.canonical_memberships WHERE generation_example_row_id=%s", (generation_id,)
                    ).fetchone()
                    if not membership:
                        raise ContentDatabaseError("content_internal_error", "canonical membership could not be resolved")
                    if int(membership["canonical_case_id"]) != canonical_case_id:
                        raise ContentDatabaseError("canonical_membership_conflict", "Generation Example already belongs to another Canonical Case")
                facet = conn.execute(
                    """
                    INSERT INTO content.taxonomy_assignments
                      (canonical_case_id, taxonomy_version, classifier_version, tag_value, tag_source, confidence, evidence)
                    VALUES (%s, 'content-taxonomy-v1', 'deterministic-facet-v1', 'exact_generation_facts', 'system_facet', 1.000, %s::jsonb)
                    ON CONFLICT DO NOTHING
                    RETURNING taxonomy_assignment_id
                    """,
                    (canonical_case_id, stable_json({"canonical_key": key, "generation_example_row_id": generation_id})),
                ).fetchone()
                if facet:
                    facets_recorded += 1
        return {
            "ready_generation_examples": ready_generation_examples,
            "created_canonical_cases": created_cases,
            "created_memberships": created_memberships,
            "deterministic_facets_recorded": facets_recorded,
        }

    def canonicalize(self) -> dict[str, int]:
        """Legacy full-ready canonicalization retained for existing Content Core callers."""

        return self._canonicalize()

    def canonicalize_revisions(self, revision_selection: Mapping[str, str]) -> dict[str, int]:
        """Canonicalize only a caller-supplied, explicit source revision selection."""

        return self._canonicalize(self._normalize_revision_selection(revision_selection))

    def _canonical_membership_count(self) -> int:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute("SELECT count(*) AS count FROM content.canonical_memberships").fetchone()
            return int(row["count"]) if row else 0
        finally:
            conn.close()

    def _legacy_ready_revision_selection(self, conn: psycopg.Connection[Any]) -> dict[str, str]:
        """Freeze legacy callers to one ready revision per source in the version itself.

        TASK-0016 sync callers never use this compatibility path: they pass the
        exact revision map chosen by the sync control plane.
        """

        rows = conn.execute(
            """
            SELECT DISTINCT ON (project.source_id) project.source_id, revision.revision_sha
            FROM inventory.source_adapter_runs AS run
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id = run.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id = revision.source_project_id
            WHERE run.state='ready'
            ORDER BY project.source_id, run.source_adapter_run_id DESC
            """
        ).fetchall()
        selection = {str(row["source_id"]): str(row["revision_sha"]) for row in rows}
        if not selection:
            raise ContentDatabaseError("publication_selection_invalid", "no ready source revisions are available for publication")
        return selection

    def _resolve_revision_selection(
        self,
        conn: psycopg.Connection[Any],
        revision_selection: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        normalized = self._normalize_revision_selection(revision_selection)
        resolved: list[dict[str, Any]] = []
        for source_id, revision_sha in normalized.items():
            row = conn.execute(
                """
                SELECT project.source_project_id, revision.source_revision_id, project.source_id, revision.revision_sha
                FROM inventory.source_projects AS project
                JOIN inventory.source_revisions AS revision ON revision.source_project_id = project.source_project_id
                WHERE project.source_id=%s AND revision.revision_sha=%s
                  AND EXISTS (
                    SELECT 1 FROM inventory.source_adapter_runs AS run
                    WHERE run.source_revision_id=revision.source_revision_id AND run.state='ready'
                  )
                """,
                (source_id, revision_sha),
            ).fetchone()
            if not row:
                raise ContentDatabaseError("publication_selection_missing", "selected source revision is not ready inventory")
            resolved.append(dict(row))
        return resolved

    @staticmethod
    def _insert_revision_selection(
        conn: psycopg.Connection[Any],
        *,
        publication_version_id: int,
        resolved_selection: Sequence[Mapping[str, Any]],
    ) -> None:
        for row in resolved_selection:
            conn.execute(
                """
                INSERT INTO content.publication_revision_selections
                  (publication_version_id, source_project_id, source_revision_id)
                VALUES (%s, %s, %s)
                """,
                (
                    publication_version_id,
                    int(row["source_project_id"]),
                    int(row["source_revision_id"]),
                ),
            )

    def record_rights_review(self, review: RightsReview) -> dict[str, Any]:
        """Append one explicit human decision; no inventory fact is upgraded or changed."""

        if review.display_policy not in PUBLIC_DISPLAY_POLICIES | {"internal_only", "blocked"}:
            raise ContentDatabaseError("rights_review_invalid", "display policy is not supported")
        if review.prompt_rights not in {"approved", "unknown", "internal_only", "blocked"} or review.asset_rights not in {
            "approved",
            "unknown",
            "internal_only",
            "blocked",
        }:
            raise ContentDatabaseError("rights_review_invalid", "rights status is not supported")
        if not isinstance(review.generation_example_row_id, int) or review.generation_example_row_id <= 0:
            raise ContentDatabaseError("rights_review_invalid", "Generation Example row id is required")
        if review.reviewed_at.tzinfo is None:
            raise ContentDatabaseError("rights_review_invalid", "reviewed_at must include a timezone")
        if review.reviewed_at.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ContentDatabaseError("rights_review_invalid", "reviewed_at cannot be in the future")
        values = (
            _require_text(review.repository_license, "repository license"),
            _require_text(review.author, "author"),
            _require_text(review.original_url, "original URL"),
            _require_text(review.evidence_url, "evidence URL"),
            _require_text(review.reviewer, "reviewer"),
        )
        with self._transaction() as conn:
            exists = conn.execute(
                """
                SELECT 1
                FROM inventory.generation_examples AS g
                JOIN inventory.source_case_versions AS v ON v.source_case_version_id = g.source_case_version_id
                JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id = v.source_adapter_run_id
                WHERE g.generation_example_row_id=%s AND g.contract_state='contract_valid' AND run.state='ready'
                """,
                (review.generation_example_row_id,),
            ).fetchone()
            if not exists:
                raise ContentDatabaseError("rights_review_target_missing", "rights review target is not a ready Generation Example")
            row = conn.execute(
                """
                INSERT INTO content.rights_review_events
                  (generation_example_row_id, repository_license, prompt_rights, asset_rights, author,
                   original_url, evidence_url, reviewer, reviewed_at, display_policy, review_note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING rights_review_event_id, reviewed_at
                """,
                (
                    review.generation_example_row_id,
                    values[0],
                    review.prompt_rights,
                    review.asset_rights,
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    review.reviewed_at,
                    review.display_policy,
                    review.review_note,
                ),
            ).fetchone()
            if not row:
                raise ContentDatabaseError("content_internal_error", "rights review event could not be recorded")
            return {"rights_review_event_id": int(row["rights_review_event_id"]), "reviewed_at": row["reviewed_at"].isoformat()}

    def record_taxonomy_assignment(
        self,
        *,
        canonical_case_id: int,
        taxonomy_version: str,
        classifier_version: str,
        tag_value: str,
        tag_source: str,
        confidence: float,
        evidence: Mapping[str, Any],
    ) -> int:
        """Append a versioned taxonomy fact; callers choose whether it is blocked."""

        if tag_source not in {"source_tag", "system_facet", "editor", "blocked"}:
            raise ContentDatabaseError("taxonomy_invalid", "taxonomy source is not supported")
        with self._transaction() as conn:
            row = conn.execute(
                """
                INSERT INTO content.taxonomy_assignments
                  (canonical_case_id, taxonomy_version, classifier_version, tag_value, tag_source, confidence, evidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT DO NOTHING
                RETURNING taxonomy_assignment_id
                """,
                (canonical_case_id, taxonomy_version, classifier_version, tag_value, tag_source, confidence, stable_json(dict(evidence))),
            ).fetchone()
            if row:
                return int(row["taxonomy_assignment_id"])
            existing = conn.execute(
                """
                SELECT taxonomy_assignment_id FROM content.taxonomy_assignments
                WHERE canonical_case_id=%s AND taxonomy_version=%s AND classifier_version=%s AND tag_value=%s AND tag_source=%s
                """,
                (canonical_case_id, taxonomy_version, classifier_version, tag_value, tag_source),
            ).fetchone()
            if not existing:
                raise ContentDatabaseError("content_internal_error", "taxonomy assignment could not be resolved")
            return int(existing["taxonomy_assignment_id"])

    def _publication_facts(
        self,
        conn: psycopg.Connection[Any],
        revision_selection: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        selection_sql, selection_params = self._selection_predicate(revision_selection, source_alias="project", revision_alias="revision")
        rows = conn.execute(
            """
            SELECT g.generation_example_row_id,
                   g.generation_example_id,
                   cm.canonical_case_id,
                   cc.canonical_key,
                   p.prompt_record_id,
                   p.raw_text,
                   g.source_claim,
                   project.source_id,
                   project.repository_id,
                   revision.revision_sha,
                   prompt_file.source_path,
                   prompt_file.source_url,
                   COALESCE(pairing.pairing_status, '') AS pairing_status,
                   review.rights_review_event_id,
                   review.repository_license,
                   review.prompt_rights,
                   review.asset_rights,
                   review.author,
                   review.original_url,
                   review.evidence_url,
                   review.reviewer,
                   review.reviewed_at,
                   review.display_policy
            FROM inventory.generation_examples AS g
            JOIN inventory.source_case_versions AS v ON v.source_case_version_id = g.source_case_version_id
            JOIN inventory.source_adapter_runs AS run ON run.source_adapter_run_id = v.source_adapter_run_id
            JOIN inventory.prompt_records AS p ON p.prompt_record_id = g.prompt_record_id
            JOIN inventory.source_files AS prompt_file ON prompt_file.source_file_id = p.source_file_id
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id = v.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id = revision.source_project_id
            LEFT JOIN content.canonical_memberships AS cm ON cm.generation_example_row_id = g.generation_example_row_id
            LEFT JOIN content.canonical_cases AS cc ON cc.canonical_case_id = cm.canonical_case_id
            LEFT JOIN LATERAL (
                SELECT CASE WHEN count(*) > 0 AND bool_and(status = 'strong') THEN 'strong' ELSE '' END AS pairing_status
                FROM inventory.pairing_evidence
                WHERE generation_example_row_id = g.generation_example_row_id
            ) AS pairing ON true
            LEFT JOIN LATERAL (
                SELECT * FROM content.rights_review_events
                WHERE generation_example_row_id = g.generation_example_row_id
                ORDER BY reviewed_at DESC, rights_review_event_id DESC
                LIMIT 1
            ) AS review ON true
            WHERE g.contract_state='contract_valid' AND run.state='ready'
            """
            + selection_sql
            + """
            ORDER BY g.generation_example_row_id
            """,
            selection_params,
        ).fetchall()
        facts: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            generation_id = int(item["generation_example_row_id"])
            outputs = conn.execute(
                """
                SELECT o.ordinal, source.role, asset.content_sha256, asset.object_key, asset.object_bucket, asset.byte_size,
                       asset.media_type, asset.integrity_state, source_file.source_path, source_file.source_url, source.source_location
                FROM inventory.generation_outputs AS o
                JOIN inventory.asset_sources AS source ON source.asset_source_id = o.asset_source_id
                JOIN inventory.assets AS asset ON asset.content_sha256 = source.content_sha256
                JOIN inventory.source_files AS source_file ON source_file.source_file_id = source.source_file_id
                WHERE o.generation_example_row_id=%s
                ORDER BY o.ordinal
                """,
                (generation_id,),
            ).fetchall()
            inputs = conn.execute(
                """
                SELECT i.ordinal, source.role, asset.content_sha256, asset.object_key, asset.object_bucket, asset.byte_size,
                       asset.media_type, asset.integrity_state, source_file.source_path, source_file.source_url, source.source_location
                FROM inventory.generation_inputs AS i
                JOIN inventory.asset_sources AS source ON source.asset_source_id = i.asset_source_id
                JOIN inventory.assets AS asset ON asset.content_sha256 = source.content_sha256
                JOIN inventory.source_files AS source_file ON source_file.source_file_id = source.source_file_id
                WHERE i.generation_example_row_id=%s
                ORDER BY i.ordinal
                """,
                (generation_id,),
            ).fetchall()
            taxonomy: list[dict[str, Any]] = []
            if item.get("canonical_case_id") is not None:
                taxonomy = [
                    {
                        "taxonomy_version": str(tag["taxonomy_version"]),
                        "classifier_version": str(tag["classifier_version"]),
                        "tag_value": str(tag["tag_value"]),
                        "tag_source": str(tag["tag_source"]),
                        "confidence": float(tag["confidence"]),
                        "evidence": _mapping(tag["evidence"]),
                    }
                    for tag in conn.execute(
                        """
                        SELECT taxonomy_version, classifier_version, tag_value, tag_source, confidence, evidence
                        FROM content.taxonomy_assignments
                        WHERE canonical_case_id=%s
                        ORDER BY taxonomy_assignment_id
                        """,
                        (item["canonical_case_id"],),
                    ).fetchall()
                ]
            review = None
            if item.get("rights_review_event_id") is not None:
                review = {
                    "rights_review_event_id": int(item["rights_review_event_id"]),
                    "repository_license": item["repository_license"],
                    "prompt_rights": item["prompt_rights"],
                    "asset_rights": item["asset_rights"],
                    "author": item["author"],
                    "original_url": item["original_url"],
                    "evidence_url": item["evidence_url"],
                    "reviewer": item["reviewer"],
                    "reviewed_at": item["reviewed_at"].isoformat() if item["reviewed_at"] else "",
                    "display_policy": item["display_policy"],
                }
            facts.append(
                {
                    "generation_example_row_id": generation_id,
                    "generation_example_id": str(item["generation_example_id"]),
                    "canonical_case_id": int(item["canonical_case_id"]) if item.get("canonical_case_id") is not None else None,
                    "canonical_key": str(item["canonical_key"]) if item.get("canonical_key") else "",
                    "prompt_record_id": int(item["prompt_record_id"]),
                    "raw_prompt": str(item["raw_text"]),
                    "source_claim": _mapping(item["source_claim"]),
                    "source": {
                        "source_id": str(item["source_id"]),
                        "repository_id": str(item["repository_id"]),
                        "revision_sha": str(item["revision_sha"]),
                        "source_path": str(item["source_path"]),
                        "source_url": str(item["source_url"]),
                    },
                    "pairing_status": str(item["pairing_status"]),
                    "outputs": [{**dict(output), "source_location": _mapping(output["source_location"])} for output in outputs],
                    "inputs": [{**dict(input_), "source_location": _mapping(input_["source_location"])} for input_ in inputs],
                    "taxonomy": taxonomy,
                    "rights_review": review,
                }
            )
        return facts

    def build_publication(
        self,
        *,
        revision_selection: Mapping[str, str] | None = None,
        failure_point: str | None = None,
    ) -> dict[str, Any]:
        """Freeze one immutable publication version with an explicit revision set.

        ``revision_selection=None`` exists only for the older Content Core CLI;
        it still writes the resolved set into the immutable publication version.
        Sync callers must provide their complete selection explicitly.
        """

        if failure_point not in {None, "before_ready"}:
            raise ContentDatabaseError("publication_failure_point_invalid", "unsupported publication build failure point")
        with self._transaction() as conn:
            selected = (
                self._normalize_revision_selection(revision_selection)
                if revision_selection is not None
                else self._legacy_ready_revision_selection(conn)
            )
            resolved_selection = self._resolve_revision_selection(conn, selected)
            version = conn.execute("INSERT INTO content.publication_versions(state) VALUES ('building') RETURNING publication_version_id").fetchone()
            if not version:
                raise ContentDatabaseError("content_internal_error", "publication version could not be created")
            version_id = int(version["publication_version_id"])
            self._insert_revision_selection(
                conn,
                publication_version_id=version_id,
                resolved_selection=resolved_selection,
            )
            included: list[dict[str, Any]] = []
            excluded_examples = 0
            reasons: Counter[str] = Counter()
            for facts in self._publication_facts(conn, selected):
                decision = evaluate_publication_gate(facts)
                if not decision.included:
                    excluded_examples += 1
                    reasons.update(decision.reason_codes)
                    continue
                snapshot = make_publication_snapshot(facts)
                snapshot_digest = json_digest(snapshot)
                conn.execute(
                    """
                    INSERT INTO content.publication_entries
                      (publication_version_id, canonical_case_id, generation_example_row_id, snapshot, snapshot_digest)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    """,
                    (version_id, facts["canonical_case_id"], facts["generation_example_row_id"], stable_json(snapshot), snapshot_digest),
                )
                included.append({"snapshot": snapshot})
            digest = publication_content_digest(included)
            if failure_point == "before_ready":
                raise ContentDatabaseError("injected_publication_build_failure", "controlled failure before publication version is ready")
            conn.execute(
                """
                UPDATE content.publication_versions
                SET state='ready', content_digest=%s, included_count=%s, excluded_count=%s,
                    reason_counts=%s::jsonb, completed_at=now()
                WHERE publication_version_id=%s AND state='building'
                """,
                (digest, len(included), excluded_examples, stable_json(dict(sorted(reasons.items()))), version_id),
            )
            return {
                "publication_version_id": version_id,
                "state": "ready",
                "content_digest": digest,
                "included_count": len(included),
                "excluded_count": excluded_examples,
                "reason_counts": dict(sorted(reasons.items())),
                "revision_selection": selected,
            }

    def build_publication_for_revisions(
        self,
        revision_selection: Mapping[str, str],
        *,
        failure_point: str | None = None,
    ) -> dict[str, Any]:
        """Build a candidate publication only from the caller's frozen revision map."""

        return self.build_publication(revision_selection=revision_selection, failure_point=failure_point)

    def _assert_version_closed(self, conn: psycopg.Connection[Any], version_id: int) -> dict[str, Any]:
        version = conn.execute(
            """
            SELECT publication_version_id, state, content_digest, included_count, excluded_count, reason_counts
            FROM content.publication_versions WHERE publication_version_id=%s FOR UPDATE
            """,
            (version_id,),
        ).fetchone()
        if not version:
            raise ContentDatabaseError("publication_version_missing", "publication version does not exist")
        if str(version["state"]) not in {"ready", "superseded", "active"}:
            raise ContentDatabaseError("publication_version_not_completed", "publication version is not completed")
        rows = conn.execute(
            "SELECT snapshot FROM content.publication_entries WHERE publication_version_id=%s ORDER BY generation_example_row_id", (version_id,)
        ).fetchall()
        entries = [{"snapshot": _mapping(row["snapshot"])} for row in rows]
        if int(version["included_count"]) != len(entries) or str(version["content_digest"]) != publication_content_digest(entries):
            raise ContentDatabaseError("publication_version_incomplete", "publication version entry closure or digest is invalid")
        return dict(version)

    @staticmethod
    def _publication_case_keys(conn: psycopg.Connection[Any], version_id: int) -> set[str]:
        rows = conn.execute(
            """
            SELECT DISTINCT canonical.canonical_key
            FROM content.publication_entries AS entry
            JOIN content.canonical_cases AS canonical ON canonical.canonical_case_id=entry.canonical_case_id
            WHERE entry.publication_version_id=%s
            """,
            (version_id,),
        ).fetchall()
        return {str(row["canonical_key"]) for row in rows}

    def _assert_no_public_loss(self, conn: psycopg.Connection[Any], target_version_id: int) -> None:
        current = conn.execute(
            "SELECT publication_version_id FROM content.publication_current WHERE singleton=true FOR UPDATE"
        ).fetchone()
        if not current:
            return
        current_id = int(current["publication_version_id"])
        current_keys = self._publication_case_keys(conn, current_id)
        target_keys = self._publication_case_keys(conn, target_version_id)
        missing = sorted(current_keys - target_keys)
        if missing:
            raise ContentDatabaseError(
                "publication_public_loss",
                f"candidate publication would remove {len(missing)} current public canonical cases",
            )

    def _switch_current(
        self, conn: psycopg.Connection[Any], *, version_id: int, event_type: str, failure_point: str | None
    ) -> dict[str, Any]:
        if failure_point not in {None, "after_pointer_before_outbox"}:
            raise ContentDatabaseError("publication_failure_point_invalid", "unsupported publication activation failure point")
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('content-publication-current-v1', 0))")
        target = self._assert_version_closed(conn, version_id)
        if target["state"] == "active":
            current = conn.execute(
                "SELECT publication_version_id FROM content.publication_current WHERE singleton=true FOR UPDATE"
            ).fetchone()
            if current and int(current["publication_version_id"]) == version_id:
                return {"publication_version_id": version_id, "state": "active", "already_current": True}
            raise ContentDatabaseError("publication_current_inconsistent", "active target is not the current publication pointer")
        current = conn.execute(
            "SELECT publication_version_id FROM content.publication_current WHERE singleton=true FOR UPDATE"
        ).fetchone()
        self._assert_no_public_loss(conn, version_id)
        if current:
            current_id = int(current["publication_version_id"])
            conn.execute(
                "UPDATE content.publication_versions SET state='superseded' WHERE publication_version_id=%s AND state='active'",
                (current_id,),
            )
        conn.execute("UPDATE content.publication_versions SET state='active' WHERE publication_version_id=%s", (version_id,))
        conn.execute(
            """
            INSERT INTO content.publication_current(singleton, publication_version_id)
            VALUES (true, %s)
            ON CONFLICT (singleton) DO UPDATE SET publication_version_id=EXCLUDED.publication_version_id, activated_at=now()
            """,
            (version_id,),
        )
        if failure_point == "after_pointer_before_outbox":
            raise ContentDatabaseError("injected_publication_activation_failure", "controlled failure after current pointer switch")
        conn.execute(
            """
            INSERT INTO content.publication_outbox(publication_version_id, event_type, event_document)
            VALUES (%s, %s, %s::jsonb)
            """,
            (version_id, event_type, stable_json({"publication_version_id": version_id, "event_type": event_type})),
        )
        return {
            "publication_version_id": version_id,
            "state": "active",
            "previous_publication_version_id": int(current["publication_version_id"]) if current else None,
            "event_type": event_type,
        }

    def activate_publication(self, version_id: int, *, failure_point: str | None = None) -> dict[str, Any]:
        with self._transaction() as conn:
            return self._switch_current(
                conn, version_id=version_id, event_type="publication_activated", failure_point=failure_point
            )

    def activate_publication_for_sync(
        self,
        *,
        version_id: int,
        sync_run_id: int,
        failure_point: str | None = None,
    ) -> dict[str, Any]:
        """Atomically activate one version, enqueue its event, and complete its sync run."""

        if failure_point not in {None, "after_pointer_before_outbox", "after_outbox_before_sync_completion"}:
            raise ContentDatabaseError("publication_failure_point_invalid", "unsupported sync activation failure point")
        with self._transaction() as conn:
            activation = self._switch_current(
                conn,
                version_id=version_id,
                event_type="publication_activated",
                failure_point="after_pointer_before_outbox" if failure_point == "after_pointer_before_outbox" else None,
            )
            if failure_point == "after_outbox_before_sync_completion":
                raise ContentDatabaseError(
                    "injected_sync_completion_failure",
                    "controlled failure after pointer and outbox before sync completion",
                )
            updated = conn.execute(
                """
                    UPDATE sync.source_sync_runs
                    SET state='completed', publication_version_id=%s,
                        reason_code=NULL, error_code=NULL,
                    result_document=source_sync_runs.result_document || jsonb_build_object(
                        'publication_version_id', %s,
                        'activation', %s::jsonb
                    )
                WHERE sync_run_id=%s AND state='ready'
                RETURNING sync_run_id
                """,
                (version_id, version_id, stable_json(activation), sync_run_id),
            ).fetchone()
            if not updated:
                existing = conn.execute(
                    "SELECT state, publication_version_id FROM sync.source_sync_runs WHERE sync_run_id=%s FOR UPDATE",
                    (sync_run_id,),
                ).fetchone()
                if not existing or str(existing["state"]) != "completed" or int(existing["publication_version_id"] or 0) != version_id:
                    raise ContentDatabaseError("sync_completion_conflict", "sync run is not ready for atomic publication completion")
            return {**activation, "sync_run_id": sync_run_id, "sync_state": "completed"}

    def rollback_publication(self, version_id: int) -> dict[str, Any]:
        with self._transaction() as conn:
            return self._switch_current(
                conn, version_id=version_id, event_type="publication_rolled_back", failure_point=None
            )

    def inspect_publication(self) -> dict[str, Any]:
        """Read only the stored active snapshot; never recalculate against mutable inventory."""

        conn = self._connect(autocommit=True)
        try:
            current = conn.execute(
                """
                SELECT v.publication_version_id, v.content_digest, v.included_count, v.excluded_count, v.reason_counts, v.completed_at
                FROM content.publication_current AS current
                JOIN content.publication_versions AS v ON v.publication_version_id=current.publication_version_id
                WHERE current.singleton=true AND v.state='active'
                """
            ).fetchone()
            if not current:
                return {"state": "no_current", "publication_version": None, "entries": []}
            version_id = int(current["publication_version_id"])
            entries = [
                _mapping(row["snapshot"])
                for row in conn.execute(
                    "SELECT snapshot FROM content.publication_entries WHERE publication_version_id=%s ORDER BY generation_example_row_id",
                    (version_id,),
                ).fetchall()
            ]
            return {
                "state": "active",
                "publication_version": {
                    "publication_version_id": version_id,
                    "content_digest": str(current["content_digest"]),
                    "included_count": int(current["included_count"]),
                    "excluded_count": int(current["excluded_count"]),
                    "reason_counts": _mapping(current["reason_counts"]),
                    "completed_at": current["completed_at"].isoformat() if current["completed_at"] else None,
                },
                "entries": entries,
            }
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_inspect_failed", "unable to inspect current publication snapshot") from exc
        finally:
            conn.close()

    def debug_counts(self) -> dict[str, int]:
        """Internal validator-only count projection; it exposes no credentials or image bytes."""

        conn = self._connect(autocommit=True)
        try:
            tables = (
                "canonical_cases",
                "canonical_memberships",
                "taxonomy_assignments",
                "rights_review_events",
                "publication_versions",
                "publication_revision_selections",
                "publication_entries",
                "publication_current",
                "publication_outbox",
            )
            return {
                table: int(conn.execute(f"SELECT count(*) AS count FROM content.{table}").fetchone()["count"])
                for table in tables
            }
        finally:
            conn.close()

    def inspect_publication_selection(self, version_id: int) -> dict[str, str]:
        """Return one immutable publication version's explicitly stored source revisions."""

        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT project.source_id, revision.revision_sha
                FROM content.publication_revision_selections AS selection
                JOIN inventory.source_projects AS project ON project.source_project_id=selection.source_project_id
                JOIN inventory.source_revisions AS revision ON revision.source_revision_id=selection.source_revision_id
                WHERE selection.publication_version_id=%s
                ORDER BY project.source_id
                """,
                (version_id,),
            ).fetchall()
            return {str(row["source_id"]): str(row["revision_sha"]) for row in rows}
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_inspect_failed", "unable to inspect publication revision selection") from exc
        finally:
            conn.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
