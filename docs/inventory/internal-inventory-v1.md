# Internal Source/Evidence inventory v1

`inventory` consumes one already-published extraction package and creates a
private, evidence-only PostgreSQL/S3 inventory. It is the handoff between the
fixed-commit extraction package and later Canonical, rights, taxonomy, or
publication tasks. It does not make any publication, quality, visibility,
rights-approval, classification, or Canonical decision.

## Commands and configuration

All credentials are read only from environment variables. Do not put a real
`.env` file in the repository; use the external runtime root for a temporary
Compose env file.

```text
python -m inventory migrate --migrations-dir migrations --json
python -m inventory import-package \
  --registry config/sources-v1.yaml \
  --audit reports/source-audit-v1.json \
  --package-root C:/external/published-package \
  --data-root C:/external/git-data \
  --json
python -m inventory inspect --idempotency-key <package-key> --json
```

Required environment variables:

```text
INVENTORY_DATABASE_URL
INVENTORY_S3_ENDPOINT_URL
INVENTORY_S3_BUCKET
INVENTORY_S3_ACCESS_KEY
INVENTORY_S3_SECRET_KEY
INVENTORY_S3_REGION=us-east-1
```

For formal execution, mutable runtime state is outside the workspace:

```text
CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2
UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0009/venv
UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0009/uv-cache
TMP=C:/Users/admin/.codex/runtime/image2/TASK-0009/tmp
TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0009/tmp
PYTHONDONTWRITEBYTECODE=1
```

## Import boundary and state

The importer completes the following state sequence:

```text
package_verified → source_verified → snapshot_verified → assets_verified
→ objects_ready → database_transaction → inventory_ready
```

Before any Git, S3, or PostgreSQL write, it verifies the published manifest,
all listed file hashes, package state, idempotency key, semantic digest,
Adapter Output/Generation Example contracts, cross-file references, registry
identity, fixed Commit, and audit metrics. A bad package therefore has no
persistent side effect.

Each package asset is re-read from the registry-pinned detached Git snapshot.
Its path containment, SHA-256, byte size, and media type must equal the package
evidence. The original bytes are stored only in a private generic S3 bucket at:

```text
sha256/<first-two>/<next-two>/<full-sha256>
```

There is no filename extension and no public ACL, public bucket policy, object
URL, or presigned URL. Before every write or reuse the client reads the raw
bucket-policy JSON and fail-closes on wildcard or otherwise unprovable `Allow`
principals (policy-status is only an additional signal), public bucket ACL, or
public object ACL; malformed or unrecognized ACL grants are also rejected as
unverifiable. Legacy S3-compatible responses may redact a canonical-user ID;
that private grant remains acceptable, but Group/unknown grants do not. New
objects are ACL-checked after upload; existing objects are
ACL-checked before and after download/hash verification. Plain HTTP is accepted only for literal loopback
endpoints (the isolated harness); every remote endpoint must use HTTPS.
Existing objects are downloaded and rehashed before reuse; a same-key mismatch
is `object_conflict` and is never overwritten.

Objects are written before one explicit PostgreSQL transaction. A database
failure can leave a correct, unreferenced immutable object, but it cannot leave
a `ready` adapter run or partial visible inventory. A later import strongly
verifies and may reuse that orphan. A session advisory lock derived from the
package idempotency key prevents concurrent writers; the other importer returns
`import_locked` or, after completion, `verified_existing`.

Successful commands exit `0`. Package/contract, source-asset, object,
migration, lock, and database failures use distinct non-zero codes in
`inventory.cli.EXIT_CODES`: `source_asset_mismatch` prevents an incorrect
original from entering the bucket, `object_conflict` never overwrites a
same-key mismatch, `migration_drift` rejects changed applied SQL, and the
controlled validation failures use exit codes 80–84.

## Database contract

All tables are in the `inventory` schema. Migration checksums are recorded in
`schema_migrations`; a changed applied SQL file fails with `migration_drift`.
`0002_inventory_security_integrity.sql` preserves the original `0001` checksum
while moving the complete registry snapshot to each immutable adapter run.
`source_projects` retains only stable `source_id` and `repository_id`, so a
later Commit, URL, status, or rights record can create a new immutable revision
without rewriting earlier history.

Rows preserve original raw Prompt text, locators, source claims, contract JSON,
pairing evidence, extensions, rights evidence, and the exact registry snapshot
used for the run. Natural keys—not surrogate IDs or timestamps—define business
identity. Immutable evidence rows reject updates/deletes at the database level.
Database triggers also reject a case version whose case/project, revision,
adapter run, or source file do not share one domain; they reject prompt or
asset-source files from another revision and generation prompts/assets from a
different case version. A `generation_example_id` is unique within its
`source_case_version_id`, rather than globally, so an unchanged stable case can
be re-imported under a later revision without losing either evidence record.
`inspect` returns a stable natural-key summary without
credentials, endpoint, timestamps, surrogate IDs, or temporary paths.

## Incremental revision handoff

