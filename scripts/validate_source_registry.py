#!/usr/bin/env python3
"""Fail-closed validator for TASK-0001 source-audit-v1 and sources-v1.

The registry is authored in the JSON profile of YAML 1.2 so this validator can
remain dependency-free.  It validates the two checked-in JSON Schemas with the
supported schema subset and then enforces the cross-file admission, family,
rights, and pilot invariants that JSON Schema alone cannot express.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
EXPECTED_CONTINUOUS_SOURCES = {
    "g0dam-work-prompts": "structured_manifest_json",
    "joesai-commercial-prompts": "markdown_prompt_pages_with_manifest",
    "conardli-gpt-image-2-101": "compiled_multi_category_case_gallery",
    "freestylefly-awesome-gpt-image-2": "centralized_case_manifest",
    "erickkkyt-awesome-gptimage2-prompts": "structured_prompt_image_manifest",
    "vigozhao-ai-visual-prompt-cookbook": "style_json_with_preview_assets",
}
EXPECTED_FIXED_HISTORY_SOURCES = {
    "chaosrealmsai-gpt-image-2-gallery": "meta_json_with_three_webp_outputs",
}
EXPECTED_ACTIVE_SOURCES = {**EXPECTED_CONTINUOUS_SOURCES, **EXPECTED_FIXED_HISTORY_SOURCES}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema(value: Any, schema: JsonObject, path: str = "$") -> list[str]:
    """Validate the deliberate, dependency-free subset used by the two schemas."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not type_matches(value, expected_type):
            return [f"{path}: expected {expected_type}"]
    elif isinstance(expected_type, list):
        if not any(isinstance(item, str) and type_matches(value, item) for item in expected_type):
            return [f"{path}: expected one of {expected_type}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: value {value!r} is not in enum")
    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: string is shorter than {minimum}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            import re

            if not re.search(pattern, value):
                errors.append(f"{path}: string does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: value is below minimum {minimum}")
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: value exceeds maximum {maximum}")
    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(validate_schema(value[key], child_schema, f"{path}.{key}"))
        if schema.get("additionalProperties") is False and isinstance(properties, dict):
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: array has fewer than {minimum} items")
        maximum = schema.get("maxItems")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: array has more than {maximum} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, f"{path}[{index}]"))
        if schema.get("uniqueItems") is True:
            fingerprints = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                errors.append(f"{path}: array contains duplicate items")
    return errors


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def add_error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def metric_value(metrics: JsonObject, key: str) -> int | float | None:
    value = metrics.get(key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def validate_semantics(audit: JsonObject, registry: JsonObject) -> tuple[list[str], JsonObject]:
    errors: list[str] = []
    records = audit.get("records")
    sources = registry.get("sources")
    exclusions = registry.get("exclusions")
    pilots = registry.get("pilots")
    if not isinstance(records, list) or not isinstance(sources, list) or not isinstance(exclusions, list) or not isinstance(pilots, list):
        return ["semantic validation cannot run because core arrays are malformed"], {}

    record_by_source: dict[str, JsonObject] = {}
    record_by_candidate: dict[str, JsonObject] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"audit.records[{index}] is not an object")
            continue
        source_id = record.get("source_id")
        candidate_key = record.get("candidate_key")
        if not nonempty_string(source_id) or not nonempty_string(candidate_key):
            errors.append(f"audit.records[{index}] has no usable source_id or candidate_key")
            continue
        if source_id in record_by_source:
            errors.append(f"duplicate audit source_id: {source_id}")
        if candidate_key in record_by_candidate:
            errors.append(f"duplicate audit candidate_key: {candidate_key}")
        record_by_source[source_id] = record
        record_by_candidate[candidate_key] = record
        metrics = record.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"audit {source_id}: metrics is missing")
            continue
        complete = metrics.get("metrics_complete") is True
        observed = metric_value(metrics, "observed_case_count")
        exact = metric_value(metrics, "exact_prompt_count")
        paired = metric_value(metrics, "paired_output_count")
        valid = metric_value(metrics, "valid_case_count")
        unique = metric_value(metrics, "unique_valid_case_count")
        pair_rate = metric_value(metrics, "pair_rate")
        broken = metric_value(metrics, "broken_asset_count")
        duplicate = metric_value(metrics, "duplicate_estimate")
        if complete:
            add_error(errors, all(value is not None for value in (observed, exact, paired, valid, unique, pair_rate, broken, duplicate)), f"audit {source_id}: complete metrics must have no null values")
            if all(isinstance(value, (int, float)) for value in (observed, exact, paired, valid, unique, pair_rate, broken, duplicate)):
                add_error(errors, observed >= 0 and exact >= 0 and paired >= 0 and valid >= 0 and unique >= 0 and broken >= 0 and duplicate >= 0, f"audit {source_id}: metrics may not be negative")
                add_error(errors, exact <= observed and paired <= observed and valid <= exact and valid <= paired and unique <= valid, f"audit {source_id}: count relationship is invalid")
                expected_rate = (valid / observed) if observed else 0.0
                add_error(errors, math.isclose(float(pair_rate), expected_rate, rel_tol=0.0, abs_tol=1e-12), f"audit {source_id}: pair_rate does not equal valid_case_count / observed_case_count")
                add_error(errors, duplicate == valid - unique, f"audit {source_id}: duplicate_estimate does not equal valid_case_count - unique_valid_case_count")
        else:
            partial_values = (observed, exact, paired, valid, unique, pair_rate, broken, duplicate)
            add_error(errors, all(value is None for value in partial_values), f"audit {source_id}: incomplete metrics must remain null rather than be treated as admission-grade partial counts")
            add_error(errors, record.get("recommended_status") != "active", f"audit {source_id}: incomplete metrics cannot recommend active")
        add_error(errors, nonempty_string(record.get("status_reason")), f"audit {source_id}: a nonempty status reason is required")

    coverage = audit.get("candidate_coverage")
    if isinstance(coverage, dict):
        add_error(errors, coverage.get("uncovered_candidate_count") == 0, "audit candidate coverage is not zero-gap")
        add_error(errors, coverage.get("unique_repositories") == len(record_by_candidate), "audit unique repository count does not match records")
    else:
        errors.append("audit candidate_coverage is missing")

    registry_candidate_map: dict[str, JsonObject] = {}
    source_ids: set[str] = set()
    repository_ids: set[str] = set()
    # Family references may point to a canonical source later in the registry
    # order, so construct this lookup before evaluating individual sources.
    source_by_id: dict[str, JsonObject] = {
        source.get("source_id"): source
        for source in sources
        if isinstance(source, dict) and nonempty_string(source.get("source_id"))
    }
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"registry.sources[{index}] is not an object")
            continue
        source_id = source.get("source_id")
        candidate_key = source.get("candidate_key")
        if not nonempty_string(source_id) or not nonempty_string(candidate_key):
            errors.append(f"registry.sources[{index}] missing source_id or candidate_key")
            continue
        if source_id in source_ids:
            errors.append(f"duplicate registry source_id: {source_id}")
        source_ids.add(source_id)
        if candidate_key in registry_candidate_map:
            errors.append(f"candidate key appears more than once in registry sources/exclusions: {candidate_key}")
        registry_candidate_map[candidate_key] = source
        record = record_by_source.get(source_id)
        if record is None:
            errors.append(f"registry source {source_id} has no audit record")
            continue
        add_error(errors, record.get("candidate_key") == candidate_key, f"registry source {source_id}: candidate_key diverges from audit")
        status = source.get("status")
        audit_status = record.get("recommended_status")
        lifecycle_status = status in {"paused", "retired"}
        add_error(
            errors,
            audit_status == status or lifecycle_status and audit_status == "active",
            f"registry source {source_id}: status diverges from audit or an unsupported lifecycle transition was used",
        )
        repository = source.get("repository")
        audited_repository = record.get("repository")
        if not isinstance(repository, dict) or not isinstance(audited_repository, dict):
            errors.append(f"registry source {source_id}: repository binding is malformed")
            continue
        add_error(errors, repository.get("url") == audited_repository.get("url"), f"registry source {source_id}: repository URL diverges from audit")
        add_error(errors, repository.get("verified_commit_sha") == audited_repository.get("verified_commit_sha"), f"registry source {source_id}: fixed commit diverges from audit")
        add_error(errors, source.get("family") == record.get("family"), f"registry source {source_id}: family diverges from audit")
        audit_content = record.get("content")
        if isinstance(audit_content, dict) and isinstance(source.get("content"), dict):
            for key in ("structure_type", "adapter_strategy", "model_scope"):
                add_error(errors, source["content"].get(key) == audit_content.get(key), f"registry source {source_id}: content.{key} diverges from audit")
        audit_rights = record.get("rights")
        source_rights = source.get("rights")
        if isinstance(audit_rights, dict) and isinstance(source_rights, dict):
            for key in ("repository_license", "prompt_policy", "asset_policy"):
                add_error(errors, source_rights.get(key) == audit_rights.get(key), f"registry source {source_id}: rights.{key} diverges from audit")
        audit_ref = source.get("audit_ref")
        add_error(errors, isinstance(audit_ref, dict) and audit_ref.get("source_id") == source_id and audit_ref.get("verified_commit_sha") == repository.get("verified_commit_sha"), f"registry source {source_id}: audit_ref does not bind this source and fixed commit")
        repo_id = repository.get("repository_id")
        if repo_id is not None:
            if repo_id in repository_ids:
                errors.append(f"duplicate non-null repository_id: {repo_id}")
            repository_ids.add(repo_id)
        family = source.get("family")
        publication = source.get("publication")
        rights = source.get("rights")
        admission = source.get("admission")
        content = source.get("content")
        if not isinstance(family, dict) or not isinstance(publication, dict) or not isinstance(rights, dict):
            errors.append(f"registry source {source_id}: family, publication, or rights is malformed")
            continue
        role = family.get("role")
        if role == "canonical":
            add_error(errors, family.get("canonical_source_id") == source_id, f"registry source {source_id}: canonical family must self-reference")
        if role in {"mirror", "backup", "translation", "derived"}:
            add_error(errors, family.get("canonical_source_id") in source_by_id, f"registry source {source_id}: family canonical source is missing")
            add_error(errors, publication.get("ingestion_policy") == "provenance_only", f"registry source {source_id}: noncanonical family cannot use full ingestion")
            add_error(errors, status != "active", f"registry source {source_id}: noncanonical family cannot be active")
        restrictive_rights = {"unknown", "review_required", "internal_only", "blocked"}
        if rights.get("prompt_policy") in restrictive_rights or rights.get("asset_policy") in restrictive_rights:
            add_error(errors, publication.get("auto_publish") is False, f"registry source {source_id}: restrictive rights require auto_publish=false")
        if status in {"paused", "retired"}:
            sync = source.get("sync")
            add_error(errors, isinstance(sync, dict) and sync.get("enabled") is False, f"registry source {source_id}: paused or retired source must disable sync")
        if status == "active":
            metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
            add_error(errors, record.get("audit_scope") == "full_case_audit", f"active source {source_id}: audit scope is not full_case_audit")
            add_error(errors, metrics.get("metrics_complete") is True, f"active source {source_id}: metrics are incomplete")
            add_error(errors, role == "canonical", f"active source {source_id}: family role must be canonical")
            add_error(errors, publication.get("ingestion_policy") == "full", f"active source {source_id}: ingestion_policy must be full")
            sync = source.get("sync")
            ingestion = source.get("ingestion")
            if isinstance(ingestion, dict) and ingestion.get("mode") == "fixed_history":
                add_error(
                    errors,
                    source_id in EXPECTED_FIXED_HISTORY_SOURCES
                    and ingestion.get("one_shot_import_only") is True
                    and isinstance(sync, dict)
                    and sync.get("enabled") is False,
                    f"active source {source_id}: fixed-history source must be one-shot and sync-disabled",
                )
            else:
                add_error(
                    errors,
                    source_id in EXPECTED_CONTINUOUS_SOURCES and isinstance(sync, dict) and sync.get("enabled") is True,
                    f"active source {source_id}: continuous source must enable sync",
                )
            add_error(errors, nonempty_string(repository.get("repository_id")), f"active source {source_id}: repository_id is required")
            add_error(errors, nonempty_string(repository.get("default_branch")) and nonempty_string(repository.get("verified_commit_sha")), f"active source {source_id}: default branch and fixed commit are required")
            add_error(errors, isinstance(content, dict) and nonempty_string(content.get("adapter_strategy")), f"active source {source_id}: deterministic adapter strategy is required")
            if isinstance(admission, dict):
                unique = metric_value(metrics, "unique_valid_case_count")
                pair_rate = metric_value(metrics, "pair_rate")
                minimum_cases = admission.get("minimum_valid_cases")
                minimum_pair = admission.get("minimum_pair_rate")
                add_error(errors, isinstance(minimum_cases, int) and isinstance(unique, (int, float)) and unique >= minimum_cases, f"active source {source_id}: unique valid cases do not satisfy threshold")
                add_error(errors, isinstance(minimum_pair, (int, float)) and isinstance(pair_rate, (int, float)) and pair_rate >= minimum_pair, f"active source {source_id}: pair rate does not satisfy threshold")
            else:
                errors.append(f"active source {source_id}: admission is malformed")
            quality = record.get("quality_sampling")
            if isinstance(quality, dict):
                result = quality.get("human_review_result")
                add_error(errors, result in {"pass", "pass_with_publication_restriction"}, f"active source {source_id}: quality sample has no passing human review")
                unique = metric_value(metrics, "unique_valid_case_count")
                if source_id in EXPECTED_FIXED_HISTORY_SOURCES:
                    expected_sample = 60
                elif unique:
                    expected_sample = min(int(unique), 50, max(20, math.ceil(float(unique) * 0.10)))
                else:
                    expected_sample = 0
                add_error(errors, quality.get("sample_size") == expected_sample, f"active source {source_id}: quality sample size is not Rule-011 compliant")
            else:
                errors.append(f"active source {source_id}: quality sampling is missing")

    for index, exclusion in enumerate(exclusions):
        if not isinstance(exclusion, dict):
            errors.append(f"registry.exclusions[{index}] is not an object")
            continue
        candidate_key = exclusion.get("candidate_key")
        source_id = exclusion.get("source_id")
        if not nonempty_string(candidate_key) or not nonempty_string(source_id):
            errors.append(f"registry.exclusions[{index}] missing candidate_key or source_id")
            continue
        if candidate_key in registry_candidate_map:
            errors.append(f"candidate key appears more than once in registry sources/exclusions: {candidate_key}")
        registry_candidate_map[candidate_key] = exclusion
        record = record_by_source.get(source_id)
        if record is None:
            errors.append(f"registry exclusion {source_id} has no audit record")
            continue
        add_error(errors, record.get("candidate_key") == candidate_key, f"registry exclusion {source_id}: candidate key diverges from audit")
        add_error(errors, record.get("audit_scope") == "out_of_scope_mapping", f"registry exclusion {source_id}: only out_of_scope audit records may be excluded")

    add_error(errors, set(registry_candidate_map) == set(record_by_candidate), "registry source/exclusion candidate mapping does not exactly cover the audit")

    pilot_source_ids: set[str] = set()
    pilot_structures: set[str] = set()
    add_error(errors, len(pilots) == len(EXPECTED_ACTIVE_SOURCES), "pilot list must cover the seven approved active sources")
    for index, pilot in enumerate(pilots):
        if not isinstance(pilot, dict):
            errors.append(f"registry.pilots[{index}] is not an object")
            continue
        source_id = pilot.get("source_id")
        structure = pilot.get("structure_type")
        source = source_by_id.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            errors.append(f"pilot {source_id!r} has no registry source")
            continue
        add_error(errors, source.get("status") in {"active", "paused", "retired"}, f"pilot {source_id}: source has no admitted lifecycle status")
        pilot_config = source.get("pilot")
        add_error(errors, isinstance(pilot_config, dict) and pilot_config.get("selected") is True, f"pilot {source_id}: source does not opt into pilot selection")
        if source_id in pilot_source_ids:
            errors.append(f"duplicate pilot source_id: {source_id}")
        pilot_source_ids.add(source_id)
        if structure in pilot_structures:
            errors.append(f"duplicate pilot structure_type: {structure}")
        pilot_structures.add(structure)
        content = source.get("content")
        add_error(errors, isinstance(content, dict) and content.get("structure_type") == structure, f"pilot {source_id}: structure type diverges from source content")
    add_error(errors, pilot_source_ids == set(EXPECTED_ACTIVE_SOURCES), "pilot source ids do not equal the approved active source set")
    for source_id, structure in EXPECTED_ACTIVE_SOURCES.items():
        source = source_by_id.get(source_id)
        add_error(
            errors,
            isinstance(source, dict) and source.get("status") in {"active", "paused", "retired"},
            f"approved source {source_id}: source has no admitted lifecycle status",
        )
        add_error(errors, source_id in pilot_source_ids and structure in pilot_structures, f"approved source {source_id}: pilot structure is missing")

    summary = {
        "audit_records": len(records),
        "registry_sources": len(sources),
        "registry_exclusions": len(exclusions),
        "active_sources": sum(source.get("status") == "active" for source in sources if isinstance(source, dict)),
        "pilots": len(pilots),
        "gate_001_candidate_coverage": not any("coverage" in error or "mapping" in error for error in errors),
        "gate_002_audit_integrity": not any(error.startswith("audit ") or "audit candidate" in error for error in errors),
        "gate_003_registry_contract": not any(error.startswith("registry source") or "active source" in error or "repository_id" in error for error in errors),
        "gate_004_end_to_end": len(pilots) == len(EXPECTED_ACTIVE_SOURCES) and not any("pilot" in error or "mapping" in error for error in errors),
    }
    return errors, summary


