# Internal review-required preview

`/internal-preview` is a loopback-only browsing surface for the six fixed-Commit
case sources. It exists so maintainers can inspect the real Prompt/image pairs
before rights review. It is not a publication surface and must never be used as
evidence that a case is publicly approved.

The preview API is separate from Public API v1:

- `apps/internal_preview` reads the existing source registry, audit record,
  adapters, and prewarmed Git mirrors.
- Its cached index contains 1,513 real source cases and 1,930 output images.
- Image bytes are read from the registered fixed Commit and verified against the
  adapter-produced SHA-256, media type, and byte size before delivery.
- Every response remains `internal_review_required`; rights values remain
  `unknown`/`review_required` and cannot activate a publication.
- The service rejects non-loopback clients and returns assets with
  `Cache-Control: private, no-store`.

Required external runtime configuration:

```text
IMAGE2_INTERNAL_PREVIEW_DATA_ROOT=C:\Users\admin\.codex\runtime\image2\source-git-v1
IMAGE2_INTERNAL_PREVIEW_CACHE_ROOT=C:\Users\admin\.codex\runtime\image2\internal-preview
IMAGE2_INTERNAL_PREVIEW_API_BASE_URL=http://127.0.0.1:8001
```

Run the API on loopback:

```text
uv run uvicorn apps.internal_preview.main:app --host 127.0.0.1 --port 8001
```

Run the existing Next.js application with the internal preview API base URL,
then open `http://127.0.0.1:3000/internal-preview`.

The first API read builds an external index from all six fixed snapshots. Later
starts reuse the index while registry, audit, adapter version, and fixed Commits
remain unchanged.

