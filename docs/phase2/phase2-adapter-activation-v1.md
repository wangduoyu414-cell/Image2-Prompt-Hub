# Phase 2 首批 Adapter 激活记录 v1

## 结论

TASK-0019 将 TASK-0018 唯一准入的 freestylefly、erickkkyt 与 VigoZhao 三个固定 Commit 接入生产解析、私有库存和增量同步边界。它们与 Phase 1 的 g0dam、JoeSai、ConardLi 共同构成当前 6 个 active 长期内容来源。

本次接入只扩大内部内容供应链，不改变权利结论、公开条件、生产部署或调度状态。所有来源继续 `auto_publish=false`，真实公开目录为 0。

## 固定来源与规模

| source_id | 固定 Commit | source cases | outputs / Generation Examples |
| --- | --- | ---: | ---: |
| `g0dam-gpt-image-2-prompts` | registry authority | 100 | 100 |
| `joesai-awesome-gpt-image-1.5` | registry authority | 50 | 50 |
| `conardli-easy-gpt-image` | registry authority | 162 | 162 |
| `freestylefly-awesome-gpt-image-2` | `76fcd0e6b3961ef2b041547aac654f1efd1ef270` | 517 | 517 |
| `erickkkyt-awesome-gptimage2-prompts` | `1b5ec5f4f3409d2bf4cd2a4741070ce6c1429c6a` | 572 | 877 |
| `vigozhao-ai-visual-prompt-cookbook` | `9fa17042b392db28bb495f7208d37f1b9c416368` | 112 | 224 |
| **总计** |  | **1513** | **1930** |

完整快照还包含 2260 个登记来源文件和 1885 个按 SHA-256 去重后的资产对象。`outputs / Generation Examples` 大于 source cases，是因为 erickkkyt 每个案例可有 1–4 张输出，VigoZhao 每个风格案例固定有横竖两张预览。

## Adapter 责任边界

- 每个来源由独立 Adapter 解析，不以跨项目通用启发式猜测结构。
- 输入必须匹配注册表中的固定 Commit、结构策略和来源路径；未知字段、缺图、重复标识、越界路径和不完整配对 fail closed。
- `source_case_key` 标识上游案例；`asset_ref_id` 标识该案例中的具体输出。管线按二者共同解析资产，不再假设每个案例只有一张图片。
- 一份 source case 投影为一份 Generation document；每个输出建立独立 Generation Example、输出引用和强配对证据。首张输出使用 `output_primary`，其余使用 `output_secondary`。
- 原始 Prompt、上游模型声明、来源位置、rights evidence 和扩展字段均保留来源事实，不从仓库名称或图片外观补造结论。

## 同步与恢复

6 个来源均沿用既有固定快照、私有库存和单来源同步控制面：同 Commit 重跑为 `no_change`；候选 Commit 必须证明 fast-forward；解析、导入或发布失败不替换上一版 current。来源可以单独启停、审计和重试。

验证覆盖了 6 个真实固定 Commit 的初次同步与重放、erickkkyt 注入失败后的同候选恢复、VigoZhao 多阶段故障和并发锁、1885 个对象的下载重哈希，以及既有 Content/API/Web 消费链。最终私有库存为 1513 cases、1930 generation/output/pairing relationships，公开列表与 current publication 均为 0。

## 明确保留的后续工作

现有 publication gate 按每个 Generation Example 是否具有 `output_primary` 判定。内部多输出投影中，第二张及以后是 `output_secondary`，因此这些关系当前还会被公开门拒绝。这不影响私有库存正确性，也符合本阶段 0 real public 的目标。

在开始真实 rights approval 前，下一任务必须先明确多图公开合同：一个公开案例如何聚合多个输出、详情页与列表页如何展示、rights 与下架粒度按案例还是按资产执行，以及 API 是否继续以单 Generation Example 为单位。未经该设计评审，不应把 secondary 自动提升为 primary 或放宽 fail-closed 门。
