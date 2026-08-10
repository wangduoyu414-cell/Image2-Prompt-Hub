# Phase 2 来源扩展准入与 TASK-0019 Handoff

> 历史准入文档：本文件记录 TASK-0018 完成时、TASK-0019 执行前的候选边界。TASK-0019 已于 2026-08-09 将这里唯一允许的三项首批输入接入为 active 来源；当前运行事实见 `phase2-adapter-activation-v1.md`、`config/sources-v1.yaml` 与 `reports/source-audit-v1.json`。

## 当前状态

Phase 1 保持原样：3 个 active 来源、312 internal Generation Examples、0 real public。Phase 2 只完成外部来源发现和 Adapter 准入研究，没有修改 registry、生产 Adapter、库存、公开权利或部署状态。

机器输入为 `reports/phase2/source-discovery-v1.json`。该文件中的 full audit 均有明确 discovery 上游、family 映射、完整 case ID ledger 和可复现质量样本；正式 live 校验会从固定 Commit 重算案例指标。TASK-0019 只能从其中的 `adapter_ready_batch` 建立实现任务，不得重新按 Stars、README 宣传数字或图片文件总量选源。

## TASK-0019 唯一允许的首批输入

| 顺序 | source_id | 固定 Commit | 预期结构策略 | 唯一有效案例 |
|---:|---|---|---|---:|
| 1 | `freestylefly-awesome-gpt-image-2` | `76fcd0e6b3961ef2b041547aac654f1efd1ef270` | `freestylefly_cases_json_v1` | 517 |
| 2 | `erickkkyt-awesome-gptimage2-prompts` | `1b5ec5f4f3409d2bf4cd2a4741070ce6c1429c6a` | `erickkkyt_prompts_json_v1` | 572 |
| 3 | `vigozhao-ai-visual-prompt-cookbook` | `9fa17042b392db28bb495f7208d37f1b9c416368` | `vigo_style_directory_v1` | 112 |

三者合计 1201 个内部候选案例。这个数字是后续 Adapter 的可解析上限，不是已经导入的 inventory 数，也不是 public 数。

## 实现顺序

TASK-0019 应按“价值、权利风险、结构成本”拆分，而不是一次把三个来源混在一个通用解析器中：

1. 先实现 `freestylefly`：MIT、517 个案例、单一 JSON 清单，最适合验证 Phase 2 的新来源接入闭环。
2. 再实现 `VigoZhao`：MIT、目录合同最清晰、质量最稳定，可验证目录型 Adapter 和双预览输出。
3. 最后实现 `erickkkyt`：案例量最大，但许可证未声明且存在一对多图片，需要更严格的 rights 标记和输出展开规则。

如果 TASK-0019 的开发资源只允许一个来源，应先选 `freestylefly`。如果目标优先验证最高视觉一致性而非最大案例价值，可把 `VigoZhao` 作为第二条独立实现卡，但不能改变 JSON 中本次调查批次的证据排序。

## 每个 Adapter 必须保持的合同

- 输入必须固定到本文件列出的 Commit；不得默默跟随默认分支 HEAD。
- 只接受有原始 Prompt 和固定本地输出的记录；外链预览、README 宣称数量和无法归属的图片不得补入。
- 为每条记录产生稳定 source case ID、Prompt、输出资产路径、来源 URL、fixed Commit、rights 状态和 provenance。
- 一对多输出必须采用确定性展开或显式数组合同，不能随机选一张。
- 解析失败、缺图、重复 ID、未知字段和单条脏数据必须 fail closed，并给出可重跑的错误账。
- 接入只进入内部 inventory 候选；Prompt 与 asset 均保持 `review_required`，`auto_publish=false`。

## 不得进入 TASK-0019 的来源

`pixmind-io-awesome-gpt-image-2-prompts` 和 `yinxiaowai-awesome-gpt-image-2-vs-nano-banana-2-prompt-gallery` 缺持续维护证据；`mageia-awesome-gpt-image-2-api-and-prompts` 全库配对率不足；`itgoyo-awesome-gpt-image2-prompt` 是 derived corpus；`zerolu-awesome-gpt-image` 与 `youmind-openlab-awesome-gpt-image-2` 没有稳定的仓库内输出资产。它们必须留在 probation/blocked/excluded，除非以后基于新固定 Commit 重新完成全量审计。

Skill、工具和应用项目不再作为长期内容来源处理。它们只有在未来产品明确需要其工作流能力时，才可能进入独立能力评估；不能混入案例来源扩展。

## TASK-0019 完成标准建议

后续任务卡至少应覆盖：三个 Adapter 的独立责任边界、固定 Commit fixtures、全量解析计数、稳定 ID、Prompt/图片强配对、重复处理、rights fail-closed、inventory 集成、同步幂等性、失败恢复和最终消费者验证。每个来源应能单独启停、单独审计、单独回滚，避免一个来源结构变化拖垮全部同步。

本段是交接时的历史判定：TASK-0019 完成前项目事实为 312 internal、0 real public，本轮 1201 个案例仅是经审计的 Adapter 开发候选。TASK-0019 完成后的现行数量不得从本文件推断。
