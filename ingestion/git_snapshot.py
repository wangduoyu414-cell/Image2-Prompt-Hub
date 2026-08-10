"""Safe fixed-commit Git mirror and temporary read-only snapshot boundary."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .registry import SourceConfig, ensure_external_root


class GitSnapshotError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
SAFE_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class GitSnapshot:
    root: Path
    commit_sha: str
    mirror_path: Path
    read_only: bool = True


@dataclass(frozen=True)
class GitCandidate:
    """A fresh, exact candidate observed from one configured remote branch."""

    source_id: str
    default_branch: str
    candidate_sha: str
    mirror_path: Path


def _require_commit_sha(value: str, label: str) -> str:
    if not isinstance(value, str) or not COMMIT_SHA.fullmatch(value):
        raise GitSnapshotError("invalid_commit_sha", f"{label} must be a lowercase 40-character commit SHA")
    return value


def _bounded_text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").strip()[:4_000]


def _runtime_git_paths(data_root: Path) -> tuple[Path, Path]:
    config_path = data_root / "git-global.config"
    hooks_path = data_root / "empty-hooks"
    hooks_path.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text("# TASK-0003 isolated git config\n", encoding="utf-8")
    return config_path, hooks_path


def _git_environment(data_root: Path) -> dict[str, str]:
    config_path, _ = _runtime_git_paths(data_root)
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(config_path),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_PAGER": "cat",
        }
    )
    return environment


def _git_prefix(data_root: Path, *, allow_file_protocol: bool = False) -> list[str]:
    _, hooks_path = _runtime_git_paths(data_root)
    return [
        "git",
        "-c",
        f"core.hooksPath={hooks_path}",
        "-c",
        f"protocol.file.allow={'always' if allow_file_protocol else 'never'}",
        "-c",
        "submodule.recurse=false",
        "-c",
        "submodule.active=none",
        "-c",
        "filter.lfs.required=false",
        "-c",
        "filter.lfs.smudge=",
        "-c",
        "filter.lfs.process=",
        "-c",
        "core.autocrlf=false",
    ]


def _run_git(
    data_root: Path,
    arguments: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int = 90,
    check: bool = True,
    allow_file_protocol: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    command = [*_git_prefix(data_root, allow_file_protocol=allow_file_protocol), *arguments]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            env=_git_environment(data_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitSnapshotError("git_unavailable", f"safe git command failed to start or timed out: {exc}") from exc
    if check and result.returncode != 0:
        raise GitSnapshotError(
            "git_failed",
            f"safe git command failed ({result.returncode}): {_bounded_text(result.stderr) or _bounded_text(result.stdout)}",
        )
    return result


def _mirror_path(data_root: Path, source_id: str) -> Path:
    return data_root / "mirrors" / f"{source_id}.git"


def _ensure_mirror(
    config: SourceConfig, data_root: Path, timeout_seconds: int, *, allow_file_protocol: bool = False
) -> Path:
    mirror = _ensure_remote_mirror(config, data_root, timeout_seconds, allow_file_protocol=allow_file_protocol)
    _run_git(
        data_root,
        ["-C", str(mirror), "fetch", "--no-tags", "--no-recurse-submodules", "origin", config.verified_commit_sha],
        timeout_seconds=timeout_seconds,
        allow_file_protocol=allow_file_protocol,
    )
    verified = _run_git(
        data_root,
        ["-C", str(mirror), "rev-parse", f"{config.verified_commit_sha}^{{commit}}"],
        timeout_seconds=timeout_seconds,
        allow_file_protocol=allow_file_protocol,
    )
    if _bounded_text(verified.stdout) != config.verified_commit_sha:
        raise GitSnapshotError("commit_mismatch", "mirror does not resolve the registered fixed commit")
    return mirror


def _ensure_remote_mirror(
    config: SourceConfig, data_root: Path, timeout_seconds: int, *, allow_file_protocol: bool = False
) -> Path:
    """Create or validate a mirror without asserting a particular revision.

    Candidate discovery intentionally precedes candidate authority construction:
    it needs a safe remote mirror and an exact branch observation, but must not
    pretend that the static audit Commit is the newly observed Commit.  Fixed
    extraction paths still use :func:`_ensure_mirror`, which verifies their
    supplied fixed Commit before exposing a worktree.
    """

    mirror = _mirror_path(data_root, config.source_id)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if not mirror.exists():
        _run_git(
            data_root,
            ["clone", "--mirror", "--no-checkout", config.repository_url, str(mirror)],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        )
    if not mirror.is_dir():
        raise GitSnapshotError("mirror_invalid", "mirror path is not a directory")
    return mirror


def _assert_safe_tree(
    config: SourceConfig,
    data_root: Path,
    mirror: Path,
    timeout_seconds: int,
    *,
    commit_sha: str | None = None,
    allow_file_protocol: bool = False,
) -> None:
    """Reject trees that would require submodule or Git filter execution."""
    commit = _require_commit_sha(commit_sha or config.verified_commit_sha, "snapshot commit")
    submodule = _run_git(
        data_root,
        ["-C", str(mirror), "cat-file", "-e", f"{commit}:.gitmodules"],
        timeout_seconds=timeout_seconds,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )
    if submodule.returncode == 0:
        raise GitSnapshotError("unsafe_submodule", "fixed source tree declares submodules; TASK-0003 does not initialize them")
    attributes = _run_git(
        data_root,
        ["-C", str(mirror), "show", f"{commit}:.gitattributes"],
        timeout_seconds=timeout_seconds,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )
    if attributes.returncode == 0 and b"filter=" in attributes.stdout.lower():
        raise GitSnapshotError("unsafe_git_filter", "fixed source tree declares a Git filter; TASK-0003 fails closed")


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def onerror(function: object, item: str, exception: object) -> None:
        try:
            os.chmod(item, 0o700)
            if callable(function):
                function(item)  # type: ignore[misc]
        except OSError:
            raise

    shutil.rmtree(path, onerror=onerror)


def _cleanup_worktree(data_root: Path, mirror: Path, worktree: Path, *, allow_file_protocol: bool = False) -> None:
    _run_git(
        data_root,
        ["-C", str(mirror), "worktree", "remove", "--force", str(worktree)],
        timeout_seconds=60,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )
    _remove_tree(worktree)
    _run_git(
        data_root,
        ["-C", str(mirror), "worktree", "prune"],
        timeout_seconds=60,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )


def _fetch_exact_commit(
    data_root: Path,
    mirror: Path,
    commit_sha: str,
    *,
    timeout_seconds: int,
    allow_file_protocol: bool,
) -> str:
    commit = _require_commit_sha(commit_sha, "candidate commit")
    _run_git(
        data_root,
        ["-C", str(mirror), "fetch", "--no-tags", "--no-recurse-submodules", "origin", commit],
        timeout_seconds=timeout_seconds,
        allow_file_protocol=allow_file_protocol,
    )
    resolved = _bounded_text(
        _run_git(
            data_root,
            ["-C", str(mirror), "rev-parse", f"{commit}^{{commit}}"],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        ).stdout
    )
    if resolved != commit:
        raise GitSnapshotError("commit_mismatch", "mirror does not resolve the fetched candidate commit")
    return resolved


def detect_default_branch_candidate(
    source_config: SourceConfig,
    data_root: Path | str,
    *,
    default_branch: str,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_file_protocol: bool = False,
) -> GitCandidate:
    """Fetch and resolve only the configured default branch to one exact commit.

    The returned SHA is evidence, not a moving branch authority.  Callers must
    still use ``candidate_snapshot`` to fetch that exact SHA again before
    reading files.
    """

    if not isinstance(default_branch, str) or not SAFE_BRANCH.fullmatch(default_branch) or ".." in default_branch:
        raise GitSnapshotError("invalid_default_branch", "configured default branch is unsafe")
    root = ensure_external_root(data_root, workspace_root=workspace_root)
    mirror = _ensure_remote_mirror(source_config, root, timeout_seconds, allow_file_protocol=allow_file_protocol)
    remote_ref = f"refs/remotes/origin/{default_branch}"
    _run_git(
        root,
        [
            "-C",
            str(mirror),
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            "origin",
            f"+refs/heads/{default_branch}:{remote_ref}",
        ],
        timeout_seconds=timeout_seconds,
        allow_file_protocol=allow_file_protocol,
    )
    candidate = _bounded_text(
        _run_git(
            root,
            ["-C", str(mirror), "rev-parse", f"{remote_ref}^{{commit}}"],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        ).stdout
    )
    return GitCandidate(
        source_id=source_config.source_id,
        default_branch=default_branch,
        candidate_sha=_require_commit_sha(candidate, "default branch candidate"),
        mirror_path=mirror,
    )


def is_fast_forward(
    source_config: SourceConfig,
    data_root: Path | str,
    *,
    previous_sha: str,
    candidate_sha: str,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_file_protocol: bool = False,
) -> bool:
    """Return whether the exact previous commit is an ancestor of candidate."""

    previous = _require_commit_sha(previous_sha, "previous commit")
    candidate = _require_commit_sha(candidate_sha, "candidate commit")
    root = ensure_external_root(data_root, workspace_root=workspace_root)
    mirror = _ensure_mirror(source_config, root, timeout_seconds, allow_file_protocol=allow_file_protocol)
    _fetch_exact_commit(root, mirror, previous, timeout_seconds=timeout_seconds, allow_file_protocol=allow_file_protocol)
    _fetch_exact_commit(root, mirror, candidate, timeout_seconds=timeout_seconds, allow_file_protocol=allow_file_protocol)
    result = _run_git(
        root,
        ["-C", str(mirror), "merge-base", "--is-ancestor", previous, candidate],
        timeout_seconds=timeout_seconds,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise GitSnapshotError("git_failed", "fast-forward relationship could not be determined")


@contextmanager
def candidate_snapshot(
    source_config: SourceConfig,
    data_root: Path | str,
    *,
    candidate_sha: str,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_file_protocol: bool = False,
) -> Iterator[GitSnapshot]:
    """Yield an external detached worktree for a freshly fetched candidate SHA."""

    candidate = _require_commit_sha(candidate_sha, "candidate commit")
    root = ensure_external_root(data_root, workspace_root=workspace_root)
    mirror = _ensure_mirror(source_config, root, timeout_seconds, allow_file_protocol=allow_file_protocol)
    _fetch_exact_commit(root, mirror, candidate, timeout_seconds=timeout_seconds, allow_file_protocol=allow_file_protocol)
    _assert_safe_tree(
        source_config,
        root,
        mirror,
        timeout_seconds,
        commit_sha=candidate,
        allow_file_protocol=allow_file_protocol,
    )
    worktree = root / "worktrees" / source_config.source_id / f"candidate-{uuid.uuid4().hex}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run_git(
            root,
            ["-C", str(mirror), "worktree", "add", "--detach", str(worktree), candidate],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        )
        actual = _bounded_text(
            _run_git(
                root,
                ["-C", str(worktree), "rev-parse", "HEAD"],
                timeout_seconds=timeout_seconds,
                allow_file_protocol=allow_file_protocol,
            ).stdout
        )
        if actual != candidate:
            raise GitSnapshotError("commit_mismatch", "temporary candidate snapshot HEAD differs from fetched SHA")
        yield GitSnapshot(root=worktree, commit_sha=actual, mirror_path=mirror)
    finally:
        _cleanup_worktree(root, mirror, worktree, allow_file_protocol=allow_file_protocol)


def retain_candidate_ref(
    source_config: SourceConfig,
    data_root: Path | str,
    *,
    candidate_sha: str,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_file_protocol: bool = False,
) -> str:
    """Create or verify an immutable internal ref after a candidate is imported."""

    candidate = _require_commit_sha(candidate_sha, "candidate commit")
    if not SAFE_SOURCE_ID.fullmatch(source_config.source_id):
        raise GitSnapshotError("invalid_source_id", "source id cannot form a retained-ref namespace")
    root = ensure_external_root(data_root, workspace_root=workspace_root)
    mirror = _ensure_mirror(source_config, root, timeout_seconds, allow_file_protocol=allow_file_protocol)
    _fetch_exact_commit(root, mirror, candidate, timeout_seconds=timeout_seconds, allow_file_protocol=allow_file_protocol)
    ref = f"refs/image2-retained/{source_config.source_id}/{candidate}"
    existing = _run_git(
        root,
        ["-C", str(mirror), "rev-parse", "--verify", "--quiet", ref],
        timeout_seconds=timeout_seconds,
        check=False,
        allow_file_protocol=allow_file_protocol,
    )
    if existing.returncode == 0:
        if _bounded_text(existing.stdout) != candidate:
            raise GitSnapshotError("retained_ref_conflict", "retained ref does not resolve to the candidate commit")
        return ref
    if existing.returncode not in {1, 128}:
        raise GitSnapshotError("git_failed", "retained ref could not be inspected")
    _run_git(
        root,
        ["-C", str(mirror), "update-ref", ref, candidate],
        timeout_seconds=timeout_seconds,
        allow_file_protocol=allow_file_protocol,
    )
    resolved = _bounded_text(
        _run_git(
            root,
            ["-C", str(mirror), "rev-parse", f"{ref}^{{commit}}"],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        ).stdout
    )
    if resolved != candidate:
        raise GitSnapshotError("retained_ref_conflict", "retained ref verification failed")
    return ref


@contextmanager
def fixed_snapshot(
    source_config: SourceConfig,
    data_root: Path | str,
    *,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_file_protocol: bool = False,
) -> Iterator[GitSnapshot]:
    """Yield an external detached fixed-commit worktree and always remove it."""
    root = ensure_external_root(data_root, workspace_root=workspace_root)
    mirror = _ensure_mirror(
        source_config, root, timeout_seconds, allow_file_protocol=allow_file_protocol
    )
    _assert_safe_tree(
        source_config, root, mirror, timeout_seconds, allow_file_protocol=allow_file_protocol
    )
    worktree = root / "worktrees" / source_config.source_id / f"run-{uuid.uuid4().hex}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run_git(
            root,
            ["-C", str(mirror), "worktree", "add", "--detach", str(worktree), source_config.verified_commit_sha],
            timeout_seconds=timeout_seconds,
            allow_file_protocol=allow_file_protocol,
        )
        actual = _bounded_text(
            _run_git(
                root,
                ["-C", str(worktree), "rev-parse", "HEAD"],
                timeout_seconds=timeout_seconds,
                allow_file_protocol=allow_file_protocol,
            ).stdout
        )
        if actual != source_config.verified_commit_sha:
            raise GitSnapshotError("commit_mismatch", "temporary snapshot HEAD differs from registered fixed commit")
        yield GitSnapshot(root=worktree, commit_sha=actual, mirror_path=mirror)
    finally:
        _cleanup_worktree(root, mirror, worktree, allow_file_protocol=allow_file_protocol)
