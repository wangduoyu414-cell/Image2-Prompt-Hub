# Public API v1

The public API is a read-only FastAPI projection of the current active Content
Core Publication Version. It does not run migrations, canonicalization, rights
review, publication build, activation, or rollback. Every request reads the
current immutable snapshot through Content Core; the API never joins inventory
tables or recalculates rights or publication eligibility.

When no active Publication Version exists, the public directory is intentionally
empty. This is a normal \`200\` response. The historical v1 acceptance baseline
used three internal sources; the current project has seven internal sources, but
the v1 compatibility current remains empty because no real public approval has
been recorded.

## Configuration

The server reads these process environment variables only when an endpoint
needs the corresponding dependency:

- \`PUBLIC_API_DATABASE_URL\` - PostgreSQL URL for the Content Core read boundary.
- \`PUBLIC_API_S3_ENDPOINT_URL\` - private S3-compatible endpoint. It must be
  HTTPS, except loopback HTTP (\`127.0.0.1\`, \`::1\`, or \`localhost\`) for local
  Compose validation.
- \`PUBLIC_API_S3_ACCESS_KEY_ID\` and \`PUBLIC_API_S3_SECRET_ACCESS_KEY\` - private
  service credentials used only by the server.
- \`PUBLIC_API_S3_REGION\` - optional region; defaults to \`us-east-1\`.

Neither configuration nor S3 bucket/object locators is returned in JSON,
headers, or error messages.

## Read endpoints

All application routes are GET-only. OpenAPI exposes no review, build,
activation, rollback, admin, upload, or other write endpoint.

| Endpoint | Result |
| --- | --- |
| \`GET /healthz\` | Process health only; no database access. |
| \`GET /readyz\` | Checks the Content Core current-publication read boundary. \`no_current\` is ready. |
| \`GET /api/v1/publication\` | Current publication metadata and unique Canonical Case count. |
| \`GET /api/v1/cases\` | Deterministic, paginated Canonical Case list with facets. |
| \`GET /api/v1/cases/{canonical_key}\` | One current Canonical Case and every public membership. |
| \`GET /api/v1/assets/{sha256}\` | A verified image only when a current snapshot authorizes mirroring. |

\`GET /api/v1/cases\` accepts:

- \`q\` (maximum 256 characters): case-insensitive substring search across raw
  Prompt, source id, reviewed author, and taxonomy tag.
- \`source\`, \`display_policy\`, \`tag\`, and \`has_reference\`: exact filters over
  the current Canonical Case grouping.
- \`page\` (1 through 10,000; default 1) and \`page_size\` (1 through 100; default
  20).

List results group by \`canonical_key\`. The stable representative is the public
membership with the smallest internal generation row, while a detail response
retains every public member in that group. Facet and total counts are calculated
over the filtered Canonical Case set, so duplicate memberships never inflate
counts. A different output remains a different Canonical Case even when its
Prompt matches another one exactly.

The public member shape includes the original raw Prompt and prompt provenance,
input and output asset provenance, source provenance, reviewed rights/display
policy, original model claim plus warning, and taxonomy. Internal database row
identifiers, S3 bucket names, and S3 object keys are deliberately omitted.

## Asset policy and integrity

An asset request first resolves the hash only from the current immutable
publication snapshot. The server calls private S3 only for entries whose
display policy is \`mirror_allowed\` or \`attribution_required\`; \`link_only\`,
old-version, unpublished, unknown, and non-image assets return \`404\` without
an object-store call.

Before a \`200\` response, the server compares S3 \`Content-Length\`,
\`Content-Type\`, downloaded byte length, and SHA-256 with the immutable snapshot.
The successful response sets the snapshot media type, quoted SHA-256 \`ETag\`,
exact \`Content-Length\`, and:

    Cache-Control: public, max-age=31536000, immutable

Objects that are missing or fail these checks return a structured \`502\`; a
database or S3 availability failure returns a structured \`503\`. Storage error
bodies are never forwarded.

## Errors and compatibility

Errors use:

    {"error":{"code":"stable_code","message":"safe public description"}}

\`422\` means a bounded request parameter is invalid, \`404\` means a case or
mirrorable current asset is absent, \`502\` means an object failed integrity, and
\`503\` means the immutable-publication or private-object dependency is
unavailable. Unexpected failures are a generic \`500\`. Responses do not include
DSNs, credentials, bucket names, object keys, stack traces, or remote error
messages.

The route prefix and response fields form the v1 consumer contract for the
next public-web slice. Content Core remains the only owner of rights,
canonicalization, immutable publication snapshots, and atomic current-pointer
changes.
