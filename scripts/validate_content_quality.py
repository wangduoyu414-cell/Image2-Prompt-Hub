"""Validate the versioned content-quality authority against fixed preview facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from content.publication import normalize_prompt
from content.quality import ContentQualityError, content_quality_decision, load_content_quality_ledger


def validate(index_path: Path | None) -> dict[str, object]:
    decisions = load_content_quality_ledger()
    result: dict[str, object] = {
        "status": "passed",
        "decision_count": len(decisions),
        "verdict_counts": dict(sorted(Counter(item.verdict for item in decisions).items())),
        "reason_counts": dict(sorted(Counter(item.reason_code for item in decisions).items())),
    }
    if index_path is None:
        return result
    payload = json.loads(index_path.resolve().read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ContentQualityError("preview index does not contain cases")
    by_key = {
        (str(item.get("source_id")), str(item.get("revision_sha")), str(item.get("source_case_key"))): item
        for item in cases
        if isinstance(item, dict)
    }
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in cases:
        if not isinstance(item, dict):
            raise ContentQualityError("preview case is malformed")
        prompt_hash = hashlib.sha256(normalize_prompt(str(item.get("prompt", ""))).encode("utf-8")).hexdigest()
        groups[prompt_hash].append(item)
    duplicate_groups = {key: value for key, value in groups.items() if len(value) > 1}
    if len(duplicate_groups) != 29 or sum(len(value) for value in duplicate_groups.values()) != 69:
        raise ContentQualityError("fixed preview duplicate-group audit scope drifted")
    matched = 0
    decision_keys = {
        (item.source_id, item.revision_sha, item.source_case_key)
        for item in decisions
    }
    for decision in decisions:
        case = by_key.get((decision.source_id, decision.revision_sha, decision.source_case_key))
        if not isinstance(case, dict):
            raise ContentQualityError("quality decision target is absent from fixed preview")
        outputs = case.get("outputs")
        if not isinstance(outputs, list):
            raise ContentQualityError("quality decision target has malformed outputs")
        observed = content_quality_decision(
            source_id=decision.source_id,
            revision_sha=decision.revision_sha,
            source_case_key=decision.source_case_key,
            raw_prompt=str(case.get("prompt", "")),
            output_content_sha256=[str(item.get("content_sha256")) for item in outputs if isinstance(item, dict)],
        )
        if observed != decision:
            raise ContentQualityError("quality decision did not round-trip")
        matched += 1
    visible_output_count = 0
    for group in groups.values():
        visible_hashes = {
            str(output.get("content_sha256"))
            for case in group
            if (
                str(case.get("source_id")),
                str(case.get("revision_sha")),
                str(case.get("source_case_key")),
            ) not in decision_keys
            for output in case.get("outputs", [])
            if isinstance(output, dict)
        }
        if not visible_hashes:
            raise ContentQualityError("quality projection removed every output from a Prompt group")
        visible_output_count += len(visible_hashes)
    raw_output_count = sum(int(item.get("output_count", 0)) for item in cases if isinstance(item, dict))
    result.update(
        {
            "preview_case_count": len(cases),
            "preview_output_count": raw_output_count,
            "exact_prompt_count": len(groups),
            "exact_duplicate_group_count": len(duplicate_groups),
            "exact_duplicate_member_count": sum(len(value) for value in duplicate_groups.values()),
            "matched_decision_count": matched,
            "visible_output_count": visible_output_count,
        }
    )
    if (len(cases), raw_output_count, len(groups), visible_output_count, matched) != (3973, 9310, 3933, 9286, 24):
        raise ContentQualityError("fixed preview baseline counts drifted")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    default_index = Path.home() / ".codex" / "runtime" / "image2" / "internal-preview" / "index-v2.json"
    parser.add_argument("--index", type=Path, default=default_index if default_index.is_file() else None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate(args.index)
    except (ContentQualityError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result = {"status": "failed", "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else result["error"])
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else "passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
