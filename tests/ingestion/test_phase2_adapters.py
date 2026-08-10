from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ingestion.adapters.erickkkyt import (
    KNOWN_FIXED_ORPHAN_ASSET_FILES,
    ErickkkytAdapterError,
    parse_erickkkyt_snapshot,
)
from ingestion.adapters.freestylefly import FreestyleflyAdapterError, parse_freestylefly_snapshot
from ingestion.adapters.vigozhao import VigoZhaoAdapterError, parse_vigozhao_snapshot
from ingestion.assets import AssetFact, read_asset
from ingestion.contracts import (
    ContractError,
    extraction_metrics,
    generation_examples,
    load_contract_context,
    resolved_adapter_output,
    validate_adapter_output,
    validate_generation_example,
)
from ingestion.registry import load_source_config


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((REPO_ROOT / "fixtures" / "adapters" / "phase2-multi-output.fixture.json").read_text(encoding="utf-8"))


def _image_bytes(label: str, suffix: str) -> bytes:
    payload = label.encode("utf-8") * 100
    if suffix == ".png":
        return b"\x89PNG\r\n\x1a\n" + payload
    if suffix == ".webp":
        return b"RIFF" + b"x" * 4 + b"WEBP" + payload
    return b"\xff\xd8\xff" + payload


def _write_image(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_image_bytes(relative, path.suffix.lower()))


def _freestyle_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "freestyle"
    path = root / "data" / "cases.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(FIXTURE["freestylefly"], ensure_ascii=False), encoding="utf-8")
    for case in FIXTURE["freestylefly"]["cases"]:
        _write_image(root, "data" + case["image"])
    for orphan in ("case12.jpg", "case169.jpg", "case170.jpg"):
        _write_image(root, f"data/images/{orphan}")
    return root


def _erick_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "erick"
    path = root / "prompts" / "prompts.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(FIXTURE["erickkkyt"], ensure_ascii=False), encoding="utf-8")
    for row in FIXTURE["erickkkyt"]:
        for image in row["images"]:
            _write_image(root, image)
    for orphan in KNOWN_FIXED_ORPHAN_ASSET_FILES:
        if Path(orphan).suffix.lower() == ".md":
            path = root / orphan
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixed non-case source file\n", encoding="utf-8")
        else:
            _write_image(root, orphan)
    return root


def _vigo_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "vigo"
    for slug, style in FIXTURE["vigozhao"].items():
        directory = root / "styles" / slug
        directory.mkdir(parents=True)
        (directory / "style.json").write_text(json.dumps(style, ensure_ascii=False), encoding="utf-8")
        _write_image(root, f"styles/{slug}/preview-16x9.jpg")
        _write_image(root, f"styles/{slug}/preview-9x16.jpg")
    return root


def _documents(snapshot: Path, source_id: str, parser):
    config = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", source_id)
    parsed, model = parser(snapshot, config)
    facts = {
        (case.source_case_key, binding.asset_ref_id): read_asset(snapshot, binding.source_path)
        for case in parsed
        for binding in case.asset_paths
    }
    adapter_output = resolved_adapter_output(config, parsed, facts)
    documents = generation_examples(adapter_output)
    metrics = extraction_metrics(adapter_output, documents)
    return parsed, model, adapter_output, documents, metrics