TASK-0016 adds a separate `sync` control plane; it does not relax the generic
inventory importer or alter static source admission. For one observed candidate
Commit, sync creates a run-scoped effective registry/audit envelope outside the
workspace, then invokes the same full fixed-Commit extraction and import
boundary. The static registry and audit remain read-only, while each successful
package creates a new immutable source revision, adapter run, case version, and
Generation Example history.

`sync.source_sync_runs` is operational state linked to the ready adapter run;
`sync.case_tombstone_events` appends durable removed/restored case identity
facts. A candidate is fully reparsed and compared by `source_case_key`; no
Markdown patch is imported directly. A case-count decline, removed case,
broken asset, insufficient quality metric, or non-fast-forward history is
review-required and cannot replace an existing public snapshot. Private
inventory may still be retained for diagnosis or a same-candidate retry.

The source Git mirror and retained candidate ref remain external runtime state.
Temporary detached worktrees, authority envelopes, packages, Compose services,
credentials, and validation data stay outside the repository and are cleaned by
their owning run. No inventory row grants rights or changes the publication
selection; a later Content Core version must select source revisions explicitly
and still requires revision-local human rights review events.

## Local integration harness

`compose.yaml` exists solely for formal integration validation. It pins
PostgreSQL 18.4 and a legacy MinIO image, binds both services to `127.0.0.1`
with validator-chosen random ports and credentials, and uses a unique short-lived
Compose project. The application code uses boto3's standard S3 API only.
The fixed legacy image reports private default ACLs but does not implement ACL
mutation. The live validator records that harness capability and uses a
short-lived loopback S3 protocol probe to exercise the production client's
public-existing-object-ACL rejection path over real boto3 HTTP.

Legacy MinIO is not a production dependency or recommendation. Production S3,
R2, IAM, TLS, KMS, backup, replication, public access, and long-lived service
operation require a separate decision and task. The validator always runs
`docker compose down -v --remove-orphans` for its own project and deletes its
external package, detached worktrees, Compose env, and log state.

### Stable fixed-source mirror cache

The six-source live validator keeps its task-neutral Git mirror cache outside
the workspace at
`C:/Users/admin/.codex/runtime/image2/source-git-v1`. Before every fresh live
run it uses the production fixed-snapshot boundary to prewarm all six active
sources with a bounded timeout. Each prewarm and
every later extraction/import still performs the registered Commit fetch,
`rev-parse`, safe-tree check, and detached-worktree verification; a retained
mirror is a transfer cache, never a substitute for source authority.

Only `mirrors/*.git` plus the isolated Git config and empty hooks may persist
under that root. Temporary `worktrees/<source>/run-*` and their empty parent
directories, extraction packages,
locks, Compose containers/networks/volumes, database/S3 state, credentials,
and logs are per-run state and must be removed. If a newly absent mirror path
is left incomplete by a failed first clone, the validator removes only that
owned mirror path. A mirror that existed before prewarm is retained on failure.
Source-snapshot errors report the source id, Git error code, and bounded,
userinfo-redacted Git message so a network failure remains diagnosable without
exposing credentials.

## Explicit multi-source package compatibility

The importer remains generic and does not gain a source-specific persistence
path. Its producer-side package verifier accepts explicit schema mappings for
the six registered Adapter packages. g0dam retains its legacy package/metrics
schema names; the other sources use their registered neutral or source-specific
package/metrics mapping. All use the same Adapter Output and Generation Example
v1 contracts.

The TASK-0009 live assembly imports the fixed g0dam 100-case, JoeSai 50-case,
and ConardLi 162-case packages into one short-lived private inventory. They
remain separate source project/revision/run domains, while identical verified
content hashes can share one immutable S3 object. The three plans close at 528
source files (101 + 101 + 326) and 312 case/version/prompt/asset-source/
Generation Example/output/pairing/rights relationships. The ConardLi 326-file
plan contains its manifest, mapping, 162 canonical logical Prompts, and 162
primary PNGs; thumbnails are source metadata only and never inventory objects.

Per-run `inspect` summaries, global counts, complete content-hash-union object
download verification, and three `verified_existing` replays are required.
ConardLi's Prompt raw text is the LF manifest/Git-blob value; a CRLF checkout
is reconciled only at the text-reader boundary before exact comparison. Registry
snapshots preserve `auto_publish=false` and `review_required`; successful
private inventory does not create a publication decision or public endpoint.

## Phase 2 six-source inventory

The current fixed-source assembly imports 6 source projects/revisions/runs and
closes at 2260 source files, 1513 case/version/prompt/rights records, and 1930
Generation Example/output/pairing relationships. Asset-source relationships
also total 1930, while immutable S3 objects total 1885 because identical bytes
share one content-addressed object.

The original three sources remain single-output and preserve their historical
package digests. Freestylefly contributes 517 cases and 517 outputs; erickkkyt
contributes 572 cases and 877 outputs; VigoZhao contributes 112 cases and 224
outputs. A multi-output case remains one source case/version/Prompt but contains
one Generation document with a separate Generation Example and pairing for each
bound output asset. This changes no database schema and creates no public row.
