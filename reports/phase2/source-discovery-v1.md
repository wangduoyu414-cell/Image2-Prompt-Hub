# Phase 2 来源发现与准入审计 v1

检索执行时间：2026-08-09 08:30 UTC；报告生成时间：2026-08-09 08:57 UTC。机器权威数据见 `source-discovery-v1.json`；本文只解释结论，不替代 JSON。

## 结论

本轮重新搜索并刷新了 8 个 Phase 1 probation 来源，另外确认 24 个不在 Phase 1 清单中的新候选，并额外复核了 Phase 1 blocked 候选 `youmind-openlab-awesome-gpt-image-2`；对 9 个优先来源完成固定 Commit 的全量案例审计。最终只有 3 个来源进入 `adapter_ready`，共 1201 个唯一有效内部候选案例：

| 排名 | 来源 | 唯一有效案例 | 配对率 | 失效资产率 | 维护证据 | 结论 |
|---:|---|---:|---:|---:|---|---|
| 1 | `freestylefly-awesome-gpt-image-2` | 517 | 1.000 | 0 | 29 个实质更新日期 | `adapter_ready` |
| 2 | `erickkkyt-awesome-gptimage2-prompts` | 572 | 1.000 | 0 | 8 个实质更新日期 | `adapter_ready` |
| 3 | `vigozhao-ai-visual-prompt-cookbook` | 112 | 1.000 | 0 | 53 个实质更新日期 | `adapter_ready` |

这里的 `adapter_ready` 只表示可以进入后续 Adapter 开发；不表示已接入、已入库、已获公开权利或已发布。Phase 1 的 3 个 active 来源、312 个 internal 案例和 0 个 real public 案例均未改变。

## 为什么不是“看到图片多就接入”

本轮使用固定门槛：至少 50 个唯一有效案例、配对率不低于 0.90、失效资产率不高于 0.05、重复率不高于 0.20、最近 180 天内有实质更新且一年内至少有 2 个实质更新日期。只有 canonical 来源在通过全量审计和质量样本后才能进入准入批次。

这套门槛排除了四类常见假阳性：

- Skill、工具和应用：仓库可能有很多界面或预览图，但不是可长期消费的提示词—输出案例库。
- 聚合页和外链画廊：README 能展示图片，但固定 Commit 内没有对应资产，后续无法稳定复现。
- 镜像或导入集合：案例多，但来源权威不清，会和其他库重复计数。
- 一次性大仓库：案例质量和配对合格，但没有持续维护证据。

## 全量审计结果

| 来源 | 有效/观察 | 配对率 | 失效率 | 质量样本 | 状态 | 主要原因 |
|---|---:|---:|---:|---:|---|---|
| `freestylefly-awesome-gpt-image-2` | 517/517 | 1.000 | 0 | 50/50 通过 | `adapter_ready` | 大型本地 JSON 清单、资产固定、持续增加案例 |
| `erickkkyt-awesome-gptimage2-prompts` | 572/572 | 1.000 | 0 | 50/50 通过 | `adapter_ready` | 结构化 Prompt 与一对多本地图片，质量稳定 |
| `vigozhao-ai-visual-prompt-cookbook` | 112/112 | 1.000 | 0 | 20/20 通过 | `adapter_ready` | 目录级 JSON/预览合同最清晰，视觉一致性最高 |
| `pixmind-io-awesome-gpt-image-2-prompts` | 150/150 | 1.000 | 0 | Gate 前停止 | `probation` | 全部实质工作集中在一个日期，不满足持续维护 |
| `itgoyo-awesome-gpt-image2-prompt` | 611/613 | 0.996737 | 0 | Gate 前停止 | `excluded` | 初始提交明确从 GitHub/OpenNana 导入，属于 derived corpus |
| `yinxiaowai-awesome-gpt-image-2-vs-nano-banana-2-prompt-gallery` | 102/102 | 1.000 | 0 | Gate 前停止 | `probation` | 两次提交发生在同一天，不满足持续维护 |
| `zerolu-awesome-gpt-image` | 10/74 | 0.135135 | 0.929078 | Gate 前停止 | `blocked` | 绝大多数输出是外链；频繁提交只是更新时间戳 |
| `youmind-openlab-awesome-gpt-image-2` | 0/127 | 0 | 1.000 | Gate 前停止 | `blocked` | 445 个输出引用均未固定在仓库 Commit 中 |
| `mageia-awesome-gpt-image-2-api-and-prompts` | 549/919 | 0.597388 | 0 | 50/50 通过 | `probation` | 质量和维护很好，但全库强配对覆盖低于 0.90 |

## 新候选发现结果

24 个新候选中，3 个进入完整审计且产生 1 个 `adapter_ready`：`erickkkyt-awesome-gptimage2-prompts`；`itgoyo-awesome-gpt-image2-prompt` 因派生来源被排除；`zerolu-awesome-gpt-image` 因外链资产和弱配对被阻断。

其余候选的分类如下：

- 无本地输出或外链输出：`anil-matcha-awesome-gpt-image-2-api-prompts`、`magiccreator-ai-awesome-gpt-image-2-prompts`、`gpt-image2-awesome-gptimage2-prompts`、`xianyu110-awesome-gptimage2`、`flatkey-ai-awesome-images`。
- Skill/工具：`liangdabiao-ecom-details-image`、`buluslan-gpt-image2-ecommerce`、`conardli-garden-skills`、`tmchow-illo-skill`、`oil-oil-draw-ui`、`nomadamas-god-tibo-imagen`、`uzenupozitiv4ik-gpt-image-2-skill`。
- 应用而非内容源：`nexu-io-open-design`、`yuqie6-productflow`、`rockbenben-img-prompt`、`cooksleep-gpt-image-playground`、`shannon4science-nanadraw`、`leochens-stickercraft`、`anil-matcha-free-ai-social-media-scheduler`。
- 多模型集合：`dongyubin-awesome-ai-images-prompts`。
- 当前不可用：`evolinkai-awesome-gpt-image-2-prompts`。

## 质量复核

对通过前置量化门槛的来源按 `min(unique, 50, max(20, ceil(10%)))` 取确定性样本，并逐一终端读取图片、对照提示词。`freestylefly` 和 `erickkkyt` 各检查 50 个案例，`VigoZhao` 检查 20 个；三者均未发现系统性错配。`mageia` 的 50 个样本也表现良好，但质量抽样不能覆盖其全库配对率不足的问题，因此仍为 probation。

JSON 现在保存每个 full audit 的完整稳定 case ID ledger、ledger digest、全量资产终端汇总、质量 sample ID、样本选择方法和逐项图片 SHA-256。`--live` 不再只看仓库是否存在：它会从固定 Commit 重新解析 9 个仓库的完整案例账、重算全部指标、复现质量样本并重新下载样本图片校验摘要；同时对全部 triaged 候选核对 repository ID、default branch、archive 状态和固定 Commit。

## 权利与下游边界

所有准入来源的 Prompt、图片和公开资格仍是 `review_required`，`auto_publish=false`。未知许可证不会阻止内部 Adapter 可行性研究，但会继续阻止公开发布。TASK-0019 只能消费 JSON 中 `adapter_ready_batch` 的三个固定 Commit，不能把 probation、blocked、excluded 候选写入 active registry。
