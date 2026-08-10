#!/usr/bin/env python3
"""Fail-closed, local-only validator for Content Contract v1.

The repository stores registry YAML in JSON profile, so this validator uses only
the Python standard library. It validates the deliberately small JSON Schema
subset used by the two v1 schemas and then applies the cross-document rules
that JSON Schema cannot express: source/commit binding, TASK-0001 quality
evidence, reference closure, pairing ceilings, coverage accounting, and the
Adapter-to-Generation projection boundary.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]
JsonValue = Any

EXPECTED_PILOTS = {
    "g0dam-work-prompts": "structured_manifest_json",
    "joesai-commercial-prompts": "markdown_prompt_pages_with_manifest",
    "conardli-gpt-image-2-101": "compiled_multi_category_case_gallery",
}
STRONG_METHODS = {
    "explicit_structured_reference",
    "explicit_markdown_block",
    "stable_native_mapping",
}
STANDARD_FIELD_NAMES = {
    "schema_version",
    "source_id",
    "revision_sha",
    "adapter_id",
    "adapter_version",
    "records",
    "parse_errors",
    "coverage",
    "source_case_key",
    "source_case_locator",
    "state",
    "prompt",
    "prompt_id",
    "raw_text",
    "language",
    "source_location",
    "source_path",
    "source_url",
    "native_id",
    "selector",
    "asset_references",
    "asset_ref_id",
    "asset_id",
    "role",
    "resolution_state",
    "content_sha256",
    "pairings",
    "method",
    "status",
    "confidence",
    "evidence",
    "source_claim",
    "generation_claim",
    "evidence_status",
    "model_raw",
    "parameters_raw",
    "raw_tags",
    "rights_evidence",
    "prompt_rights_status",
    "asset_rights_status",
    "evidence_urls",
    "note",
    "prompts",
    "assets",
    "generation_examples",
    "generation_example_id",
    "input_asset_ids",
    "output_asset_ids",
    "extensions",
    "input_case_count",
    "extracted_candidate_count",
    "contract_valid_count",
    "quarantined_count",
    "stage",
    "error_code",
    "message",
}
FORBIDDEN_DECISION_FIELDS = {
    "canonical",
    "canonical_id",
    "canonical_status",
    "category",
    "classification",
    "quality",
    "quality_status",
    "quality_approved",
    "rights_approved",
    "rights_decision",
    "publication_status",
    "publish_status",
    "public_status",
    "visibility",
    "auto_publish",
    "release_status",
    "decision",
}
EXTENSION_NAME = re.compile(r"^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_.-]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> JsonValue:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_prompt(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def prompt_sha256(value: str) -> str:
    return hashlib.sha256(normalize_prompt(value).encode("utf-8")).hexdigest()


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


def resolve_ref(root: JsonObject, reference: str) -> JsonObject:
    if not reference.startswith("#/"):
        raise ValueError(f"unsupported schema reference {reference!r}")
    current: Any = root
    for component in reference[2:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or component not in current:
            raise ValueError(f"unresolvable schema reference {reference!r}")
        current = current[component]
    if not isinstance(current, dict):
        raise ValueError(f"schema reference {reference!r} does not resolve to an object")
    return current


def validate_json_schema(value: JsonValue, schema: JsonObject, root: JsonObject, path: str = "$") -> list[str]:
    """Validate the dependency-free Draft 2020-12 subset used in this task."""
    errors: list[str] = []
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str):
            return [f"{path}: schema $ref is not a string"]
        try:
            errors.extend(validate_json_schema(value, resolve_ref(root, reference), root, path))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
        sibling_schema = {key: item for key, item in schema.items() if key != "$ref"}
        if sibling_schema:
            errors.extend(validate_json_schema(value, sibling_schema, root, path))
        return errors

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        alternatives = [validate_json_schema(value, item, root, path) for item in any_of if isinstance(item, dict)]
        if not alternatives or not any(not item_errors for item_errors in alternatives):
            errors.append(f"{path}: does not satisfy any allowed schema alternative")
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = sum(1 for item in one_of if isinstance(item, dict) and not validate_json_schema(value, item, root, path))
        if matches != 1:
            errors.append(f"{path}: must satisfy exactly one schema alternative")
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            if isinstance(item, dict):
                errors.extend(validate_json_schema(value, item, root, path))
    not_schema = schema.get("not")
    if isinstance(not_schema, dict) and not validate_json_schema(value, not_schema, root, path):
        errors.append(f"{path}: matches a prohibited schema")
    conditional = schema.get("if")
    if isinstance(conditional, dict):
        branch = "then" if not validate_json_schema(value, conditional, root, path) else "else"
        branch_schema = schema.get(branch)
        if isinstance(branch_schema, dict):
            errors.extend(validate_json_schema(value, branch_schema, root, path))

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        if not type_matches(value, expected_type):
            return errors + [f"{path}: expected {expected_type}"]
    elif isinstance(expected_type, list):
        allowed = [item for item in expected_type if isinstance(item, str)]
        if not any(type_matches(value, item) for item in allowed):
            return errors + [f"{path}: expected one of {allowed}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        errors.append(f"{path}: value {value!r} is not in enum")

    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: string is shorter than {minimum}")
        maximum = schema.get("maxLength")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: string exceeds {maximum}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if not re.search(pattern, value):
                    errors.append(f"{path}: string does not match pattern")
            except re.error:
                errors.append(f"{path}: schema contains an invalid pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: value is below minimum")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: value exceeds maximum")
    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                errors.extend(validate_json_schema(value[key], child_schema, root, f"{path}.{key}"))
        property_names = schema.get("propertyNames")
        if isinstance(property_names, dict):
            for key in value:
                errors.extend(validate_json_schema(key, property_names, root, f"{path}.<property-name>"))
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{path}: array has fewer than {minimum} items")
        if isinstance(maximum, int) and len(value) > maximum:
            errors.append(f"{path}: array exceeds {maximum} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_json_schema(item, item_schema, root, f"{path}[{index}]"))
        if schema.get("uniqueItems") is True:
            item_fingerprints = [canonical_json(item) for item in value]
            if len(item_fingerprints) != len(set(item_fingerprints)):
                errors.append(f"{path}: array contains duplicate items")
    return errors


def sorted_by(values: list[Any], key: Any, path: str) -> list[str]:
    rendered = [str(key(item)) for item in values]
    return [] if rendered == sorted(rendered) else [f"{path}: items are not in deterministic order"]


def source_location_errors(value: Any, path: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: source location is not an object"]
    source_path = value.get("source_path")
    source_url = value.get("source_url")
    if not nonempty_string(source_path) and not nonempty_string(source_url):
        return [f"{path}: requires source_path or source_url"]
    return []


def source_claim_errors(value: Any, path: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{path}: source claim is not an object"]
    status = value.get("evidence_status")
    model = value.get("model_raw")
    parameters = value.get("parameters_raw")
    errors: list[str] = []
    if status == "unknown" and (model is not None or parameters is not None):
        errors.append(f"{path}: unknown claim must retain null model_raw and parameters_raw")
    if status == "source_claimed" and not nonempty_string(model):
        errors.append(f"{path}: source_claimed model requires nonempty source text")
    return errors


def extension_and_boundary_errors(value: Any, path: str = "$") -> list[str]:
    """Reject decision fields and extensions that try to redefine a standard field."""
    errors: list[str] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(extension_and_boundary_errors(item, f"{path}[{index}]"))
        return errors
    if not isinstance(value, dict):
        return errors
    for key, item in value.items():
        lower_key = key.lower()
        if key == "extensions":
            if not isinstance(item, dict):
                errors.append(f"{path}.extensions: must be an object")
                continue
            for extension_key in item:
                if not EXTENSION_NAME.fullmatch(extension_key):
                    errors.append(f"{path}.extensions.{extension_key}: extension key is not namespaced")
                tail = extension_key.rsplit(".", 1)[-1]
                if tail in STANDARD_FIELD_NAMES:
                    errors.append(f"{path}.extensions.{extension_key}: extension shadows standard field {tail}")
            continue
        if lower_key in FORBIDDEN_DECISION_FIELDS:
            errors.append(f"{path}.{key}: contract may not carry a downstream decision field")
        errors.extend(extension_and_boundary_errors(item, f"{path}.{key}"))
    return errors


def registry_indexes(registry: Any, audit: Any) -> tuple[dict[str, JsonObject], dict[str, JsonObject], list[str]]:
    errors: list[str] = []
    source_index: dict[str, JsonObject] = {}
    audit_index: dict[str, JsonObject] = {}
    sources = registry.get("sources") if isinstance(registry, dict) else None
    records = audit.get("records") if isinstance(audit, dict) else None
    if not isinstance(sources, list):
        return source_index, audit_index, ["registry.sources is missing or malformed"]
    if not isinstance(records, list):
        return source_index, audit_index, ["audit.records is missing or malformed"]
    for index, source in enumerate(sources):
        source_id = source.get("source_id") if isinstance(source, dict) else None
        if not nonempty_string(source_id):
            errors.append(f"registry.sources[{index}] has no usable source_id")
        elif source_id in source_index:
            errors.append(f"registry has duplicate source_id {source_id}")
        else:
            source_index[source_id] = source
    for index, record in enumerate(records):
        source_id = record.get("source_id") if isinstance(record, dict) else None
        if not nonempty_string(source_id):
            errors.append(f"audit.records[{index}] has no usable source_id")
        elif source_id in audit_index:
            errors.append(f"audit has duplicate source_id {source_id}")
        else:
            audit_index[source_id] = record
    return source_index, audit_index, errors


def source_binding_errors(
    source_id: Any,
    revision_sha: Any,
    registry: dict[str, JsonObject],
    audit: dict[str, JsonObject],
    path: str,
) -> list[str]:
    errors: list[str] = []
    if not nonempty_string(source_id):
        return [f"{path}: source_id is unusable"]
    source = registry.get(source_id)
    if source is None:
        return [f"{path}: source_id {source_id!r} is absent from sources-v1"]
    if source.get("status") != "active":
        errors.append(f"{path}: source_id {source_id!r} is not active")
    repository = source.get("repository")
    expected_revision = repository.get("verified_commit_sha") if isinstance(repository, dict) else None
    if revision_sha != expected_revision:
        errors.append(f"{path}: revision_sha does not equal registered verified commit")
    audited = audit.get(source_id)
    if audited is None:
        errors.append(f"{path}: source_id has no audit record")
    else:
        audit_repository = audited.get("repository")
        audit_revision = audit_repository.get("verified_commit_sha") if isinstance(audit_repository, dict) else None
        if audited.get("recommended_status") != "active":
            errors.append(f"{path}: audit record is not active")
        if audit_revision != revision_sha:
            errors.append(f"{path}: audit verified commit does not bind revision_sha")
    return errors


def discover_quality_samples(root: Path) -> tuple[dict[str, list[JsonObject]], JsonObject, list[str]]:
    """Read the task-0001 history, fail closed on conflicting authorities."""
    errors: list[str] = []
    paths = sorted(root.rglob("active-candidate-full-metrics.json"))
    if not paths:
        return {}, {}, ["TASK-0001 active-candidate-full-metrics.json is missing"]
    candidates: list[tuple[Path, dict[str, list[JsonObject]], str]] = []
    required_sample_fields = {
        "case_id",
        "prompt_source_path",
        "image_path",
        "prompt_sha256",
        "image_sha256",
    }
    for path in paths:
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read TASK-0001 metrics {path}: {exc}")
            continue
        audits = data.get("audits") if isinstance(data, dict) else None
        if not isinstance(audits, list):
            errors.append(f"TASK-0001 metrics {path} has no audits list")
            continue
        sample_index: dict[str, list[JsonObject]] = {}
        malformed = False
        for audit in audits:
            source_id = audit.get("source_id") if isinstance(audit, dict) else None
            quality_sampling = audit.get("quality_sampling") if isinstance(audit, dict) else None
            samples = quality_sampling.get("samples") if isinstance(quality_sampling, dict) else None
            if not nonempty_string(source_id) or not isinstance(samples, list):
                malformed = True
                break
            prepared: list[JsonObject] = []
            for sample in samples:
                if not isinstance(sample, dict) or not required_sample_fields.issubset(sample):
                    malformed = True
                    break
                prepared.append({key: sample[key] for key in sorted(required_sample_fields)})
            if malformed:
                break
            sample_index[source_id] = sorted(prepared, key=canonical_json)
        if malformed:
            errors.append(f"TASK-0001 metrics {path} has malformed quality samples")
            continue
        candidates.append((path, sample_index, fingerprint(sample_index)))
    if errors:
        return {}, {}, sorted(errors)
    fingerprints = {item[2] for item in candidates}
    if len(fingerprints) == 1:
        selected = candidates[0]
        return selected[1], {
            "authority": "content-equivalent-task-0001-metrics",
            "paths": [str(item[0]) for item in candidates],
            "fingerprint": selected[2],
        }, []
    historical = [item for item in candidates if "history" in {part.lower() for part in item[0].parts}]
    if len(historical) == 1:
        selected = historical[0]
        return selected[1], {
            "authority": "unique-history-task-0001-metrics",
            "paths": [str(selected[0])],
            "fingerprint": selected[2],
        }, []
    return {}, {}, ["multiple non-equivalent TASK-0001 metric authorities cannot be disambiguated"]


def schema_contract_errors(generation_schema: Any, adapter_schema: Any) -> list[str]:
    errors: list[str] = []
    expected = (
        (generation_schema, "generation-example/v1", {"source_id", "revision_sha", "state", "source_case_key", "prompts", "assets", "generation_examples"}, "Generation Example"),
        (adapter_schema, "adapter-output/v1", {"source_id", "revision_sha", "adapter_id", "adapter_version", "records", "parse_errors", "coverage"}, "Adapter Output"),
    )
    for schema, version, required_fields, label in expected:
        if not isinstance(schema, dict):
            errors.append(f"{label} schema is not an object")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{label} schema does not declare Draft 2020-12")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{label} root must fail closed on unknown fields")
        schema_version = schema.get("properties", {}).get("schema_version") if isinstance(schema.get("properties"), dict) else None
        if not isinstance(schema_version, dict) or schema_version.get("const") != version:
            errors.append(f"{label} schema_version constant is missing or wrong")
        required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
        missing = required_fields - required
        if missing:
            errors.append(f"{label} schema is missing required fields {sorted(missing)}")
        definitions = schema.get("$defs") if isinstance(schema.get("$defs"), dict) else {}
        extensions = definitions.get("extensions") if isinstance(definitions, dict) else None
        if not isinstance(extensions, dict) or not isinstance(extensions.get("propertyNames"), dict):
            errors.append(f"{label} schema has no namespaced extensions definition")
    return errors


def document_contract_errors(document: str) -> list[str]:
    required_phrases = (
        "Adapter Output v1",
        "Generation Example v1",
        "unresolved",
        "not_constructible",
        "source_claimed",
        "inferred_local_order",
        "ambiguous",
        "extensions",
        "Publication Layer",
        "GATE-001",
        "GATE-002",
        "GATE-003",
    )
    return [f"contract document is missing required semantic phrase {phrase!r}" for phrase in required_phrases if phrase not in document]


def validate_adapter_semantics(document: Any, registry: dict[str, JsonObject], audit: dict[str, JsonObject], path: str) -> list[str]:
    if not isinstance(document, dict):
        return [f"{path}: Adapter fixture is not an object"]
    errors = source_binding_errors(document.get("source_id"), document.get("revision_sha"), registry, audit, path)
    errors.extend(extension_and_boundary_errors(document, path))
    records = document.get("records")
    parse_errors = document.get("parse_errors")
    coverage = document.get("coverage")
    if not isinstance(records, list) or not isinstance(parse_errors, list) or not isinstance(coverage, dict):
        return errors + [f"{path}: records, parse_errors, or coverage is malformed"]
    errors.extend(sorted_by(records, lambda item: item.get("source_case_key", "") if isinstance(item, dict) else "", f"{path}.records"))
    errors.extend(sorted_by(parse_errors, lambda item: item.get("source_case_key", "") if isinstance(item, dict) else "", f"{path}.parse_errors"))
    record_keys: list[str] = []
    state_counts = {"extracted_candidate": 0, "contract_valid": 0}
    for index, record in enumerate(records):
        record_path = f"{path}.records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{record_path}: record is not an object")
            continue
        key = record.get("source_case_key")
        if nonempty_string(key):
            record_keys.append(key)
        state = record.get("state")
        if state in state_counts:
            state_counts[state] += 1
        else:
            errors.append(f"{record_path}: invalid record state")
        errors.extend(source_location_errors(record.get("source_case_locator"), f"{record_path}.source_case_locator"))
        prompt = record.get("prompt")
        if not isinstance(prompt, dict):
            errors.append(f"{record_path}.prompt: malformed")
        else:
            raw_text = prompt.get("raw_text")
            if not isinstance(raw_text, str) or not normalize_prompt(raw_text):
                errors.append(f"{record_path}.prompt.raw_text: empty prompt is invalid")
            else:
                expected_id = f"prompt:sha256:{prompt_sha256(raw_text)}"
                if prompt.get("prompt_id") != expected_id:
                    errors.append(f"{record_path}.prompt.prompt_id: must be derived from normalized raw_text SHA-256")
            errors.extend(source_location_errors(prompt.get("source_location"), f"{record_path}.prompt.source_location"))
        assets = record.get("asset_references")
        asset_ids: set[str] = set()
        output_count = 0
        if not isinstance(assets, list):
            errors.append(f"{record_path}.asset_references: malformed")
        else:
            errors.extend(sorted_by(assets, lambda item: item.get("asset_ref_id", "") if isinstance(item, dict) else "", f"{record_path}.asset_references"))
            for asset_index, asset in enumerate(assets):
                asset_path = f"{record_path}.asset_references[{asset_index}]"
                if not isinstance(asset, dict):
                    errors.append(f"{asset_path}: asset reference is malformed")
                    continue
                asset_id = asset.get("asset_ref_id")
                if nonempty_string(asset_id):
                    if asset_id in asset_ids:
                        errors.append(f"{asset_path}.asset_ref_id: duplicate in record")
                    asset_ids.add(asset_id)
                if asset.get("role") in {"output_primary", "output_secondary"}:
                    output_count += 1
                resolution = asset.get("resolution_state")
                has_hash = "content_sha256" in asset
                if resolution == "unresolved" and has_hash:
                    errors.append(f"{asset_path}: unresolved reference may not carry content_sha256")
                if resolution == "resolved" and (not isinstance(asset.get("content_sha256"), str) or not SHA256.fullmatch(asset["content_sha256"])):
                    errors.append(f"{asset_path}: resolved reference requires SHA-256")
                errors.extend(source_location_errors(asset.get("source_location"), f"{asset_path}.source_location"))
        pairings = record.get("pairings")
        if not isinstance(pairings, list):
            errors.append(f"{record_path}.pairings: malformed")
        else:
            errors.extend(sorted_by(pairings, lambda item: (item.get("prompt_id", ""), item.get("asset_ref_id", "")) if isinstance(item, dict) else ("", ""), f"{record_path}.pairings"))
            for pairing_index, pairing in enumerate(pairings):
                pairing_path = f"{record_path}.pairings[{pairing_index}]"
                if not isinstance(pairing, dict):
                    errors.append(f"{pairing_path}: pairing is malformed")
                    continue
                if isinstance(prompt, dict) and pairing.get("prompt_id") != prompt.get("prompt_id"):
                    errors.append(f"{pairing_path}: prompt_id does not resolve to the record prompt")
                if pairing.get("asset_ref_id") not in asset_ids:
                    errors.append(f"{pairing_path}: asset_ref_id does not resolve to the record")
                method = pairing.get("method")
                status = pairing.get("status")
                if status == "strong" and method not in STRONG_METHODS:
                    errors.append(f"{pairing_path}: weak or ambiguous method cannot be strong")
                if method == "inferred_local_order" and status != "review_required":
                    errors.append(f"{pairing_path}: inferred_local_order must be review_required")
                if method == "ambiguous" and status != "ambiguous":
                    errors.append(f"{pairing_path}: ambiguous method must remain ambiguous")
                evidence = pairing.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    errors.append(f"{pairing_path}: pairing requires source evidence")
                elif any(source_location_errors(item, f"{pairing_path}.evidence[{evidence_index}]") for evidence_index, item in enumerate(evidence)):
                    for evidence_index, item in enumerate(evidence):
                        errors.extend(source_location_errors(item, f"{pairing_path}.evidence[{evidence_index}]"))
                if state == "contract_valid" and (status != "strong" or method not in STRONG_METHODS):
                    errors.append(f"{pairing_path}: contract_valid record requires strong, non-inferred pairing")
        if state == "contract_valid" and output_count == 0:
            errors.append(f"{record_path}: contract_valid record requires an output asset reference")
        errors.extend(source_claim_errors(record.get("source_claim"), f"{record_path}.source_claim"))
    error_keys: list[str] = []
    for index, error in enumerate(parse_errors):
        error_path = f"{path}.parse_errors[{index}]"
        if not isinstance(error, dict):
            errors.append(f"{error_path}: parse error is not an object")
            continue
        key = error.get("source_case_key")
        if nonempty_string(key):
            error_keys.append(key)
        if error.get("state") != "quarantined":
            errors.append(f"{error_path}: parse error must be quarantined")
        errors.extend(source_location_errors(error.get("source_case_locator"), f"{error_path}.source_case_locator"))
    if len(record_keys) != len(set(record_keys)):
        errors.append(f"{path}: source_case_key is duplicated in records")
    if len(error_keys) != len(set(error_keys)):
        errors.append(f"{path}: source_case_key is duplicated in parse_errors")
    if set(record_keys) & set(error_keys):
        errors.append(f"{path}: source_case_key cannot be both record and parse error")
    expected_coverage = {
        "extracted_candidate_count": state_counts["extracted_candidate"],
        "contract_valid_count": state_counts["contract_valid"],
        "quarantined_count": len(parse_errors),
    }
    for key, expected_value in expected_coverage.items():
        if coverage.get(key) != expected_value:
            errors.append(f"{path}.coverage.{key}: expected {expected_value}")
    expected_input = sum(expected_coverage.values())
    if coverage.get("input_case_count") != expected_input:
        errors.append(f"{path}.coverage.input_case_count: expected {expected_input}")
    return errors


def validate_generation_semantics(document: Any, registry: dict[str, JsonObject], audit: dict[str, JsonObject], path: str) -> list[str]:
    if not isinstance(document, dict):
        return [f"{path}: Generation fixture is not an object"]
    errors = source_binding_errors(document.get("source_id"), document.get("revision_sha"), registry, audit, path)
    errors.extend(extension_and_boundary_errors(document, path))
    if document.get("state") != "contract_valid":
        errors.append(f"{path}.state: only a closed contract_valid payload may be Generation Example v1")
    errors.extend(source_location_errors(document.get("source_case_locator"), f"{path}.source_case_locator"))
    prompts = document.get("prompts")
    assets = document.get("assets")
    examples = document.get("generation_examples")
    if not isinstance(prompts, list) or not isinstance(assets, list) or not isinstance(examples, list):
        return errors + [f"{path}: prompts, assets, or generation_examples is malformed"]
    errors.extend(sorted_by(prompts, lambda item: item.get("prompt_id", "") if isinstance(item, dict) else "", f"{path}.prompts"))
    errors.extend(sorted_by(assets, lambda item: item.get("asset_id", "") if isinstance(item, dict) else "", f"{path}.assets"))
    errors.extend(sorted_by(examples, lambda item: item.get("generation_example_id", "") if isinstance(item, dict) else "", f"{path}.generation_examples"))
    prompt_ids: set[str] = set()
    for index, prompt in enumerate(prompts):
        prompt_path = f"{path}.prompts[{index}]"
        if not isinstance(prompt, dict):
            errors.append(f"{prompt_path}: prompt is malformed")
            continue
        prompt_id = prompt.get("prompt_id")
        if nonempty_string(prompt_id):
            if prompt_id in prompt_ids:
                errors.append(f"{prompt_path}.prompt_id: duplicate")
            prompt_ids.add(prompt_id)
        raw_text = prompt.get("raw_text")
        if not isinstance(raw_text, str) or not normalize_prompt(raw_text):
            errors.append(f"{prompt_path}.raw_text: empty prompt is invalid")
        else:
            expected_id = f"prompt:sha256:{prompt_sha256(raw_text)}"
            if prompt_id != expected_id:
                errors.append(f"{prompt_path}.prompt_id: must be derived from normalized raw_text SHA-256")
        errors.extend(source_location_errors(prompt.get("source_location"), f"{prompt_path}.source_location"))
    asset_ids: set[str] = set()
    output_use_count: dict[str, int] = {}
    asset_by_id: dict[str, JsonObject] = {}
    for index, asset in enumerate(assets):
        asset_path = f"{path}.assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{asset_path}: asset is malformed")
            continue
        asset_id = asset.get("asset_id")
        asset_hash = asset.get("content_sha256")
        if nonempty_string(asset_id):
            if asset_id in asset_ids:
                errors.append(f"{asset_path}.asset_id: duplicate")
            asset_ids.add(asset_id)
            asset_by_id[asset_id] = asset
            output_use_count[asset_id] = 0
        if not isinstance(asset_hash, str) or not SHA256.fullmatch(asset_hash):
            errors.append(f"{asset_path}.content_sha256: resolved asset requires SHA-256")
        elif asset_id != f"asset:sha256:{asset_hash}":
            errors.append(f"{asset_path}.asset_id: must be derived from content_sha256")
        errors.extend(source_location_errors(asset.get("source_location"), f"{asset_path}.source_location"))
    generation_ids: set[str] = set()
    for index, example in enumerate(examples):
        example_path = f"{path}.generation_examples[{index}]"
        if not isinstance(example, dict):
            errors.append(f"{example_path}: generation example is malformed")
            continue
        generation_id = example.get("generation_example_id")
        if nonempty_string(generation_id):
            if generation_id in generation_ids:
                errors.append(f"{example_path}.generation_example_id: duplicate")
            generation_ids.add(generation_id)
        if example.get("prompt_id") not in prompt_ids:
            errors.append(f"{example_path}.prompt_id: does not resolve within document")
        inputs = example.get("input_asset_ids")
        outputs = example.get("output_asset_ids")
        if isinstance(inputs, list):
            for asset_id in inputs:
                asset = asset_by_id.get(asset_id)
                if asset is None:
                    errors.append(f"{example_path}.input_asset_ids: dangling asset reference")
                elif asset.get("role") != "input_reference":
                    errors.append(f"{example_path}.input_asset_ids: must reference input_reference asset")
        if not isinstance(outputs, list) or not outputs:
            errors.append(f"{example_path}.output_asset_ids: requires at least one output")
        else:
            for asset_id in outputs:
                asset = asset_by_id.get(asset_id)
                if asset is None:
                    errors.append(f"{example_path}.output_asset_ids: dangling asset reference")
                else:
                    if asset.get("role") not in {"output_primary", "output_secondary"}:
                        errors.append(f"{example_path}.output_asset_ids: must reference output asset")
                    output_use_count[asset_id] = output_use_count.get(asset_id, 0) + 1
        pairing = example.get("pairing")
        if not isinstance(pairing, dict):
            errors.append(f"{example_path}.pairing: malformed")
        else:
            if pairing.get("method") not in STRONG_METHODS or pairing.get("status") != "strong":
                errors.append(f"{example_path}.pairing: Generation Example requires a strong structured/markdown/native mapping")
            evidence = pairing.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{example_path}.pairing: source evidence is required")
            else:
                for evidence_index, evidence_item in enumerate(evidence):
                    errors.extend(source_location_errors(evidence_item, f"{example_path}.pairing.evidence[{evidence_index}]"))
        errors.extend(source_claim_errors(example.get("generation_claim"), f"{example_path}.generation_claim"))
    for asset_id, asset in asset_by_id.items():
        if asset.get("role") in {"output_primary", "output_secondary"} and output_use_count.get(asset_id, 0) != 1:
            errors.append(f"{path}.assets[{asset_id}]: output asset must belong to exactly one Generation Example")
    return errors


def manifest_errors(manifest: Any, registry: dict[str, JsonObject], audit: dict[str, JsonObject]) -> list[str]:
    if not isinstance(manifest, dict):
        return ["fixture manifest is not an object"]
    errors: list[str] = []
    expected_keys = {"schema_version", "contract_version", "payload_policy", "pilots", "negative_cases_file"}
    unexpected = set(manifest) - expected_keys
    if unexpected:
        errors.append(f"fixture manifest has unexpected keys {sorted(unexpected)}")
    if manifest.get("schema_version") != "content-contract-fixture-manifest/v1":
        errors.append("fixture manifest has unsupported schema_version")
    if manifest.get("contract_version") != "v1":
        errors.append("fixture manifest has unsupported contract_version")
    policy = manifest.get("payload_policy")
    if not isinstance(policy, dict) or policy != {
        "positive_fixture_origin": "real_fixed_commit",
        "stores_image_bytes": False,
        "stores_full_upstream_data": False,
        "network_required_by_validator": False,
    }:
        errors.append("fixture manifest payload_policy does not enforce minimal local-only evidence")
    if manifest.get("negative_cases_file") != "negative-cases.json":
        errors.append("fixture manifest must bind negative-cases.json")
    pilots = manifest.get("pilots")
    if not isinstance(pilots, list):
        return errors + ["fixture manifest pilots is malformed"]
    pilot_ids: list[str] = []
    for index, pilot in enumerate(pilots):
        path = f"manifest.pilots[{index}]"
        if not isinstance(pilot, dict):
            errors.append(f"{path}: pilot is malformed")
            continue
        expected_fields = {
            "source_id",
            "revision_sha",
            "structure_profile",
            "case_id",
            "origin_kind",
            "adapter_fixture",
            "generation_fixture",
            "historical_quality_sample",
        }
        if set(pilot) != expected_fields:
            errors.append(f"{path}: pilot fields do not match the v1 manifest contract")
            continue
        source_id = pilot.get("source_id")
        if nonempty_string(source_id):
            pilot_ids.append(source_id)
        if pilot.get("origin_kind") != "real_fixed_commit":
            errors.append(f"{path}: positive pilot origin must be real_fixed_commit")
        if source_id not in EXPECTED_PILOTS:
            errors.append(f"{path}: unrecognized pilot source_id")
        elif pilot.get("structure_profile") != EXPECTED_PILOTS[source_id]:
            errors.append(f"{path}: structure profile is not the required pilot profile")
        errors.extend(source_binding_errors(source_id, pilot.get("revision_sha"), registry, audit, path))
        source = registry.get(source_id) if isinstance(source_id, str) else None
        content = source.get("content") if isinstance(source, dict) else None
        if isinstance(content, dict) and pilot.get("structure_profile") != content.get("structure_type"):
            errors.append(f"{path}: profile diverges from registered source content structure")
        for fixture_key in ("adapter_fixture", "generation_fixture"):
            fixture_path = pilot.get(fixture_key)
            if not isinstance(fixture_path, str) or fixture_path.startswith(("/", "\\")) or ".." in Path(fixture_path).parts:
                errors.append(f"{path}.{fixture_key}: must be a fixture-root-relative path")
        sample = pilot.get("historical_quality_sample")
        expected_sample_fields = {"prompt_source_path", "image_path", "prompt_sha256", "asset_sha256"}
        if not isinstance(sample, dict) or set(sample) != expected_sample_fields:
            errors.append(f"{path}.historical_quality_sample: malformed")
    if set(pilot_ids) != set(EXPECTED_PILOTS) or len(pilot_ids) != len(EXPECTED_PILOTS):
        errors.append("fixture manifest must contain exactly the three required pilot sources")
    return errors


def cross_contract_errors(
    manifest: JsonObject,
    adapter_documents: dict[str, Any],
    generation_documents: dict[str, Any],
    quality_samples: dict[str, list[JsonObject]],
) -> list[str]:
    errors: list[str] = []
    pilots = manifest.get("pilots")
    if not isinstance(pilots, list):
        return ["cross-contract check cannot run: manifest pilots malformed"]
    for pilot in pilots:
        if not isinstance(pilot, dict):
            continue
        source_id = pilot.get("source_id")
        revision = pilot.get("revision_sha")
        case_id = pilot.get("case_id")
        adapter_path = pilot.get("adapter_fixture")
        generation_path = pilot.get("generation_fixture")
        label = f"cross-contract[{source_id}]"
        adapter = adapter_documents.get(adapter_path) if isinstance(adapter_path, str) else None
        generation = generation_documents.get(generation_path) if isinstance(generation_path, str) else None
        if not isinstance(adapter, dict) or not isinstance(generation, dict):
            errors.append(f"{label}: paired fixtures cannot be loaded")
            continue
        expected_case_key = f"{source_id}:{case_id}"
        for document_name, document in (("adapter", adapter), ("generation", generation)):
            if document.get("source_id") != source_id or document.get("revision_sha") != revision:
                errors.append(f"{label}: {document_name} source/revision diverges from manifest")
        if generation.get("state") != "contract_valid":
            errors.append(f"{label}: Generation fixture is not contract_valid")
        if generation.get("source_case_key") != expected_case_key:
            errors.append(f"{label}: Generation Example case key diverges from manifest")
        records = adapter.get("records")
        parse_errors = adapter.get("parse_errors")
        if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
            errors.append(f"{label}: positive Adapter fixture must contain exactly one real minimal record")
            continue
        if parse_errors != []:
            errors.append(f"{label}: positive Adapter fixture may not present a synthetic/error pilot record")
        record = records[0]
        if record.get("source_case_key") != expected_case_key:
            errors.append(f"{label}: Adapter case key diverges from manifest")
        record_locator = record.get("source_case_locator")
        generation_locator = generation.get("source_case_locator")
        if not isinstance(record_locator, dict) or record_locator.get("native_id") != case_id:
            errors.append(f"{label}: Adapter native case locator diverges from manifest")
        if not isinstance(generation_locator, dict) or generation_locator.get("native_id") != case_id:
            errors.append(f"{label}: Generation native case locator diverges from manifest")
        sample = pilot.get("historical_quality_sample")
        if not isinstance(sample, dict):
            errors.append(f"{label}: historical sample is malformed")
            continue
        candidates = quality_samples.get(source_id, [])
        matching = [
            candidate
            for candidate in candidates
            if candidate.get("case_id") == case_id
            and candidate.get("prompt_source_path") == sample.get("prompt_source_path")
            and candidate.get("image_path") == sample.get("image_path")
            and candidate.get("prompt_sha256") == sample.get("prompt_sha256")
            and candidate.get("image_sha256") == sample.get("asset_sha256")
        ]
        if len(matching) != 1:
            errors.append(f"{label}: TASK-0001 quality sample does not uniquely match manifest provenance")
        prompt = record.get("prompt")
        generation_prompts = generation.get("prompts")
        if not isinstance(prompt, dict) or not isinstance(generation_prompts, list) or len(generation_prompts) != 1 or not isinstance(generation_prompts[0], dict):
            errors.append(f"{label}: prompt projection is malformed")
            continue
        generation_prompt = generation_prompts[0]
        for document_name, prompt_record in (("adapter", prompt), ("generation", generation_prompt)):
            raw_text = prompt_record.get("raw_text")
            actual_hash = prompt_sha256(raw_text) if isinstance(raw_text, str) else None
            if actual_hash != sample.get("prompt_sha256"):
                errors.append(f"{label}: {document_name} exact Prompt does not match TASK-0001 SHA-256")
            location = prompt_record.get("source_location")
            if not isinstance(location, dict) or location.get("source_path") != sample.get("prompt_source_path"):
                errors.append(f"{label}: {document_name} Prompt source path does not match TASK-0001 evidence")
        if prompt.get("raw_text") != generation_prompt.get("raw_text"):
            errors.append(f"{label}: Adapter and Generation Example Prompt text diverge")
        adapter_assets = record.get("asset_references")
        generation_assets = generation.get("assets")
        if not isinstance(adapter_assets, list) or len(adapter_assets) != 1 or not isinstance(adapter_assets[0], dict):
            errors.append(f"{label}: Adapter asset projection is malformed")
            continue
        if not isinstance(generation_assets, list) or len(generation_assets) != 1 or not isinstance(generation_assets[0], dict):
            errors.append(f"{label}: Generation asset projection is malformed")
            continue
        adapter_asset = adapter_assets[0]
        generation_asset = generation_assets[0]
        if adapter_asset.get("resolution_state") != "unresolved" or "content_sha256" in adapter_asset:
            errors.append(f"{label}: Adapter positive must demonstrate an unresolved asset reference")
        if generation_asset.get("content_sha256") != sample.get("asset_sha256"):
            errors.append(f"{label}: resolved Generation asset hash does not match TASK-0001 evidence")
        adapter_location = adapter_asset.get("source_location")
        generation_location = generation_asset.get("source_location")
        for document_name, location in (("adapter", adapter_location), ("generation", generation_location)):
            if not isinstance(location, dict) or location.get("source_path") != sample.get("image_path"):
                errors.append(f"{label}: {document_name} asset path does not match TASK-0001 evidence")
        if isinstance(adapter_location, dict) and isinstance(generation_location, dict) and adapter_location.get("source_path") != generation_location.get("source_path"):
            errors.append(f"{label}: staging did not preserve asset source location")
        for document_name, document in (("adapter", adapter), ("generation", generation)):
            for url in _collect_source_urls(document):
                if f"/{revision}/" not in url:
                    errors.append(f"{label}: {document_name} source URL is not fixed to registered commit")
        adapter_pairings = record.get("pairings")
        examples = generation.get("generation_examples")
        if not isinstance(adapter_pairings, list) or len(adapter_pairings) != 1 or not isinstance(adapter_pairings[0], dict):
            errors.append(f"{label}: Adapter pairing is malformed")
            continue
        if not isinstance(examples, list) or len(examples) != 1 or not isinstance(examples[0], dict):
            errors.append(f"{label}: Generation pairing is malformed")
            continue
        adapter_pairing = adapter_pairings[0]
        generation_pairing = examples[0].get("pairing")
        if not isinstance(generation_pairing, dict):
            errors.append(f"{label}: Generation pairing object is missing")
        else:
            if adapter_pairing.get("method") != generation_pairing.get("method"):
                errors.append(f"{label}: pairing method changed during staging")
            if adapter_pairing.get("status") != "strong" or generation_pairing.get("status") != "strong":
                errors.append(f"{label}: positive projection must retain strong pairing")
            if adapter_pairing.get("method") not in STRONG_METHODS:
                errors.append(f"{label}: positive projection uses a non-admissible pairing method")
        coverage = adapter.get("coverage")
        if not isinstance(coverage, dict) or coverage.get("input_case_count") != 1 or coverage.get("contract_valid_count") != 1 or coverage.get("quarantined_count") != 0:
            errors.append(f"{label}: positive fixture coverage is not minimal and complete")
    return errors


def _collect_source_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, list):
        for item in value:
            urls.extend(_collect_source_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "source_url" and isinstance(item, str):
                urls.append(item)
            else:
                urls.extend(_collect_source_urls(item))
    return urls


def pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def pointer_set(value: Any, pointer: str, replacement: Any) -> None:
    parts = pointer_parts(pointer)
    current = value
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                current[part] = [] if next_part.isdigit() else {}
            current = current[part]
        else:
            raise ValueError("JSON pointer traverses a scalar")
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = replacement
    elif isinstance(current, dict):
        current[last] = replacement
    else:
        raise ValueError("JSON pointer terminates at a scalar")


def pointer_delete(value: Any, pointer: str) -> None:
    parts = pointer_parts(pointer)
    current = value
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    if isinstance(current, list):
        del current[int(parts[-1])]
    else:
        del current[parts[-1]]


def append_controlled_parse_error(document: JsonObject) -> None:
    records = document.get("records")
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        raise ValueError("controlled partial-failure mutation requires a record")
    source_id = document.get("source_id")
    locator = copy.deepcopy(records[0].get("source_case_locator"))
    if not isinstance(locator, dict):
        raise ValueError("controlled partial-failure mutation requires a source locator")
    locator["native_id"] = "__controlled-contract-error__"
    locator["selector"] = "controlled mutation; not a source-derived pilot fact"
    document.setdefault("parse_errors", []).append(
        {
            "source_case_key": f"{source_id}:__controlled-contract-error__",
            "source_case_locator": locator,
            "state": "quarantined",
            "stage": "prompt_extraction",
            "error_code": "MISSING_PROMPT",
            "message": "Controlled contract mutation; no source-derived Prompt is introduced."
        }
    )
    coverage = document.setdefault("coverage", {})
    coverage["input_case_count"] = int(coverage.get("input_case_count", 0)) + 1
    coverage["quarantined_count"] = int(coverage.get("quarantined_count", 0)) + 1


def projection_mutation_errors(
    adapter: JsonObject,
    generation: JsonObject,
    *,
    allow_staging_resolution: bool,
    reject_quarantined: bool,
) -> list[str]:
    errors: list[str] = []
    records = adapter.get("records") if isinstance(adapter, dict) else None
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        return ["assembly mutation lacks a usable Adapter record"]
    assets = records[0].get("asset_references")
    if not isinstance(assets, list):
        return ["assembly mutation lacks Adapter asset references"]
    if not allow_staging_resolution and any(isinstance(asset, dict) and asset.get("resolution_state") == "unresolved" for asset in assets):
        errors.append("assembly: unresolved Adapter asset cannot directly enter Generation Example")
    if reject_quarantined and adapter.get("parse_errors"):
        errors.append("assembly: quarantined parse error cannot enter Generation Example")
    return errors


def apply_mutation(document: Any, operation: JsonObject) -> Any:
    mutated = copy.deepcopy(document)
    op = operation.get("op")
    if op == "set":
        pointer_set(mutated, operation["path"], copy.deepcopy(operation.get("value")))
    elif op == "delete":
        pointer_delete(mutated, operation["path"])
    elif op == "duplicate_record":
        if not isinstance(mutated, dict) or not isinstance(mutated.get("records"), list) or not mutated["records"]:
            raise ValueError("duplicate_record requires an Adapter record")
        mutated["records"].append(copy.deepcopy(mutated["records"][0]))
    elif op == "append_controlled_parse_error":
        if not isinstance(mutated, dict):
            raise ValueError("controlled partial failure requires an object")
        append_controlled_parse_error(mutated)
    else:
        raise ValueError(f"unsupported mutation operation {op!r}")
    return mutated


def run_negative_cases(
    cases_data: Any,
    fixture_root: Path,
    manifest: JsonObject,
    adapter_documents: dict[str, Any],
    generation_documents: dict[str, Any],
    generation_schema: JsonObject,
    adapter_schema: JsonObject,
    registry: dict[str, JsonObject],
    audit: dict[str, JsonObject],
) -> tuple[list[JsonObject], list[str]]:
    if not isinstance(cases_data, dict) or cases_data.get("schema_version") != "content-contract-negative-cases/v1":
        return [], ["negative-cases.json has unsupported schema_version"]
    cases = cases_data.get("cases")
    if not isinstance(cases, list):
        return [], ["negative-cases.json has no cases array"]
    results: list[JsonObject] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        case_path = f"negative-cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{case_path}: malformed")
            continue
        case_id = case.get("id")
        if not nonempty_string(case_id) or case_id in seen_ids:
            errors.append(f"{case_path}: id is missing or duplicated")
            continue
        seen_ids.add(case_id)
        gate = case.get("gate")
        expected = case.get("expect")
        operation = case.get("operation")
        target = case.get("target")
        mutation_errors: list[str] = []
        try:
            if target == "assembly":
                adapter = copy.deepcopy(adapter_documents.get("adapter-output/g0dam-work-prompts.valid.json"))
                generation = copy.deepcopy(generation_documents.get("generation-example/g0dam-work-prompts.valid.json"))
                if not isinstance(adapter, dict) or not isinstance(generation, dict):
                    raise ValueError("assembly baseline fixtures are unavailable")
                op = operation.get("op") if isinstance(operation, dict) else None
                if op == "project_without_resolution":
                    mutation_errors.extend(projection_mutation_errors(adapter, generation, allow_staging_resolution=False, reject_quarantined=True))
                elif op == "project_quarantined_case":
                    append_controlled_parse_error(adapter)
                    mutation_errors.extend(projection_mutation_errors(adapter, generation, allow_staging_resolution=True, reject_quarantined=True))
                else:
                    raise ValueError("unsupported assembly mutation")
            elif target == "manifest.json":
                if not isinstance(operation, dict):
                    raise ValueError("manifest mutation is malformed")
                mutated = apply_mutation(manifest, operation)
                mutation_errors.extend(manifest_errors(mutated, registry, audit))
            elif isinstance(target, str) and target.startswith("adapter-output/"):
                baseline = adapter_documents.get(target)
                if not isinstance(operation, dict):
                    raise ValueError("Adapter mutation is malformed")
                mutated = apply_mutation(baseline, operation)
                mutation_errors.extend(validate_json_schema(mutated, adapter_schema, adapter_schema, "$"))
                mutation_errors.extend(validate_adapter_semantics(mutated, registry, audit, target))
            elif isinstance(target, str) and target.startswith("generation-example/"):
                baseline = generation_documents.get(target)
                if not isinstance(operation, dict):
                    raise ValueError("Generation mutation is malformed")
                mutated = apply_mutation(baseline, operation)
                mutation_errors.extend(validate_json_schema(mutated, generation_schema, generation_schema, "$"))
                mutation_errors.extend(validate_generation_semantics(mutated, registry, audit, target))
            else:
                raise ValueError("unsupported negative target")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            mutation_errors.append(f"mutation setup failed: {exc}")
        observed = "reject" if mutation_errors else "accept"
        passed = expected in {"accept", "reject"} and observed == expected
        if not passed:
            errors.append(f"{case_id}: expected {expected!r}, observed {observed!r}")
        results.append(
            {
                "id": case_id,
                "gate": gate,
                "rule": case.get("rule"),
                "expected": expected,
                "observed": observed,
                "status": "passed" if passed else "failed",
                "error_count": len(mutation_errors),
            }
        )
    return sorted(results, key=lambda item: item["id"]), sorted(errors)


def fixture_file_errors(fixture_root: Path, manifest: JsonObject) -> list[str]:
    expected = {"manifest.json", "negative-cases.json"}
    pilots = manifest.get("pilots") if isinstance(manifest, dict) else []
    if isinstance(pilots, list):
        for pilot in pilots:
            if isinstance(pilot, dict):
                for key in ("adapter_fixture", "generation_fixture"):
                    if isinstance(pilot.get(key), str):
                        expected.add(pilot[key])
    actual = {path.relative_to(fixture_root).as_posix() for path in fixture_root.rglob("*") if path.is_file()}
    errors: list[str] = []
    if actual != expected:
        errors.append(f"fixture root must contain only the declared minimal JSON fixtures; unexpected/missing={sorted(actual ^ expected)}")
    if any(Path(item).suffix != ".json" for item in actual):
        errors.append("fixture root contains a non-JSON artifact")
    return errors


def evaluate(args: argparse.Namespace) -> JsonObject:
    gate_errors: dict[str, list[str]] = {"GATE-001": [], "GATE-002": [], "GATE-003": []}
    try:
        generation_schema = load_json(args.generation_schema)
        adapter_schema = load_json(args.adapter_schema)
        registry_data = load_json(args.registry)
        audit_data = load_json(args.audit)
        manifest = load_json(args.fixtures / "manifest.json")
        negative_cases = load_json(args.fixtures / "negative-cases.json")
        document = args.contract_doc.read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        gate_errors["GATE-003"].append(f"cannot load local validator input: {exc}")
        return build_result(gate_errors, {}, [], {}, {})
    if not isinstance(generation_schema, dict) or not isinstance(adapter_schema, dict) or not isinstance(manifest, dict):
        gate_errors["GATE-003"].append("schema or fixture manifest is not a JSON object")
        return build_result(gate_errors, {}, [], {}, {})

    registry, audit, index_errors = registry_indexes(registry_data, audit_data)
    gate_errors["GATE-002"].extend(index_errors)
    gate_errors["GATE-003"].extend(schema_contract_errors(generation_schema, adapter_schema))
    gate_errors["GATE-003"].extend(document_contract_errors(document))
    gate_errors["GATE-002"].extend(manifest_errors(manifest, registry, audit))
    gate_errors["GATE-002"].extend(fixture_file_errors(args.fixtures, manifest))

    adapter_documents: dict[str, Any] = {}
    generation_documents: dict[str, Any] = {}
    pilots = manifest.get("pilots") if isinstance(manifest, dict) else []
    if isinstance(pilots, list):
        for pilot in pilots:
            if not isinstance(pilot, dict):
                continue
            for key, target in (("adapter_fixture", adapter_documents), ("generation_fixture", generation_documents)):
                relative = pilot.get(key)
                if not isinstance(relative, str):
                    continue
                path = args.fixtures / relative
                try:
                    target[relative] = load_json(path)
                except (OSError, json.JSONDecodeError) as exc:
                    if key == "adapter_fixture":
                        gate_errors["GATE-002"].append(f"cannot load {relative}: {exc}")
                    else:
                        gate_errors["GATE-001"].append(f"cannot load {relative}: {exc}")

    for relative, adapter in sorted(adapter_documents.items()):
        gate_errors["GATE-002"].extend(validate_json_schema(adapter, adapter_schema, adapter_schema, relative))
        gate_errors["GATE-002"].extend(validate_adapter_semantics(adapter, registry, audit, relative))
    for relative, generation in sorted(generation_documents.items()):
        gate_errors["GATE-001"].extend(validate_json_schema(generation, generation_schema, generation_schema, relative))
        gate_errors["GATE-001"].extend(validate_generation_semantics(generation, registry, audit, relative))

    quality_samples, authority, quality_errors = discover_quality_samples(args.prior_source_evidence_root)
    gate_errors["GATE-002"].extend(quality_errors)
    if not quality_errors:
        gate_errors["GATE-002"].extend(cross_contract_errors(manifest, adapter_documents, generation_documents, quality_samples))
        gate_errors["GATE-003"].extend(cross_contract_errors(manifest, adapter_documents, generation_documents, quality_samples))

    negative_results: list[JsonObject] = []
    if args.self_test:
        negative_results, negative_errors = run_negative_cases(
            negative_cases,
            args.fixtures,
            manifest,
            adapter_documents,
            generation_documents,
            generation_schema,
            adapter_schema,
            registry,
            audit,
        )
        for error in negative_errors:
            gate = next((item.get("gate") for item in negative_results if item.get("id") in error), "GATE-003")
            if gate not in gate_errors:
                gate = "GATE-003"
            gate_errors[gate].append(error)
    semantic_summary = semantic_summary_for(manifest, adapter_documents, generation_documents)
    return build_result(gate_errors, authority, negative_results, semantic_summary, {
        "adapter_fixture_count": len(adapter_documents),
        "generation_fixture_count": len(generation_documents),
        "quality_sample_source_count": len(quality_samples),
    })


def semantic_summary_for(manifest: JsonObject, adapters: dict[str, Any], generations: dict[str, Any]) -> JsonObject:
    rows: list[JsonObject] = []
    pilots = manifest.get("pilots") if isinstance(manifest, dict) else []
    if isinstance(pilots, list):
        for pilot in pilots:
            if not isinstance(pilot, dict):
                continue
            adapter = adapters.get(pilot.get("adapter_fixture"))
            generation = generations.get(pilot.get("generation_fixture"))
            adapter_record = adapter.get("records", [None])[0] if isinstance(adapter, dict) and isinstance(adapter.get("records"), list) and adapter.get("records") else None
            generation_prompt = generation.get("prompts", [None])[0] if isinstance(generation, dict) and isinstance(generation.get("prompts"), list) and generation.get("prompts") else None
            generation_asset = generation.get("assets", [None])[0] if isinstance(generation, dict) and isinstance(generation.get("assets"), list) and generation.get("assets") else None
            rows.append(
                {
                    "source_id": pilot.get("source_id"),
                    "revision_sha": pilot.get("revision_sha"),
                    "case_id": pilot.get("case_id"),
                    "structure_profile": pilot.get("structure_profile"),
                    "adapter_case_key": adapter_record.get("source_case_key") if isinstance(adapter_record, dict) else None,
                    "prompt_sha256": prompt_sha256(generation_prompt.get("raw_text")) if isinstance(generation_prompt, dict) and isinstance(generation_prompt.get("raw_text"), str) else None,
                    "asset_sha256": generation_asset.get("content_sha256") if isinstance(generation_asset, dict) else None,
                }
            )
    rows = sorted(rows, key=lambda item: str(item["source_id"]))
    summary = {"contract_version": "v1", "pilots": rows}
    return {"sha256": fingerprint(summary), "value": summary}


def build_result(
    gate_errors: dict[str, list[str]],
    quality_authority: JsonObject,
    negative_results: list[JsonObject],
    semantic_summary: JsonObject,
    counts: JsonObject,
) -> JsonObject:
    gates = {
        gate: {
            "status": "passed" if not sorted(set(errors)) else "failed",
            "error_count": len(sorted(set(errors))),
            "errors": sorted(set(errors)),
        }
        for gate, errors in sorted(gate_errors.items())
    }
    status = "passed" if all(gate["status"] == "passed" for gate in gates.values()) else "failed"
    return {
        "schema_version": "content-contract-validation-result/v1",
        "validator_id": "content-contract-v1",
        "status": status,
        "gates": gates,
        "negative_cases": negative_results,
        "quality_evidence_authority": quality_authority,
        "semantic_summary": semantic_summary,
        "counts": counts,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Content Contract v1 locally and deterministically.")
    parser.add_argument("--generation-schema", required=True, type=Path)
    parser.add_argument("--adapter-schema", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--prior-source-evidence-root", required=True, type=Path)
    parser.add_argument("--contract-doc", required=True, type=Path)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--determinism-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = evaluate(args)
    if args.determinism_check:
        second = evaluate(args)
        deterministic = (
            result.get("semantic_summary") == second.get("semantic_summary")
            and result.get("gates") == second.get("gates")
            and result.get("negative_cases") == second.get("negative_cases")
        )
        result["determinism"] = {
            "status": "passed" if deterministic else "failed",
            "first_semantic_summary": result.get("semantic_summary", {}).get("sha256"),
            "second_semantic_summary": second.get("semantic_summary", {}).get("sha256"),
        }
        if not deterministic:
            result["status"] = "failed"
            result["gates"]["GATE-003"]["status"] = "failed"
            result["gates"]["GATE-003"]["errors"].append("repeat validation did not produce the same stable result")
            result["gates"]["GATE-003"]["errors"] = sorted(set(result["gates"]["GATE-003"]["errors"]))
            result["gates"]["GATE-003"]["error_count"] = len(result["gates"]["GATE-003"]["errors"])
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(f"content-contract-v1: {result['status']}")
        for gate, gate_result in result["gates"].items():
            print(f"  {gate}: {gate_result['status']} ({gate_result['error_count']} errors)")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
