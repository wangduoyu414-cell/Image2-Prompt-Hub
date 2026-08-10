---
task_contract_version: 3
card_id: "TASK-0002"
title: "冻结 Generation Example v1 与 Source Adapter 输出契约"
status: "ready"
work_kind: "mixed"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "external-boundary"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`:
  - 用户已确认的项目方向：长期固定高价值案例来源，核心资产是可追溯、强绑定的原始 Prompt 与对应图片，而不是 Skill、工具或工作流项目。
  - `D:/image2/1.md`，重点是第 3、5、6、7、12、15、16、18 节。
  - `D:/image2/config/sources-v1.yaml`，作为已冻结的来源、固定 Commit、状态与 pilot 选择权威配置。
  - `D:/image2/reports/source-audit-v1.json`，作为三个 pilot 的结构类型、固定 Commit、Adapter 策略和审计事实来源。
  - `D:/image2/tasks/TASK-0001-source-audit-and-sources-v1-freeze.md` 及其已验证交付物，作为本任务的上游边界；本任务不得重新审计或改写来源名单。
- `decision_owner`: 用户拥有业务边界、数据不变量、兼容性与风险接受的最终决定权；执行者可以在本卡约束内确定具体 JSON 字段组织、Schema 复用方式和验证器内部实现。
- `material_unknowns`:
  - `1.md` 当前提供的是建议 Schema 和职责原则，不是可直接执行的正式 v1 合同；本任务的目标正是消除这一缺口。
  - 生产数据库表、Pydantic 模型、API DTO、对象存储结构和具体 Adapter 类尚未实现，不属于本任务前置条件，也不得在本任务中提前决定。
  - 三个 pilot 的完整固定 Commit 源文件夹具将在后续纵向 Adapter 任务建立；本任务只从每个固定 Commit 提取一个真实、最小、可追溯案例作为合同样例，不保存图片字节或完整上游数据集。
  - 若执行中发现 `sources-v1.yaml` 的 pilot、固定 Commit 或结构事实与审计 JSON 冲突，必须停止并回到上游来源合同修正，不得在本任务中静默选择一方。

# 2. 业务目标

- `actor`: 后续 Ingestion Worker、Source Adapter、图片处理、Content Core 和发布门的实施者。
- `workflow_and_trigger`: `sources-v1` 已冻结，准备开发三个不同结构的 pilot Adapter；在写任何 Adapter、数据库或网页前，先建立所有生产者和消费者共同遵守的、版本化且可机器验证的内容交接合同。
- `single_outcome`: 形成一套正式的 `Generation Example v1` 与 `Adapter Output v1` 合同，使不同来源结构都能无损表达原始 Prompt、输入/输出图片角色、来源 Commit、配对证据、上游模型声明、来源与权利证据，并能在进入后续内容层前 fail closed。
- `observable_results`:
  - `RESULT-001`: `Generation Example v1` Schema 能表达并验证最小可信内容单元，且每个输出图片都能反向定位到确切 Prompt、生成上下文和来源证据。
  - `RESULT-002`: `Adapter Output v1` 明确区分有效提取记录、待解析资产引用和逐案例解析错误；Adapter 不能在合同中执行分类、去重、质量判断、权利裁决或发布决定。
  - `RESULT-003`: 三个已选 pilot 的结构画像均有独立契约样例，证明结构化 JSON、Markdown 图文页和大型编译图库可以进入同一合同，而无需共享同一解析算法。
  - `RESULT-004`: 无副作用 Validator 同时校验两个 Schema、正反例样例、跨合同引用、版本兼容、pilot/Commit 绑定与重复执行确定性。
- `non_goals`:
  - 不实现 Git 镜像、更新检测、定时同步、生产 Adapter、图片下载、图片转码或对象存储。
  - 不实现数据库、迁移、API、网页、搜索、分类、去重、Canonical Case、权利审核或 Publication Version。
  - 不修改 `sources-v1.yaml`、来源审计产物、`1.md` 或 TASK-0001 产物。
  - 不复制三个上游项目的完整 Prompt 库或图片资产到仓库；每个正例只保留一个固定 Commit 的真实最小案例、来源位置、Prompt 原文、资产路径/URL 和已验证哈希，不保存图片字节。
  - 不对外部仓库、Issue、PR、作者或其他外部系统执行写操作。

# 3. 需求质疑与确认

- `user_statement`: 在来源已经稳定固定后，继续严谨推进可提取图片与 Prompt 的长期内容系统。
- `REQ-001` (`required_behavior`): 创建版本化的 `Generation Example v1` JSON Schema，定义一个可独立验证的内容证据包；其中 Prompt、Generation Example、输入/输出资产引用、来源位置和配对证据之间必须可闭合解析。
- `REQ-002` (`required_behavior`): 创建版本化的 `Adapter Output v1` JSON Schema 和文字合同，定义批次身份、来源/Commit/Adapter 版本、有效案例候选、资产引用、来源声明、原始标签、逐案例解析错误和确定性字段。
- `REQ-003` (`required_behavior`): 明确 Adapter 输出与最终 Generation Example 的状态边界：Adapter 可以输出尚未获取内容哈希的资产引用，但只有解析到受验证资产记录、来源位置和内容哈希后才能形成有效 Generation Example。
- `REQ-004` (`required_behavior`): 固定配对方法、配对状态、来源声明、未知值、稳定身份、扩展字段和版本兼容规则，禁止通过置信度、默认值或推测把弱证据提升为强事实。
- `REQ-005` (`required_behavior`): 为 `g0dam-work-prompts`、`joesai-commercial-prompts`、`conardli-gpt-image-2-101` 各选择 TASK-0001 已记录 Prompt/asset hash 的质量抽检案例，从登记的固定 Commit 取回确切 Prompt 和来源定位，建立一个真实、最小、可追溯契约正例，并建立覆盖核心失败路径的显式变异反例；不得用合成 Prompt 冒充真实来源事实。
- `REQ-006` (`required_behavior`): 创建合同说明文档和无副作用 Validator；Schema、说明文档、fixtures 与验证器必须表达同一套 v1 语义，并在重复执行时得到相同稳定结论。
- `INV-001`: 固定 `source_id + revision_sha` 下的原始 Prompt 不得被清洗、翻译、补全或改写；任何派生文本必须是独立记录，且本任务不创建派生文本流程。
- `INV-002`: 每个有效 Generation Example 至少有一个 `output` 资产；每个输出资产必须明确属于一个 Generation Example，不能只挂在案例级图片集合上。
- `INV-003`: 未知模型、参数、作者或原始链接必须显式保存为 `unknown`、`null` 或缺失证据状态；不得从仓库名称、目录名、Prompt 内容或图片外观推断。
- `INV-004`: Adapter 只提取上游事实和结构证据，不得输出最终分类、Canonical 合并、质量通过、权利裁决、公开状态或自动发布决定。
- `INV-005`: 一个 Generation Example 文档内的 Prompt/资产引用必须全部解析到同一受验证文档中的记录；每个最终资产记录必须包含来源定位和 SHA-256 内容哈希。
- `INV-006`: `inferred_local_order` 不能成为 `strong`；`ambiguous` 不能进入有效 Generation Example 或自动发布候选，只能进入解析错误或人工审核路径。
- `INV-007`: Adapter 批次和其中每条记录必须绑定 `sources-v1` 中存在的 `source_id` 与该次固定 `revision_sha`；三个 pilot 契约样例必须绑定各自已登记 Commit。
- `INV-008`: 相同来源快照、Adapter 版本和输入记录重复执行时，稳定身份、业务字段、排序和语义摘要保持一致；运行时间、日志路径等动态元数据不得参与稳定身份或内容摘要。
- `INV-009`: v1 合同默认拒绝未声明字段；来源特有的保留信息只能进入明确、命名空间化的扩展容器，且不得覆盖标准字段或被下游当作已验证事实。
- `INV-010`: 合同必须保存权利声明、证据链接或未知状态，但 Adapter Output 和 Generation Example 均不得把这些事实直接转换为公开授权；发布决定仍属于 Publication Layer。
- `material_ambiguities`:
  - `1.md` 的 JSON 仅是建议形状。执行者可以采用内联记录或同文档引用表，但必须满足 `INV-001` 至 `INV-010` 和跨引用闭合，不得只复刻示例字段而遗漏不变量。
  - Adapter 输出可能包含部分成功。v1 必须允许有效记录与逐案例 `parse_errors` 并存，但来源身份、Commit、Schema 版本或批次级合同错误必须使整个批次无效。
  - 资产内容哈希在 Adapter 提取阶段可能尚不可得。v1 必须明确区分“待解析资产引用”和“可进入 Generation Example 的已解析资产记录”，不能用空哈希伪装完成。
- `decisions_and_authority`:
  - `1.md` 明确 Generation Example 是最小可信内容单元，并明确 Adapter 只提取事实；这两个边界是本任务不可更改的合同权威。
  - v1 支持的配对方法至少包括 `explicit_structured_reference`、`explicit_markdown_block`、`stable_native_mapping`、`inferred_local_order` 和 `ambiguous`。
  - 前三种方法只有在保存可追溯结构证据时才可标记 `strong`；`inferred_local_order` 默认进入人工审核，`ambiguous` fail closed。
  - 不支持的 `schema_version` 必须拒绝；改变必填字段含义、身份语义、配对等级或引用闭合规则需要新版本或经用户确认的变更记录。
  - 三个 pilot 仅用于证明合同覆盖三种结构，不授权在本任务中实现完整 Adapter 或复制其全部内容。

# 4. 业务场景与规则

- `SCN-001` 主路径: Adapter 从已登记来源的固定 Commit 提取一个案例，输出原始 Prompt、一个或多个资产引用、来源声明与强配对证据；资产解析后生成引用闭合、Schema 合法的 Generation Example。
- `SCN-002` 多图与可选输入边界: 一个案例可以没有输入图、包含多个输入/参考图、多个输出图或多个 Generation Example；每个资产角色和每个 Generation Example 的上下文必须独立明确。
- `SCN-003` 弱配对或歧义路径: Prompt 与图片只能依靠相邻顺序推断，或一条 Prompt 与多图关系不明。Adapter 必须保存原始位置和诊断，将记录置于人工审核或解析错误，不得构造强配对 Generation Example。
- `SCN-004` 部分解析失败路径: 一个 Adapter 批次中部分案例合法、部分案例缺 Prompt、缺输出或引用无效。合法记录可以保留，失败记录必须带来源定位和机器可读错误；计数必须与输入覆盖相符。
- `SCN-005` 未解析资产路径: Adapter 已识别图片路径或外部 URL，但尚未读取字节和计算 SHA-256。该引用可以存在于 Adapter Output，不能伪装为最终资产或通过 Generation Example Gate。
- `SCN-006` 重复与版本路径: 同一固定 Commit 和 Adapter 版本重复产生相同稳定内容；换 Commit、Adapter 版本或合同主版本时身份边界和兼容行为明确，不静默覆盖旧记录。
- `SCN-007` fixture 获取失败路径: 固定 Commit 的公开源文件暂时不可读取。只有现有只读证据已经包含确切 Prompt、来源位置和资产哈希时才可复用；否则任务必须保持未完成，不得用合成内容替代真实 pilot 正例。
- `RULE-001`: `source_id` 必须来自 `sources-v1`；`revision_sha` 必须是完整固定 Commit SHA，不接受分支名、移动标签或默认分支 HEAD 作为内容版本。
- `RULE-002`: 每个 Adapter 批次必须声明 `schema_version`、`source_id`、`revision_sha`、`adapter_id` 和 `adapter_version`；批次级身份错误使整个批次无效。
- `RULE-003`: 每个案例候选必须有 Adapter 在当前 `source_id + revision_sha` 内稳定生成的 `source_case_key`，并保存原生 ID 或结构定位证据；数组顺序、运行时间和随机值不得作为唯一身份来源。
- `RULE-004`: 原始 Prompt 必须保存逐字文本、语言未知状态和来源定位；空字符串、仅标题、仅标签或执行者补写内容不算有效原始 Prompt。
- `RULE-005`: 资产引用角色必须区分输入/参考与输出，至少支持 `output_primary`；来源路径与外部 URL 至少存在一个。最终资产记录必须额外具有 SHA-256，并能由 `asset_id` 闭合引用。
- `RULE-006`: Generation Example 必须保存上游模型与参数为 source claim；v1 至少区分 `source_claimed` 与 `unknown`，不得把 source claim 表述为官方验证。
- `RULE-007`: 配对对象必须同时保存 method、status、可选 confidence 和一个或多个来源定位证据；confidence 只能补充证据，不能改变 method 对 status 的上限。
- `RULE-008`: Adapter 批次中的有效记录与 `parse_errors` 必须互斥且可计数；错误至少包含稳定案例定位、错误代码、阶段和非敏感说明，不得吞掉失败案例。
- `RULE-009`: 契约样例和 Validator 必须证明三种 pilot 画像：结构化 JSON、Markdown Prompt 页面＋manifest、大型多分类编译图库；每个正例优先选择 TASK-0001 `quality_sampling.samples` 已记录 `case_id`、`prompt_sha256`、`image_sha256` 和来源路径的案例，并绑定真实 source_id、固定 Commit、确切 Prompt 和资产路径/hash，但不要求复刻上游全部字段或保存图片字节。
- `RULE-010`: 合同文档必须定义稳定字段、动态字段、排序、扩展容器、未知值、引用解析、错误语义和版本升级规则；Schema 与 Validator 不得与文档相互矛盾。
- `RULE-011`: 正例 fixture 必须全部通过；每个核心不变量至少有一个反例或自检变异会非零失败，且失败输出能定位到规则或记录。
- `RULE-012`: Validator 必须只读取本地文件、结果确定、无网络和外部写入；相同输入重复运行的业务摘要必须一致。
- `RULE-013`: fixture 准备阶段只允许读取 `sources-v1` 已登记的公开固定 Commit；请求必须有超时和有限重试，不使用登录态，不执行仓库代码，不保留完整下载或缓存。真实正例一旦写入仓库，正式 Validator 不再依赖网络。
- `RULE-014`: 正式 Validator 必须从只读 `D:/image2/.task-runs/TASK-0001/**/active-candidate-full-metrics.json` 发现 TASK-0001 的质量样本 hash 证据；若找到多个文件，只允许内容等价或能明确识别权威历史版本，冲突或缺失必须 fail closed。
- `STATE-001` Adapter 记录状态:
  - `extracted_candidate`: 原始事实已提取，资产可以仍是 unresolved reference。
  - `contract_valid`: 记录满足 Adapter Output v1，可进入资产解析与 staging；不代表质量、权利或发布通过。
  - `quarantined`: 记录存在弱配对、歧义、缺字段或引用错误，只能进入 `parse_errors`/人工审核。
- `STATE-002` Generation Example 状态:
  - `not_constructible`: Prompt、输出资产、来源身份、引用闭合或强配对条件不足。
  - `contract_valid`: Prompt、Generation Example、资产、来源和配对引用闭合；仍不代表已分类、去重、权利批准或发布。
- `FLOW-001`: `sources-v1` 来源身份 → Adapter Output 原始事实 → 资产获取/哈希与 pairing staging → Generation Example v1 → 后续去重、分类、权利与发布门。

### Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| `DEP-001` | TASK-0001 的 `sources-v1` 与审计结果 | TASK-0002 合同 | execution prerequisite / authority input | TASK-0001 交付物、`1.md` 第 15/18 节 | confirmed | 不表示来源内容已经进入生产库存 | 本任务的 pilot、source_id、Commit 与结构画像 |
| `REL-001` | Adapter Output v1 | Generation Example v1 | producer-to-consumer projection | `1.md` 第 5/6/7 节 | confirmed | Adapter 合法不表示最终 Generation Example 已可构造 | 引用闭合、资产解析、配对与错误语义 |
| `PERM-001` | Adapter / Generation Example | Publication Layer | decision boundary | `1.md` 第 3/7/12 节 | confirmed | 不得推导分类、质量、权利批准或公开状态 | 合同字段、禁止字段与 Gate |

- `risk_sensitive_invariants`:
  - 两个 Schema 将成为三个 pilot Adapter、未来批量 Adapter、Content Core 和测试夹具的共享合同；错误字段语义会跨模块持续传播。
  - Generation Example 的引用闭合和稳定身份影响去重、历史版本、幂等入库和前台追溯，不能依赖动态字段或隐式数组位置。
  - Adapter 的事实职责与 Publication Layer 的决策职责必须隔离，避免来源解析代码绕过权利与质量门。
  - 部分失败必须可观察；静默丢弃案例会让后续数量突降和同步异常无法判断。
- `inapplicable_faces_with_reason`:
  - UI 页面状态：本任务不实现网页或管理后台。
  - 生产并发与队列重试：本任务只冻结静态合同，不实现调度、队列和数据库事务。
  - 数据迁移：当前尚无生产持久化形状；v1 版本规则只定义未来兼容边界，不执行迁移。
  - 外部副作用：fixture 准备仅执行固定 Commit 的只读公开请求；正式 Validator 不访问网络、不下载图片、不修改上游或外部系统。

# 5. 当前证据与目标差异

- `FACT-001`: `D:/image2/1.md` 已定义四层数据架构、Generation Example 的最小可信关系、数据不变量、Adapter 职责、配对方法和自动发布最低条件，但只提供建议 JSON，没有正式 Schema 或可执行验证器。
- `FACT-002`: `D:/image2/config/sources-v1.yaml` 已选择三个 active pilot：
  - `g0dam-work-prompts`，`structured_manifest_json`，固定 Commit `690c2d6969a65b406b17ba7d41f18695a652c3fe`。
  - `joesai-commercial-prompts`，`markdown_prompt_pages_with_manifest`，固定 Commit `6f9b01fd21efbc05cfdde1176fc988013d3c4a9b`。
  - `conardli-gpt-image-2-101`，`compiled_multi_category_case_gallery`，固定 Commit `971b67dc8cbca8cf6eb32e196fea04bddd6abe99`。
- `FACT-003`: TASK-0001 的正式 Validator 当前确认 50 条审计记录、3 个 active pilot、GATE-001 至 GATE-004 全部通过，来源注册表可作为本任务输入。
- `FACT-004`: 当前工作区不存在 `generation-example-v1` Schema、`adapter-output-v1` Schema、内容合同文档、契约 fixtures 或对应 Validator。
- `FACT-005`: 当前工作区不是 Git 仓库；Windows Python Launcher 已验证可使用 Python 3.12，TASK-0001 的本地无副作用验证器已在该解释器通过。
- `FACT-006`: `D:/image2/.task-runs/TASK-0001` 的只读历史证据中存在 `active-candidate-full-metrics.json`，包含三个 pilot 质量样本的 case_id、Prompt hash、asset hash 和来源路径，可作为 fixture provenance 的本地交叉验证输入。
- `ASM-001`: 通用合同语义由设计文档、来源注册表和审计事实决定；三个正例需要对已登记固定 Commit 做最小只读内容获取，但不需要执行任何上游仓库代码。
- `ASM-002`: TASK-0001 的只读历史 `active-candidate-full-metrics` 证据已为三个 pilot 的质量样本记录 case_id、source path、Prompt hash 和 asset hash；缺少的 Prompt 原文必须从相同固定 Commit 读取并与历史 hash 匹配。合成数据只能作为明确的负例变异，不能标记为真实 source fact。
- `current_execution_path`: 后续 Adapter 只有自然语言职责和三个来源策略名，没有统一输出 Schema；未来实现者可能各自定义字段、弱化配对证据或把未解析图片直接当作最终资产。
- `target_delta`: 将叙述性数据模型冻结为两个版本化 Schema、一个规范文档、一套三类 pilot 契约 fixtures 和一个跨文件语义 Validator，使生产者与消费者在写实现前共享同一合同。
- `evidence_gaps`:
  - 尚无可验证的稳定身份、版本、扩展字段和动态字段规则。
  - 尚无 Adapter 部分失败、弱配对、未解析资产和跨引用错误的机器可读合同。
  - 尚无证明三种 pilot 结构可进入同一合同的正例和反例。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `D:/image2/schemas/generation-example-v1.schema.json`
  - `D:/image2/schemas/adapter-output-v1.schema.json`
  - `D:/image2/docs/contracts/content-contract-v1.md`
  - `D:/image2/fixtures/contracts/content-contract-v1/**`
  - `D:/image2/scripts/validate_content_contracts.py`
  - `C:/Users/admin/.codex/task-state/image2/**`，仅限正式生命周期为 TASK-0002 自动解析出的唯一 canonical run 目录，用于 sidecar、receipt、独立审查和 Completion Report
- `hard_protected_scope`:
  - 不修改 `D:/image2/1.md`、现有 Markdown/XLSX 调研材料、`reports/source-audit-v1.*`、`config/sources-v1.yaml`、TASK-0001 的两个 Schema 或 `scripts/validate_source_registry.py`。
  - `D:/image2/.task-runs/**` 只作为历史证据，TASK-0002 不得写入。
  - `D:/image2/.work/source-audit/**` 保持只读，不新增缓存、下载、克隆或 fixtures。
  - 不创建生产应用目录、数据库迁移、Adapter 实现、媒体文件、对象存储或网页代码。
  - 只允许读取 `sources-v1` 已登记的公开固定 Commit；不访问需要凭据的资源，不执行不可信上游代码，不进行任何外部写入。
- `protected_contracts_and_invariants`:
  - 保持 `1.md` 的 Source/Evidence/Canonical/Publication 四层职责边界。
  - 保持原始事实与派生内容分离、图文强绑定、未知不猜测、Source Claim 不等于官方事实、公开与内部库存分离。
  - 保持 `sources-v1` 的 source_id、固定 Commit、pilot 与 fail-closed 权利默认值不变。
  - 不以 Schema 能通过为理由弱化真实引用闭合、失败路径或消费者语义。
- `authorization_limits`: 本任务授权对三个已登记 pilot 的固定 Commit 执行最小、只读、无登录内容获取，以建立各一个真实合同 fixture；允许瞬时读取图片字节以核对已有 SHA-256，但不得把图片字节、完整仓库或完整数据集写入工作区。除此之外只授权创建本地合同、Schema、fixtures、Validator 和工作区外执行证据；不授权实现后续管线、公开图片、作出法律结论、变更来源状态或接受兼容性例外。
- `stop_if_scope_expands`:
  - 需要改变 `1.md` 的最小可信内容单元、配对等级、Adapter 职责或发布权利边界。
  - 需要修改 `sources-v1` pilot、Commit、状态或 Adapter 策略才能使样例通过。
  - 需要决定生产数据库/API/对象存储的具体公共形状，或需要实现真实 Adapter 才能完成合同。
  - 发现现有权威材料对身份、资产解析或配对语义存在无法兼容的冲突。
  - 任一 pilot 的确切 Prompt、来源位置和资产哈希既无法从固定 Commit 读取，也不存在可复用的同 Commit 只读证据。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`:
  - `caller`: 项目所有者以 TASK-0001 已冻结的 registry 启动内容合同冻结。
  - `entry`: `1.md` 的数据不变量与 Adapter 职责，加上 `sources-v1` 的三个 pilot 身份、Commit 和结构画像。
  - `current_path`: 叙述性建议 Schema → 各后续实现者自行解释；当前没有机器合同或跨模块失败门。
  - `target_path`: registry 绑定 → Adapter Output v1 → 资产/配对解析边界 → Generation Example v1 → 后续 Adapter 和 Content Core 共同消费。
  - `final_consumer`: 下一张三来源纵向管线任务；其 Adapter 必须产出 Adapter Output v1，其 staging/Content Core 必须只接受通过 Generation Example v1 验证的记录。
- `current_contract`: 只有 `1.md` 的建议 JSON、文字不变量、Adapter 职责和配对表；没有版本、错误、兼容、稳定身份、部分失败和引用闭合的可执行定义。
- `target_contract`:
  - 两个 Schema 都显式声明合同版本和 JSON Schema dialect。
  - Adapter Output 是生产者合同，允许 unresolved asset refs 和逐案例 parse errors，但禁止下游决策字段。
  - Generation Example 是消费者可接受的证据合同，要求 Prompt、Generation Example、资产与来源引用闭合，输出资产已解析并具有 SHA-256。
  - 版本、扩展、未知值、错误代码、稳定字段和动态字段在文档与 Validator 中一致。
- `expected_touchpoints_or_search_anchors`:
  - 已验证输入：`D:/image2/1.md` 第 5、6、7、12、15、16 节。
  - 已验证输入：`D:/image2/config/sources-v1.yaml` 的 `pilots` 与三个 active source 条目。
  - 已验证输入：`D:/image2/reports/source-audit-v1.json` 的三个 pilot 审计记录。
  - 目标产物：第 6 节列出的两个 Schema、合同文档、fixtures 和 Validator。
- `wiring_to_final_consumer`:
  - `adapter-output-v1.schema.json` 约束未来三个项目专用 Adapter 的直接输出。
  - `generation-example-v1.schema.json` 约束后续 staging 转换和 Content Core 接受的最小可信证据包。
  - `content-contract-v1.md` 是字段语义、状态、版本、错误与职责边界的规范来源；Schema 负责结构，Validator 负责跨字段和跨文件语义。
  - 三个 pilot 正例只证明合同适配性；后续真实 Adapter 必须另建固定 Commit 源文件 fixtures 并产生运行证据。
- `failure_and_recovery`:
  - Schema 或语义失败：Validator 非零退出并报告文件、记录定位和规则；不得跳过失败 fixture。
  - 单条 Adapter 候选失败：进入 `parse_errors`，其他合法记录可保留；批次计数必须显示失败，不能静默丢弃。
  - 批次身份、版本或 registry 绑定失败：整个批次无效，不允许部分接受。
  - 未解析资产或歧义配对：保留 Adapter 事实并阻止 Generation Example 构造；修复来源映射后重新生成，不修改原始 Prompt。
  - 合同变更：改变必填语义、身份、枚举上限或引用规则时停止执行并建立版本/任务变更，不原地放宽 v1。
- `compatibility_and_error_semantics`:
  - 不支持的主合同版本 fail closed。
  - 未声明顶层/标准对象字段 fail closed；来源特有数据只能位于明确扩展容器。
  - 机器错误必须包含稳定错误代码和定位；自由文本只作诊断，不作程序分支合同。
  - 运行时间等动态元数据允许存在于明确 metadata 区，但不得改变稳定业务摘要。
- `implementation_freedom`: 在满足全部规则和 Gate 的前提下，执行者可选择 JSON Schema draft、内联或引用表布局、Python JSON/YAML 库、fixture 文件拆分和 Validator 内部结构；不得把实现选择升级为未经授权的业务规则。
- `selected_profile_obligations`:
  - `public-contract`: 明确生产者、消费者、版本、必填语义、未知值、错误、兼容、扩展、引用闭合和合同测试；未来实现不得绕过 Schema/Validator 直接建立私有字段合同。
  - `external-boundary`: fixture 获取只访问 registry 固定的公开 Commit 和必要源文件/图片，设置超时与有限重试；不使用凭据、不执行仓库代码、不保留完整克隆或下载；失败必须记录且不得用合成正例掩盖。

### Module Boundary

| module | owns | reads | writes/emits | consumes | must not do | authority source |
|---|---|---|---|---|---|---|
| Source Registry | 来源身份、状态、固定 Commit、pilot 画像 | TASK-0001 审计事实 | `sources-v1` | Source Manager、Adapter 选择、合同 fixtures | 不承载案例内容或发布决定 | `1.md` 第 4/5 节；TASK-0001 |
| Source Adapter | 上游事实提取和结构证据 | 固定 Commit 源文件、registry | Adapter Output v1 | 后续资产/配对 staging | 不改写 Prompt，不分类、去重、裁决权利或发布 | `1.md` 第 7.1 节 |
| Ingestion staging / media | 资产获取、内容哈希、引用解析、配对校验 | Adapter Output v1 | 可构造 Generation Example 的已解析记录或错误 | Content Core | 不把 unresolved/ambiguous 伪装为完整 Generation Example | `1.md` 第 5.2、6.3、9 节 |
| Content Core | 统一数据模型和来源证据保存 | Generation Example v1 | 后续 Canonical/rights/quality 输入 | 去重、分类、发布门 | 不删除 Source Case/Generation Example 来源证据 | `1.md` 第 5/6/10 节 |
| Publication Layer | 可见性、权利与质量决定 | Generation Example 及后续决策记录 | Publication Version | API/网页 | 不让 Adapter 或 Schema 合法性替代权利/质量判断 | `1.md` 第 5.1、12 节 |

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`, `REQ-003`, `REQ-004`, `INV-001`, `INV-002`, `INV-003`, `INV-005`, `INV-006`, `INV-008`, `INV-010`
- `owns_behavior`: 冻结可独立验证的 Generation Example v1 证据合同，使 Prompt、生成上下文、输入/输出资产、来源和配对证据全部闭合且不越权表达发布决定。
- `target_delta`: 将 `1.md` 的建议 JSON 和文字不变量转为版本化 JSON Schema、规范说明、正反例和跨字段验证规则。
- `business_result`: 后续 Content Core 能明确判断一个记录是否已经达到“最小可信内容单元”，而不是仅凭存在 Prompt 和图片数组作出猜测。
- `behavior_faces`:
  - `normal`: 一个原始 Prompt、可选输入图、至少一个已解析输出图、source claim 与 strong 配对。
  - `boundary`: 无输入图、多个输入/输出、未知模型/参数、多个 Generation Example 共享同一 Source Case。
  - `failure`: 空 Prompt、无输出、输出引用悬空、资产无来源/hash、weak/ambiguous 被标 strong、未知模型被猜测。
  - `empty`: 空证据包或只有 Source Case 而没有可构造 Generation Example 时不得通过。
  - `repeated`: 相同 fixture 重复验证得到相同稳定摘要和错误顺序。
  - `downstream_error`: 任何引用未闭合的文档必须阻止 Content Core 接受，而不是依赖未来数据库修复。
- `state_change`:
  - `entry_condition`: 只有建议字段和文字不变量。
  - `exit_condition`: Schema、文档、正反例和 Validator 对同一 v1 语义达成一致。
  - `failure_degradation`: 保持合同未完成并报告最早失败规则；不得通过放宽必填项绕过失败。
- `data_flow`:
  - `input_source`: `1.md` 的 Generation Example、数据不变量、资产角色和发布门规则。
  - `single_source_of_truth`: `content-contract-v1.md` 的语义＋`generation-example-v1.schema.json` 的结构，两者冲突时任务不完成。
  - `write_target`: Generation Example Schema、合同文档对应章节、正反例 fixtures、Validator 规则。
  - `downstream_consumers`: 三来源纵向 staging、Content Core、后续数据库/API 合同任务。
- `integration_edges`: Adapter Output 经资产解析后映射到 Generation Example；所有 prompt/asset id 必须在同一受验证证据包内解析。
- `expected_touchpoints`: `schemas/generation-example-v1.schema.json`、`docs/contracts/content-contract-v1.md`、`fixtures/contracts/content-contract-v1/generation-example/**`、`scripts/validate_content_contracts.py`
- `scope_boundary`:
  - `hard`: 不设计数据库表、API DTO 或发布状态；不允许 unresolved asset 进入最终合同。
  - `soft`: 不优化未来序列化性能或存储大小。
- `allowed_write_scope`: 仅第 6 节中与本 TASK 对应的 Schema、文档、fixtures、Validator 和外部执行证据。
- `acceptance_scenarios`:
  - 正常和多图边界 fixtures 通过且引用闭合。
  - unknown 模型/参数保持显式未知，不影响内部 Generation Example 合法性。
  - 空 Prompt、无输出、悬空引用、无 SHA-256 和非法强配对 fixtures 均被拒绝。
  - 重复验证摘要一致。
- `linked_tests`: `TEST-001`
- `stop_conditions`: 需要改变最小可信关系、允许未解析资产进入最终合同或引入发布决定字段。

### TASK-002

- `links`: `OBJ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `INV-004`, `INV-006`, `INV-007`, `INV-008`, `INV-009`, `INV-010`
- `owns_behavior`: 冻结 Adapter Output v1 生产者合同，使不同仓库结构以同一批次语义输出原始事实、资产引用、配对证据和逐案例错误，同时保持来源特有扩展和下游职责边界。
- `target_delta`: 将每个未来 Adapter 可能自定义的输出形状统一为版本化 envelope 和记录合同，并以三个 pilot 画像与失败变异证明适配性。
- `business_result`: 后续 Adapter 实现者只需解决来源解析，不再自行发明内容字段、错误格式、发布状态或稳定身份规则。
- `behavior_faces`:
  - `normal`: 有效批次包含来源/Commit/Adapter 身份和一个或多个可进入 staging 的案例候选。
  - `boundary`: 部分案例失败、外部资产 URL、无输入图、source-specific extensions、弱配对人工审核。
  - `failure`: 固定 Commit 最小案例不可取得、registry/Commit 不匹配、重复或不稳定 case key、错误被吞掉、禁止的分类/发布字段、ambiguous 进入有效记录。
  - `empty`: 来源确实没有可提取案例时允许零有效记录，但必须有覆盖计数和诊断；不能以空数组假装成功。
  - `repeated`: 相同来源快照和 Adapter 版本产生相同稳定记录、排序和摘要。
  - `downstream_error`: staging 只能消费 contract-valid 记录；parse_errors 和 unresolved refs 不能直接进入 Generation Example。
- `state_change`:
  - `entry_condition`: 来源策略名存在，但没有共同输出合同。
  - `exit_condition`: Adapter Schema、文档、三个 pilot 正例、反例和 Validator 形成一致的生产者边界。
  - `failure_degradation`: 无法表达的真实来源事实进入扩展或错误，不通过猜测/丢弃强行满足 Schema。
- `data_flow`:
  - `input_source`: `sources-v1`、三个 pilot 审计结构画像、各固定 Commit 的一个真实最小案例和 `1.md` Adapter 职责。
  - `single_source_of_truth`: `content-contract-v1.md` 的生产者语义＋`adapter-output-v1.schema.json` 的结构。
  - `write_target`: Adapter Output Schema、文档对应章节、pilot/negative fixtures、Validator 规则。
  - `downstream_consumers`: 后续三个项目专用 Adapter、资产/配对 staging、解析错误监控。
- `integration_edges`: registry 身份/Commit → Adapter envelope；有效候选 → ASSEMBLY-001；parse_errors → 后续错误存储，不进入 Generation Example。
- `expected_touchpoints`: `schemas/adapter-output-v1.schema.json`、`docs/contracts/content-contract-v1.md`、`fixtures/contracts/content-contract-v1/adapter-output/**`、`scripts/validate_content_contracts.py`
- `scope_boundary`:
  - `hard`: 不实现真实解析器、不复制完整来源内容、不输出下游决策。
  - `soft`: 不决定未来 Adapter 类继承结构或运行调度接口。
- `allowed_write_scope`: 仅第 6 节中与本 TASK 对应的 Schema、文档、fixtures、Validator 和外部执行证据。
- `acceptance_scenarios`:
  - 三种 pilot 结构画像的真实最小正例均通过，并绑定正确 source_id/Commit、来源位置、Prompt 原文和资产哈希。
  - 部分失败批次保留合法记录和可计数 errors，不静默遗漏。
  - registry/Commit 漂移、非法强配对、禁止字段和不稳定身份变异均被拒绝。
  - 重复验证稳定摘要一致。
- `linked_tests`: `TEST-002`
- `stop_conditions`: 任一真实最小正例无法从固定 Commit 或同 Commit 只读证据获得；需要变更 pilot/Commit、实现真实 Adapter，或允许 Adapter 作出分类、权利、质量和发布决定。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`
- `end_to_end_entry`: `sources-v1` 中三个 pilot 的固定身份和结构画像。
- `shared_contract_state_data`: schema_version、source_id、revision_sha、source_case_key、原始 Prompt、资产角色/来源定位、generation claim、pairing method/status/evidence、parse errors、稳定与动态字段边界。
- `final_consumer`: 下一阶段三来源纵向 Adapter/staging 任务。
- `cross_task_failure_path`: Adapter Output 合法不能自动证明 Generation Example 合法；unresolved asset、weak/ambiguous pairing、悬空引用或缺 SHA-256 必须在投影 Gate 被阻止，且错误不得从批次统计中消失。
- `linked_test_evidence_gate`: `TEST-003` / `EV-003` / `GATE-003`

# 9. 验证与验收

- `consumer_chain_validation`: `TEST-003` 必须验证 `sources-v1 pilot → Adapter Output fixture → 资产解析边界 → Generation Example fixture` 的正反向引用和状态约束；分别通过两个 Schema 不能替代该组装验证。
- `real_integration_evidence`: 当前尚无生产 Adapter/Content Core，因此真实集成证据限定为同一 Validator 内对三个真实固定 Commit 最小案例的跨合同投影、registry 绑定和失败变异；后续 Adapter 任务仍必须建立更完整的固定 Commit 源文件 fixtures 做真实解析测试。

### RISK-001

- `links`: `REQ-005`, `TASK-002`, `TEST-002`
- `description`: 合同被某一个 pilot 的当前字段结构绑死，其他来源只能丢字段或绕过 Schema。
- `mitigation`: 使用三个结构画像和命名空间扩展，Gate 检查共同语义而不是要求相同解析算法。

### RISK-002

- `links`: `REQ-003`, `INV-005`, `SCN-005`, `TEST-001`, `TEST-003`
- `description`: 只识别到 URL/path 的未解析图片被当成最终资产，导致缺少哈希、图片失效或来源不可追溯。
- `mitigation`: 分离 Adapter asset reference 与 Generation Example resolved asset；跨合同 Gate 明确拒绝 unresolved 引用。

### RISK-003

- `links`: `INV-006`, `RULE-007`, `TEST-001`, `TEST-002`
- `description`: 一个高 confidence 数值掩盖弱配对方法，使 Prompt 与错误图片被错误绑定。
- `mitigation`: method 决定 status 上限，Validator 对非法组合做负例自检，confidence 不参与升级。

### RISK-004

- `links`: `INV-008`, `SCN-006`, `TEST-001`, `TEST-002`
- `description`: 动态时间、数组位置或随机 ID 进入稳定身份，造成重复同步产生新记录或旧记录漂移。
- `mitigation`: 文档明确稳定/动态字段和排序，Validator 对同一 fixtures 重跑并比较稳定业务摘要。

### RISK-005

- `links`: `INV-004`, `INV-010`, `PERM-001`, `TEST-002`, `TEST-003`
- `description`: Adapter 输出分类、质量、权利批准或发布状态，绕过 Content Core 与 Publication Layer。
- `mitigation`: Schema 默认拒绝未声明字段，负例加入禁止决策字段并要求非零失败。

### RISK-006

- `links`: `REQ-006`, `RULE-010`, `TEST-003`
- `description`: Schema、说明文档、fixtures 与 Validator 对字段或状态含义解释不一致。
- `mitigation`: Validator 读取两个 Schema、registry 和全部 fixtures，并通过跨合同规则和文档声明清单做一致性检查。

### RISK-007

- `links`: `REQ-005`, `SCN-007`, `RULE-009`, `RULE-013`, `TEST-002`
- `description`: 为了避免网络读取或真实数据处理，执行者用合成 Prompt 配上真实 source_id/Commit，制造能够过 Schema 但 provenance 为假的正例。
- `mitigation`: 每个 pilot 正例必须记录固定 Commit 来源路径/URL、原始 case id、Prompt hash、asset hash 和最小获取证据；Validator 核对 fixture manifest 与 registry/审计绑定，禁止 synthetic 标记的 payload 充当正例。

### TEST-001

- `links`: `TASK-001`, `REQ-001`, `REQ-003`, `REQ-004`, `INV-001`, `INV-002`, `INV-003`, `INV-005`, `INV-006`, `INV-008`, `RISK-002`, `RISK-003`, `RISK-004`
- `method`: 使用正式 Validator 校验 Generation Example Schema 自身和全部正例；运行内置负例/变异，覆盖空 Prompt、无输出、悬空 prompt/asset 引用、最终资产无 SHA-256、非法配对 method/status、模型证据猜测、动态字段污染稳定摘要和不支持版本。
- `expected_observable_result`: 所有正例通过且引用闭合；所有变异均由预期规则拒绝；同一输入两次运行的稳定摘要、错误排序和 Gate 结果一致。
- `failure_path_covered`: 缺字段、错误引用、多图关系、未知模型、弱配对冒充 strong、未解析资产冒充完成、版本不兼容。
- `cannot_prove`: 不能证明未来数据库引用或 API 序列化与该合同一致，也不能证明图片字节安全或权利可公开。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: Schema 路径/哈希、正例文件清单、每个负例对应规则与非零结果、引用闭合摘要、稳定内容摘要两次对比和零未预期错误；实际结果写入执行 sidecar。

### TEST-002

- `links`: `TASK-002`, `REQ-002`, `REQ-004`, `REQ-005`, `REQ-006`, `INV-004`, `INV-006`, `INV-007`, `INV-008`, `INV-009`, `INV-010`, `RISK-001`, `RISK-003`, `RISK-004`, `RISK-005`, `RISK-007`
- `method`: 使用正式 Validator 校验 Adapter Output Schema、三个 pilot 正例、fixture manifest 和部分失败批次；核对每个正例的 case_id、真实固定 Commit 来源定位、Prompt/asset hash 与 registry、审计记录及 TASK-0001 只读质量样本证据一致；运行负例/变异，覆盖合成正例冒充、registry/Commit 不匹配、不稳定或重复 case key、ambiguous 进入有效记录、吞掉 errors、非法标准外字段、扩展覆盖标准字段、分类/权利批准/发布字段和不支持版本。
- `expected_observable_result`: 三个真实最小 pilot 正例均通过且绑定正确 source_id/Commit、来源位置、Prompt/asset hash；部分失败批次的有效数、错误数和覆盖数一致；所有合成冒充、越权、身份、版本和确定性变异均被拒绝。
- `failure_path_covered`: 空来源、部分解析失败、弱配对、外部 URL、来源特有扩展、registry 漂移和 Adapter 越权。
- `cannot_prove`: 不能证明三个真实上游仓库的完整当前内容可被未来 Adapter 正确解析；该证明属于后续固定 Commit Adapter fixtures。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: 三个 pilot fixture 的 source_id、revision_sha、原始 case id、来源路径/URL、Prompt hash、asset hash、最小获取证据、structure profile、有效/错误/覆盖计数、Schema 结果、负例规则矩阵、禁止字段检查和重复运行稳定摘要；实际结果写入执行 sidecar。

### TEST-003

- `links`: `OBJ-001`, `ASSEMBLY-001`, `TASK-001`, `TASK-002`, `REQ-003`, `REQ-005`, `REQ-006`, `REL-001`, `PERM-001`, `RISK-002`, `RISK-005`, `RISK-006`
- `method`: 对三个 pilot 的 Adapter Output 正例执行参考投影/跨合同语义检查：contract-valid 候选在补齐已解析资产记录后形成 Generation Example 正例；unresolved、weak/ambiguous、悬空引用和 parse_error 记录不得形成 Generation Example。双向检查 registry、Adapter Output、Generation Example 和合同文档声明的一致性。
- `expected_observable_result`: 三个结构画像均至少产生一个合法 Generation Example 契约结果；所有 source_id、Commit、case key、Prompt、资产角色、来源定位和配对证据可追溯；所有阻断记录保持阻断；Schema、文档和 Validator 无字段/枚举漂移。
- `failure_path_covered`: 仅 Schema 各自通过但跨合同无法映射、错误记录被遗漏、unresolved 资产泄漏、Adapter 决策字段传播到下游、pilot/Commit 漂移。
- `cannot_prove`: 不能证明生产媒体管线、数据库、去重、权利门、网页或 Commit 更新同步已经实现。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: 三个 pilot 的跨合同映射矩阵、每个合法/阻断记录的结果、registry 双向绑定、引用闭合结果、Schema/文档字段一致性摘要、两次执行确定性对比和无剩余漂移列表；实际结果写入执行 sidecar。

### 正式 Validator Manifest

以下声明是 TEST-001 至 TEST-003 的正式行为验证入口。预检只确认解释器兼容性，不产生通过结论。

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "content-contract-v1",
      "command": [
        "py",
        "-3.12",
        "scripts/validate_content_contracts.py",
        "--generation-schema",
        "schemas/generation-example-v1.schema.json",
        "--adapter-schema",
        "schemas/adapter-output-v1.schema.json",
        "--registry",
        "config/sources-v1.yaml",
        "--audit",
        "reports/source-audit-v1.json",
        "--prior-source-evidence-root",
        ".task-runs/TASK-0001",
        "--contract-doc",
        "docs/contracts/content-contract-v1.md",
        "--fixtures",
        "fixtures/contracts/content-contract-v1",
        "--self-test",
        "--determinism-check",
        "--json"
      ],
      "cwd": ".",
      "timeout_seconds": 120,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "reports/source-audit-v1.json",
        ".task-runs/TASK-0001",
        "schemas/generation-example-v1.schema.json",
        "schemas/adapter-output-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "fixtures/contracts/content-contract-v1",
        "scripts/validate_content_contracts.py"
      ],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": [
        "py",
        "-3.12",
        "-c",
        "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
      ],
      "preflight_timeout_seconds": 10
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | Generation Example 最小可信合同 | `OBJ-001` / `TASK-001` / `TEST-001` | 正例、边界和确定性检查通过；缺 Prompt/输出/hash、悬空引用、非法 strong、猜测模型和不支持版本均被拒绝 | `EV-001` | 不证明生产持久化、媒体安全和法律权利 |
| `GATE-002` | Adapter Output 生产者合同 | `OBJ-001` / `TASK-002` / `TEST-002` | 三个 pilot 画像和部分失败批次通过；registry/Commit、身份、错误、扩展、越权字段和版本规则全部 fail closed | `EV-002` | 不证明真实完整仓库解析已实现 |
| `GATE-003` | Adapter 到 Generation Example 组装闭环 | `OBJ-001` / `ASSEMBLY-001` / `TASK-001` / `TASK-002` / `TEST-003` | 三个结构画像可形成合法契约结果，阻断记录不泄漏，registry/引用/文档/Schema 双向一致且重复执行确定 | `EV-003` | 不证明后续数据库、去重、权利、发布和网页链路 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `schemas/generation-example-v1.schema.json`
  - `schemas/adapter-output-v1.schema.json`
  - `docs/contracts/content-contract-v1.md`
  - `fixtures/contracts/content-contract-v1/manifest.json`
  - `fixtures/contracts/content-contract-v1/adapter-output/g0dam-work-prompts.valid.json`
  - `fixtures/contracts/content-contract-v1/adapter-output/joesai-commercial-prompts.valid.json`
  - `fixtures/contracts/content-contract-v1/adapter-output/conardli-gpt-image-2-101.valid.json`
  - `fixtures/contracts/content-contract-v1/generation-example/g0dam-work-prompts.valid.json`
  - `fixtures/contracts/content-contract-v1/generation-example/joesai-commercial-prompts.valid.json`
  - `fixtures/contracts/content-contract-v1/generation-example/conardli-gpt-image-2-101.valid.json`
  - `fixtures/contracts/content-contract-v1/negative-cases.json`
  - `scripts/validate_content_contracts.py`

### 必交产物

- `schemas/generation-example-v1.schema.json`
- `schemas/adapter-output-v1.schema.json`
- `docs/contracts/content-contract-v1.md`
- `fixtures/contracts/content-contract-v1/manifest.json`
- `fixtures/contracts/content-contract-v1/adapter-output/g0dam-work-prompts.valid.json`
- `fixtures/contracts/content-contract-v1/adapter-output/joesai-commercial-prompts.valid.json`
- `fixtures/contracts/content-contract-v1/adapter-output/conardli-gpt-image-2-101.valid.json`
- `fixtures/contracts/content-contract-v1/generation-example/g0dam-work-prompts.valid.json`
- `fixtures/contracts/content-contract-v1/generation-example/joesai-commercial-prompts.valid.json`
- `fixtures/contracts/content-contract-v1/generation-example/conardli-gpt-image-2-101.valid.json`
- `fixtures/contracts/content-contract-v1/negative-cases.json`
- `scripts/validate_content_contracts.py`

### 完成与回写规则

- `documentation_impact`: updated；新增正式内容合同文档、Schema 和契约 fixtures，不修改 `1.md`、来源注册表或历史调研。
- `repository_hygiene_requirement`:
  - 每个 pilot fixture 只保存一个真实固定 Commit 案例所需的最小 JSON、Prompt 原文、来源定位和资产哈希；不保存图片字节、上游完整 Prompt 库、完整源文件、Git 仓库、LFS 对象、凭据或网络缓存。
  - `D:/image2/.task-runs` 与 `D:/image2/.work/source-audit` 保持只读；正式执行证据写入工作区外 canonical root。
  - Validator 不产生 bytecode cache；正式运行使用 `PYTHONDONTWRITEBYTECODE` 或等效无缓存方式。
  - 当前工作区不是 Git 仓库，因此不要求 commit；最终必须列出新增文件并确认第 6 节保护文件未修改。
- `external_review`: policy=never；reason=本任务冻结本地跨模块数据合同并要求 L3 独立语义审查，但不需要额外外部模型审阅；任何业务不变量或兼容性变更仍须由用户确认。
- `non_completion_rules`:
  - 两个 Schema、合同文档、三种 pilot 正例、核心反例、Validator 任一缺失时不得完成。
  - 任一 pilot 正例没有真实固定 Commit 来源定位、Prompt/asset hash，或使用合成 Prompt 冒充来源事实时不得完成。
  - TASK-0001 只读质量样本证据缺失、存在冲突，或 fixture 的 case_id/Prompt hash/asset hash 无法与之匹配时不得完成。
  - Generation Example 允许空 Prompt、无输出、悬空引用、最终资产无 SHA-256 或 weak/ambiguous 冒充 strong 时不得完成。
  - Adapter Output 允许静默丢弃错误、动态身份、registry/Commit 漂移、标准字段被扩展覆盖或分类/权利批准/发布决定时不得完成。
  - unresolved asset reference 能直接通过 Generation Example Gate 时不得完成。
  - Schema、文档、fixtures 和 Validator 对版本、字段、枚举、状态或错误语义存在漂移时不得完成。
  - TEST-001 至 TEST-003 的实际证据未产生、GATE-001 至 GATE-003 任一不通过、保护范围被修改或正式 Completion Report 未通过校验时不得完成。
  - 若必须改变 `1.md`、`sources-v1`、pilot/Commit、核心数据不变量或发布职责边界，必须停止并请求任务卡变更，不得把 TASK-0002 标记完成。

执行时将 `CODEX_TASK_STATE_ROOT` 固定为 `C:/Users/admin/.codex/task-state/image2`；run ID、candidate、实际命令、实际输出、文件哈希、Validator receipt、独立审查、最终状态和任何跳过项写入正式生命周期自动解析的唯一 TASK-0002 canonical run 目录，不写回本任务卡，也不得写入仓库内 `D:/image2/.task-runs`。
