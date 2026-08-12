export type AdminRole = "viewer" | "reviewer" | "admin";
export type ReviewState = "pending" | "review_required" | "publishable" | "internal_only" | "blocked";

export interface AdminSession {
  authenticated: true;
  user: { username: string; role: AdminRole };
  csrf_token: string;
  expires_at: number;
}

export interface ReviewQueueItem {
  source_case_version_id: number;
  source_id: string;
  source_case_key: string;
  revision_sha: string;
  prompt_preview: string;
  output_count: number;
  state: ReviewState;
  latest_batch_id: number | null;
}

export interface ReviewQueue {
  subject_count: number;
  output_count: number;
  filtered_count: number;
  state_counts: Record<ReviewState, number>;
  items: ReviewQueueItem[];
  limit: number;
  offset: number;
}

export interface ReviewOutput {
  generation_output_id: number;
  ordinal: number;
  source_role: string;
  content_sha256: string;
  media_type: string;
  byte_size: number;
  source_path: string;
  source_url: string;
}

export interface ReviewGeneration {
  generation_example_row_id: number;
  generation_example_id: string;
  source_claim: Record<string, unknown>;
  inputs: Array<Record<string, unknown>>;
  outputs: ReviewOutput[];
}

export interface ReviewSubject {
  state: ReviewState;
  case_facts: {
    source_case_version_id: number;
    source: {
      source_id: string;
      repository_id: string;
      revision_sha: string;
      source_case_key: string;
    };
    prompt: {
      prompt_id: string;
      raw_text: string;
      language: string;
      source_path: string;
      source_url: string;
    };
    existing_rights_evidence: Record<string, unknown>;
    generations: ReviewGeneration[];
  };
  latest_review: Record<string, unknown> | null;
  review_defaults: {
    repository_license: string | null;
    original_url: string;
    evidence_url: string;
    author: string | null;
  };
}

export interface ReviewSubmissionPayload {
  source_case_version_id: number;
  idempotency_key: string;
  expected_latest_batch_id: number | null;
  repository_license: string;
  prompt_rights: "approved" | "unknown" | "internal_only" | "blocked";
  author: string;
  original_url: string;
  evidence_url: string;
  output_decisions: Array<{
    generation_output_id: number;
    asset_rights: "approved" | "unknown" | "internal_only" | "blocked";
    display_policy: "mirror_allowed" | "attribution_required" | "link_only" | "internal_only" | "blocked";
    public_display_role: "public_primary" | "public_gallery" | "hidden";
    decision_note: string;
  }>;
  review_note: string;
}

export interface PublicationAdminStatus {
  current: Record<string, unknown>;
  takedowns: { total: number; items: Array<Record<string, unknown>> };
  revision_selection: Record<string, string>;
}

export class AdminApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("invalid admin response");
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  if (typeof value !== "string") throw new Error("invalid admin text");
  return value;
}

function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error("invalid admin number");
  return value;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error("invalid admin array");
  return value;
}

function nullableNumber(value: unknown): number | null {
  return value === null ? null : number(value);
}

function reviewState(value: unknown): ReviewState {
  const state = text(value);
  if (!["pending", "review_required", "publishable", "internal_only", "blocked"].includes(state)) {
    throw new Error("invalid review state");
  }
  return state as ReviewState;
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/admin-backend/${path.replace(/^\//, "")}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
  });
  const value = await response.json().catch(() => null);
  if (!response.ok) {
    const error = value && typeof value === "object" ? record(record(value).error) : {};
    throw new AdminApiError(
      typeof error.code === "string" ? error.code : "admin_unavailable",
      typeof error.message === "string" ? error.message : "审核后台暂时不可用。",
      response.status,
    );
  }
  return value;
}

export function parseAdminSession(value: unknown): AdminSession {
  const item = record(value);
  const user = record(item.user);
  const role = text(user.role);
  if (!["viewer", "reviewer", "admin"].includes(role)) throw new Error("invalid admin role");
  if (item.authenticated !== true) throw new Error("invalid admin session");
  return {
    authenticated: true,
    user: { username: text(user.username), role: role as AdminRole },
    csrf_token: text(item.csrf_token),
    expires_at: number(item.expires_at),
  };
}

export function parseReviewQueue(value: unknown): ReviewQueue {
  const item = record(value);
  const counts = record(item.state_counts);
  return {
    subject_count: number(item.subject_count),
    output_count: number(item.output_count),
    filtered_count: number(item.filtered_count),
    state_counts: {
      pending: number(counts.pending),
      review_required: number(counts.review_required),
      publishable: number(counts.publishable),
      internal_only: number(counts.internal_only),
      blocked: number(counts.blocked),
    },
    items: array(item.items).map((value) => {
      const row = record(value);
      return {
        source_case_version_id: number(row.source_case_version_id),
        source_id: text(row.source_id),
        source_case_key: text(row.source_case_key),
        revision_sha: text(row.revision_sha),
        prompt_preview: text(row.prompt_preview),
        output_count: number(row.output_count),
        state: reviewState(row.state),
        latest_batch_id: nullableNumber(row.latest_batch_id),
      };
    }),
    limit: number(item.limit),
    offset: number(item.offset),
  };
}

