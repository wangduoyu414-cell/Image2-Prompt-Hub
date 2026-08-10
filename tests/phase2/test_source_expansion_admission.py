from __future__ import annotations

import copy
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from scripts import validate_phase2_source_expansion_admission as validator


AUDIT = validator.REPO_ROOT / "reports" / "phase2" / "source-expansion-admission-v2.json"
SCHEMA = validator.REPO_ROOT / "schemas" / "phase2-source-expansion-admission-v2.schema.json"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _image(path: Path, magic: bytes = b"\x89PNG\r\n\x1a\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(magic + b"x" * 1024)


def _repository_evidence(path: Path, *, notice: bool = False) -> None:
    (path / "LICENSE").write_text("fixture license\n", encoding="utf-8")
    (path / "README.md").write_text("fixture readme\n", encoding="utf-8")
    if notice:
        (path / "NOTICE.md").write_text("fixture notice\n", encoding="utf-8")


def test_normalization_and_sample_formula_are_frozen() -> None:
    assert validator._normalize_prompt(" Ａ  B\nC ") == "a b c"
    assert validator._normalize_source_url("https://twitter.com/User/status/123?x=1#f") == "https://x.com/user/status/123"
    assert validator._normalize_source_url("https://github.com/owner/repository") is None
    assert validator._expected_sample_size(284) == 43
    assert validator._expected_sample_size(198) == 30
    assert validator._expected_sample_size(95) == 30
    assert validator._normalize_visual_quality("medium") == "acceptable"


def test_imagine_parser_preserves_one_prompt_with_multiple_remote_outputs(tmp_path: Path) -> None:
    _repository_evidence(tmp_path)
    payload = [
        {
            "id": 1,
            "model": "gpt-image-2",
            "content": "A complete cinematic portrait prompt with enough detail to be independently useful.",
            "sourceLink": "https://x.com/example/status/123",
            "sourceMedia": [
                "https://pbs.twimg.com/media/one.jpg",
                "https://pbs.twimg.com/media/two.jpg",
            ],
            "author": {"name": "@example", "link": "https://x.com/example"},
            "sourceMeta": {"source": "twitterapi.io", "model_evidence": "gpt-image-2"},
            "imageCategories": {"workflows": [{"slug": "directed-editing"}]},
        }
    ]
    _write_json(tmp_path / "data" / "prompts.json", payload)
    parsed = validator._parse_imagine(tmp_path)
    assert parsed["source_record_count"] == 1
    assert len(parsed["cases"]) == 1
    assert len(parsed["cases"][0]["outputs"]) == 2
    assert all(item["authority"] == "remote_observation" for item in parsed["cases"][0]["outputs"])


def test_hiapi_parser_expands_prompt_variants_and_accounts_for_orphans(tmp_path: Path) -> None:
    _repository_evidence(tmp_path, notice=True)
    _image(tmp_path / "images" / "ui_case5" / "output.jpg")
    _image(tmp_path / "images" / "ui_case5" / "output_2.jpg", b"\xff\xd8\xff")
    _image(tmp_path / "images" / "unused" / "output.jpg")
    _image(tmp_path / "images" / "ui_case6" / "output.jpg")
    _image(tmp_path / "images" / "ui_case6" / "output_2.jpg", b"\xff\xd8\xff")
    _image(tmp_path / "images" / "ui_case6" / "contact-sheet.jpg")
    payload = {
        "name": "fixture",
        "model": "gpt-image-2",
        "updated_at": "2026-08-10",
        "source": {},
        "categories": [],
        "items": [
            {
                "id": "ui-case-5",
                "category": "ui-social",
                "source_url": "https://x.com/example/status/123",
                "image": "images/ui_case5/output.jpg",
                "prompt": "1. first\n2. second",
                "prompt_variants": [
                    {"label": "1", "image": "images/ui_case5/output.jpg", "prompt": "A complete first UI prompt with clear layout instructions."},
                    {"label": "2", "image": "images/ui_case5/output_2.jpg", "prompt": "A complete second UI prompt with clear layout instructions."},
                ],
            },
            {
                "id": "ui-case-6",
                "category": "ui-social",
                "source_url": "https://x.com/example/status/456",
                "image": "images/ui_case6/output.jpg",
                "prompt": "A complete UI prompt with two explicitly attributable same-directory outputs.",
            },
        ],
    }
    _write_json(tmp_path / "data" / "prompts.json", payload)
    parsed = validator._parse_hiapi(tmp_path)
    assert [item["case_id"] for item in parsed["cases"]] == ["ui-case-5:variant-1", "ui-case-5:variant-2", "ui-case-6"]
    assert len(parsed["cases"][-1]["outputs"]) == 2
    assert parsed["orphan_assets"] == ["images/ui_case6/contact-sheet.jpg", "images/unused/output.jpg"]
    assert len(parsed["asset_terminal_results"]) == 6


def test_ecom_parser_requires_aggregate_and_per_record_equality(tmp_path: Path) -> None:
    _repository_evidence(tmp_path)
    _image(tmp_path / "assets" / "prompts" / "fixture" / "preview-1.png")
    record = {
        "$schema": "../schema.json",
        "schemaVersion": 2,
        "id": "ec-0001",
        "slug": "fixture",
        "model": "gpt-image-2",
        "category": "fixture",
        "variants": [
            {
                "id": "variant-1",
                "prompt": "A complete e-commerce product prompt with specific composition and lighting instructions.",
                "sample": {"after": "assets/prompts/fixture/preview-1.png", "before": None},
            }
        ],
        "source": {"url": None},
    }
    _write_json(tmp_path / "data" / "prompts.json", {"schemaVersion": 2, "prompts": [record]})
    _write_json(tmp_path / "data" / "prompts" / "ec-0001-fixture.json", record)
    parsed = validator._parse_ecom(tmp_path)
    assert parsed["source_record_count"] == 1
    assert len(parsed["cases"]) == 1
    changed = copy.deepcopy(record)
    changed["variants"][0]["prompt"] = "changed"
    _write_json(tmp_path / "data" / "prompts" / "ec-0001-fixture.json", changed)
    with pytest.raises(validator.ValidationFailure, match="aggregate record differs"):
        validator._parse_ecom(tmp_path)


def test_ecom_parser_validates_before_assets(tmp_path: Path) -> None:
    _repository_evidence(tmp_path)
    _image(tmp_path / "assets" / "prompts" / "fixture" / "preview-1.png")
    record = {
        "$schema": "../schema.json",
        "schemaVersion": 2,
        "id": "ec-0001",
        "slug": "fixture",
        "model": "gpt-image-2",
        "category": "fixture",
        "variants": [
            {
                "id": "variant-1",
                "prompt": "A complete e-commerce edit prompt with a fixed local reference input.",
                "sample": {
                    "after": "assets/prompts/fixture/preview-1.png",
                    "before": "assets/prompts/fixture/missing-reference.png",
                },
            }
        ],
        "source": {"url": None},
    }
    _write_json(tmp_path / "data" / "prompts.json", {"schemaVersion": 2, "prompts": [record]})
    _write_json(tmp_path / "data" / "prompts" / "ec-0001-fixture.json", record)
    with pytest.raises(validator.ValidationFailure, match="asset validation failed"):
        validator._parse_ecom(tmp_path)


def test_quality_gate_requires_visual_quality_and_complete_coverage() -> None:
    case = {
        "case_id": "case-1",
        "category": "poster",
        "prompt_sha256": "a" * 64,
        "prompt_length": 120,
        "source_url_key": None,
        "outputs": [{"authority": "fixed_local", "content_sha256": "b" * 64}],
        "risk_flags": ["public_figure_or_celebrity"],
        "strong_pairing": True,
    }
    contribution = {
        "current_source_url_overlap_case_ids": [],
        "current_prompt_overlap_case_ids": [],
        "current_image_overlap_case_ids": [],
    }
    quality = validator._quality_block(
        [case],
        {
            "case-1": {
                "result": "pass",
                "prompt_complete": True,
                "image_readable": True,
                "semantic_match": True,
                "visual_quality": "low",
                "notes": "Readable but visibly unfinished.",
            }
        },
        contribution,
    )
    assert quality["result"] == "fail"
    assert quality["coverage"]["source_categories"] == ["poster"]
    assert quality["coverage"]["sampled_risk_flags"] == ["public_figure_or_celebrity"]


def test_quality_sample_covers_all_categories_risks_and_overlap_groups() -> None:
    cases = [
        {
            "case_id": f"case-{index}",
            "category": f"category-{index}",
            "prompt_sha256": f"{index:064x}",
            "prompt_length": 100 + index,
            "outputs": [{"authority": "fixed_local"}],
            "risk_flags": ["identity_or_official_document"] if index == 4 else [],
            "strong_pairing": True,
        }
        for index in range(5)
    ]
    sample = validator._select_quality_sample(cases, 5, {"image": ["case-3"]})
    assert set(sample) == {item["case_id"] for item in cases}


def test_within_source_exact_dedupe_uses_prompt_and_cross_record_url_or_image() -> None:
    def case(case_id: str, record_id: str, prompt_hash: str, url: str | None, image_hash: str) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "source_record_id": record_id,
            "prompt_sha256": prompt_hash,
            "source_url_key": url,
            "outputs": [{"authority": "fixed_local", "content_sha256": image_hash}],
            "strong_pairing": True,
        }

    cases = [
        case("a", "record-a", "1" * 64, "https://x.com/a/status/1", "a" * 64),
        case("b", "record-b", "2" * 64, "https://x.com/a/status/1", "b" * 64),
        case("c", "record-c", "3" * 64, "https://x.com/c/status/3", "a" * 64),
        case("d", "record-d", "1" * 64, "https://x.com/d/status/4", "d" * 64),
        case("e", "record-a", "5" * 64, "https://x.com/a/status/1", "e" * 64),
    ]
    assert [item["case_id"] for item in validator._unique_valid_cases(cases)] == ["a", "e"]


