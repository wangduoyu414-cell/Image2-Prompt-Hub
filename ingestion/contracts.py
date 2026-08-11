"""TASK-0002 contract projection, validation, and stable summaries."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from jsonschema import Draft202012Validator

from .adapters.base import ParsedCase, prompt_sha256
from .assets import AssetFact
from .registry import SourceConfig


ADAPTER_VERSION = "1.0.0"
CONTRACT_VERSION = "v1"
PACKAGE_SCHEMA_BY_ADAPTER = {
    "g0dam_manifest_json_v1": "g0dam-extraction-package/v1",
    "joesai_manifest_markdown_v1": "extraction-package/v1",
    "conardli_compiled_case_manifest_v1": "extraction-package/v1",
    "freestylefly_cases_json_v1": "extraction-package/v1",
    "erickkkyt_prompts_json_v1": "extraction-package/v1",
    "vigo_style_directory_v1": "extraction-package/v1",
    "chaos_meta_three_webp_v1": "extraction-package/v1",
}
METRICS_SCHEMA_BY_ADAPTER = {
    "g0dam_manifest_json_v1": "g0dam-extraction-metrics/v1",
    "joesai_manifest_markdown_v1": "extraction-metrics/v1",
    "conardli_compiled_case_manifest_v1": "extraction-metrics/v1",
    "freestylefly_cases_json_v1": "extraction-metrics/v1",
    "erickkkyt_prompts_json_v1": "extraction-metrics/v1",
    "vigo_style_directory_v1": "extraction-metrics/v1",
    "chaos_meta_three_webp_v1": "extraction-metrics/v1",
}


class ContractError(ValueError):
    def __init__(self, code: str, messages: list[str] | str) -> None:
        detail = [messages] if isinstance(messages, str) else messages
        super().__init__("; ".join(detail))
        self.error_code = code
        self.messages = detail


def package_schema_version(adapter_strategy: str) -> str:
    value = PACKAGE_SCHEMA_BY_ADAPTER.get(adapter_strategy)
    if value is None:
        raise ContractError("package_schema_invalid", "adapter strategy has no supported package schema")
    return value


def metrics_schema_version(adapter_strategy: str) -> str:
    value = METRICS_SCHEMA_BY_ADAPTER.get(adapter_strategy)
    if value is None:
        raise ContractError("package_schema_invalid", "adapter strategy has no supported metrics schema")
    return value


@dataclass(frozen=True)
class ContractContext:
    repo_root: Path
    adapter_schema: dict[str, Any]
    generation_schema: dict[str, Any]
    registry: dict[str, Any]
    audit: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@lru_cache(maxsize=2)
def _task2_validator_module(repo_root_text: str) -> ModuleType:
    path = Path(repo_root_text) / "scripts" / "validate_content_contracts.py"
    spec = importlib.util.spec_from_file_location("task2_content_contract_validator", path)
    if spec is None or spec.loader is None:
        raise ContractError("contract_validator_missing", f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("contract_input_invalid", f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("contract_input_invalid", f"{path} must contain a JSON object")
    return value


def load_contract_context(repo_root: Path, registry_path: Path, audit_path: Path) -> ContractContext:
    root = repo_root.resolve()
    return ContractContext(
        repo_root=root,
        adapter_schema=_load_json(root / "schemas" / "adapter-output-v1.schema.json"),
        generation_schema=_load_json(root / "schemas" / "generation-example-v1.schema.json"),
        registry=_load_json(registry_path),
        audit=_load_json(audit_path),
    )


def _schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    try:
        validator = Draft202012Validator(schema)
    except Exception as exc:
        return [f"{label}: schema cannot be initialized: {exc}"]
    return [
        f"{label}{''.join(f'[{part!r}]' for part in error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    ]


def validate_adapter_output(context: ContractContext, adapter_output: dict[str, Any]) -> None:
    module = _task2_validator_module(str(context.repo_root))
    registry, audit, index_errors = module.registry_indexes(context.registry, context.audit)
    errors = list(index_errors)
    errors.extend(_schema_errors(adapter_output, context.adapter_schema, "adapter-output"))
    errors.extend(module.validate_json_schema(adapter_output, context.adapter_schema, context.adapter_schema, "adapter-output"))
    errors.extend(module.validate_adapter_semantics(adapter_output, registry, audit, "adapter-output"))
    if errors:
        raise ContractError("adapter_contract_invalid", sorted(set(errors)))


def validate_generation_example(context: ContractContext, generation_example: dict[str, Any]) -> None:
    module = _task2_validator_module(str(context.repo_root))
    registry, audit, index_errors = module.registry_indexes(context.registry, context.audit)
    errors = list(index_errors)
    errors.extend(_schema_errors(generation_example, context.generation_schema, "generation-example"))
    errors.extend(module.validate_json_schema(generation_example, context.generation_schema, context.generation_schema, "generation-example"))
    errors.extend(module.validate_generation_semantics(generation_example, registry, audit, "generation-example"))
    if errors:
        raise ContractError("generation_contract_invalid", sorted(set(errors)))


def resolved_adapter_output(
    source_config: SourceConfig,
    parsed_cases: list[ParsedCase],
    assets_by_reference: dict[tuple[str, str] | str, AssetFact],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for parsed in parsed_cases:
        if not parsed.asset_paths:
            raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} has no asset bindings")
        record = copy.deepcopy(parsed.adapter_record)
        references = record.get("asset_references")
        if not isinstance(references, list) or not references or not all(isinstance(item, dict) for item in references):
            raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} has no usable output references")
        reference_by_id: dict[str, dict[str, Any]] = {}
        for reference in references:
            asset_ref_id = reference.get("asset_ref_id")
            if not isinstance(asset_ref_id, str) or not asset_ref_id or asset_ref_id in reference_by_id:
                raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} has duplicate or invalid asset_ref_id")
            reference_by_id[asset_ref_id] = reference
        binding_ids = [binding.asset_ref_id for binding in parsed.asset_paths]
        if len(binding_ids) != len(set(binding_ids)) or set(binding_ids) != set(reference_by_id):
            raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} asset bindings do not close references")
        resolved_hashes: set[str] = set()
        for binding in parsed.asset_paths:
            reference = reference_by_id[binding.asset_ref_id]
            location = reference.get("source_location")
            if not isinstance(location, dict) or location.get("source_path") != binding.source_path:
                raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} binding path differs from reference")
            fact = assets_by_reference.get((parsed.source_case_key, binding.asset_ref_id))
            if fact is None and len(parsed.asset_paths) == 1:
                fact = assets_by_reference.get(parsed.source_case_key)
            if fact is None:
                raise ContractError(
                    "asset_mapping_missing", f"missing asset fact for {parsed.source_case_key}:{binding.asset_ref_id}"
                )
            if fact.source_path != binding.source_path:
                raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} asset fact path differs from binding")
            if fact.content_sha256 in resolved_hashes:
                raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} repeats identical output content")
            resolved_hashes.add(fact.content_sha256)
            reference["resolution_state"] = "resolved"
            reference["content_sha256"] = fact.content_sha256
            extensions = copy.deepcopy(reference.get("extensions", {}))
            if not isinstance(extensions, dict):
                raise ContractError("adapter_mapping_invalid", f"{parsed.source_case_key} asset extensions are malformed")
            extensions["ingestion.asset"] = {
                "byte_size": fact.byte_size,
                "media_type": fact.media_type,
            }
            reference["extensions"] = extensions
        records.append(record)
    records.sort(key=lambda item: str(item["source_case_key"]))
    return {
        "schema_version": "adapter-output/v1",
        "source_id": source_config.source_id,
        "revision_sha": source_config.verified_commit_sha,
        "adapter_id": source_config.adapter_strategy,
        "adapter_version": ADAPTER_VERSION,
        "records": records,
        "parse_errors": [],
        "coverage": {
            "input_case_count": len(records),
            "extracted_candidate_count": 0,
            "contract_valid_count": len(records),
            "quarantined_count": 0,
        },
    }


def generation_example_for(record: dict[str, Any], *, source_id: str, revision_sha: str) -> dict[str, Any]:
    references = record["asset_references"]
    if not isinstance(references, list) or not references or not all(isinstance(item, dict) for item in references):
        raise ContractError("adapter_mapping_invalid", "record must contain one or more output asset references")
    source_case_key = record["source_case_key"]
    prompt = copy.deepcopy(record["prompt"])
    pairings = record.get("pairings")
    if not isinstance(pairings, list) or not pairings or not all(isinstance(item, dict) for item in pairings):
        raise ContractError("adapter_mapping_invalid", "record pairings are missing")
    pairing_by_ref: dict[str, dict[str, Any]] = {}
    for pairing in pairings:
        asset_ref_id = pairing.get("asset_ref_id")
        if not isinstance(asset_ref_id, str) or asset_ref_id in pairing_by_ref:
            raise ContractError("adapter_mapping_invalid", "record pairing asset_ref_id is duplicated or invalid")
        if pairing.get("prompt_id") != prompt.get("prompt_id"):
            raise ContractError("adapter_mapping_invalid", "record pairing prompt_id does not match its prompt")
        pairing_by_ref[asset_ref_id] = pairing
    assets: list[dict[str, Any]] = []
    generations: list[dict[str, Any]] = []
    seen_asset_ids: set[str] = set()
    expected_prefix = f"asset-ref:{source_case_key}:"
    for reference in references:
        asset_ref_id = reference.get("asset_ref_id")
        if not isinstance(asset_ref_id, str) or not asset_ref_id.startswith(expected_prefix):
            raise ContractError("adapter_mapping_invalid", "asset_ref_id does not use the stable source-case prefix")
        pairing = pairing_by_ref.get(asset_ref_id)
        if pairing is None:
            raise ContractError("adapter_mapping_invalid", "asset reference has no unique pairing")
        content_sha256 = reference.get("content_sha256")
        if not isinstance(content_sha256, str):
            raise ContractError("asset_unresolved", "resolved Generation Example requires content_sha256")
        asset_id = f"asset:sha256:{content_sha256}"
        if asset_id in seen_asset_ids:
            raise ContractError("adapter_mapping_invalid", "one case cannot repeat identical output content")
        seen_asset_ids.add(asset_id)
        assets.append(
            {
                "asset_id": asset_id,
                "role": reference["role"],
                "content_sha256": content_sha256,
                "source_location": copy.deepcopy(reference["source_location"]),
                "extensions": copy.deepcopy(reference.get("extensions", {})),
            }
        )
        projected_pairing = copy.deepcopy(pairing)
        projected_pairing.pop("prompt_id", None)
        projected_pairing.pop("asset_ref_id", None)
        generation_suffix = asset_ref_id[len(expected_prefix) :]
        generations.append(
            {
                "generation_example_id": f"generation:{source_case_key}:{generation_suffix}",
                "prompt_id": prompt["prompt_id"],
                "input_asset_ids": [],
                "output_asset_ids": [asset_id],
                "generation_claim": copy.deepcopy(record["source_claim"]),
                "pairing": projected_pairing,
            }
        )
    if set(pairing_by_ref) != {reference.get("asset_ref_id") for reference in references}:
        raise ContractError("adapter_mapping_invalid", "record has a pairing without a matching asset reference")
    assets.sort(key=lambda item: str(item["asset_id"]))
    generations.sort(key=lambda item: str(item["generation_example_id"]))
    document = {
        "schema_version": "generation-example/v1",
        "source_id": source_id,
        "revision_sha": revision_sha,
        "state": "contract_valid",
        "source_case_key": source_case_key,
        "source_case_locator": copy.deepcopy(record["source_case_locator"]),
        "prompts": [prompt],
        "assets": assets,
        "generation_examples": generations,
        "rights_evidence": copy.deepcopy(record["rights_evidence"]),
    }
    # g0dam Generation Example fixtures are a frozen compatibility surface.
    # Only explicitly approved non-legacy source namespaces may propagate.
    extensions = record.get("extensions")
    if isinstance(extensions, dict):
        propagated = {
            key: copy.deepcopy(extensions[key])
            for key in (
                "joesai.source",
                "conardli.source",
                "freestylefly.source",
                "erickkkyt.source",
                "vigozhao.source",
                "chaosrealms.source",
            )
            if key in extensions
        }
        if propagated:
            document["extensions"] = propagated
    return document


def generation_examples(adapter_output: dict[str, Any]) -> list[dict[str, Any]]:
    records = adapter_output.get("records")
    if not isinstance(records, list):
        raise ContractError("adapter_mapping_invalid", "adapter records is missing")
    source_id = adapter_output.get("source_id")
    revision_sha = adapter_output.get("revision_sha")
    if not isinstance(source_id, str) or not isinstance(revision_sha, str):
        raise ContractError("adapter_mapping_invalid", "adapter source identity is missing")
    documents = [
        generation_example_for(record, source_id=source_id, revision_sha=revision_sha)
        for record in records
        if isinstance(record, dict)
    ]
    documents.sort(key=lambda item: str(item["source_case_key"]))
    return documents


def case_fingerprint_aggregate(adapter_output: dict[str, Any]) -> str:
    fingerprints: list[dict[str, Any]] = []
    for record in adapter_output.get("records", []):
        if not isinstance(record, dict):
            continue
        prompt = record.get("prompt")
        references = record.get("asset_references")
        location = record.get("source_case_locator")
        if not isinstance(prompt, dict) or not isinstance(references, list) or not references or not isinstance(location, dict):
            raise ContractError("aggregate_invalid", "record is incomplete for aggregate calculation")
        raw_text = prompt.get("raw_text")
        content_hashes = [
            reference.get("content_sha256")
            for reference in references
            if isinstance(reference, dict)
        ]
        case_id = location.get("native_id")
        if (
            not isinstance(raw_text, str)
            or not content_hashes
            or not all(isinstance(item, str) for item in content_hashes)
            or not isinstance(case_id, str)
        ):
            raise ContractError("aggregate_invalid", "record lacks native id, raw prompt, or resolved asset hash")
        if len(content_hashes) == 1:
            fingerprint = {
                "case_id": case_id,
                "prompt_sha256": prompt_sha256(raw_text),
                "image_sha256": content_hashes[0],
                "strong_pair": True,
            }
        else:
            fingerprint = {
                "case_id": case_id,
                "prompt_sha256": prompt_sha256(raw_text),
                "image_sha256s": content_hashes,
                "strong_pair": True,
            }
        fingerprints.append(fingerprint)
    payload = sorted(fingerprints, key=lambda item: str(item["case_id"]))
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def stable_payload_summary(adapter_output: dict[str, Any], examples: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    metrics_without_digest = {key: value for key, value in metrics.items() if key != "semantic_digest"}
    return {
        "adapter_output": adapter_output,
        "generation_examples": examples,
        "metrics": metrics_without_digest,
    }


def extraction_metrics(adapter_output: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
    records = adapter_output.get("records", [])
    case_signatures = {
        (
            record["prompt"]["prompt_id"],
            tuple(reference["content_sha256"] for reference in record["asset_references"]),
        )
        for record in records
        if isinstance(record, dict)
    }
    media_types = Counter(
        reference.get("extensions", {}).get("ingestion.asset", {}).get("media_type")
        for record in records
        if isinstance(record, dict)
        for reference in record.get("asset_references", [])
        if isinstance(reference, dict)
    )
    generation_count = sum(
        len(document.get("generation_examples", []))
        for document in examples
        if isinstance(document, dict)
    )
    adapter_strategy = adapter_output.get("adapter_id")
    if not isinstance(adapter_strategy, str):
        raise ContractError("adapter_mapping_invalid", "adapter output lacks a supported adapter strategy")
    metrics = {
        "schema_version": metrics_schema_version(adapter_strategy),
        "source_id": adapter_output["source_id"],
        "revision_sha": adapter_output["revision_sha"],
        "observed_case_count": len(records),
        "exact_prompt_count": len(records),
        "paired_output_count": len(records),
        "valid_case_count": len(records),
        "unique_valid_case_count": len(case_signatures),
        "pair_rate": 1.0 if records else 0.0,
        "broken_asset_count": 0,
        "duplicate_estimate": len(records) - len(case_signatures),
        "generation_example_count": generation_count,
        "case_fingerprint_aggregate_sha256": case_fingerprint_aggregate(adapter_output),
        "asset_media_type_counts": {key: media_types[key] for key in sorted(media_types) if isinstance(key, str)},
    }
    metrics["semantic_digest"] = stable_sha256(stable_payload_summary(adapter_output, examples, metrics))
    return metrics
