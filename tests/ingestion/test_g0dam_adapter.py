from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ingestion.adapters.base import normalize_prompt as shared_normalize_prompt
from ingestion.adapters.base import prompt_sha256 as shared_prompt_sha256
from ingestion.adapters.g0dam import G0damAdapterError, normalize_prompt, parse_g0dam_snapshot, prompt_sha256
from ingestion.assets import AssetError, read_asset
from ingestion.contracts import (
    extraction_metrics,
    generation_examples,
    load_contract_context,
    resolved_adapter_output,
    validate_adapter_output,
    validate_generation_example,
)
from ingestion.registry import load_source_config


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "adapters" / "g0dam-work-prompts" / "690c2d6969a65b406b17ba7d41f18695a652c3fe"


def fixture_png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"x" * 600


def make_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    (root / "data").mkdir(parents=True)
    shutil.copy2(FIXTURE_ROOT / "source-files" / "data" / "prompts.sample.json", root / "data" / "prompts.json")
    image = root / "images" / "gptimg2-work-002-search-ad-landing-hero.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(fixture_png())
    return root


def build_fixture_documents(tmp_path: Path):
    source_config = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "g0dam-work-prompts")
    snapshot = make_snapshot(tmp_path)
    parsed, _ = parse_g0dam_snapshot(snapshot, source_config)
    assets = {case.source_case_key: read_asset(snapshot, case.image_path) for case in parsed}
    adapter_output = resolved_adapter_output(source_config, parsed, assets)
    generations = generation_examples(adapter_output)
    metrics = extraction_metrics(adapter_output, generations)
    return adapter_output, generations, metrics


def test_fixed_structure_fixture_matches_contract_expected_documents(tmp_path: Path) -> None:
    adapter_output, generations, metrics = build_fixture_documents(tmp_path)
    expected_adapter = json.loads((FIXTURE_ROOT / "expected-adapter-output.json").read_text(encoding="utf-8"))
    expected_generations = json.loads((FIXTURE_ROOT / "expected-generation-examples.json").read_text(encoding="utf-8"))
    expected_metrics = json.loads((FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))
    assert adapter_output == expected_adapter
    assert generations == expected_generations
    assert metrics == expected_metrics
    context = load_contract_context(REPO_ROOT, REPO_ROOT / "config" / "sources-v1.yaml", REPO_ROOT / "reports" / "source-audit-v1.json")
    validate_adapter_output(context, adapter_output)
    for generation in generations:
        validate_generation_example(context, generation)


def test_g0dam_prompt_identity_helpers_remain_backward_compatible() -> None:
    sample = "  Cafe\u0301\r\nsecond line  "
    assert normalize_prompt(sample) == shared_normalize_prompt(sample)
    assert prompt_sha256(sample) == shared_prompt_sha256(sample)


def test_asset_boundary_rejects_escape_html_magic_and_small_files(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path)
    with pytest.raises(AssetError) as escape:
        read_asset(root, "../escape.png")
    assert escape.value.error_code == "asset_path_escape"
    html = root / "images" / "html.png"
    html.write_bytes(b"<html>not an image</html>" + b"x" * 600)
    with pytest.raises(AssetError) as html_failure:
        read_asset(root, "images/html.png")
    assert html_failure.value.error_code == "asset_html_payload"
    bad_magic = root / "images" / "bad.png"
    bad_magic.write_bytes(b"not-a-image" * 100)
    with pytest.raises(AssetError) as bad_magic_failure:
        read_asset(root, "images/bad.png")
    assert bad_magic_failure.value.error_code == "asset_unsupported_magic"
    small = root / "images" / "small.png"
    small.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
    with pytest.raises(AssetError) as small_failure:
        read_asset(root, "images/small.png")
    assert small_failure.value.error_code == "asset_too_small"


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (lambda data: data.__setitem__("count", 2), "source_count_mismatch"),
        (
            lambda data: (
                data["prompts"].append(dict(data["prompts"][0])),
                data.__setitem__("count", 2),
            ),
            "source_duplicate_id",
        ),
        (lambda data: data["prompts"][0]["prompt"].__setitem__("en", ""), "source_shape_invalid"),
    ],
)
def test_adapter_rejects_structural_drift(tmp_path: Path, mutator, expected_code: str) -> None:
    root = make_snapshot(tmp_path)
    path = root / "data" / "prompts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutator(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    source_config = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "g0dam-work-prompts")
    with pytest.raises(G0damAdapterError) as failure:
        parse_g0dam_snapshot(root, source_config)
    assert failure.value.error_code == expected_code
