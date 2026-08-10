"""Fresh local end-to-end evidence for the TASK-0016 incremental-sync boundary.

The harness creates only synthetic, loopback Git/Compose state below the task
runtime.  It never fetches a public repository or executes source code from a
snapshot.  Static registry and audit files are read-only inputs; candidate
authority is created by the production sync pipeline outside the workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import quote, urlparse

import psycopg
from botocore.config import Config
import boto3


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from content.database import ContentDatabase, ContentDatabaseSettings, RightsReview
from ingestion.registry import SourceConfig, load_source_config
from inventory.database import DatabaseConfig, InventoryDatabase
from inventory.object_store import ObjectFact, ObjectStoreConfig, S3ObjectStore
from sync.database import SyncDatabase, SyncDatabaseSettings
from sync.pipeline import SyncPipelineError, SyncSettings, run_source


EXPECTED_RUNTIME_ROOT = Path(r"C:/Users/admin/.codex/runtime/image2/TASK-0016")
SOURCE_IDS = (
    "g0dam-work-prompts",
    "joesai-commercial-prompts",
    "conardli-gpt-image-2-101",
)


class ValidationFailure(RuntimeError):
    """A stable, fail-closed live-validation conclusion."""


def _must_be_external(path: Path, workspace: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if resolved == workspace or workspace in resolved.parents:
        raise ValidationFailure(f"{label} must be outside the workspace")
    return resolved


def _runtime_environment() -> dict[str, str]:
    workspace = REPO_ROOT.resolve()
    expected = {
        "UV_PROJECT_ENVIRONMENT": EXPECTED_RUNTIME_ROOT / "venv",
        "UV_CACHE_DIR": EXPECTED_RUNTIME_ROOT / "uv-cache",
        "TMP": EXPECTED_RUNTIME_ROOT / "tmp",
        "TEMP": EXPECTED_RUNTIME_ROOT / "tmp",
    }
    observed: dict[str, str] = {}
    for name, required in expected.items():
        raw = os.environ.get(name)
        if not raw:
            raise ValidationFailure(f"{name} is required")
        actual = _must_be_external(Path(raw), workspace, name)
        if actual != required.resolve(strict=False):
            raise ValidationFailure(f"{name} must use the TASK-0016 external runtime path")
        observed[name] = str(actual)
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValidationFailure("PYTHONDONTWRITEBYTECODE must equal 1")
    return observed


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _token(length: int = 24) -> str:
    return secrets.token_urlsafe(length).replace("-", "a").replace("_", "b")


def _sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _png(label: str) -> bytes:
    """Create a valid-enough image payload above the production size floor."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"tEXt", b"Description\x00" + label.encode("utf-8") + (b"-incremental-sync" * 48))
        + chunk(b"IDAT", zlib.compress(b"\x00" + digest[:3]))
        + chunk(b"IEND", b"")
    )


def _webp(label: str) -> bytes:
    # The strict ConardLi parser requires the thumbnail to be a nonempty regular
    # file; it is not an imported asset.  Keep an unambiguous WebP-shaped byte
    # payload without storing source images in the workspace.
    payload = (label.encode("utf-8") + b"-thumbnail") * 24
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + b"WEBP" + payload


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _safe_remove(path: Path, *, external_root: Path) -> None:
    resolved = path.resolve(strict=False)
    root = external_root.resolve(strict=False)
    if resolved == root or root not in resolved.parents:
        raise ValidationFailure("cleanup target is outside the owned runtime root")
    if path.exists():
        def onerror(function: object, item: str, exception: object) -> None:
            try:
                os.chmod(item, 0o700)
                if callable(function):
                    function(item)  # type: ignore[misc]
            except OSError:
                raise

        shutil.rmtree(path, onerror=onerror)


