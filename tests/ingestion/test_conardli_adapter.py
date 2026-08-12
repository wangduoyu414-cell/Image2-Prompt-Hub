from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ingestion.adapters.conardli import ConardLiAdapterError, parse_conardli_snapshot
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


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    REPO_ROOT
    / "fixtures"
    / "adapters"
    / "conardli-gpt-image-2-101"
    / "971b67dc8cbca8cf6eb32e196fea04bddd6abe99"
)


def fixture_png(native_id: str) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + hashlib.sha256(native_id.encode("utf-8")).digest() * 32


def fixture_webp(native_id: str) -> bytes:
    payload = native_id.encode("utf-8") * 8
    return b"RIFF" + len(payload).to_bytes(4, "little") + b"WEBP" + payload


def source_config():
    return load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "conardli-gpt-image-2-101")


def make_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    shutil.copytree(FIXTURE_ROOT / "source-files", root)
    manifest = json.loads((root / "src" / "data" / "cases.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        native_id = str(case["id"])
        image = root / "public" / "case" / f"{native_id}.png"
        thumbnail = root / "public" / "case" / f"{native_id}-thumb.webp"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(fixture_png(native_id))
        thumbnail.write_bytes(fixture_webp(native_id))
    return root


def build_fixture_documents(tmp_path: Path):
    snapshot = make_snapshot(tmp_path)
    config = source_config()
    parsed, model = parse_conardli_snapshot(snapshot, config)
    assets = {case.source_case_key: read_asset(snapshot, case.image_path) for case in parsed}
    adapter_output = resolved_adapter_output(config, parsed, assets)
    generations = generation_examples(adapter_output)
    metrics = extraction_metrics(adapter_output, generations)
    return snapshot, parsed, model, adapter_output, generations, metrics


def _fixture_json(name: str):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _manifest(root: Path) -> dict:
    return json.loads((root / "src" / "data" / "cases.json").read_text(encoding="utf-8"))


def _write_manifest(root: Path, value: dict) -> None:
    (root / "src" / "data" / "cases.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_real_shape_fixture_matches_expected_documents_contracts_and_logical_text(tmp_path: Path) -> None:
    snapshot, parsed, model, adapter_output, generations, metrics = build_fixture_documents(tmp_path)
    assert model is None
    assert adapter_output == _fixture_json("expected-adapter-output.json")
    assert generations == _fixture_json("expected-generation-examples.json")
    assert metrics == _fixture_json("expected-metrics.json")
    assert len(parsed) == 3
    assert metrics["schema_version"] == "extraction-metrics/v1"

    manifest = _manifest(snapshot)
    first_case = manifest["cases"][0]
    first_prompt_path = snapshot / "public" / "case" / first_case["prompt_path"]
    first_prompt_path.write_bytes(first_prompt_path.read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in first_prompt_path.read_bytes()
    record = next(item for item in adapter_output["records"] if item["source_case_key"].endswith(first_case["id"]))
    assert record["prompt"]["raw_text"] == first_case["prompt_content"]
    assert "\r" not in record["prompt"]["raw_text"]
    assert record["prompt"]["source_location"]["source_path"] == f"public/case/{first_case['prompt_path']}"
    assert [item["source_path"] for item in record["pairings"][0]["evidence"]] == [
        "src/data/cases.json",
        "public/case/_mapping.json",
        f"public/case/{first_case['prompt_path']}",
        f"public/case/{first_case['id']}.png",
    ]
    extension = record["extensions"]["conardli.source"]
    assert extension["case"]["category_label"] == extension["category"]["cn"]
    assert extension["category"]["ready"] == extension["category"]["total"] == 2
    assert "prompt_content" not in extension["case"]
    assert "cases" not in extension["mapping"]["item"]
    assert record["asset_references"] == [record["asset_references"][0]]
    assert record["asset_references"][0]["role"] == "output_primary"
    assert "thumbnail_location" in extension
    assert record["source_claim"] == {"evidence_status": "unknown", "model_raw": None, "parameters_raw": None}
    assert record["rights_evidence"]["prompt_rights_status"] == "unknown"
    assert record["rights_evidence"]["asset_rights_status"] == "unknown"

    context = load_contract_context(
        REPO_ROOT,
        REPO_ROOT / "config" / "sources-v1.yaml",
        REPO_ROOT / "reports" / "source-audit-v1.json",
    )
    validate_adapter_output(context, adapter_output)
    for generation in generations:
        validate_generation_example(context, generation)


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda data: data["cases"][0].__setitem__("unexpected", True),
            "source_shape_invalid",
        ),
        (
            lambda data: data["categories"]["academic-figures"].__setitem__("ready", True),
            "source_shape_invalid",
        ),
        (
            lambda data: data["categories"]["academic-figures"].__setitem__("ready", 3),
            "source_shape_invalid",
        ),
        (
            lambda data: data["cases"][0].__setitem__("category_label", "Academic figures"),
            "source_shape_invalid",
        ),
        (
            lambda data: data["templates"]["academic-figures/qualitative-comparison-grid"].__setitem__(
                "cases_count", 2
            ),
            "source_shape_invalid",
        ),
    ],
)
def test_adapter_rejects_corrected_shape_and_cross_index_drift(tmp_path: Path, mutator, expected_code: str) -> None:
    root = make_snapshot(tmp_path)
    data = _manifest(root)
    mutator(data)
    _write_manifest(root, data)
    with pytest.raises(ConardLiAdapterError) as failure:
        parse_conardli_snapshot(root, source_config())
    assert failure.value.error_code == expected_code


def test_adapter_reconciles_only_eol_and_rejects_non_eol_prompt_drift(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path)
    parsed, _ = parse_conardli_snapshot(root, source_config())
    assert len(parsed) == 3
    prompt = root / "public" / "case" / "academic-figures" / "qualitative-comparison-grid" / "1.json"
    prompt.write_bytes(prompt.read_bytes().replace("Comparison".encode("utf-8"), "Xomparison".encode("utf-8"), 1))
    with pytest.raises(ConardLiAdapterError) as failure:
        parse_conardli_snapshot(root, source_config())
    assert failure.value.error_code == "source_prompt_invalid"


def test_adapter_rejects_invalid_utf8_as_source_data_error(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path)
    prompt = root / "public" / "case" / "academic-figures" / "scientific-schematic" / "1.txt"
    prompt.write_bytes(b"\xff\xfeinvalid")
    with pytest.raises(ConardLiAdapterError) as failure:
        parse_conardli_snapshot(root, source_config())
    assert failure.value.error_code == "source_data_invalid"


def test_mapping_file_set_and_directory_symlink_fail_closed_while_index_is_non_authoritative(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path / "index")
    before, _ = parse_conardli_snapshot(root, source_config())
    (root / "public" / "case" / "INDEX.md").write_text("stale count: 999\n", encoding="utf-8")
    after, _ = parse_conardli_snapshot(root, source_config())
    assert [item.adapter_record for item in after] == [item.adapter_record for item in before]

    extra_root = make_snapshot(tmp_path / "extra")
    (extra_root / "public" / "case" / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ConardLiAdapterError) as extra_failure:
        parse_conardli_snapshot(extra_root, source_config())
    assert extra_failure.value.error_code == "source_shape_invalid"

    link_root = make_snapshot(tmp_path / "symlink")
    original = link_root / "public" / "case" / "academic-figures"
    target = link_root / "public" / "case" / "academic-figures-target"
    original.rename(target)
    original.symlink_to(target, target_is_directory=True)
    with pytest.raises(ConardLiAdapterError) as link_failure:
        parse_conardli_snapshot(link_root, source_config())
    assert link_failure.value.error_code == "source_shape_invalid"


def test_mapping_drift_and_thumbnail_non_asset_behavior(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path)
    mapping_path = root / "public" / "case" / "_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["items"][0]["cases"][0]["file"] = "academic-figures/qualitative-comparison-grid/wrong.json"
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ConardLiAdapterError) as failure:
        parse_conardli_snapshot(root, source_config())
    assert failure.value.error_code == "source_shape_invalid"

    clean_root = make_snapshot(tmp_path / "clean")
    parsed, _ = parse_conardli_snapshot(clean_root, source_config())
    for parsed_case in parsed:
        references = parsed_case.adapter_record["asset_references"]
        assert len(references) == 1
        assert references[0]["role"] == "output_primary"
        assert parsed_case.adapter_record["extensions"]["conardli.source"]["thumbnail_location"]["source_path"].endswith(
            "-thumb.webp"
        )
