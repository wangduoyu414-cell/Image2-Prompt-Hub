# Internal review-required preview

`/internal-preview` is a loopback-only browsing surface for the seven approved
fixed-authority case sources: six continuously synchronized fixed-Commit sources
plus the one-shot Chaos fixed-history snapshot. It exists so maintainers can
inspect the real Prompt/image pairs before rights review. It is not a publication
surface and must never be used as evidence that a case is publicly approved.

The preview API is separate from Public API v2 and the v1 compatibility API:

- `apps/internal_preview` reads the existing source registry, audit record,
  adapters, and prewarmed Git mirrors.
- Its current `internal-preview-index/v2` contains 3,973 real source cases and
  9,310 output references. The review projection groups them into 3,933 exact
  Prompt groups, deduplicates repeated output hashes within each group, and
  exposes 9,286 quality-eligible output references. The historical six-source v1 cache remains a frozen
  1,513-case/1,930-output compatibility artifact and is not the current preview.
- Image bytes are read from the registered fixed Commit and verified against the
  adapter-produced SHA-256, media type, and byte size before delivery.
- Every response remains `internal_review_required`; rights values remain
  `unknown`/`review_required` and cannot activate a publication.
- `config/content-quality-v1.json` is the versioned, fixed-revision manual
  quality authority. The first complete exact-duplicate review covered 29
  groups / 69 source cases / 78 output references. Five mismatched or non-result
  captures and nineteen exact/subset/near-identical cross-source duplicates are retained as source
  evidence but isolated from the preview gallery and blocked from Publication v2.
- The service rejects non-loopback clients and returns assets with
  `Cache-Control: private, no-store`.

Current fixed-authority counts are:

| Source | Cases | Outputs |
| --- | ---: | ---: |
| `chaosrealmsai-gpt-image-2-gallery` | 2,460 | 7,380 |
| `conardli-gpt-image-2-101` | 162 | 162 |
| `erickkkyt-awesome-gptimage2-prompts` | 572 | 877 |
| `freestylefly-awesome-gpt-image-2` | 517 | 517 |
| `g0dam-work-prompts` | 100 | 100 |
| `joesai-commercial-prompts` | 50 | 50 |
| `vigozhao-ai-visual-prompt-cookbook` | 112 | 224 |
| **Total** | **3,973** | **9,310** |

Current review projection: **3,933 exact Prompt groups**, **9,286 visible output
references**, and **24 isolated source cases**. These projection counts do not
rewrite the raw source totals above.

Required external runtime configuration:

```text
IMAGE2_INTERNAL_PREVIEW_DATA_ROOT=C:\Users\admin\.codex\runtime\image2\source-git-v1
IMAGE2_INTERNAL_PREVIEW_CACHE_ROOT=C:\Users\admin\.codex\runtime\image2\internal-preview
IMAGE2_INTERNAL_PREVIEW_API_BASE_URL=http://127.0.0.1:8001
```

Keep the Python environment outside the checkout, install the locked runtime once,
and run the API on loopback:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\Users\admin\AppData\Local\image2-runtime\venv'
$env:UV_CACHE_DIR = 'C:\Users\admin\AppData\Local\image2-runtime\uv-cache'
uv sync --frozen
uv run --frozen --no-sync uvicorn apps.internal_preview.main:app --host 127.0.0.1 --port 8001
```

Run the existing Next.js application with the internal preview API base URL,
then open `http://127.0.0.1:3000/internal-preview`.

The first API read builds an external index from all seven approved snapshots.
Later starts reuse the v2 index only while the registry, audit, quality ledger,
quality schema, adapter version, source set, and fixed authorities remain unchanged. A stale six-source cache or
any authority digest mismatch is rejected and rebuilt before the service becomes
ready.

Validate the versioned quality ledger against the current fixed preview cache:

```powershell
python -m scripts.validate_content_quality --json
```

The validator uses the standard external preview cache when it exists; pass an
explicit `--index` path when validating a different fixed snapshot.
