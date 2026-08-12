"""Validate and optionally write one controlled source lifecycle transition."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.registry import RegistryError, load_source_config

ALLOWED = {
    "active": {"paused", "retired"},
    "paused": {"active", "retired"},
    "retired": set(),
}


def _audit_authority(audit_path: Path, *, source_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    records = audit.get("records") if isinstance(audit, dict) else None
    matches = [row for row in records if isinstance(row, dict) and row.get("source_id") == source_id] if isinstance(records, list) else []
    if len(matches) != 1:
        raise RegistryError("source audit must identify exactly one lifecycle source")
    sources = registry.get("sources") if isinstance(registry, dict) else None
    registry_matches = [row for row in sources if isinstance(row, dict) and row.get("source_id") == source_id] if isinstance(sources, list) else []
    if len(registry_matches) != 1:
        raise RegistryError("registry must identify exactly one lifecycle source")
    audit_repository = matches[0].get("repository") if isinstance(matches[0].get("repository"), dict) else {}
    registry_repository = registry_matches[0].get("repository") if isinstance(registry_matches[0].get("repository"), dict) else {}
    if audit_repository.get("verified_commit_sha") != registry_repository.get("verified_commit_sha"):
        raise RegistryError("source audit and registry commit authority differ")
    return matches[0]


def transition_document(registry: dict[str, Any], *, source_id: str, target: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = registry.get("sources") if isinstance(registry, dict) else None
    matches = [row for row in rows if isinstance(row, dict) and row.get("source_id") == source_id] if isinstance(rows, list) else []
    if len(matches) != 1:
        raise RegistryError("registry must identify exactly one lifecycle source")
    source = matches[0]
    current = source.get("status")
    if current not in ALLOWED or target not in ALLOWED[current]:
        raise RegistryError(f"unsupported source lifecycle transition: {current!r} -> {target!r}")
    ingestion = source.get("ingestion") if isinstance(source.get("ingestion"), dict) else {}
    sync = source.get("sync") if isinstance(source.get("sync"), dict) else {}
    if target == "active":
        sync["enabled"] = ingestion.get("mode") == "continuous"
    else:
        sync["enabled"] = False
    source["status"] = target
    evidence = {
        "source_id": source_id,
        "from_status": current,
        "to_status": target,
        "sync_enabled": sync.get("enabled"),
        "ingestion_mode": ingestion.get("mode"),
    }
    return registry, evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--to", choices=("active", "paused", "retired"), required=True)
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "config" / "sources-v2.yaml")
    parser.add_argument("--audit", type=Path, default=REPO_ROOT / "reports" / "source-audit-v2.json")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry_path = args.registry.resolve()
        original = registry_path.read_bytes()
        registry = json.loads(original.decode("utf-8"))
        audit_path = args.audit.resolve()
        audit_authority = _audit_authority(audit_path, source_id=args.source_id, registry=registry)
        updated, evidence = transition_document(registry, source_id=args.source_id, target=args.to)
        temporary = registry_path.with_name(f".{registry_path.name}.lifecycle-validation")
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            load_source_config(temporary, args.source_id, require_active=args.to == "active")
            from scripts.validate_source_registry import load_json, validate_documents

            report = validate_documents(
                load_json(audit_path),
                load_json(temporary),
                load_json(REPO_ROOT / "schemas" / "source-audit-v2.schema.json"),
                load_json(REPO_ROOT / "schemas" / "source-registry-v2.schema.json"),
            )
            if not report["ok"]:
                raise RegistryError("lifecycle transition violates source registry authority")
        finally:
            temporary.unlink(missing_ok=True)
        receipt = {
            "status": "written" if args.write else "validated",
            **evidence,
            "reason": args.reason,
            "approved_by": args.approved_by,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "previous_registry_sha256": hashlib.sha256(original).hexdigest(),
            "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
            "verified_commit_sha": audit_authority["repository"]["verified_commit_sha"],
            "next_registry_sha256": hashlib.sha256((json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()).hexdigest(),
        }
        if args.write:
            registry_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True) if args.json else receipt["status"])
        return 0
    except (OSError, json.JSONDecodeError, RegistryError) as exc:
        payload = {"status": "failed", "error_code": "source_lifecycle_invalid", "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else str(exc))
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
