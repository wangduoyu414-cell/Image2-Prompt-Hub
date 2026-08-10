---
task_contract_version: 3
card_id: "TASK-0001"
title: "审计候选案例仓库并冻结首版长期内容来源注册表"
status: "ready"
work_kind: "mixed"
execution_target: "agent-executable"
complexity: "standard"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "external-boundary"
  - "configuration"
  - "investigation"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- objective_id: OBJ-001
- readiness: ready
- authority_sources:
  - 用户最新确认：只管理高价值案例多、能够提取对应图片和 Prompt 的项目，并将其固定为长期内容来源。
  - D:/image2/1.md，重点是第 1、4、6、15、16、18 节及附录 A。
  - D:/image2/gpt-image-2-two-track-research-2026-08-01.md 与配套 XLSX，仅作为候选来源发现材料，不作为 active 状态或项目质量的最终证据。
  - 执行期间固定的上游仓库 Commit、仓库文件、LICENSE、案例数据、图片文件和可追溯原始链接，作为逐项目事实证据。
- decision_owner: 用户；执行者可以依据本卡的硬性准入规则设置 active、probation、paused 或 blocked，任何阈值变更、例外准入或风险接受仍由用户决定。
- material_unknowns:
  - 首版最终 active 来源数量和名单，属于本任务必须产出的调查结果。
  - 每个候选仓库当前是否可访问、默认分支、固定 Commit、真实案例数、图文配对率、失效图片和权利状态，属于本任务的调查对象。
  - 权利调查只能记录可观察声明和证据，不能替代法律意见。
  - 上述未知不阻止开始审计；若关键外部来源整体不可访问、候选集合无法还原或必须修改既定准入规则，任务必须停止并升级。

# 2. 业务目标

- actor: 项目所有者和后续内容平台实施者。
- workflow_and_trigger: 在实现采集平台、Adapter 和网页之前，以现有调研候选为入口，对每个候选仓库执行固定版本审计，并生成后续系统唯一可读取的首版来源注册表。
- single_outcome: 形成一套证据可追溯、机器可校验、状态规则一致的 sources-v1，明确哪些项目是长期 active 来源、哪些保留在 probation/paused/blocked，以及首批三个纵向验证来源。
- observable_results:
  - RESULT-001：现有 Markdown 和 XLSX 调研中出现的所有候选案例项目均被纳入审计清单，或被明确映射为镜像、重复、非案例项目或不可访问项目，不得静默遗漏。
  - RESULT-002：每个唯一候选仓库均记录稳定身份、固定 Commit、实际案例指标、图文配对证据、维护证据、来源家族和权利证据状态。
  - RESULT-003：sources-v1.yaml 通过结构与语义校验，active 来源均能追溯到审计记录且满足既定硬门槛。
  - RESULT-004：注册表明确标记三个结构不同、处于 active 且适合下一阶段纵向验证的 pilot 来源。
- non_goals:
  - 不实现 Git 镜像服务、持续同步调度器、生产数据库、对象存储、Adapter 或网页。
  - 不生成或重新运行图片模型。
  - 不把旧评分、Star 数或 README 更新时间直接转换为 active 状态。
  - 不对外部仓库、GitHub Issue、作者账号或其他外部系统执行写操作。
  - 不修改 D:/image2/1.md 和现有调研文件。
  - 不给出法律结论或承诺图片、Prompt 可商业使用。

# 3. 需求质疑与确认

