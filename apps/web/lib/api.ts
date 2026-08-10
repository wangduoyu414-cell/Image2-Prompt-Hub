export type DisplayPolicy = "mirror_allowed" | "attribution_required" | "link_only";

export interface PublicationVersion {
  content_digest: string;
  included_count: number;
  excluded_count: number;
  reason_counts: Record<string, number>;
  completed_at: string | null;
}

export interface PublicationResponse {
  state: "no_current" | "active";
  publication: PublicationVersion | null;
  case_count: number;
}

export interface Asset {
  content_sha256: string;
  media_type: string;
  byte_size: number;
  ordinal: number;
  role: string;
  source_path: string;
  source_url: string;
}

export interface CaseMember {
  prompt: {
    raw_text: string;
    provenance: {
      source_path: string;
      source_url: string;
    };
  };
  inputs: Asset[];
  outputs: Asset[];
  source: {
    source_id: string;
    repository_id: string;
    revision_sha: string;
    source_path: string;
    source_url: string;
  };
  rights: {
    repository_license: string;
    prompt_rights: string;
    asset_rights: string;
    author: string;
    original_url: string;
    evidence_url: string;
    reviewer: string;
    reviewed_at: string;
    display_policy: DisplayPolicy;
  };
  model: {
    source_claim: {
      evidence_status: string;
      model_raw: string | null;
      parameters_raw: Record<string, unknown>;
    };
    warning: string;
  };
  taxonomy: Array<{
    taxonomy_version: string;
    classifier_version: string;
    tag_value: string;
    tag_source: string;
    confidence: number;
  }>;
}

export interface CaseSummary {
  canonical_key: string;
  prompt_preview: string;
  source_ids: string[];
  display_policies: DisplayPolicy[];
  tags: string[];
  has_reference: boolean;
  member_count: number;
}

export interface CaseFacets {
  sources: Array<{ value: string; count: number }>;
  display_policies: Array<{ value: DisplayPolicy; count: number }>;
  tags: Array<{ value: string; count: number }>;
  has_reference: Array<{ value: boolean; count: number }>;
}

export interface CaseListResponse {
  publication: PublicationResponse;
  total: number;
  page: number;
  page_size: number;
  cases: CaseSummary[];
  facets: CaseFacets;
}

export interface CaseDetailResponse {
  publication: PublicationResponse;
  canonical_key: string;
  member_count: number;
  representative: CaseMember;
  members: CaseMember[];
}

export interface CaseFilters {
  q?: string;
  source?: string;
  displayPolicy?: DisplayPolicy;
  tag?: string;
  hasReferenceInput?: boolean;
  page?: number;
}

const REQUEST_TIMEOUT_MS = 8_000;
const MIRRORABLE_POLICIES = new Set<DisplayPolicy>(["mirror_allowed", "attribution_required"]);

export class ApiError extends Error {
  readonly status: number | null;
  readonly kind: "not_found" | "invalid_response" | "unavailable";

  constructor(kind: ApiError["kind"], status: number | null = null) {
    super(kind === "not_found" ? "The requested case is not available." : "The public directory is temporarily unavailable.");
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

function apiBaseUrl(): string {
  const configured = process.env.IMAGE2_API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const parsed = new URL(configured);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return parsed.toString().replace(/\/$/, "");
  } catch {
    throw new ApiError("unavailable");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new ApiError("invalid_response");
  }
  return value;
}

function string(value: unknown): string {
  if (typeof value !== "string") {
    throw new ApiError("invalid_response");
  }
  return value;
}

function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ApiError("invalid_response");
  }
  return value;
}

function boolean(value: unknown): boolean {
  if (typeof value !== "boolean") {
    throw new ApiError("invalid_response");
  }
  return value;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) {
    throw new ApiError("invalid_response");
  }
  return value;
}

function stringArray(value: unknown): string[] {
  return array(value).map(string);
}

function displayPolicy(value: unknown): DisplayPolicy {
  const candidate = string(value);
  if (candidate === "mirror_allowed" || candidate === "attribution_required" || candidate === "link_only") {
    return candidate;
  }
  throw new ApiError("invalid_response");
}

