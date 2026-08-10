# GPT Image 2 开源生态：两类深度调研与扩展发现

**调研截止：2026-08-01（America/New_York）。GitHub 使用 UTC 记录，部分提交时间可能显示为 2026-08-02。**

本报告把现有调研与新增发现严格拆成两类：

1. **Skill 技能类型**：用于需求抽取、视觉导演、Prompt 编译、模型适配、编辑约束、质量校验、迭代、执行和评测。
2. **高质量 Prompt 案例 + 效果展示**：用于学习优秀 Prompt 结构、对照真实输出、建立可复现案例库和业务模板库。

评分是按项目角色做的专业审查分，不是模型跑分。等级：S ≥ 92，A = 84–91，B = 72–83，C < 72。

## 一、核心判断

### 1. 最佳方案不是“找一个最大仓库”，而是分层组合

推荐的生产链：

**官方规范 → Prompt 编译/校验 → 视觉导演 → 垂直工作流 → 执行工具 → 资产管理 → 回归评测**

当前最强组合：

- 官方基线：`openai/codex` 内置 `imagegen` Skill
- 通用 Prompt 编译：`veryCoolTimo/imagegen-skills` 或 `gongnyang/gongnyang-prompt-kit`
- 审美与多图一致性：`smixs/visual-skills`、`Leonxlnx/taste-skill`、`trin-zenityx/image-craft-lv`
- 垂直工作流：`JuneYaooo/gpt-image2-ppt-skills`、`shaowen-ye/image-prompt-builder`
- 执行层：`Wangnov/gpt-image-2-skill`
- 私有资产层：`EddieTYP/image-prompt-library`
- 评测层：`stevenflyai/multi-agent-image-gen-evals`

### 2. 本轮新增的高价值发现

- `openai/codex` 的官方 `imagegen` Skill 应成为所有第三方 Skill 的验收基准。
- `veryCoolTimo/imagegen-skills` 是新发现中最完整的通用提示词系统之一。
- `trin-zenityx/image-craft-lv` 用 A/B Arena、Lessons Ledger 和自审机制，把提示经验变成可验证知识。
- `noxx/visual-atelier-skill` 把 Brief 编译、真实调用、输出检查和 sidecar 回执连成可复现生产链。
- `shaowen-ye/image-prompt-builder` 对科学图件建立了明确红线：真实数据图、地图、网络拓扑和精确数值图不能交给图像模型伪造。
- `g0dam/Awesome-GPT-Image-2-Work-Prompts` 是新增案例主榜：100 个双语业务 Prompt、JSON 和 100 张效果图。

### 3. 最大纠偏：大量仓库不是独立项目

- 多个 `GPT-Image2-Skill` 仓库是 `wuyoscar/GPT-Image2-Skill` 的完整镜像。
- `zhuihunzhe/gpt-image2-prompt-skill` 的 README、徽章和案例内容直接指向 `freestylefly/awesome-gpt-image-2`。
- `mageia`、`LeonSooLab`、`chattydogmagazine`、`GuomingXu` 等多仓属于 EvoLink 同内容家族。
- `tigerowo` 明确是 EvoLinkAI backup；README 为空，不能视为独立案例源。
- 高频 `auto-update README` 或 manifest 时间戳变化，不能证明有新增 Prompt 或效果图。

## 二、Skill 技能类型主榜