export function parseReviewSubject(value: unknown): ReviewSubject {
  const item = record(value);
  const facts = record(item.case_facts);
  const source = record(facts.source);
  const prompt = record(facts.prompt);
  const defaults = record(item.review_defaults);
  return {
    state: reviewState(item.state),
    case_facts: {
      source_case_version_id: number(facts.source_case_version_id),
      source: {
        source_id: text(source.source_id),
        repository_id: text(source.repository_id),
        revision_sha: text(source.revision_sha),
        source_case_key: text(source.source_case_key),
      },
      prompt: {
        prompt_id: text(prompt.prompt_id),
        raw_text: text(prompt.raw_text),
        language: text(prompt.language),
        source_path: text(prompt.source_path),
        source_url: text(prompt.source_url),
      },
      existing_rights_evidence: record(facts.existing_rights_evidence),
      generations: array(facts.generations).map((value) => {
        const generation = record(value);
        return {
          generation_example_row_id: number(generation.generation_example_row_id),
          generation_example_id: text(generation.generation_example_id),
          source_claim: record(generation.source_claim),
          inputs: array(generation.inputs).map(record),
          outputs: array(generation.outputs).map((value) => {
            const output = record(value);
            return {
              generation_output_id: number(output.generation_output_id),
              ordinal: number(output.ordinal),
              source_role: text(output.source_role),
              content_sha256: text(output.content_sha256),
              media_type: text(output.media_type),
              byte_size: number(output.byte_size),
              source_path: text(output.source_path),
              source_url: text(output.source_url),
            };
          }),
        };
      }),
    },
    latest_review: item.latest_review === null ? null : record(item.latest_review),
    review_defaults: {
      repository_license: defaults.repository_license === null ? null : text(defaults.repository_license),
      original_url: text(defaults.original_url),
      evidence_url: text(defaults.evidence_url),
      author: defaults.author === null ? null : text(defaults.author),
    },
  };
}

export async function getAdminSession(): Promise<AdminSession> {
  return parseAdminSession(await request("session"));
}

export async function loginAdmin(username: string, password: string): Promise<AdminSession> {
  return parseAdminSession(
    await request("session/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  );
}

export async function logoutAdmin(csrfToken: string): Promise<void> {
  await request("session/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
}

export async function getReviewQueue(state: ReviewState | "", offset: number): Promise<ReviewQueue> {
  const query = new URLSearchParams({ limit: "50", offset: String(Math.max(0, offset)) });
  if (state) query.set("state", state);
  return parseReviewQueue(await request(`review-queue?${query.toString()}`));
}

export async function getReviewSubject(sourceCaseVersionId: number): Promise<ReviewSubject> {
  return parseReviewSubject(await request(`review-subjects/${sourceCaseVersionId}`));
}

export async function submitReview(payload: ReviewSubmissionPayload, csrfToken: string): Promise<Record<string, unknown>> {
  return record(
    await request("reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    }),
  );
}

export async function getCandidatePreview(sourceCaseVersionId: number): Promise<Record<string, unknown>> {
  return record(await request(`review-subjects/${sourceCaseVersionId}/candidate`));
}

export async function getPublicationV2Status(): Promise<PublicationAdminStatus> {
  const item = record(await request("publication-v2"));
  const takedowns = record(item.takedowns);
  const selection = record(item.revision_selection);
  return {
    current: record(item.current),
    takedowns: { total: number(takedowns.total), items: array(takedowns.items).map(record) },
    revision_selection: Object.fromEntries(Object.entries(selection).map(([key, value]) => [key, text(value)])),
  };
}

async function mutatePublication(path: string, body: Record<string, unknown>, csrfToken: string): Promise<Record<string, unknown>> {
  return record(await request(path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: JSON.stringify(body) }));
}

export function buildPublicationV2(idempotencyKey: string, csrfToken: string) {
  return mutatePublication("publication-v2/build", { idempotency_key: idempotencyKey }, csrfToken);
}
export function activatePublicationV2(versionId: number, csrfToken: string) {
  return mutatePublication("publication-v2/activate", { publication_version_v2_id: versionId }, csrfToken);
}
export function rollbackPublicationV2(versionId: number, csrfToken: string) {
  return mutatePublication("publication-v2/rollback", { publication_version_v2_id: versionId }, csrfToken);
}
export function recordTakedownV2(payload: Record<string, unknown>, csrfToken: string) {
  return mutatePublication("takedowns-v2", payload, csrfToken);
}
