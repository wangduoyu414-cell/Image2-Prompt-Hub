# Incremental Source Sync v1

`sync` is the control plane for one registered source at a time. It does not
change source admission, parse upstream code, decide rights, or expose an HTTP
surface. It composes the existing fixed-snapshot extraction, private inventory
import, and Content Core publication boundaries.

## Authority

`config/sources-v1.yaml` and `reports/source-audit-v1.json` are the current
versioned admission authority. A sync invocation first observes the configured default
branch through the production Git mirror, resolves it to one full Commit SHA,
and records that SHA as the candidate. A branch name or moving `HEAD` is never
used as extraction authority.

For that candidate only, `sync.revision` writes an effective registry and audit
envelope below the caller-provided external evidence root. The envelope differs
only in the selected source's fixed Commit and, after extraction, its observed
metrics. It is deterministically reconstructible from the static files, the
fetched Commit, and the immutable package metrics; it is not a new admission
record and is never written back into the workspace.

The Git boundary remains the owner of clone, fetch, safe-tree, detached
worktree, and retained-reference side effects. Successful imports retain
`refs/image2-retained/<source-id>/<commit>` in the external mirror. Temporary
worktrees are always removed. Hooks, submodules, LFS filters, and source code
execution remain disabled.

## One-source JSON CLI

The maintenance interface has no implicit all-source loop:

```text
python -m sync run-source --source-id <registered-source-id> --json
python -m sync inspect-source --source-id <registered-source-id> --json
```

`run-source` reads these environment variables without printing their values:

```text
SYNC_DATABASE_URL
SYNC_S3_ENDPOINT_URL
SYNC_S3_BUCKET
SYNC_S3_ACCESS_KEY_ID
SYNC_S3_SECRET_ACCESS_KEY
SYNC_GIT_DATA_ROOT
SYNC_PACKAGE_ROOT
SYNC_EVIDENCE_ROOT
```

All mutable roots must be outside the workspace. The result reports only stable
source/candidate identity, status, diff, quality gate, publication identifiers,
and non-sensitive error/reason codes.

## State, diff, and recovery

`sync.source_sync_runs` persists the candidate-specific idempotency key,
previous revision, authority digest facts, package/inventory identifiers,
diff/metrics, gate result, publication link, and terminal state. It is mutable
operational control state; immutable source facts remain in `inventory`.

The normal path is:

```text
detect exact branch Commit
→ fast-forward proof
→ full fixed-Commit extraction
→ stable set diff and quality gate
→ private inventory import
→ retained Git ref
→ explicit publication revision selection
→ build / current pointer / outbox / sync completion transaction
```

Diff identity is `source_case_key`. A case is `modified` only when its raw
Prompt, resolved input/output hashes, generation/source claim, or strong
pairing facts change. Revision-bound raw URLs, source paths, timestamps, and
other operational provenance do not turn an otherwise unchanged case into a
modification. There is no Markdown patching: every candidate is fully parsed.

`no_change` is a no-write result when the observed SHA equals the last ingested
candidate. Removed identities append immutable `sync.case_tombstone_events`.
Any count decline, removed case, broken asset, insufficient case count/pair
rate, non-fast-forward history, public loss, or failed boundary stops automatic
publication. Candidate packages and ready private inventory can remain for a
same-candidate retry, but a failed run never changes the current publication.
Stable PostgreSQL advisory locks reject a second writer for the same candidate.

## Publication selection and rights

Before a build, sync passes an explicit `source_id -> revision_sha` selection
to Content Core. The active selection is carried forward and only the candidate
source revision is substituted. This prevents an implicit query over every
ready inventory run from changing a public snapshot.

Source inventory rights are evidence only. New Generation Examples do not
inherit rights-review events from an earlier revision. A candidate can publish
only after its own explicit review events satisfy the existing Content Core
gate. Before activation, Content Core compares the target Canonical Case set
with the current public set; any loss is `public_loss` and leaves `current`,
outbox, and prior publication unchanged.

The successful activation transaction writes the new current pointer, its
outbox event, and `sync.source_sync_runs.state=completed` together. Faults
before or after the outbox insertion roll the entire transaction back, leaving
the preceding active version usable.

## Phase 2 six-source activation

The control plane now recognizes the six active registry entries: g0dam,
JoeSai, ConardLi, freestylefly, erickkkyt, and VigoZhao. Each remains an
independent `run-source` domain with its own fixed Commit, Adapter strategy,
lock, diff, quality gate, evidence root, and retained ref. There is still no
implicit all-source production loop.

Multi-output sources do not alter sync identity. Diff identity remains
`source_case_key`, while its semantic digest includes the deterministic ordered
set of resolved output hashes. Reordering, dropping, adding, or changing an
output therefore changes that case; repeating the same fixed Commit produces
`no_change`. A retry after an extraction/import failure reuses the same
candidate boundary without advancing current publication.

The six-source live closure verifies all same-Commit replays, injected recovery
for erickkkyt, failure stages and concurrent-writer rejection for VigoZhao, and
the existing Content/API/Web consumers. The resulting private inventory has
1513 cases and 1930 output relationships; rights remain review-required and
the current real public catalog remains empty.
