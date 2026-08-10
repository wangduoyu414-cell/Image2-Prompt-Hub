from __future__ import annotations

import json
import shutil
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import ingestion.pipeline as pipeline
from ingestion.adapters import adapter_for_strategy
from ingestion.adapters.base import AdapterError
from ingestion.adapters.conardli import parse_conardli_snapshot
from ingestion.adapters.g0dam import parse_g0dam_snapshot
from ingestion.adapters.joesai import parse_joesai_snapshot
from ingestion.git_snapshot import GitSnapshot, GitSnapshotError
from ingestion.registry import load_source_config
from ingestion.pipeline import ExtractionError, extract, verify_published_package
from scripts import validate_joesai_multi_source as shared_live_validator
from scripts import validate_three_pilot_sources as three_source_validator


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "adapters" / "g0dam-work-prompts" / "690c2d6969a65b406b17ba7d41f18695a652c3fe"
JOESAI_FIXTURE_ROOT = (
    REPO_ROOT
    / "fixtures"
    / "adapters"
    / "joesai-commercial-prompts"
    / "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b"
)
CONARDLI_FIXTURE_ROOT = (
    REPO_ROOT
    / "fixtures"
    / "adapters"
    / "conardli-gpt-image-2-101"
    / "971b67dc8cbca8cf6eb32e196fea04bddd6abe99"
)


def make_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    (root / "data").mkdir(parents=True)
    shutil.copy2(FIXTURE_ROOT / "source-files" / "data" / "prompts.sample.json", root / "data" / "prompts.json")
    image = root / "images" / "gptimg2-work-002-search-ad-landing-hero.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 600)
    return root


def make_joesai_snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "joesai-snapshot"
    shutil.copytree(JOESAI_FIXTURE_ROOT / "source-files", root)
    manifest = root / "data" / "prompts.sample.json"
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    manifest.rename(root / "data" / "prompts.json")
    for row in rows:
        image = root / row["example_image"]
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + row["slug"].encode("utf-8") * 80)
    return root