| 项目 | 类型 | 角色 | 分数 | 等级 | 建议 | 核心价值 | 主要风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| openai/codex（内置 imagegen Skill） | 官方规范与执行 | 通用基线 | 98 | S | 核心采用 | 官方模式路由；输入图角色；精确文字；编辑不变量；小步迭代；透明背景降级；资产落盘 | 它是执行/提示规范，不是大型社区案例库 |
| openai/openai-cookbook | 官方方法与样例 | 规范基线 | 96 | S | 核心采用 | 官方图像生成、编辑、多模态提示方法；适合作为第三方 Skill 验收标准 | 不等同于可直接安装的单一 Skill |
| veryCoolTimo/imagegen-skills | Prompt 编译/模型适配 | 通用提示词系统 | 95 | S | 核心采用 | 9 块提示结构；9 类视觉原型；多模型适配；风格预设；编辑/Remix；GPT Image 2 专属适配 | 普通摄影场景可能被过度参数化 |
| gongnyang/gongnyang-prompt-kit | Prompt-as-Code/校验 | 提示词编译器 | 95 | S | 核心采用 | 结构化编译、Schema、白名单、反模板化规则、回归夹具、CI 校验 | 需要把规则裁剪到自身业务，避免过度工程化 |
| JuneYaooo/gpt-image2-ppt-skills | 垂直生产流程 | PPT/模板克隆 | 94 | S | 垂直首选 | 模板验证；单页确认；并发生成；回渲染验收；确定性修复；可编辑对象重建 | 密集表格、财务、法务和精确数字仍需人工验收 |
| smixs/visual-skills | 视觉导演/知识路由 | 通用视觉生产 | 92 | S | 核心采用 | 模型规则→黄金规则→任务模块→创意方向→Prompt 框架；Change/Preserve/Constraints 编辑结构 | 部分尺寸上限偏保守，需以官方 API 为准 |
| trin-zenityx/image-craft-lv | 持续学习/质量门 | 多图一致性与自审 | 91 | A | 重点采用 | Pre-submit Checklist、Batch Gate、Post-generate Self-review、Lessons Ledger、A/B Arena | 非 GPT Image 2 专属；当前仅 1 条 lesson 完成正式验证 |
| ningzimu/codex-ppt-skill | 垂直生产流程 | PPT/个人风格库 | 91 | A | 垂直采用 | 需求澄清、样张确认、风格沉淀、整页图像式 PPT 工作流 | 原生可编辑能力弱于 JuneYaooo 方案 |
| Leonxlnx/taste-skill | 视觉导演/审美 | Web 视觉资产 | 90 | A | 重点采用 | 反 AI 套路；一段一图；构图、叙事、CTA、背景与节奏多样化 | 偏网站视觉，不是通用模型语法规范 |
| noxx/visual-atelier-skill | Prompt 编译/执行/回执 | 多工作流视觉生产 | 89 | A | 重点采用 | 8 类工作流；Brief 编译；OpenAI/Gemini 生成与编辑；输出检查；JSON sidecar 回执；测试 | 更新频率较低；样例效果库规模有限 |
| yun-666-666/image-prompt-skill | Prompt 优化/意图保护 | 通用提示词优化 | 89 | A | 重点采用 | 最小有效增强；精确文字；编辑不变量；完整性清单；双语 A/B 样例 | A/B 没有固定种子或统计检验；部分本地语料路径不可移植 |
| Wangnov/gpt-image-2-skill | 执行工具链 | CLI/Desktop/Docker/Skill | 89 | A | 执行层首选 | 统一 Rust core；生成/编辑；参考图；透明 PNG；历史；OAuth；JSON 协议；安全与 CI | 核心价值是执行与交付，不是原创 Prompt 方法论 |
| fzfzerro/image2skill | 图像反推/风格包 | Style Skill Pack | 88 | A | 精选采用 | 把样图拆成可复用 Style Skill；基础 Prompt、变体、真实效果图库 | 规模较小；部分名人/IP 示例商业使用风险较高 |
| stevenflyai/multi-agent-image-gen-evals | 评测/回归 | 同 Prompt 横评 | 88 | A | 评测层采用 | 双模型并行；六维评分；独立批评与修订；HIL 门控；全量产物归档 | 主要评估图像，不直接负责写 Prompt |
| EddieTYP/image-prompt-library | 资产管理/检索 | 私有 Prompt+图片库 | 88 | A | 管理层采用 | 本地 SQLite；图像优先检索；多语言 Prompt 变体；来源元数据；生成结果入库；备份恢复 | 公开演示内容来自上游聚合，不是原创案例源 |
| junyeo217/codex-gpt-image-2-skill | Prompt 语法/校验 | 结构化单轮生成 | 87 | A | 选择性采用 | 渐进披露；领域 lanes；核心语法；机械校验；数值锚点；反套路 | 固定尺寸白名单和部分负面词规则过严；一行/一轮偏工作流偏好 |
| shaowen-ye/image-prompt-builder | 科学视觉/红线判断 | 科学插图与流程图 | 87 | A | 垂直采用 | 英文本体+中文审阅；多系列规范；真实数据图/地图/拓扑/精确数值红线；后处理检查 | 仓库更新集中在首发阶段；无大规模真实效果库 |
| eugeniughelbur/gpt-image-cookbook | Skill+CLI+案例 | 跨 Provider Cookbook | 87 | A | 精选采用 | 分类→检索案例→精炼→CLI 生成；记录 provider/model/quality/size 和成败经验 | 案例数较少，Imagen/Flux 支持部分仍在演进 |

