# Public Web v2

The Next public catalog now reads `/api/v2/cases` and the stable detail route
`/api/v2/cases/{public_case_key}`. The home page is image-first, supports Prompt
and source search, source/display-policy/reference facets and pagination. Detail
pages show the complete original Prompt, copy action, every public output image,
source/Commit, rights evidence, reference-input count and model source claims.

Images use `/backend-v2/assets/{sha256}` only for mirrorable policies. A
`link_only` output renders a source-link placeholder, and an image load failure
does not weaken asset authorization. If no v2 current exists or no real review
has passed, the site shows a truthful empty state and does not fall back to
internal preview or Publication v1.

`/admin/publication` is a separate authenticated operator page. Viewer/reviewer
roles can inspect status but only `admin` can build, activate, rollback, remove
or restore. All mutations retain signed session, exact Origin and CSRF controls,
and the server binds the actor and UTC time.
