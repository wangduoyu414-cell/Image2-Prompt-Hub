# Phase 2 来源准入 v3 Adapter Handoff

本文件是 TASK-0022 的只读消费合同。它不表示来源已 active、已导入库存、已进入 scheduler 或已公开。

| source_id | fixed revision | mode | case count | case ledger SHA-256 | structure strategy | family role | exclusions |
|---|---|---|---:|---|---|---|---:|
| `chaosrealmsai-gpt-image-2-gallery` | `5296db8c996e38776c83a0bc8c64f848dcd512b3` | `fixed_history` | 2460 | `33484746656377578e62ad6f425d5d07f23cce0f9fdc5b04697fb31d402fa65b` | `chaos_meta_three_webp_v1` | `canonical` | 1466 |

## 消费约束

- 只允许消费 `reports/phase2/source-expansion-admission-v3.json` 中完全相同的 `adapter_ready_batch`；完整 exclusion ledger 以该 JSON 为准。
- `continuous` 只适用于 Goku；`fixed_history` 只适用于 Chaos，且固定历史必须 `sync_eligible=false`、`one_shot_import_only=true`。
- 不得跟随 moving HEAD，不得用 README 数量替换 case scope，不得自行加入 YouMind 或 tigerowo。
- 导入后仍需独立完成 Adapter、库存事务、rights review 和 public consumer 任务；所有内容继续 `review_required`、`auto_publish=false`。
- 当前生产基线仍是 6 active、1513 cases、1930 outputs、1885 去重资产、2260 source files、0 real public。