def _run_process(command: list[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None, timeout: int = 180) -> str:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        completed = subprocess.run(command, cwd=str(cwd) if cwd else None, env=merged, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationFailure("owned local process did not complete") from exc
    if completed.returncode != 0:
        raise ValidationFailure("owned local process failed")
    return completed.stdout.strip()


def _git(command: list[str], *, cwd: Path | None, hooks: Path, timeout: int = 180) -> str:
    hooks.mkdir(parents=True, exist_ok=True)
    return _run_process(
        [
            "git",
            "-c",
            f"core.hooksPath={hooks}",
            "-c",
            "core.autocrlf=false",
            "-c",
            "protocol.file.allow=always",
            *command,
        ],
        cwd=cwd,
        env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"},
        timeout=timeout,
    )


def _repository_relative_url(config: SourceConfig) -> tuple[str, ...]:
    parsed = urlparse(config.repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValidationFailure("registered pilot repository URL is not a GitHub HTTPS URL")
    parts = tuple(part for part in parsed.path.split("/") if part)
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise ValidationFailure("registered pilot repository path is unsafe")
    return parts


def _initialize_remote(worktree: Path, remote: Path, *, hooks: Path, message: str) -> str:
    _git(["init", "-b", "main"], cwd=worktree, hooks=hooks)
    _git(["config", "user.name", "TASK-0016 synthetic validator"], cwd=worktree, hooks=hooks)
    _git(["config", "user.email", "task0016@example.invalid"], cwd=worktree, hooks=hooks)
    _git(["add", "--all"], cwd=worktree, hooks=hooks)
    _git(["commit", "-m", message], cwd=worktree, hooks=hooks)
    remote.parent.mkdir(parents=True, exist_ok=True)
    _git(["init", "--bare", str(remote)], cwd=worktree, hooks=hooks)
    _git(["remote", "add", "origin", remote.as_uri()], cwd=worktree, hooks=hooks)
    _git(["push", "--set-upstream", "origin", "main"], cwd=worktree, hooks=hooks)
    _git(["--git-dir", str(remote), "update-server-info"], cwd=None, hooks=hooks)
    return _git(["rev-parse", "HEAD"], cwd=worktree, hooks=hooks)


def _commit_and_push(worktree: Path, remote: Path, *, hooks: Path, message: str, force: bool = False) -> str:
    _git(["add", "--all"], cwd=worktree, hooks=hooks)
    _git(["commit", "-m", message], cwd=worktree, hooks=hooks)
    candidate = _git(["rev-parse", "HEAD"], cwd=worktree, hooks=hooks)
    push = ["push"]
    if force:
        push.append("--force")
    push.extend(["origin", "HEAD:main"])
    _git(push, cwd=worktree, hooks=hooks)
    _git(["--git-dir", str(remote), "update-server-info"], cwd=None, hooks=hooks)
    return candidate


def _reset_worktree(worktree: Path, revision_sha: str, *, hooks: Path) -> None:
    _git(["checkout", "--force", "main"], cwd=worktree, hooks=hooks)
    _git(["reset", "--hard", revision_sha], cwd=worktree, hooks=hooks)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib hook name
        return


@contextmanager
def _git_http_server(root: Path) -> Iterator[str]:
    port = _free_loopback_port()
    handler = partial(_QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, name="task0016-synthetic-git", daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=15)
        if thread.is_alive():
            raise ValidationFailure("owned synthetic Git HTTP server did not stop")


def _write_git_rewrite(data_root: Path, http_base: str) -> None:
    config = data_root / "git-global.config"
    config.parent.mkdir(parents=True, exist_ok=True)
    _write_text(config, f'[url "{http_base}"]\n\tinsteadOf = https://github.com/\n')


def _g0dam_tree(root: Path, *, revision_label: str = "baseline") -> None:
    prompts: list[dict[str, Any]] = []
    for index in range(1, 51):
        image_path = f"images/case-{index:03d}.png"
        (root / image_path).parent.mkdir(parents=True, exist_ok=True)
        (root / image_path).write_bytes(_png("g0dam-shared-base"))
        prompts.append(
            {
                "id": f"case-{index:03d}",
                "title": f"Synthetic catalog case {index}",
                "prompt": {
                    "en": (
                        f"{revision_label} synthetic studio prompt {index}: create a precisely composed product scene "
                        "with measured lighting, a clean neutral background, deliberate typography-free framing, and "
                        "repeatable visual constraints for controlled evaluation."
                    ),
                    "zh": f"合成目录案例 {index}",
                },
                "category": {"slug": "synthetic", "label": "Synthetic"},
                "image_path": image_path,
                "tags": ["synthetic", "catalog"],
            }
        )
    _write_json(root / "data" / "prompts.json", {"count": len(prompts), "model_target": "GPT Image 2", "prompts": prompts})


def _joesai_markdown(title: str, *, index: int, revision_label: str) -> str:
    english = (
        f"{revision_label} synthetic commercial prompt {index}: create a polished catalog image with restrained "
        "composition, an accessible visual hierarchy, controlled studio lighting, faithful material detail, and "
        "a clear product-focused scene that can be evaluated without inferred context."
    )
    return (
        f"# {title}\n\n"
        "## Best For\n"
        "Controlled catalog and accessibility review.\n\n"
        "## Prompt (EN)\n"
        "```text\n"
        f"{english}\n"
        "```\n\n"
        "## 提示词（中文）\n"
        "```text\n"
        f"合成商业提示词 {index}，用于受控目录验证。\n"
        "```\n"
    )


def _joesai_tree(root: Path, *, revision_label: str = "baseline") -> None:
    manifest: list[dict[str, Any]] = []
    for index in range(1, 51):
        slug = f"case-{index:03d}"
        title = f"Synthetic Commercial Case {index}"
        image = f"assets/examples/{slug}.png"
        manifest.append(
            {
                "slug": slug,
                "category": "synthetic",
                "title": title,
                "title_zh": f"合成商业案例 {index}",
                "use_case": "controlled catalog validation",
                "asset_type": "product image",
                "languages": ["en", "zh-CN"],
                "featured": index == 1,
                "example_image": image,
            }
        )
        _write_text(root / "prompts" / "synthetic" / f"{slug}.md", _joesai_markdown(title, index=index, revision_label=revision_label))
        (root / image).parent.mkdir(parents=True, exist_ok=True)
        (root / image).write_bytes(_png("joesai-shared-base"))
    _write_json(root / "data" / "prompts.json", manifest)
    _write_text(root / "prompts" / "README.md", "Synthetic validator manifest pages.\n")


def _conardli_tree(root: Path, *, revision_label: str = "baseline") -> None:
    category = "synthetic"
    template_name = "catalog"
    template_key = f"{category}/{template_name}"
    cases: list[dict[str, Any]] = []
    mapping_cases: list[dict[str, Any]] = []
    for index in range(1, 51):
        native_id = f"{template_key}/{index}"
        prompt = (
            f"{revision_label} synthetic compiled prompt {index}: make a carefully bounded visual artifact with "
            "clear subject hierarchy, stable lighting rules, explicit composition constraints, and no inferred rights claim."
        )
        prompt_path = f"{native_id}.txt"
        case = {
            "id": native_id,
            "category": category,
            "category_label": "合成",
            "category_accent": "#2458A6",
            "template_key": template_key,
            "template_label": "Catalog",
            "idx": index,
            "title": f"Synthetic compiled case {index}",
            "brief": f"Controlled compiled gallery case {index}",
            "format": "txt",
            "prompt_path": prompt_path,
            "prompt_url": f"/case/{prompt_path}",
            "image_url": f"/case/{native_id}.png",
            "thumb_url": f"/case/{native_id}-thumb.webp",
            "has_image": True,
            "prompt_content": prompt,
        }
        cases.append(case)
        mapping_cases.append(
            {"idx": index, "title": case["title"], "brief": case["brief"], "format": "txt", "file": prompt_path}
        )
        _write_text(root / "public" / "case" / prompt_path, prompt)
        primary = root / "public" / "case" / f"{native_id}.png"
        primary.parent.mkdir(parents=True, exist_ok=True)
        primary.write_bytes(_png("conardli-shared-base"))
        thumbnail = root / "public" / "case" / f"{native_id}-thumb.webp"
        thumbnail.write_bytes(_webp(f"conardli-{index}"))
    manifest = {
        "generated_at": "2026-01-01T00:00:00Z",
        "summary": {"templates": 1, "cases": len(cases)},
        "categories": {
            category: {
                "accent": "#2458A6",
                "cn": "合成",
                "key": category,
                "label": "Synthetic",
                "ready": len(cases),
                "templates": [template_key],
                "total": len(cases),
            }
        },
        "templates": {
            template_key: {
                "cases_count": len(cases),
                "category": category,
                "content": None,
                "description": None,
                "key": template_key,
                "label": "Catalog",
                "md_path": "prompts/synthetic/catalog.md",
                "name": template_name,
            }
        },
        "cases": cases,
    }
    _write_json(root / "src" / "data" / "cases.json", manifest)
    _write_json(
        root / "public" / "case" / "_mapping.json",
        {
            "summary": manifest["summary"],
            "items": [
                {
                    "category": category,
                    "template_basename": template_name,
                    "template_md": "prompts/synthetic/catalog.md",
                    "prompt_dir": template_key,
                    "source_md": "synthetic/catalog.md",
                    "cases": mapping_cases,
                }
            ],
        },
    )
    _write_text(root / "public" / "case" / "INDEX.md", "Synthetic compiled case index.\n")


def _mutate_source(worktree: Path, source_id: str, *, label: str, remove_one: bool = False) -> None:
    if source_id == "g0dam-work-prompts":
        path = worktree / "data" / "prompts.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        prompts = payload["prompts"]
        if remove_one:
            removed = prompts.pop()
            (worktree / str(removed["image_path"])).unlink()
        else:
            prompts[0]["prompt"]["en"] += f" Revision marker {label} changes semantic source evidence."
            (worktree / str(prompts[0]["image_path"])).write_bytes(_png(f"g0dam-{label}"))
        payload["count"] = len(prompts)
        _write_json(path, payload)
        return
    if source_id == "joesai-commercial-prompts":
        path = worktree / "prompts" / "synthetic" / "case-001.md"
        page = path.read_text(encoding="utf-8")
        _write_text(path, page.replace("controlled evaluation.", f"controlled evaluation with revision {label}."))
        (worktree / "assets" / "examples" / "case-001.png").write_bytes(_png(f"joesai-{label}"))
        return
    if source_id == "conardli-gpt-image-2-101":
        path = worktree / "src" / "data" / "cases.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload["cases"]
        if remove_one:
            removed = cases.pop()
            native_id = str(removed["id"])
            for relative in (str(removed["prompt_path"]), f"{native_id}.png", f"{native_id}-thumb.webp"):
                (worktree / "public" / "case" / relative).unlink()
            payload["summary"]["cases"] = len(cases)
            payload["categories"]["synthetic"]["ready"] = len(cases)
            payload["categories"]["synthetic"]["total"] = len(cases)
            payload["templates"]["synthetic/catalog"]["cases_count"] = len(cases)
            mapping_path = worktree / "public" / "case" / "_mapping.json"
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            mapping["summary"] = payload["summary"]
            mapping["items"][0]["cases"].pop()
            _write_json(mapping_path, mapping)
        else:
            case = cases[0]
            prompt = str(case["prompt_content"]) + f" Revision marker {label} changes semantic source evidence."
            case["prompt_content"] = prompt
            _write_text(worktree / "public" / "case" / str(case["prompt_path"]), prompt)
            (worktree / "public" / "case" / f"{case['id']}.png").write_bytes(_png(f"conardli-{label}"))
        _write_json(path, payload)
        return
    raise ValidationFailure("unexpected synthetic source id")


def _compose(command: list[str], *, env_file: Path, project: str, check: bool = True, timeout: int = 420) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", "compose", "-f", str(REPO_ROOT / "compose.yaml"), "--env-file", str(env_file), "-p", project, *command],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise ValidationFailure("isolated Compose operation failed")
    return completed


def _write_compose_env(path: Path, values: Mapping[str, str]) -> None:
    required = {
        "INVENTORY_POSTGRES_DB",
        "INVENTORY_POSTGRES_USER",
        "INVENTORY_POSTGRES_PASSWORD",
        "INVENTORY_POSTGRES_PORT",
        "INVENTORY_S3_ACCESS_KEY",
        "INVENTORY_S3_SECRET_KEY",
        "INVENTORY_S3_PORT",
    }
    if set(values) != required:
        raise ValidationFailure("isolated Compose environment differs from the task contract")
    _write_text(path, "".join(f"{key}={values[key]}\n" for key in sorted(values)))


def _wait_postgres(database_url: str) -> None:
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=3) as connection:
                connection.execute("SELECT 1").fetchone()
            return
        except psycopg.Error:
            time.sleep(1)
    raise ValidationFailure("isolated PostgreSQL service did not become ready")


def _s3_client(endpoint: str, access_key: str, secret_key: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2, "mode": "standard"}, s3={"addressing_style": "path"}),
    )


