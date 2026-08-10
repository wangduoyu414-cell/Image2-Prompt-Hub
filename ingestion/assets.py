"""File-system containment and image-byte evidence for a fixed snapshot."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class AssetError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


@dataclass(frozen=True)
class AssetFact:
    source_path: str
    content_sha256: str
    byte_size: int
    media_type: str


MAGIC_TYPES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_relative_path(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise AssetError("asset_path_invalid", "asset path must be a nonempty relative path")
    if ":" in value.split("/")[0].split("\\")[0]:
        raise AssetError("asset_path_invalid", "asset path may not contain a drive prefix")
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    parts = tuple(part for part in pure.parts if part not in {"", "."})
    if not parts or any(part == ".." for part in parts):
        raise AssetError("asset_path_escape", "asset path escapes the snapshot")
    return parts


def resolve_asset_path(snapshot_root: Path, source_path: str) -> Path:
    root = snapshot_root.resolve(strict=True)
    candidate = root.joinpath(*_safe_relative_path(source_path))
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise AssetError("asset_missing", f"asset does not exist: {source_path}") from exc
    if not _is_relative_to(resolved, root):
        raise AssetError("asset_path_escape", "asset symlink or path escapes the snapshot")
    if candidate.is_symlink() or not resolved.is_file():
        raise AssetError("asset_path_invalid", "asset must be a regular non-symlink file")
    return resolved


def image_magic(first: bytes) -> str | None:
    for magic, media_type in MAGIC_TYPES:
        if first.startswith(magic):
            return media_type
    if first.startswith(b"RIFF") and len(first) >= 12 and first[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_asset(snapshot_root: Path, source_path: str) -> AssetFact:
    path = resolve_asset_path(snapshot_root, source_path)
    digest = hashlib.sha256()
    first = b""
    byte_size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(128 * 1024)
            if not chunk:
                break
            if len(first) < 64:
                first += chunk[: 64 - len(first)]
            digest.update(chunk)
            byte_size += len(chunk)
    if first.lstrip().lower().startswith((b"<html", b"<!doctype html")):
        raise AssetError("asset_html_payload", "asset contains HTML rather than image bytes")
    media_type = image_magic(first)
    if media_type is None:
        raise AssetError("asset_unsupported_magic", "asset does not have a supported image magic")
    if byte_size <= 512:
        raise AssetError("asset_too_small", "asset byte size must exceed 512 bytes")
    return AssetFact(
        source_path=source_path.replace("\\", "/"),
        content_sha256=digest.hexdigest(),
        byte_size=byte_size,
        media_type=media_type,
    )
