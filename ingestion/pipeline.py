"""Stateful external extraction, idempotency lock, and atomic file publication."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .adapters import adapter_for_strategy
from .adapters.base import AdapterError
from .assets import AssetError, AssetFact, read_asset
from .contracts import (
    ADAPTER_VERSION,
    CONTRACT_VERSION,
    ContractError,
    extraction_metrics,
    generation_examples,
    load_contract_context,
    metrics_schema_version,
    package_schema_version,
    resolved_adapter_output,
    stable_sha256,
    validate_adapter_output,
    validate_generation_example,
)
from .git_snapshot import GitSnapshotError, fixed_snapshot
from .registry import RegistryError, ensure_external_root, load_source_config, repo_root


class ExtractionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    output_path: Path
    idempotency_key: str
    semantic_digest: str
    metrics: dict[str, Any]
    states: tuple[str, ...]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(128 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, prefix=f".{path.name}.", suffix=".tmp") as stream:
        temporary = Path(stream.name)
        stream.write(_json_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def onerror(function: object, item: str, exception: object) -> None:
        os.chmod(item, 0o700)
        if callable(function):
            function(item)  # type: ignore[misc]

    shutil.rmtree(path, onerror=onerror)


def _safe_package_name(idempotency_key: str) -> str:
    return f"package-{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"


@contextmanager
def _idempotency_lock(output_root: Path, idempotency_key: str) -> Iterator[None]:
    lock_root = output_root / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_path = lock_root / f"{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ExtractionError("run_locked", "another same-key extraction owns the local lock") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "idempotency_key": idempotency_key}, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _manifest_stable_sha256(manifest: dict[str, Any]) -> str:
    copy = dict(manifest)
    copy.pop("manifest_stable_sha256", None)
    return hashlib.sha256(_canonical_json(copy).encode("utf-8")).hexdigest()


def _file_entries(candidate_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(candidate_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(candidate_root).as_posix()
        if relative == "manifest.json":
            continue
        if path.suffix != ".json":
            raise ExtractionError("candidate_invalid", f"extraction package contains non-JSON file: {relative}")
        entries.append({"path": relative, "sha256": _sha256_file(path), "byte_size": path.stat().st_size})
    return entries


def verify_published_package(path: Path, expected_key: str | None = None) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionError("published_package_invalid", f"published manifest cannot be read: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("package_state") != "published":
        raise ExtractionError("published_package_invalid", "package manifest is not a published manifest")
    if expected_key is not None and manifest.get("idempotency_key") != expected_key:
        raise ExtractionError("published_package_invalid", "published manifest idempotency key does not match")
    if manifest.get("manifest_stable_sha256") != _manifest_stable_sha256(manifest):
        raise ExtractionError("published_package_invalid", "manifest stable hash does not verify")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ExtractionError("published_package_invalid", "manifest has no stable files")
    observed: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ExtractionError("published_package_invalid", "manifest file entry is malformed")
        relative = entry.get("path")
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise ExtractionError("published_package_invalid", "manifest file path is unsafe")
        target = path / relative
        if not target.is_file() or _sha256_file(target) != entry.get("sha256"):
            raise ExtractionError("published_package_invalid", f"manifest file hash does not verify: {relative}")
        observed.add(relative)
    actual = {item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file() and item.name != "manifest.json"}
    if actual != observed:
        raise ExtractionError("published_package_invalid", "manifest does not enumerate exactly the stable package files")
    try:
        adapter_output = json.loads((path / "adapter-output.json").read_text(encoding="utf-8"))
        metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtractionError("published_package_invalid", "published package metadata cannot be read") from exc
    if not isinstance(adapter_output, dict) or not isinstance(metrics, dict):
        raise ExtractionError("published_package_invalid", "published package metadata must be JSON objects")
    adapter_strategy = adapter_output.get("adapter_id")
    if not isinstance(adapter_strategy, str):
        raise ExtractionError("published_package_invalid", "adapter output lacks its static adapter strategy")
    try:
        expected_package_schema = package_schema_version(adapter_strategy)
        expected_metrics_schema = metrics_schema_version(adapter_strategy)
    except ContractError as exc:
        raise ExtractionError("published_package_invalid", str(exc)) from exc
    if manifest.get("schema_version") != expected_package_schema:
        raise ExtractionError("published_package_invalid", "package schema is not supported for its adapter strategy")
    if metrics.get("schema_version") != expected_metrics_schema:
        raise ExtractionError("published_package_invalid", "metrics schema is not supported for its adapter strategy")
    if adapter_output.get("source_id") != manifest.get("source_id") or adapter_output.get("revision_sha") != manifest.get("revision_sha"):
        raise ExtractionError("published_package_invalid", "adapter output identity differs from package manifest")
    if metrics.get("source_id") != manifest.get("source_id") or metrics.get("revision_sha") != manifest.get("revision_sha"):
        raise ExtractionError("published_package_invalid", "metrics identity differs from package manifest")
    return manifest


def _publish_candidate(candidate: Path, final: Path, idempotency_key: str) -> tuple[str, Path, dict[str, Any]]:
    candidate_manifest = verify_published_package(candidate, idempotency_key)
    if final.exists():
        existing_manifest = verify_published_package(final, idempotency_key)
        if existing_manifest.get("semantic_digest") != candidate_manifest.get("semantic_digest"):
            raise ExtractionError("idempotency_conflict", "existing published package has a different semantic digest")
        _remove_tree(candidate)
        return "verified_existing", final, existing_manifest
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, final)
    published = verify_published_package(final, idempotency_key)
    return "published", final, published


def _write_candidate(
    candidate_root: Path,
    *,
    source_config: Any,
    idempotency_key: str,
    adapter_output: dict[str, Any],
    examples: list[dict[str, Any]],
    metrics: dict[str, Any],
    failure_point: str | None,
) -> None:
    _atomic_write_json(candidate_root / "adapter-output.json", adapter_output)
    for example in examples:
        case_key = str(example["source_case_key"])
        filename = f"case-{hashlib.sha256(case_key.encode('utf-8')).hexdigest()}.json"
        _atomic_write_json(candidate_root / "generation-examples" / filename, example)
    _atomic_write_json(candidate_root / "metrics.json", metrics)
    if failure_point == "before_manifest":
        raise ExtractionError("injected_before_manifest", "controlled failure before manifest publication")
    manifest = {
        "schema_version": package_schema_version(source_config.adapter_strategy),
        "package_state": "published",
        "idempotency_key": idempotency_key,
        "source_id": source_config.source_id,
        "revision_sha": source_config.verified_commit_sha,
        "adapter_version": ADAPTER_VERSION,
        "contract_version": CONTRACT_VERSION,
        "semantic_digest": metrics["semantic_digest"],
        "files": _file_entries(candidate_root),
    }
    manifest["manifest_stable_sha256"] = _manifest_stable_sha256(manifest)
    _atomic_write_json(candidate_root / "manifest.json", manifest)
    verify_published_package(candidate_root, idempotency_key)


def extract(
    *,
    registry_path: Path | str,
    audit_path: Path | str,
    source_id: str,
    data_root: Path | str,
    output_root: Path | str,
    failure_point: str | None = None,
    lock_hold_seconds: float = 0.0,
) -> ExtractionResult:
    """Run the complete fixed-commit extraction without storing image bytes in output."""
    root = repo_root()
    try:
        source_config = load_source_config(registry_path, source_id)
        external_data = ensure_external_root(data_root, workspace_root=root)
        external_output = ensure_external_root(output_root, workspace_root=root)
        context = load_contract_context(root, Path(registry_path), Path(audit_path))
    except RegistryError as exc:
        raise ExtractionError(exc.error_code, str(exc)) from exc
    idempotency_key = source_config.idempotency_key
    states: list[str] = ["registry_validated"]
    candidate: Path | None = None
    final = external_output / "packages" / _safe_package_name(idempotency_key)
    try:
        with _idempotency_lock(external_output, idempotency_key):
            if lock_hold_seconds > 0:
                import time

                time.sleep(lock_hold_seconds)
            with fixed_snapshot(source_config, external_data, workspace_root=root) as snapshot:
                states.extend(["mirror_ready", "snapshot_ready"])
                parser = adapter_for_strategy(source_config.adapter_strategy)
                parsed_cases, _model_target = parser(snapshot.root, source_config)
                if failure_point == "after_adapter":
                    raise ExtractionError("injected_after_adapter", "controlled failure after adapter parsing")
                assets_by_reference: dict[tuple[str, str], AssetFact] = {}
                for parsed in parsed_cases:
                    if not parsed.asset_paths:
                        raise ExtractionError("adapter_mapping_invalid", "parsed case has no asset path bindings")
                    for binding in parsed.asset_paths:
                        key = (parsed.source_case_key, binding.asset_ref_id)
                        if key in assets_by_reference:
                            raise ExtractionError("adapter_mapping_invalid", "parsed asset binding is duplicated")
                        assets_by_reference[key] = read_asset(snapshot.root, binding.source_path)
                states.extend(["adapter_valid", "assets_resolved"])
                if failure_point == "after_assets":
                    raise ExtractionError("injected_after_assets", "controlled failure after asset resolution")
                adapter_output = resolved_adapter_output(source_config, parsed_cases, assets_by_reference)
                validate_adapter_output(context, adapter_output)
                examples = generation_examples(adapter_output)
                for example in examples:
                    validate_generation_example(context, example)
                states.append("generation_valid")
                metrics = extraction_metrics(adapter_output, examples)
                temporary_root = external_output / ".temporary"
                temporary_root.mkdir(parents=True, exist_ok=True)
                candidate = Path(tempfile.mkdtemp(prefix="candidate-", dir=temporary_root))
                _write_candidate(
                    candidate,
                    source_config=source_config,
                    idempotency_key=idempotency_key,
                    adapter_output=adapter_output,
                    examples=examples,
                    metrics=metrics,
                    failure_point=failure_point,
                )
                states.append("candidate_verified")
                if failure_point == "before_publish":
                    raise ExtractionError("injected_before_publish", "controlled failure before atomic publish")
                if failure_point == "before_replace":
                    raise ExtractionError("injected_before_replace", "controlled failure immediately before atomic replace")
                status, output_path, manifest = _publish_candidate(candidate, final, idempotency_key)
                candidate = None
                states.append("published")
                return ExtractionResult(
                    status=status,
                    output_path=output_path,
                    idempotency_key=idempotency_key,
                    semantic_digest=str(manifest["semantic_digest"]),
                    metrics=metrics,
                    states=tuple(states),
                )
    except (GitSnapshotError, AdapterError, AssetError, ContractError) as exc:
        code = getattr(exc, "error_code", "extraction_failed")
        raise ExtractionError(code, str(exc)) from exc
    finally:
        if candidate is not None:
            _remove_tree(candidate)