def _wait_minio(endpoint: str, access_key: str, secret_key: str) -> None:
    client = _s3_client(endpoint, access_key, secret_key)
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            client.list_buckets()
            return
        except Exception:  # Boto's exception hierarchy varies by installed version.
            time.sleep(1)
    raise ValidationFailure("isolated MinIO service did not become ready")


def _assert_no_project_orphans(project: str) -> None:
    containers = _run_process(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"], timeout=60)
    volumes = _run_process(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"], timeout=60)
    if containers or volumes:
        raise ValidationFailure("isolated Compose resources remain after cleanup")


def _current_version(database_url: str) -> int:
    with psycopg.connect(database_url) as connection:
        row = connection.execute("SELECT publication_version_id FROM content.publication_current WHERE singleton=true").fetchone()
    if not row:
        raise ValidationFailure("current publication pointer is missing")
    return int(row[0])


def _generation_ids(database_url: str, source_id: str, revision_sha: str) -> list[int]:
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            """
            SELECT generation.generation_example_row_id
            FROM inventory.generation_examples AS generation
            JOIN inventory.source_case_versions AS version ON version.source_case_version_id=generation.source_case_version_id
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id=version.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
            WHERE project.source_id=%s AND revision.revision_sha=%s
            ORDER BY generation.generation_example_row_id
            """,
            (source_id, revision_sha),
        ).fetchall()
    return [int(row[0]) for row in rows]


def _rights_count(database_url: str, source_id: str, revision_sha: str) -> int:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT count(*)
            FROM content.rights_review_events AS review
            JOIN inventory.generation_examples AS generation ON generation.generation_example_row_id=review.generation_example_row_id
            JOIN inventory.source_case_versions AS version ON version.source_case_version_id=generation.source_case_version_id
            JOIN inventory.source_revisions AS revision ON revision.source_revision_id=version.source_revision_id
            JOIN inventory.source_projects AS project ON project.source_project_id=revision.source_project_id
            WHERE project.source_id=%s AND revision.revision_sha=%s
            """,
            (source_id, revision_sha),
        ).fetchone()
    return int(row[0]) if row else 0


def _record_synthetic_reviews(content: ContentDatabase, generation_ids: Sequence[int]) -> None:
    for generation_id in generation_ids:
        content.record_rights_review(
            RightsReview(
                generation_example_row_id=generation_id,
                repository_license="synthetic-test-license",
                prompt_rights="approved",
                asset_rights="approved",
                author="synthetic-test-author",
                original_url="https://example.invalid/synthetic-source",
                evidence_url="https://example.invalid/synthetic-evidence",
                reviewer="synthetic-test-reviewer",
                reviewed_at=datetime.now(timezone.utc),
                display_policy="mirror_allowed",
                review_note="Isolated validator-only explicit review event.",
            )
        )


def _all_object_facts(database_url: str) -> dict[str, ObjectFact]:
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            "SELECT content_sha256, object_key, object_bucket, byte_size, media_type, integrity_state FROM inventory.assets ORDER BY content_sha256"
        ).fetchall()
    facts: dict[str, ObjectFact] = {}
    for content_sha256, object_key, bucket, byte_size, media_type, state in rows:
        facts[str(content_sha256)] = ObjectFact(
            content_sha256=str(content_sha256),
            object_key=str(object_key),
            bucket=str(bucket),
            byte_size=int(byte_size),
            media_type=str(media_type),
            state=str(state),
        )
    return facts


def _assert_completion_atomicity(database_url: str, sync_db: SyncDatabase, source_id: str, candidate_sha: str) -> dict[str, Any]:
    run = sync_db.get_run(source_id, candidate_sha)
    if not run or run.get("state") != "completed" or not isinstance(run.get("publication_version_id"), int):
        raise ValidationFailure("successful sync run did not reach completed state")
    result_document = run.get("result_document")
    if not isinstance(result_document, dict) or not isinstance(result_document.get("quality_gate"), dict) or not isinstance(
        result_document.get("authority"), dict
    ) or not isinstance(result_document.get("retained_ref"), str):
        raise ValidationFailure("atomic sync completion discarded candidate authority or quality evidence")
    version_id = int(run["publication_version_id"])
    if _current_version(database_url) != version_id:
        raise ValidationFailure("completed sync run is not the current publication pointer")
    with psycopg.connect(database_url) as connection:
        outbox = connection.execute(
            "SELECT count(*) FROM content.publication_outbox WHERE publication_version_id=%s AND event_type='publication_activated'",
            (version_id,),
        ).fetchone()
        selected = connection.execute(
            "SELECT count(*) FROM content.publication_revision_selections WHERE publication_version_id=%s", (version_id,)
        ).fetchone()
        publication = connection.execute(
            "SELECT included_count, excluded_count FROM content.publication_versions WHERE publication_version_id=%s", (version_id,)
        ).fetchone()
    if int(outbox[0]) != 1 or int(selected[0]) != len(SOURCE_IDS) or not publication:
        raise ValidationFailure("publication pointer, outbox, and explicit revision selection are not closed atomically")
    return {"publication_version_id": version_id, "included_count": int(publication[0]), "excluded_count": int(publication[1])}


def _expect_sync_failure(action: Any, expected_code: str) -> None:
    try:
        action()
    except SyncPipelineError as exc:
        if exc.error_code != expected_code:
            raise ValidationFailure("injected sync failure produced the wrong stable code") from exc
        return
    raise ValidationFailure("injected sync failure unexpectedly completed")


def _run_sync_cli(settings: SyncSettings, source_id: str, command: str) -> dict[str, Any]:
    """Exercise the public one-source CLI without exposing its environment."""

    if command not in {"run-source", "inspect-source"}:
        raise ValidationFailure("validator selected an unsupported sync CLI command")
    environment = dict(os.environ)
    environment.update(
        {
            "SYNC_DATABASE_URL": settings.database_url,
            "SYNC_S3_ENDPOINT_URL": settings.s3_endpoint_url,
            "SYNC_S3_BUCKET": settings.s3_bucket,
            "SYNC_S3_ACCESS_KEY_ID": settings.s3_access_key_id,
            "SYNC_S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
            "SYNC_GIT_DATA_ROOT": str(settings.git_data_root),
            "SYNC_PACKAGE_ROOT": str(settings.package_root),
            "SYNC_EVIDENCE_ROOT": str(settings.evidence_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "sync", command, "--source-id", source_id, "--json"],
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise ValidationFailure("public sync CLI did not return a successful structured result")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationFailure("public sync CLI did not emit JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationFailure("public sync CLI result is malformed")
    sensitive = (
        settings.database_url,
        settings.s3_endpoint_url,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
    )
    if any(secret in completed.stdout or secret in completed.stderr for secret in sensitive):
        raise ValidationFailure("public sync CLI leaked a runtime secret")
    return payload


def _assert_no_worktrees(data_root: Path) -> None:
    worktrees = data_root / "worktrees"
    retained = [
        path
        for path in worktrees.rglob("*")
        if path.name.startswith(("candidate-", "run-")) or path.is_file()
    ] if worktrees.exists() else []
    if retained:
        raise ValidationFailure("temporary source snapshot worktree remains")


def run() -> dict[str, Any]:
    environment = _runtime_environment()
    runtime_root = _must_be_external(EXPECTED_RUNTIME_ROOT, REPO_ROOT.resolve(), "TASK-0016 runtime root")
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="incremental-sync-live-", dir=runtime_root))
    project = f"task0016{uuid.uuid4().hex[:12]}"
    env_file = run_root / "compose.env"
    compose_started = False
    cleanup_complete = False
    http_server_started = False
    try:
        configs = {source_id: load_source_config(REPO_ROOT / "config" / "sources-v1.yaml", source_id) for source_id in SOURCE_IDS}
        hooks = run_root / "empty-hooks"
        source_worktrees = run_root / "synthetic-sources"
        server_root = run_root / "synthetic-git-remote"
        worktrees: dict[str, Path] = {}
        remotes: dict[str, Path] = {}
        builders = {
            "g0dam-work-prompts": _g0dam_tree,
            "joesai-commercial-prompts": _joesai_tree,
            "conardli-gpt-image-2-101": _conardli_tree,
        }
        baselines: dict[str, str] = {}
        for source_id in SOURCE_IDS:
            worktree = source_worktrees / source_id
            builders[source_id](worktree)
            remote = server_root.joinpath(*_repository_relative_url(configs[source_id]))
            baselines[source_id] = _initialize_remote(worktree, remote, hooks=hooks, message="synthetic baseline")
            worktrees[source_id] = worktree
            remotes[source_id] = remote

        with _git_http_server(server_root) as http_base:
            http_server_started = True
            git_root = run_root / "git-cache"
            _write_git_rewrite(git_root, http_base)
            postgres_port = _free_loopback_port()
            s3_port = _free_loopback_port()
            postgres_user = "u" + _token(12)
            postgres_password = _token(24)
            s3_access_key = "a" + _token(12)
            s3_secret_key = _token(24)
            compose_values = {
                "INVENTORY_POSTGRES_DB": "incrementalsync",
                "INVENTORY_POSTGRES_USER": postgres_user,
                "INVENTORY_POSTGRES_PASSWORD": postgres_password,
                "INVENTORY_POSTGRES_PORT": str(postgres_port),
                "INVENTORY_S3_ACCESS_KEY": s3_access_key,
                "INVENTORY_S3_SECRET_KEY": s3_secret_key,
                "INVENTORY_S3_PORT": str(s3_port),
            }
            _write_compose_env(env_file, compose_values)
            database_url = (
                f"postgresql://{quote(postgres_user)}:{quote(postgres_password)}@127.0.0.1:{postgres_port}/incrementalsync"
            )
            endpoint = f"http://127.0.0.1:{s3_port}"
            bucket = "incremental-sync-private"
            _assert_no_project_orphans(project)
            compose_started = True
            _compose(["up", "-d", "postgres", "minio"], env_file=env_file, project=project, timeout=600)
            _wait_postgres(database_url)
            _wait_minio(endpoint, s3_access_key, s3_secret_key)
            migrations = InventoryDatabase(DatabaseConfig(database_url)).apply_migrations(REPO_ROOT / "migrations")
            if [entry["version"] for entry in migrations] != [
                "0001_internal_inventory",
                "0002_inventory_security_integrity",
                "0003_content_core_publication",
                "0004_incremental_sync",
                "0005_rights_review_queue_and_public_case_v2",
            ]:
                raise ValidationFailure("migration sequence does not close through incremental sync")
            second_migrations = InventoryDatabase(DatabaseConfig(database_url)).apply_migrations(REPO_ROOT / "migrations")
            if any(entry["status"] != "verified_existing" for entry in second_migrations):
                raise ValidationFailure("incremental sync migration replay is not idempotent")

            settings = SyncSettings(
                database_url=database_url,
                s3_endpoint_url=endpoint,
                s3_bucket=bucket,
                s3_access_key_id=s3_access_key,
                s3_secret_access_key=s3_secret_key,
                git_data_root=git_root,
                package_root=run_root / "packages",
                evidence_root=run_root / "authority-evidence",
            )
            sync_db = SyncDatabase(SyncDatabaseSettings(database_url))
            content = ContentDatabase(ContentDatabaseSettings(database_url))
            sync_db.assert_migrated()
            content.assert_migrated()

            baseline_results: dict[str, dict[str, Any]] = {}
            for source_id in SOURCE_IDS:
                result = run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                )
                if result.status != "completed" or result.candidate_revision_sha != baselines[source_id] or result.diff["counts"]["added"] != 50:
                    raise ValidationFailure("synthetic baseline did not complete a full source chain")
                baseline_results[source_id] = result.as_json()

            base_objects = _all_object_facts(database_url)
            if len(base_objects) != len(SOURCE_IDS):
                raise ValidationFailure("baseline content-addressed object reuse did not close")

            first_updates: dict[str, str] = {}
            first_update_results: dict[str, dict[str, Any]] = {}
            for source_id in SOURCE_IDS:
                _mutate_source(worktrees[source_id], source_id, label="first")
                first_updates[source_id] = _commit_and_push(
                    worktrees[source_id], remotes[source_id], hooks=hooks, message="synthetic first update"
                )
                result = run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                )
                if result.status != "completed" or result.diff["counts"] != {"added": 0, "modified": 1, "removed": 0, "unchanged": 49}:
                    raise ValidationFailure("synthetic fast-forward update did not create the expected full-reparse diff")
                if not result.publication or not isinstance(result.publication.get("retained_ref"), str):
                    raise ValidationFailure("successful candidate did not create a retained ref")
                first_update_results[source_id] = result.as_json()

            current_objects = _all_object_facts(database_url)
            if set(base_objects) - set(current_objects) or len(current_objects) != len(SOURCE_IDS) * 2:
                raise ValidationFailure("existing objects changed or candidate objects were not content-addressed once")
            object_store = S3ObjectStore(ObjectStoreConfig(endpoint, bucket, s3_access_key, s3_secret_key))
            downloaded = object_store.download_hashes(current_objects)
            if set(downloaded.values()) != set(current_objects):
                raise ValidationFailure("all current content-addressed objects were not download-hash verified")

            no_change: dict[str, str] = {}
            for source_id in SOURCE_IDS:
                result = run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                )
                if result.status != "no_change" or result.candidate_revision_sha != first_updates[source_id]:
                    raise ValidationFailure("unchanged branch did not return no_change")
                no_change[source_id] = result.status

            cli_no_change = _run_sync_cli(settings, "joesai-commercial-prompts", "run-source")
            cli_inspect = _run_sync_cli(settings, "joesai-commercial-prompts", "inspect-source")
            if cli_no_change.get("status") != "no_change" or cli_inspect.get("status") != "inspected":
                raise ValidationFailure("public one-source sync CLI did not preserve no-change or inspection semantics")

            # Continue only one source through failure, review, recovery, and
            # publication scenarios; all three have already completed baseline
            # and fast-forward chains above.
            source_id = "g0dam-work-prompts"
            _mutate_source(worktrees[source_id], source_id, label="reviewed")
            reviewed_sha = _commit_and_push(worktrees[source_id], remotes[source_id], hooks=hooks, message="reviewable update")
            before_current = _current_version(database_url)
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                    failure_point="after_import",
                ),
                "injected_after_import",
            )
            if _current_version(database_url) != before_current:
                raise ValidationFailure("post-import failure changed the current publication")
            reviewed_generation_ids = _generation_ids(database_url, source_id, reviewed_sha)
            if len(reviewed_generation_ids) != 50 or _rights_count(database_url, source_id, first_updates[source_id]) != 0:
                raise ValidationFailure("new revision incorrectly inherited rights or did not close inventory")
            _record_synthetic_reviews(content, reviewed_generation_ids)
            recovered = run_source(
                registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                source_id=source_id,
                settings=settings,
            )
            if recovered.status != "completed":
                raise ValidationFailure("same-candidate retry did not complete after explicit synthetic reviews")
            recovered_atomic = _assert_completion_atomicity(database_url, sync_db, source_id, reviewed_sha)
            if recovered_atomic["included_count"] != 50 or _rights_count(database_url, source_id, reviewed_sha) != 50:
                raise ValidationFailure("reviewed candidate did not produce exactly its explicit public entries")

            _mutate_source(worktrees[source_id], source_id, label="unreviewed")
            unreviewed_sha = _commit_and_push(worktrees[source_id], remotes[source_id], hooks=hooks, message="unreviewed update")
            public_before_loss = _current_version(database_url)
            public_loss = run_source(
                registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                source_id=source_id,
                settings=settings,
            )
            if public_loss.status != "review_required" or public_loss.reason_code != "public_loss" or _current_version(database_url) != public_before_loss:
                raise ValidationFailure("unreviewed candidate did not fail closed for public loss")
            if _rights_count(database_url, source_id, unreviewed_sha) != 0:
                raise ValidationFailure("rights were inherited into an unreviewed revision")

            _mutate_source(worktrees[source_id], source_id, label="removed", remove_one=True)
            removed_sha = _commit_and_push(worktrees[source_id], remotes[source_id], hooks=hooks, message="removed case update")
            removed = run_source(
                registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                source_id=source_id,
                settings=settings,
            )
            if removed.status != "review_required" or not {"case_count_decrease", "removed_cases"}.issubset(set(removed.quality_gate["reasons"])):
                raise ValidationFailure("removed case did not trigger the zero-decrease quality gate")
            with psycopg.connect(database_url) as connection:
                event = connection.execute(
                    "SELECT count(*) FROM sync.case_tombstone_events WHERE source_id=%s AND candidate_revision_sha=%s AND event_type='removed'",
                    (source_id, removed_sha),
                ).fetchone()
            if int(event[0]) != 1 or _current_version(database_url) != public_before_loss:
                raise ValidationFailure("removed case did not retain immutable tombstone evidence safely")

            _reset_worktree(worktrees[source_id], reviewed_sha, hooks=hooks)
            _mutate_source(worktrees[source_id], source_id, label="nonfast")
            nonfast_sha = _commit_and_push(
                worktrees[source_id], remotes[source_id], hooks=hooks, message="non-fast-forward update", force=True
            )
            nonfast = run_source(
                registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                source_id=source_id,
                settings=settings,
            )
            if nonfast.status != "review_required" or nonfast.reason_code != "non_fast_forward" or _current_version(database_url) != public_before_loss:
                raise ValidationFailure("non-fast-forward source change did not remain review-required")

            _write_git_rewrite(git_root, "http://127.0.0.1:1/")
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                ),
                "git_failed",
            )
            _write_git_rewrite(git_root, http_base)
            if _current_version(database_url) != public_before_loss:
                raise ValidationFailure("Git failure changed the current publication")

            _reset_worktree(worktrees[source_id], unreviewed_sha, hooks=hooks)
            # Build a fast-forward candidate from the unreviewed revision that
            # restores the current public semantic set.  That lets the
            # activation-failure injection reach the pointer/outbox transaction
            # rather than correctly stopping earlier at the public-loss gate.
            _git(
                ["checkout", reviewed_sha, "--", "data/prompts.json", "images/case-001.png"],
                cwd=worktrees[source_id],
                hooks=hooks,
            )
            _write_text(worktrees[source_id] / "TASK-0016-synthetic-note.txt", "non-semantic local Git candidate marker\n")
            recoverable_sha = _commit_and_push(
                worktrees[source_id], remotes[source_id], hooks=hooks, message="recoverable fast-forward", force=True
            )
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                    failure_point="import",
                ),
                "injected_after_first_object",
            )
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                    failure_point="build",
                ),
                "injected_publication_build_failure",
            )
            if _current_version(database_url) != public_before_loss:
                raise ValidationFailure("import or build failure changed the current publication")
            recoverable_generation_ids = _generation_ids(database_url, source_id, recoverable_sha)
            if len(recoverable_generation_ids) != 50:
                raise ValidationFailure("recoverable candidate inventory did not remain reusable")
            _record_synthetic_reviews(content, recoverable_generation_ids)
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                    failure_point="activation_completion",
                ),
                "injected_sync_completion_failure",
            )
            if _current_version(database_url) != public_before_loss:
                raise ValidationFailure("atomic activation failure changed the current publication")
            retry_after_activation = run_source(
                registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                source_id=source_id,
                settings=settings,
            )
            if retry_after_activation.status != "completed":
                raise ValidationFailure("activation retry did not complete")
            activation_atomic = _assert_completion_atomicity(database_url, sync_db, source_id, recoverable_sha)

            _mutate_source(worktrees[source_id], source_id, label="concurrent")
            concurrent_sha = _commit_and_push(worktrees[source_id], remotes[source_id], hooks=hooks, message="concurrency candidate")
            primary_result: list[Any] = []
            primary_error: list[BaseException] = []

            def primary_writer() -> None:
                try:
                    primary_result.append(
                        run_source(
                            registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                            audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                            source_id=source_id,
                            settings=settings,
                            lock_hold_seconds=2.0,
                        )
                    )
                except BaseException as exc:  # captured only to preserve the validator's assertion context
                    primary_error.append(exc)

            writer = threading.Thread(target=primary_writer, name="task0016-sync-writer")
            writer.start()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                row = sync_db.get_run(source_id, concurrent_sha)
                if row and row.get("state") == "extracting":
                    break
                time.sleep(0.1)
            else:
                raise ValidationFailure("primary sync writer did not acquire its stable lock")
            _expect_sync_failure(
                lambda: run_source(
                    registry_path=REPO_ROOT / "config" / "sources-v1.yaml",
                    audit_path=REPO_ROOT / "reports" / "source-audit-v1.json",
                    source_id=source_id,
                    settings=settings,
                ),
                "sync_locked",
            )
            writer.join(timeout=180)
            if writer.is_alive() or primary_error or len(primary_result) != 1 or primary_result[0].status != "review_required":
                raise ValidationFailure("concurrent sync writers did not preserve one stable owner")
            if _current_version(database_url) != activation_atomic["publication_version_id"]:
                raise ValidationFailure("concurrent candidate changed current publication")

            final_objects = _all_object_facts(database_url)
            final_downloaded = object_store.download_hashes(final_objects)
            if set(final_downloaded.values()) != set(final_objects):
                raise ValidationFailure("final inventory object union was not fully download-hash verified")
            listed_keys: set[str] = set()
            paginator = object_store.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                listed_keys.update(str(item["Key"]) for item in page.get("Contents", []) if isinstance(item, dict) and "Key" in item)
            if listed_keys != {fact.object_key for fact in final_objects.values()}:
                raise ValidationFailure("private bucket contains an unverified object outside the final inventory union")
            _assert_no_worktrees(git_root)
            run_rows = {source: len(sync_db.inspect_source(source)["runs"]) for source in SOURCE_IDS}
            if any(count < 2 for count in run_rows.values()):
                raise ValidationFailure("each source lacks baseline and candidate sync evidence")
            return {
                "status": "passed",
                "environment": environment,
                "docker": {"loopback_only": True, "services": ["postgres", "minio"]},
                "sources": {
                    source: {
                        "baseline": baselines[source],
                        "first_update": first_updates[source],
                        "baseline_status": baseline_results[source]["status"],
                        "first_update_status": first_update_results[source]["status"],
                        "no_change": no_change[source],
                    }
                    for source in SOURCE_IDS
                },
                "object_download_hash_count": len(final_downloaded),
                "object_reuse_and_new_object_once": True,
                "public_sync_cli": {"run_source": cli_no_change["status"], "inspect_source": cli_inspect["status"]},
                "g0dam_recovery": {
                    "reviewed_revision": reviewed_sha,
                    "unreviewed_revision": unreviewed_sha,
                    "removed_revision": removed_sha,
                    "non_fast_forward_revision": nonfast_sha,
                    "recoverable_revision": recoverable_sha,
                    "public_loss_blocked": True,
                    "rights_not_inherited": True,
                    "tombstone_recorded": True,
                    "git_import_build_activation_failures_preserved_current": True,
                    "concurrency_rejected_second_writer": True,
                },
                "atomic_completion": activation_atomic,
                "sync_run_counts": run_rows,
                "temporary_runtime_cleaned": True,
                "compose_cleanup": True,
                "gates": {"GATE-001": "passed", "GATE-002": "passed", "GATE-003": "pending formal closure"},
            }
    finally:
        if http_server_started:
            # The context manager owns normal server shutdown. This flag keeps
            # the finally block declarative without attempting a second stop.
            http_server_started = False
        if compose_started:
            _compose(["down", "--volumes", "--remove-orphans"], env_file=env_file, project=project, check=False, timeout=420)
            _assert_no_project_orphans(project)
        _safe_remove(run_root, external_root=runtime_root)
        cleanup_complete = True
        if not cleanup_complete:
            raise ValidationFailure("owned live runtime cleanup did not complete")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fresh local TASK-0016 incremental-sync validation.")
    parser.add_argument("--json", action="store_true", help="emit one stable JSON result")
    args = parser.parse_args(argv)
    try:
        payload = run()
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except ValidationFailure as exc:
        print(json.dumps({"status": "failed", "error_code": "validation_failed", "message": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 20
    except Exception:
        print(json.dumps({"status": "failed", "error_code": "validation_failed", "message": "incremental sync validation did not complete"}, sort_keys=True))
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
