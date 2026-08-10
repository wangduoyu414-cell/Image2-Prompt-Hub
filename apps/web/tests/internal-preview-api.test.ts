import assert from "node:assert/strict";
import test from "node:test";

import { getInternalPreviewCases, parseInternalPreviewList } from "../lib/internal-preview";

process.env.IMAGE2_INTERNAL_PREVIEW_API_BASE_URL = "http://preview.invalid";

const valid = {
  mode: "internal_review_required",
  disclaimer: "未审核",
  total: 1,
  page: 1,
  page_size: 24,
  case_count: 1513,
  output_count: 1930,
  sources: [{ value: "source-a", count: 1 }],
  cases: [
    {
      case_id: "a".repeat(64),
      source_id: "source-a",
      revision_sha: "b".repeat(40),
      source_case_key: "source-a:one",
      source_url: "https://example.invalid/source-a/one",
      prompt: "A real Prompt",
      language: "en",
      model_claims: ["gpt-image-2"],
      prompt_rights_status: "unknown",
      asset_rights_status: "unknown",
      review_state: "review_required",
      outputs: [
        {
          asset_id: "c".repeat(64),
          ordinal: 0,
          role: "output_primary",
          media_type: "image/png",
          byte_size: 1024,
          content_sha256: "d".repeat(64),
          source_url: "https://example.invalid/source-a/one.png",
        },
      ],
      output_count: 1,
    },
  ],
};

test("internal preview parser preserves review-required facts and counts", () => {
  const parsed = parseInternalPreviewList(valid);
  assert.equal(parsed.case_count, 1513);
  assert.equal(parsed.output_count, 1930);
  assert.equal(parsed.cases[0]?.review_state, "review_required");
  assert.equal(parsed.cases[0]?.outputs[0]?.asset_id, "c".repeat(64));
});

test("internal preview parser rejects public-looking or malformed responses", () => {
  assert.throws(() => parseInternalPreviewList({ ...valid, mode: "active" }));
  assert.throws(() =>
    parseInternalPreviewList({
      ...valid,
      cases: [{ ...valid.cases[0], review_state: "approved" }],
    }),
  );
});

test("internal preview client sends bounded shareable filters", async () => {
  const original = globalThis.fetch;
  let observed = "";
  globalThis.fetch = (async (input: string | URL | Request) => {
    observed = String(input);
    return Response.json(valid);
  }) as typeof fetch;
  try {
    const response = await getInternalPreviewCases({ q: "glass", source: "source-a", page: 3 });
    assert.equal(response.total, 1);
    assert.match(observed, /q=glass/);
    assert.match(observed, /source=source-a/);
    assert.match(observed, /page=3/);
    assert.match(observed, /page_size=24/);
  } finally {
    globalThis.fetch = original;
  }
});

