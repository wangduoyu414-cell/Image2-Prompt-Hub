"""Stable response contracts for the public read-only API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicModel(BaseModel):
    """Reject accidental response fields at the public API boundary."""

    model_config = ConfigDict(extra="forbid")


class ErrorBody(PublicModel):
    code: str
    message: str


class ErrorResponse(PublicModel):
    error: ErrorBody


class PublicationVersion(PublicModel):
    content_digest: str
    included_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    reason_counts: dict[str, int]
    completed_at: str | None


class PublicationResponse(PublicModel):
    state: Literal["no_current", "active"]
    publication: PublicationVersion | None
    case_count: int = Field(ge=0)


class SourceProvenance(PublicModel):
    source_id: str
    repository_id: str
    revision_sha: str
    source_path: str
    source_url: str


class PromptProvenance(PublicModel):
    source_path: str
    source_url: str


class Prompt(PublicModel):
    raw_text: str
    provenance: PromptProvenance


class Asset(PublicModel):
    content_sha256: str
    media_type: str
    byte_size: int = Field(gt=0)
    ordinal: int = Field(ge=0)
    role: str
    source_path: str
    source_url: str
    source_location: dict[str, Any]


class Rights(PublicModel):
    repository_license: str
    prompt_rights: str
    asset_rights: str
    author: str
    original_url: str
    evidence_url: str
    reviewer: str
    reviewed_at: str
    display_policy: str


class ModelClaim(PublicModel):
    evidence_status: str
    model_raw: str | None
    parameters_raw: dict[str, Any]


class ModelInfo(PublicModel):
    source_claim: ModelClaim
    warning: str


class TaxonomyTag(PublicModel):
    taxonomy_version: str
    classifier_version: str
    tag_value: str
    tag_source: str
    confidence: float


class CaseMember(PublicModel):
    prompt: Prompt
    inputs: list[Asset]
    outputs: list[Asset]
    source: SourceProvenance
    rights: Rights
    model: ModelInfo
    taxonomy: list[TaxonomyTag]


class CaseSummary(PublicModel):
    canonical_key: str
    prompt_preview: str
    source_ids: list[str]
    display_policies: list[str]
    tags: list[str]
    has_reference: bool
    member_count: int = Field(ge=1)


class FacetValue(PublicModel):
    value: str
    count: int = Field(ge=0)


class BooleanFacetValue(PublicModel):
    value: bool
    count: int = Field(ge=0)


class CaseFacets(PublicModel):
    sources: list[FacetValue]
    display_policies: list[FacetValue]
    tags: list[FacetValue]
    has_reference: list[BooleanFacetValue]


class CaseListResponse(PublicModel):
    publication: PublicationResponse
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    cases: list[CaseSummary]
    facets: CaseFacets


class CaseDetailResponse(PublicModel):
    publication: PublicationResponse
    canonical_key: str
    member_count: int = Field(ge=1)
    representative: CaseMember
    members: list[CaseMember]


class HealthResponse(PublicModel):
    status: Literal["ok"]


class ReadinessResponse(PublicModel):
    status: Literal["ready"]
    state: Literal["no_current", "active"]


class V2PublicOutput(PublicModel):
    content_sha256: str
    media_type: str
    byte_size: int = Field(gt=0)
    ordinal: int = Field(ge=0)
    source_role: str
    public_display_role: Literal["public_primary", "public_gallery"]
    source_path: str
    source_url: str
    display_policy: Literal["mirror_allowed", "attribution_required", "link_only"]


class V2CaseSummary(PublicModel):
    public_case_key: str
    prompt_preview: str
    source_id: str
    display_policies: list[str]
    has_reference: bool
    public_output_count: int = Field(ge=1)
    tags: list[str]
    primary_output: V2PublicOutput


class V2CaseFacets(PublicModel):
    sources: list[FacetValue]
    display_policies: list[FacetValue]
    has_reference: list[BooleanFacetValue]
    tags: list[FacetValue]


class V2CaseListResponse(PublicModel):
    publication: PublicationResponse
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    cases: list[V2CaseSummary]
    facets: V2CaseFacets


class V2Prompt(PublicModel):
    prompt_id: str
    raw_text: str
    language: str
    source_path: str
    source_url: str


class V2Source(PublicModel):
    source_id: str
    repository_id: str
    revision_sha: str
    source_case_key: str


class V2Rights(PublicModel):
    repository_license: str
    prompt_rights: Literal["approved"]
    author: str
    original_url: str
    evidence_url: str
    reviewed_at: str


class V2GenerationMember(PublicModel):
    generation_example_id: str
    source_claim: dict[str, Any]
    reference_input_count: int = Field(ge=0)
    hidden_output_count: int = Field(ge=0)
    public_outputs: list[V2PublicOutput]


class V2Case(PublicModel):
    public_case_key: str
    prompt: V2Prompt
    source: V2Source
    rights: V2Rights
    tags: list[str]
    generation_members: list[V2GenerationMember]
    candidate_content_digest: str


class V2CaseDetailResponse(PublicModel):
    publication: PublicationResponse
    case: V2Case
