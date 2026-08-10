# Phase 2 高质量新来源准入审计 v2

> 机器权威：`source-expansion-admission-v2.json`；生成时间：`2026-08-10T14:05:05.829653Z`。

## 结论

本轮只审计三个新候选，不修改 registry、Adapter、Canonical、库存或公开状态。当前基线保持 6 active、1513 cases、1930 outputs、2260 source files、1885 deduplicated asset objects、0 real public。

| 来源 | fixed Commit / tree | records / cases / outputs | exact-new | 状态 |
|---|---|---:|---:|---|
| `ecomimagelab-ecommerce-gpt-image-prompts` | `6f63eadc6a1ac594a6304e9a3e1eb3e201812d58` / `568c0f7d471feda6bc30fa4f73cd31d923567483` | 74 / 284 / 284 | 284 | `probation` |
| `hiapiai-awesome-gpt-image-2-prompts` | `92ed9bcd93a93e036edd6244e76668a437985743` / `b3ac6a330e66b9d59a71822c79c74e75f74e1f4c` | 189 / 198 / 198 | 140 | `probation` |
| `imaginevid-awesome-gpt-image-2-prompts-and-skills` | `04f0ee2af1156ae3b556d8c90725727d6aec7acc` / `966d599dfd0d4f3595c31cf930340820324d36a5` | 95 / 95 / 207 | 95 | `probation` |

## 质量、来源与资产边界

### `ecomimagelab-ecommerce-gpt-image-prompts`

- 结构：`ecomimagelab_prompt_variants_v1`；质量样本 43，结论 `fail`。
- 样本覆盖：22/22 类别，2/2 风险簇；失败案例：`ec-0023:amazon-claim-free-main-image`。
- 全量风险/低信息 flag 事件：85；这些是审核线索，不代表自动删除或公开批准。
- 资产：303/303 本地 raster 完成魔数/大小/SHA-256 终端校验；local outputs 284，remote outputs 0，orphan rasters 18。
- 维护：最近实质更新 `2026-07-30`；过去 365 天 7 个不同更新日；成熟跨度 10 天。
- 独立贡献 overlap：source URL 0、Prompt 0、fixed image 0。
- 远程观测：无；图片权威来自 fixed Commit 本地文件。
- Rights：Prompt/asset 均 `review_required`，`auto_publish=false`。
- 结论：quality sample failed: ec-0023:amazon-claim-free-main-image。

### `hiapiai-awesome-gpt-image-2-prompts`

- 结构：`hiapiai_prompt_items_with_variants_v1`；质量样本 30，结论 `fail`。
- 样本覆盖：8/8 类别，4/4 风险簇；失败案例：`character-design-cases-case-9-chaos-notes-hidden-face-character-art-by-loglogrog`, `portrait-case-5-mirror-selfie-bedroom-portrait-by-shinning1010`, `ui-case-1-one-prompt-ui-design-generation-by-austinit`。
- 全量风险/低信息 flag 事件：105；这些是审核线索，不代表自动删除或公开批准。
- 资产：202/202 本地 raster 完成魔数/大小/SHA-256 终端校验；local outputs 198，remote outputs 0，orphan rasters 4。
- 维护：最近实质更新 `2026-06-01`；过去 365 天 5 个不同更新日；成熟跨度 30 天。
- 独立贡献 overlap：source URL 0、Prompt 34、fixed image 51。
- 远程观测：无；图片权威来自 fixed Commit 本地文件。
- Rights：Prompt/asset 均 `review_required`，`auto_publish=false`。
- 结论：quality sample failed: character-design-cases-case-9-chaos-notes-hidden-face-character-art-by-loglogrog, portrait-case-5-mirror-selfie-bedroom-portrait-by-shinning1010, ui-case-1-one-prompt-ui-design-generation-by-austinit。

### `imaginevid-awesome-gpt-image-2-prompts-and-skills`

- 结构：`imaginevid_remote_media_manifest_v1`；质量样本 30，结论 `fail`。
- 样本覆盖：6/6 类别，4/4 风险簇；失败案例：`imagine-004`, `imagine-055`, `imagine-061`, `imagine-095`。
- 全量风险/低信息 flag 事件：14；这些是审核线索，不代表自动删除或公开批准。
- 资产：1/1 本地 raster 完成魔数/大小/SHA-256 终端校验；local outputs 0，remote outputs 207，orphan rasters 0。
- 维护：最近实质更新 `2026-08-03`；过去 365 天 10 个不同更新日；成熟跨度 23 天。
- 独立贡献 overlap：source URL 0、Prompt 0、fixed image 0。
- 远程观测：207/207 通过当前 HTTP/图片终端检查；该值不属于 fixed-core authority。
- Rights：Prompt/asset 均 `review_required`，`auto_publish=false`。
- 结论：remote media has no immutable snapshot authority; quality sample failed: imagine-004, imagine-055, imagine-061, imagine-095。

## Adapter handoff

只有 JSON `adapter_ready_batch` 中的 fixed Commit 可以进入下一张 Adapter 卡。imagineVid 的远程图片观测是时点证据，不是 immutable asset authority。

本任务不做 Mageia remediation、历史大库导入或 Canonical/近似去重。