## 三、高质量 Prompt 案例 + 效果展示主榜

| 项目 | 类型 | 角色 | 分数 | 等级 | 建议 | 证据链 | 主要风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| openai/openai-cookbook | 官方案例/规范 | 官方核心 | 96 | S | 核心采用 | 官方样例与 Notebook | 不是大规模风格图库 |
| VigoZhao/AI-Visual-Prompt-Cookbook | 结构化风格案例 | 核心案例库 | 96 | S | 核心采用 | Prompt 与输出一一配对，含风格锚点 | 跨模型可用不等于每条都做过 GPT Image 2 固定版本回归 |
| JuneYaooo/gpt-image2-ppt-skills | PPT 输入输出对照 | 垂直核心 | 91 | A | 垂直采用 | 真实图片、PPTX 和回渲染结果 | 案例集中在 PPT，不是通用图库 |
| ConardLi/gpt-image-2-101 | 教程+案例+对话 | 核心教材 | 89 | A | 核心采用 | Prompt、效果图与教程结构 | 不适合作为最新动态源 |
| mageia/awesome-gpt-image-2-API-and-Prompts | 社区精选案例 | 核心候选/发现 | 88 | A | 精选采用 | 近期提交确实新增案例与输出媒体 | 存在大量同内容镜像；X 作者内容不能因仓库 CC0 自动视为可再授权 |
| g0dam/Awesome-GPT-Image-2-Work-Prompts | 职场/业务视觉 | 核心案例库 | 88 | A | 核心采用 | Prompt+输出图+结构化数据 | 近期无实质更新，需自行做版本回归 |
| fzfzerro/image2skill | 风格 Skill+效果 | 小而精案例 | 88 | A | 精选采用 | Prompt 与图像强配对 | 规模小；部分 IP/名人风格商业风险 |
| eugeniughelbur/gpt-image-cookbook | 自生成 Cookbook | 小而精案例 | 87 | A | 精选采用 | 项目自身 CLI 生成的真实结果 | 真实条目约十余个，规模小 |
| JoeSai/awesome-gpt-image-2-commercial-prompts | 商业视觉 | 核心商业案例 | 86 | A | 精选采用 | 双语 Prompt 与预览成对 | 停止更新较早；品牌与广告场景需合规复核 |
| freestylefly/awesome-gpt-image-2 | 大型中文案例/Prompt-as-Code | 核心发现 | 86 | A | 发现层采用 | 大量本地效果图与案例页 | 混有品牌/IP/艺术家风格、Midjourney flags、8K 等非官方或不可直接复制元素 |
| wuyoscar/GPT-Image2-Skill | Skill+案例 | 混合核心 | 86 | A | 保留上游 | 约 162 个示例 | 大量镜像；只保留原上游 |
| lin351540-ship-it/prompt-atlas-jj | 透明聚合图库 | 发现层 | 85 | A | 发现层采用 | Prompt、图片与来源信息 | 不是原创案例库；质量由上游决定 |
| 0aicoder0/gpt-image-2-prompt-gallery | 分类案例图库 | 精选案例 | 84 | A | 精选采用 | README 与分类 Gallery | 更新集中在首发期；部分媒体风格/IP Prompt 风险 |
| yinxiaowai/awesome-gpt-image-2-vs-nano-banana-2-prompt-gallery | 同 Prompt 模型对照 | 评测图库 | 84 | A | 评测采用 | 约 200 张对照图 | 缺固定种子、完整参数快照与统计设计；Prompt 本身常较简单 |
| EddieTYP/image-prompt-library（公开 Demo） | 图像优先聚合目录 | 发现/管理层 | 84 | A | 发现层采用 | 上游案例的可浏览卡片 | 公开内容来自 wuyoscar 与 freestylefly，不是第三个独立案例源 |

