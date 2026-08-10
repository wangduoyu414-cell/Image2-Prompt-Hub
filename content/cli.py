"""JSON-only maintenance boundary for Content Core; it contains no HTTP surface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings, RightsReview
from .review_store import RightsReviewStore, submission_from_mapping


EXIT_CODES = {
    "content_config_invalid": 20,
    "content_database_unavailable": 21,
    "content_schema_not_migrated": 22,
    "canonical_membership_conflict": 30,
    "rights_review_invalid": 40,
    "rights_review_target_missing": 41,
    "publication_version_missing": 50,
    "publication_version_not_completed": 51,
    "publication_version_incomplete": 52,
    "publication_current_inconsistent": 53,
    "publication_failure_point_invalid": 54,
    "injected_publication_build_failure": 80,
    "injected_publication_activation_failure": 81,
    "rights_review_v2_invalid": 90,
    "rights_review_v2_target_missing": 91,
    "rights_review_v2_batch_missing": 92,
    "rights_review_v2_idempotency_conflict": 93,
    "rights_review_v2_stale": 94,
    "rights_review_v2_selection_invalid": 95,
    "rights_review_v2_candidate_invalid": 96,
    "rights_review_v2_read_failed": 97,
    "rights_review_v2_database_failed": 98,
}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(
            json.dumps(
                {"status": "failed", "error_code": "rights_review_v2_invalid", "message": message},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(EXIT_CODES["rights_review_v2_invalid"])


def _database() -> ContentDatabase:
    value = os.environ.get("CONTENT_DATABASE_URL")
    if not value:
        raise ContentDatabaseError("content_config_invalid", "required runtime setting is missing: CONTENT_DATABASE_URL")
    return ContentDatabase(ContentDatabaseSettings(value))


def _review_store() -> RightsReviewStore:
    value = os.environ.get("CONTENT_DATABASE_URL")
    if not value:
        raise ContentDatabaseError("content_config_invalid", "required runtime setting is missing: CONTENT_DATABASE_URL")
    return RightsReviewStore(ContentDatabaseSettings(value))


def _read_json_object(path_value: str) -> dict[str, Any]:
    path = Path(path_value).resolve()
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ContentDatabaseError("rights_review_v2_invalid", "review submission JSON is too large")
        value = json.loads(path.read_text(encoding="utf-8"))
    except ContentDatabaseError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentDatabaseError("rights_review_v2_invalid", "review submission JSON is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise ContentDatabaseError("rights_review_v2_invalid", "review submission JSON root must be an object")
    return value


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(payload.get("status", "unknown"))


def _parse_reviewed_at(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContentDatabaseError("rights_review_invalid", "reviewed_at must be ISO-8601 with timezone") from exc
    if result.tzinfo is None:
        raise ContentDatabaseError("rights_review_invalid", "reviewed_at must include a timezone")
    return result


def _parser(*, json_errors: bool = False) -> argparse.ArgumentParser:
    parser_class = JsonArgumentParser if json_errors else argparse.ArgumentParser
    parser = parser_class(description="Operate the fail-closed Content Core publication boundary.")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=parser_class)
    for name, help_text in (
        ("canonicalize", "assign ready Generation Examples to exact Canonical Cases"),
        ("build-publication", "build one immutable ready publication version"),
        ("inspect-publication", "read only the active immutable publication snapshot"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true")
    build = commands.choices["build-publication"]
    build.add_argument("--failure-point", choices=["before_ready"])

    review = commands.add_parser("record-rights-review", help="append an explicit human rights review event")
    review.add_argument("--generation-example-row-id", type=int, required=True)
    review.add_argument("--repository-license", required=True)
    review.add_argument("--prompt-rights", choices=["approved", "unknown", "internal_only", "blocked"], required=True)
    review.add_argument("--asset-rights", choices=["approved", "unknown", "internal_only", "blocked"], required=True)
    review.add_argument("--author", required=True)
    review.add_argument("--original-url", required=True)
    review.add_argument("--evidence-url", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reviewed-at", required=True)
    review.add_argument(
        "--display-policy", choices=["mirror_allowed", "attribution_required", "link_only", "internal_only", "blocked"], required=True
    )
    review.add_argument("--review-note")
    review.add_argument("--json", action="store_true")

    queue = commands.add_parser("list-rights-review-queue", help="list case-level rights review subjects")
    queue.add_argument("--state", choices=["pending", "review_required", "publishable", "internal_only", "blocked"])
    queue.add_argument("--limit", type=int, default=100)
    queue.add_argument("--offset", type=int, default=0)
    queue.add_argument("--json", action="store_true")

    subject = commands.add_parser("inspect-rights-review-subject", help="inspect one case-level review subject")
    subject.add_argument("--source-case-version-id", type=int, required=True)
    subject.add_argument("--json", action="store_true")

    submit = commands.add_parser("submit-rights-review", help="atomically append one complete case-level review batch")
    submit.add_argument("--input-json", required=True)
    submit.add_argument("--json", action="store_true")

    inspect_batch = commands.add_parser("inspect-rights-review-batch", help="inspect one immutable review batch")
    inspect_batch.add_argument("--batch-id", type=int, required=True)
    inspect_batch.add_argument("--json", action="store_true")

    preview = commands.add_parser("preview-public-case-v2", help="build one non-activating Public Case Candidate v2")
    preview.add_argument("--source-case-version-id", type=int, required=True)
    preview.add_argument("--json", action="store_true")

    for name, help_text in (("activate-publication", "atomically activate a completed version"), ("rollback-publication", "atomically restore a completed version")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--version-id", type=int, required=True)
        command.add_argument("--json", action="store_true")
        if name == "activate-publication":
            command.add_argument("--failure-point", choices=["after_pointer_before_outbox"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    v2_commands = {
        "list-rights-review-queue",
        "inspect-rights-review-subject",
        "submit-rights-review",
        "inspect-rights-review-batch",
        "preview-public-case-v2",
    }
    args = _parser(json_errors=bool(raw_argv and raw_argv[0] in v2_commands)).parse_args(raw_argv)
    json_only_command = args.command in v2_commands
    try:
        if args.command == "list-rights-review-queue":
            result = _review_store().list_queue(state=args.state, limit=args.limit, offset=args.offset)
        elif args.command == "inspect-rights-review-subject":
            result = _review_store().inspect_subject(args.source_case_version_id)
        elif args.command == "submit-rights-review":
            result = _review_store().submit_review(submission_from_mapping(_read_json_object(args.input_json)))
        elif args.command == "inspect-rights-review-batch":
            result = _review_store().inspect_batch(args.batch_id)
        elif args.command == "preview-public-case-v2":
            result = _review_store().preview_candidate(args.source_case_version_id)
        else:
            database = _database()
            if args.command == "canonicalize":
                result = database.canonicalize()
            elif args.command == "record-rights-review":
                result = database.record_rights_review(
                    RightsReview(
                        generation_example_row_id=args.generation_example_row_id,
                        repository_license=args.repository_license,
                        prompt_rights=args.prompt_rights,
                        asset_rights=args.asset_rights,
                        author=args.author,
                        original_url=args.original_url,
                        evidence_url=args.evidence_url,
                        reviewer=args.reviewer,
                        reviewed_at=_parse_reviewed_at(args.reviewed_at),
                        display_policy=args.display_policy,
                        review_note=args.review_note,
                    )
                )
            elif args.command == "build-publication":
                result = database.build_publication(failure_point=args.failure_point)
            elif args.command == "activate-publication":
                result = database.activate_publication(args.version_id, failure_point=args.failure_point)
            elif args.command == "rollback-publication":
                result = database.rollback_publication(args.version_id)
            elif args.command == "inspect-publication":
                result = database.inspect_publication()
            else:  # argparse makes this unreachable.
                raise AssertionError("unrecognized content command")
        _emit({"status": "ok", "operation": args.command, "result": result}, json_only_command or args.json)
        return 0
    except ContentDatabaseError as exc:
        _emit(
            {"status": "failed", "error_code": exc.error_code, "message": str(exc)},
            json_only_command or getattr(args, "json", False),
        )
        return EXIT_CODES.get(exc.error_code, 1)


if __name__ == "__main__":
    raise SystemExit(main())
