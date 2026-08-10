"""Command-line boundary for the one permitted extraction slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .pipeline import ExtractionError, extract


EXIT_CODES = {
    "registry_invalid": 20,
    "run_locked": 21,
    "git_unavailable": 30,
    "git_failed": 31,
    "commit_mismatch": 32,
    "unsafe_submodule": 33,
    "unsafe_git_filter": 34,
    "source_data_invalid": 40,
    "source_shape_invalid": 41,
    "source_count_mismatch": 42,
    "source_duplicate_id": 43,
    "source_prompt_invalid": 44,
    "asset_path_invalid": 50,
    "asset_path_escape": 51,
    "asset_missing": 52,
    "asset_html_payload": 53,
    "asset_unsupported_magic": 54,
    "asset_too_small": 55,
    "adapter_contract_invalid": 60,
    "generation_contract_invalid": 61,
    "published_package_invalid": 70,
    "idempotency_conflict": 71,
    "injected_after_adapter": 80,
    "injected_after_assets": 81,
    "injected_before_manifest": 82,
    "injected_before_publish": 83,
    "injected_before_replace": 84,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract the frozen g0dam fixed commit into a verified external package.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    extract_parser = subcommands.add_parser("extract", help="run one external fixed-commit extraction")
    extract_parser.add_argument("--registry", required=True, type=Path)
    extract_parser.add_argument("--audit", required=True, type=Path)
    extract_parser.add_argument("--source-id", required=True)
    extract_parser.add_argument("--data-root", required=True, type=Path)
    extract_parser.add_argument("--output-root", required=True, type=Path)
    extract_parser.add_argument(
        "--failure-point",
        choices=["after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace"],
    )
    extract_parser.add_argument("--json", action="store_true")
    return parser


def _emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(payload.get("status", "unknown"))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "extract":
        raise AssertionError("argparse accepted an unsupported command")
    try:
        result = extract(
            registry_path=args.registry,
            audit_path=args.audit,
            source_id=args.source_id,
            data_root=args.data_root,
            output_root=args.output_root,
            failure_point=args.failure_point,
        )
    except ExtractionError as exc:
        _emit({"status": "failed", "error_code": exc.error_code, "message": str(exc)}, args.json)
        return EXIT_CODES.get(exc.error_code, 1)
    _emit(
        {
            "status": result.status,
            "output_path": str(result.output_path),
            "idempotency_key": result.idempotency_key,
            "semantic_digest": result.semantic_digest,
            "metrics": result.metrics,
            "states": list(result.states),
        },
        args.json,
    )
    return 0
