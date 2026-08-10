# Source Audit v1

## Conclusion

Three independent, fixed-commit sources meet the v1 active baseline and are selected as three structurally distinct pilots. Public mirroring is disabled for every source because prompt/asset rights remain evidence states rather than legal conclusions.

## Scope and method

- Local candidate inputs: `gpt-image-2-two-track-research-2026-08-01.md` and its XLSX companion; `1.md` supplied the admission and fail-closed rules.
- Remote reads only: GitHub repository metadata, fixed default-branch commit feeds, fixed-commit file trees, and fixed raw blobs. No external repository code was executed and no external write occurred.
- Full metrics for active sources use streamed output-image SHA-256, exact normalized prompt hashes, full-collection pairing checks, and Rule-011 20-case deterministic visual samples.
- `sources-v1.yaml` is emitted in the JSON profile of YAML 1.2 so the standalone Python validator remains dependency-free.

## Active sources and pilots

| Source | Structure / pilot role | Unique valid cases | Pair rate | Broken assets | Publication |
| --- | --- | ---: | ---: | ---: | --- |
| `conardli-gpt-image-2-101` | compiled_multi_category_case_gallery | 162 | 100% | 0 | review_required; auto_publish=false |
| `g0dam-work-prompts` | structured_manifest_json | 100 | 100% | 0 | review_required; auto_publish=false |
| `joesai-commercial-prompts` | markdown_prompt_pages_with_manifest | 50 | 100% | 0 | review_required; auto_publish=false |

## Candidate coverage and dispositions

