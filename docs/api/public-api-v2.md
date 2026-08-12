# Public API v2

Public API v2 is a read-only projection of `content.publication_current_v2`.
It never queries review queue state or inventory as a replacement for a frozen
publication. API v1 remains available and continues to read only v1 current.

Routes:

```text
GET /api/v2/publication
GET /api/v2/cases
GET /api/v2/cases/{public_case_key}
GET /api/v2/assets/{content_sha256}
```

The list is case-oriented rather than Generation-Example-oriented. Every item
has one reviewed `public_primary`, may expose multiple `public_gallery` outputs,
and reports only redacted counts for private reference inputs and hidden outputs.
Stable case keys survive re-review and source revisions. Asset delivery is
authorized against the current version's private asset manifest before S3 read;
`link_only` outputs never receive a mirrorable locator.

Search and facets operate only on the current immutable v2 entry set. Source raw
tags form category facets; reference requirements remain an independent boolean
facet. The public response excludes database row ids, review batch ids, reviewer
login identity, object keys and buckets. API OpenAPI remains GET/HEAD-only.
