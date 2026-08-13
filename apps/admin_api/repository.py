"""Authenticated review-service facade and private output locator lookup."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

import psycopg
from psycopg.rows import dict_row

from apps.api.repository import AssetLocator
from content.database import ContentDatabaseError, ContentDatabaseSettings
from content.review import ReviewSubmission
from content.review_store import RightsReviewStore
from content.publication_store_v2 import PublicationV2Store
from sync.status import operations_status


class AdminRepositoryError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class AdminReviewService(Protocol):
    def list_queue(self, *, state: str | None, limit: int, offset: int) -> dict[str, Any]: ...
    def inspect_subject(self, source_case_version_id: int) -> dict[str, Any]: ...
    def submit_review(self, submission: ReviewSubmission) -> dict[str, Any]: ...
    def inspect_batch(self, batch_id: int) -> dict[str, Any]: ...
    def preview_candidate(self, source_case_version_id: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SourceReviewDefaults:
    repository_license: str
    original_url: str
    evidence_url: str


class ReviewAuthorityCatalog:
    def __init__(self, records: Mapping[str, SourceReviewDefaults]) -> None:
        self._records = dict(records)

    @classmethod
    def from_path(cls, path: Path | str) -> "ReviewAuthorityCatalog":
        try:
            payload = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdminRepositoryError("admin_authority_invalid", "review source authority cannot be read") from exc
        rows = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise AdminRepositoryError("admin_authority_invalid", "review source authority records are malformed")
        records: dict[str, SourceReviewDefaults] = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("recommended_status") != "active":
                continue
            source_id = row.get("source_id")
            repository = row.get("repository")
            rights = row.get("rights")
            if not isinstance(source_id, str) or not isinstance(repository, dict) or not isinstance(rights, dict):
                continue
            repository_url = repository.get("url")
            revision = repository.get("verified_commit_sha")
            license_name = rights.get("repository_license")
            license_path = rights.get("repository_license_evidence_path")
            if not all(isinstance(value, str) and value for value in (repository_url, revision, license_name)):
                continue
            evidence_url = repository_url
            if isinstance(license_path, str) and license_path:
                evidence_url = f"{repository_url}/blob/{revision}/{license_path.lstrip('/')}"
            records[source_id] = SourceReviewDefaults(
                repository_license=license_name,
                original_url=repository_url,
                evidence_url=evidence_url,
            )
        if not records:
            raise AdminRepositoryError("admin_authority_invalid", "review source authority contains no active records")
        return cls(records)

    def defaults_for(self, source_id: str, prompt_source_url: str) -> dict[str, str | None]:
        record = self._records.get(source_id)
        if record is None:
            return {
                "repository_license": None,
                "original_url": prompt_source_url,
                "evidence_url": prompt_source_url,
                "author": None,
            }
        return {
            "repository_license": record.repository_license,
            "original_url": prompt_source_url or record.original_url,
            "evidence_url": record.evidence_url,
            "author": None,
        }


class AdminReviewRepository:
    def __init__(
        self,
        *,
        settings: ContentDatabaseSettings,
        store: AdminReviewService,
        authority: ReviewAuthorityCatalog,
    ) -> None:
        self._settings = settings
        self._store = store
        self._authority = authority
        self._publication_v2 = PublicationV2Store(settings)

    @classmethod
    def from_environment(cls) -> "AdminReviewRepository":
        database_url = os.environ.get("CONTENT_DATABASE_URL", "")
        if not database_url:
            raise AdminRepositoryError("admin_config_invalid", "CONTENT_DATABASE_URL is required")
        settings = ContentDatabaseSettings(database_url)
        authority_path = os.environ.get(
            "IMAGE2_ADMIN_SOURCE_AUDIT",
            str(Path(__file__).resolve().parents[2] / "reports/source-audit-v2.json"),
        )
        return cls(
            settings=settings,
            store=RightsReviewStore(settings),
            authority=ReviewAuthorityCatalog.from_path(authority_path),
        )

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._settings.database_url, autocommit=True, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AdminRepositoryError("admin_database_unavailable", "review database is unavailable") from exc

    def readiness(self) -> str:
        try:
            if hasattr(self._store, "assert_migrated"):
                self._store.assert_migrated()  # type: ignore[attr-defined]
            self._publication_v2.assert_migrated()
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT to_regclass('content.rights_review_batches_v2') AS batches"
                ).fetchone()
            if not row or row.get("batches") is None:
                raise AdminRepositoryError("admin_database_unavailable", "review schema is unavailable")
            return "ready"
        except AdminRepositoryError:
            raise
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc
        except psycopg.Error as exc:
            raise AdminRepositoryError("admin_database_unavailable", "review database is unavailable") from exc

    def operations_status(self) -> dict[str, Any]:
        try:
            return operations_status(database_url=self._settings.database_url)
        except Exception as exc:
            error_code = getattr(exc, "error_code", "operations_read_failed")
            raise AdminRepositoryError(str(error_code), "operations status is unavailable") from exc

    def list_queue(self, *, state: str | None, limit: int, offset: int) -> dict[str, Any]:
        try:
            return self._store.list_queue(state=state, limit=limit, offset=offset)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def inspect_subject(self, source_case_version_id: int) -> dict[str, Any]:
        try:
            subject = self._store.inspect_subject(source_case_version_id)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc
        facts = subject.get("case_facts") if isinstance(subject, dict) else None
        source = facts.get("source") if isinstance(facts, dict) else None
        prompt = facts.get("prompt") if isinstance(facts, dict) else None
        if not isinstance(source, dict) or not isinstance(prompt, dict):
            raise AdminRepositoryError("admin_subject_invalid", "review subject facts are malformed")
        result = dict(subject)
        result["review_defaults"] = self._authority.defaults_for(
            str(source.get("source_id", "")),
            str(prompt.get("source_url", "")),
        )
        return result

    def submit_review(self, submission: ReviewSubmission) -> dict[str, Any]:
        try:
            return self._store.submit_review(submission)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def inspect_batch(self, batch_id: int) -> dict[str, Any]:
        try:
            return self._store.inspect_batch(batch_id)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def preview_candidate(self, source_case_version_id: int) -> dict[str, Any]:
        try:
            return self._store.preview_candidate(source_case_version_id)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def locate_output(self, generation_output_id: int) -> AssetLocator:
        if not isinstance(generation_output_id, int) or generation_output_id <= 0:
            raise AdminRepositoryError("admin_asset_not_found", "review output does not exist")
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT asset.content_sha256, asset.object_bucket, asset.object_key,
                           asset.media_type, asset.byte_size
                    FROM inventory.generation_outputs AS output
                    JOIN inventory.generation_examples AS generation
                      ON generation.generation_example_row_id=output.generation_example_row_id
                    JOIN inventory.source_case_versions AS version
                      ON version.source_case_version_id=generation.source_case_version_id
                    JOIN inventory.source_adapter_runs AS run
                      ON run.source_adapter_run_id=version.source_adapter_run_id
                    JOIN inventory.asset_sources AS source
                      ON source.asset_source_id=output.asset_source_id
                    JOIN inventory.assets AS asset ON asset.content_sha256=source.content_sha256
                    WHERE output.generation_output_id=%s
                      AND generation.contract_state='contract_valid'
                      AND version.contract_state='contract_valid'
                      AND run.state='ready'
                    """,
                    (generation_output_id,),
                ).fetchone()
        except AdminRepositoryError:
            raise
        except psycopg.Error as exc:
            raise AdminRepositoryError("admin_database_unavailable", "review asset lookup failed") from exc
        if not row:
            raise AdminRepositoryError("admin_asset_not_found", "review output does not exist")
        return AssetLocator(
            content_sha256=str(row["content_sha256"]),
            bucket=str(row["object_bucket"]),
            object_key=str(row["object_key"]),
            media_type=str(row["media_type"]),
            byte_size=int(row["byte_size"]),
        )

    def publication_v2_status(self) -> dict[str, Any]:
        try:
            current = self._publication_v2.inspect_current()
            current_summary: dict[str, Any] = {"state": current.get("state")}
            if current.get("state") == "active" and isinstance(current.get("publication_version"), dict):
                current_summary["publication_version"] = current["publication_version"]
            return {
                "current": current_summary,
                "takedowns": self._publication_v2.inspect_takedowns(limit=100, offset=0),
                "revision_selection": self._store.latest_ready_revision_selection(),
            }
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def build_publication_v2(self, *, actor: str, idempotency_key: str) -> dict[str, Any]:
        try:
            return self._publication_v2.build_publication(
                revision_selection=self._store.latest_ready_revision_selection(),
                created_by=actor,
                idempotency_key=idempotency_key,
            )
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def activate_publication_v2(self, version_id: int) -> dict[str, Any]:
        try:
            return self._publication_v2.activate_publication(version_id)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def rollback_publication_v2(self, version_id: int) -> dict[str, Any]:
        try:
            return self._publication_v2.rollback_publication(version_id)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc

    def record_takedown_v2(self, **facts: Any) -> dict[str, Any]:
        try:
            return self._publication_v2.record_takedown(**facts)
        except ContentDatabaseError as exc:
            raise AdminRepositoryError(exc.error_code, str(exc)) from exc


__all__ = [
    "AdminRepositoryError",
    "AdminReviewRepository",
    "AdminReviewService",
    "ReviewAuthorityCatalog",
]