| Candidate | Scope | Status / disposition | Fixed commit | Reason |
| --- | --- | --- | --- | --- |
| `0aicoder0/gpt-image-2-prompt-gallery` | family_mapping | blocked | `ae0738b08d79f85b92e633d991e8c52a9de551a2` | Fixed-commit evidence shows all 31 gallery Markdown files match wuyoscar after only relative-image-path normalization and all shared gallery image blobs are identical. |
| `aeboli/gpt-image2-studio` | out_of_scope_mapping | excluded | `f506c3b4406c988d0d64279b480643339b647c8a` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `angchow/gpt-image-2-style-library` | out_of_scope_mapping | excluded | `9a57e7de102b50bad64545c23a006a449f67b351` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `atlascloudai/awesome-gpt-image-2-prompts` | family_mapping | blocked | `191b709200b96e3b1ae3c3d006b586668da93ec5` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `conardli/gpt-image-2-101` | full_case_audit | active | `971b67dc8cbca8cf6eb32e196fea04bddd6abe99` | Fixed-commit full metrics satisfy the 50 unique valid case and 0.90 pair-rate baseline; publication stays fail-closed pending per-asset/prompt rights review. |
| `davidwuw0811-boop/awesome-gpt-image2-prompts` | family_mapping | blocked | `228edb6341d978aa2572911adf7e7e147ebf95d3` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `eddietyp/image-prompt-library` | family_mapping | blocked | `71a17248303057b5d0b7f37ebc2562fe22028582` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `eugeniughelbur/gpt-image-cookbook` | case_audit_incomplete | probation | `1e4ae093cd26818013c5462fbdff170e51cfc0a1` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `freestylefly/awesome-gpt-image-2` | case_audit_incomplete | probation | `76fcd0e6b3961ef2b041547aac654f1efd1ef270` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `fzfzerro/image2skill` | case_audit_incomplete | probation | `9f7a5772189ec832b0e0cc5d212926908871f5f7` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `g0dam/awesome-gpt-image-2-work-prompts` | full_case_audit | active | `690c2d6969a65b406b17ba7d41f18695a652c3fe` | Fixed-commit full metrics satisfy the 50 unique valid case and 0.90 pair-rate baseline; publication stays fail-closed pending per-asset/prompt rights review. |
| `gokuscraper/gpt-image-2-prompts-skill` | out_of_scope_mapping | excluded | `5f5d0aa13371be21eeea53da60c2569c37bc8b24` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `gongnyang/gongnyang-prompt-kit` | out_of_scope_mapping | excluded | `fb5f75f2f6dbaaa649464dc089f573bea4a9ebf1` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `hurris1/gpt-image2-explorer` | family_mapping | blocked | `c9be4502520e4a0a5b15cc8d1254bd8abd660ddf` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `imaginevid/awesome-gpt-image-2-prompts-and-skills` | out_of_scope_mapping | excluded | `21b0a0444307b9380d2b34d3ca2b7a29e82f164b` | Auto-updated list/metadata project; no fixed, extractable prompt-and-output corpus was established from its current tree. |
| `jackvidal/image-prompt-architect` | out_of_scope_mapping | excluded | `unavailable` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `jau123/meigen-ai-design-mcp` | out_of_scope_mapping | excluded | `68cddce2970f58656ea0878c1d07ff1ba91cda28` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `jezweb/claude-skills` | out_of_scope_mapping | excluded | `e875a6bfff809e5d42c584104031e36e1f014f18` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `joesai/awesome-gpt-image-2-commercial-prompts` | full_case_audit | active | `6f9b01fd21efbc05cfdde1176fc988013d3c4a9b` | Fixed-commit full metrics satisfy the 50 unique valid case and 0.90 pair-rate baseline; publication stays fail-closed pending per-asset/prompt rights review. |
| `juneyaooo/gpt-image2-ppt-skills` | out_of_scope_mapping | excluded | `7c0e8772e1991af0cf052c94812ade21ad910289` | PPT workflow/implementation project, not an independently extractable long-term prompt-and-output case corpus under the no-repository-code rule. |
| `junyeo217/codex-gpt-image-2-skill` | out_of_scope_mapping | excluded | `dcabf4bb20e47b11dc470f20a69e4b652741439f` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `leonsoolab/awesome-gpt-image-2-api-and-prompts` | family_mapping | blocked | `unavailable` | Current repository URL returned 404 and the historical research maps it into the EvoLink content family; it is blocked until a stable identity and independent content proof exist. |
| `leonxlnx/taste-skill` | out_of_scope_mapping | excluded | `e988add20dab0fa97d7a76781c48961c8184288e` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `lidge-jun/ima2-gen` | out_of_scope_mapping | excluded | `f06db103539c61f2c115450a5c13f6e603af278b` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `lin351540-ship-it/prompt-atlas-jj` | family_mapping | blocked | `002f754977c4daf3c5d3da667482aa13edaeb498` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `litreily/codex-skill-eastern-beauty-director` | out_of_scope_mapping | excluded | `384210fdde84f58442215f421bb37570765f8989` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `mageia/awesome-gpt-image-2-api-and-prompts` | case_audit_incomplete | probation | `09edfcc2bcf6c7e3bbcedf7136abac136e3fd84e` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `michae1y/gpt-image2-skill-gallery` | family_mapping | blocked | `5c41386ec8e5cbcb0cd11e9636effa2bdbd79a38` | The fixed-commit README explicitly says the static site is organized from wuyoscar/GPT-Image2-Skill. |
| `ningzimu/codex-ppt-skill` | out_of_scope_mapping | excluded | `f2ed80372f65bb05fe62dd07979b239a17ac065d` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `noxx/visual-atelier-skill` | out_of_scope_mapping | excluded | `90a4b12522dc9dfcd418aa1bc6fb99dfa4714ef1` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `oakplank/claude-gpt-image-bridge` | out_of_scope_mapping | excluded | `unavailable` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `openai/codex` | out_of_scope_mapping | excluded | `2b5bdcf67547860f2e5c5a605009a70026796b2b` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `openai/openai-cookbook` | out_of_scope_mapping | excluded | `0a796c4b95457a82dc090d0e31392deaf3b07f28` | Official methods and notebooks are retained as a standards baseline, not admitted as a single long-term case corpus in sources-v1. |
| `pixmind-io/awesome-gpt-image-2-prompts` | case_audit_incomplete | probation | `4ac21d49915fffd5a5be56f2d5b674b6dda34568` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `shannon4science/postermeld` | out_of_scope_mapping | excluded | `cd4990d2b36cb437938aa87adff512df8186dfaa` | Benchmark and poster-generation implementation project; it is not a long-term prompt-and-output source registry candidate. |
| `shaowen-ye/image-prompt-builder` | out_of_scope_mapping | excluded | `0cdf78d2bb78b02a0e957a420636efaa04aac482` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `smixs/visual-skills` | out_of_scope_mapping | excluded | `75d8ce8d52e0b6ab25f28d1a07223b7611dd682a` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `stevenflyai/multi-agent-image-gen-evals` | out_of_scope_mapping | excluded | `3fd8cdcd9371f1206ad4490069f8ec0971b2dc57` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `tigerowo/awesome-gpt-image-2-prompts` | family_mapping | blocked | `60e9c65baecfd6d6d51ac4e4d87f146af834bb64` | The fixed-commit README explicitly states it is a backup of the EvoLinkAI repository; it cannot become an independent full-ingestion source. |
| `trin-zenityx/image-craft-lv` | out_of_scope_mapping | excluded | `e76c84c1566273f779e8fd0d236f82aeb66d7bba` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `verycooltimo/imagegen-skills` | out_of_scope_mapping | excluded | `b135eda638093f9ce070b4d265afbfd488349ed2` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `vigozhao/ai-visual-prompt-cookbook` | case_audit_incomplete | probation | `7c535ae274604f38d79ea5e744125f32fca756a8` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `wangnov/gpt-image-2-skill` | out_of_scope_mapping | excluded | `49b0a6b8e6692869027f9ffd39d6b8240a6b50cc` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `wuyoscar/gpt-image2-skill` | case_audit_incomplete | probation | `ecc9c5420c265f6677edc5f4d255bca02497ef71` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `yinxiaowai/awesome-gpt-image-2-vs-nano-banana-2-prompt-gallery` | case_audit_incomplete | probation | `e0c1fad883a5a1ba6e98369258d15bd32cda5a07` | Fixed repository identity and tree evidence were collected, but a complete per-case prompt/output/rights audit was not established under this v1 run. It remains non-active; no partial count is treated as an admission result. |
| `youmind-openlab/awesome-gpt-image-2` | family_mapping | blocked | `de4ce23d10c38a211f286bfa88e1aa718af9fefd` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `youmind-openlab/gpt-image-2-prompts-search` | family_mapping | blocked | `32bfbf79453e412532de5a6e100bbd9d77bf5a45` | This repository aggregates or indexes upstream material. A complete fixed-commit, per-case original-author/original-link/strong-pair proof was not established, so it remains fail-closed and provenance-only. |
| `yun-666-666/image-prompt-skill` | out_of_scope_mapping | excluded | `3535bdc94ded38235b202fd7c0b214ffe0427273` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `zhouwei713/gpt-image-2-prompting-skill` | out_of_scope_mapping | excluded | `dd0b07d763477c381288963f7073b1752af1bee0` | This repository appears only in the Skill/tool research track, not as a candidate case-source corpus; it is mapped to prevent silent omission but is excluded from sources-v1. |
| `zhuihunzhe/gpt-image2-prompt-skill` | family_mapping | blocked | `bc4b046e00a74c89756bdc62df1c5b6bce3293ca` | The fixed-commit README badges and declared case references point to freestylefly/awesome-gpt-image-2. |

## Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| GATE-001 | PASS | Candidate extraction, normalized identity union, source/exclusion zero-gap mapping |
| GATE-002 | PASS | Fixed commits, active full metrics, explicit non-active failure/provenance records |
| GATE-003 | PASS | Two schemas plus fail-closed cross-file validator |
| GATE-004 | PASS | Bidirectional audit/registry mapping and three active structural pilots |

## Known limitations and non-approvals

- Non-active records with `metrics_complete=false` are deliberately not treated as zero-case sources; their unknowns are explicit and they cannot become active through defaults.
- Mirror, backup, derived, and aggregator records are never configured for full ingestion. Their publication policy is provenance-only and auto-publication remains disabled.
- Repository licenses and source statements do not establish prompt or output-image rights. All configured sources remain `review_required` for prompt and asset publication.
