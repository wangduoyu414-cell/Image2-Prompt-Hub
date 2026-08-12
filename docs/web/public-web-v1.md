# Public Web v1

`apps/web` is the minimal public, read-only Next.js catalog above the TASK-0014
API. It owns browser presentation, URL filter state, image fallback, and the
copy interaction. It does not read PostgreSQL or S3, recalculate publication or
rights state, expose an admin surface, or add a write endpoint.

## Pages and API boundary

- `/` reads `GET /api/v1/cases` on the server, displays the API's canonical
  items/count/facets, and keeps `q`, `source`, `display_policy`, `tag`,
  `has_reference_input`, and `page` in the shareable URL.
- `/cases/[canonicalKey]` reads `GET /api/v1/cases/{canonicalKey}` and shows
  the API's full `raw_text`, input/output assets, source/Commit, reviewed
  display policy, model warning, taxonomy, and every public member.
- The browser uses only same-origin `/backend/assets/{sha256}` image URLs.
  `next.config.ts` rewrites them to the private API's `/api/v1/assets/*`
  route. `link_only` never constructs that route; it shows an API-supplied
  source link/placeholder instead.

The API response remains the sole authority. The UI does not deduplicate,
infer rights, invent a model claim, or transform the original Prompt. The copy
button passes `prompt.raw_text` unchanged to the browser clipboard API and
reports success or a safe manual-copy fallback accessibly.

## Configuration and local runtime

Set `IMAGE2_API_INTERNAL_BASE_URL` before building or starting Next. It is a
server-only URL (the local default is `http://127.0.0.1:8000`) and must never
be prefixed with `NEXT_PUBLIC_`. Browser asset requests stay same-origin.

This repository keeps npm dependencies, `.next`, screenshots, logs, and
temporary browser state outside `D:/image2`. For the formal validation flow,
use an external runtime directory such as `D:/image2-runtime/TASK-0015`:

```powershell
$env:IMAGE2_WEB_RUNTIME_ROOT = 'D:\image2-runtime\TASK-0015\web-runtime'
$env:IMAGE2_WEB_EVIDENCE_DIR = 'D:\image2-runtime\TASK-0015\browser-evidence'
$env:IMAGE2_API_INTERNAL_BASE_URL = 'http://127.0.0.1:8000'
Set-Location D:\image2\apps\web
npm run validate
```

`npm run validate` copies the frozen web source to that external runtime,
installs the locked Node dependencies there, then runs tests, TypeScript, and
the production build. It removes that temporary copy even if a development
check fails. A normal interactive development server may use the same external
dependency runtime; do not retain `node_modules` or `.next` in the workspace.

## Empty and failure states

`no_current` and an active version with zero matching entries are valid public
states. The home page says `尚无可公开案例` and does not create placeholder
content. A `404`, API validation failure, timeout, or `503` becomes a stable
user-facing unavailable/missing page without the API base URL, stack trace,
DSN, bucket, object key, or credentials. An authorized image that fails to
load switches to a clear fallback. These states do not weaken the API's asset
or rights boundary.

## Acceptance commands

The offline check requires Node 24 and verifies the fixed dependency lock,
Node tests, TypeScript, and `next build`:

```powershell
Set-Location D:\image2\apps\web
npm run validate
```

The live check starts a local synthetic API, builds/starts Next production in
the external runtime, and drives a locally installed Chromium-family browser.
It verifies canonical listing/filter URL state, detail/raw Prompt/copy,
authorized image delivery, `link_only` non-request behavior, image fallback,
empty/error/404 states, mobile keyboard access, screenshots, and cleanup:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\image2-runtime\TASK-0015\venv'
$env:UV_CACHE_DIR = 'D:\image2-runtime\TASK-0015\uv-cache'
$env:TMP = 'D:\image2-runtime\TASK-0015\tmp'
$env:TEMP = $env:TMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:IMAGE2_WEB_RUNTIME_ROOT = 'D:\image2-runtime\TASK-0015\web-runtime'
$env:IMAGE2_WEB_EVIDENCE_DIR = 'D:\image2-runtime\TASK-0015\browser-evidence'
Set-Location D:\image2
uv run --frozen --no-sync python -B scripts\validate_public_web.py --json
```

The historical v1 acceptance baseline used three internal sources. The current
project has seven internal sources and Public API/Web v2 is the active consumer
contract, but no real public rights approval has been recorded. The empty v1
compatibility directory therefore remains the correct fail-closed result; its
non-empty browser flow is tested only against the local synthetic API.
