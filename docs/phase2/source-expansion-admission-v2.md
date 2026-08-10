# Phase 2 高质量新来源准入 v2 与 Adapter Handoff

## 当前保护基线

当前仍为 6 active、1513 internal Source Cases、1930 outputs、2260 source files、1885 deduplicated asset objects、0 real public。`source-expansion-admission-v2` 不修改 registry、库存、Canonical、Candidate v2 或 Public API/Web v1。

## 唯一允许的第二批 Adapter 输入

| Rank | source_id | fixed Commit | strategy | scope records/cases/outputs | valid / exact-new |
|---:|---|---|---|---:|---:|
| — | — | — | — | 0 / 0 / 0 | 0 / 0 |

## 候选边界

- `ecomimagelab-ecommerce-gpt-image-prompts`：`probation`；quality sample failed: ec-0023:amazon-claim-free-main-image；quality-failed 1，orphan rasters 18，remote outputs 0。
- `hiapiai-awesome-gpt-image-2-prompts`：`probation`；quality sample failed: character-design-cases-case-9-chaos-notes-hidden-face-character-art-by-loglogrog, portrait-case-5-mirror-selfie-bedroom-portrait-by-shinning1010, ui-case-1-one-prompt-ui-design-generation-by-austinit；quality-failed 3，orphan rasters 4，remote outputs 0。
- `imaginevid-awesome-gpt-image-2-prompts-and-skills`：`probation`；remote media has no immutable snapshot authority; quality sample failed: imagine-004, imagine-055, imagine-061, imagine-095；quality-failed 4，orphan rasters 0，remote outputs 207。

## 后续 Adapter 必须保持

- 只消费本文件列出的 fixed Commit、strategy 和明确 source scope。
- 全量覆盖 case/output/orphan，未知字段、缺图、弱配对、重复 ID 和越界路径 fail closed。
- Prompt/asset 继续 `review_required`，`auto_publish=false`；准入不等于 active 或 public。
- exact-overlap 只用于来源贡献审计，不写 Canonical Case，不做语义/视觉自动合并。
- imagineVid 在独立 immutable snapshot 任务完成前不得进入 Adapter 激活。
