# Authenticated Review Administration v1

## Outcome

The project now has a real browser/operator boundary over the existing immutable
case-level review service:

- FastAPI admin API under `/api/admin/v1`;
- Next.js review queue at `/admin/review` and complete case forms at
  `/admin/review/<source_case_version_id>`;
- environment-owned users with `viewer`, `reviewer`, or `admin` roles;
- scrypt password hashes, HMAC-signed short-lived sessions, HttpOnly SameSite
  cookies, exact-origin checks, CSRF tokens, and bounded login throttling;
- authenticated reviewer identity injected by the server rather than accepted
  from browser form data;
- private output delivery from content-addressed S3 after authenticated database
  lookup and full byte/hash/media-type verification;
- no approve-all endpoint, no inferred license/author/rights decision, and no
  automatic Publication activation.

The UI exposes the complete Prompt, all generation inputs/outputs, immutable
source facts, current rights evidence, the previous review batch if present, and
one explicit decision row per output. A review write still goes through
`RightsReviewStore.submit_review`, so idempotency, latest-batch conflict checks,
project/case locking, exact output coverage, append-only triggers, and revision
fencing remain the authoritative transaction boundary.

## Runtime configuration

Create each password hash outside the repository:

```powershell
py -3.12 -m apps.admin_api hash-password
```

Configure users and sessions only in the runtime environment:

```text
IMAGE2_ADMIN_USERS_JSON={"reviewer":{"role":"reviewer","password_hash":"scrypt$..."}}
IMAGE2_ADMIN_SESSION_SECRET=<at least 32 random bytes>
IMAGE2_ADMIN_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
IMAGE2_ADMIN_SECURE_COOKIES=false
IMAGE2_ADMIN_SOURCE_AUDIT=D:\image2\reports\source-audit-v2.json
IMAGE2_ADMIN_API_BASE_URL=http://127.0.0.1:8002
```

Production HTTPS must set `IMAGE2_ADMIN_SECURE_COOKIES=true` and restrict
`IMAGE2_ADMIN_ALLOWED_ORIGINS` to the exact deployed admin origin. The API also
uses the existing `CONTENT_DATABASE_URL` and private `INVENTORY_S3_*` settings.

Example local processes:

```powershell
py -3.12 -m uvicorn apps.admin_api.main:app --host 127.0.0.1 --port 8002
cd apps\web
npm run dev
```

The Next rewrite maps `/admin-backend/*` to the configured admin API. The admin
page itself contains no review data before authentication; all queue, subject,
asset, candidate, and write requests require a valid session cookie.

## Permission model

| Role | Queue/subject/assets/candidate | Submit complete review |
|---|---:|---:|
| `viewer` | yes | no |
| `reviewer` | yes | yes |
| `admin` | yes | yes |

There is no browser field for `reviewer` or `reviewed_at`. The API assigns the
authenticated username and server UTC time. State-changing requests also need
the session-bound CSRF token and an exact allowed `Origin`.

## Verified boundary

Unit/integration validation covers password hashing, signed-session tampering
and expiry, rate limiting, unauthenticated denial, viewer/reviewer separation,
CSRF denial, authenticated identity binding, logout, asset delivery, and safe
response headers. Web validation covers the admin response parsers, TypeScript,
tests, and a production Next build.

A read-only live check against the isolated Chaos inventory authenticated a real
reviewer session, read a 2460-subject/7380-output queue, inspected a three-output
case, streamed and verified its private WebP, and built a pending Candidate v2.
The check left `rights_review_batches_v2=0` and `publication_entries=0`.

No real approval has been invented. The next product stage is Public API/Web v2
consumption of explicitly publishable Candidate v2 records, including multi-image
display, revision re-review, and case/asset takedown behavior.
