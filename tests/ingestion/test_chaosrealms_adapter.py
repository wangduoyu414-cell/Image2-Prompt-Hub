from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ingestion.adapters.chaosrealms import ChaosRealmsAdapterError, parse_chaos_snapshot
from ingestion.assets import read_asset
from ingestion.contracts import generation_examples, resolved_adapter_output
from ingestion.registry import SourceConfig, load_source_config


REVISION = "5296db8c996e38776c83a0bc8c64f848dcd512b3"
SOURCE_ID = "chaosrealmsai-gpt-image-2-gallery"
CASE_ID = "topic-one/package-one/case-one"
EXCLUDED_ID = "topic-one/package-one/case-two"
PROMPT = "Create a carefully composed square editorial image with precise lighting, material detail, clear subject separation, and no readable text or logos."


def _config() -> SourceConfig:
    return SourceConfig(
        source_id=SOURCE_ID,
        repository_url="https://github.com/ChaosRealmsAI/gpt-image-2-gallery",
        verified_commit_sha=REVISION,
        adapter_strategy="chaos_meta_three_webp_v1",
        structure_type="meta_json_with_three_webp_outputs",
        rights={"prompt_policy": "review_required", "asset_policy": "review_required", "repository_license": "MIT"},
        ingestion_mode="fixed_history",
        sync_enabled=False,
        one_shot_import_only=True,
    )


def _webp(seed: bytes) -> bytes:
    payload = (seed * 700)[:700]
    return b"RIFF" + len(payload).to_bytes(4, "little") + b"WEBP" + payload


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    case_dir = tmp_path / "works/topics/topic-one/packages/package-one/images/case-one"
    case_dir.mkdir(parents=True)
    meta_path = "works/topics/topic-one/packages/package-one/images/case-one/meta.json"
    meta = {
        "id": "case-one",
        "title": "Case One",
        "description": "A complete fixed-history example.",
        "type": "single",
        "prompt": PROMPT,
        "aspect_ratio": "1:1",
        "tags": ["editorial", "single"],
        "refs": [],
        "status": "done",
        "generation": {"mode": "image", "model": "gpt-image-2", "depends_on": [], "ref_urls": []},
        "display": {"featured": False},
    }
    (case_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for width in (400, 1600, 2400):
        (case_dir / f"image.w{width}.webp").write_bytes(_webp(str(width).encode()))
    index = {
        "schema_version": 1,
        "images": [
            {"id": CASE_ID, "image_id": "case-one", "topic_slug": "topic-one", "meta_path": meta_path},
            {
                "id": EXCLUDED_ID,
                "image_id": "case-two",
                "topic_slug": "topic-one",
                "meta_path": "works/topics/topic-one/packages/package-one/images/case-two/meta.json",
            },
        ],
    }
    (tmp_path / "works/index.json").write_text(json.dumps(index), encoding="utf-8")
    admission = {
        "schema_version": "fixed-history-admission/v1",
        "source_id": SOURCE_ID,
        "revision": REVISION,
        "mode": "fixed_history",
        "structure_strategy": "chaos_meta_three_webp_v1",
        "family_role": "canonical",
        "sync_eligible": False,
        "one_shot_import_only": True,
        "raw_case_count": 2,
        "case_count": 1,
        "excluded_case_count": 1,
        "output_variants": [
            {"suffix": "01-primary-w1600", "filename": "image.w1600.webp", "role": "output_primary", "width": 1600},
            {"suffix": "02-secondary-w400", "filename": "image.w400.webp", "role": "output_secondary", "width": 400},
            {"suffix": "03-secondary-w2400", "filename": "image.w2400.webp", "role": "output_secondary", "width": 2400},
        ],
        "admitted_case_ids": [CASE_ID],
        "exclusions": [{"case_id": EXCLUDED_ID, "reason": "risk:reference_dependency"}],
    }
    admission_path = tmp_path / "admission.json"
    admission_path.write_text(json.dumps(admission), encoding="utf-8")
    return admission_path, case_dir


def test_actual_v2_registry_loads_fixed_history_policy() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_source_config(root / "config/sources-v2.yaml", SOURCE_ID)
    assert config.ingestion_mode == "fixed_history"
    assert config.sync_enabled is False
    assert config.one_shot_import_only is True


def test_parse_fixed_history_case_preserves_three_outputs(tmp_path: Path) -> None:
    admission_path, _ = _fixture(tmp_path)
    parsed, cursor = parse_chaos_snapshot(tmp_path, _config(), admission_path=admission_path)
    assert cursor is None
    assert len(parsed) == 1
    assert [item.source_path for item in parsed[0].asset_paths] == [
        "works/topics/topic-one/packages/package-one/images/case-one/image.w1600.webp",
        "works/topics/topic-one/packages/package-one/images/case-one/image.w400.webp",
        "works/topics/topic-one/packages/package-one/images/case-one/image.w2400.webp",
    ]
    facts = {
        (parsed[0].source_case_key, binding.asset_ref_id): read_asset(tmp_path, binding.source_path)
        for binding in parsed[0].asset_paths
    }
    documents = generation_examples(resolved_adapter_output(_config(), parsed, facts))
    assert len(documents) == 1
    assert len(documents[0]["generation_examples"]) == 3
    assert [asset["role"] for asset in documents[0]["assets"]].count("output_primary") == 1
    assert documents[0]["extensions"]["chaosrealms.source"]["category"] == "topic-one"


def test_reference_dependency_and_partition_drift_fail_closed(tmp_path: Path) -> None:
    admission_path, case_dir = _fixture(tmp_path)
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    meta["generation"]["depends_on"] = [{"id": "reference"}]
    (case_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ChaosRealmsAdapterError, match="reference input"):
        parse_chaos_snapshot(tmp_path, _config(), admission_path=admission_path)

    meta["generation"]["depends_on"] = []
    (case_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    broken = copy.deepcopy(admission)
    broken["exclusions"] = []
    broken["excluded_case_count"] = 0
    broken["raw_case_count"] = 1
    admission_path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ChaosRealmsAdapterError, match="index does not equal"):
        parse_chaos_snapshot(tmp_path, _config(), admission_path=admission_path)