function canonicalKey(value: unknown): string {
  const candidate = string(value);
  if (!/^[0-9a-f]{64}$/.test(candidate)) {
    throw new ApiError("invalid_response");
  }
  return candidate;
}

function externalUrl(value: unknown): string {
  const candidate = string(value);
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return parsed.toString();
  } catch {
    throw new ApiError("invalid_response");
  }
}

function contentHash(value: unknown): string {
  const candidate = string(value);
  if (!/^[0-9a-f]{64}$/.test(candidate)) {
    throw new ApiError("invalid_response");
  }
  return candidate;
}

function mapPublication(value: unknown): PublicationResponse {
  const item = record(value);
  const state = string(item.state);
  if (state !== "active" && state !== "no_current") {
    throw new ApiError("invalid_response");
  }
  const publicationValue = item.publication;
  if (state === "no_current") {
    if (publicationValue !== null) {
      throw new ApiError("invalid_response");
    }
    return { state, publication: null, case_count: number(item.case_count) };
  }
  const publication = record(publicationValue);
  const reasonCounts = record(publication.reason_counts);
  const completedAt = publication.completed_at;
  if (completedAt !== null && typeof completedAt !== "string") {
    throw new ApiError("invalid_response");
  }
  return {
    state,
    publication: {
      content_digest: string(publication.content_digest),
      included_count: number(publication.included_count),
      excluded_count: number(publication.excluded_count),
      reason_counts: Object.fromEntries(Object.entries(reasonCounts).map(([key, count]) => [key, number(count)])),
      completed_at: completedAt,
    },
    case_count: number(item.case_count),
  };
}

function mapAsset(value: unknown): Asset {
  const item = record(value);
  return {
    content_sha256: contentHash(item.content_sha256),
    media_type: string(item.media_type),
    byte_size: number(item.byte_size),
    ordinal: number(item.ordinal),
    role: string(item.role),
    source_path: string(item.source_path),
    source_url: externalUrl(item.source_url),
  };
}

function mapMember(value: unknown): CaseMember {
  const item = record(value);
  const prompt = record(item.prompt);
  const promptProvenance = record(prompt.provenance);
  const source = record(item.source);
  const rights = record(item.rights);
  const model = record(item.model);
  const sourceClaim = record(model.source_claim);
  const modelRaw = sourceClaim.model_raw;
  if (modelRaw !== null && typeof modelRaw !== "string") {
    throw new ApiError("invalid_response");
  }
  const parameters = record(sourceClaim.parameters_raw);
  return {
    prompt: {
      raw_text: string(prompt.raw_text),
      provenance: {
        source_path: string(promptProvenance.source_path),
        source_url: externalUrl(promptProvenance.source_url),
      },
    },
    inputs: array(item.inputs).map(mapAsset),
    outputs: array(item.outputs).map(mapAsset),
    source: {
      source_id: string(source.source_id),
      repository_id: string(source.repository_id),
      revision_sha: string(source.revision_sha),
      source_path: string(source.source_path),
      source_url: externalUrl(source.source_url),
    },
    rights: {
      repository_license: string(rights.repository_license),
      prompt_rights: string(rights.prompt_rights),
      asset_rights: string(rights.asset_rights),
      author: string(rights.author),
        original_url: externalUrl(rights.original_url),
        evidence_url: externalUrl(rights.evidence_url),
      reviewer: string(rights.reviewer),
      reviewed_at: string(rights.reviewed_at),
      display_policy: displayPolicy(rights.display_policy),
    },
    model: {
      source_claim: {
        evidence_status: string(sourceClaim.evidence_status),
        model_raw: modelRaw,
        parameters_raw: parameters,
      },
      warning: string(model.warning),
    },
    taxonomy: array(item.taxonomy).map((tag) => {
      const item = record(tag);
      return {
        taxonomy_version: string(item.taxonomy_version),
        classifier_version: string(item.classifier_version),
        tag_value: string(item.tag_value),
        tag_source: string(item.tag_source),
        confidence: number(item.confidence),
      };
    }),
  };
}

function mapFacetValues(value: unknown): Array<{ value: string; count: number }> {
  return array(value).map((facet) => {
    const item = record(facet);
    return { value: string(item.value), count: number(item.count) };
  });
}

