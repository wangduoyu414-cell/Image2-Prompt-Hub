import assert from "node:assert/strict";
import test from "node:test";

import { parseAdminSession, parseOperationsStatus, parseReviewQueue, parseReviewSubject } from "../lib/admin";

test("admin parsers preserve authenticated identity and explicit review facts", () => {
  const session = parseAdminSession({
    authenticated: true,
    user: { username: "reviewer", role: "reviewer" },
    csrf_token: "csrf-token-value",
    expires_at: 123456,
  });
  assert.equal(session.user.username, "reviewer");
  assert.equal(session.user.role, "reviewer");

  const queue = parseReviewQueue({
    subject_count: 1,
    output_count: 3,
    filtered_count: 1,
    state_counts: { pending: 1, review_required: 0, publishable: 0, internal_only: 0, blocked: 0 },
    items: [
      {
        source_case_version_id: 7,
        source_id: "source",
        source_case_key: "source:case",
        revision_sha: "a".repeat(40),
        prompt_preview: "Prompt",
        output_count: 3,
        state: "pending",
        latest_batch_id: null,
      },
    ],
    limit: 50,
    offset: 0,
  });
  assert.equal(queue.items[0].output_count, 3);

  const subject = parseReviewSubject({
    state: "pending",
    case_facts: {
      source_case_version_id: 7,
      source: { source_id: "source", repository_id: "1", revision_sha: "a".repeat(40), source_case_key: "source:case" },
      prompt: { prompt_id: "prompt:1", raw_text: "Prompt", language: "en", source_path: "meta.json", source_url: "https://example.com/meta.json" },
      existing_rights_evidence: { prompt_rights_status: "unknown" },
      generations: [
        {
          generation_example_row_id: 9,
          generation_example_id: "generation:1",
          source_claim: { model_raw: "gpt-image-2" },
          inputs: [],
          outputs: [
            {
              generation_output_id: 11,
              ordinal: 0,
              source_role: "output_primary",
              content_sha256: "b".repeat(64),
              media_type: "image/webp",
              byte_size: 1024,
              source_path: "image.webp",
              source_url: "https://example.com/image.webp",
            },
          ],
        },
      ],
    },
    latest_review: null,
    review_defaults: { repository_license: "MIT", original_url: "https://example.com/meta.json", evidence_url: "https://example.com/LICENSE", author: null },
  });
  assert.equal(subject.case_facts.generations[0].outputs[0].generation_output_id, 11);
  assert.equal(subject.review_defaults.repository_license, "MIT");
});

test("operations parser preserves the seven-source runtime boundary", () => {
  const status = parseOperationsStatus({
    status: "ready",
    observed_at: "2026-08-12T00:00:00Z",
    registry_sha256: "a".repeat(64),
    eligible_source_count: 6,
    scheduler_runtime: { last_heartbeat_at: "2026-08-12T00:00:00Z", last_status: "idle", details: {}, updated_at: "2026-08-12T00:00:00Z" },
    latest_cycle: null,
    review_queue: { subject_count: 3973, output_count: 9310, state_counts: { pending: 3973 } },
    sources: [{
      source_id: "chaosrealmsai-gpt-image-2-gallery",
      status: "active",
      ingestion_mode: "fixed_history",
      sync_enabled: false,
      cadence_seconds: 604800,
      jitter_seconds: 0,
      registered_revision_sha: "b".repeat(40),
      latest_candidate_revision_sha: null,
      latest_sync_state: null,
      latest_sync_reason_code: null,
      latest_sync_error_code: null,
      latest_sync_updated_at: null,
      latest_scheduler_state: null,
      latest_scheduler_finished_at: null,
      eligible: false,
    }],
    open_alerts: [],
  });
  assert.equal(status.eligible_source_count, 6);
  assert.equal(status.sources[0].sync_enabled, false);
  assert.equal(status.sources[0].eligible, false);
  assert.equal(status.review_queue.subject_count, 3973);
  assert.equal(status.scheduler_runtime?.last_status, "idle");
  assert.throws(() => parseOperationsStatus({ ...status, sources: [{ ...status.sources[0], eligible: "false" }] }));
});

test("admin parsers reject public-looking unauthenticated or malformed data", () => {
  assert.throws(() => parseAdminSession({ authenticated: false, user: { username: "x", role: "admin" }, csrf_token: "x", expires_at: 1 }));
  assert.throws(() => parseReviewQueue({ subject_count: 0, output_count: 0, filtered_count: 0, state_counts: {}, items: [], limit: 50, offset: 0 }));
});
