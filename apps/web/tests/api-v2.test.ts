import assert from "node:assert/strict";
import test from "node:test";

import { filtersV2 } from "../lib/api-v2";

test("public v2 filters preserve shareable bounded URL state", () => {
  assert.deepEqual(
    filtersV2({ q: "  glass  ", source: "source-a", display_policy: "link_only", has_reference: "false", page: "3" }),
    { q: "glass", source: "source-a", tag: undefined, displayPolicy: "link_only", hasReference: false, page: 3 },
  );
  assert.deepEqual(filtersV2({ display_policy: "private", has_reference: "maybe", page: "0" }), {
    q: undefined, source: undefined, tag: undefined, displayPolicy: undefined, hasReference: undefined, page: 1,
  });
});
