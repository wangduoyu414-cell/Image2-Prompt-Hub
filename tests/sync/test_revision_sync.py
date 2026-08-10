from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ingestion.git_snapshot import (
    GitSnapshotError,
    candidate_snapshot,
    detect_default_branch_candidate,
    is_fast_forward,
    retain_candidate_ref,
)
from ingestion.registry import SourceConfig
from sync.revision import SyncSource, evaluate_quality_gate, fingerprint_map, stable_set_diff


REPO_ROOT = Path(__file__).resolve().parents[2]


def git(path: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *arguments], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def local_history(tmp_path: Path) -> tuple[Path, str, str]:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "sync test")
    git(source, "config", "user.email", "sync@example.invalid")
    (source / "payload.txt").write_text("baseline", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "baseline")
    baseline = git(source, "rev-parse", "HEAD")
    (source / "payload.txt").write_text("candidate", encoding="utf-8")
    git(source, "commit", "-am", "candidate")
    candidate = git(source, "rev-parse", "HEAD")
    return source, baseline, candidate


def config(source: Path, baseline: str) -> SourceConfig:
    return SourceConfig(
        source_id="sync-test-source",
        repository_url=source.as_uri(),
        verified_commit_sha=baseline,
        adapter_strategy="g0dam_manifest_json_v1",
        structure_type="structured_manifest_json",
        rights={},
    )


def test_candidate_authority_fetches_exact_fast_forward_commit_retains_ref_and_cleans(tmp_path: Path) -> None:
    source, baseline, candidate = local_history(tmp_path)
    runtime = tmp_path / "runtime"
    source_config = config(source, baseline)
    observed = detect_default_branch_candidate(
        source_config,
        runtime,
        default_branch="main",
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    )
    assert observed.candidate_sha == candidate
    assert is_fast_forward(
        source_config,
        runtime,
        previous_sha=baseline,
        candidate_sha=candidate,
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    )
    with candidate_snapshot(
        source_config,
        runtime,
        candidate_sha=candidate,
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    ) as snapshot:
        assert snapshot.commit_sha == candidate
        assert (snapshot.root / "payload.txt").read_text(encoding="utf-8") == "candidate"
    assert not list((runtime / "worktrees" / source_config.source_id).glob("candidate-*"))
    ref = retain_candidate_ref(
        source_config,
        runtime,
        candidate_sha=candidate,
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    )
    assert ref.endswith(candidate)
    assert retain_candidate_ref(
        source_config,
        runtime,
        candidate_sha=candidate,
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    ) == ref


def test_non_fast_forward_is_detected_without_moving_the_registered_baseline(tmp_path: Path) -> None:
    source, baseline, _candidate = local_history(tmp_path)
    git(source, "checkout", "-b", "rewrite", baseline)
    (source / "rewrite.txt").write_text("replacement", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "rewrite")
    replacement = git(source, "rev-parse", "HEAD")
    source_config = config(source, baseline)
    assert not is_fast_forward(
        source_config,
        tmp_path / "runtime",
        previous_sha=_candidate,
        candidate_sha=replacement,
        workspace_root=REPO_ROOT,
        allow_file_protocol=True,
    )
    assert source_config.verified_commit_sha == baseline


def _case(key: str, prompt: str, *, asset: str = "a" * 64, locator: str = "one") -> dict[str, object]:
    return {
        "source_case_key": key,
        "adapter_record": {
            "source_case_key": key,
            "prompt": {"raw_text": prompt, "source_location": {"source_path": locator}},
            "asset_references": [{"role": "output_primary", "content_sha256": asset, "resolution_state": "resolved"}],
            "source_claim": {"evidence_status": "source_claimed", "model_raw": "model"},
            "pairings": [{"prompt_id": "p", "asset_ref_id": "a", "method": "explicit", "status": "strong"}],
        },
        "generation_document": {"source_case_key": key, "generation_examples": [], "prompts": [], "assets": []},
    }


def test_stable_diff_ignores_source_paths_but_detects_semantic_prompt_change() -> None:
    previous = fingerprint_map([_case("source:a", "same", locator="old"), _case("source:b", "old")])
    candidate = fingerprint_map([_case("source:a", "same", locator="new"), _case("source:b", "new"), _case("source:c", "added")])
    diff = stable_set_diff(previous, candidate)
    assert diff["added"] == ["source:c"]
    assert diff["modified"] == ["source:b"]
    assert diff["unchanged"] == ["source:a"]
    assert diff["removed"] == []


def test_stable_diff_ignores_revision_bound_generation_provenance() -> None:
    old = _case("source:a", "same")
    new = _case("source:a", "same")
    for document, revision in ((old["generation_document"], "a" * 40), (new["generation_document"], "b" * 40)):
        document.update(
            {
                "revision_sha": revision,
                "source_case_locator": {"source_url": f"https://example.invalid/{revision}/case"},
                "prompts": [
                    {
                        "prompt_id": "p",
                        "raw_text": "same",
                        "language": "en",
                        "source_location": {"source_url": f"https://example.invalid/{revision}/prompt"},
                    }
                ],
                "assets": [
                    {
                        "asset_id": "asset:sha256:" + "a" * 64,
                        "role": "output_primary",
                        "content_sha256": "a" * 64,
                        "source_location": {"source_url": f"https://example.invalid/{revision}/asset"},
                    }
                ],
                "generation_examples": [
                    {
                        "generation_example_id": "generation:source:a:output-primary",
                        "prompt_id": "p",
                        "input_asset_ids": [],
                        "output_asset_ids": ["asset:sha256:" + "a" * 64],
                        "generation_claim": {"evidence_status": "source_claimed", "model_raw": "model", "parameters_raw": None},
                        "pairing": {"method": "explicit_structured_reference", "status": "strong", "evidence": [{"source_url": f"https://example.invalid/{revision}/pair"}]},
                    }
                ],
            }
        )
    assert stable_set_diff(fingerprint_map([old]), fingerprint_map([new]))["counts"] == {
        "added": 0,
        "modified": 0,
        "removed": 0,
        "unchanged": 1,
    }


def test_quality_gate_is_zero_tolerance_for_removal_or_count_drop() -> None:
    source = SyncSource(config(REPO_ROOT / "synthetic-source", "a" * 40), "main", 50, 0.9, "b" * 64, "c" * 64)
    gate = evaluate_quality_gate(
        candidate_metrics={"valid_case_count": 50, "pair_rate": 0.9, "broken_asset_count": 0},
        previous_metrics={"valid_case_count": 51},
        diff={"removed": ["source:removed"]},
        source=source,
    )
    assert gate["status"] == "review_required"
    assert set(gate["reasons"]) == {"case_count_decrease", "removed_cases"}


def test_candidate_snapshot_rejects_an_invalid_sha_before_git_side_effects(tmp_path: Path) -> None:
    source, baseline, _candidate = local_history(tmp_path)
    with pytest.raises(GitSnapshotError) as failure:
        with candidate_snapshot(config(source, baseline), tmp_path / "runtime", candidate_sha="not-a-sha", workspace_root=REPO_ROOT):
            pass
    assert failure.value.error_code == "invalid_commit_sha"