- user_statement: 固定高价值案例多且能提取对应图片和提示词的项目作为长期内容来源，并按已确认设计严谨继续。
- REQ-001 required_behavior: 从现有 Markdown 与 XLSX 调研材料建立案例来源候选全集，并按稳定仓库身份和来源家族去重；纯工具、纯工作流或没有足量 Prompt＋图片案例的项目只记录为 out_of_scope，不进入完整来源审计。
- REQ-002 required_behavior: 对每个唯一候选项目固定审计 Commit，保存默认分支、Repository ID 或等效稳定身份、仓库 URL、审计时间和证据路径。
- REQ-003 required_behavior: 对每个候选项目记录 observed_case_count、exact_prompt_count、paired_output_count、valid_case_count、unique_valid_case_count、pair_rate、broken_asset_count、duplicate_estimate、model_scope、质量抽检结果、维护证据、权利证据和 Adapter 策略。
- REQ-004 required_behavior: 按 1.md 中的首版准入规则和本卡规则分配 candidate、probation、active、paused、retired 或 blocked，不允许为追求来源数量降低证据门槛。
- REQ-005 required_behavior: 为审计 JSON 和来源注册表分别生成 JSON Schema，生成 sources-v1.yaml 和无副作用验证器，验证结构、唯一性、状态规则、来源家族、跨文件一致性和发布默认值。
- REQ-006 required_behavior: 从 active 来源中选择三个结构不同的 pilot 来源；若不足三个满足条件，必须报告缺口，不得用非 active 来源补足。
- REQ-007 required_behavior: 所有结论必须区分事实、来源声明、计算结果、人工判断和未确认项。
- INV-001: 旧调研评分只能用于候选发现，不能作为 active 的充分证据。
- INV-002: 每个 active 来源必须有固定 Commit、完整审计记录、明确 Adapter 策略和达到注册表配置阈值的 pair_rate。
- INV-003: mirror、backup 和无独立内容的 translation 不得作为独立 active 内容源；其 ingestion_policy 默认只能是 provenance_only。
- INV-004: 权利为 unknown、review_required、internal_only 或 blocked 的资产不得配置自动公开镜像。
- INV-005: 不得猜测案例数量、模型、参数、作者、许可证、原始链接、维护状态或图文对应关系。
- INV-006: 同一审计 Commit 和同一审计规则重复计算，应得到相同的项目身份、计数和状态输入。
- material_ambiguities:
  - Markdown 与 XLSX 的候选集合或字段可能不一致。执行时取两者并集，以稳定仓库身份去重，并在审计报告记录冲突。
  - “高价值”包含一定人工判断。执行者只能依据明确的内容密度、完整度、多样性和可提取性规则记录判断；边界项目保持 probation，不得自行批准例外。
  - 仓库级许可证不必然覆盖第三方图片和 Prompt。任务只记录证据层级和展示策略建议。
- decisions_and_authority:
  - 1.md 中“常规来源建议至少 50 个有效案例、垂直独特来源可降至 20 个、自动图文配对率原则上不低于 90%”作为 v1 准入基线。
  - 清楚满足全部硬门槛的项目可以进入 active；证据不足、边界判断或需例外的项目保持 probation。
  - 镜像和备份保留血缘但不重复产生前台内容。
  - 任何阈值、公开权利规则或例外准入的改变均超出本任务授权。
- CHG-001: 用户授权为 TEST-003/TEST-004 补充稳定的正式 validators manifest；该变更不改变目标、准入规则、业务写入范围、风险接受或验收含义。
- CHG-002: 用户确认修正正式执行环境合同：D:/image2/.work/source-audit 中的审计脚本和质量样本作为本地复现证据保留，不再要求删除；仓库内既有 D:/image2/.task-runs 只作为历史证据且后续只读；新的 canonical run sidecar、receipt、独立审查和 Completion Report 必须写入 C:/Users/admin/.codex/task-state/image2/TASK-0001。该变更只解除宿主清理限制和仓库快照自修改冲突，不降低任何业务 Gate、来源门槛、权利规则或验证要求。

# 4. 业务场景与规则

- SCN-001 主路径: 候选仓库公开可访问，默认分支和固定 Commit 可确认，完整 Prompt 与输出图片可按确定结构提取。审计记录全部指标并依据硬门槛给出 active 或 probation 状态。
- SCN-002 镜像与聚合边界: 候选仓库属于镜像、备份、翻译或聚合项目。审计必须建立 source_family；聚合项目只有能逐条保留作者、原始链接和图文对应关系时才可继续评估为内容源。
- SCN-003 外部失败路径: 仓库不可访问、需要凭据、图片批量失效、Git LFS 对象缺失、结构无法完整解析或案例关系存在歧义。项目不得进入 active，并必须记录失败事实、影响范围和下一步条件。
- SCN-004 输入冲突路径: Markdown、XLSX 和上游仓库对项目名称、数量、来源或镜像关系的描述冲突。上游固定 Commit 的可观察内容优先用于事实字段；无法解决的冲突保留在报告中并阻止对应项目进入 active。
- SCN-005 重复执行路径: 对同一 Commit 和相同审计规则重新运行，输出顺序、计数、标识和状态输入保持确定；审计时间等动态字段不得影响实体身份或业务结论。
- RULE-001: observed_case_count 是在固定 Commit 中按项目自身结构识别到的案例单元数量。
- RULE-002: exact_prompt_count 是包含可复制完整 Prompt 原文的案例数量。
- RULE-003: paired_output_count 是至少有一张输出图与 Prompt 达到 strong 配对证据的案例数量。
- RULE-004: valid_case_count 是同时具有完整 Prompt 和 strong 输出图配对的案例数量。
- RULE-005: unique_valid_case_count 是 valid 案例按规范化 Prompt 精确哈希与输出图片 SHA-256 去除项目内完全重复后保留的数量；近似变体不自动删除。
- RULE-006: pair_rate 等于 valid_case_count 除以 observed_case_count；observed_case_count 为零时 pair_rate 为 0。
- RULE-007: last_substantive_content_update 必须由实际案例、Prompt、图片或结构数据变化证明，时间戳和自动 README 刷新不算实质更新。
- RULE-008: active 来源必须以 unique_valid_case_count 满足自身注册的 minimum_valid_cases，并满足 minimum_pair_rate、可访问性、确定性 Adapter 策略和非镜像约束；权利不清时仍必须 auto_publish=false。
- RULE-009: pilot 来源必须来自 active，并覆盖三种不同结构，优先为结构化数据、Markdown 图文结构和大型或复杂图库结构。
- RULE-010: observed_case_count、exact_prompt_count、paired_output_count、valid_case_count、unique_valid_case_count、pair_rate 和 broken_asset_count 必须基于固定 Commit 的完整当前案例集合计算；抽样不得用于外推这些全量指标。
- RULE-011: 内容价值采用分层抽检记录，样本量取 unique_valid_case_count、50 与 max(20, 向上取整(unique_valid_case_count × 10%)) 三者中的最小值；样本应覆盖主要分类或目录。每个样本检查 Prompt 是否完整且有实质信息、图片是否清楚体现 Prompt、案例是否具有参考或复用价值、是否为占位或明显重复内容。质量边界不清的项目保持 probation。
- RULE-012: 候选提取以案例内容为准而非项目名称；纯工具、纯执行层、纯工作流和没有可提取图文案例的项目必须在候选映射中标记 out_of_scope 及证据，不进入案例数量、质量和 active 判定。
- risk_sensitive_invariants:
  - sources-v1 将成为后续 Source Manager、Adapter 接入和发布策略的共享权威配置，任何无证据 active 条目都可能向下游传播错误内容和权利状态。
  - stable source_id 和 repository_id 必须唯一，仓库改名不能创建新的独立来源身份。
  - 所有 active 状态和 pilot 选择必须能够反向追溯到审计记录、固定 Commit 和计算字段。
  - source claim、审计判断和法律结论必须保持区分。
