"""PostgreSQL write/read boundary for immutable Public Case Publication v2."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .database import ContentDatabaseError, ContentDatabaseSettings
from .publication import json_digest, stable_json
from .publication_v2 import (
    PublicationV2PolicyError,
    freeze_candidate,
    publication_v2_digest,
    snapshot_digest,
)
from .review import ReviewPolicyError, build_public_case_candidate
from .review_store import RightsReviewStore


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TAKEDOWN_SCOPES = frozenset({"asset", "prompt", "case", "source"})
TAKEDOWN_ACTIONS = frozenset({"remove", "restore"})


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


def _text(value: object, label: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentDatabaseError("publication_v2_invalid", f"{label} must be nonempty text")
    result = value.strip()
    if len(result) > maximum:
        raise ContentDatabaseError("publication_v2_invalid", f"{label} is too long")
    return result


class PublicationV2Store:
    def __init__(self, settings: ContentDatabaseSettings) -> None:
        settings.validate()
        self.settings = settings
        self._reviews = RightsReviewStore(settings)

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
        except PublicationV2PolicyError as exc:
            raise ContentDatabaseError("publication_v2_candidate_invalid", str(exc)) from exc
        except psycopg.Error as exc:
            if isinstance(exc.sqlstate, str) and exc.sqlstate.startswith("23"):
                raise ContentDatabaseError("publication_v2_invalid", "publication v2 violates its persisted authority") from exc
            raise ContentDatabaseError("publication_v2_database_failed", "publication v2 transaction rolled back") from exc
        finally:
            conn.close()

    def assert_migrated(self) -> None:
        conn = self._connect(autocommit=True)
        try:
            row = conn.execute(
                """
                SELECT to_regclass('content.publication_versions_v2') AS versions,
                       to_regclass('content.publication_entries_v2') AS entries,
                       to_regclass('content.takedown_requests_v2') AS takedowns
                """
            ).fetchone()
            if not row or any(row.get(name) is None for name in ("versions", "entries", "takedowns")):
                raise ContentDatabaseError("content_schema_not_migrated", "publication v2 migration has not been applied")
        except psycopg.Error as exc:
            raise ContentDatabaseError("content_schema_not_migrated", "publication v2 migration has not been applied") from exc
        finally:
            conn.close()

    @staticmethod
    def _normalize_selection(revision_selection: Mapping[str, str]) -> dict[str, str]:
        if not isinstance(revision_selection, Mapping) or not revision_selection:
            raise ContentDatabaseError("publication_v2_selection_invalid", "revision selection must be nonempty")
        result: dict[str, str] = {}
        for raw_source_id, raw_sha in revision_selection.items():
            source_id = str(raw_source_id).strip()
            revision_sha = str(raw_sha).strip()
            if not source_id or COMMIT_SHA.fullmatch(revision_sha) is None or source_id in result:
                raise ContentDatabaseError("publication_v2_selection_invalid", "revision selection is malformed")
            result[source_id] = revision_sha
        return dict(sorted(result.items()))

    @staticmethod
    def _resolved_selection(conn: psycopg.Connection[Any], selected: Mapping[str, str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for source_id, revision_sha in selected.items():
            row = conn.execute(
                """
                SELECT project.source_project_id, revision.source_revision_id
                FROM inventory.source_projects project
                JOIN inventory.source_revisions revision ON revision.source_project_id=project.source_project_id
                JOIN inventory.source_adapter_runs run ON run.source_revision_id=revision.source_revision_id
                WHERE project.source_id=%s AND revision.revision_sha=%s AND run.state='ready'
                ORDER BY run.source_adapter_run_id DESC LIMIT 1
                """,
                (source_id, revision_sha),
            ).fetchone()
            if not row:
                raise ContentDatabaseError("publication_v2_selection_invalid", "selected source revision is not ready")
            result.append(
                {
                    "source_id": source_id,
                    "revision_sha": revision_sha,
                    "source_project_id": int(row["source_project_id"]),
                    "source_revision_id": int(row["source_revision_id"]),
                }
            )
        return result

    @staticmethod
    def _effective_takedowns(conn: psycopg.Connection[Any]) -> dict[tuple[str, str], dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (scope_type, scope_key)
                   takedown_request_v2_id, scope_type, scope_key, action, reason_code,
                   evidence_url, note, requested_by, requested_at
            FROM content.takedown_requests_v2
            ORDER BY scope_type, scope_key, requested_at DESC, takedown_request_v2_id DESC
            """
        ).fetchall()
        return {
            (str(row["scope_type"]), str(row["scope_key"])): {
                "takedown_request_v2_id": int(row["takedown_request_v2_id"]),
                "scope_type": str(row["scope_type"]),
                "scope_key": str(row["scope_key"]),
                "action": str(row["action"]),
                "reason_code": str(row["reason_code"]),
                "evidence_url": str(row["evidence_url"]),
                "note": str(row["note"]),
                "requested_by": str(row["requested_by"]),
                "requested_at": row["requested_at"].isoformat(),
            }
            for row in rows
        }

    @staticmethod
    def _active_takedown(
        effective: Mapping[tuple[str, str], Mapping[str, Any]], scope_type: str, scope_key: str
    ) -> Mapping[str, Any] | None:
        record = effective.get((scope_type, scope_key))
        return record if record is not None and record.get("action") == "remove" else None

    @staticmethod
    def _takedown_reason(
        candidate: Mapping[str, Any], effective: Mapping[tuple[str, str], Mapping[str, Any]]
    ) -> str | None:
        source_case = _mapping(candidate.get("source_case"))
        prompt = _mapping(candidate.get("prompt"))
        checks: list[tuple[str, str]] = [
            ("source", str(source_case.get("source_id", ""))),
            (
                "case",
                f"{source_case.get('source_id', '')}:{source_case.get('source_case_key', '')}",
            ),
            ("prompt", f"{source_case.get('source_id', '')}:{prompt.get('prompt_id', '')}"),
        ]
        for member in candidate.get("generation_members", []):
            if not isinstance(member, Mapping):
                continue
            for output in member.get("public_outputs", []):
                if isinstance(output, Mapping):
                    checks.append(("asset", str(output.get("content_sha256", ""))))
        for scope_type, scope_key in checks:
            if scope_key and PublicationV2Store._active_takedown(effective, scope_type, scope_key) is not None:
                return f"takedown_{scope_type}"
        return None

    @staticmethod
    def _apply_takedowns(
        candidate: Mapping[str, Any], effective: Mapping[tuple[str, str], Mapping[str, Any]]
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None, dict[str, Any] | None]:
        document = json.loads(stable_json(candidate))
        source_case = _mapping(document.get("source_case"))
        prompt = _mapping(document.get("prompt"))
        broad_scopes = [
            ("source", str(source_case.get("source_id", ""))),
            ("case", f"{source_case.get('source_id', '')}:{source_case.get('source_case_key', '')}"),
            ("prompt", f"{source_case.get('source_id', '')}:{prompt.get('prompt_id', '')}"),
        ]
        for scope_type, scope_key in broad_scopes:
            record = PublicationV2Store._active_takedown(effective, scope_type, scope_key)
            if scope_key and record is not None:
                return None, [], f"takedown_{scope_type}", dict(record)
        applied: list[dict[str, Any]] = []
        for member in document.get("generation_members", []):
            kept: list[dict[str, Any]] = []
            for output in member.get("public_outputs", []):
                record = PublicationV2Store._active_takedown(
                    effective, "asset", str(output.get("content_sha256", ""))
                )
                if record is None:
                    kept.append(output)
                    continue
                applied.append(dict(record))
                if output.get("public_display_role") == "public_primary":
                    return None, [], "takedown_asset_primary", dict(record)
                member.setdefault("hidden_outputs", []).append({"redacted": True})
            member["public_outputs"] = kept
        return document, applied, None, None

    def record_takedown(
        self,
        *,
        idempotency_key: str,
        scope_type: str,
        scope_key: str,
        action: str,
        reason_code: str,
        evidence_url: str,
        note: str,
        requested_by: str,
        requested_at: datetime,
    ) -> dict[str, Any]:
        key = _text(idempotency_key, "idempotency_key", maximum=200)
        if scope_type not in TAKEDOWN_SCOPES or action not in TAKEDOWN_ACTIONS:
            raise ContentDatabaseError("publication_v2_invalid", "takedown scope or action is unsupported")
        normalized_scope_key = _text(scope_key, "scope_key", maximum=1000)
        if scope_type == "asset" and SHA256.fullmatch(normalized_scope_key) is None:
            raise ContentDatabaseError("publication_v2_invalid", "asset takedown scope must be a lowercase SHA-256")
        if requested_at.tzinfo is None or requested_at.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ContentDatabaseError("publication_v2_invalid", "requested_at must be timezone-aware and not future dated")
        document = {
            "scope_type": scope_type,
            "scope_key": normalized_scope_key,
            "action": action,
            "reason_code": _text(reason_code, "reason_code", maximum=200),
            "evidence_url": _text(evidence_url, "evidence_url", maximum=2000),
            "note": _text(note, "note"),
            "requested_by": _text(requested_by, "requested_by", maximum=200),
            "requested_at": requested_at.astimezone(timezone.utc).isoformat(),
        }
        digest = json_digest(document)
        with self._transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('content-takedown-v2', 0))")
            existing = conn.execute(
                "SELECT takedown_request_v2_id, request_digest FROM content.takedown_requests_v2 WHERE idempotency_key=%s",
                (key,),
            ).fetchone()
            if existing:
                if str(existing["request_digest"]) != digest:
                    raise ContentDatabaseError("publication_v2_idempotency_conflict", "takedown key is bound to different facts")
                return {"status": "verified_existing", "takedown_request_v2_id": int(existing["takedown_request_v2_id"])}
            row = conn.execute(
                """
                INSERT INTO content.takedown_requests_v2
                  (idempotency_key, request_digest, scope_type, scope_key, action, reason_code,
                   evidence_url, note, requested_by, requested_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING takedown_request_v2_id
                """,
                (
                    key,
                    digest,
                    document["scope_type"],
                    document["scope_key"],
                    document["action"],
                    document["reason_code"],
                    document["evidence_url"],
                    document["note"],
                    document["requested_by"],
                    document["requested_at"],
                ),
            ).fetchone()
            if not row:
                raise ContentDatabaseError("publication_v2_database_failed", "takedown request could not be recorded")
            return {"status": "recorded", "takedown_request_v2_id": int(row["takedown_request_v2_id"])}

    def build_publication(
        self,
        *,
        revision_selection: Mapping[str, str],
        created_by: str,
        idempotency_key: str,
        failure_point: str | None = None,
    ) -> dict[str, Any]:
        if failure_point not in {None, "before_ready"}:
            raise ContentDatabaseError("publication_v2_failure_point_invalid", "unsupported publication v2 failure point")
        selected = self._normalize_selection(revision_selection)
        actor = _text(created_by, "created_by", maximum=200)
        request_key = _text(idempotency_key, "idempotency_key", maximum=200)
        request_digest = json_digest({"revision_selection": selected, "created_by": actor})
        with self._transaction() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('content-publication-build-v2:' || %s, 0))",
                (request_key,),
            )
            existing = conn.execute(
                """
                SELECT request.request_digest, version.*
                FROM content.publication_build_requests_v2 request
                JOIN content.publication_versions_v2 version
                  ON version.publication_version_v2_id=request.publication_version_v2_id
                WHERE request.idempotency_key=%s
                """,
                (request_key,),
            ).fetchone()
            if existing:
                if str(existing["request_digest"]) != request_digest:
                    raise ContentDatabaseError(
                        "publication_v2_idempotency_conflict", "build idempotency key is bound to different facts"
                    )
                if str(existing["state"]) not in {"ready", "active", "superseded"}:
                    raise ContentDatabaseError(
                        "publication_v2_version_not_completed", "existing idempotent build is not completed"
                    )
                return {
                    "status": "verified_existing",
                    "publication_version_v2_id": int(existing["publication_version_v2_id"]),
                    "state": str(existing["state"]),
                    "content_digest": str(existing["content_digest"]),
                    "included_count": int(existing["included_count"]),
                    "excluded_count": int(existing["excluded_count"]),
                    "reason_counts": _mapping(existing["reason_counts"]),
                    "revision_selection": selected,
                }
            project_rows: list[dict[str, Any]] = []
            for source_id, revision_sha in selected.items():
                row = conn.execute(
                    """
                    SELECT project.source_project_id
                    FROM inventory.source_projects project
                    JOIN inventory.source_revisions revision ON revision.source_project_id=project.source_project_id
                    JOIN inventory.source_adapter_runs run ON run.source_revision_id=revision.source_revision_id
                    WHERE project.source_id=%s AND revision.revision_sha=%s AND run.state='ready'
                    ORDER BY run.source_adapter_run_id DESC LIMIT 1
                    """,
                    (source_id, revision_sha),
                ).fetchone()
                if not row:
                    raise ContentDatabaseError(
                        "publication_v2_selection_invalid", "selected source revision is not ready"
                    )
                project_rows.append({"source_project_id": int(row["source_project_id"])})
            for item in sorted(project_rows, key=lambda value: int(value["source_project_id"])):
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended('image2-ready-review-project-v2:' || %s::text, 0))",
                    (item["source_project_id"],),
                )
            resolved = self._resolved_selection(conn, selected)
            if {int(item["source_project_id"]) for item in resolved} != {
                int(item["source_project_id"]) for item in project_rows
            }:
                raise ContentDatabaseError("publication_v2_selection_invalid", "selected project authority changed")
            self._assert_selected_revisions_latest(conn, resolved)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('content-takedown-v2', 0))")
            version = conn.execute(
                "INSERT INTO content.publication_versions_v2(state, created_by) VALUES ('building', %s) RETURNING publication_version_v2_id",
                (actor,),
            ).fetchone()
            if not version:
                raise ContentDatabaseError("publication_v2_database_failed", "publication v2 version could not be created")
            version_id = int(version["publication_version_v2_id"])
            conn.execute(
                """
                INSERT INTO content.publication_build_requests_v2
                  (idempotency_key, request_digest, publication_version_v2_id)
                VALUES (%s,%s,%s)
                """,
                (request_key, request_digest, version_id),
            )
            for item in resolved:
                conn.execute(
                    """
                    INSERT INTO content.publication_revision_selections_v2
                      (publication_version_v2_id, source_project_id, source_revision_id)
                    VALUES (%s,%s,%s)
                    """,
                    (version_id, item["source_project_id"], item["source_revision_id"]),
                )
            predicate, params = self._reviews._selection_predicate(selected)
            rows = conn.execute(
                f"""
                SELECT version.source_case_version_id
                FROM inventory.source_case_versions version
                JOIN inventory.source_revisions revision ON revision.source_revision_id=version.source_revision_id
                JOIN inventory.source_projects project ON project.source_project_id=revision.source_project_id
                JOIN inventory.source_adapter_runs run ON run.source_adapter_run_id=version.source_adapter_run_id
                WHERE version.contract_state='contract_valid' AND run.state='ready' AND {predicate}
                  AND run.source_adapter_run_id=(
                    SELECT max(authority_run.source_adapter_run_id)
                    FROM inventory.source_adapter_runs authority_run
                    WHERE authority_run.source_revision_id=version.source_revision_id
                      AND authority_run.state='ready'
                  )
                ORDER BY project.source_id, version.source_case_version_id
                """,
                params,
            ).fetchall()
            effective_takedowns = self._effective_takedowns(conn)
            entries: list[dict[str, Any]] = []
            reasons: Counter[str] = Counter()
            for row in rows:
                source_case_version_id = int(row["source_case_version_id"])
                facts = self._reviews._case_facts(conn, source_case_version_id)
                review = self._reviews._latest_review(conn, source_case_version_id)
                try:
                    candidate = build_public_case_candidate(facts, review)
                except ReviewPolicyError:
                    reasons["candidate_invalid"] += 1
                    conn.execute(
                        """
                        INSERT INTO content.publication_exclusions_v2
                          (publication_version_v2_id, source_case_version_id, reason_code)
                        VALUES (%s,%s,'candidate_invalid')
                        """,
                        (version_id, source_case_version_id),
                    )
                    continue
                if candidate["state"] != "publishable":
                    reason = f"review_{candidate['state']}"
                    reasons[reason] += 1
                    conn.execute(
                        """
                        INSERT INTO content.publication_exclusions_v2
                          (publication_version_v2_id, source_case_version_id, reason_code)
                        VALUES (%s,%s,%s)
                        """,
                        (version_id, source_case_version_id, reason),
                    )
                    continue
                publication_candidate, applied_takedowns, takedown_reason, excluding_takedown = self._apply_takedowns(
                    candidate, effective_takedowns
                )
                if takedown_reason:
                    reasons[takedown_reason] += 1
                    conn.execute(
                        """
                        INSERT INTO content.publication_exclusions_v2
                          (publication_version_v2_id, source_case_version_id, reason_code, takedown_request_v2_id)
                        VALUES (%s,%s,%s,%s)
                        """,
                        (
                            version_id,
                            source_case_version_id,
                            takedown_reason,
                            int(excluding_takedown["takedown_request_v2_id"]) if excluding_takedown else None,
                        ),
                    )
                    continue
                if publication_candidate is None:
                    raise ContentDatabaseError("publication_v2_candidate_invalid", "takedown projection is inconsistent")
                entry = freeze_candidate(publication_candidate)
                conn.execute(
                    """
                    INSERT INTO content.publication_entries_v2
                      (publication_version_v2_id, public_case_key, source_case_version_id,
                       rights_review_batch_id, snapshot, snapshot_digest)
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s)
                    """,
                    (
                        version_id,
                        entry["public_case_key"],
                        entry["source_case_version_id"],
                        entry["rights_review_batch_id"],
                        stable_json(entry),
                        snapshot_digest(entry),
                    ),
                )
                for member in entry["generation_members"]:
                    for output in member["public_outputs"]:
                        asset = conn.execute(
                            """
                            SELECT inventory_asset.object_bucket, inventory_asset.object_key,
                                   inventory_asset.media_type, inventory_asset.byte_size
                            FROM inventory.generation_outputs generation_output
                            JOIN inventory.asset_sources source ON source.asset_source_id=generation_output.asset_source_id
                            JOIN inventory.assets inventory_asset ON inventory_asset.content_sha256=source.content_sha256
                            WHERE generation_output.generation_output_id=%s
                              AND inventory_asset.content_sha256=%s
                            """,
                            (output["generation_output_id"], output["content_sha256"]),
                        ).fetchone()
                        if not asset:
                            raise ContentDatabaseError(
                                "publication_v2_candidate_invalid", "public output is absent from immutable inventory"
                            )
                        policy = str(output["rights"]["display_policy"])
                        conn.execute(
                            """
                            INSERT INTO content.publication_assets_v2
                              (publication_version_v2_id, public_case_key, generation_output_id,
                               content_sha256, object_bucket, object_key, media_type, byte_size,
                               display_policy, public_display_role)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (
                                version_id,
                                entry["public_case_key"],
                                output["generation_output_id"],
                                output["content_sha256"],
                                str(asset["object_bucket"]) if policy != "link_only" else None,
                                str(asset["object_key"]) if policy != "link_only" else None,
                                str(asset["media_type"]),
                                int(asset["byte_size"]),
                                policy,
                                output["public_display_role"],
                            ),
                        )
                for takedown in applied_takedowns:
                    conn.execute(
                        """
                        INSERT INTO content.publication_takedown_applications_v2
                          (publication_version_v2_id, public_case_key, takedown_request_v2_id, effect_type)
                        VALUES (%s,%s,%s,'asset_removed')
                        """,
                        (version_id, entry["public_case_key"], int(takedown["takedown_request_v2_id"])),
                    )
                entries.append(entry)
            digest = publication_v2_digest(entries)
            if failure_point == "before_ready":
                raise ContentDatabaseError("injected_publication_v2_build_failure", "controlled failure before v2 ready")
            conn.execute(
                """
                UPDATE content.publication_versions_v2
                SET state='ready', content_digest=%s, included_count=%s, excluded_count=%s,
                    reason_counts=%s::jsonb, completed_at=now()
                WHERE publication_version_v2_id=%s AND state='building'
                """,
                (digest, len(entries), len(rows) - len(entries), stable_json(dict(sorted(reasons.items()))), version_id),
            )
            return {
                "status": "built",
                "publication_version_v2_id": version_id,
                "state": "ready",
                "content_digest": digest,
                "included_count": len(entries),
                "excluded_count": len(rows) - len(entries),
                "reason_counts": dict(sorted(reasons.items())),
                "revision_selection": selected,
            }

    @staticmethod
    def _version_entries(conn: psycopg.Connection[Any], version_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        version = conn.execute(
            """
            SELECT publication_version_v2_id, state, content_digest, included_count, excluded_count,
                   reason_counts, created_by, created_at, completed_at
            FROM content.publication_versions_v2 WHERE publication_version_v2_id=%s FOR UPDATE
            """,
            (version_id,),
        ).fetchone()
        if not version:
            raise ContentDatabaseError("publication_v2_version_missing", "publication v2 version does not exist")
        if str(version["state"]) not in {"ready", "active", "superseded"}:
            raise ContentDatabaseError("publication_v2_version_not_completed", "publication v2 version is not completed")
        entries = [
            _mapping(row["snapshot"])
            for row in conn.execute(
                "SELECT snapshot FROM content.publication_entries_v2 WHERE publication_version_v2_id=%s ORDER BY public_case_key",
                (version_id,),
            ).fetchall()
        ]
        exclusion_count = int(
            conn.execute(
                "SELECT count(*) AS count FROM content.publication_exclusions_v2 WHERE publication_version_v2_id=%s",
                (version_id,),
            ).fetchone()["count"]
        )
        asset_count = int(
            conn.execute(
                "SELECT count(*) AS count FROM content.publication_assets_v2 WHERE publication_version_v2_id=%s",
                (version_id,),
            ).fetchone()["count"]
        )
        expected_asset_count = sum(
            len(member.get("public_outputs", []))
            for entry in entries
            for member in entry.get("generation_members", [])
        )
        if (
            int(version["included_count"]) != len(entries)
            or int(version["excluded_count"]) != exclusion_count
            or asset_count != expected_asset_count
            or str(version["content_digest"]) != publication_v2_digest(entries)
        ):
            raise ContentDatabaseError("publication_v2_version_incomplete", "publication v2 entry closure is invalid")
        return dict(version), entries

    @staticmethod
    def _assert_selected_revisions_latest(
        conn: psycopg.Connection[Any], resolved_selection: Sequence[Mapping[str, Any]]
    ) -> None:
        for item in resolved_selection:
            row = conn.execute(
                """
                SELECT revision.source_revision_id
                FROM inventory.source_adapter_runs run
                JOIN inventory.source_revisions revision ON revision.source_revision_id=run.source_revision_id
                WHERE run.state='ready' AND revision.source_project_id=%s
                ORDER BY run.source_adapter_run_id DESC LIMIT 1
                """,
                (int(item["source_project_id"]),),
            ).fetchone()
            if not row or int(row["source_revision_id"]) != int(item["source_revision_id"]):
                raise ContentDatabaseError(
                    "publication_v2_stale_revision", "selected source revision is not the latest ready authority"
                )

    @staticmethod
    def _lock_selected_projects(conn: psycopg.Connection[Any], version_id: int) -> None:
        rows = conn.execute(
            """
            SELECT source_project_id, source_revision_id
            FROM content.publication_revision_selections_v2
            WHERE publication_version_v2_id=%s
            ORDER BY source_project_id
            """,
            (version_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('image2-ready-review-project-v2:' || %s::text, 0))",
                (int(row["source_project_id"]),),
            )
        PublicationV2Store._assert_selected_revisions_latest(conn, rows)

    @staticmethod
    def _assert_target_review_authority(conn: psycopg.Connection[Any], version_id: int) -> None:
        stale = conn.execute(
            """
            SELECT count(*) AS count
            FROM content.publication_entries_v2 entry
            WHERE entry.publication_version_v2_id=%s AND NOT EXISTS (
                SELECT 1
                FROM content.rights_review_batches_v2 batch
                WHERE batch.source_case_version_id=entry.source_case_version_id
                  AND batch.rights_review_batch_id=entry.rights_review_batch_id
                  AND NOT EXISTS (
                    SELECT 1
                    FROM content.rights_review_batches_v2 newer
                    WHERE newer.source_case_version_id=batch.source_case_version_id
                      AND (newer.reviewed_at, newer.rights_review_batch_id) >
                          (batch.reviewed_at, batch.rights_review_batch_id)
                  )
            )
            """,
            (version_id,),
        ).fetchone()
        if stale and int(stale["count"]) > 0:
            raise ContentDatabaseError(
                "publication_v2_stale_review", "target contains cases superseded by a newer rights review"
            )

    @staticmethod
    def _current_version_id(conn: psycopg.Connection[Any]) -> int | None:
        row = conn.execute(
            "SELECT publication_version_v2_id FROM content.publication_current_v2 WHERE singleton=true FOR UPDATE"
        ).fetchone()
        return int(row["publication_version_v2_id"]) if row else None

    @staticmethod
    def _assert_public_loss_authorized(
        conn: psycopg.Connection[Any], current_entries: Sequence[Mapping[str, Any]], target_entries: Sequence[Mapping[str, Any]]
    ) -> None:
        target_by_key = {str(entry["public_case_key"]): entry for entry in target_entries}
        effective = PublicationV2Store._effective_takedowns(conn)
        unauthorized: list[str] = []
        for entry in current_entries:
            key = str(entry["public_case_key"])
            if key in target_by_key:
                continue
            source_case = _mapping(entry.get("source_case"))
            prompt = _mapping(entry.get("prompt"))
            broad = any(
                PublicationV2Store._active_takedown(effective, scope_type, scope_key) is not None
                for scope_type, scope_key in (
                    ("source", str(source_case.get("source_id", ""))),
                    ("case", f"{source_case.get('source_id', '')}:{source_case.get('source_case_key', '')}"),
                    ("prompt", f"{source_case.get('source_id', '')}:{prompt.get('prompt_id', '')}"),
                )
            )
            primary_assets = [
                str(output["content_sha256"])
                for member in entry.get("generation_members", [])
                for output in member.get("public_outputs", [])
                if output.get("public_display_role") == "public_primary"
            ]
            primary_removed = any(
                PublicationV2Store._active_takedown(effective, "asset", content_sha256) is not None
                for content_sha256 in primary_assets
            )
            if not broad and not primary_removed:
                unauthorized.append(key)
        if unauthorized:
            raise ContentDatabaseError(
                "publication_v2_public_loss", f"candidate would remove {len(unauthorized)} public cases without takedown authority"
            )

    def _switch_current(self, conn: psycopg.Connection[Any], *, version_id: int, event_type: str) -> dict[str, Any]:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('content-publication-current-v2', 0))")
        self._lock_selected_projects(conn, version_id)
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('content-takedown-v2', 0))")
        self._assert_target_review_authority(conn, version_id)
        target, target_entries = self._version_entries(conn, version_id)
        effective = self._effective_takedowns(conn)
        unsafe_target = [
            str(entry["public_case_key"])
            for entry in target_entries
            if self._takedown_reason(entry, effective) is not None
        ]
        if unsafe_target:
            raise ContentDatabaseError(
                "publication_v2_active_takedown", f"target contains {len(unsafe_target)} cases under active takedown"
            )
        current_id = self._current_version_id(conn)
        if str(target["state"]) == "active":
            if current_id == version_id:
                return {"publication_version_v2_id": version_id, "state": "active", "already_current": True}
            raise ContentDatabaseError("publication_v2_current_inconsistent", "active v2 target is not current")
        if current_id is not None:
            _, current_entries = self._version_entries(conn, current_id)
            if event_type == "publication_v2_activated":
                self._assert_public_loss_authorized(conn, current_entries, target_entries)
            conn.execute(
                "UPDATE content.publication_versions_v2 SET state='superseded' WHERE publication_version_v2_id=%s AND state='active'",
                (current_id,),
            )
        conn.execute(
            "UPDATE content.publication_versions_v2 SET state='active' WHERE publication_version_v2_id=%s",
            (version_id,),
        )
        conn.execute(
            """
            INSERT INTO content.publication_current_v2(singleton, publication_version_v2_id)
            VALUES (true,%s)
            ON CONFLICT (singleton) DO UPDATE
            SET publication_version_v2_id=EXCLUDED.publication_version_v2_id, activated_at=now()
            """,
            (version_id,),
        )
        conn.execute(
            """
            INSERT INTO content.publication_outbox_v2(publication_version_v2_id, event_type, event_document)
            VALUES (%s,%s,%s::jsonb)
            """,
            (version_id, event_type, stable_json({"publication_version_v2_id": version_id, "event_type": event_type})),
        )
        return {
            "publication_version_v2_id": version_id,
            "state": "active",
            "previous_publication_version_v2_id": current_id,
            "event_type": event_type,
        }

    def activate_publication(self, version_id: int) -> dict[str, Any]:
        with self._transaction() as conn:
            return self._switch_current(conn, version_id=version_id, event_type="publication_v2_activated")

    def rollback_publication(self, version_id: int) -> dict[str, Any]:
        with self._transaction() as conn:
            return self._switch_current(conn, version_id=version_id, event_type="publication_v2_rolled_back")

    def inspect_current(self) -> dict[str, Any]:
        conn = self._connect(autocommit=True)
        try:
            current = conn.execute(
                """
                SELECT version.*
                FROM content.publication_current_v2 current
                JOIN content.publication_versions_v2 version
                  ON version.publication_version_v2_id=current.publication_version_v2_id
                WHERE current.singleton=true AND version.state='active'
                """
            ).fetchone()
            if not current:
                return {"state": "no_current", "publication_version": None, "entries": []}
            version_id = int(current["publication_version_v2_id"])
            entries = [
                _mapping(row["snapshot"])
                for row in conn.execute(
                    "SELECT snapshot FROM content.publication_entries_v2 WHERE publication_version_v2_id=%s ORDER BY public_case_key",
                    (version_id,),
                ).fetchall()
            ]
            exclusion_count = int(
                conn.execute(
                    "SELECT count(*) AS count FROM content.publication_exclusions_v2 WHERE publication_version_v2_id=%s",
                    (version_id,),
                ).fetchone()["count"]
            )
            asset_count = int(
                conn.execute(
                    "SELECT count(*) AS count FROM content.publication_assets_v2 WHERE publication_version_v2_id=%s",
                    (version_id,),
                ).fetchone()["count"]
            )
            expected_asset_count = sum(
                len(member.get("public_outputs", []))
                for entry in entries
                for member in entry.get("generation_members", [])
            )
            if (
                int(current["included_count"]) != len(entries)
                or int(current["excluded_count"]) != exclusion_count
                or asset_count != expected_asset_count
                or str(current["content_digest"]) != publication_v2_digest(entries)
            ):
                raise ContentDatabaseError("publication_v2_version_incomplete", "active publication v2 closure is invalid")
            return {
                "state": "active",
                "publication_version": {
                    "publication_version_v2_id": version_id,
                    "content_digest": str(current["content_digest"]),
                    "included_count": int(current["included_count"]),
                    "excluded_count": int(current["excluded_count"]),
                    "reason_counts": _mapping(current["reason_counts"]),
                    "created_by": str(current["created_by"]),
                    "completed_at": current["completed_at"].isoformat() if current["completed_at"] else None,
                },
                "entries": entries,
            }
        except ContentDatabaseError:
            raise
        except psycopg.Error as exc:
            raise ContentDatabaseError("publication_v2_read_failed", "unable to inspect publication v2") from exc
        finally:
            conn.close()

    def inspect_takedowns(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 500 or offset < 0:
            raise ContentDatabaseError("publication_v2_invalid", "takedown pagination is invalid")
        conn = self._connect(autocommit=True)
        try:
            rows = conn.execute(
                """
                SELECT takedown_request_v2_id, scope_type, scope_key, action, reason_code,
                       evidence_url, note, requested_by, requested_at, created_at
                FROM content.takedown_requests_v2
                ORDER BY requested_at DESC, takedown_request_v2_id DESC LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
            total = int(conn.execute("SELECT count(*) AS count FROM content.takedown_requests_v2").fetchone()["count"])
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [
                    {
                        **dict(row),
                        "takedown_request_v2_id": int(row["takedown_request_v2_id"]),
                        "requested_at": row["requested_at"].isoformat(),
                        "created_at": row["created_at"].isoformat(),
                    }
                    for row in rows
                ],
            }
        except psycopg.Error as exc:
            raise ContentDatabaseError("publication_v2_read_failed", "unable to inspect takedown timeline") from exc
        finally:
            conn.close()
