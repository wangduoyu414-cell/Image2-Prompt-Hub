from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from ingestion.adapters.joesai import JoeSaiAdapterError, parse_joesai_snapshot
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
    / "joesai-commercial-prompts"
    / "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b"
)


def fixture_png(slug: str) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + slug.encode("utf-8") * 80


def make_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    shutil.copytree(FIXTURE_ROOT / "source-files", root)
    manifest = root / "data" / "prompts.sample.json"
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.rename(root / "data" / "prompts.json")
    for row in rows:
        image = root / row["example_image"]
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(fixture_png(row["slug"]))
    return root


def source_config():
    return load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "joesai-commercial-prompts")


def build_fixture_documents(tmp_path: Path):
    snapshot = make_snapshot(tmp_path)
    parsed, model = parse_joesai_snapshot(snapshot, source_config())
    assets = {case.source_case_key: read_asset(snapshot, case.image_path) for case in parsed}
    adapter_output = resolved_adapter_output(source_config(), parsed, assets)
    generations = generation_examples(adapter_output)
    metrics = extraction_metrics(adapter_output, generations)
    return parsed, model, adapter_output, generations, metrics


def _manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _replace_english_prompt(path: Path, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index("```text", text.index("## Prompt (EN)")) + len("```text")
    end = text.index("\n```", start)
    path.write_text(text[:start] + "\n" + value + text[end:], encoding="utf-8")


def _replace_fence_after(path: Path, heading: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index("```text", text.index(heading))
    path.write_text(text[:start] + replacement + text[start + len("```text") :], encoding="utf-8")


def test_real_shape_fixture_matches_expected_documents_and_contracts(tmp_path: Path) -> None:
    parsed, model, adapter_output, generations, metrics = build_fixture_documents(tmp_path)
    assert model is None
    assert adapter_output == json.loads((FIXTURE_ROOT / "expected-adapter-output.json").read_text(encoding="utf-8"))
    assert generations == json.loads((FIXTURE_ROOT / "expected-generation-examples.json").read_text(encoding="utf-8"))
    assert metrics == json.loads((FIXTURE_ROOT / "expected-metrics.json").read_text(encoding="utf-8"))
    assert metrics["schema_version"] == "extraction-metrics/v1"
    assert len(parsed) == 3
    jewelry = next(case for case in parsed if case.native_id == "luxury-jewelry-campaign")
    assert jewelry.image_path == "assets/examples/luxury-jewelry-campaign-necklace.png"
    record = next(item for item in adapter_output["records"] if item["source_case_key"] == jewelry.source_case_key)
    extension = record["extensions"]["joesai.source"]
    assert extension["manifest"]["example_image"] == jewelry.image_path
    assert extension["prompt_zh_raw"].startswith("目标：生成一张高级珠宝")
    assert extension["why_it_works_raw"].startswith("It tells the model")
    assert record["source_claim"] == {"evidence_status": "unknown", "model_raw": None, "parameters_raw": None}
    assert record["rights_evidence"]["prompt_rights_status"] == "unknown"
    assert record["rights_evidence"]["asset_rights_status"] == "unknown"
    assert [item["source_path"] for item in record["pairings"][0]["evidence"]] == [
        "data/prompts.json",
        "prompts/jewelry/luxury-jewelry-campaign.md",
        "assets/examples/luxury-jewelry-campaign-necklace.png",
    ]
    context = load_contract_context(
        REPO_ROOT,
        REPO_ROOT / "config" / "sources-v1.yaml",
        REPO_ROOT / "reports" / "source-audit-v1.json",
    )
    validate_adapter_output(context, adapter_output)
    for generation in generations:
        validate_generation_example(context, generation)


def test_shared_logical_text_reader_preserves_joesai_frozen_output_and_decode_error(tmp_path: Path) -> None:
    root = make_snapshot(tmp_path / "crlf")
    page = root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md"
    logical = page.read_text(encoding="utf-8")
    page.write_bytes(logical.replace("\n", "\r\n").encode("utf-8"))
    parsed, _ = parse_joesai_snapshot(root, source_config())
    assets = {case.source_case_key: read_asset(root, case.image_path) for case in parsed}
    adapter_output = resolved_adapter_output(source_config(), parsed, assets)
    assert adapter_output == json.loads((FIXTURE_ROOT / "expected-adapter-output.json").read_text(encoding="utf-8"))

    invalid_root = make_snapshot(tmp_path / "invalid-utf8")
    (invalid_root / "data" / "prompts.json").write_bytes(b"\xff")
    with pytest.raises(JoeSaiAdapterError) as failure:
        parse_joesai_snapshot(invalid_root, source_config())
    assert failure.value.error_code == "source_data_invalid"


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda root: (
                lambda rows, path: (_write_manifest(path, rows + [copy.deepcopy(rows[0])]))
            )(_manifest(root / "data" / "prompts.json"), root / "data" / "prompts.json"),
            "source_duplicate_id",
        ),
        (
            lambda root: (
                lambda rows, path: (rows[0].pop("featured"), _write_manifest(path, rows))
            )(_manifest(root / "data" / "prompts.json"), root / "data" / "prompts.json"),
            "source_shape_invalid",
        ),
        (
            lambda root: (
                lambda rows, path: (rows[0].__setitem__("example_image", "../escape.png"), _write_manifest(path, rows))
            )(_manifest(root / "data" / "prompts.json"), root / "data" / "prompts.json"),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").write_text(
                (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").read_text(encoding="utf-8").replace(
                    "# Beauty Campaign KV Editorial", "# Wrong title", 1
                ),
                encoding="utf-8",
            ),
            "source_shape_invalid",
        ),
        (
            lambda root: _replace_fence_after(
                root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md", "## 提示词（中文）", "```markdown"
            ),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").write_text(
                (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").read_text(encoding="utf-8").replace(
                    "```text", "```markdown", 1
                ),
                encoding="utf-8",
            ),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").write_text(
                (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").read_text(encoding="utf-8").replace(
                    "## Best For", "## Prompt (EN)", 1
                ),
                encoding="utf-8",
            ),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "extra-case.md").write_text("# Extra\n", encoding="utf-8"),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").write_text(
                (root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md").read_text(encoding="utf-8")
                + "\n## Prompt (EN)\n\n```text\nA duplicate section that must not be parsed.\n```\n",
                encoding="utf-8",
            ),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "prompts" / "beauty" / "unrecognized.txt").write_text("not a prompt page", encoding="utf-8"),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "assets" / "examples" / "unregistered.png").write_bytes(fixture_png("unregistered")),
            "source_shape_invalid",
        ),
        (
            lambda root: (root / "assets" / "examples" / "beauty-campaign-kv-editorial.png").unlink(),
            "source_shape_invalid",
        ),
        (lambda root: _replace_english_prompt(root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md", "too short"), "source_prompt_invalid"),
    ],
)
def test_adapter_rejects_manifest_markdown_and_asset_drift(tmp_path: Path, mutator, expected_code: str) -> None:
    root = make_snapshot(tmp_path)
    mutator(root)
    with pytest.raises(JoeSaiAdapterError) as failure:
        parse_joesai_snapshot(root, source_config())
    assert failure.value.error_code == expected_code


