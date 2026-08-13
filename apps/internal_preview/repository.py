"""Fixed-commit internal preview index and asset delivery boundary."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ingestion.adapters import adapter_for_strategy
from ingestion.assets import image_magic, read_asset
from ingestion.contracts import (
    ADAPTER_VERSION,
    generation_examples,
    load_contract_context,
    resolved_adapter_output,
    validate_adapter_output,
    validate_generation_example,
)
from ingestion.git_snapshot import fixed_snapshot
from ingestion.registry import SourceConfig, ensure_external_root, load_source_config, repo_root
from content.quality import ContentQualityError, content_quality_decision
from content.publication import normalize_prompt


INDEX_SCHEMA = "internal-preview-index/v2"
LEGACY_INDEX_SCHEMA = "internal-preview-index/v1"
EXPECTED_CASE_COUNT = 3973
EXPECTED_OUTPUT_COUNT = 9310
EXPECTED_PROMPT_GROUP_COUNT = 3933
EXPECTED_VISIBLE_OUTPUT_COUNT = 9286
EXPECTED_QUALITY_EXCLUSION_COUNT = 24
SOURCE_IDS = (
    "g0dam-work-prompts",
    "joesai-commercial-prompts",
    "conardli-gpt-image-2-101",
    "freestylefly-awesome-gpt-image-2",
    "erickkkyt-awesome-gptimage2-prompts",
    "vigozhao-ai-visual-prompt-cookbook",
)
CURRENT_SOURCE_IDS = (
    *SOURCE_IDS,
    "chaosrealmsai-gpt-image-2-gallery",
)


class InternalPreviewError(RuntimeError):
    """Stable local-preview failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class PreviewAssetLocator:
    asset_id: str
    source_id: str
    revision_sha: str
    source_path: str
    content_sha256: str
    media_type: str
    byte_size: int
    role: str


@dataclass(frozen=True)
class PreviewAssetDelivery:
    content: bytes
    media_type: str
    content_sha256: str


