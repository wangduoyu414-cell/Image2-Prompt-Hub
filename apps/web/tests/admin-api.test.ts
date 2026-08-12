import assert from "node:assert/strict";
import test from "node:test";

import { parseAdminSession, parseReviewQueue, parseReviewSubject } from "../lib/admin";

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

test("admin parsers reject public-looking unauthenticated or malformed data", () => {
  assert.throws(() => parseAdminSession({ authenticated: false, user: { username: "x", role: "admin" }, csrf_token: "x", expires_at: 1 }));
  assert.throws(() => parseReviewQueue({ subject_count: 0, output_count: 0, filtered_count: 0, state_counts: {}, items: [], limit: 50, offset: 0 }));
});