def test_remote_observation_requires_a_successful_image_terminal_result() -> None:
    base = {
        "status": 200,
        "media_type": "image/jpeg",
        "byte_size": 100,
        "observed_bytes_sha256": "a" * 64,
    }
    assert validator._remote_observation_ok(base)
    assert not validator._remote_observation_ok({**base, "media_type": "text/html"})


def test_remove_tree_clears_readonly_git_like_files(tmp_path: Path) -> None:
    target = tmp_path / "runtime"
    pack = target / ".git" / "objects" / "pack" / "fixture.pack"
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b"pack")
    pack.chmod(stat.S_IREAD)
    validator._remove_tree(target)
    assert not target.exists()


def test_checked_in_report_passes_offline_semantics() -> None:
    result = validator.validate(AUDIT, SCHEMA, determinism_check=True)
    assert result["status"] == "passed"
    assert result["summary"]["current_case_count"] == 1513
    assert result["summary"]["current_output_count"] == 1930
    assert result["summary"]["real_public_cases"] == 0


def _inject_remote_image_overlap(payload: dict[str, Any]) -> None:
    candidate = next(
        item for item in payload["candidates"] if item["source_id"].startswith("imaginevid-")
    )
    case_id = candidate["evidence"]["case_ledger"][0]["case_id"]
    contribution = candidate["contribution"]
    contribution["current_image_overlap_count"] = 1
    contribution["current_image_overlap_case_ids"] = [case_id]
    overlap_ids = (
        set(contribution["current_source_url_overlap_case_ids"])
        | set(contribution["current_prompt_overlap_case_ids"])
        | set(contribution["current_image_overlap_case_ids"])
    )
    unique_ids = sorted(
        row["case_id"]
        for row in candidate["evidence"]["case_ledger"]
        if row["case_id"] not in overlap_ids
    )
    contribution["unique_exact_contribution_count"] = len(unique_ids)
    contribution["unique_exact_contribution_case_ids_sha256"] = validator._hash_lines(unique_ids)
    candidate["quality"]["coverage"]["exact_overlap_sample_counts"]["image"] = int(
        case_id in candidate["quality"]["sample_ids"]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["candidates"].pop(), "exactly the three"),
        (
            lambda payload: next(item for item in payload["candidates"] if item["source_id"].startswith("imaginevid-" )).update({"status": "adapter_ready"}),
            "cannot be adapter_ready",
        ),
        (
            _inject_remote_image_overlap,
            "remote bytes may not participate",
        ),
        (
            lambda payload: next(item for item in payload["candidates"] if item["source_id"].startswith("ecomimagelab-" ))["quality"]["sample_ids"].pop(),
            "quality sample size",
        ),
        (lambda payload: payload["adapter_ready_batch"].append({"unexpected": True}), "exactly match"),
        (
            lambda payload: payload["candidates"][0]["rights"].update({"auto_publish": True}),
            "rights/publication",
        ),
        (lambda payload: payload["authority"].update({"current_case_count": 1512}), "1513/1930/2260/1885/0-public"),
    ],
)
def test_semantic_mutations_fail_closed(tmp_path: Path, mutation: Any, message: str) -> None:
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    mutation(payload)
    with pytest.raises(validator.ValidationFailure, match=message):
        validator._semantic_validate(payload)