## 四、两类项目的收录标准

### Skill 技能类

必须优先检查：

- 是否正确区分文本生图、编辑、多参考图、透明背景和批量任务。
- 是否明确精确文字、参考图角色和必须保持不变的属性。
- 是否能从模糊需求抽取目标、用途、主体、构图、光线、材质、文字和约束。
- 是否有预检、后检、A/B、回归、失败诊断或有界修复。
- 是否有可复用输出契约，而不是只输出一段“更长的 Prompt”。
- 是否有真实测试、案例或生成回执。
- 是否实质维护，且不是镜像。

### 案例 + 效果类

进入核心案例库的最低字段建议：

```text
exact_prompt
model_snapshot
generation_date
size
quality
input_images
input_image_roles
output_image
source_author
source_url
license_status
locked_invariants
editable_variables
failure_notes
human_score
parent_prompt_id
```

没有完整 Prompt、没有效果图、没有来源或只能看到缩略图的项目，只进入“发现层”，不进入核心案例库。

## 五、推荐落地结构

### 核心 Skill 栈

1. `openai/codex imagegen`：官方规则与调用基线。
2. `veryCoolTimo/imagegen-skills` 或 `gongnyang-prompt-kit`：Prompt 编译和质量门。
3. `smixs/visual-skills` / `taste-skill`：视觉导演与反套路。
4. `image-craft-lv`：多图一致性、批量门控和经验验证。
5. 垂直 Skill：PPT、科学图、商业产品等。
6. `Wangnov/gpt-image-2-skill`：执行和交付。
7. `EddieTYP/image-prompt-library`：私有资产沉淀。
8. `multi-agent-image-gen-evals`：版本回归。

### 核心案例源

优先入库：

- OpenAI 官方 Cookbook
- `VigoZhao/AI-Visual-Prompt-Cookbook`
- `ConardLi/gpt-image-2-101`
- `g0dam/Awesome-GPT-Image-2-Work-Prompts`
- `JoeSai/awesome-gpt-image-2-commercial-prompts`
- `mageia/awesome-gpt-image-2-API-and-Prompts` 中通过来源复核的条目
- `eugeniughelbur/gpt-image-cookbook`
- `fzfzerro/image2skill`

召回与发现层：

- `prompt-atlas-jj`
- YouMind
- AtlasCloud
- `freestylefly`
- `hurris1/gpt-image2-explorer`

这些大库用于找候选，不能未经筛选直接作为生产 Prompt 库。

## 六、持续拓展规则

后续每轮更新不按 Star 或提交次数排名，而按以下证据更新：

- 新增了真实 Prompt 正文和效果图。
- 新增了测试、Schema、回归夹具、评测结果或工作流。
- 新增案例保留作者、原帖、许可和参数。
- 固定测试集在新模型快照下重新生成，并保存差异。
- 镜像、自动 README 和时间戳更新不增加内容分。
- 出现模型参数错误、来源不明、授权外溢或严重过拟合时下调评分。

完整项目明细、评分、镜像血缘和跟踪规则见配套 Excel。
