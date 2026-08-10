"""Source-neutral safe access to a fixed static snapshot."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..registry import RegistryError, normalize_repository_path


ErrorFactory = Callable[[str], Exception]


def safe_repository_path(value: str, *, label: str, error_factory: ErrorFactory) -> str:
    """Normalize one repository-relative path without assigning source semantics."""

    try:
        return normalize_repository_path(value)
    except RegistryError as exc:
        raise error_factory(f"{label} is not a safe repository-relative path") from exc


def fixed_snapshot_root(snapshot_root: Path, *, error_factory: ErrorFactory) -> Path:
    """Resolve a trusted snapshot root while rejecting a link at the root itself."""

    try:
        if snapshot_root.is_symlink():
            raise error_factory("fixed snapshot root may not be a symbolic link")
        root = snapshot_root.resolve(strict=True)
    except OSError as exc:
        raise error_factory("fixed snapshot root is missing or unreadable") from exc
    if not snapshot_root.is_dir() or not root.is_dir():
        raise error_factory("fixed snapshot root must be a regular directory")
    return root


def reject_symlink_components(root: Path, candidate: Path, *, label: str, error_factory: ErrorFactory) -> None:
    """Reject every symbolic-link component below ``root`` before file access."""

    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise error_factory(f"{label} escapes the fixed snapshot") from exc
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise error_factory(f"{label} may not traverse a symbolic link")


def snapshot_file(snapshot_root: Path, relative_path: str, *, label: str, error_factory: ErrorFactory) -> Path:
    """Return one existing regular non-symlink file within the fixed snapshot."""

    root = fixed_snapshot_root(snapshot_root, error_factory=error_factory)
    safe = safe_repository_path(relative_path, label=label, error_factory=error_factory)
    candidate = root.joinpath(*safe.split("/"))
    reject_symlink_components(root, candidate, label=label, error_factory=error_factory)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise error_factory(f"{label} is missing or escapes the fixed snapshot") from exc
    if not resolved.is_file():
        raise error_factory(f"{label} must be a regular non-symlink file")
    return resolved


def read_snapshot_text(
    snapshot_root: Path,
    relative_path: str,
    *,
    label: str,
    error_factory: ErrorFactory,
    read_error_factory: ErrorFactory | None = None,
) -> str:
    """Read logical UTF-8 text from a regular snapshot file without source semantics."""

    path = snapshot_file(snapshot_root, relative_path, label=label, error_factory=error_factory)
    try:
        # Match ``Path.read_text`` logical-text behavior: CRLF and lone CR are
        # represented as LF, while no trimming, Unicode normalization, or
        # other content rewrite is performed here.
        with path.open("r", encoding="utf-8", newline=None) as stream:
            return stream.read()
    except (OSError, UnicodeDecodeError) as exc:
        factory = read_error_factory or error_factory
        detail = f"cannot decode {label} as UTF-8" if isinstance(exc, UnicodeDecodeError) else f"cannot read {label}"
        raise factory(detail) from exc


def regular_relative_files(
    snapshot_root: Path,
    relative_root: str,
    *,
    suffix: str | None = None,
    error_factory: ErrorFactory,
) -> set[str]:
    """Enumerate exactly the regular files beneath a non-symlink directory.

    Traversal deliberately checks a symlink before considering whether an entry
    is a directory.  A directory link is therefore a hard failure rather than a
    silently skipped subtree.
    """

    root = fixed_snapshot_root(snapshot_root, error_factory=error_factory)
    safe_root = safe_repository_path(relative_root, label="fixed snapshot directory", error_factory=error_factory)
    directory = root.joinpath(*safe_root.split("/"))
    reject_symlink_components(root, directory, label=relative_root, error_factory=error_factory)
    try:
        resolved_directory = directory.resolve(strict=True)
        resolved_directory.relative_to(root)
    except (OSError, ValueError) as exc:
        raise error_factory(f"{relative_root} is missing or escapes the fixed snapshot") from exc
    if not resolved_directory.is_dir():
        raise error_factory(f"{relative_root} must be a regular directory")

    result: set[str] = set()

    def visit(directory_path: Path) -> None:
        try:
            children = sorted(directory_path.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise error_factory(f"{relative_root} is missing or unreadable") from exc
        for path in children:
            reject_symlink_components(root, path, label=f"{relative_root} entry", error_factory=error_factory)
            if path.is_symlink():
                raise error_factory(f"{relative_root} entry may not traverse a symbolic link")
            if path.is_dir():
                visit(path)
                continue
            if not path.is_file():
                raise error_factory(f"{relative_root} contains a non-regular file")
            relative = path.relative_to(root).as_posix()
            if suffix is None or path.suffix == suffix:
                result.add(relative)

    visit(resolved_directory)
    return result
