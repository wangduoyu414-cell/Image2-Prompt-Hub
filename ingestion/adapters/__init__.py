"""Fixed, code-owned dispatch for the supported static source adapters."""

from .base import AdapterError, AssetPathBinding, FixedSnapshotAdapter, ParsedCase
from .conardli import parse_conardli_snapshot
from .erickkkyt import parse_erickkkyt_snapshot
from .freestylefly import parse_freestylefly_snapshot
from .g0dam import parse_g0dam_snapshot
from .joesai import parse_joesai_snapshot
from .vigozhao import parse_vigozhao_snapshot


STATIC_ADAPTER_PARSERS: dict[str, FixedSnapshotAdapter] = {
    "g0dam_manifest_json_v1": parse_g0dam_snapshot,
    "joesai_manifest_markdown_v1": parse_joesai_snapshot,
    "conardli_compiled_case_manifest_v1": parse_conardli_snapshot,
    "freestylefly_cases_json_v1": parse_freestylefly_snapshot,
    "erickkkyt_prompts_json_v1": parse_erickkkyt_snapshot,
    "vigo_style_directory_v1": parse_vigozhao_snapshot,
}


def adapter_for_strategy(adapter_strategy: str) -> FixedSnapshotAdapter:
    parser = STATIC_ADAPTER_PARSERS.get(adapter_strategy)
    if parser is None:
        raise AdapterError("registry_invalid", "source adapter strategy is not implemented")
    return parser

__all__ = [
    "AdapterError",
    "AssetPathBinding",
    "ParsedCase",
    "STATIC_ADAPTER_PARSERS",
    "adapter_for_strategy",
    "parse_g0dam_snapshot",
    "parse_joesai_snapshot",
    "parse_conardli_snapshot",
    "parse_freestylefly_snapshot",
    "parse_erickkkyt_snapshot",
    "parse_vigozhao_snapshot",
]