- inapplicable_faces_with_reason:
  - 权限写入：本任务不修改外部系统、不发布内容、不接受权利风险。
  - 生产并发：本任务不实现后台任务系统；并行审计只允许在最终输出合并规则确定且结果可重复时使用。
  - 生产回滚：本任务只创建本地审计和配置产物；错误结果通过重新审计和替换未执行的 v1 配置恢复。

# 5. 当前证据与目标差异

- FACT-001: D:/image2 当前不是 Git 仓库；已确认存在 1.md、gpt-image-2-two-track-research-2026-08-01.md 和配套 XLSX。
- FACT-002: 1.md 已明确来源准入、Source Registry、Generation Example、实施路线、验收标准和候选审计字段。
- FACT-003: Markdown 调研包含案例项目榜单、镜像纠偏、核心候选和持续拓展规则，并声明完整项目明细位于 XLSX。
- FACT-004: 当前工作区尚不存在 sources-v1.yaml、来源注册表 Schema、正式逐仓审计报告或注册表验证器。
- FACT-005: 当前主机默认 python 为 3.8.6，无法导入使用现代内置泛型注解的验证器；Windows Python Launcher 已验证可选择 Python 3.12，且使用 py -3.12 运行完整 Validator、自检与确定性检查可以正常执行。
- ASM-001: 执行时可以通过互联网和 Git/GitHub 读取公开候选仓库；单个来源失败可按 SCN-003 降级，关键来源整体无法访问则必须停止。
- ASM-002: XLSX 是候选发现和历史判断的补充输入，其任何评分或状态必须由当前固定 Commit 证据重新验证。
- current_execution_path: 历史调研文件人工列出候选和评分，但没有统一、机器可读、固定 Commit 证据支撑的正式来源注册表，因此后续平台无法确定权威来源集合。
- target_delta: 建立候选全集，逐项目采集固定版本证据和指标，形成审计报告与结构化审计数据，再生成并校验 sources-v1。
- evidence_gaps:
  - 候选项目全集尚未从 Markdown 与 XLSX 统一提取和去重。
  - 各仓库当前状态、固定 Commit、真实案例指标和权利证据尚未完成本轮复核。
  - 最终 active、probation、blocked 和 pilot 名单尚未产生。
  - 注册表 Schema 与语义验证器尚不存在。

# 6. 范围与责任边界

