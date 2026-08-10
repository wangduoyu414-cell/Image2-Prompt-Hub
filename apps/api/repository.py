"""Immutable-publication read model and deterministic Canonical Case projection."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from content.database import ContentDatabase, ContentDatabaseError, ContentDatabaseSettings


_PUBLIC_ASSET_POLICIES = frozenset({"mirror_allowed", "attribution_required"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_PUBLIC_LOCATION_KEYS = frozenset(
    {
        "object_bucket",
        "object_key",
        "bucket",
        "access_key",
        "secret_access_key",
        "credential",
        "credentials",
        "password",
        "dsn",
        "database_url",
        "endpoint_url",
    }
)
_FORBIDDEN_PUBLIC_LOCATION_KEY_PARTS = (
    "bucket",
    "object_key",
    "s3_key",
    "storage",
    "credential",
    "secret",
    "password",
    "dsn",
    "endpoint",
    "access_key",
)


class PublicApiError(RuntimeError):
    """A stable failure which can be safely mapped to a public error code."""


class PublicationUnavailable(PublicApiError):
    """The active immutable snapshot could not be read."""


class PublicationSnapshotInvalid(PublicApiError):
    """Stored snapshot data does not satisfy the public projection contract."""


class CaseNotFound(PublicApiError):
    """A Canonical Case is absent from the active immutable snapshot."""


class AssetNotAuthorized(PublicApiError):
    """An asset is absent, non-mirrorable, or not part of the active snapshot."""


class PublicationReader(Protocol):
    def inspect_current(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class AssetLocator:
    content_sha256: str
    bucket: str
    object_key: str
    media_type: str
    byte_size: int


@dataclass(frozen=True)
class CurrentPublication:
    state: str
    publication: Mapping[str, Any] | None
    entries: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class CanonicalCase:
    canonical_key: str
    members: tuple[Mapping[str, Any], ...]

    @property
    def representative(self) -> Mapping[str, Any]:
        return self.members[0]


class ContentPublicationRepository:
    """The sole production reader: ContentDatabase.inspect_publication()."""

    def __init__(self, database_url: str) -> None:
        try:
            settings = ContentDatabaseSettings(database_url)
            settings.validate()
        except ContentDatabaseError as exc:
            raise PublicationUnavailable("publication configuration is unavailable") from exc
        self._database = ContentDatabase(settings)

    @classmethod
    def from_environment(cls) -> "ContentPublicationRepository":
        return cls(os.environ.get("PUBLIC_API_DATABASE_URL", ""))

    def inspect_current(self) -> Mapping[str, Any]:
        try:
            value = self._database.inspect_publication()
        except ContentDatabaseError as exc:
            raise PublicationUnavailable("current publication is unavailable") from exc
        if not isinstance(value, Mapping):
            raise PublicationSnapshotInvalid("current publication must be an object")
        return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicationSnapshotInvalid(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PublicationSnapshotInvalid(f"{label} must be an array")
    return value


def _text(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise PublicationSnapshotInvalid(f"{label} must be non-empty text")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise PublicationSnapshotInvalid(f"{label} must be an integer")
    return value


def _entry_row_id(entry: Mapping[str, Any]) -> int:
    generation = _mapping(entry.get("generation_example"), "generation_example")
    return _integer(generation.get("generation_example_row_id"), "generation_example_row_id", minimum=1)


def _entry_key(entry: Mapping[str, Any]) -> str:
    canonical = _mapping(entry.get("canonical"), "canonical")
    return _text(canonical.get("canonical_key"), "canonical_key")


def _entry_assets(entry: Mapping[str, Any], collection: str) -> tuple[Mapping[str, Any], ...]:
    return tuple(_mapping(item, f"{collection} item") for item in _sequence(entry.get(collection), collection))


def _source(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(entry.get("source"), "source")


def _rights(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(entry.get("rights"), "rights")


def _tags(entry: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_mapping(item, "taxonomy item") for item in _sequence(entry.get("taxonomy"), "taxonomy"))


def _safe_location(value: object, label: str) -> dict[str, Any]:
    """Preserve source location provenance without letting it smuggle locators."""

    def visit(item: object, path: str) -> Any:
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        if isinstance(item, Mapping):
            projected: dict[str, Any] = {}
            for key, nested in item.items():
                safe_key = _text(key, f"{path} key")
                lowered_key = safe_key.casefold()
                if (
                    lowered_key in _FORBIDDEN_PUBLIC_LOCATION_KEYS
                    or lowered_key in {"key", "object"}
                    or any(part in lowered_key for part in _FORBIDDEN_PUBLIC_LOCATION_KEY_PARTS)
                ):
                    raise PublicationSnapshotInvalid("asset source location contains a protected storage or secret field")
                projected[safe_key] = visit(nested, f"{path}.{safe_key}")
            return projected
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            return [visit(nested, f"{path}[]") for nested in item]
        raise PublicationSnapshotInvalid(f"{path} contains a non-JSON value")

    projected = visit(_mapping(value, label), label)
    assert isinstance(projected, dict)
    return projected


def _policy(entry: Mapping[str, Any]) -> str:
    return _text(_rights(entry).get("display_policy"), "display_policy")


def _validate_entry(entry: Mapping[str, Any]) -> None:
    """Check only fields needed by the projection before exposing a snapshot."""

    _entry_key(entry)
    _entry_row_id(entry)
    prompt = _mapping(entry.get("prompt"), "prompt")
    _text(prompt.get("raw_text"), "prompt.raw_text")
    provenance = _mapping(prompt.get("provenance"), "prompt.provenance")
    _text(provenance.get("source_path"), "prompt.provenance.source_path")
    _text(provenance.get("source_url"), "prompt.provenance.source_url")
    for field in ("source_id", "repository_id", "revision_sha", "source_path", "source_url"):
        _text(_source(entry).get(field), f"source.{field}")
    for field in (
        "repository_license",
        "prompt_rights",
        "asset_rights",
        "author",
        "original_url",
        "evidence_url",
        "reviewer",
        "reviewed_at",
    ):
        _text(_rights(entry).get(field), f"rights.{field}", allow_empty=field in {"author", "reviewer"})
    _policy(entry)
    model = _mapping(entry.get("model"), "model")
    _text(model.get("warning"), "model.warning")
    claim = _mapping(model.get("source_claim"), "model.source_claim")
    _text(claim.get("evidence_status"), "model.source_claim.evidence_status")
    for collection in ("inputs", "outputs"):
        for asset in _entry_assets(entry, collection):
            content_sha256 = _text(asset.get("content_sha256"), f"{collection}.content_sha256")
            if not _SHA256_RE.fullmatch(content_sha256):
                raise PublicationSnapshotInvalid(f"{collection}.content_sha256 must be lowercase SHA-256")
            _text(asset.get("media_type"), f"{collection}.media_type")
            _integer(asset.get("byte_size"), f"{collection}.byte_size", minimum=1)
            _integer(asset.get("ordinal"), f"{collection}.ordinal", minimum=0)
            _text(asset.get("role"), f"{collection}.role")
            _text(asset.get("source_path"), f"{collection}.source_path")
            _text(asset.get("source_url"), f"{collection}.source_url")
            _safe_location(asset.get("source_location"), f"{collection}.source_location")
    for tag in _tags(entry):
        for field in ("taxonomy_version", "classifier_version", "tag_value", "tag_source"):
            _text(tag.get(field), f"taxonomy.{field}")
        if not isinstance(tag.get("confidence"), (int, float)) or isinstance(tag.get("confidence"), bool):
            raise PublicationSnapshotInvalid("taxonomy.confidence must be numeric")


class PublicReadRepository:
    """Projects the current immutable snapshot without inventory or rights joins."""

    def __init__(self, reader: PublicationReader) -> None:
        self._reader = reader

    def _current(self) -> CurrentPublication:
        raw = self._reader.inspect_current()
        state = raw.get("state")
        if state == "no_current":
            if raw.get("publication_version") is not None or raw.get("entries") not in ([], ()):
                raise PublicationSnapshotInvalid("no_current response carries publication data")
            return CurrentPublication(state="no_current", publication=None, entries=())
        if state != "active":
            raise PublicationSnapshotInvalid("publication state is not recognized")
        publication = _mapping(raw.get("publication_version"), "publication_version")
        entries = tuple(_mapping(item, "publication entry") for item in _sequence(raw.get("entries"), "entries"))
        for entry in entries:
            _validate_entry(entry)
        return CurrentPublication(state="active", publication=publication, entries=entries)

    def _groups(self, current: CurrentPublication) -> tuple[CanonicalCase, ...]:
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for entry in current.entries:
            grouped.setdefault(_entry_key(entry), []).append(entry)
        return tuple(
            CanonicalCase(
                canonical_key=key,
                members=tuple(sorted(members, key=lambda item: _entry_row_id(item))),
            )
            for key, members in sorted(grouped.items())
        )

    @staticmethod
    def _publication_response(current: CurrentPublication, case_count: int) -> dict[str, Any]:
        if current.state == "no_current":
            return {"state": "no_current", "publication": None, "case_count": case_count}
        assert current.publication is not None
        raw = current.publication
        reason_counts = _mapping(raw.get("reason_counts"), "publication_version.reason_counts")
        normalized_counts: dict[str, int] = {}
        for key, value in reason_counts.items():
            normalized_counts[_text(key, "publication reason key")] = _integer(value, "publication reason count")
        return {
            "state": "active",
            "publication": {
                "content_digest": _text(raw.get("content_digest"), "publication_version.content_digest"),
                "included_count": _integer(raw.get("included_count"), "publication_version.included_count"),
                "excluded_count": _integer(raw.get("excluded_count"), "publication_version.excluded_count"),
                "reason_counts": normalized_counts,
                "completed_at": raw.get("completed_at")
                if raw.get("completed_at") is None
                else _text(raw.get("completed_at"), "publication_version.completed_at"),
            },
            "case_count": case_count,
        }

    @staticmethod
    def _safe_asset(asset: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "content_sha256": _text(asset.get("content_sha256"), "asset.content_sha256"),
            "media_type": _text(asset.get("media_type"), "asset.media_type"),
            "byte_size": _integer(asset.get("byte_size"), "asset.byte_size", minimum=1),
            "ordinal": _integer(asset.get("ordinal"), "asset.ordinal", minimum=0),
            "role": _text(asset.get("role"), "asset.role"),
            "source_path": _text(asset.get("source_path"), "asset.source_path"),
            "source_url": _text(asset.get("source_url"), "asset.source_url"),
            "source_location": _safe_location(asset.get("source_location"), "asset.source_location"),
        }

    @classmethod
    def _member(cls, entry: Mapping[str, Any]) -> dict[str, Any]:
        prompt = _mapping(entry.get("prompt"), "prompt")
        provenance = _mapping(prompt.get("provenance"), "prompt.provenance")
        source = _source(entry)
        rights = _rights(entry)
        model = _mapping(entry.get("model"), "model")
        claim = _mapping(model.get("source_claim"), "model.source_claim")
        parameters = claim.get("parameters_raw", {})
        if not isinstance(parameters, Mapping):
            raise PublicationSnapshotInvalid("model.source_claim.parameters_raw must be an object")
        return {
            "prompt": {
                "raw_text": _text(prompt.get("raw_text"), "prompt.raw_text"),
                "provenance": {
                    "source_path": _text(provenance.get("source_path"), "prompt.provenance.source_path"),
                    "source_url": _text(provenance.get("source_url"), "prompt.provenance.source_url"),
                },
            },
            "inputs": [cls._safe_asset(asset) for asset in _entry_assets(entry, "inputs")],
            "outputs": [cls._safe_asset(asset) for asset in _entry_assets(entry, "outputs")],
            "source": {
                field: _text(source.get(field), f"source.{field}")
                for field in ("source_id", "repository_id", "revision_sha", "source_path", "source_url")
            },
            "rights": {
                field: _text(rights.get(field), f"rights.{field}", allow_empty=field in {"author", "reviewer"})
                for field in (
                    "repository_license",
                    "prompt_rights",
                    "asset_rights",
                    "author",
                    "original_url",
                    "evidence_url",
                    "reviewer",
                    "reviewed_at",
                    "display_policy",
                )
            },
            "model": {
                "source_claim": {
                    "evidence_status": _text(claim.get("evidence_status"), "model.source_claim.evidence_status"),
                    "model_raw": claim.get("model_raw") if isinstance(claim.get("model_raw"), str) else None,
                    "parameters_raw": dict(parameters),
                },
                "warning": _text(model.get("warning"), "model.warning"),
            },
            "taxonomy": [
                {
                    "taxonomy_version": _text(tag.get("taxonomy_version"), "taxonomy.taxonomy_version"),
                    "classifier_version": _text(tag.get("classifier_version"), "taxonomy.classifier_version"),
                    "tag_value": _text(tag.get("tag_value"), "taxonomy.tag_value"),
                    "tag_source": _text(tag.get("tag_source"), "taxonomy.tag_source"),
                    "confidence": float(tag["confidence"]),
                }
                for tag in _tags(entry)
            ],
        }

    @classmethod
    def _summary(cls, group: CanonicalCase) -> dict[str, Any]:
        representative = cls._member(group.representative)
        source_ids = sorted({_text(_source(member).get("source_id"), "source.source_id") for member in group.members})
        policies = sorted({_policy(member) for member in group.members})
        tags = sorted(
            {
                _text(tag.get("tag_value"), "taxonomy.tag_value")
                for member in group.members
                for tag in _tags(member)
            }
        )
        prompt = representative["prompt"]["raw_text"]
        return {
            "canonical_key": group.canonical_key,
            "prompt_preview": prompt[:280],
            "source_ids": source_ids,
            "display_policies": policies,
            "tags": tags,
            "has_reference": any(bool(_entry_assets(member, "inputs")) for member in group.members),
            "member_count": len(group.members),
        }

    @staticmethod
    def _matches(
        group: CanonicalCase,
        *,
        q: str | None,
        source: str | None,
        display_policy: str | None,
        tag: str | None,
        has_reference: bool | None,
    ) -> bool:
        members = group.members
        if source is not None and not any(_source(member).get("source_id") == source for member in members):
            return False
        if display_policy is not None and not any(_policy(member) == display_policy for member in members):
            return False
        if tag is not None and not any(tag == item.get("tag_value") for member in members for item in _tags(member)):
            return False
        if has_reference is not None and any(bool(_entry_assets(member, "inputs")) for member in members) != has_reference:
            return False
        if not q:
            return True
        needle = q.casefold()
        for member in members:
            prompt = _mapping(member.get("prompt"), "prompt").get("raw_text")
            source_id = _source(member).get("source_id")
            author = _rights(member).get("author")
            tag_values = [item.get("tag_value") for item in _tags(member)]
            if any(isinstance(value, str) and needle in value.casefold() for value in [prompt, source_id, author, *tag_values]):
                return True
        return False

    @staticmethod
    def _facets(groups: Sequence[CanonicalCase]) -> dict[str, Any]:
        sources: Counter[str] = Counter()
        policies: Counter[str] = Counter()
        tags: Counter[str] = Counter()
        references: Counter[bool] = Counter()
        for group in groups:
            sources.update({_text(_source(member).get("source_id"), "source.source_id") for member in group.members})
            policies.update({_policy(member) for member in group.members})
            tags.update(
                {
                    _text(tag.get("tag_value"), "taxonomy.tag_value")
                    for member in group.members
                    for tag in _tags(member)
                }
            )
            references[any(bool(_entry_assets(member, "inputs")) for member in group.members)] += 1
        return {
            "sources": [{"value": value, "count": count} for value, count in sorted(sources.items())],
            "display_policies": [{"value": value, "count": count} for value, count in sorted(policies.items())],
            "tags": [{"value": value, "count": count} for value, count in sorted(tags.items())],
            "has_reference": [{"value": value, "count": references[value]} for value in (False, True) if value in references],
        }

    def publication(self) -> dict[str, Any]:
        current = self._current()
        return self._publication_response(current, len(self._groups(current)))

    def readiness(self) -> str:
        return self._current().state

    def list_cases(
        self,
        *,
        q: str | None,
        source: str | None,
        display_policy: str | None,
        tag: str | None,
        has_reference: bool | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        current = self._current()
        all_groups = self._groups(current)
        filtered = tuple(
            group
            for group in all_groups
            if self._matches(
                group,
                q=q,
                source=source,
                display_policy=display_policy,
                tag=tag,
                has_reference=has_reference,
            )
        )
        start = (page - 1) * page_size
        return {
            "publication": self._publication_response(current, len(all_groups)),
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "cases": [self._summary(group) for group in filtered[start : start + page_size]],
            "facets": self._facets(filtered),
        }

    def case_detail(self, canonical_key: str) -> dict[str, Any]:
        current = self._current()
        groups = self._groups(current)
        for group in groups:
            if group.canonical_key == canonical_key:
                members = [self._member(member) for member in group.members]
                return {
                    "publication": self._publication_response(current, len(groups)),
                    "canonical_key": group.canonical_key,
                    "member_count": len(members),
                    "representative": members[0],
                    "members": members,
                }
        raise CaseNotFound("case is not current")

    def locate_current_asset(self, content_sha256: str) -> AssetLocator:
        """Authorize before any S3 client is obtained or asked for bytes."""

        current = self._current()
        matches: list[AssetLocator] = []
        for entry in current.entries:
            if _policy(entry) not in _PUBLIC_ASSET_POLICIES:
                continue
            for collection in ("inputs", "outputs"):
                for asset in _entry_assets(entry, collection):
                    if asset.get("content_sha256") != content_sha256:
                        continue
                    media_type = _text(asset.get("media_type"), "asset.media_type").lower()
                    if not media_type.startswith("image/"):
                        continue
                    bucket = asset.get("object_bucket")
                    object_key = asset.get("object_key")
                    if not isinstance(bucket, str) or not bucket or not isinstance(object_key, str) or not object_key:
                        raise PublicationSnapshotInvalid("mirrorable asset omitted immutable object locator")
                    matches.append(
                        AssetLocator(
                            content_sha256=content_sha256,
                            bucket=bucket,
                            object_key=object_key,
                            media_type=media_type,
                            byte_size=_integer(asset.get("byte_size"), "asset.byte_size", minimum=1),
                        )
                    )
        if not matches:
            raise AssetNotAuthorized("asset is not in the current mirrorable publication")
        first = matches[0]
        if any(item != first for item in matches[1:]):
            raise PublicationSnapshotInvalid("same public asset hash has inconsistent immutable locators")
        return first