def make_conardli_snapshot(tmp_path: Path) -> Path:
    import hashlib

    root = tmp_path / "conardli-snapshot"
    shutil.copytree(CONARDLI_FIXTURE_ROOT / "source-files", root)
    manifest = json.loads((root / "src" / "data" / "cases.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        native_id = str(case["id"])
        image = root / "public" / "case" / f"{native_id}.png"
        thumbnail = root / "public" / "case" / f"{native_id}-thumb.webp"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + hashlib.sha256(native_id.encode("utf-8")).digest() * 32)
        thumbnail.write_bytes(b"RIFF" + native_id.encode("utf-8") * 8)
    return root


def install_fake_snapshot(monkeypatch: pytest.MonkeyPatch, snapshot_root: Path):
    @contextmanager
    def fake_snapshot(source_config, data_root, **_kwargs):
        yield GitSnapshot(
            root=snapshot_root,
            commit_sha=source_config.verified_commit_sha,
            mirror_path=Path(data_root) / "fake-mirror",
        )

    monkeypatch.setattr(pipeline, "fixed_snapshot", fake_snapshot)


def run_extract(tmp_path: Path, output_root: Path, **kwargs):
    return extract(
        registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
        audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
        source_id="g0dam-work-prompts",
        data_root=tmp_path / "external-data",
        output_root=output_root,
        **kwargs,
    )


def run_joesai_extract(tmp_path: Path, output_root: Path, **kwargs):
    return extract(
        registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
        audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
        source_id="joesai-commercial-prompts",
        data_root=tmp_path / "external-joesai-data",
        output_root=output_root,
        **kwargs,
    )


def run_conardli_extract(tmp_path: Path, output_root: Path, **kwargs):
    return extract(
        registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
        audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
        source_id="conardli-gpt-image-2-101",
        data_root=tmp_path / "external-conardli-data",
        output_root=output_root,
        **kwargs,
    )


def file_hashes(root: Path) -> dict[str, str]:
    import hashlib

    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def test_pipeline_publishes_then_verifies_existing_without_image_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_snapshot(monkeypatch, make_snapshot(tmp_path))
    output_root = tmp_path / "external-output"
    first = run_extract(tmp_path, output_root)
    second = run_extract(tmp_path, output_root)
    assert first.status == "published"
    assert second.status == "verified_existing"
    assert first.semantic_digest == second.semantic_digest
    manifest = verify_published_package(first.output_path, first.idempotency_key)
    assert manifest["semantic_digest"] == first.semantic_digest
    assert all(path.suffix == ".json" for path in first.output_path.rglob("*") if path.is_file())
    assert len(list((first.output_path / "generation-examples").glob("*.json"))) == 1


def test_static_dispatch_and_neutral_joesai_package_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert adapter_for_strategy("g0dam_manifest_json_v1") is parse_g0dam_snapshot
    assert adapter_for_strategy("joesai_manifest_markdown_v1") is parse_joesai_snapshot
    assert adapter_for_strategy("conardli_compiled_case_manifest_v1") is parse_conardli_snapshot
    with pytest.raises(AdapterError) as unsupported:
        adapter_for_strategy("unknown_adapter_v1")
    assert unsupported.value.error_code == "registry_invalid"

    install_fake_snapshot(monkeypatch, make_joesai_snapshot(tmp_path))
    output_root = tmp_path / "joesai-output"
    first = run_joesai_extract(tmp_path, output_root)
    first_hashes = file_hashes(first.output_path)
    second = run_joesai_extract(tmp_path, output_root)
    manifest = verify_published_package(first.output_path, first.idempotency_key)
    metrics = json.loads((first.output_path / "metrics.json").read_text(encoding="utf-8"))
    assert first.status == "published"
    assert second.status == "verified_existing"
    assert first.semantic_digest == second.semantic_digest
    assert first_hashes == file_hashes(second.output_path)
    assert manifest["schema_version"] == "extraction-package/v1"
    assert metrics["schema_version"] == "extraction-metrics/v1"
    assert len(list((first.output_path / "generation-examples").glob("*.json"))) == 3
    assert all(path.suffix == ".json" for path in first.output_path.rglob("*") if path.is_file())


def test_conardli_pipeline_uses_neutral_package_without_thumbnail_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_snapshot(monkeypatch, make_conardli_snapshot(tmp_path))
    output_root = tmp_path / "conardli-output"
    first = run_conardli_extract(tmp_path, output_root)
    second = run_conardli_extract(tmp_path, output_root)
    manifest = verify_published_package(first.output_path, first.idempotency_key)
    adapter_output = json.loads((first.output_path / "adapter-output.json").read_text(encoding="utf-8"))
    metrics = json.loads((first.output_path / "metrics.json").read_text(encoding="utf-8"))
    assert first.status == "published"
    assert second.status == "verified_existing"
    assert manifest["schema_version"] == "extraction-package/v1"
    assert metrics["schema_version"] == "extraction-metrics/v1"
    assert metrics["observed_case_count"] == 3
    assert len(adapter_output["records"]) == 3
    assert all(len(record["asset_references"]) == 1 for record in adapter_output["records"])
    assert all("\r" not in record["prompt"]["raw_text"] for record in adapter_output["records"])
    assert all(path.suffix == ".json" for path in first.output_path.rglob("*") if path.is_file())


def test_three_source_validator_structures_shared_helper_failure_without_docker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_shared_failure(_args):
        raise shared_live_validator.ValidationFailure("shared helper failure")

    monkeypatch.setattr(three_source_validator, "run", raise_shared_failure)
    result = three_source_validator.main(
        [
            "--registry", "config/sources-v1.yaml", "--audit", "reports/source-audit-v1.json",
            "--g0dam-source-id", "g0dam-work-prompts", "--g0dam-expected-commit", "a", "--g0dam-expected-cases", "100", "--g0dam-expected-aggregate", "a",
            "--joesai-source-id", "joesai-commercial-prompts", "--joesai-expected-commit", "b", "--joesai-expected-cases", "50", "--joesai-expected-aggregate", "b",
            "--conardli-source-id", "conardli-gpt-image-2-101", "--conardli-expected-commit", "c", "--conardli-expected-cases", "162", "--conardli-expected-aggregate", "c",
            "--runs", "2", "--failure-injection", "--concurrency", "--json",
        ]
    )
    assert result == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "failed",
        "error": "shared helper failure",
        "error_type": "ValidationFailure",
    }


