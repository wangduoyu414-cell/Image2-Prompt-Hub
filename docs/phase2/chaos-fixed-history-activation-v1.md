# Chaos 固定历史来源接入 v1

## 结果

`ChaosRealmsAI/gpt-image-2-gallery` 已按 TASK-0022 的唯一 `fixed_history` handoff 接入私有内容链。接入只消费：

- source ID：`chaosrealmsai-gpt-image-2-gallery`
- 固定 Commit：`5296db8c996e38776c83a0bc8c64f848dcd512b3`
- case scope：2460
- case ledger SHA-256：`33484746656377578e62ad6f425d5d07f23cce0f9fdc5b04697fb31d402fa65b`
- Adapter：`chaos_meta_three_webp_v1`
- family role：`canonical`
- exclusions：1466 条、1338 个唯一被排除案例

完整准入投影保存在 `config/fixed-history/chaosrealmsai-gpt-image-2-gallery-v1.json`，并同时绑定 TASK-0022 报告文件摘要、canonical digest 和 `adapter_ready_batch` 项摘要。

## 运行边界

当前 operational authority 使用 `config/sources-v2.yaml` 与 `reports/source-audit-v2.json`：

- 6 个既有来源为 `continuous`、`sync.enabled=true`；
- Chaos 为 `fixed_history`、`sync.enabled=false`、`one_shot_import_only=true`；
- `sync run-source` 会显式拒绝 Chaos；
- 唯一写入入口是 `inventory import-fixed-history`；
- 一次性导入只完成提取、私有对象存储、库存事务和 Canonical/审核队列接线，不构建或激活 Publication。

示例：

```powershell
py -3.12 -m inventory import-fixed-history `
  --registry config/sources-v2.yaml `
  --audit reports/source-audit-v2.json `
  --source-id chaosrealmsai-gpt-image-2-gallery `
  --git-data-root C:\external\image2-git `
  --package-root C:\external\image2-packages `
  --json
```

数据库和 S3 凭据仍通过既有 `INVENTORY_*` 环境变量提供，运行根目录必须在仓库外部。

## 已验证事实

固定快照和真实隔离导入已得到：

| 项目 | 数量 |
|---|---:|
| Source Cases / Prompt records | 2460 |
| Generation Examples / outputs | 7380 |
| 互异内容寻址资产 | 7380 |
| source files | 9840 |
| Canonical memberships | 7380 |
| 待审 subjects | 2460 |
| 审核批次 | 0 |
| Publication Versions | 0 |
| Public entries | 0 |

提取语义摘要为 `47d746621924f17f05df74287b3df9cf0fb2151daf9786f4de1a0a3541abf5df`；同一幂等键复跑返回 `verified_existing`。七来源内部预览闭合为 3973 个案例、9310 张效果图，其中每个 Chaos 案例保留 w400、w1600、w2400 三个固定输出。

## 验证

静态和真实固定快照验证：

```powershell
py -3.12 scripts/validate_chaos_fixed_history.py --json
py -3.12 scripts/validate_chaos_fixed_history.py `
  --live `
  --snapshot-root C:\external\chaos-fixed-snapshot `
  --json
```

全部 Prompt 与图片继续保持 `review_required`、`auto_publish=false`。该接入不代表公开授权，也不改变真实 public catalog 为 0 的事实。
