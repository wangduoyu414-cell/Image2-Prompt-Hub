# Scheduler, monitoring, and source lifecycle v1

## Runtime model

The scheduler wakes every five minutes and reads `config/sources-v2.yaml`. It
queues only sources that are simultaneously `active`, `continuous`, not
one-shot, and `sync.enabled=true`. Each source keeps its own cadence and jitter
in the registry. The current authority is six continuous sources; Chaos is
fixed-history and can never enter this queue.

Redis/Dramatiq is transport only. PostgreSQL stores scheduler cycles, per-source
results, an independent scheduler heartbeat, synchronization runs, diffs,
quality-gate results, and alert state. A
PostgreSQL source lock plus the existing candidate lock make duplicate delivery
safe. One source failure is recorded and does not prevent the remaining source
messages from being dispatched or processed.

Each due cycle writes its complete source ledger in one PostgreSQL transaction
before any queue message is sent. A scheduler restart resumes an unfinished
dispatch before it considers a new cycle. Redis AOF loss or a worker crash is
recovered by redelivering queued/running rows only after the four-hour actor
limit plus a safety margin; the source lock prevents overlapping execution.
Message binding accepts a worker that starts before the scheduler persists its
Dramatiq ID, and a worker cannot move a still-dispatching cycle out of recovery
visibility. This closes the queue/worker ordering race without making Redis an
authority.

The worker reuses the existing safe `run_source` chain: exact default-branch
observation, fast-forward proof, full repository parse, stable case diff,
zero-tolerance count/removal gate, private object verification, retained Git
ref, and atomic publication behavior. `review_required` is a terminal operator
state, not an automatic retry loop.

## Monitoring and alerts

The monitor runs every five minutes and treats a missing scheduler heartbeat
for twenty minutes as stale. It checks:

- the external Web readiness aggregate;
- Publication v2 readability (`no_current` remains valid);
- one real current primary image when an active public case exists;
- scheduler-heartbeat freshness (including intentionally idle periods) and
  explicit scheduler errors or cycle partial failures;
- stuck queued/running source work;
- latest source failures and quality/count-drop review gates;
- sources that have never completed a scheduled observation.

The authenticated `/admin/operations` page combines these runtime facts with
the current rights-review queue totals, so operators can distinguish source
freshness work from the separate human publication bottleneck.

Alerts are fingerprinted in PostgreSQL. A webhook receives only the first
notification for an open fingerprint; later healthy observations resolve it,
and a future recurrence opens a new alert. The optional webhook must use HTTPS
without URL credentials. Sentry and OTLP are also external settings and remain
disabled when their environment variables are empty. `OTEL_CONSOLE_EXPORTER`
is a local diagnostic switch and should remain `false` in ordinary production.

For a deployment probe that must fail on open alerts:

```console
docker compose --env-file /secure/image2.env -f compose.prod.yaml exec \
  -e MONITOR_FAIL_ON_ALERT=true monitor python -m sync monitor-once --json
```

The CI/static durability check is:

```console
python scripts/validate_operations_runtime.py --json
```

Against a disposable migrated PostgreSQL database, add
`--database-url postgresql://...` to exercise worker-first message ordering,
cycle count closure, active-work projection, and heartbeat persistence. Live
mode intentionally requires empty operational tables and removes its own
validator facts before returning.

## Source lifecycle

The Git registry remains the lifecycle authority. Never edit running database
rows to pause or retire a source. Prepare and validate a transition with:

```console
python -m scripts.source_lifecycle \
  --source-id g0dam-work-prompts \
  --to paused \
  --reason upstream-maintenance \
  --approved-by operator-name \
  --json
```

Add `--write` only in a reviewed Git branch, inspect the exact registry diff,
run the registry/adapter validators, commit, and deploy. Allowed transitions are
`active -> paused|retired` and `paused -> active|retired`; retired is final.
Paused/retired continuous sources must have sync disabled. A fixed-history
source may be paused/retired for catalog governance, but reactivation still
keeps sync disabled and one-shot semantics intact.

Adding or replacing a source is not a lifecycle toggle. It must repeat the
fixed-version audit, quality sample, lineage/dedup analysis, adapter fixture,
rights fail-closed checks, and isolated inventory/sync validation before the
registry may mark it active. A replacement retains the prior Source Revision
and object evidence rather than rewriting history.

## Operator recovery

- `failed`: inspect the admin `/admin/operations` page and structured worker
  log, correct the external condition, then let the 30-minute retry cadence run
  or dispatch a new cycle.
- `review_required`: inspect count/removal/rights evidence; do not repeatedly
  retry the same candidate or bypass the quality gate.
- stuck queued/running: restart the worker. Dramatiq redelivery plus the source
  lock resumes safely; no second source execution may run concurrently.
- Redis loss: restore its volume when possible. PostgreSQL records remain
  authoritative; the scheduler redelivers stale queued/running rows without
  creating a second cycle.
- database/S3 failure: repair the dependency before retry. The previous ready
  inventory/publication stays current.

Back up PostgreSQL, the private S3/R2 object set, retained Git mirrors, and the
Redis AOF. Database and object backups together form the content recovery point.
