# Phase 2 大规模来源准入审计 v3

## 最终结论

本轮固定审计了 2 个完整候选、1 个家族对照源和 1 个排除控制源。最终 `adapter_ready_batch` 包含 1 个来源：`chaosrealmsai-gpt-image-2-gallery`。

该结论只形成后续 Adapter/一次性导入的只读 handoff；没有修改 Source Registry、Adapter、库存、Canonical、Candidate、Publication、API 或网页，也没有公开任何第三方案例。

## 当前生产边界

| active 来源 | internal cases | outputs | 去重资产对象 | source files | real public |
|---:|---:|---:|---:|---:|---:|
| 6 | 1513 | 1930 | 1885 | 2260 | 0 |

以上基线由现有生产解析路径重建；TASK-0021 v2 仍为空批次，全部受保护文件摘要未漂移。

## 四来源角色与固定权威

| 来源 | 审计角色 | 家族角色 | mode | fixed revision | 状态 |
|---|---|---|---|---|---|
| `goku-openlab-gpt-image-2-prompts-datasets` | `full` | `aggregator` | `continuous` | `c4e79e9e11b3e754ec64f6400c7f94de6a5f103d` | `blocked` |
| `chaosrealmsai-gpt-image-2-gallery` | `full` | `canonical` | `fixed_history` | `5296db8c996e38776c83a0bc8c64f848dcd512b3` | `fixed_history_ready` |
| `youmind-openlab-gpt-image-2-prompts-search` | `comparator` | `reserve` | `reserve` | `08861ab6db5d772e311f5661cfb0a3ae06e10bb1` | `comparator_only` |
| `tigerowo-awesome-gpt-image-2-prompts` | `excluded_control` | `backup` | `excluded` | `60e9c65baecfd6d6d51ac4e4d87f146af834bb64` | `excluded` |

Goku 与 YouMind 属于同一 OpenLab/Atlas 聚合家族边界：保留各自 provenance，但按标准化 Prompt SHA-256 去重，不把聚合、对照和上游重复计为独立贡献。tigerowo 仅保存 EvoLink backup/排除证据，不建立完整准入账，也不能进入 handoff。

YouMind fixed revision 共 23283 条分类记录、14799 个唯一 ID、33779 个 CMS 图片引用（21444 个唯一 URL）；15714 条声明需要参考图。全部图片只作为 `observation_only` 的 CMS HTTPS 对照，作者归因行=0、原帖链接行=0，因此不能作为独立权利或固定资产来源。

## 完整候选漏斗

| 来源 | raw | parseable | authority-valid | safety-eligible | within-source unique | within-family unique | current exact-new | quality-valid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `goku-openlab-gpt-image-2-prompts-datasets` | 16759 | 16759 | 16710 | 8907 | 8660 | 2609 | 2513 | 0 |
| `chaosrealmsai-gpt-image-2-gallery` | 3798 | 3798 | 3797 | 2460 | 2460 | 2460 | 2460 | 2460 |

计数来自完整 case/asset/orphan/exclusion ledgers；filtered 子集不删除 raw 事实，每一条排除均保留 case ID、原因与确定性摘要。

## 资产、质量与维护证据

### `goku-openlab-gpt-image-2-prompts-datasets`

- 固定权威：`hf`；tree manifest `0acc235b6d5ca21d28276c8b904126722f7d97080314072d9a1a160fed618b71`。
- 资产账：28293 个资产条目，1932 个 orphan；strong pair rate=0.9997，broken authoritative asset rate=0.0003。
- 质量证据：确定性准入样本 60 个，排除原因样本 17 类，样本 manifest `5f42ab78e5da2a7f2fc5f3585c5f734cf811991aed0abce7e4629cb96da2761a`；结果 `fail`。
- 未通过的准入样本：13 个（`GI2_00015`, `GI2_00004`, `GI2_16784`, `GI2_09262`, `GI2_11918`, `GI2_11710`, `GI2_05683`, `GI2_14099`, `GI2_11896`, `GI2_12019`, `GI2_16085`, `GI2_11924`, `GI2_00441`）。
- 维护判定：实质更新日期 2026-07-10, 2026-07-19, 2026-07-29, 2026-08-03；`continuous_eligible=true`。
- 最终状态：`blocked`。

### `chaosrealmsai-gpt-image-2-gallery`

- 固定权威：`git`；tree manifest `cef3ba3807ba81e5cd0647dad87bcf5e85edf0718d3b584a09d055b41bd6c705`。
- 资产账：11559 个资产条目，168 个 orphan；strong pair rate=0.9997，broken authoritative asset rate=0.0003。
- 质量证据：确定性准入样本 60 个，排除原因样本 12 类，样本 manifest `5f42ab78e5da2a7f2fc5f3585c5f734cf811991aed0abce7e4629cb96da2761a`；结果 `pass`。
- 固定历史判定：`fixed_snapshot_complete=true`、`sync_eligible=false`、`one_shot_import_only=true`。
- 最终状态：`fixed_history_ready`。

## 权利与消费边界

- 所有 Prompt 与图片均保持 `review_required`，`auto_publish=false`；仓库或 dataset license 只作为上游声明，不等于真实公开授权。
- Git 图片以 fixed revision 下安全相对路径、文件 bytes、媒体魔数和 SHA-256 为权威；Goku 图片以 fixed HF revision 的 LFS path/OID/size 为全量权威，只有质量样本被实际下载、哈希、解码和人工查看。
- YouMind CMS/远程图只用于对照边界，不被写成 immutable asset authority；tigerowo 不产生可准入案例。
- 本轮只做 exact URL、Prompt SHA-256 与固定资产摘要去重，不执行语义近似自动合并。

## Adapter handoff

- `chaosrealmsai-gpt-image-2-gallery`：`fixed_history`，revision `5296db8c996e38776c83a0bc8c64f848dcd512b3`，case scope 2460，case ledger `33484746656377578e62ad6f425d5d07f23cce0f9fdc5b04697fb31d402fa65b`，structure `chaos_meta_three_webp_v1`，family role `canonical`，排除记录 1466 条。

下一任务只能消费 JSON `adapter_ready_batch` 的 fixed revision、mode、case scope、structure strategy、family role 和完整 exclusions；不得重新按 HEAD、README 数量或 Stars 选源。
