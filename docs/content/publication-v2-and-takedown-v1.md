# Publication v2 and takedown timeline

## Boundary

Publication v2 is the immutable public snapshot for reviewed Public Case
Candidate v2 documents. It is additive: Publication v1 and its current pointer
remain unchanged for compatibility, while the current public API/Web v2 consumer
reads only the independently activated v2 pointer.

The write path is:

```text
latest ready source revision
→ latest complete case-level rights review
→ validated publishable Candidate v2
→ active takedown projection
→ immutable Publication v2 version
→ explicit atomic activation or rollback
```

No review is inferred. A case with no latest publishable batch is recorded as an
exclusion. The real seven-source inventory therefore still produces zero public
entries until authorized reviewers enter evidence-backed decisions.

## Immutable authority

Migration `0006_publication_v2_and_takedown.sql` adds:

- version, explicit revision-selection, entry, current-pointer and outbox tables;
- a private asset delivery manifest separate from the public JSON snapshot;
- one immutable exclusion row for every selected case that is not published;
- an append-only takedown/restore timeline and version-bound application rows.

The public snapshot contains the full original Prompt, source `raw_tags`, the
reviewed public output subset, redacted hidden-output and reference-input counts,
source/Commit, model claim and public review evidence. Internal database row ids,
review batch id and reviewer login identity stay outside the public JSON. It also
contains no bucket, object key or credential.
Mirrorable object locators exist only in the private asset manifest and database
triggers verify them against immutable inventory and the public output facts.

`public_case_key` is stable across source revisions and re-review: it is derived
from `source_id + source_case_key`. Candidate content and review changes produce
a new snapshot digest without breaking the case URL. A new ready source revision
never inherits the prior review, so it remains excluded until explicitly
reviewed again.

Build and activation share the existing per-source ready/review advisory lock,
then the takedown lock. Activation rechecks that each selected revision is still
the latest ready authority and every entry still points to the latest review
batch. The version is closed only when entry, exclusion and private asset counts
all agree with its immutable metadata and digest.

## Takedown and correction

Supported scopes are `asset`, `prompt`, `case`, and `source`. Case scope keys use
`<source_id>:<source_case_key>`; Prompt keys use `<source_id>:<prompt_id>`;
asset keys use lowercase SHA-256. Every action is an append-only `remove` or
`restore` event with evidence, actor, note and timezone-aware timestamp.

A build applies the latest action per exact scope:

- source, case and Prompt removals exclude the complete case;
- removal of the reviewed public primary excludes the complete case;
- removal of a public gallery image keeps the case, redacts that output and
  records the exact takedown application outside the public JSON snapshot;
- a later `restore` makes the scope eligible in the next built version.

Historical versions are never edited. Activation rejects accidental case loss;
removal is permitted only when the effective takedown timeline authorizes it.
Rollback may restore an earlier completed version only when it does not contain
content under a currently active takedown.

## Maintenance commands

All commands require `CONTENT_DATABASE_URL` and are JSON-only:

```text
python -m content build-publication-v2 --revision-selection-json <json> --created-by <actor> --idempotency-key <key> --json
python -m content activate-publication-v2 --version-id <id> --json
python -m content rollback-publication-v2 --version-id <id> --json
python -m content inspect-publication-v2 --json
python -m content record-takedown-v2 ... --json
python -m content list-takedowns-v2 --json
```

Authenticated publication/takedown controls and the read-only Public API/Web v2
consumer are implemented. This boundary still does not manufacture the first
real approval: without evidence-backed human decisions, a build remains empty
and no public content is activated.

The isolated migration/fail-closed validator is:

```text
python -B scripts/validate_publication_v2.py --json
```