def validate_documents(audit: JsonObject, registry: JsonObject, audit_schema: JsonObject, registry_schema: JsonObject) -> JsonObject:
    errors = validate_schema(audit, audit_schema, "audit") + validate_schema(registry, registry_schema, "registry")
    semantic_errors, summary = validate_semantics(audit, registry)
    errors.extend(semantic_errors)
    return {"ok": not errors, "errors": errors, "summary": summary}


def run_self_tests(audit: JsonObject, registry: JsonObject, audit_schema: JsonObject, registry_schema: JsonObject) -> list[str]:
    failures: list[str] = []
    source_list = registry.get("sources") if isinstance(registry.get("sources"), list) else []
    active = next((source for source in source_list if isinstance(source, dict) and source.get("status") == "active"), None)
    fixed_history = next((source for source in source_list if isinstance(source, dict) and isinstance(source.get("ingestion"), dict) and source["ingestion"].get("mode") == "fixed_history"), None)
    if not isinstance(active, dict) or not isinstance(fixed_history, dict) or len(source_list) < 2:
        return ["self-test fixture needs one active, one fixed-history source, and two registry sources"]
    duplicate_id = copy.deepcopy(registry)
    duplicate_id["sources"][1]["repository"]["repository_id"] = duplicate_id["sources"][0]["repository"]["repository_id"]
    if validate_documents(audit, duplicate_id, audit_schema, registry_schema)["ok"]:
        failures.append("duplicate repository_id mutation did not fail")
    missing_audit = copy.deepcopy(audit)
    missing_audit["records"] = [record for record in missing_audit["records"] if record.get("source_id") != active["source_id"]]
    if validate_documents(missing_audit, registry, audit_schema, registry_schema)["ok"]:
        failures.append("missing active audit mutation did not fail")
    bad_fixed_history = copy.deepcopy(registry)
    target = next(source for source in bad_fixed_history["sources"] if source.get("source_id") == fixed_history["source_id"])
    target["sync"]["enabled"] = True
    if validate_documents(audit, bad_fixed_history, audit_schema, registry_schema)["ok"]:
        failures.append("fixed-history scheduler mutation did not fail")
    noncanonical_audit = copy.deepcopy(audit)
    noncanonical_registry = copy.deepcopy(registry)
    noncanonical_source = copy.deepcopy(noncanonical_registry["sources"][0])
    noncanonical_record = copy.deepcopy(
        next(record for record in noncanonical_audit["records"] if record.get("source_id") == noncanonical_source["source_id"])
    )
    noncanonical_source["source_id"] = "self-test-derived-source"
    noncanonical_source["candidate_key"] = "self-test/derived-source"
    noncanonical_source["repository"]["repository_id"] = "self-test-derived-repository"
    noncanonical_source["repository"]["url"] = "https://example.com/self-test-derived-source"
    noncanonical_source["status"] = "probation"
    noncanonical_source["family"] = {"family_id": "family-self-test", "canonical_source_id": active["source_id"], "role": "derived"}
    noncanonical_source["publication"]["ingestion_policy"] = "provenance_only"
    noncanonical_source["audit_ref"]["source_id"] = noncanonical_source["source_id"]
    noncanonical_registry["sources"].append(noncanonical_source)
    noncanonical_record["source_id"] = noncanonical_source["source_id"]
    noncanonical_record["candidate_key"] = noncanonical_source["candidate_key"]
    noncanonical_record["repository"].update(copy.deepcopy(noncanonical_source["repository"]))
    noncanonical_record["recommended_status"] = "probation"
    noncanonical_record["family"] = copy.deepcopy(noncanonical_source["family"])
    noncanonical_audit["records"].append(noncanonical_record)
    noncanonical_audit["candidate_coverage"]["unique_repositories"] += 1
    if not validate_documents(noncanonical_audit, noncanonical_registry, audit_schema, registry_schema)["ok"]:
        failures.append("valid noncanonical provenance-only fixture did not pass")
    noncanonical_registry["sources"][-1]["publication"]["ingestion_policy"] = "full"
    if validate_documents(noncanonical_audit, noncanonical_registry, audit_schema, registry_schema)["ok"]:
        failures.append("noncanonical full-ingestion mutation did not fail")
    bad_rights = copy.deepcopy(registry)
    target = next(source for source in bad_rights["sources"] if source.get("source_id") == active["source_id"])
    target["publication"]["auto_publish"] = True
    if validate_documents(audit, bad_rights, audit_schema, registry_schema)["ok"]:
        failures.append("restrictive-rights public mutation did not fail")
    bad_lifecycle = copy.deepcopy(registry)
    target = next(source for source in bad_lifecycle["sources"] if source.get("source_id") == active["source_id"])
    target["status"] = "paused"
    target["sync"]["enabled"] = True
    if validate_documents(audit, bad_lifecycle, audit_schema, registry_schema)["ok"]:
        failures.append("paused scheduler-enabled mutation did not fail")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--audit-schema", required=True, type=Path)
    parser.add_argument("--registry-schema", required=True, type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--determinism-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        audit = load_json(args.audit)
        registry = load_json(args.registry)
        audit_schema = load_json(args.audit_schema)
        registry_schema = load_json(args.registry_schema)
    except (OSError, json.JSONDecodeError) as exc:
        report = {"ok": False, "errors": [f"input read failed: {type(exc).__name__}: {exc}"], "summary": {}}
        print(json.dumps(report, ensure_ascii=False, sort_keys=True) if args.json else report["errors"][0])
        return 1
    report = validate_documents(audit, registry, audit_schema, registry_schema)
    if args.determinism_check:
        repeated = validate_documents(audit, registry, audit_schema, registry_schema)
        report["determinism_check"] = report == repeated
        if not report["determinism_check"]:
            report["ok"] = False
            report["errors"].append("validator result is not deterministic for identical inputs")
    if args.self_test:
        self_test_failures = run_self_tests(audit, registry, audit_schema, registry_schema)
        report["self_test_failures"] = self_test_failures
        if self_test_failures:
            report["ok"] = False
            report["errors"].extend(self_test_failures)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    elif report["ok"]:
        print("PASS: source audit, source registry, cross-file invariants, and pilot gate are valid")
    else:
        print("FAIL:")
        for error in report["errors"]:
            print(f"- {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
