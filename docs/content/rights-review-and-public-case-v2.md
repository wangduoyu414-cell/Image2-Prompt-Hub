# Rights Review Queue and Public Case Candidate v2

## Status and boundary

This module provides the internal, case-level foundation for human rights review.
It does not infer or record any real approval, activate a publication, or change
Public API/Web v1. An authenticated HTTP/browser operator layer now consumes it
without replacing its transaction boundary. The current seven-source inventory is
3973 internal source cases, 9310 generation outputs, and 0 real public cases.

The authoritative review subject is one immutable
`inventory.source_case_versions.source_case_version_id`. A submission must cover
every `generation_output_id` belonging to that version exactly once. Source roles
such as `output_primary` and `output_secondary` remain immutable source facts;
the reviewer separately chooses `public_primary`, `public_gallery`, or `hidden`.
Subject inspection includes the full Prompt, every generation input and output,
their source locations and hashes, the model claim, and the existing immutable
`inventory.rights_records` evidence. Submission is rejected after a newer ready
revision supersedes that source-case version.

## Persistence and state

Migration `0005_rights_review_queue_and_public_case_v2.sql` adds two append-only
tables:

- `content.rights_review_batches_v2` stores the case-level review authority,
  reviewer evidence, idempotency key, and expected latest batch.
- `content.rights_review_output_decisions_v2` stores one rights/display/public
  role decision for each output in the case.

Submission is one PostgreSQL transaction. A shared source-project lock fences
new ready revisions against reviews, while a case-level advisory lock,
idempotency uniqueness, expected-latest comparison, cross-case guards, deferred
complete-coverage constraint, and immutable update/delete triggers prevent
partial batches, lost updates, conflicting replays, and historical rewriting.
The effective batch is the latest by `reviewed_at` and batch id. A new source
revision creates a different source-case version and therefore returns to
`pending`; historical decisions are never copied forward. An exact replay of a
previously successful idempotency key still verifies its immutable historical
batch after supersession, but a new review request for the old version is rejected.

Derived queue states are:

- `pending`: no review exists for this exact source-case version.
- `review_required`: a batch exists but does not satisfy a public outcome.
- `publishable`: Prompt rights are approved, every output is explicitly decided,
  and exactly one approved/public-policy output is `public_primary`.
- `internal_only`: the effective decision keeps the case internal.
- `blocked`: the Prompt or complete output decision blocks use.

## Candidate v2

`schemas/public-case-candidate-v2.schema.json` defines a non-activating preview.
It preserves source-case identity, Prompt provenance, all Generation members,
source roles, the authorized public output subset, redacted hidden-output
placeholders whose array length is the count, review
authority, and a deterministic content digest.

Hidden outputs are represented only by `{redacted: true}` placeholders. They do not expose output ids,
paths, URLs, object keys, buckets, or credentials. Candidate v2 never writes
Publication v1 and is not consumed by Public API/Web v1. Raw model parameters are
also excluded from the public candidate: only the validated evidence status and
model label are projected, and locator-like keys fail closed. The digest excludes
the database-generated review batch id while the visible review summary retains
that audit identity. All published provenance URLs must be public HTTPS URLs with
no embedded credentials, query string, literal IP, non-default port, localhost,
noncanonical numeric-IP notation, or known object-storage host. Projected model labels, native ids, and selectors
are metadata text rather than URL/drive/storage-locator escape hatches. Source
metadata rejects every URI-scheme form, not only `scheme://`. Source paths must remain repository-relative, including rejection of Windows drive
paths and every URI-scheme form. Both contracts reject boundary whitespace so it
cannot conceal a locator prefix. Non-publishable states contain no public output
paths or URLs; their outputs remain redacted placeholders.
Publishable schema validation also limits every Generation member to at most one
primary and exactly one member to one primary, matching the builder's global
exactly-one-primary rule.
Public identity and review-authority fields may retain normal namespaced ids such
as `prompt:sha256:...`, but reject network, executable, and private-storage URI
schemes even without `//`; raw Prompt
text remains verbatim by design. Nested browser URL wrappers, known object-storage
hosts, and credential query markers also fail closed in identity fields.

## Maintenance CLI

All commands require `CONTENT_DATABASE_URL` and return bounded JSON:

```text
python -m content list-rights-review-queue --limit 100 --offset 0 --json
python -m content inspect-rights-review-subject --source-case-version-id <id> --json
python -m content submit-rights-review --input-json <review.json> --json
python -m content inspect-rights-review-batch --batch-id <id> --json
python -m content preview-public-case-v2 --source-case-version-id <id> --json
```

There is deliberately no approve-all command and no inferred license, author,
rights status, display policy, or public primary. Review submission JSON must
provide all authority fields and all output decisions explicitly.

## Authenticated administration

`apps.admin_api` and `/admin/review` provide the real operator entry described in
`docs/content/authenticated-review-admin-v1.md`. Users and password hashes stay in
the external runtime environment. Viewer/reviewer/admin roles, signed HttpOnly
sessions, exact-origin CSRF checks, and server-bound reviewer identity protect all
review data and writes. The browser cannot supply its own reviewer or reviewed-at
value, and the admin API has no Publication activation endpoint.

## Validation evidence

The live validator is:

```text
uv run --frozen --no-sync python -B scripts/validate_rights_review_queue.py --json
```

It rebuilds the six fixed-Commit sources in an isolated PostgreSQL/object-store
runtime and verifies 1513 queue subjects, 1930 outputs, single- and multi-output
reviews, Candidate v2 schema/redaction, idempotent replay, conflicting replay,
stale expected-latest, one-winner concurrency, rollback, append-only triggers,
CLI output, and unchanged Content/API/Web v1 with 0 real public cases. Synthetic
review rows exist only in the temporary validation database and are destroyed
during cleanup.

## Handoff

Authenticated review administration is now implemented. The next product slice is
Candidate v2 API/Web consumption, multi-image public presentation, case/asset
takedown and revision re-review behavior, followed by deployment, scheduling, and
monitoring. No real approval or public activation occurs until explicit evidence
has been entered through the authenticated review workflow.
