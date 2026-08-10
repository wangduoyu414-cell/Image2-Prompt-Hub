import assert from "node:assert/strict";
import test from "node:test";

import { copyRawPrompt } from "../components/copy-prompt";
import { ApiError, buildCaseQuery, filtersFromSearchParams, getCaseDetail, getCaseList } from "../lib/api";

process.env.IMAGE2_API_INTERNAL_BASE_URL = "http://synthetic.invalid";

const activePublication = {
  state: "active",
  publication: {
    content_digest: "a".repeat(64),
    included_count: 2,
    excluded_count: 0,
    reason_counts: {},
    completed_at: "2026-08-08T00:00:00+00:00",
  },
  case_count: 2,
};

const validList = {
  publication: activePublication,
  total: 2,
  page: 2,
  page_size: 12,
  cases: [
    {
      canonical_key: "b".repeat(64),
      prompt_preview: "A precise glass sculpture",
      source_ids: ["source-a"],
      display_policies: ["mirror_allowed"],
      tags: ["studio"],
      has_reference: true,
      member_count: 1,
    },
  ],
  facets: {
    sources: [{ value: "source-a", count: 1 }],
    display_policies: [{ value: "mirror_allowed", count: 1 }],
    tags: [{ value: "studio", count: 1 }],
    has_reference: [{ value: true, count: 1 }],
  },
};

function withFetch(handler: (url: string) => Response): () => void {
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: string | URL | Request) => handler(String(input))) as typeof fetch;
  return () => {
    globalThis.fetch = original;
  };
}

test("query construction maps shareable URL state to the public API fields", () => {
  const query = buildCaseQuery({
    q: "glass sculpture",
    source: "source-a",
    displayPolicy: "attribution_required",
    tag: "studio",
    hasReferenceInput: true,
    page: 3,
  });
  assert.equal(
    query.toString(),
    "q=glass+sculpture&source=source-a&display_policy=attribution_required&tag=studio&has_reference=true&page=3&page_size=12",
  );
  assert.deepEqual(
    filtersFromSearchParams({ q: "  glass  ", source: "source-a", display_policy: "link_only", has_reference_input: "false", page: "4" }),
    { q: "glass", source: "source-a", displayPolicy: "link_only", tag: undefined, hasReferenceInput: false, page: 4 },
  );
});

test("API client maps valid canonical list data without doing browser-side dedupe", async () => {
  let observedUrl = "";
  const restore = withFetch((url) => {
    observedUrl = url;
    return Response.json(validList);
  });
  try {
    const response = await getCaseList({ source: "source-a", page: 2 });
    assert.equal(response.total, 2);
    assert.equal(response.cases[0]?.canonical_key, "b".repeat(64));
    assert.match(observedUrl, /\/api\/v1\/cases\?source=source-a&page=2&page_size=12$/);
  } finally {
    restore();
  }
});

test("API errors and malformed data are reduced to stable safe client errors", async () => {
  const restoreUnavailable = withFetch(() => new Response('{"error":"postgresql://secret"}', { status: 503 }));
  try {
    await assert.rejects(getCaseList({}), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.kind, "unavailable");
      assert.doesNotMatch(error.message, /secret|postgresql/i);
      return true;
    });
  } finally {
    restoreUnavailable();
  }

  const restoreInvalid = withFetch(() => Response.json({ total: "not-a-number" }));
  try {
    await assert.rejects(getCaseList({}), (error: unknown) => error instanceof ApiError && error.kind === "invalid_response");
  } finally {
    restoreInvalid();
  }
});

test("invalid detail keys fail closed without an API request", async () => {
  let calls = 0;
  const restore = withFetch(() => {
    calls += 1;
    return Response.json(validList);
  });
  try {
    await assert.rejects(getCaseDetail("not-a-canonical-key"), (error: unknown) => error instanceof ApiError && error.kind === "not_found");
    assert.equal(calls, 0);
  } finally {
    restore();
  }
});

test("copy helper passes the raw prompt through unchanged and exposes denial", async () => {
  const rawPrompt = "Line one\r\nLine two — 原文";
  let copied = "";
  await copyRawPrompt(rawPrompt, async (value) => {
    copied = value;
  });
  assert.equal(copied, rawPrompt);
  await assert.rejects(copyRawPrompt(rawPrompt, async () => Promise.reject(new Error("denied"))));
});
