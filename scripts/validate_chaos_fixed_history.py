"""Validate the Chaos fixed-history activation and its exact TASK-0022 handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.adapters.chaosrealms import parse_chaos_snapshot
from ingestion.assets import read_asset
from ingestion.contracts import (
    extraction_metrics,
    generation_examples,
    load_contract_context,
    resolved_adapter_output,
    validate_adapter_output,
    validate_generation_example,
)
from ingestion.registry import load_source_config
from sync.revision import RevisionError, load_sync_source


SOURCE_ID = "chaosrealmsai-gpt-image-2-gallery"
REVISION = "5296db8c996e38776c83a0bc8c64f848dcd512b3"
EXPECTED_SOURCE_IDS = {
    SOURCE_ID,
    "conardli-gpt-image-2-101",
    "erickkkyt-awesome-gptimage2-prompts",
    "freestylefly-awesome-gpt-image-2",
    "g0dam-work-prompts",
    "joesai-commercial-prompts",
    "vigozhao-ai-visual-prompt-cookbook",
}
EXPECTED_METRICS = {
    "observed_case_count": 2460,
    "exact_prompt_count": 2460,
    "paired_output_count": 2460,
    "valid_case_count": 2460,
    "unique_valid_case_count": 2460,
    "broken_asset_count": 0,
    "pair_rate": 1.0,
    "case_fingerprint_aggregate_sha256": "21e68e472d22bd877a960c317ab5cc18360fa5e51a9c21f7627bdd4202379858",
    "generation_example_count": 7380,
}


class ValidationFailure(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailure(f"cannot read JSON authority: {path}") from exc
    if not isinstance(value, dict):
        raise ValidationFailure(f"JSON authority must contain an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _schema_errors(value: Any, schema: Mapping[str, Any], label: str) -> list[str]:
    return [
        f"{label}{''.join(f'[{part!r}]' for part in error.absolute_path)}: {error.message}"
        for error in sorted(Draft202012Validator(dict(schema)).iter_errors(value), key=lambda item: list(item.absolute_path))
    ]


def _index(rows: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
        raise ValidationFailure(f"{label} must be an object array")
    result = {str(item.get("source_id")): item for item in rows}
    if len(result) != len(rows) or "None" in result:
        raise ValidationFailure(f"{label} source IDs must be unique and nonempty")
    return result


def validate_static() -> dict[str, Any]:
    admission_path = REPO_ROOT / "config/fixed-history/chaosrealmsai-gpt-image-2-gallery-v1.json"
    registry_path = REPO_ROOT / "config/sources-v2.yaml"
    audit_path = REPO_ROOT / "reports/source-audit-v2.json"
    v3_path = REPO_ROOT / "reports/phase2/source-expansion-admission-v3.json"
    admission = _load(admission_path)
    registry = _load(registry_path)
    audit = _load(audit_path)
    v3 = _load(v3_path)

    errors: list[str] = []
    errors.extend(_schema_errors(admission, _load(REPO_ROOT / "schemas/fixed-history-admission-v1.schema.json"), "admission"))
    errors.extend(_schema_errors(registry, _load(REPO_ROOT / "schemas/source-registry-v2.schema.json"), "registry"))
    errors.extend(_schema_errors(audit, _load(REPO_ROOT / "schemas/source-audit-v2.schema.json"), "audit"))
    if errors:
        raise ValidationFailure(errors[0])

    batch = [item for item in v3.get("adapter_ready_batch", []) if isinstance(item, dict)]
    if len(batch) != 1 or batch[0].get("source_id") != SOURCE_ID:
        raise ValidationFailure("TASK-0022 adapter_ready_batch is no longer the one-source Chaos handoff")
    source_rows = [item for item in v3.get("sources", []) if isinstance(item, dict) and item.get("source_id") == SOURCE_ID]
    if len(source_rows) != 1:
        raise ValidationFailure("TASK-0022 Chaos source evidence is missing or duplicated")
    source = source_rows[0]
    evidence = source.get("evidence") if isinstance(source.get("evidence"), dict) else {}
    case_ledger = evidence.get("case_ledger")
    exclusion_ledger = evidence.get("exclusion_ledger")
    if not isinstance(case_ledger, list) or not isinstance(exclusion_ledger, list):
        raise ValidationFailure("TASK-0022 Chaos case/exclusion ledgers are malformed")
    if admission["source_report_sha256"] != _sha256(v3_path):
        raise ValidationFailure("admission no longer binds the exact TASK-0022 report bytes")
    if admission["source_report_canonical_digest"] != v3.get("canonical_digest"):
        raise ValidationFailure("admission no longer binds the TASK-0022 canonical digest")
    if admission["adapter_ready_item_sha256"] != _digest(batch[0]):
        raise ValidationFailure("admission no longer binds the exact TASK-0022 handoff item")
    if admission["admitted_case_ids"] != sorted(str(item.get("case_id")) for item in case_ledger):
        raise ValidationFailure("admission case scope differs from the TASK-0022 filtered case ledger")
    if admission["exclusions"] != exclusion_ledger or admission["exclusions"] != batch[0].get("exclusions"):
        raise ValidationFailure("admission exclusions differ from the complete TASK-0022 exclusion ledger")
    if (
        admission["case_count"] != 2460
        or admission["raw_case_count"] != 3798
        or admission["excluded_case_count"] != 1338
        or len(admission["exclusions"]) != 1466
        or admission["case_ledger_sha256"] != "33484746656377578e62ad6f425d5d07f23cce0f9fdc5b04697fb31d402fa65b"
    ):
        raise ValidationFailure("fixed-history case/exclusion arithmetic drifted")

    registry_index = _index(registry.get("sources"), "registry.sources")
    audit_index = _index(audit.get("records"), "audit.records")
    if set(registry_index) != EXPECTED_SOURCE_IDS or set(audit_index) != EXPECTED_SOURCE_IDS:
        raise ValidationFailure("operational v2 authority must contain exactly the seven activated sources")
    for source_id, row in registry_index.items():
        ingestion = row.get("ingestion") if isinstance(row.get("ingestion"), dict) else {}
        sync = row.get("sync") if isinstance(row.get("sync"), dict) else {}
        if row.get("status") != "active" or row.get("publication", {}).get("auto_publish") is not False:
            raise ValidationFailure(f"{source_id} is not active-internal and fail-closed")
        if source_id == SOURCE_ID:
            if (
                ingestion != {"mode": "fixed_history", "one_shot_import_only": True}
                or sync.get("enabled") is not False
                or row.get("repository", {}).get("verified_commit_sha") != REVISION
                or row.get("content", {}).get("adapter_strategy") != "chaos_meta_three_webp_v1"
            ):
                raise ValidationFailure("Chaos operational mode/revision/adapter drifted")
        elif ingestion != {"mode": "continuous", "one_shot_import_only": False} or sync.get("enabled") is not True:
            raise ValidationFailure(f"continuous source policy drifted: {source_id}")
    chaos_audit = audit_index[SOURCE_ID]
    metrics = chaos_audit.get("metrics") if isinstance(chaos_audit.get("metrics"), dict) else {}
    for key, expected in EXPECTED_METRICS.items():
        if metrics.get(key) != expected:
            raise ValidationFailure(f"Chaos audit metric drifted: {key}")
    if (
        chaos_audit.get("recommended_status") != "active"
        or chaos_audit.get("rights", {}).get("prompt_policy") != "review_required"
        or chaos_audit.get("rights", {}).get("asset_policy") != "review_required"
        or chaos_audit.get("rights", {}).get("auto_publish") is not False
    ):
        raise ValidationFailure("Chaos operational audit rights/status boundary drifted")

    config = load_source_config(registry_path, SOURCE_ID)
    if config.ingestion_mode != "fixed_history" or config.sync_enabled or not config.one_shot_import_only:
        raise ValidationFailure("runtime SourceConfig lost fixed-history isolation")
    try:
        load_sync_source(registry_path, audit_path, SOURCE_ID)
    except RevisionError:
        pass
    else:
        raise ValidationFailure("Chaos fixed history unexpectedly entered incremental sync")
    return {
        "status": "passed",
        "source_count": 7,
        "case_count": 2460,
        "output_count": 7380,
        "sync_eligible": False,
        "auto_publish": False,
    }


def validate_live(snapshot_root: Path) -> dict[str, Any]:
    registry_path = REPO_ROOT / "config/sources-v2.yaml"
    audit_path = REPO_ROOT / "reports/source-audit-v2.json"
    config = load_source_config(registry_path, SOURCE_ID)
    parsed, _ = parse_chaos_snapshot(snapshot_root, config)
    asset_facts = {
        (case.source_case_key, binding.asset_ref_id): read_asset(snapshot_root, binding.source_path)
        for case in parsed
        for binding in case.asset_paths
    }
    adapter_output = resolved_adapter_output(config, parsed, asset_facts)
    documents = generation_examples(adapter_output)
    metrics = extraction_metrics(adapter_output, documents)
    context = load_contract_context(REPO_ROOT, registry_path, audit_path)
    validate_adapter_output(context, adapter_output)
    for document in documents:
        validate_generation_example(context, document)
    for key, expected in EXPECTED_METRICS.items():
        if metrics.get(key) != expected:
            raise ValidationFailure(f"live fixed snapshot metric drifted: {key}")
    if len(asset_facts) != 7380 or len({fact.content_sha256 for fact in asset_facts.values()}) != 7380:
        raise ValidationFailure("live fixed snapshot asset coverage or uniqueness drifted")
    return {
        "status": "passed",
        "parsed_case_count": len(parsed),
        "generation_example_count": metrics["generation_example_count"],
        "unique_asset_count": len({fact.content_sha256 for fact in asset_facts.values()}),
        "semantic_digest": metrics["semantic_digest"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = {"static": validate_static()}
        if args.live:
            if args.snapshot_root is None:
                raise ValidationFailure("--live requires --snapshot-root")
            result["live"] = validate_live(args.snapshot_root.resolve())
        payload = {"status": "passed", **result}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else "PASS: Chaos fixed-history activation")
        return 0
    except (OSError, ValueError, ValidationFailure) as exc:
        payload = {"status": "failed", "error": type(exc).__name__, "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
