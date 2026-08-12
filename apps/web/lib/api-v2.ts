export type DisplayPolicyV2 = "mirror_allowed" | "attribution_required" | "link_only";

export interface PublicOutputV2 {
  content_sha256: string;
  media_type: string;
  byte_size: number;
  ordinal: number;
  source_role: string;
  public_display_role: "public_primary" | "public_gallery";
  source_path: string;
  source_url: string;
  display_policy: DisplayPolicyV2;
}

export interface PublicationV2Response {
  state: "no_current" | "active";
  publication: null | {
    content_digest: string;
    included_count: number;
    excluded_count: number;
    reason_counts: Record<string, number>;
    completed_at: string | null;
  };
  case_count: number;
}

export interface CaseSummaryV2 {
  public_case_key: string;
  prompt_preview: string;
  source_id: string;
  display_policies: DisplayPolicyV2[];
  has_reference: boolean;
  public_output_count: number;
  tags: string[];
  primary_output: PublicOutputV2;
}

export interface CaseListV2 {
  publication: PublicationV2Response;
  total: number;
  page: number;
  page_size: number;
  cases: CaseSummaryV2[];
  facets: {
    sources: Array<{ value: string; count: number }>;
    display_policies: Array<{ value: DisplayPolicyV2; count: number }>;
    has_reference: Array<{ value: boolean; count: number }>;
    tags: Array<{ value: string; count: number }>;
  };
}

export interface PublicCaseV2 {
  public_case_key: string;
  prompt: { prompt_id: string; raw_text: string; language: string; source_path: string; source_url: string };
  source: { source_id: string; repository_id: string; revision_sha: string; source_case_key: string };
  rights: {
    repository_license: string;
    prompt_rights: "approved";
    author: string;
    original_url: string;
    evidence_url: string;
    reviewed_at: string;
  };
  tags: string[];
  generation_members: Array<{
    generation_example_id: string;
    source_claim: Record<string, unknown>;
    reference_input_count: number;
    hidden_output_count: number;
    public_outputs: PublicOutputV2[];
  }>;
  candidate_content_digest: string;
}

export interface CaseDetailV2 {
  publication: PublicationV2Response;
  case: PublicCaseV2;
}

export class ApiV2Error extends Error {
  constructor(readonly kind: "not_found" | "unavailable" | "invalid_response") {
    super(kind === "not_found" ? "案例不存在。" : "公共目录暂时不可用。");
  }
}

function apiBaseUrl(): string {
  const value = process.env.IMAGE2_API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    return parsed.toString().replace(/\/$/, "");
  } catch {
    throw new ApiV2Error("unavailable");
  }
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ApiV2Error("invalid_response");
  return value as Record<string, unknown>;
}
function array(value: unknown): unknown[] { if (!Array.isArray(value)) throw new ApiV2Error("invalid_response"); return value; }
function text(value: unknown): string { if (typeof value !== "string") throw new ApiV2Error("invalid_response"); return value; }
function number(value: unknown): number { if (typeof value !== "number" || !Number.isFinite(value)) throw new ApiV2Error("invalid_response"); return value; }
function bool(value: unknown): boolean { if (typeof value !== "boolean") throw new ApiV2Error("invalid_response"); return value; }
function policy(value: unknown): DisplayPolicyV2 {
  const item = text(value);
  if (!["mirror_allowed", "attribution_required", "link_only"].includes(item)) throw new ApiV2Error("invalid_response");
  return item as DisplayPolicyV2;
}

function output(value: unknown): PublicOutputV2 {
  const item = record(value);
  const role = text(item.public_display_role);
  if (role !== "public_primary" && role !== "public_gallery") throw new ApiV2Error("invalid_response");
  return {
    content_sha256: text(item.content_sha256), media_type: text(item.media_type), byte_size: number(item.byte_size),
    ordinal: number(item.ordinal), source_role: text(item.source_role), public_display_role: role,
    source_path: text(item.source_path), source_url: text(item.source_url), display_policy: policy(item.display_policy),
  };
}

function publication(value: unknown): PublicationV2Response {
  const item = record(value);
  const state = text(item.state);
  if (state === "no_current") return { state, publication: null, case_count: number(item.case_count) };
  if (state !== "active") throw new ApiV2Error("invalid_response");
  const version = record(item.publication);
  const counts = record(version.reason_counts);
  return {
    state,
    publication: {
      content_digest: text(version.content_digest), included_count: number(version.included_count), excluded_count: number(version.excluded_count),
      reason_counts: Object.fromEntries(Object.entries(counts).map(([key, value]) => [key, number(value)])),
      completed_at: version.completed_at === null ? null : text(version.completed_at),
    },
    case_count: number(item.case_count),
  };
}

