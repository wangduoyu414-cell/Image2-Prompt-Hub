"""Small, source-neutral protocol boundary for static source adapters."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AssetPathBinding:
    """Explicitly bind one adapter asset reference to one snapshot path."""

    asset_ref_id: str
    source_path: str


@dataclass(frozen=True)
class ParsedCase:
    source_case_key: str
    native_id: str
    asset_paths: tuple[AssetPathBinding, ...]
    adapter_record: dict[str, Any]

    @property
    def image_path(self) -> str:
        """Backward-compatible single-output view for the Phase 1 adapters."""
        if len(self.asset_paths) != 1:
            raise AdapterError("adapter_mapping_invalid", "multi-output case has no single image_path")
        return self.asset_paths[0].source_path


class AdapterError(ValueError):
    """Fail-closed adapter error with a stable CLI-compatible code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


def normalize_prompt(value: str) -> str:
    """Normalize only the stable prompt identity representation.

    Source adapters retain their delivered prompt text separately.  This helper
    is intentionally equivalent to the former g0dam-local implementation so
    that its prompt IDs and published package identity remain unchanged.
    """

    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def prompt_sha256(value: str) -> str:
    return hashlib.sha256(normalize_prompt(value).encode("utf-8")).hexdigest()


class FixedSnapshotAdapter(Protocol):
    def __call__(self, snapshot_root: Any, source_config: Any) -> tuple[list[ParsedCase], str | None]: ...
