# Content Core and Publication Version v1

Content Core is the write-side boundary between immutable `inventory` source
evidence and a future read-only API. It has no HTTP, web, image-transfer, or
automatic-rights-decision surface. The API/web layer must read only the current
completed Publication Version; it must not recompute rights or query mutable
inventory rows as a substitute for a publication snapshot.

## Authority and default state

`inventory` remains the authority for source projects, revisions, files,
prompts, assets, pairing evidence, Generation Examples, and its own rights
facts. `content` only references those rows. It does not add publication fields
to inventory and it never updates or deletes inventory evidence.

There is currently no supplied human public-rights approval for the three
registered sources. Therefore a build from real current inventory legitimately
creates a completed version with zero public entries. An empty current version
is a correct fail-closed state, not an error or a signal to infer permission.

## Exact Canonical Cases

`content.canonical_cases` groups only exact Generation Example facts. Its
stable SHA-256 key is calculated from:

- the minimally normalized original prompt (Unicode/EOL/trailing-line noise
  only; the raw prompt remains unchanged in the snapshot);
- input asset content hashes in ordinal order;
- output asset content hashes in ordinal order; and
- stable JSON of the original model/source claim.

`content.canonical_memberships` preserves every source Generation Example. Two
exact duplicates may share a Canonical Case, but the same prompt with a changed
input, output, model claim, or parameters claim gets a different Canonical
Case. Similarity, embeddings, and visual distance never auto-merge content in
v1. Canonical memberships are append-only and cannot erase source lineage.

The first canonicalization records only a deterministic `system_facet` named
`exact_generation_facts`. It does not invent semantic categories. Additional
taxonomy assignments carry taxonomy version, classifier version, source,
confidence, and evidence. A `blocked` assignment prevents publication.

## Explicit rights review

`content.rights_review_events` is an append-only human-review ledger. Each
event records repository license, prompt and asset rights states, author,
original URL, evidence URL, reviewer, timezone-aware review time, and one
display policy:

`mirror_allowed`, `attribution_required`, `link_only`, `internal_only`, or
`blocked`.

Only a latest explicit event with both prompt and asset rights equal to
`approved`, complete reviewer/evidence fields, and one of the first three
display policies can pass the public gate. Existing inventory `unknown`,
`review_required`, repository metadata, or `auto_publish=false` neither grant
nor upgrade approval. `internal_only` and `blocked` remain excluded.
Future-dated reviews are rejected at both the service and database boundary.

`link_only` snapshots retain Prompt/source metadata and source links, but omit
`object_key` and `object_bucket` from input/output assets. They cannot supply a
mirrorable asset path to a later reader.

## Publication gate and immutable snapshot

Each Generation Example is evaluated independently with stable exclusion codes.
The gate requires a Canonical membership, a non-empty raw Prompt, verified
`output_primary`, strong pairing, complete source project/Commit/file location,
an accurately representable model claim, no blocked taxonomy assignment, and a
complete explicit rights review. Every input or output asset represented in a
snapshot must also be verified. Missing evidence is excluded, never filled in
or silently downgraded.

`content.publication_entries` stores the public snapshot itself: raw Prompt,
input/output descriptions with ordinal, role, source-file path/URL and source
location, source project/Commit, rights event and display policy, model
claim/warning, taxonomy, and field provenance. It is immutable
after insertion and does not change if inventory or future review rows change.
The deterministic version digest is computed from the sorted frozen entry set.

## Explicit revision selection

Every newly built Publication Version persists an immutable selection of
`source_project_id` and `source_revision_id` rows in
`content.publication_revision_selections`. A selection may be inserted only
while its version is `building`; it must stay inside the source project's
domain, and it cannot be updated or deleted later. Publication entries are
database-checked against that frozen selection, so a version cannot silently
include a later ready inventory revision.

The legacy local Content Core command resolves one latest ready revision per
source before writing that same immutable selection. Incremental sync callers
instead supply their complete `source_id -> revision_sha` map explicitly. This
separates a candidate revision, last private inventory revision, and the
current public snapshot: they can be related but are never interchangeable.

## Atomic lifecycle

`build-publication` creates a `building` version, writes all gated entries,
computes the content digest, then marks the version `ready` in one transaction.
Any build exception rolls back; no incomplete version becomes current.

`activate-publication` and `rollback-publication` hold a PostgreSQL transaction
lock, transition the old active version to `superseded`, transition the target
completed version to `active`, update the singleton current pointer, and append
an outbox event in the same transaction. A failed activation leaves the prior
pointer, version states, entries, and outbox unchanged. Completed version data
and entries cannot be rewritten or deleted; rollback only moves the pointer to
an already complete historical snapshot.

Before moving `current`, activation compares the target version's Canonical Case
keys to the active version. If a previously public key would disappear, it
fails with `publication_public_loss`; an empty or reduced candidate cannot
replace a nonempty public version merely because it built successfully.

`activate_publication_for_sync` extends the same transaction for the sync
control plane: pointer change, outbox insert, and the matching
`sync.source_sync_runs` transition to `completed` commit together. Faults
before sync completion roll back all three facts. A later retry may reuse
immutable inventory/package evidence, but it must build a new candidate version
and cannot rewrite the old snapshot.

## Maintenance CLI

The package provides a JSON-only local maintenance boundary:

```text
python -m content canonicalize --json
python -m content record-rights-review ... --json
python -m content build-publication --json
python -m content activate-publication --version-id <id> --json
python -m content rollback-publication --version-id <id> --json
python -m content inspect-publication --json
```

It requires `CONTENT_DATABASE_URL` and emits structured status, version,
digest, inclusion/exclusion counts, and reason counts. It never prints the
database URL or credentials. Review inputs are explicit command arguments;
the CLI does not fabricate approvals.

Case-level Rights Review v2 is an additive, isolated contract documented in
`docs/content/rights-review-and-public-case-v2.md`. Its queue, batches, output
decisions, and Candidate v2 preview are not read by Publication v1 and therefore
cannot change the current Public API/Web v1 snapshot. The legacy
`record-rights-review` command remains part of the protected v1 contract.
