# Content Contract v1

`Adapter Output v1` is the producer contract for a deterministic source adapter. `Generation Example v1` is the resolved, consumer-facing evidence contract. Both contracts preserve upstream facts and evidence; neither makes classification, deduplication, quality, rights approval, visibility, or publication decisions. Those decisions remain solely in the later Publication Layer.

## Contract boundary

The only permitted progression is:

```text
registered source + fixed revision
  -> Adapter Output v1 (raw facts; asset references may be unresolved)
  -> asset/hash and pairing staging
  -> Generation Example v1 (closed resolved evidence)
  -> later content, rights, and publication layers
```

`contract_valid` means that the relevant contract's evidence requirements are met. It does not mean that content is high quality, licensed for public use, canonical, classified, or publishable.

## Common source and identity rules

- `source_id` must name an active entry in `sources-v1`; `revision_sha` must be that entry's full 40-character verified commit SHA. A branch name, tag, or moving HEAD is invalid.
- `source_case_key` is the adapter's stable case identity inside one `source_id + revision_sha`. It is derived from a native identifier or durable structural locator, never array order, time, or random data.
- A `source_location` contains at least one of `source_path` or `source_url`; `native_id` and `selector` retain local structural evidence when available.
- A raw Prompt is verbatim upstream text in `raw_text`. It is not normalized, translated, completed, or cleaned. `language: "unknown"` is valid when the source did not declare a language.
- Stable business fields are the schema version, source and revision identity, adapter identity/version, case key, raw prompt, locations, asset identifiers/roles, hashes, claims, pairing evidence, parse errors, and extensions. Runtime timestamps, log paths, retry counters, temporary files, and network telemetry are dynamic operational data and must not appear in a v1 payload or participate in identity/semantic summaries.
- Arrays must be emitted deterministically: records and parse errors by `source_case_key`, prompts/assets/generation examples by their identifier, and pairings by `prompt_id`, then asset identifier. The validator rejects duplicates and verifies repeatable summaries.

## Candidate revision authority

The v1 contract stays bound to one exact 40-character Commit; it does not admit
a branch, tag, or moving `HEAD`. Incremental sync may observe a later default-
branch Commit, but first materializes a run-scoped effective registry and audit
outside the workspace. That envelope is derived from the protected static
registry/audit plus the freshly fetched candidate SHA (and later the observed
package metrics), and is used only for that one full extraction/import run.

Consequently an Adapter Output or Generation Example emitted for a candidate
still has one exact `revision_sha`, exact raw source URLs for that SHA, and the
unchanged schema/semantic validation rules. The envelope is runtime evidence,
not a new source-admission claim. Stable update comparison intentionally omits
revision-bound URLs, locators, timestamps, and temporary paths while retaining
the Prompt, resolved asset hashes, generation/source claim, and strong pairing
facts; a pure provenance URL change is not a content modification.

## Adapter Output v1

An Adapter batch has `schema_version: "adapter-output/v1"`, `source_id`, `revision_sha`, `adapter_id`, `adapter_version`, `records`, `parse_errors`, and `coverage`.

Each entry in `records` has one raw `prompt`, one or more `asset_references`, and one or more `pairings`. Its state is either:

- `extracted_candidate`: fact extraction is recorded but later contract admission may still be required.
- `contract_valid`: the Adapter contract is closed and the record may enter asset/pairing staging.

An asset reference has an explicit role: `input_reference`, `output_primary`, or `output_secondary`. Its `resolution_state` is one of:

- `unresolved`: an adapter identified a path or URL but has not supplied a content hash. It is valid only in Adapter Output and cannot directly form a Generation Example.
- `resolved`: the reference includes a SHA-256 content hash. This only records the resolution fact; Generation Example admission still requires closed references and strong pairing.

`parse_errors` holds quarantined source cases, rather than silently discarding them. Every error has a stable case key, location, `state: "quarantined"`, machine-readable stage/code, and non-sensitive message. A case key is mutually exclusive between `records` and `parse_errors`; `coverage.input_case_count` equals `extracted_candidate_count + contract_valid_count + quarantined_count`, where the counts exactly match the record states and error array. A controlled fixture mutation may model partial success; it is marked as a contract test and is never a source-derived pilot fact.

`raw_tags` preserve only upstream tags. `source_claim` records `evidence_status` as `unknown` or `source_claimed`; a source claim is not official verification. `rights_evidence` preserves `unknown`, source-claimed, or recorded evidence plus links, but does not grant permission.