def test_remote_observation_time_changes_do_not_change_fixed_core_digest() -> None:
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    imagine = next(item for item in payload["candidates"] if item["source_id"].startswith("imaginevid-"))
    imagine["evidence"]["remote_observations"][0]["observed_at"] = "2026-08-10T12:00:00Z"
    imagine["evidence"]["remote_observations_sha256"] = validator._digest(imagine["evidence"]["remote_observations"])
    original_digest = payload["canonical_digest"]
    summary = validator._semantic_validate(payload)
    assert summary["candidate_count"] == 3
    assert payload["canonical_digest"] == original_digest
    assert validator._digest(validator._fixed_core_payload(payload)) == original_digest


def test_remote_observation_health_changes_do_not_change_fixed_core_digest() -> None:
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    imagine = next(item for item in payload["candidates"] if item["source_id"].startswith("imaginevid-"))
    observation = imagine["evidence"]["remote_observations"][0]
    observation.update(
        {
            "status": None,
            "media_type": None,
            "byte_size": None,
            "observed_bytes_sha256": None,
            "error": "URLError",
        }
    )
    imagine["evidence"]["remote_observations_sha256"] = validator._digest(imagine["evidence"]["remote_observations"])
    imagine["metrics"]["broken_asset_count"] += 1
    imagine["metrics"]["broken_asset_rate"] = round(
        imagine["metrics"]["broken_asset_count"] / imagine["metrics"]["output_reference_count"], 8
    )
    original_digest = payload["canonical_digest"]
    validator._semantic_validate(payload)
    assert validator._digest(validator._fixed_core_payload(payload)) == original_digest
