# JoeSai fixed-commit Markdown extraction v1

`joesai-commercial-prompts` is a static second source adapter, not a generic
Markdown crawler. It reads only the registry-pinned Commit
`6f9b01fd21efbc05cfdde1176fc988013d3c4a9b`, uses safe Git mirror and detached
worktree operations, and never imports or executes upstream code, hooks,
submodules, filters, or LFS behavior.

## Source contract

`data/prompts.json` is the discovery and pairing authority. Every row must use
exactly these fields:

```text
slug, category, title, title_zh, use_case, asset_type, languages, featured,
example_image
```

Slugs, categories, and image paths are validated as safe repository-relative
values. The adapter requires the case Markdown set to equal the manifest's
`prompts/{category}/{slug}.md` paths plus the one allowlisted
`prompts/README.md`; it also requires the `assets/examples` image set to equal
the manifest `example_image` set. It never derives an image name from a slug.

Each case page must have the exact manifest-title H1 followed by `Best For`, a
single `Prompt (EN)` `text` fence, a single Chinese Prompt `text` fence, and
optionally `Why It Works`, in that order. Missing, duplicate, out-of-order, or
ambiguous headings/fences fail before package publication. The primary Prompt
is the English fence body with line endings represented as LF; its interior
content is not translated, rewritten, or replaced by title/metadata.

The adapter records three strong-pairing source locations: the manifest row,
the English Markdown fence, and the manifest-selected image. Chinese Prompt,
Best For, optional Why It Works, and the complete manifest row are retained in
the `joesai.source` namespaced extension. Source claim remains `unknown`; both
prompt and asset rights remain `unknown` evidence despite the repository's MIT
license or model-related metadata.

## Package compatibility and runtime

JoeSai publishes the existing JSON-only package layout with
`extraction-package/v1` and `extraction-metrics/v1`. The package verifier
accepts only the explicit static schema mapping for the adapter strategy;
g0dam retains its legacy `g0dam-*` schema names unchanged. All Git mirrors,
worktrees, temporary candidates, locks, packages, and test environments belong
outside the workspace under `C:/Users/admin/.codex/runtime/image2/TASK-0006`.

The formal live validator processes the full fixed 50-case source twice,
checks deterministic package files and the fixed audit aggregate, exercises
all shared extraction failure points and same-key concurrency, then imports
the package with g0dam's full 100-case package into the same isolated private
PostgreSQL/S3 inventory. It verifies every content-addressed object by download
hash, both package replays, source-domain counts, registry snapshots, unknown
rights, and cleanup of its own Compose resources. It does not authorize public
URLs, publication, APIs, a website, or a third adapter.
