"""One-shot fixed-history extraction, inventory import, and review-queue wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from content.database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings
from ingestion.pipeline import ExtractionError, extract
from ingestion.registry import RegistryError, load_source_config

from .importer import ImportError, ImportResult, ImportSettings, import_package


class FixedHistoryImportError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class FixedHistoryImportResult:
    status: str
    source_id: str
    revision_sha: str
    package_path: Path
    extraction_status: str
    inventory_status: str
    idempotency_key: str
    semantic_digest: str
    object_count: int
    inventory_summary: dict[str, Any]
    canonicalization: dict[str, int]


def import_fixed_history(
    *,
    registry_path: Path | str,
    audit_path: Path | str,
    source_id: str,
    git_data_root: Path | str,
    package_root: Path | str,
    settings: ImportSettings,
) -> FixedHistoryImportResult:
    """Run the only supported fixed-history path without publication or HEAD polling."""

    try:
        config = load_source_config(registry_path, source_id)
    except RegistryError as exc:
        raise FixedHistoryImportError(exc.error_code, str(exc)) from exc
    if config.ingestion_mode != "fixed_history" or config.sync_enabled or not config.one_shot_import_only:
        raise FixedHistoryImportError(
            "fixed_history_policy_invalid",
            "source is not authorized for fixed-history one-shot import",
        )
    try:
        extraction = extract(
            registry_path=registry_path,
            audit_path=audit_path,
            source_id=source_id,
            data_root=git_data_root,
            output_root=package_root,
        )
        imported: ImportResult = import_package(
            package_root=extraction.output_path,
            registry_path=registry_path,
            audit_path=audit_path,
            settings=settings,
        )
        content = ContentDatabase(ContentDatabaseSettings(settings.database.dsn))
        canonicalization = content.canonicalize_revisions({source_id: config.verified_commit_sha})
    except (ExtractionError, ImportError, ContentDatabaseError) as exc:
        raise FixedHistoryImportError(getattr(exc, "error_code", "fixed_history_import_failed"), str(exc)) from exc
    return FixedHistoryImportResult(
        status="ready_for_review",
        source_id=source_id,
        revision_sha=config.verified_commit_sha,
        package_path=extraction.output_path,
        extraction_status=extraction.status,
        inventory_status=imported.status,
        idempotency_key=imported.idempotency_key,
        semantic_digest=imported.semantic_digest,
        object_count=imported.object_count,
        inventory_summary=imported.summary,
        canonicalization=canonicalization,
    )


__all__ = [
    "FixedHistoryImportError",
    "FixedHistoryImportResult",
    "import_fixed_history",
]