def test_phase2_adapters_preserve_case_counts_and_multi_output_contract(tmp_path: Path) -> None:
    rows = [
        (_freestyle_snapshot(tmp_path), "freestylefly-awesome-gpt-image-2", parse_freestylefly_snapshot, 2, 2),
        (_erick_snapshot(tmp_path), "erickkkyt-awesome-gptimage2-prompts", parse_erickkkyt_snapshot, 2, 3),
        (_vigo_snapshot(tmp_path), "vigozhao-ai-visual-prompt-cookbook", parse_vigozhao_snapshot, 2, 4),
    ]
    context = load_contract_context(
        REPO_ROOT, REPO_ROOT / "config" / "sources-v1.yaml", REPO_ROOT / "reports" / "source-audit-v1.json"
    )
    for snapshot, source_id, parser, expected_cases, expected_outputs in rows:
        parsed, _model, adapter_output, documents, metrics = _documents(snapshot, source_id, parser)
        assert len(parsed) == expected_cases
        assert len(adapter_output["records"]) == expected_cases
        assert len(documents) == expected_cases
        assert sum(len(item["generation_examples"]) for item in documents) == expected_outputs
        assert metrics["observed_case_count"] == expected_cases
        assert metrics["generation_example_count"] == expected_outputs
        validate_adapter_output(context, adapter_output)
        for document in documents:
            validate_generation_example(context, document)

    _, _, _, erick_documents, _ = _documents(
        rows[1][0], "erickkkyt-awesome-gptimage2-prompts", parse_erickkkyt_snapshot
    )
    multi = next(item for item in erick_documents if item["source_case_key"].endswith(":x-222"))
    assert len(multi["assets"]) == 2
    assert len(multi["generation_examples"]) == 2
    assert all(len(item["output_asset_ids"]) == 1 for item in multi["generation_examples"])


def test_multi_output_resolution_rejects_duplicate_content(tmp_path: Path) -> None:
    snapshot = _erick_snapshot(tmp_path)
    config = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "erickkkyt-awesome-gptimage2-prompts")
    parsed, _ = parse_erickkkyt_snapshot(snapshot, config)
    case = next(item for item in parsed if item.native_id == "x-222")
    facts = {
        (case.source_case_key, binding.asset_ref_id): AssetFact(binding.source_path, "a" * 64, 1024, "image/jpeg")
        for binding in case.asset_paths
    }
    with pytest.raises(ContractError) as failure:
        resolved_adapter_output(config, [case], facts)
    assert failure.value.error_code == "adapter_mapping_invalid"


def test_phase2_adapters_fail_closed_on_source_relationship_drift(tmp_path: Path) -> None:
    freestyle = _freestyle_snapshot(tmp_path / "f")
    _write_image(freestyle, "data/images/case999.jpg")
    config_path = REPO_ROOT / "config" / "sources-v1.yaml"
    with pytest.raises(FreestyleflyAdapterError):
        parse_freestylefly_snapshot(
            freestyle, load_source_config(config_path, "freestylefly-awesome-gpt-image-2")
        )

    erick = _erick_snapshot(tmp_path / "e")
    manifest = erick / "prompts" / "prompts.json"
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    rows[1]["pair_ids"][1] = rows[1]["pair_ids"][0]
    manifest.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ErickkkytAdapterError):
        parse_erickkkyt_snapshot(erick, load_source_config(config_path, "erickkkyt-awesome-gptimage2-prompts"))

    erick_orphan = _erick_snapshot(tmp_path / "eo")
    _write_image(erick_orphan, "assets/gpt-image-2-x-discussions/unreferenced-new-output.jpg")
    with pytest.raises(ErickkkytAdapterError):
        parse_erickkkyt_snapshot(
            erick_orphan, load_source_config(config_path, "erickkkyt-awesome-gptimage2-prompts")
        )

    erick_missing_fixed = _erick_snapshot(tmp_path / "em")
    (erick_missing_fixed / sorted(KNOWN_FIXED_ORPHAN_ASSET_FILES)[0]).unlink()
    with pytest.raises(ErickkkytAdapterError):
        parse_erickkkyt_snapshot(
            erick_missing_fixed, load_source_config(config_path, "erickkkyt-awesome-gptimage2-prompts")
        )

    vigo = _vigo_snapshot(tmp_path / "v")
    (vigo / "styles" / "acid-lime-fixture-style" / "preview-9x16.jpg").unlink()
    with pytest.raises(VigoZhaoAdapterError):
        parse_vigozhao_snapshot(vigo, load_source_config(config_path, "vigozhao-ai-visual-prompt-cookbook"))


def test_phase2_adapters_are_deterministic_for_same_snapshot(tmp_path: Path) -> None:
    snapshot = _vigo_snapshot(tmp_path)
    first = _documents(snapshot, "vigozhao-ai-visual-prompt-cookbook", parse_vigozhao_snapshot)
    second = _documents(snapshot, "vigozhao-ai-visual-prompt-cookbook", parse_vigozhao_snapshot)
    assert first[2:] == second[2:]
