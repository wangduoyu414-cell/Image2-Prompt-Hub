from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ingestion.git_snapshot import GitSnapshotError, detect_default_branch_candidate, fixed_snapshot
from ingestion.registry import RegistryError, SourceConfig, ensure_external_root, load_source_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def make_local_source(tmp_path: Path, *, attributes: str | None = None) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    run_git(source, "init")
    run_git(source, "config", "user.name", "TASK-0003 test")
    run_git(source, "config", "user.email", "task-0003@example.invalid")
    (source / "data").mkdir()
    (source / "data" / "prompts.json").write_text('{"count": 0, "prompts": [], "model_target": "fixture"}', encoding="utf-8")
    if attributes is not None:
        (source / ".gitattributes").write_text(attributes, encoding="utf-8")
    run_git(source, "add", ".")
    run_git(source, "commit", "-m", "fixed source")
    return source, run_git(source, "rev-parse", "HEAD")


def local_config(source: Path, commit: str) -> SourceConfig:
    return SourceConfig(
        source_id="g0dam-work-prompts",
        repository_url=source.as_uri(),
        verified_commit_sha=commit,
        adapter_strategy="g0dam_manifest_json_v1",
        structure_type="structured_manifest_json",
        rights={},
    )


def test_registry_accepts_all_three_static_supported_strategies() -> None:
    g0dam = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "g0dam-work-prompts")
    joesai = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "joesai-commercial-prompts")
    conardli = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "conardli-gpt-image-2-101")
    assert g0dam.verified_commit_sha == "690c2d6969a65b406b17ba7d41f18695a652c3fe"
    assert g0dam.adapter_strategy == "g0dam_manifest_json_v1"
    assert joesai.verified_commit_sha == "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b"
    assert joesai.adapter_strategy == "joesai_manifest_markdown_v1"
    assert joesai.structure_type == "markdown_prompt_pages_with_manifest"
    assert joesai.raw_url("data/prompts.json").endswith(f"/{joesai.verified_commit_sha}/data/prompts.json")
    assert conardli.verified_commit_sha == "971b67dc8cbca8cf6eb32e196fea04bddd6abe99"
    assert conardli.adapter_strategy == "conardli_compiled_case_manifest_v1"
    assert conardli.structure_type == "compiled_multi_category_case_gallery"
    assert conardli.raw_url("src/data/cases.json").endswith(f"/{conardli.verified_commit_sha}/src/data/cases.json")


def test_registry_rejects_unsupported_third_strategy_before_snapshot(tmp_path: Path) -> None:
    registry = json.loads((REPO_ROOT / "config" / "sources-v1.yaml").read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["source_id"] == "conardli-gpt-image-2-101")
    source["content"]["adapter_strategy"] = "conardli_dynamic_module_v1"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(RegistryError, match="not implemented"):
        load_source_config(path, "conardli-gpt-image-2-101")


def test_registry_rejects_noneligible_source_before_network(tmp_path: Path) -> None:
    registry = json.loads((REPO_ROOT / "config" / "sources-v1.yaml").read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["source_id"] == "g0dam-work-prompts")
    source["status"] = "probation"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(RegistryError, match="active"):
        load_source_config(path, "g0dam-work-prompts")


def test_registry_rejects_strategy_structure_mismatch_before_snapshot(tmp_path: Path) -> None:
    registry = json.loads((REPO_ROOT / "config" / "sources-v1.yaml").read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["source_id"] == "joesai-commercial-prompts")
    source["content"]["structure_type"] = "structured_manifest_json"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(RegistryError, match="structure type"):
        load_source_config(path, "joesai-commercial-prompts")


def test_runtime_root_inside_workspace_is_rejected() -> None:
    with pytest.raises(RegistryError, match="outside workspace"):
        ensure_external_root(REPO_ROOT, workspace_root=REPO_ROOT)


def test_fixed_snapshot_uses_exact_local_commit_and_cleans_worktree(tmp_path: Path) -> None:
    source, commit = make_local_source(tmp_path)
    config = local_config(source, commit)
    runtime = tmp_path / "runtime"
    with fixed_snapshot(config, runtime, workspace_root=REPO_ROOT, allow_file_protocol=True) as snapshot:
        assert snapshot.commit_sha == commit
        assert snapshot.read_only is True
        assert (snapshot.root / "data" / "prompts.json").is_file()
    worktree_parent = runtime / "worktrees" / config.source_id
    assert not any(worktree_parent.glob("run-*"))


def test_fixed_snapshot_fails_closed_for_git_filter_tree(tmp_path: Path) -> None:
    source, commit = make_local_source(tmp_path, attributes="*.png filter=lfs\n")
    config = local_config(source, commit)
    with pytest.raises(GitSnapshotError) as failure:
        with fixed_snapshot(config, tmp_path / "runtime", workspace_root=REPO_ROOT, allow_file_protocol=True):
            pass
    assert failure.value.error_code == "unsafe_git_filter"


def test_default_branch_detection_is_new_authority_while_fixed_snapshot_stays_on_registered_commit(tmp_path: Path) -> None:
    source, baseline = make_local_source(tmp_path)
    (source / "data" / "prompts.json").write_text('{"count": 1, "prompts": [], "model_target": "fixture"}', encoding="utf-8")
    run_git(source, "add", ".")
    run_git(source, "commit", "-m", "candidate")
    candidate = run_git(source, "rev-parse", "HEAD")
    config = local_config(source, baseline)
    runtime = tmp_path / "runtime"
    observed = detect_default_branch_candidate(
        config,
        runtime,
        default_branch=run_git(source, "branch", "--show-current"),
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    )
    assert observed.candidate_sha == candidate
    with fixed_snapshot(config, runtime, workspace_root=REPO_ROOT, allow_file_protocol=True) as snapshot:
        assert snapshot.commit_sha == baseline