def test_three_source_validator_prewarm_uses_all_sources_with_persistent_root_without_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[dict[str, object]] = []

    @contextmanager
    def fake_fixed_snapshot(config, data_root, **kwargs):
        observed.append({"source_id": config.source_id, "data_root": data_root, "kwargs": kwargs})
        (data_root / "mirrors" / f"{config.source_id}.git").mkdir(parents=True)
        (data_root / "worktrees" / config.source_id).mkdir(parents=True)
        yield object()

    monkeypatch.setattr(three_source_validator, "fixed_snapshot", fake_fixed_snapshot)
    source_ids = ["g0dam-work-prompts", "joesai-commercial-prompts", "conardli-gpt-image-2-101"]
    source_root = tmp_path / "external-source-git"
    prewarmed = three_source_validator._prewarm_source_mirrors(
        REPO_ROOT / "config" / "sources-v1.yaml", source_ids, source_root
    )

    assert prewarmed == source_ids
    assert observed == [
        {"source_id": source_id, "data_root": source_root, "kwargs": {"workspace_root": REPO_ROOT, "timeout_seconds": 900}}
        for source_id in source_ids
    ]
    assert three_source_validator._source_cache_evidence(source_root, prewarmed) == {
        "persistent_source_git_root": str(source_root),
        "prewarmed_source_ids": source_ids,
        "retained_mirror_source_ids": source_ids,
        "temporary_worktrees_cleaned": True,
    }
    assert not (source_root / "worktrees").exists()
    stale_worktree = source_root / "worktrees" / source_ids[0] / "run-stale"
    stale_worktree.mkdir(parents=True)
    with pytest.raises(three_source_validator.ValidationFailure, match="temporary source-cache worktree"):
        three_source_validator._source_cache_evidence(source_root, prewarmed)


def test_three_source_prewarm_reports_git_details_and_cleans_only_new_incomplete_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", "g0dam-work-prompts")
    source_root = tmp_path / "external-source-git"
    mirror_path = source_root / "mirrors" / f"{config.source_id}.git"

    def fail_after_creating_mirror(_config, data_root, **_kwargs):
        (data_root / "mirrors" / f"{config.source_id}.git").mkdir(parents=True, exist_ok=True)
        raise GitSnapshotError("git_unavailable", "https://secret-token@example.test/repo.git timed out")

    monkeypatch.setattr(three_source_validator, "fixed_snapshot", fail_after_creating_mirror)
    with pytest.raises(three_source_validator.ValidationFailure) as new_error:
        three_source_validator._prewarm_source_mirror(config, source_root)
    assert not mirror_path.exists()
    assert "source_id=g0dam-work-prompts" in str(new_error.value)
    assert "git_error_code=git_unavailable" in str(new_error.value)
    assert "https://<redacted>@example.test" in str(new_error.value)
    assert "secret-token" not in str(new_error.value)
    assert "cache_cleanup=new_incomplete_mirror_removed" in str(new_error.value)

    mirror_path.mkdir(parents=True)
    with pytest.raises(three_source_validator.ValidationFailure) as existing_error:
        three_source_validator._prewarm_source_mirror(config, source_root)
    assert mirror_path.is_dir()
    assert "cache_cleanup=existing_mirror_retained" in str(existing_error.value)