async function request(path: string): Promise<unknown> {
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, { cache: "no-store", headers: { Accept: "application/json" } });
    if (response.status === 404) throw new ApiV2Error("not_found");
    if (!response.ok) throw new ApiV2Error("unavailable");
    return await response.json();
  } catch (error) {
    if (error instanceof ApiV2Error) throw error;
    throw new ApiV2Error("unavailable");
  }
}

export function filtersV2(searchParams: Record<string, string | string[] | undefined>) {
  const first = (name: string) => { const value = searchParams[name]; return Array.isArray(value) ? value[0] : value; };
  const page = Number(first("page") ?? "1");
  const rawPolicy = first("display_policy");
  return {
    q: first("q")?.trim() || undefined,
    source: first("source")?.trim() || undefined,
    tag: first("tag")?.trim() || undefined,
    displayPolicy: rawPolicy === "mirror_allowed" || rawPolicy === "attribution_required" || rawPolicy === "link_only" ? rawPolicy : undefined,
    hasReference: first("has_reference") === "true" ? true : first("has_reference") === "false" ? false : undefined,
    page: Number.isInteger(page) && page > 0 ? page : 1,
  };
}

export async function getCaseListV2(filters: ReturnType<typeof filtersV2>): Promise<CaseListV2> {
  const query = new URLSearchParams({ page: String(filters.page), page_size: "18" });
  if (filters.q) query.set("q", filters.q);
  if (filters.source) query.set("source", filters.source);
  if (filters.tag) query.set("tag", filters.tag);
  if (filters.displayPolicy) query.set("display_policy", filters.displayPolicy);
  if (filters.hasReference !== undefined) query.set("has_reference", String(filters.hasReference));
  const item = record(await request(`/api/v2/cases?${query}`));
  const facets = record(item.facets);
  return {
    publication: publication(item.publication), total: number(item.total), page: number(item.page), page_size: number(item.page_size),
    cases: array(item.cases).map((value) => { const row = record(value); return {
      public_case_key: text(row.public_case_key), prompt_preview: text(row.prompt_preview), source_id: text(row.source_id),
      display_policies: array(row.display_policies).map(policy), has_reference: bool(row.has_reference),
      public_output_count: number(row.public_output_count), tags: array(row.tags).map(text), primary_output: output(row.primary_output),
    }; }),
    facets: {
      sources: array(facets.sources).map((value) => { const row = record(value); return { value: text(row.value), count: number(row.count) }; }),
      display_policies: array(facets.display_policies).map((value) => { const row = record(value); return { value: policy(row.value), count: number(row.count) }; }),
      has_reference: array(facets.has_reference).map((value) => { const row = record(value); return { value: bool(row.value), count: number(row.count) }; }),
      tags: array(facets.tags).map((value) => { const row = record(value); return { value: text(row.value), count: number(row.count) }; }),
    },
  };
}

export async function getCaseDetailV2(key: string): Promise<CaseDetailV2> {
  if (!/^[0-9a-f]{64}$/.test(key)) throw new ApiV2Error("not_found");
  const item = record(await request(`/api/v2/cases/${key}`));
  const rawCase = record(item.case); const prompt = record(rawCase.prompt); const source = record(rawCase.source); const rights = record(rawCase.rights);
  return {
    publication: publication(item.publication),
    case: {
      public_case_key: text(rawCase.public_case_key),
      prompt: { prompt_id: text(prompt.prompt_id), raw_text: text(prompt.raw_text), language: text(prompt.language), source_path: text(prompt.source_path), source_url: text(prompt.source_url) },
      source: { source_id: text(source.source_id), repository_id: text(source.repository_id), revision_sha: text(source.revision_sha), source_case_key: text(source.source_case_key) },
      rights: { repository_license: text(rights.repository_license), prompt_rights: "approved", author: text(rights.author), original_url: text(rights.original_url), evidence_url: text(rights.evidence_url), reviewed_at: text(rights.reviewed_at) },
      tags: array(rawCase.tags).map(text),
      generation_members: array(rawCase.generation_members).map((value) => { const member = record(value); return {
        generation_example_id: text(member.generation_example_id), source_claim: record(member.source_claim),
        reference_input_count: number(member.reference_input_count), hidden_output_count: number(member.hidden_output_count),
        public_outputs: array(member.public_outputs).map(output),
      }; }),
      candidate_content_digest: text(rawCase.candidate_content_digest),
    },
  };
}