- allowed_write_scope:
  - D:/image2/reports/source-audit-v1.md
  - D:/image2/reports/source-audit-v1.json
  - D:/image2/config/sources-v1.yaml
  - D:/image2/schemas/source-audit-v1.schema.json
  - D:/image2/schemas/source-registry-v1.schema.json
  - D:/image2/scripts/validate_source_registry.py
  - D:/image2/.work/source-audit/** 用于保留审计复现脚本、质量抽检样本和已披露的宿主受限缓存；不得新增凭据、仓库克隆或与本任务无关的缓存
  - C:/Users/admin/.codex/task-state/image2/TASK-0001/** 作为新的 canonical run sidecar、receipt、独立审查和 Completion Report 根目录
- hard_protected_scope:
  - 不修改 D:/image2/1.md。
  - 不修改现有 Markdown 和 XLSX 调研文件。
  - 既有 D:/image2/.task-runs/** 是历史执行证据；新的正式闭环不得继续写入或更新该目录。
  - 不修改任何外部仓库，不创建 Issue、PR、评论、镜像仓库或其他外部写入。
  - 不实现生产采集平台、Adapter、数据库、对象存储、网页或定时同步。
- protected_contracts_and_invariants:
  - 保持 1.md 的来源准入、内部库存与公开分离、镜像不重复、未知权利不自动公开等边界。
  - active 状态必须以固定 Commit 的当前证据为基础。
  - 审计失败或未知必须显式记录，不得通过默认值伪装为通过。
  - 现有研究评分不覆盖本任务的实际审计结果。
- authorization_limits: 本任务卡只授权创建本地审计、配置、Schema、验证器和执行证据，并授权将正式执行证据写入 C:/Users/admin/.codex/task-state/image2/TASK-0001；该路径是本机执行 sidecar，不是外部系统写入。本卡不构成实施平台、公开发布内容、接受法律风险或执行外部网络写操作的授权。
- stop_if_scope_expands:
  - 需要修改 v1 准入阈值、权利策略或 1.md 的设计决定。
  - 需要凭据、登录态、付费访问或执行不可信仓库代码才能完成关键来源审计。
  - 关键候选集合无法从现有材料还原。
  - 大量候选仓库因网络或服务状态不可访问，导致无法形成有代表性的 v1。
  - 需要对权利作出法律结论或批准例外 active 来源。

# 7. 实现蓝图

- blueprint_status: confirmed
- caller_entry_consumer:
  - caller: 项目所有者通过本任务启动来源冻结。
  - entry: 1.md 的来源准入规则，以及 Markdown/XLSX 的候选来源材料。
  - execution_path: 候选提取与身份归一化 → 固定仓库 Commit → 全量案例指标与证据采集 → 来源家族和权利分类 → 状态判定 → 注册表生成 → Schema 与语义校验。
  - final_consumer: 下一阶段的 Generation Example/Adapter 契约任务、三来源纵向验证任务和后续 Source Manager；这些消费者只读取 sources-v1，不直接把旧调研评分当作权威配置。
- expected_touchpoints_or_search_anchors:
  - 已验证输入：D:/image2/1.md。
  - 已验证输入：D:/image2/gpt-image-2-two-track-research-2026-08-01.md。
  - 已验证输入：D:/image2/gpt-image-2-two-track-research-2026-08-01.xlsx。
  - 目标产物路径见第 6 节 allowed_write_scope。
- wiring_to_final_consumer:
  - source-audit-v1.json 是机器可核对的事实、全量计数和质量抽检结果。
  - source-audit-v1.md 是面向用户的结论、冲突和风险说明。
  - sources-v1.yaml 只引用已审计 source_id、固定 Commit、状态、阈值、family、Adapter 策略和发布默认值。
  - source-audit-v1.schema.json、source-registry-v1.schema.json 与 validate_source_registry.py 共同阻止缺字段、重复身份、错误状态组合和审计/注册表不一致。
  - pilot 标记由下一阶段任务消费，但本任务不实现对应 Adapter。
  - 正式 run sidecar 与 Completion Report 写入 C:/Users/admin/.codex/task-state/image2/TASK-0001，使执行证据不参与 D:/image2 的最终工作区快照。
- failure_and_recovery:
  - 单个仓库不可访问：记录错误、最后可确认状态和影响；不得进入 active。
  - 仓库内容无法全量确定解析：记录 observed 指标和 evidence gap，保持 probation。
  - 镜像关系冲突：保留所有候选记录，等待以 repository_id、Git 血缘和内容证据解决；未解决前不得重复 active。
  - 权利不清：使用 unknown/review_required/internal_only，强制 auto_publish=false。
  - Validator 失败：修复产物或保持任务未完成，不允许以人工描述替代机器校验。
  - 正式 sidecar 或 Completion Report 写入仓库根目录：停止该运行并使用任务卡声明的外部 canonical evidence root 重新建立合法运行，避免执行证据改变被验证工作区。
- implementation_freedom: 在不执行不可信代码、不扩大写入范围并满足证据与确定性要求的前提下，执行者可选择 Git、GitHub API、文本解析、电子表格读取、哈希和统计工具。
- selected_profile_obligations:
  - external-boundary: 对网络、GitHub 和 Git 请求设置超时、有限重试与失败记录；所有事实固定到 Commit，不依赖易变网页状态作为唯一证据。
  - configuration: 定义字段来源、唯一性、状态枚举、默认值、阈值、family 约束和 fail-closed 校验；同一输入生成确定性注册表；canonical evidence root 位于工作区外，仓库内历史 sidecar 不参与新运行。
  - investigation: 明确候选全集、审计问题、方法、事实证据、假设、缺口、结论和对下一任务的交接。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- links: OBJ-001, REQ-001, REQ-002, REQ-003, REQ-004, REQ-007, INV-001, INV-003, INV-005, INV-006
- owns_behavior: 建立无静默遗漏的候选全集，对每个唯一项目执行固定 Commit 审计，计算全量统一指标，执行分层质量抽检，并记录来源家族、维护、模型范围、权利证据和状态建议。
- target_delta: 将分散在 Markdown/XLSX 中、缺少当前仓库证据的历史候选，转换为逐来源固定 Commit、统一指标、质量抽检和证据缺口完整记录的审计数据集。
- business_result: 任何后续执行者都可以仅凭审计产物回答每个候选项目是否被检查、检查了哪个版本、发现多少有效图文案例、为什么建议某个状态以及还缺什么证据。
- behavior_faces:
  - normal: 公开仓库可以完整读取、确定性提取并完成全量计数和质量抽检。
  - boundary: 垂直小型来源、混合模型来源、聚合来源、镜像或翻译来源。
  - failure: 仓库不可访问、图片失效、结构无法完整解析、权利或来源冲突。
  - empty: 仓库不存在有效案例或 observed_case_count 为零。
  - repeated: 同一 Commit 重跑得到相同身份、计数和状态输入。
  - downstream_error: 审计证据不足时必须阻止 TASK-002 将项目设为 active。
- state_change:
  - entry_condition: 只有历史候选材料，没有正式逐仓审计。
  - exit_condition: 每个候选都有唯一审计记录或明确 duplicate/mirror 映射。
  - failure_degradation: 无法完成的项目保留失败记录并保持非 active；关键候选整体不可审计时停止任务。
- data_flow:
  - input_source: 1.md、Markdown/XLSX 候选材料、上游仓库固定 Commit。
  - single_source_of_truth: source-audit-v1.json 中的逐来源事实和计算结果。
  - write_target: source-audit-v1.json 与 source-audit-v1.md。
  - downstream_consumers: TASK-002、后续来源接入和 Adapter 任务。
- integration_edges: 候选材料 → 统一仓库身份 → 固定 Commit 内容 → 审计数据；TASK-002 只能消费已通过字段完整性检查的记录。
- expected_touchpoints: D:/image2/reports/source-audit-v1.md；D:/image2/reports/source-audit-v1.json；D:/image2/.work/source-audit/**
- scope_boundary:
  - hard: 不修改输入文档，不执行仓库代码，不进行外部写入，不自行改变准入规则。
  - soft: 不为下一阶段实现 Adapter 或生产同步。
- allowed_write_scope: 仅第 6 节中 reports、.work 和外部 canonical evidence root 的相关路径。
- acceptance_scenarios:
  - 正常：候选全集与每个固定 Commit 审计记录一一对应，全量计数公式一致，质量抽检覆盖主要内容结构。
  - 边界：镜像、聚合、混合模型和垂直小型项目具有明确角色与状态理由。
  - 失败：不可访问或无法完整解析的项目有失败证据且不会进入 active。
  - 重复：同一输入重跑不改变稳定身份和业务计数。
- linked_tests: TEST-001, TEST-002
- stop_conditions:
  - 无法可靠提取 Markdown 与 XLSX 候选并集。
  - 关键外部仓库整体不可访问。
  - 需要修改准入阈值或接受例外风险。

### TASK-002

- links: OBJ-001, REQ-004, REQ-005, REQ-006, INV-002, INV-003, INV-004, INV-006
- owns_behavior: 将 TASK-001 的审计事实转换为唯一、版本化、机器可校验的 sources-v1，并从 active 中选择三个符合条件的 pilot 来源。
- target_delta: 将审计数据从调查结果转换为后续系统可直接消费的来源配置合同，并通过 Schema、语义规则和跨文件一致性检查阻止无证据或错误状态来源进入 active。
- business_result: 下游任务能够读取一个明确的来源集合和状态，不再从研究文档或自然语言评分推断应该接入哪些仓库。
- behavior_faces:
  - normal: 审计完整且项目满足 active 门槛。
  - boundary: 项目满足内容门槛但权利不清、属于聚合来源或仅适合 probation。
  - failure: 审计记录缺字段、重复 source_id/repository_id、active 不满足阈值、镜像被配置为完整内容源。
  - empty: 没有足够的 active 来源或不足三个不同结构的 active pilot。
  - repeated: 相同审计数据重复生成和验证得到相同稳定字段与状态。
  - downstream_error: 注册表或审计不一致时，下游不得开始 Adapter 和 Source Manager 实现。
- state_change:
  - entry_condition: 已有逐项目审计，但没有权威配置。
  - exit_condition: Schema、YAML、验证器和 pilot 选择一致且通过全部 gate。
  - failure_degradation: 校验失败则保留 draft 产物或修复，不发布 sources-v1 作为下游权威。
- data_flow:
  - input_source: source-audit-v1.json。
  - single_source_of_truth: 事实以审计 JSON 为准；运行配置以通过校验的 sources-v1.yaml 为准。
  - write_target: sources-v1.yaml、source-audit-v1.schema.json、source-registry-v1.schema.json、validate_source_registry.py。
  - downstream_consumers: 后续数据契约、纵向管线和来源接入任务。
- integration_edges: 审计 source_id、repository_id、Commit、指标和状态理由必须映射到注册表；Validator 同时检查 YAML Schema 和跨文件语义。
- expected_touchpoints: D:/image2/config/sources-v1.yaml；D:/image2/schemas/source-audit-v1.schema.json；D:/image2/schemas/source-registry-v1.schema.json；D:/image2/scripts/validate_source_registry.py
- scope_boundary:
  - hard: 不把 probation/blocked 项目伪装成 active，不修改 1.md，不实现运行时 Source Manager。
  - soft: 不优化未来配置热加载、调度和数据库同步。
- allowed_write_scope: 仅第 6 节中 config、schemas、scripts 和外部 canonical evidence root 的相关路径。
- acceptance_scenarios:
  - 正常：全部 active 条目通过硬门槛并能追溯到审计记录。
  - 边界：权利未知或聚合项目配置为 fail-closed，镜像仅 provenance_only。
  - 失败：任何重复身份、缺证据 active、错误状态组合或跨文件不一致使 Validator 非零退出。
  - 空集：不足三个不同结构的 active pilot 时明确报告并阻止 GATE-004，而不是降低门槛。
- linked_tests: TEST-003, TEST-004
- stop_conditions:
  - 审计 JSON 不完整或存在未解决的项目身份冲突。
  - 需要改变准入规则、公开默认值或批准例外来源。

### ASSEMBLY-001

- participating_tasks: TASK-001, TASK-002
- end_to_end_entry: 现有调研候选材料和 1.md 的准入规则。
- shared_contract_state_data: source_id、repository_id、family、verified_commit_sha、审计指标、rights 状态、recommended_status、final registry status 和 pilot_priority。
- final_consumer: 下一阶段 Generation Example/Adapter 契约任务与三来源纵向验证任务。
- cross_task_failure_path: TASK-001 的缺失、冲突或失败记录不得在 TASK-002 中被默认值掩盖；任何无审计证据的注册表条目、状态漂移或 pilot 补足行为都使组装失败。
- linked_test_evidence_gate: TEST-004 / EV-004 / GATE-004

# 9. 验证与验收

- consumer_chain_validation: TEST-004 必须验证候选材料 → source-audit-v1.json → sources-v1.yaml → pilot 选择的双向映射，任何缺失、无审计配置或状态漂移均阻止最终 Gate。
- real_integration_evidence: EV-004 必须包含跨文件零差异检查输出和 pilot 选择矩阵；只有分别通过 Schema 的文件不能替代这项真实组装证据。

### RISK-001

- links: OBJ-001, REQ-001, TEST-001
- description: Markdown 或 XLSX 中的候选被遗漏，导致所谓“完整审计”实际只覆盖部分历史调研。
- mitigation: 分别提取两个输入的候选集合，按稳定仓库身份做并集和双向差集验证。

### RISK-002

- links: REQ-003, RULE-001, RULE-011, TEST-002
- description: 不同项目结构采用不一致的案例、去重和 pair_rate 定义，导致状态不可比较。
- mitigation: 固定统一计数公式、全量计数规则和分层质量抽检规则，并保存每个来源的计算证据。

### RISK-003

- links: INV-003, SCN-002, TEST-002, TEST-003
- description: 镜像、Fork、翻译或聚合内容被误判为独立来源。
- mitigation: 使用稳定 repository_id、Git 血缘、内容哈希和原始链接建立 source_family，并由 Validator 阻止错误 active/full 组合。

### RISK-004

- links: INV-004, TEST-002, TEST-003
- description: 仓库级许可证被错误扩展为图片或 Prompt 的公开权利。
- mitigation: 分开记录 repository、Prompt 和 asset 证据；未知或待审权利强制 auto_publish=false。

### RISK-005

- links: REQ-002, SCN-005, TEST-002
- description: 审计过程中上游继续变化，导致报告、计数和证据不在同一版本。
- mitigation: 所有内容事实固定到 verified_commit_sha；易变仓库页面只作为辅助元数据，不作为案例计数依据。

### RISK-006

- links: REQ-005, ASSEMBLY-001, TEST-003, TEST-004
- description: 审计报告、审计 JSON 和 sources-v1 之间出现状态或字段漂移。
- mitigation: 两个 Schema、跨文件 Validator 和双向零差异检查共同 fail closed。

### TEST-001

- links: TASK-001, REQ-001, SCN-004, RISK-001, INV-001
- method: 分别提取 Markdown 与 XLSX 中的仓库候选，按 RULE-012 区分案例来源候选和 out_of_scope 项目，标准化仓库 URL 和稳定身份后做并集；将案例来源并集与 source-audit-v1.json 的审计记录及 duplicate/mirror 映射双向比较。
- expected_observable_result: 每个历史候选恰好对应一个唯一审计记录、明确的来源家族映射或有证据的 out_of_scope 记录；案例候选总数、唯一仓库数、镜像/重复数、out_of_scope 数和未审计数在报告中一致，未审计数为零。
- failure_path_covered: XLSX 读取失败、名称不同但仓库相同、历史项目已删除、同内容多仓库。
- cannot_prove: 不能证明现有调研之外不存在其他值得发现的新项目。

### EV-001

- for: TEST-001
- required_evidence_shape: 候选提取清单、标准化前后仓库标识、并集与去重映射、未覆盖差集为零的机器检查输出；实际输出保存到执行 sidecar。

### TEST-002

- links: TASK-001, REQ-002, REQ-003, REQ-004, REQ-007, SCN-001, SCN-002, SCN-003, SCN-005, RISK-002, RISK-003, RISK-004, RISK-005
- method: 对每个唯一候选固定 Commit，按 RULE-001 至 RULE-010 对完整当前案例集合计算指标，并按 RULE-011 执行分层质量抽检；记录仓库文件或数据路径、图文配对证据、图片可访问性、维护 diff、来源家族和权利声明；对同一 Commit 重算关键计数。
- expected_observable_result: 每条审计记录包含附录 A 所需字段、固定 Commit、全量计数、质量抽检和可追溯证据；计数公式一致；active 建议满足所有硬门槛且质量判断明确；失败或质量边界项目保持非 active；重复计算无业务差异。
- failure_path_covered: 仓库不可访问、结构无法完整解析、LFS 或外部图片缺失、Prompt 与图片关系歧义、权利证据不明。
- cannot_prove: 不能证明未来仓库会持续维护，也不能把仓库声明转化为法律结论或证明主观审美价值。

### EV-002

- for: TEST-002
- required_evidence_shape: 每个来源的 repository_id、URL、verified_commit_sha、审计时间、全量计数字段、计算公式、质量抽检样本标识与结果、证据文件路径或链接、维护证据、family 结论、rights 证据状态、status 理由及重算对比；实际命令和输出保存到执行 sidecar。

### TEST-003

- links: TASK-002, REQ-005, INV-002, INV-003, INV-004, INV-006, SCN-005, RISK-003, RISK-004, RISK-006
- method: 使用本任务创建的无副作用 Validator，分别校验 source-audit-v1.json 和 sources-v1.yaml 的 JSON Schema，再执行跨文件语义校验，并在相同输入上重复运行。
- expected_observable_result: Validator 零退出；source_id 和 repository_id 唯一；每个 active 条目存在完整审计记录并满足阈值；mirror/backup 不使用 full；未知权利强制 auto_publish=false；相同输入输出的稳定业务字段一致。
- failure_path_covered: 缺字段、重复身份、无审计 active、错误 family/ingestion_policy 组合、权利和发布默认值冲突、动态字段污染确定性。
- cannot_prove: 静态 Validator 不能证明远端仓库在验证后没有变化，也不能证明未来生产 Adapter 能成功解析。

### EV-003

- for: TEST-003
- required_evidence_shape: Validator 版本或文件哈希、审计 JSON、来源 YAML、两个 Schema 的输入路径、零退出输出、规则检查摘要和重复运行对比；实际结果保存到执行 sidecar。

### TEST-004

- links: ASSEMBLY-001, TASK-001, TASK-002, OBJ-001, REQ-006, RISK-006
- method: 双向比对 source-audit-v1.json 与 sources-v1.yaml 的 source_id、repository_id、Commit、状态、family、阈值、rights 默认值和证据引用；检查 pilot 来源只来自合格记录并覆盖三个不同结构。
- expected_observable_result: 注册表不存在无审计来源；审计中的每个最终状态均在注册表或明确排除表中得到一致表达；三个 pilot 均为 active、满足结构差异和准入条件，或明确报告不足并保持 GATE-004 不通过。
- failure_path_covered: 手工复制导致字段漂移、pilot 为凑数绕过门槛、审计状态与注册表状态不一致。
- cannot_prove: 不能证明 pilot 的未来 Adapter 实现一定成功，只能证明其当前证据适合作为下一阶段输入。

### EV-004

- for: TEST-004
- required_evidence_shape: 审计与注册表双向差异为零的检查输出、pilot 选择矩阵、每个 pilot 的结构类型与准入证据、任何不足或阻断说明；实际结果保存到执行 sidecar。

### 正式 Validator Manifest

以下声明是 TEST-003 和 TEST-004 的正式行为验证入口。预检只确认解释器兼容性，不产生通过结论。

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "source-audit-registry-contract",
      "command": [
        "py",
        "-3.12",
        "scripts/validate_source_registry.py",
        "--audit",
        "reports/source-audit-v1.json",
        "--registry",
        "config/sources-v1.yaml",
        "--audit-schema",
        "schemas/source-audit-v1.schema.json",
        "--registry-schema",
        "schemas/source-registry-v1.schema.json",
        "--self-test",
        "--determinism-check",
        "--json"
      ],
      "cwd": ".",
      "timeout_seconds": 120,
      "invalidation_paths": [
        "1.md",
        "gpt-image-2-two-track-research-2026-08-01.md",
        "gpt-image-2-two-track-research-2026-08-01.xlsx",
        "reports/source-audit-v1.md",
        "reports/source-audit-v1.json",
        "config/sources-v1.yaml",
        "schemas/source-audit-v1.schema.json",
        "schemas/source-registry-v1.schema.json",
        "scripts/validate_source_registry.py"
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
| GATE-001 | 候选全集覆盖 | OBJ-001 / TASK-001 / TEST-001 | Markdown 与 XLSX 候选并集全部被审计或明确映射，未覆盖差集为零 | EV-001 | 不证明调研之外没有新项目 |
| GATE-002 | 逐来源审计可信 | OBJ-001 / TASK-001 / TEST-002 | 所有唯一候选均有固定 Commit、统一指标、证据和可解释状态；失败与未知未被隐藏 | EV-002 | 不证明未来维护和法律权利 |
| GATE-003 | 注册表合同有效 | OBJ-001 / TASK-002 / TEST-003 | Schema 与语义 Validator 通过，active、family、rights 和确定性规则全部满足 | EV-003 | 不证明生产运行时行为 |
| GATE-004 | 来源冻结端到端闭环 | OBJ-001 / ASSEMBLY-001 / TASK-001 / TASK-002 / TEST-004 | 审计与注册表双向一致，三个不同结构的 active pilot 已确定；若不足三个则本 Gate 不得通过 | EV-004 | 不证明下一阶段 Adapter 已实现 |

# 10. 产物与完成回写

- required_deliverables:
  - D:/image2/reports/source-audit-v1.md
  - D:/image2/reports/source-audit-v1.json
  - D:/image2/config/sources-v1.yaml
  - D:/image2/schemas/source-audit-v1.schema.json
  - D:/image2/schemas/source-registry-v1.schema.json
  - D:/image2/scripts/validate_source_registry.py
- documentation_impact: updated；新增来源审计和注册表合同，不修改 1.md 与历史调研文件。
- repository_hygiene_requirement:
  - D:/image2/.work/source-audit 中现有五个审计辅助脚本和三个质量样本图作为复现证据保留；已披露的 Python bytecode cache 属于宿主限制残留，不作为验收证据，也不因无法删除而阻止完成。
  - 后续正式闭环不得在 D:/image2/.work/source-audit 中新增仓库克隆、下载、凭据或额外缓存；运行 Python 时应避免产生新的 bytecode cache。
  - D:/image2/.task-runs 作为历史证据保持只读；新 run 不得在其中生成或更新 sidecar。
  - 不把凭据、令牌、浏览器会话、未授权图片副本或工具缓存作为交付物。
  - 当前工作区不是 Git 仓库，因此不要求提交；最终必须明确列出新增文件和未修改的保护文件。
- external_review: policy=never；reason=本任务冻结本地调查和配置合同，不要求外部审阅。权利结论保持证据状态而非法律判断；任何例外准入仍由用户决定。
- non_completion_rules:
  - 任一历史候选被静默遗漏时不得完成。
  - 任一 active 来源缺少固定 Commit、完整审计记录、门槛证据或 Adapter 策略时不得完成。
  - 镜像或备份被配置为独立 full active 来源时不得完成。
  - 权利未知但 auto_publish 不为 false 时不得完成。
  - 两个 Schema、Validator、审计报告、审计 JSON 和 sources-v1 任一缺失时不得完成。
  - TEST-001 至 TEST-004 的实际验证证据未产生或 GATE-001 至 GATE-004 任一不通过时不得完成。
  - 需要改变设计阈值、接受例外风险或不足三个不同结构的 active pilot 时，必须报告实际状态，不得把任务标记完成。

执行 run ID、实际命令、实际输出、远端响应、文件哈希、验证结果、最终状态和任何跳过项写入 C:/Users/admin/.codex/task-state/image2/TASK-0001/ 下的执行 sidecar 或 Completion Report，不写回本任务卡，也不得写入仓库内 D:/image2/.task-runs。