AssetReader = Callable[[PreviewAssetLocator], bytes]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(128 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InternalPreviewError("preview_index_invalid", f"{label} must be an object")
    return dict(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InternalPreviewError("preview_index_invalid", f"{label} must be nonempty text")
    return value.strip()


def _positive_integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise InternalPreviewError("preview_index_invalid", f"{label} must be a positive integer")
    return value


def _cache_key(registry_path: Path, audit_path: Path, configs: Sequence[SourceConfig]) -> str:
    schema_version = _schema_for_configs(configs)
    authority = {
        "schema": schema_version,
        "adapter_version": ADAPTER_VERSION,
        "registry_sha256": _sha256_file(registry_path),
        "audit_sha256": _sha256_file(audit_path),
        "quality_ledger_sha256": _sha256_file(repo_root().resolve() / "config" / "content-quality-v1.json"),
        "quality_schema_sha256": _sha256_file(repo_root().resolve() / "schemas" / "content-quality-v1.schema.json"),
        "sources": [
            {
                "source_id": config.source_id,
                "revision_sha": config.verified_commit_sha,
                "adapter_strategy": config.adapter_strategy,
            }
            for config in configs
        ],
    }
    return hashlib.sha256(
        json.dumps(authority, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _schema_for_configs(configs: Sequence[SourceConfig]) -> str:
    source_ids = tuple(config.source_id for config in configs)
    if set(source_ids) == set(SOURCE_IDS) and len(source_ids) == len(SOURCE_IDS):
        return LEGACY_INDEX_SCHEMA
    if set(source_ids) == set(CURRENT_SOURCE_IDS) and len(source_ids) == len(CURRENT_SOURCE_IDS):
        return INDEX_SCHEMA
    raise InternalPreviewError("preview_configuration_invalid", "preview source set is not an approved baseline")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _case_from_document(
    document: Mapping[str, Any],
    *,
    source_config: SourceConfig,
) -> tuple[dict[str, Any], list[PreviewAssetLocator]]:
    prompts = document.get("prompts")
    assets = document.get("assets")
    generations = document.get("generation_examples")
    if not isinstance(prompts, list) or len(prompts) != 1 or not isinstance(prompts[0], Mapping):
        raise InternalPreviewError("preview_index_invalid", "generation document must contain exactly one Prompt")
    if not isinstance(assets, list) or not assets or not all(isinstance(item, Mapping) for item in assets):
        raise InternalPreviewError("preview_index_invalid", "generation document has no output assets")
    if not isinstance(generations, list) or not generations or not all(isinstance(item, Mapping) for item in generations):
        raise InternalPreviewError("preview_index_invalid", "generation document has no generation members")

    prompt = dict(prompts[0])
    prompt_text = _text(prompt.get("raw_text"), "prompt.raw_text")
    prompt_location = _mapping(prompt.get("source_location"), "prompt.source_location")
    asset_by_id = {_text(item.get("asset_id"), "asset.asset_id"): dict(item) for item in assets}

    ordered_asset_ids: list[str] = []
    model_claims: set[str] = set()
    for generation in generations:
        output_ids = generation.get("output_asset_ids")
        if not isinstance(output_ids, list) or not output_ids:
            raise InternalPreviewError("preview_index_invalid", "generation member has no output assets")
        for asset_id in output_ids:
            normalized = _text(asset_id, "generation.output_asset_id")
            if normalized not in ordered_asset_ids:
                ordered_asset_ids.append(normalized)
        claim = generation.get("generation_claim")
        if isinstance(claim, Mapping):
            model_raw = claim.get("model_raw")
            if isinstance(model_raw, str) and model_raw.strip():
                model_claims.add(model_raw.strip())

    source_case_key = _text(document.get("source_case_key"), "source_case_key")
    case_id = _stable_id(source_config.source_id, source_config.verified_commit_sha, source_case_key)
    output_rows: list[dict[str, Any]] = []
    locators: list[PreviewAssetLocator] = []
    for ordinal, contract_asset_id in enumerate(ordered_asset_ids):
        asset = asset_by_id.get(contract_asset_id)
        if asset is None:
            raise InternalPreviewError("preview_index_invalid", "generation output does not resolve to a case asset")
        location = _mapping(asset.get("source_location"), "asset.source_location")
        extensions = _mapping(asset.get("extensions", {}), "asset.extensions")
        ingestion_extension = _mapping(extensions.get("ingestion.asset"), "asset.extensions.ingestion.asset")
        source_path = _text(location.get("source_path"), "asset.source_path")
        content_sha256 = _text(asset.get("content_sha256"), "asset.content_sha256")
        media_type = _text(ingestion_extension.get("media_type"), "asset.media_type")
        byte_size = _positive_integer(ingestion_extension.get("byte_size"), "asset.byte_size")
        role = _text(asset.get("role"), "asset.role")
        asset_id = _stable_id(source_config.source_id, source_config.verified_commit_sha, source_path, content_sha256)
        locator = PreviewAssetLocator(
            asset_id=asset_id,
            source_id=source_config.source_id,
            revision_sha=source_config.verified_commit_sha,
            source_path=source_path,
            content_sha256=content_sha256,
            media_type=media_type,
            byte_size=byte_size,
            role=role,
        )
        locators.append(locator)
        output_rows.append(
            {
                "asset_id": asset_id,
                "ordinal": ordinal,
                "role": role,
                "media_type": media_type,
                "byte_size": byte_size,
                "content_sha256": content_sha256,
                "source_url": location.get("source_url") if isinstance(location.get("source_url"), str) else None,
            }
        )

    rights = _mapping(document.get("rights_evidence"), "rights_evidence")
    return (
        {
            "case_id": case_id,
            "source_id": source_config.source_id,
            "revision_sha": source_config.verified_commit_sha,
            "source_case_key": source_case_key,
            "source_url": prompt_location.get("source_url")
            if isinstance(prompt_location.get("source_url"), str)
            else source_config.repository_url,
            "prompt": prompt_text,
            "language": prompt.get("language") if isinstance(prompt.get("language"), str) else "unknown",
            "model_claims": sorted(model_claims),
            "prompt_rights_status": rights.get("prompt_rights_status", "unknown"),
            "asset_rights_status": rights.get("asset_rights_status", "unknown"),
            "review_state": "review_required",
            "outputs": output_rows,
            "output_count": len(output_rows),
        },
        locators,
    )


def _prompt_group_id(prompt: str) -> str:
    return hashlib.sha256(normalize_prompt(prompt).encode("utf-8")).hexdigest()


def _quality_decision_for_case(case: Mapping[str, Any]):
    try:
        return content_quality_decision(
            source_id=str(case["source_id"]),
            revision_sha=str(case["revision_sha"]),
            source_case_key=str(case["source_case_key"]),
            raw_prompt=str(case["prompt"]),
            output_content_sha256=[str(item["content_sha256"]) for item in case["outputs"]],
        )
    except (KeyError, TypeError, ContentQualityError) as exc:
        raise InternalPreviewError("preview_quality_invalid", "content quality authority does not match preview facts") from exc


def _group_cases(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_case in cases:
        case = dict(raw_case)
        by_prompt[_prompt_group_id(str(case["prompt"]))].append(case)
    groups: list[dict[str, Any]] = []
    for prompt_group_id, raw_members in by_prompt.items():
        members = sorted(raw_members, key=lambda item: (str(item["source_id"]), str(item["source_case_key"])))
        eligible_members: list[dict[str, Any]] = []
        excluded_members: list[dict[str, Any]] = []
        for case in members:
            decision = _quality_decision_for_case(case)
            member = {
                "case_id": str(case["case_id"]),
                "source_id": str(case["source_id"]),
                "revision_sha": str(case["revision_sha"]),
                "source_case_key": str(case["source_case_key"]),
                "source_url": str(case["source_url"]),
                "output_count": int(case["output_count"]),
                "quality_verdict": "eligible" if decision is None else decision.verdict,
                "quality_reason_code": None if decision is None else decision.reason_code,
            }
            if decision is not None and decision.blocks_publication:
                excluded_members.append(member)
            else:
                eligible_members.append(member)
        if not eligible_members:
            continue
        eligible_case_ids = {str(item["case_id"]) for item in eligible_members}
        representative = next(case for case in members if str(case["case_id"]) in eligible_case_ids)
        outputs: list[dict[str, Any]] = []
        outputs_by_content: dict[str, dict[str, Any]] = {}
        excluded_case_ids = {str(item["case_id"]) for item in excluded_members}
        for case in members:
            if str(case["case_id"]) in excluded_case_ids:
                continue
            for raw_output in case["outputs"]:
                content_sha256 = str(raw_output["content_sha256"])
                existing_output = outputs_by_content.get(content_sha256)
                if existing_output is not None:
                    source_id = str(case["source_id"])
                    source_case_key = str(case["source_case_key"])
                    if source_id not in existing_output["source_ids"]:
                        existing_output["source_ids"].append(source_id)
                        existing_output["source_ids"].sort()
                    if source_case_key not in existing_output["source_case_keys"]:
                        existing_output["source_case_keys"].append(source_case_key)
                        existing_output["source_case_keys"].sort()
                    continue
                output = dict(raw_output)
                output["ordinal"] = len(outputs)
                output["source_id"] = str(case["source_id"])
                output["source_case_key"] = str(case["source_case_key"])
                output["source_ids"] = [str(case["source_id"])]
                output["source_case_keys"] = [str(case["source_case_key"])]
                outputs_by_content[content_sha256] = output
                outputs.append(output)
        if not outputs:
            raise InternalPreviewError("preview_quality_invalid", "quality projection removed every output from a prompt group")
        source_ids = sorted({str(item["source_id"]) for item in members})
        model_claims = sorted(
            {
                str(value)
                for item in members
                if str(item["case_id"]) in eligible_case_ids
                for value in item.get("model_claims", [])
            }
        )
        languages = sorted({str(item.get("language", "unknown")) for item in members})
        groups.append(
            {
                "case_id": prompt_group_id,
                "prompt_group_id": prompt_group_id,
                "prompt": str(representative["prompt"]),
                "language": languages[0] if len(languages) == 1 else "mixed",
                "model_claims": model_claims,
                "prompt_rights_status": "review_required",
                "asset_rights_status": "review_required",
                "review_state": "review_required",
                "source_ids": source_ids,
                "source_id": source_ids[0] if len(source_ids) == 1 else "multiple_sources",
                "source_url": str(eligible_members[0]["source_url"]),
                "source_case_key": str(eligible_members[0]["source_case_key"]),
                "revision_sha": str(eligible_members[0]["revision_sha"]),
                "member_count": len(members),
                "eligible_member_count": len(eligible_members),
                "excluded_member_count": len(excluded_members),
                "members": eligible_members,
                "excluded_members": excluded_members,
                "outputs": outputs,
                "output_count": len(outputs),
            }
        )
    groups.sort(key=lambda item: str(item["prompt_group_id"]))
    return groups


def _build_index(
    *,
    repo: Path,
    registry_path: Path,
    audit_path: Path,
    data_root: Path,
    configs: Sequence[SourceConfig],
    cache_key: str,
) -> dict[str, Any]:
    context = load_contract_context(repo, registry_path, audit_path)
    cases: list[dict[str, Any]] = []
    assets: dict[str, dict[str, Any]] = {}
    for source_config in configs:
        with fixed_snapshot(source_config, data_root, workspace_root=repo) as snapshot:
            parsed_cases, _ = adapter_for_strategy(source_config.adapter_strategy)(snapshot.root, source_config)
            asset_facts = {
                (parsed.source_case_key, binding.asset_ref_id): read_asset(snapshot.root, binding.source_path)
                for parsed in parsed_cases
                for binding in parsed.asset_paths
            }
            adapter_output = resolved_adapter_output(source_config, parsed_cases, asset_facts)
            validate_adapter_output(context, adapter_output)
            documents = generation_examples(adapter_output)
            for document in documents:
                validate_generation_example(context, document)
                case, locators = _case_from_document(document, source_config=source_config)
                cases.append(case)
                for locator in locators:
                    serialized = locator.__dict__
                    existing = assets.setdefault(locator.asset_id, serialized)
                    if existing != serialized:
                        raise InternalPreviewError("preview_index_invalid", "asset id collision has inconsistent facts")

    cases.sort(key=lambda item: str(item["case_id"]))
    schema_version = _schema_for_configs(configs)
    expected = (1513, 1930) if schema_version == LEGACY_INDEX_SCHEMA else (EXPECTED_CASE_COUNT, EXPECTED_OUTPUT_COUNT)
    if len(cases) != expected[0] or sum(int(item["output_count"]) for item in cases) != expected[1]:
        raise InternalPreviewError("preview_index_invalid", "preview counts differ from the approved source baseline")
    return {
        "schema_version": schema_version,
        "cache_key": cache_key,
        "case_count": len(cases),
        "output_count": sum(int(item["output_count"]) for item in cases),
        "cases": cases,
        "assets": assets,
    }


class InternalPreviewRepository:
    """Read-only review-required projection over fixed-commit source cases."""

    def __init__(
        self,
        *,
        cases: Sequence[Mapping[str, Any]],
        assets: Mapping[str, PreviewAssetLocator],
        asset_reader: AssetReader,
    ) -> None:
        self._cases = tuple(dict(item) for item in cases)
        self._groups = tuple(_group_cases(self._cases))
        self._assets = dict(assets)
        self._asset_reader = asset_reader
        if len(self._cases) == EXPECTED_CASE_COUNT:
            visible_outputs = sum(int(item["output_count"]) for item in self._groups)
            excluded_members = sum(int(item["excluded_member_count"]) for item in self._groups)
            if (
                len(self._groups) != EXPECTED_PROMPT_GROUP_COUNT
                or visible_outputs != EXPECTED_VISIBLE_OUTPUT_COUNT
                or excluded_members != EXPECTED_QUALITY_EXCLUSION_COUNT
            ):
                raise InternalPreviewError("preview_quality_invalid", "quality projection differs from the approved baseline")

    @classmethod
    def from_environment(cls) -> "InternalPreviewRepository":
        repo = repo_root().resolve()
        registry_path = repo / "config" / "sources-v2.yaml"
        audit_path = repo / "reports" / "source-audit-v2.json"
        data_value = os.environ.get("IMAGE2_INTERNAL_PREVIEW_DATA_ROOT")
        cache_value = os.environ.get("IMAGE2_INTERNAL_PREVIEW_CACHE_ROOT")
        if not data_value or not cache_value:
            raise InternalPreviewError(
                "preview_configuration_missing",
                "IMAGE2_INTERNAL_PREVIEW_DATA_ROOT and IMAGE2_INTERNAL_PREVIEW_CACHE_ROOT are required",
            )
        data_root = ensure_external_root(data_value, workspace_root=repo, create=False)
        cache_root = ensure_external_root(cache_value, workspace_root=repo)
        configs = tuple(load_source_config(registry_path, source_id) for source_id in CURRENT_SOURCE_IDS)
        cache_key = _cache_key(registry_path, audit_path, configs)
        cache_path = cache_root / "index-v2.json"
        payload: dict[str, Any] | None = None
        if cache_path.is_file():
            try:
                candidate = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                candidate = None
            if isinstance(candidate, dict) and candidate.get("cache_key") == cache_key:
                payload = candidate
        if payload is None:
            payload = _build_index(
                repo=repo,
                registry_path=registry_path,
                audit_path=audit_path,
                data_root=data_root,
                configs=configs,
                cache_key=cache_key,
            )
            _atomic_write_json(cache_path, payload)

        if payload.get("schema_version") != INDEX_SCHEMA:
            raise InternalPreviewError("preview_index_invalid", "internal preview cache schema is unsupported")
        raw_cases = payload.get("cases")
        raw_assets = payload.get("assets")
        if not isinstance(raw_cases, list) or not isinstance(raw_assets, dict):
            raise InternalPreviewError("preview_index_invalid", "internal preview cache is malformed")
        locators = {
            asset_id: PreviewAssetLocator(**_mapping(value, f"assets.{asset_id}"))
            for asset_id, value in raw_assets.items()
        }

        def git_asset_reader(locator: PreviewAssetLocator) -> bytes:
            mirror = data_root / "mirrors" / f"{locator.source_id}.git"
            if not mirror.is_dir():
                raise InternalPreviewError("preview_asset_unavailable", "source mirror is unavailable")
            completed = subprocess.run(
                ["git", "-C", str(mirror), "show", f"{locator.revision_sha}:{locator.source_path}"],
                capture_output=True,
                timeout=60,
                check=False,
            )
            if completed.returncode != 0:
                raise InternalPreviewError("preview_asset_unavailable", "fixed-commit asset cannot be read")
            return completed.stdout

        return cls(cases=raw_cases, assets=locators, asset_reader=git_asset_reader)

    def status(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "mode": "internal_review_required",
            "case_count": len(self._cases),
            "output_count": sum(int(item["output_count"]) for item in self._cases),
            "prompt_group_count": len(self._groups),
            "visible_output_count": sum(int(item["output_count"]) for item in self._groups),
            "quality_exclusion_count": sum(int(item["excluded_member_count"]) for item in self._groups),
            "source_count": len({str(item["source_id"]) for item in self._cases}),
        }

    def list_cases(
        self,
        *,
        q: str | None,
        source: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        query = (q or "").strip().casefold()
        filtered = []
        for item in self._groups:
            members = [member for member in item["members"] if source is None or member["source_id"] == source]
            excluded_members = [
                member for member in item["excluded_members"] if source is None or member["source_id"] == source
            ]
            searchable = " ".join(
                [
                    str(item["prompt"]),
                    *[str(member["source_id"]) for member in members + excluded_members],
                    *[str(member["source_case_key"]) for member in members + excluded_members],
                ]
            ).casefold()
            if query and query not in searchable:
                continue
            if not members:
                continue
            outputs = [
                output
                for output in item["outputs"]
                if source is None or source in output.get("source_ids", [])
            ]
            if not outputs:
                continue
            projected = dict(item)
            projected["members"] = members
            projected["excluded_members"] = excluded_members
            projected["member_count"] = len(members) + len(excluded_members)
            projected["eligible_member_count"] = len(members)
            projected["excluded_member_count"] = len(excluded_members)
            projected["source_ids"] = sorted({str(member["source_id"]) for member in members + excluded_members})
            projected["source_id"] = projected["source_ids"][0] if len(projected["source_ids"]) == 1 else "multiple_sources"
            projected["outputs"] = outputs
            projected["output_count"] = len(outputs)
            filtered.append(projected)
        total = len(filtered)
        start = (page - 1) * page_size
        sources: dict[str, int] = {}
        for item in self._cases:
            source_id = str(item["source_id"])
            sources[source_id] = sources.get(source_id, 0) + 1
        return {
            "mode": "internal_review_required",
            "disclaimer": "未经过公开权利审核，仅供本机内部浏览；不得作为公开发布结果。",
            "total": total,
            "page": page,
            "page_size": page_size,
            "case_count": len(self._cases),
            "output_count": sum(int(item["output_count"]) for item in self._cases),
            "prompt_group_count": len(self._groups),
            "visible_output_count": sum(int(item["output_count"]) for item in self._groups),
            "quality_exclusion_count": sum(int(item["excluded_member_count"]) for item in self._groups),
            "cases": filtered[start : start + page_size],
            "sources": [{"value": key, "count": sources[key]} for key in sorted(sources)],
        }

    def read_asset(self, asset_id: str) -> PreviewAssetDelivery:
        locator = self._assets.get(asset_id)
        if locator is None:
            raise InternalPreviewError("preview_asset_not_found", "asset is not part of the internal preview index")
        content = self._asset_reader(locator)
        if len(content) != locator.byte_size or _sha256_bytes(content) != locator.content_sha256:
            raise InternalPreviewError("preview_asset_integrity_failed", "fixed-commit asset integrity check failed")
        observed_type = image_magic(content[:64])
        if observed_type != locator.media_type:
            raise InternalPreviewError("preview_asset_integrity_failed", "fixed-commit asset media type changed")
        return PreviewAssetDelivery(
            content=content,
            media_type=locator.media_type,
            content_sha256=locator.content_sha256,
        )
