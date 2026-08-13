export interface InternalPreviewAsset {
  asset_id: string;
  ordinal: number;
  role: string;
  media_type: string;
  byte_size: number;
  content_sha256: string;
  source_url: string | null;
  source_id: string;
  source_case_key: string;
  source_ids: string[];
  source_case_keys: string[];
}

export interface InternalPreviewMember {
  case_id: string;
  source_id: string;
  revision_sha: string;
  source_case_key: string;
  source_url: string;
  output_count: number;
  quality_verdict: "eligible" | "blocked" | "duplicate_only";
  quality_reason_code: string | null;
}

export interface InternalPreviewCase {
  case_id: string;
  source_id: string;
  revision_sha: string;
  source_case_key: string;
  source_url: string;
  prompt: string;
  language: string;
  model_claims: string[];
  prompt_rights_status: string;
  asset_rights_status: string;
  review_state: "review_required";
  prompt_group_id: string;
  source_ids: string[];
  member_count: number;
  eligible_member_count: number;
  excluded_member_count: number;
  members: InternalPreviewMember[];
  excluded_members: InternalPreviewMember[];
  outputs: InternalPreviewAsset[];
  output_count: number;
}

export interface InternalPreviewList {
  mode: "internal_review_required";
  disclaimer: string;
  total: number;
  page: number;
  page_size: number;
  case_count: number;
  output_count: number;
  prompt_group_count: number;
  visible_output_count: number;
  quality_exclusion_count: number;
  cases: InternalPreviewCase[];
  sources: Array<{ value: string; count: number }>;
}

export interface InternalPreviewFilters {
  q?: string;
  source?: string;
  page?: number;
}

const REQUEST_TIMEOUT_MS = 120_000;

function apiBaseUrl(): string {
  const configured = process.env.IMAGE2_INTERNAL_PREVIEW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const parsed = new URL(configured);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("Internal preview API base URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("invalid internal preview response");
  }
  return value as Record<string, unknown>;
}

function string(value: unknown): string {
  if (typeof value !== "string") throw new Error("invalid internal preview string");
  return value;
}

function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error("invalid internal preview number");
  return value;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error("invalid internal preview array");
  return value;
}

function hash(value: unknown): string {
  const candidate = string(value);
  if (!/^[0-9a-f]{64}$/.test(candidate)) throw new Error("invalid internal preview hash");
  return candidate;
}

function optionalUrl(value: unknown): string | null {
  if (value === null) return null;
  return externalUrl(value);
}

function externalUrl(value: unknown): string {
  const candidate = string(value);
  const parsed = new URL(candidate);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") throw new Error("invalid internal preview URL");
  return parsed.toString();
}

function mapAsset(value: unknown): InternalPreviewAsset {
  const item = record(value);
  return {
    asset_id: hash(item.asset_id),
    ordinal: number(item.ordinal),
    role: string(item.role),
    media_type: string(item.media_type),
    byte_size: number(item.byte_size),
    content_sha256: hash(item.content_sha256),
    source_url: optionalUrl(item.source_url),
    source_id: string(item.source_id),
    source_case_key: string(item.source_case_key),
    source_ids: array(item.source_ids).map(string),
    source_case_keys: array(item.source_case_keys).map(string),
  };
}

function mapMember(value: unknown): InternalPreviewMember {
  const item = record(value);
  const verdict = string(item.quality_verdict);
  if (!['eligible', 'blocked', 'duplicate_only'].includes(verdict)) throw new Error('invalid quality verdict');
  return {
    case_id: hash(item.case_id),
    source_id: string(item.source_id),
    revision_sha: string(item.revision_sha),
    source_case_key: string(item.source_case_key),
    source_url: externalUrl(item.source_url),
    output_count: number(item.output_count),
    quality_verdict: verdict as InternalPreviewMember['quality_verdict'],
    quality_reason_code: item.quality_reason_code === null ? null : string(item.quality_reason_code),
  };
}

function mapCase(value: unknown): InternalPreviewCase {
  const item = record(value);
  const reviewState = string(item.review_state);
  if (reviewState !== "review_required") throw new Error("internal preview case is not review-required");
  const outputs = array(item.outputs).map(mapAsset);
  const outputCount = number(item.output_count);
  if (outputs.length !== outputCount || outputs.length === 0) throw new Error("internal preview output count mismatch");
  const members = array(item.members).map(mapMember);
  const excludedMembers = array(item.excluded_members).map(mapMember);
  const memberCount = number(item.member_count);
  const eligibleMemberCount = number(item.eligible_member_count);
  const excludedMemberCount = number(item.excluded_member_count);
  if (members.length !== eligibleMemberCount || excludedMembers.length !== excludedMemberCount || memberCount !== eligibleMemberCount + excludedMemberCount) {
    throw new Error("internal preview member count mismatch");
  }
  return {
    case_id: hash(item.case_id),
    prompt_group_id: hash(item.prompt_group_id),
    source_id: string(item.source_id),
    source_ids: array(item.source_ids).map(string),
    revision_sha: string(item.revision_sha),
    source_case_key: string(item.source_case_key),
    source_url: externalUrl(item.source_url),
    prompt: string(item.prompt),
    language: string(item.language),
    model_claims: array(item.model_claims).map(string),
    prompt_rights_status: string(item.prompt_rights_status),
    asset_rights_status: string(item.asset_rights_status),
    review_state: reviewState,
    member_count: memberCount,
    eligible_member_count: eligibleMemberCount,
    excluded_member_count: excludedMemberCount,
    members,
    excluded_members: excludedMembers,
    outputs,
    output_count: outputCount,
  };
}

export function parseInternalPreviewList(value: unknown): InternalPreviewList {
  const item = record(value);
  const mode = string(item.mode);
  if (mode !== "internal_review_required") throw new Error("invalid internal preview mode");
  return {
    mode,
    disclaimer: string(item.disclaimer),
    total: number(item.total),
    page: number(item.page),
    page_size: number(item.page_size),
    case_count: number(item.case_count),
    output_count: number(item.output_count),
    prompt_group_count: number(item.prompt_group_count),
    visible_output_count: number(item.visible_output_count),
    quality_exclusion_count: number(item.quality_exclusion_count),
    cases: array(item.cases).map(mapCase),
    sources: array(item.sources).map((source) => {
      const facet = record(source);
      return { value: string(facet.value), count: number(facet.count) };
    }),
  };
}

export async function getInternalPreviewCases(filters: InternalPreviewFilters): Promise<InternalPreviewList> {
  const query = new URLSearchParams({
    page: String(filters.page && filters.page > 0 ? filters.page : 1),
    page_size: "24",
  });
  if (filters.q) query.set("q", filters.q);
  if (filters.source) query.set("source", filters.source);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${apiBaseUrl()}/api/internal-preview/v1/cases?${query.toString()}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("internal preview unavailable");
    return parseInternalPreviewList(await response.json());
  } finally {
    clearTimeout(timeout);
  }
}
