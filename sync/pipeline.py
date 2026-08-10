"""One-shot safe Commit update orchestration for a single registered source."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from content.database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings
from ingestion.git_snapshot import GitSnapshotError, detect_default_branch_candidate, is_fast_forward, retain_candidate_ref
from ingestion.pipeline import ExtractionError, extract
from inventory.database import DatabaseConfig
from inventory.importer import ImportError, ImportSettings, import_package
from inventory.object_store import ObjectStoreConfig

from .database import SyncDatabase, SyncDatabaseError, SyncDatabaseSettings, stable_sync_key
from .revision import (
    RevisionError,
    create_revision_authority,
    evaluate_quality_gate,
    fingerprint_map,
    load_sync_source,
    stable_set_diff,
)


class SyncPipelineError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SyncSettings:
    database_url: str
    s3_endpoint_url: str
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    git_data_root: Path
    package_root: Path
    evidence_root: Path

    def import_settings(self) -> ImportSettings:
        return ImportSettings(
            database=DatabaseConfig(self.database_url),
            object_store=ObjectStoreConfig(
                self.s3_endpoint_url,
                self.s3_bucket,
                self.s3_access_key_id,
                self.s3_secret_access_key,
            ),
            data_root=self.git_data_root,
        )


@dataclass(frozen=True)
class SyncResult:
    status: str
    source_id: str
    previous_revision_sha: str | None
    candidate_revision_sha: str
    sync_run_id: int | None
    diff: dict[str, Any]
    quality_gate: dict[str, Any]
    publication: dict[str, Any] | None
    reason_code: str | None = None
    error_code: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_id": self.source_id,
            "previous_revision_sha": self.previous_revision_sha,
            "candidate_revision_sha": self.candidate_revision_sha,
            "sync_run_id": self.sync_run_id,
            "diff": self.diff,
            "quality_gate": self.quality_gate,
            "publication": self.publication,
            "reason_code": self.reason_code,
            "error_code": self.error_code,
        }


def _read_candidate_case_documents(package_root: Path) -> list[dict[str, Any]]:
    try:
        adapter = json.loads((package_root / "adapter-output.json").read_text(encoding="utf-8"))
        generation_files = sorted((package_root / "generation-examples").glob("*.json"))
        generation_documents = [json.loads(path.read_text(encoding="utf-8")) for path in generation_files]
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncPipelineError("sync_package_invalid", "candidate package cannot be read") from exc
    records = adapter.get("records") if isinstance(adapter, dict) else None
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise SyncPipelineError("sync_package_invalid", "candidate package records are invalid")
    documents_by_key: dict[str, list[dict[str, Any]]] = {}
    for document in generation_documents:
        if not isinstance(document, dict) or not isinstance(document.get("source_case_key"), str):
            raise SyncPipelineError("sync_package_invalid", "candidate generation document is invalid")
        documents_by_key.setdefault(str(document["source_case_key"]), []).append(document)
    result: list[dict[str, Any]] = []
    for record in records:
        key = record.get("source_case_key")
        if not isinstance(key, str) or key not in documents_by_key:
            raise SyncPipelineError("sync_package_invalid", "candidate package does not close adapter and generation documents")
        documents = documents_by_key[key]
        generation_document: dict[str, Any] = documents[0] if len(documents) == 1 else {"documents": documents}
        result.append({"source_case_key": key, "adapter_record": record, "generation_document": generation_document})
    return result


def _empty_diff() -> dict[str, Any]:
    return {"added": [], "modified": [], "removed": [], "unchanged": [], "counts": {"added": 0, "modified": 0, "removed": 0, "unchanged": 0}}


def _empty_quality() -> dict[str, Any]:
    return {"status": "not_run", "reasons": []}


def _failure_point(value: str | None, expected: str) -> bool:
    return value == expected


def run_source(
    *,
    registry_path: Path | str,
    audit_path: Path | str,
    source_id: str,
    settings: SyncSettings,
    failure_point: str | None = None,
    lock_hold_seconds: float = 0.0,
) -> SyncResult:
    """Detect, prove, parse, import, gate, and safely publish one source update."""

    sync_db = SyncDatabase(SyncDatabaseSettings(settings.database_url))
    content_db = ContentDatabase(ContentDatabaseSettings(settings.database_url))
    run_row: dict[str, Any] | None = None
    publication: dict[str, Any] | None = None
    source = load_sync_source(registry_path, audit_path, source_id)
    try:
        sync_db.assert_migrated()
        content_db.assert_migrated()
        candidate = detect_default_branch_candidate(
            source.config,
            settings.git_data_root,
            default_branch=source.default_branch,
        )
        candidate_config = replace(source.config, verified_commit_sha=candidate.candidate_sha)
        previous = sync_db.latest_ready_inventory(source_id)
        previous_sha = str(previous["revision_sha"]) if previous else None
        existing = sync_db.get_run(source_id, candidate.candidate_sha)
        retrying_existing = existing is not None and str(existing["state"]) in {"failed", "review_required", "ready", "imported", "gated"}
        if retrying_existing:
            previous_sha = str(existing["previous_revision_sha"]) if existing.get("previous_revision_sha") else previous_sha
        if previous_sha == candidate.candidate_sha and not retrying_existing:
            return SyncResult(
                status="no_change",
                source_id=source_id,
                previous_revision_sha=previous_sha,
                candidate_revision_sha=candidate.candidate_sha,
                sync_run_id=None,
                diff=_empty_diff(),
                quality_gate=_empty_quality(),
                publication=None,
                reason_code="no_change",
            )

        key = stable_sync_key(source_id, candidate.candidate_sha)
        with sync_db.advisory_lock(key):
            run_row = sync_db.begin_run(
                source_id=source_id,
                previous_revision_sha=previous_sha,
                candidate_revision_sha=candidate.candidate_sha,
                authority={
                    "source_id": source_id,
                    "candidate_revision_sha": candidate.candidate_sha,
                    "default_branch": source.default_branch,
                    "mirror_path_sha256_namespace": source_id,
                    "static_registry_sha256": source.static_registry_sha256,
                    "static_audit_sha256": source.static_audit_sha256,
                },
            )
            run_id = int(run_row["sync_run_id"])
            if str(run_row["state"]) == "completed":
                return SyncResult(
                    status="completed",
                    source_id=source_id,
                    previous_revision_sha=previous_sha,
                    candidate_revision_sha=candidate.candidate_sha,
                    sync_run_id=run_id,
                    diff=dict(run_row["diff_document"]),
                    quality_gate=dict(run_row["result_document"].get("quality_gate", {})),
                    publication={"publication_version_id": run_row.get("publication_version_id")},
                )
            if previous_sha and not is_fast_forward(
                candidate_config,
                settings.git_data_root,
                previous_sha=previous_sha,
                candidate_sha=candidate.candidate_sha,
            ):
                run_row = sync_db.update_run(
                    run_id,
                    state="review_required",
                    reason_code="non_fast_forward",
                    result_document={"quality_gate": {"status": "review_required", "reasons": ["non_fast_forward"]}},
                )
                return SyncResult(
                    status="review_required",
                    source_id=source_id,
                    previous_revision_sha=previous_sha,
                    candidate_revision_sha=candidate.candidate_sha,
                    sync_run_id=run_id,
                    diff=_empty_diff(),
                    quality_gate={"status": "review_required", "reasons": ["non_fast_forward"]},
                    publication=None,
                    reason_code="non_fast_forward",
                )

            sync_db.update_run(run_id, state="extracting", reason_code=None, error_code=None)
            authority = create_revision_authority(
                registry_path=registry_path,
                audit_path=audit_path,
                source=source,
                candidate_revision_sha=candidate.candidate_sha,
                evidence_root=settings.evidence_root,
            )
            extraction = extract(
                registry_path=authority.registry_path,
                audit_path=authority.extraction_audit_path,
                source_id=source_id,
                data_root=settings.git_data_root,
                output_root=settings.package_root,
                failure_point="after_adapter" if _failure_point(failure_point, "git_or_extract") else None,
                lock_hold_seconds=lock_hold_seconds,
            )
            if _failure_point(failure_point, "after_extract"):
                raise SyncPipelineError("injected_after_extract", "controlled failure after immutable package publication")
            candidate_documents = _read_candidate_case_documents(extraction.output_path)
            candidate_fingerprints = fingerprint_map(candidate_documents)
            previous_documents = (
                sync_db.revision_case_documents(source_id, previous_sha) if previous_sha is not None else []
            )
            previous_fingerprints = fingerprint_map(previous_documents) if previous_documents else {}
            diff = stable_set_diff(previous_fingerprints, candidate_fingerprints)
            quality = evaluate_quality_gate(
                candidate_metrics=extraction.metrics,
                previous_metrics=previous.get("metrics") if previous else None,
                diff=diff,
                source=source,
            )
            sync_db.record_tombstone_events(
                sync_run_id=run_id,
                source_id=source_id,
                previous_revision_sha=previous_sha,
                candidate_revision_sha=candidate.candidate_sha,
                removed_case_keys=list(diff["removed"]),
                added_case_keys=list(diff["added"]),
            )
            authority = create_revision_authority(
                registry_path=registry_path,
                audit_path=audit_path,
                source=source,
                candidate_revision_sha=candidate.candidate_sha,
                evidence_root=settings.evidence_root,
                candidate_metrics=extraction.metrics,
            )
            if quality["status"] != "passed":
                sync_db.update_run(
                    run_id,
                    state="review_required",
                    diff_document=diff,
                    metrics=extraction.metrics,
                    package_idempotency_key=extraction.idempotency_key,
                    reason_code="quality_gate",
                    result_document={"quality_gate": quality, "authority": authority.evidence},
                )
                return SyncResult(
                    status="review_required",
                    source_id=source_id,
                    previous_revision_sha=previous_sha,
                    candidate_revision_sha=candidate.candidate_sha,
                    sync_run_id=run_id,
                    diff=diff,
                    quality_gate=quality,
                    publication=None,
                    reason_code="quality_gate",
                )

            imported = import_package(
                package_root=extraction.output_path,
                registry_path=authority.registry_path,
                audit_path=authority.import_audit_path or authority.extraction_audit_path,
                settings=settings.import_settings(),
                failure_point="after_first_object" if _failure_point(failure_point, "import") else None,
            )
            if _failure_point(failure_point, "after_import"):
                raise SyncPipelineError("injected_after_import", "controlled failure after ready inventory")
            adapter_run_id = sync_db.adapter_run_id_for_package(imported.idempotency_key)
            retained_ref = retain_candidate_ref(
                candidate_config,
                settings.git_data_root,
                candidate_sha=candidate.candidate_sha,
            )
            sync_db.update_run(
                run_id,
                state="imported",
                diff_document=diff,
                metrics=extraction.metrics,
                package_idempotency_key=imported.idempotency_key,
                source_adapter_run_id=adapter_run_id,
                result_document={"quality_gate": quality, "authority": authority.evidence, "retained_ref": retained_ref},
            )
            selection = sync_db.publication_selection(source_id=source_id, candidate_revision_sha=candidate.candidate_sha)
            content_db.canonicalize_revisions(selection)
            publication = content_db.build_publication_for_revisions(
                selection,
                failure_point="before_ready" if _failure_point(failure_point, "build") else None,
            )
            sync_db.update_run(
                run_id,
                state="ready",
                publication_version_id=int(publication["publication_version_id"]),
                result_document={
                    "quality_gate": quality,
                    "authority": authority.evidence,
                    "retained_ref": retained_ref,
                    "revision_selection": selection,
                    "publication": publication,
                },
            )
            activation = content_db.activate_publication_for_sync(
                version_id=int(publication["publication_version_id"]),
                sync_run_id=run_id,
                failure_point=(
                    "after_pointer_before_outbox"
                    if _failure_point(failure_point, "activation_pointer")
                    else "after_outbox_before_sync_completion"
                    if _failure_point(failure_point, "activation_completion")
                    else None
                ),
            )
            return SyncResult(
                status="completed",
                source_id=source_id,
                previous_revision_sha=previous_sha,
                candidate_revision_sha=candidate.candidate_sha,
                sync_run_id=run_id,
                diff=diff,
                quality_gate=quality,
                publication={**publication, "activation": activation, "retained_ref": retained_ref},
            )
    except ContentDatabaseError as exc:
        if exc.error_code == "publication_public_loss" and run_row is not None:
            updated = sync_db.update_run(
                int(run_row["sync_run_id"]),
                state="review_required",
                publication_version_id=int(publication["publication_version_id"]) if publication else None,
                reason_code="public_loss",
                error_code=None,
                result_document={"quality_gate": {"status": "review_required", "reasons": ["public_loss"]}},
            )
            return SyncResult(
                status="review_required",
                source_id=source_id,
                previous_revision_sha=previous_sha,
                candidate_revision_sha=candidate.candidate_sha,
                sync_run_id=int(run_row["sync_run_id"]),
                diff=dict(updated.get("diff_document", {})),
                quality_gate={"status": "review_required", "reasons": ["public_loss"]},
                publication=publication,
                reason_code="public_loss",
            )
        code = exc.error_code
        if run_row is not None:
            try:
                sync_db.update_run(int(run_row["sync_run_id"]), state="failed", error_code=code, reason_code="failed")
            except SyncDatabaseError:
                pass
        raise SyncPipelineError(code, "incremental sync did not complete") from exc
    except (RevisionError, GitSnapshotError, ExtractionError, ImportError, SyncDatabaseError, SyncPipelineError) as exc:
        code = getattr(exc, "error_code", "sync_failed")
        if run_row is not None:
            try:
                sync_db.update_run(int(run_row["sync_run_id"]), state="failed", error_code=code, reason_code="failed")
            except SyncDatabaseError:
                pass
        raise SyncPipelineError(code, "incremental sync did not complete") from exc


def inspect_source(*, source_id: str, database_url: str) -> dict[str, Any]:
    database = SyncDatabase(SyncDatabaseSettings(database_url))
    database.assert_migrated()
    return database.inspect_source(source_id)
