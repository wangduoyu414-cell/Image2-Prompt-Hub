"""Registry authority and external-runtime path checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SUPPORTED_ADAPTER_STRUCTURES = {
    "g0dam_manifest_json_v1": "structured_manifest_json",
    "joesai_manifest_markdown_v1": "markdown_prompt_pages_with_manifest",
    "conardli_compiled_case_manifest_v1": "compiled_multi_category_case_gallery",
    "freestylefly_cases_json_v1": "centralized_case_manifest",
    "erickkkyt_prompts_json_v1": "structured_prompt_image_manifest",
    "vigo_style_directory_v1": "style_json_with_preview_assets",
    "chaos_meta_three_webp_v1": "meta_json_with_three_webp_outputs",
}


class RegistryError(ValueError):
    """Raised before any Git or extraction side effect can begin."""

    error_code = "registry_invalid"


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    repository_url: str
    verified_commit_sha: str
    adapter_strategy: str
    structure_type: str
    rights: dict[str, Any]
    ingestion_mode: str = "continuous"
    sync_enabled: bool = True
    one_shot_import_only: bool = False

    @property
    def idempotency_key(self) -> str:
        return f"{self.source_id}:{self.verified_commit_sha}:{self.adapter_strategy}:content-contract-v1"

    def raw_url(self, relative_path: str) -> str:
        parts = urlparse(self.repository_url)
        if parts.scheme != "https" or parts.netloc != "github.com":
            raise RegistryError("repository URL is not an HTTPS GitHub repository")
        repository_parts = [part for part in parts.path.strip("/").split("/") if part]
        if len(repository_parts) != 2:
            raise RegistryError("repository URL does not identify one owner/repository pair")
        safe_path = normalize_repository_path(relative_path)
        return "https://raw.githubusercontent.com/{}/{}/{}/{}".format(
            repository_parts[0], repository_parts[1], self.verified_commit_sha, safe_path
        )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_repository_path(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise RegistryError("repository path must be a nonempty relative path")
    normalized = value.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise RegistryError("repository path escapes the fixed snapshot")
    return "/".join(parts)


def ensure_external_root(path: Path | str, *, workspace_root: Path | None = None, create: bool = True) -> Path:
    """Ensure that runtime state cannot be created inside the repository."""
    target = Path(path).expanduser().resolve(strict=False)
    workspace = (workspace_root or repo_root()).resolve()
    if target == workspace or workspace in target.parents:
        raise RegistryError(f"runtime root must be outside workspace: {target}")
    if target.exists() and not target.is_dir():
        raise RegistryError(f"runtime root is not a directory: {target}")
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{label} must be a nonempty string")
    return value


def load_source_config(registry_path: Path | str, source_id: str) -> SourceConfig:
    """Load the one registry entry eligible for this extraction slice."""
    path = Path(registry_path).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load registry: {exc}") from exc
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        raise RegistryError("registry.sources must be an array")
    matches = [item for item in sources if isinstance(item, dict) and item.get("source_id") == source_id]
    if len(matches) != 1:
        raise RegistryError(f"registry must contain exactly one source_id={source_id!r}")
    source = matches[0]
    if source.get("status") != "active":
        raise RegistryError("source status must be active")
    pilot = _require_mapping(source.get("pilot"), "pilot")
    sync = _require_mapping(source.get("sync"), "sync")
    ingestion_value = source.get("ingestion")
    ingestion = _require_mapping(ingestion_value, "ingestion") if ingestion_value is not None else None
    family = _require_mapping(source.get("family"), "family")
    publication = _require_mapping(source.get("publication"), "publication")
    content = _require_mapping(source.get("content"), "content")
    repository = _require_mapping(source.get("repository"), "repository")
    rights = _require_mapping(source.get("rights"), "rights")
    if pilot.get("selected") is not True:
        raise RegistryError("source pilot.selected must be true")
    sync_enabled = sync.get("enabled")
    if not isinstance(sync_enabled, bool):
        raise RegistryError("source sync.enabled must be boolean")
    if ingestion is None:
        ingestion_mode = "continuous"
        one_shot_import_only = False
    else:
        ingestion_mode = ingestion.get("mode")
        one_shot_import_only = ingestion.get("one_shot_import_only")
        if ingestion_mode not in {"continuous", "fixed_history"} or not isinstance(one_shot_import_only, bool):
            raise RegistryError("source ingestion policy is malformed")
    if ingestion_mode == "continuous" and (sync_enabled is not True or one_shot_import_only):
        raise RegistryError("continuous source must enable sync and may not be one-shot only")
    if ingestion_mode == "fixed_history" and (sync_enabled is not False or one_shot_import_only is not True):
        raise RegistryError("fixed-history source must disable sync and require one-shot import")
    if family.get("role") != "canonical":
        raise RegistryError("source family.role must be canonical")
    if publication.get("ingestion_policy") != "full":
        raise RegistryError("source publication.ingestion_policy must be full")
    if publication.get("auto_publish") is not False:
        raise RegistryError("source publication.auto_publish must remain false")
    commit = _require_string(repository.get("verified_commit_sha"), "repository.verified_commit_sha")
    if not COMMIT_SHA.fullmatch(commit):
        raise RegistryError("repository.verified_commit_sha must be a full lowercase commit SHA")
    adapter_strategy = _require_string(content.get("adapter_strategy"), "content.adapter_strategy")
    structure_type = _require_string(content.get("structure_type"), "content.structure_type")
    expected_structure = SUPPORTED_ADAPTER_STRUCTURES.get(adapter_strategy)
    if expected_structure is None:
        raise RegistryError("source adapter strategy is not implemented for this extraction boundary")
    if structure_type != expected_structure:
        raise RegistryError("source structure type does not match its supported static adapter strategy")
    return SourceConfig(
        source_id=source_id,
        repository_url=_require_string(repository.get("url"), "repository.url"),
        verified_commit_sha=commit,
        adapter_strategy=adapter_strategy,
        structure_type=structure_type,
        rights=rights,
        ingestion_mode=ingestion_mode,
        sync_enabled=sync_enabled,
        one_shot_import_only=one_shot_import_only,
    )