function mapCaseList(value: unknown): CaseListResponse {
  const item = record(value);
  const facets = record(item.facets);
  return {
    publication: mapPublication(item.publication),
    total: number(item.total),
    page: number(item.page),
    page_size: number(item.page_size),
    cases: array(item.cases).map((caseValue) => {
      const candidate = record(caseValue);
      return {
        canonical_key: canonicalKey(candidate.canonical_key),
        prompt_preview: string(candidate.prompt_preview),
        source_ids: stringArray(candidate.source_ids),
        display_policies: array(candidate.display_policies).map(displayPolicy),
        tags: stringArray(candidate.tags),
        has_reference: boolean(candidate.has_reference),
        member_count: number(candidate.member_count),
      };
    }),
    facets: {
      sources: mapFacetValues(facets.sources),
      display_policies: mapFacetValues(facets.display_policies).map((item) => ({ ...item, value: displayPolicy(item.value) })),
      tags: mapFacetValues(facets.tags),
      has_reference: array(facets.has_reference).map((facet) => {
        const item = record(facet);
        return { value: boolean(item.value), count: number(item.count) };
      }),
    },
  };
}

function mapCaseDetail(value: unknown): CaseDetailResponse {
  const item = record(value);
  const members = array(item.members).map(mapMember);
  const memberCount = number(item.member_count);
  if (members.length === 0 || memberCount !== members.length) {
    throw new ApiError("invalid_response");
  }
  return {
    publication: mapPublication(item.publication),
    canonical_key: canonicalKey(item.canonical_key),
    member_count: memberCount,
    representative: mapMember(item.representative),
    members,
  };
}

async function fetchPublicJson(path: string): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (response.status === 404) {
      throw new ApiError("not_found", response.status);
    }
    if (!response.ok) {
      throw new ApiError("unavailable", response.status);
    }
    try {
      return await response.json();
    } catch {
      throw new ApiError("invalid_response", response.status);
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("unavailable");
  } finally {
    clearTimeout(timeout);
  }
}

export function filtersFromSearchParams(searchParams: Record<string, string | string[] | undefined>): CaseFilters {
  const first = (name: string): string | undefined => {
    const value = searchParams[name];
    return Array.isArray(value) ? value[0] : value;
  };
  const policy = first("display_policy");
  const hasReference = first("has_reference_input");
  const page = Number(first("page") ?? "1");
  return {
    q: first("q")?.trim() || undefined,
    source: first("source")?.trim() || undefined,
    displayPolicy: policy === "mirror_allowed" || policy === "attribution_required" || policy === "link_only" ? policy : undefined,
    tag: first("tag")?.trim() || undefined,
    hasReferenceInput: hasReference === "true" ? true : hasReference === "false" ? false : undefined,
    page: Number.isInteger(page) && page >= 1 ? page : 1,
  };
}

export function buildCaseQuery(filters: CaseFilters, pageSize = 12): URLSearchParams {
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.source) query.set("source", filters.source);
  if (filters.displayPolicy) query.set("display_policy", filters.displayPolicy);
  if (filters.tag) query.set("tag", filters.tag);
  if (filters.hasReferenceInput !== undefined) query.set("has_reference", String(filters.hasReferenceInput));
  query.set("page", String(filters.page && filters.page > 0 ? filters.page : 1));
  query.set("page_size", String(pageSize));
  return query;
}

export function isMirrorablePolicy(policy: DisplayPolicy): boolean {
  return MIRRORABLE_POLICIES.has(policy);
}

export async function getCaseList(filters: CaseFilters): Promise<CaseListResponse> {
  const query = buildCaseQuery(filters);
  return mapCaseList(await fetchPublicJson(`/api/v1/cases?${query.toString()}`));
}

export async function getCaseDetail(canonicalKey: string): Promise<CaseDetailResponse> {
  if (!/^[0-9a-f]{64}$/.test(canonicalKey)) {
    throw new ApiError("not_found", 404);
  }
  return mapCaseDetail(await fetchPublicJson(`/api/v1/cases/${encodeURIComponent(canonicalKey)}`));
}
