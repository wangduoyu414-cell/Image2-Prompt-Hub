"""Read-only published-package validation and immutable import planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ingestion.contracts import (
    ContractError,
    extraction_metrics,
    load_contract_context,
    stable_sha256,
    validate_adapter_output,
    validate_generation_example,
)
from ingestion.pipeline import ExtractionError, verify_published_package
from ingestion.registry import RegistryError, SourceConfig, load_source_config, repo_root


CORE_METRIC_KEYS = (
    "observed_case_count",
    "exact_prompt_count",
    "paired_output_count",
    "valid_case_count",
    "unique_valid_case_count",
    "broken_asset_count",
    "pair_rate",
    "case_fingerprint_aggregate_sha256",
)


class PackageValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class AssetSourcePlan:
    source_case_key: str
    asset_id: str
    asset_ref_id: str
    role: str
    content_sha256: str
    source_location: dict[str, Any]
    byte_size: int
    media_type: str


@dataclass(frozen=True)
class ImportPlan:
    package_root: Path
    source_config: SourceConfig
    source_record: dict[str, Any]
    manifest: dict[str, Any]
    adapter_output: dict[str, Any]
    generation_documents: tuple[dict[str, Any], ...]
    metrics: dict[str, Any]
    asset_sources: tuple[AssetSourcePlan, ...]
    source_files: tuple[dict[str, str], ...]
    plan_digest: str

    @property
    def idempotency_key(self) -> str:
        return str(self.manifest["idempotency_key"])

    @property
    def source_id(self) -> str:
        return self.source_config.source_id

    @property
    def revision_sha(self) -> str:
        return self.source_config.verified_commit_sha

    @property
    def semantic_digest(self) -> str:
        return str(self.manifest["semantic_digest"])


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageValidationError("package_json_invalid", f"cannot read package JSON: {path.name}") from exc


def _workspace_root() -> Path:
    return repo_root().resolve()


def _require_external_package_root(path: Path | str) -> Path:
    root = Path(path).expanduser().resolve(strict=True)
    workspace = _workspace_root()
    if root == workspace or workspace in root.parents:
        raise PackageValidationError("package_root_unsafe", "published package root must be outside the workspace")
    if not root.is_dir():
        raise PackageValidationError("package_root_invalid", "published package root is not a directory")
    return root


def _source_record(registry_path: Path, source_id: str) -> dict[str, Any]:
    payload = _load_json(registry_path)
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        raise PackageValidationError("registry_invalid", "registry.sources must be an array")
    matches = [item for item in sources if isinstance(item, dict) and item.get("source_id") == source_id]
    if len(matches) != 1:
        raise PackageValidationError("registry_invalid", "registry must contain exactly one package source")
    return matches[0]


def _audit_metrics(audit_path: Path, source_id: str, revision_sha: str) -> dict[str, Any]:
    payload = _load_json(audit_path)
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise PackageValidationError("audit_invalid", "audit.records must be an array")
    matches = [item for item in records if isinstance(item, dict) and item.get("source_id") == source_id]
    if len(matches) != 1:
        raise PackageValidationError("audit_invalid", "audit must contain exactly one package source")
    record = matches[0]
    repository = record.get("repository")
    metrics = record.get("metrics")
    if not isinstance(repository, dict) or repository.get("verified_commit_sha") != revision_sha:
        raise PackageValidationError("audit_commit_mismatch", "audit Commit differs from the registry fixed Commit")
    if not isinstance(metrics, dict):
        raise PackageValidationError("audit_invalid", "audit metrics must be an object")
    return metrics


def _expected_package_paths(manifest: dict[str, Any], root: Path) -> tuple[Path, Path, list[Path]]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise PackageValidationError("package_manifest_invalid", "manifest files must be an array")
    listed = {item.get("path") for item in files if isinstance(item, dict) and isinstance(item.get("path"), str)}
    adapter = root / "adapter-output.json"
    metrics = root / "metrics.json"
    generations_root = root / "generation-examples"
    generation_files = sorted(generations_root.glob("*.json")) if generations_root.is_dir() else []
    expected = {
        "adapter-output.json",
        "metrics.json",
        *(path.relative_to(root).as_posix() for path in generation_files),
    }
    if not generation_files or listed != expected:
        raise PackageValidationError("package_file_set_invalid", "published package has missing, extra, or unlisted stable files")
    if not adapter.is_file() or not metrics.is_file():
        raise PackageValidationError("package_file_set_invalid", "published package is missing adapter output or metrics")
    return adapter, metrics, generation_files


def _require_mapping(value: Any, code: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageValidationError(code, f"{label} must be an object")
    return value


def _require_string(value: Any, code: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PackageValidationError(code, f"{label} must be a nonempty string")
    return value


def _location(value: Any, code: str, label: str) -> dict[str, Any]:
    location = _require_mapping(value, code, label)
    _require_string(location.get("source_path"), code, f"{label}.source_path")
    _require_string(location.get("source_url"), code, f"{label}.source_url")
    return location


def _asset_sources(
    adapter_output: dict[str, Any], generation_documents: Iterable[dict[str, Any]]
) -> tuple[AssetSourcePlan, ...]:
    records = adapter_output.get("records")
    if not isinstance(records, list) or not records:
        raise PackageValidationError("package_records_invalid", "adapter output must contain records")
    records_by_case: dict[str, dict[str, Any]] = {}
    for record in records:
        item = _require_mapping(record, "package_records_invalid", "adapter record")
        case_key = _require_string(item.get("source_case_key"), "package_records_invalid", "source_case_key")
        if case_key in records_by_case:
            raise PackageValidationError("package_records_invalid", "adapter source_case_key is duplicated")
        records_by_case[case_key] = item

    seen_generation_ids: set[str] = set()
    seen_asset_source_keys: set[tuple[str, str]] = set()
    result: list[AssetSourcePlan] = []
    for document in generation_documents:
        source_case_key = _require_string(document.get("source_case_key"), "package_reference_invalid", "generation source_case_key")
        record = records_by_case.get(source_case_key)
        if record is None:
            raise PackageValidationError("package_reference_invalid", "Generation Example references an unknown adapter record")
        record_prompt = _require_mapping(record.get("prompt"), "package_reference_invalid", "adapter prompt")
        record_prompt_id = _require_string(record_prompt.get("prompt_id"), "package_reference_invalid", "adapter prompt_id")
        record_references = record.get("asset_references")
        if not isinstance(record_references, list):
            raise PackageValidationError("package_reference_invalid", "adapter asset_references must be an array")
        references_by_hash: dict[str, dict[str, Any]] = {}
        for reference in record_references:
            ref = _require_mapping(reference, "package_reference_invalid", "adapter asset reference")
            if ref.get("resolution_state") != "resolved":
                raise PackageValidationError("package_reference_invalid", "Generation Example cannot use an unresolved asset")
            content_hash = _require_string(ref.get("content_sha256"), "package_reference_invalid", "adapter asset hash")
            references_by_hash[content_hash] = ref

        prompts = document.get("prompts")
        assets = document.get("assets")
        generations = document.get("generation_examples")
        if not isinstance(prompts, list) or not isinstance(assets, list) or not isinstance(generations, list):
            raise PackageValidationError("package_reference_invalid", "Generation Example arrays are required")
        prompt_ids = {
            _require_string(_require_mapping(prompt, "package_reference_invalid", "generation prompt").get("prompt_id"), "package_reference_invalid", "generation prompt_id")
            for prompt in prompts
        }
        if record_prompt_id not in prompt_ids:
            raise PackageValidationError("package_reference_invalid", "Generation Example does not preserve its adapter prompt")
        document_assets: dict[str, dict[str, Any]] = {}
        for asset in assets:
            item = _require_mapping(asset, "package_reference_invalid", "generation asset")
            asset_id = _require_string(item.get("asset_id"), "package_reference_invalid", "generation asset_id")
            content_hash = _require_string(item.get("content_sha256"), "package_reference_invalid", "generation asset hash")
            if asset_id in document_assets:
                raise PackageValidationError("package_reference_invalid", "Generation Example asset_id is duplicated")
            document_assets[asset_id] = item

        for generation in generations:
            item = _require_mapping(generation, "package_reference_invalid", "generation entry")
            generation_id = _require_string(item.get("generation_example_id"), "package_reference_invalid", "generation_example_id")
            if generation_id in seen_generation_ids:
                raise PackageValidationError("package_reference_invalid", "generation_example_id is duplicated")
            seen_generation_ids.add(generation_id)
            if item.get("prompt_id") not in prompt_ids:
                raise PackageValidationError("package_reference_invalid", "generation entry references an unknown prompt")
            pairing = _require_mapping(item.get("pairing"), "package_reference_invalid", "generation pairing")
            if pairing.get("status") != "strong":
                raise PackageValidationError("package_pairing_invalid", "only strong pairings can enter ready inventory")
            output_ids = item.get("output_asset_ids")
            input_ids = item.get("input_asset_ids")
            if not isinstance(output_ids, list) or not output_ids:
                raise PackageValidationError("package_reference_invalid", "generation entry needs at least one output asset")
            if not isinstance(input_ids, list):
                raise PackageValidationError("package_reference_invalid", "generation input_asset_ids must be an array")
            for asset_id in [*input_ids, *output_ids]:
                if not isinstance(asset_id, str) or asset_id not in document_assets:
                    raise PackageValidationError("package_reference_invalid", "generation entry references an unknown asset")
            for asset_id in [*input_ids, *output_ids]:
                asset = document_assets[asset_id]
                content_hash = _require_string(asset.get("content_sha256"), "package_reference_invalid", "generation output hash")
                reference = references_by_hash.get(content_hash)
                if reference is None:
                    raise PackageValidationError("package_reference_invalid", "Generation output does not match an adapter asset reference")
                extension = _require_mapping(asset.get("extensions"), "package_reference_invalid", "generation asset extensions")
                ingestion_asset = _require_mapping(extension.get("ingestion.asset"), "package_reference_invalid", "generation asset facts")
                byte_size = ingestion_asset.get("byte_size")
                media_type = ingestion_asset.get("media_type")
                if not isinstance(byte_size, int) or byte_size <= 512 or not isinstance(media_type, str):
                    raise PackageValidationError("package_reference_invalid", "generation asset facts are invalid")
                location = _location(asset.get("source_location"), "package_reference_invalid", "generation asset source_location")
                reference_location = _location(reference.get("source_location"), "package_reference_invalid", "adapter asset source_location")
                if location != reference_location:
                    raise PackageValidationError("package_reference_invalid", "Generation output locator differs from adapter reference")
                asset_ref_id = _require_string(reference.get("asset_ref_id"), "package_reference_invalid", "adapter asset_ref_id")
                key = (source_case_key, asset_ref_id)
                if key in seen_asset_source_keys:
                    continue
                seen_asset_source_keys.add(key)
                result.append(
                    AssetSourcePlan(
                        source_case_key=source_case_key,
                        asset_id=asset_id,
                        asset_ref_id=asset_ref_id,
                        role=_require_string(asset.get("role"), "package_reference_invalid", "generation asset role"),
                        content_sha256=content_hash,
                        source_location=location,
                        byte_size=byte_size,
                        media_type=media_type,
                    )
                )
    if not result:
        raise PackageValidationError("package_reference_invalid", "package has no output asset sources")
    return tuple(sorted(result, key=lambda item: (item.source_case_key, item.asset_ref_id)))


def _source_files(
    adapter_output: dict[str, Any],
    generation_documents: Iterable[dict[str, Any]],
    asset_sources: Iterable[AssetSourcePlan],
) -> tuple[dict[str, str], ...]:
    locations: dict[tuple[str, str], dict[str, str]] = {}

    def add_location(value: Any, label: str) -> None:
        location = _location(value, "package_reference_invalid", label)
        locations[(str(location["source_path"]), str(location["source_url"]))] = {
            "source_path": str(location["source_path"]),
            "source_url": str(location["source_url"]),
        }

    records = adapter_output.get("records", [])
    for record in records:
        if not isinstance(record, dict):
            continue
        add_location(record.get("source_case_locator"), "adapter case location")
        add_location(_require_mapping(record.get("prompt"), "package_records_invalid", "adapter prompt").get("source_location"), "adapter prompt location")
        for reference in record.get("asset_references", []):
            if isinstance(reference, dict):
                add_location(reference.get("source_location"), "adapter asset location")
        for pairing in record.get("pairings", []):
            if not isinstance(pairing, dict):
                continue
            for evidence in pairing.get("evidence", []):
                add_location(evidence, "adapter pairing evidence")
    for document in generation_documents:
        add_location(document.get("source_case_locator"), "Generation Example case location")
        for prompt in document.get("prompts", []):
            if isinstance(prompt, dict):
                add_location(prompt.get("source_location"), "Generation Example prompt location")
        for asset in document.get("assets", []):
            if isinstance(asset, dict):
                add_location(asset.get("source_location"), "Generation Example asset location")
        for generation in document.get("generation_examples", []):
            if not isinstance(generation, dict):
                continue
            pairing = generation.get("pairing")
            if isinstance(pairing, dict):
                for evidence in pairing.get("evidence", []):
                    add_location(evidence, "Generation Example pairing evidence")
    for asset_source in asset_sources:
        add_location(asset_source.source_location, "planned asset source location")
    return tuple(locations[key] for key in sorted(locations))


def _plan_digest(manifest: dict[str, Any], adapter_output: dict[str, Any], documents: list[dict[str, Any]], metrics: dict[str, Any]) -> str:
    payload = {
        "manifest_stable_sha256": manifest.get("manifest_stable_sha256"),
        "idempotency_key": manifest.get("idempotency_key"),
        "semantic_digest": manifest.get("semantic_digest"),
        "adapter_output": adapter_output,
        "generation_documents": documents,
        "metrics": metrics,
    }
    return stable_sha256(payload)


def build_import_plan(
    *,
    package_root: Path | str,
    registry_path: Path | str,
    audit_path: Path | str,
) -> ImportPlan:
    """Validate every static producer fact before any Git, S3, or DB access."""
    root = _require_external_package_root(package_root)
    registry = Path(registry_path).resolve()
    audit = Path(audit_path).resolve()
    try:
        manifest = verify_published_package(root)
    except ExtractionError as exc:
        raise PackageValidationError("package_manifest_invalid", str(exc)) from exc
    if manifest.get("package_state") != "published":
        raise PackageValidationError("package_manifest_invalid", "package_state must be published")
    source_id = _require_string(manifest.get("source_id"), "package_manifest_invalid", "manifest source_id")
    revision_sha = _require_string(manifest.get("revision_sha"), "package_manifest_invalid", "manifest revision_sha")
    try:
        source_config = load_source_config(registry, source_id)
    except RegistryError as exc:
        raise PackageValidationError("registry_invalid", str(exc)) from exc
    if revision_sha != source_config.verified_commit_sha:
        raise PackageValidationError("package_commit_mismatch", "package revision differs from registry fixed Commit")
    if manifest.get("idempotency_key") != source_config.idempotency_key:
        raise PackageValidationError("package_identity_invalid", "package idempotency key differs from registry identity")
    source_record = _source_record(registry, source_id)
    audit_metrics = _audit_metrics(audit, source_id, revision_sha)
    adapter_path, metrics_path, generation_paths = _expected_package_paths(manifest, root)
    adapter_output = _load_json(adapter_path)
    metrics = _load_json(metrics_path)
    documents = sorted(
        [_load_json(path) for path in generation_paths],
        key=lambda document: str(document.get("source_case_key", "")) if isinstance(document, dict) else "",
    )
    if not isinstance(adapter_output, dict) or not isinstance(metrics, dict) or not all(isinstance(item, dict) for item in documents):
        raise PackageValidationError("package_json_invalid", "package documents have invalid root types")
    if adapter_output.get("source_id") != source_id or adapter_output.get("revision_sha") != revision_sha:
        raise PackageValidationError("package_identity_invalid", "adapter output source identity differs from manifest")
    if adapter_output.get("adapter_id") != source_config.adapter_strategy:
        raise PackageValidationError("package_identity_invalid", "adapter strategy differs from registry")
    if metrics.get("source_id") != source_id or metrics.get("revision_sha") != revision_sha:
        raise PackageValidationError("package_identity_invalid", "metrics source identity differs from manifest")
    try:
        context = load_contract_context(_workspace_root(), registry, audit)
        validate_adapter_output(context, adapter_output)
        for document in documents:
            validate_generation_example(context, document)
    except ContractError as exc:
        raise PackageValidationError("package_contract_invalid", str(exc)) from exc
    rebuilt_metrics = extraction_metrics(adapter_output, documents)
    if rebuilt_metrics != metrics:
        raise PackageValidationError("package_metrics_invalid", "metrics do not match the validated package documents")
    if manifest.get("semantic_digest") != metrics.get("semantic_digest"):
        raise PackageValidationError("package_digest_invalid", "manifest and metrics semantic digests differ")
    for key in CORE_METRIC_KEYS:
        if metrics.get(key) != audit_metrics.get(key):
            raise PackageValidationError("package_audit_mismatch", f"package metric differs from audit: {key}")
    records = adapter_output.get("records")
    coverage = adapter_output.get("coverage")
    if not isinstance(records, list) or not records or not isinstance(coverage, dict):
        raise PackageValidationError("package_coverage_invalid", "adapter records and coverage are required")
    if coverage.get("input_case_count") != len(records) or coverage.get("contract_valid_count") != len(records):
        raise PackageValidationError("package_coverage_invalid", "adapter coverage does not conserve record count")
    if coverage.get("extracted_candidate_count") != 0 or coverage.get("quarantined_count") != 0 or adapter_output.get("parse_errors") != []:
        raise PackageValidationError("package_coverage_invalid", "ready inventory requires zero candidates, quarantines, and parse errors")
    generation_count = sum(len(document.get("generation_examples", [])) for document in documents)
    if metrics.get("generation_example_count") != generation_count:
        raise PackageValidationError("package_coverage_invalid", "metrics generation_example_count differs from entries")
    asset_sources = _asset_sources(adapter_output, documents)
    source_files = _source_files(adapter_output, documents, asset_sources)
    if len(source_files) < 2:
        raise PackageValidationError("package_reference_invalid", "package must retain source data and asset source files")
    return ImportPlan(
        package_root=root,
        source_config=source_config,
        source_record=source_record,
        manifest=manifest,
        adapter_output=adapter_output,
        generation_documents=tuple(documents),
        metrics=metrics,
        asset_sources=asset_sources,
        source_files=source_files,
        plan_digest=_plan_digest(manifest, adapter_output, documents, metrics),
    )
