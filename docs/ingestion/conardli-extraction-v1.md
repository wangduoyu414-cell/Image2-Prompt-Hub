# ConardLi compiled-case extraction v1

`conardli-gpt-image-2-101` is a fixed-commit static adapter for the compiled
gallery at `971b67dc8cbca8cf6eb32e196fea04bddd6abe99`. It reads only detached
snapshot files and image bytes; it never runs, installs, imports, or builds the
upstream frontend, skill, Node code, or `references/*.md` content.

## Authority and strict source shape

`src/data/cases.json` is the sole case-discovery authority. It has exactly
`generated_at`, `summary`, `categories`, `templates`, and `cases`; the fixed
Commit closes at 17 categories, 79 templates, and 162 cases. `_mapping.json`
is a required cross-check for those same cases. `INDEX.md` is present in the
strict file set but is non-authoritative because its prose count is stale.

Every case has exactly these 16 fields:

```text
brief, category, category_accent, category_label, format, has_image, id, idx,
image_url, prompt_content, prompt_path, prompt_url, template_key,
template_label, thumb_url, title
```

The adapter requires `category.ready` and `category.total` to be positive
integers equal to the actual category case count. `case.category_label` equals
`category.cn`, while `case.category_accent` and `case.template_label` equal
their indexed category/template metadata. IDs, URLs, paths, mappings, category
and template indexes, counts, and the complete `public/case` file set must all
close exactly; path escapes, symlinks, missing files, extra files, malformed
JSON, and cross-index drift fail closed.

## Logical prompt text and pairing

The canonical raw Prompt is the LF logical text in `cases.json.prompt_content`,
which is identical to the fixed Git blob. A Windows checkout may represent the
same text as CRLF (or lone CR); the shared snapshot reader reconciles only
those line endings to LF before exact comparison. It never trims, NFC
normalizes, reorders JSON, or changes any other character. A non-EOL difference
or invalid UTF-8 is a parsing failure. `prompt.raw_text` remains the manifest
value, so package identity is deterministic across checkout settings.

Each record has one primary asset:

```text
public/case/{case-id}.png → output_primary
```

The matching `-thumb.webp` is checked as a nonempty regular source file and is
retained only as a locator in `conardli.source`; it is never a second asset,
generation input/output, source file, or inventory object. Strong native
pairing evidence retains the fixed-Commit locations for the cases manifest,
mapping, Prompt, and PNG. This gives the ConardLi ImportPlan exactly 326 source
files: one manifest, one mapping, 162 Prompts, and 162 PNGs.

`conardli.source` retains necessary case/category/template metadata, current
mapping-case metadata, and locators without copying `prompt_content` or all
mapping siblings. Prompt language is `mixed`; source claim and both rights
statuses remain `unknown`. Registry `review_required` evidence and
`auto_publish=false` do not authorize publication.

## Package and live consumer

The adapter uses the explicit static strategy
`conardli_compiled_case_manifest_v1` and neutral
`extraction-package/v1` / `extraction-metrics/v1` schemas. Only the namespaced
`conardli.source` extension propagates to Generation Examples; frozen g0dam
output stays legacy-compatible and JoeSai stays neutral-compatible.

TASK-0009 validates fresh two-run extraction of g0dam (100), JoeSai (50), and
ConardLi (162), including ConardLi's five controlled failure points and
same-key concurrency. The resulting packages enter one private loopback
PostgreSQL/S3 harness with 528 source files and 312 case-level relationships.
All distinct content-addressed objects are downloaded and hashed, all three
packages replay as `verified_existing`, and the validator cleans only its own
external Git, package, Compose, credential, and temporary state. This private
ingestion result is not a rights approval, public URL, API, web, sync, or
publication decision.