## Generation Example v1

A Generation document has `schema_version: "generation-example/v1"`, `state: "contract_valid"`, one source/revision/case identity, a `source_case_locator`, tables of `prompts` and resolved `assets`, one or more `generation_examples`, and `rights_evidence`. `not_constructible` is an explicit staging outcome—not a valid Generation Example payload—when Prompt, output asset, source binding, reference closure, resolved hash, or strong pairing is missing. The validator rejects any attempt to serialize that outcome as a completed Generation Example.

Each `generation_example` references its `prompt_id`, optional `input_asset_ids`, and at least one `output_asset_id`. Every referenced prompt and asset identifier must resolve inside the same validated document. Every output asset must be `output_primary` or `output_secondary`, carry a source location and a 64-character SHA-256, and belong to an explicit Generation Example. There is no case-level output collection that bypasses this relationship.

### Deterministic multi-output projection

One Adapter record may explicitly bind multiple output asset references. The
resolved projection keeps one Generation document for the source case and emits
one `generation_example` per bound output in deterministic source order. Each
example references the shared Prompt, exactly its own resolved output asset,
and its matching strong pairing evidence. The first output is
`output_primary`; later outputs are `output_secondary`. Asset resolution is by
`source_case_key + asset_ref_id`, so filename proximity or a legacy single-image
field cannot substitute for an explicit binding.

This is an internal evidence contract, not a public gallery decision. The
current Publication Layer still requires its existing primary-output condition
for every published Generation Example. Any future grouping or publication of
secondary outputs requires a separately reviewed public contract; adapters may
not silently promote, discard, or randomly choose outputs to satisfy that gate.

The generation `generation_claim` retains upstream model/parameter text as `unknown` or `source_claimed`. A `source_claimed` model must carry non-empty source text; a repository name, directory, Prompt, or image appearance may never create a claim. Unknown stays explicit as `null` or `unknown`.

## Pairing evidence

Every pairing has a method, status, and one or more source locations. The supported methods are:

| Method | Maximum admissible status | Meaning |
| --- | --- | --- |
| `explicit_structured_reference` | `strong` | A source structure directly binds the Prompt and asset. |
| `explicit_markdown_block` | `strong` | One explicit Markdown case block binds them. |
| `stable_native_mapping` | `strong` | A durable native path/key mapping binds them. |
| `inferred_local_order` | `review_required` | Only neighboring order suggests the mapping. |
| `ambiguous` | `ambiguous` | The mapping is not determinable. |

`confidence` is optional supporting information only. It cannot elevate a weak method. Generation Example v1 accepts only one of the first three methods with `status: "strong"`; inferred or ambiguous pairings remain quarantined/reviewable in Adapter Output and cannot cross the generation gate.

## Extensions, failures, and compatibility

- All standard objects reject unknown properties. Source-specific retained facts belong only in `extensions` under a namespaced key matching `namespace.name`; extensions cannot shadow any standard field and are not asserted downstream as verified facts.
- The contracts intentionally contain no fields for canonical decisions, classification, quality approval, rights approval, public visibility, or publication. Such fields fail closed.
- Unsupported `schema_version` values fail closed. Any incompatible change to a required field, stable identity, pairing meaning, reference closure rule, or accepted status requires a new major contract version and an explicit decision record.
- The validator is local-only and deterministic. It reads the schemas, fixture manifest, source registry/audit, and TASK-0001 quality-sample evidence; it does not fetch network resources, execute source code, or write fixture data.

## Fixture provenance and gate meaning

The three positive pilot fixtures retain one minimal real fixed-commit case each. They contain the exact source Prompt, case locator, asset path/URL, and historical Prompt/asset SHA-256 evidence, but no image bytes, full upstream prompt files, cloned repository, cache, or credentials. Their structure profiles cover structured JSON, Markdown Prompt page plus manifest, and a compiled multi-category case gallery.

The formal validator reports:

- `GATE-001`: Generation Example structure, closed references, resolved assets, strong pairing, unknown-claim handling, and rejection mutations.
- `GATE-002`: Adapter batch identity, registry/commit binding, historical TASK-0001 hash evidence, coverage/error accounting, extension/decision boundaries, and rejection mutations.
- `GATE-003`: projection of each valid Adapter record through resolved staging into its paired Generation Example, with unresolved/weak/error leakage blocked.

Passing these gates freezes the contracts only. It does not implement an adapter, database, website, image download pipeline, legal assessment, or publishing chain.