def test_three_source_validator_uses_one_persistent_root_for_extract_and_import_without_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    source_root = tmp_path / "source-git-v1"
    prewarm_calls: list[tuple[str, Path]] = []
    extraction_roots: list[Path] = []
    import_roots: list[Path] = []

    def fake_prewarm(config, data_root: Path) -> None:
        prewarm_calls.append((config.source_id, data_root))
        (data_root / "mirrors" / f"{config.source_id}.git").mkdir(parents=True, exist_ok=True)

    def fake_extract_source_twice(**kwargs):
        source_id = kwargs["source_id"]
        extraction_roots.append(kwargs["data_root"])
        return SimpleNamespace(idempotency_key=f"key-{source_id}"), tmp_path / f"package-{source_id}", {"source_id": source_id}

    class FakeStore:
        def ensure_private_bucket(self) -> None:
            return None

        def download_hashes(self, _objects):
            return {}

    def fake_run_inventory(argv, _environment):
        if argv[0] == "migrate":
            return 0, {"status": "migrated"}
        assert argv[0] == "import-package"
        import_roots.append(Path(argv[argv.index("--data-root") + 1]))
        status = "imported" if len(import_roots) <= 3 else "verified_existing"
        return 0, {"status": status, "summary": {"counts": {"source_files": 1}}}

    monkeypatch.setattr(three_source_validator, "EXPECTED_RUNTIME_ROOT", runtime_root)
    monkeypatch.setattr(three_source_validator, "EXPECTED_SOURCE_GIT_ROOT", source_root)
    monkeypatch.setattr(three_source_validator, "_runtime_environment", lambda: {"runtime": "test"})
    monkeypatch.setattr(three_source_validator, "_prewarm_source_mirror", fake_prewarm)
    monkeypatch.setattr(three_source_validator.shared, "_extract_source_twice", fake_extract_source_twice)
    monkeypatch.setattr(three_source_validator, "_assert_expected_source_files", lambda _plans: None)
    monkeypatch.setattr(three_source_validator, "_verify_conardli_failure_and_concurrency", lambda **_kwargs: {"status": "checked"})
    monkeypatch.setattr(three_source_validator.shared, "_write_compose_env", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(three_source_validator.shared, "_runtime_env", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(three_source_validator.shared, "_compose", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(three_source_validator.shared, "_wait_for_services", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(three_source_validator.shared, "_run_inventory", fake_run_inventory)
    monkeypatch.setattr(three_source_validator.shared, "_expected_run_counts", lambda _plan: {"source_files": 1})
    monkeypatch.setattr(three_source_validator.shared, "_expected_global_counts", lambda _plans: {"source_files": 528, "source_cases": 312})
    monkeypatch.setattr(three_source_validator.shared, "_database_counts", lambda _url: {"source_files": 528, "source_cases": 312})
    monkeypatch.setattr(three_source_validator.shared, "_inspect", lambda _env, _key: {"counts": {"source_files": 1}})
    monkeypatch.setattr(three_source_validator.shared, "_object_keys", lambda *_args: [])
    monkeypatch.setattr(three_source_validator.shared, "_assert_extraction_cleanup", lambda *_args: None)
    monkeypatch.setattr(three_source_validator.shared, "_cleanup_compose", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(three_source_validator, "_object_facts", lambda _plans, _bucket: {})
    monkeypatch.setattr(three_source_validator, "_assert_rights_and_publication", lambda *_args: None)
    monkeypatch.setattr(three_source_validator, "S3ObjectStore", lambda _config: FakeStore())
    monkeypatch.setattr(three_source_validator, "_free_loopback_port", lambda: 39001)

    args = SimpleNamespace(
        registry=REPO_ROOT / "config" / "sources-v1.yaml",
        audit=REPO_ROOT / "reports" / "source-audit-v1.json",
        g0dam_source_id="g0dam-work-prompts",
        g0dam_expected_commit="g0dam-commit",
        g0dam_expected_cases=100,
        g0dam_expected_aggregate="g0dam-aggregate",
        joesai_source_id="joesai-commercial-prompts",
        joesai_expected_commit="joesai-commit",
        joesai_expected_cases=50,
        joesai_expected_aggregate="joesai-aggregate",
        conardli_source_id="conardli-gpt-image-2-101",
        conardli_expected_commit="conardli-commit",
        conardli_expected_cases=162,
        conardli_expected_aggregate="conardli-aggregate",
        runs=2,
        failure_injection=True,
        concurrency=True,
    )

    result = three_source_validator.run(args)
    expected_ids = ["g0dam-work-prompts", "joesai-commercial-prompts", "conardli-gpt-image-2-101"]
    assert [source_id for source_id, _root in prewarm_calls] == expected_ids
    assert all(root == source_root for _source_id, root in prewarm_calls)
    assert extraction_roots == [source_root, source_root, source_root]
    assert import_roots == [source_root] * 6
    assert result["fresh_mirror_sources"] == expected_ids
    assert result["source_snapshot_cache"] == {
        "persistent_source_git_root": str(source_root),
        "prewarmed_source_ids": expected_ids,
        "retained_mirror_source_ids": expected_ids,
        "temporary_worktrees_cleaned": True,
    }


def test_package_verifier_rejects_schema_not_explicitly_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_snapshot(monkeypatch, make_joesai_snapshot(tmp_path))
    published = run_joesai_extract(tmp_path, tmp_path / "joesai-output")
    manifest_path = published.output_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "g0dam-extraction-package/v1"
    manifest.pop("manifest_stable_sha256")
    import hashlib

    manifest["manifest_stable_sha256"] = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ExtractionError) as failure:
        verify_published_package(published.output_path, published.idempotency_key)
    assert failure.value.error_code == "published_package_invalid"


@pytest.mark.parametrize("failure_point", ["after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace"])
def test_failure_injection_preserves_previous_published_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    install_fake_snapshot(monkeypatch, make_snapshot(tmp_path))
    output_root = tmp_path / "external-output"
    published = run_extract(tmp_path, output_root)
    before = file_hashes(published.output_path)
    with pytest.raises(ExtractionError) as failure:
        run_extract(tmp_path, output_root, failure_point=failure_point)
    assert failure.value.error_code.startswith("injected_")
    assert file_hashes(published.output_path) == before
    temporary = output_root / ".temporary"
    assert not any(temporary.glob("candidate-*"))


def test_same_key_concurrency_allows_one_writer_and_fails_fast_second(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_snapshot(monkeypatch, make_snapshot(tmp_path))
    output_root = tmp_path / "external-output"
    holder: dict[str, object] = {}

    def first_run() -> None:
        try:
            holder["result"] = run_extract(tmp_path, output_root, lock_hold_seconds=0.5)
        except BaseException as exc:  # assertion carries the original test failure to the main thread
            holder["error"] = exc

    thread = threading.Thread(target=first_run)
    thread.start()
    deadline = time.monotonic() + 3
    while not list((output_root / ".locks").glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.01)
    with pytest.raises(ExtractionError) as second:
        run_extract(tmp_path, output_root)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert "error" not in holder
    assert second.value.error_code == "run_locked"
    assert getattr(holder["result"], "status") == "published"


def test_joesai_failure_and_concurrency_preserve_previous_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_snapshot(monkeypatch, make_joesai_snapshot(tmp_path))
    output_root = tmp_path / "joesai-output"
    published = run_joesai_extract(tmp_path, output_root)
    before = file_hashes(published.output_path)
    for failure_point in ("after_adapter", "after_assets", "before_manifest", "before_publish", "before_replace"):
        with pytest.raises(ExtractionError) as failure:
            run_joesai_extract(tmp_path, output_root, failure_point=failure_point)
        assert failure.value.error_code.startswith("injected_")
        assert file_hashes(published.output_path) == before
    holder: dict[str, object] = {}

    def first_run() -> None:
        try:
            holder["result"] = run_joesai_extract(tmp_path, tmp_path / "joesai-concurrent-output", lock_hold_seconds=0.5)
        except BaseException as exc:
            holder["error"] = exc

    thread = threading.Thread(target=first_run)
    thread.start()
    deadline = time.monotonic() + 3
    lock_root = tmp_path / "joesai-concurrent-output" / ".locks"
    while not list(lock_root.glob("*.lock")) and time.monotonic() < deadline:
        time.sleep(0.01)
    with pytest.raises(ExtractionError) as second:
        run_joesai_extract(tmp_path, tmp_path / "joesai-concurrent-output")
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert "error" not in holder
    assert second.value.error_code == "run_locked"
    assert getattr(holder["result"], "status") == "published"
