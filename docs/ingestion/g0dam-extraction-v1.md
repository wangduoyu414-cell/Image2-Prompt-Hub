# g0dam fixed-commit extraction v1

This package implements only the `g0dam-work-prompts` fixed-commit extraction
slice. It reads the active source entry from `config/sources-v1.yaml`, requires
Commit `690c2d6969a65b406b17ba7d41f18695a652c3fe`, and creates a validated
external file package for the next persistence task.

## Compatibility in the static two-adapter dispatch

The extraction pipeline now selects one of two code-owned, fixed parsers by
the registry's `adapter_strategy`: this g0dam structured-JSON parser or the
JoeSai manifest/Markdown parser. It does not dynamically import adapters or
execute source-repository extensions. The registry accepts a strategy only
when it has its one supported `structure_type`; unsupported strategies fail
before a Git snapshot is opened.

This does not change the g0dam output contract. g0dam continues to publish
`g0dam-extraction-package/v1` and `g0dam-extraction-metrics/v1`, with the same
prompt identity normalization, stable files, semantic digest, and fixed
100-case aggregate. The newer neutral package names belong only to JoeSai.

It is not an Adapter framework, database writer, object-store client, web
service, publication workflow, or implementation for another source. The
source's rights fields remain evidence only; this slice never changes
`review_required` into permission, quality approval, or automatic publication.

## Runtime boundary

All mutable state is external to the repository. The formal run uses:

```text
CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2
UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0003/venv
UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0003/uv-cache
PYTHONDONTWRITEBYTECODE=1
```

Temporary directories must also be under
`C:/Users/admin/.codex/runtime/image2/TASK-0003`. `D:/image2/.task-runs` and
`D:/image2/.work/source-audit` are historical read-only evidence. The extractor
rejects runtime data or output roots inside the repository.

## Entry point

```text
python -m ingestion extract \
  --registry config/sources-v1.yaml \
  --audit reports/source-audit-v1.json \
  --source-id g0dam-work-prompts \
  --data-root C:/external/task-0003/data \
  --output-root C:/external/task-0003/output \
  --json
```

The execution path is registry validation → safe fixed-commit mirror and
detached worktree → structured `data/prompts.json` parsing → streamed asset
checks and hashes → Adapter Output and Generation Example contract validation →
metrics and manifest → atomic publication.

Git is invoked only for mirror, fetch, tree inspection, and detached worktree
operations. It disables hooks, terminal prompts, submodules, LFS smudging and
Git filters; `.gitmodules` or a `filter=` attribute fail closed. No upstream
source code is imported or executed.

## Published package

Each idempotency key maps to one `package-<sha256>` directory below the external
output root. A published package contains only JSON:

- `adapter-output.json`
- `generation-examples/*.json`
- `metrics.json`
- `manifest.json`

The manifest enumerates every stable file with its SHA-256 and has its own
stable hash. Image bytes are streamed only long enough to validate type/size and
compute a digest; they are not retained in the package. A successful rerun with
the same semantic digest returns `verified_existing`; a different digest fails
closed. Candidate output is written under an external temporary directory and
atomically replaced only after manifest verification.

The process uses an exclusive same-key lock. Failure at adapter parsing, asset
resolution, manifest creation, or immediately before publication removes the
candidate and preserves an existing published package. A conflicting concurrent
writer receives `run_locked`.

## Fixed-contract facts

For this frozen Commit, live validation requires exactly 100 observed, exact,
paired, valid, and unique valid cases; zero broken assets; pair rate `1.0`; and
case fingerprint aggregate
`ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0`.
The top-level source `model_target` is emitted only as a `source_claimed`
literal claim. Prompt and asset rights remain `unknown` unless another task
provides a new explicit decision.