@pytest.mark.parametrize(
    "link_kind",
    ("snapshot_root", "manifest_directory", "directory_component", "markdown_file", "image_file"),
)
def test_adapter_rejects_any_symlink_in_snapshot_file_paths(tmp_path: Path, link_kind: str) -> None:
    root = make_snapshot(tmp_path / link_kind)
    parse_root = root
    if link_kind == "snapshot_root":
        parse_root = tmp_path / "snapshot-root-link"
        parse_root.symlink_to(root, target_is_directory=True)
    elif link_kind == "manifest_directory":
        original = root / "data"
        target = root / "data-target"
        original.rename(target)
        original.symlink_to(target, target_is_directory=True)
    elif link_kind == "directory_component":
        original = root / "prompts" / "beauty"
        target = root / "prompts" / "beauty-target"
        original.rename(target)
        original.symlink_to(target, target_is_directory=True)
    elif link_kind == "markdown_file":
        original = root / "prompts" / "beauty" / "beauty-campaign-kv-editorial.md"
        target = root / "prompts" / "beauty" / "beauty-campaign-kv-editorial-target.md"
        original.rename(target)
        original.symlink_to(target)
    else:
        original = root / "assets" / "examples" / "beauty-campaign-kv-editorial.png"
        target = root / "assets" / "examples" / "beauty-campaign-kv-editorial-target.png"
        original.rename(target)
        original.symlink_to(target)

    with pytest.raises(JoeSaiAdapterError) as failure:
        parse_joesai_snapshot(parse_root, source_config())

    assert failure.value.error_code == "source_shape_invalid"
