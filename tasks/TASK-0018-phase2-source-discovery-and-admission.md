---
task_contract_version: 3
card_id: "TASK-0018"
title: "建立Phase 2高价值案例来源候选池与Adapter准入批次"
status: "ready"
work_kind: "investigation"
execution_target: "agent-executable"
complexity: "standard"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "investigation"
  - "external-boundary"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户确认 Phase 2 应优先扩充长期内容来源；用户此前明确要求寻找持续维护、案例质量高、能够稳定提取对应图片和提示词的开源项目；`1.md` v1.1 第 18 节；Phase 1 closure；现有 source-audit-v1、sources-v1 与准入规则。
- `decision_owner`: 用户确认本阶段先做来源扩充与准入，不提前开发 Adapter、内部审核台或公共网页改版。
- `material_unknowns`: 新发现项目及其最终结论属于本调查的预期输出，不是就绪阻断；若外部网络或 GitHub 无法取得固定版本证据，按失败规则记录，不能用搜索摘要替代。

# 2. 业务目标

- `actor`: 项目维护者，以及下一阶段 Adapter 实现任务的执行者。
- `workflow_and_trigger`: 从 Phase 1 已冻结的 3 个 active 来源出发，复核现有 8 个 probation 候选，并通过当前 GitHub/网页检索扩大候选全集；对优先候选固定 Commit、完成案例图文配对和维护质量审计，形成可直接供下一张 Adapter 任务消费的准入批次。
- `single_outcome`: 产生一份可复核、可机器校验、没有把 Skill/工具仓库或镜像仓库误当案例源的 Phase 2 来源候选池，并至少确定 3 个满足高价值、持续维护和稳定图文提取要求的 `adapter_ready` canonical 来源；若客观证据不足 3 个，则不得虚构准入结果。
- `observable_results`:
  - `RESULT-001`: 现有 8 个 probation 来源全部重新取得当前仓库身份、默认分支、固定 Commit、维护证据与结构初判。
  - `RESULT-002`: 通过定义明确的多组查询发现并去重至少 20 个不在 source-audit-v1 中的新案例源候选；若公共结果客观不足，输出完整查询与差集证据并保持任务未完成或真实阻断。
  - `RESULT-003`: Skill、工具、API 封装、纯聚合列表、教程、镜像、翻译、备份和无独立案例语料的仓库被明确分类，不进入独立 Adapter 准入批次。
  - `RESULT-004`: 对排序最高的至少 8 个 canonical 候选完成固定 Commit 全量案例审计，而非只看 README、Stars、搜索摘要或抽样数量。
  - `RESULT-005`: 每个全量审计候选记录可提取 Prompt 数、配对输出数、有效案例数、唯一有效案例数、配对率、失效资产率、重复率、图片位置稳定性、维护活跃度、许可证/权利证据、结构类型和 Adapter 复杂度。
  - `RESULT-006`: 至少 3 个候选满足 `adapter_ready` 门槛并按价值/实现成本排序；准入只表示可进入内部 Adapter 开发，不表示 active、已抓取、已获公开权利或可自动发布。
  - `RESULT-007`: 机器 JSON、Schema、Validator、单元测试、中文审计报告与 Phase 2 handoff 文档相互一致，并明确下一张 TASK-0019 的输入范围。
- `non_goals`: 不开发或修改任何 Adapter；不更新 `config/sources-v1.yaml` 或 Phase 1 audit；不导入内部库存；不建立权利审核 UI；不批准公开权利；不修改 API/Web；不部署或启用 scheduler。

# 3. 需求质疑与确认

- `user_statement`: 长期内容来源应稳定固定为高价值案例多、能够提取对应图片和提示词、持续维护更新的项目；当前应先扩充来源，再进入 Adapter 和产品页面。
- `REQ-001` (`required_behavior`): Phase 2 调查必须复核 8 个现有 probation 来源，并发现不少于 20 个新的唯一候选，不能只重复 Phase 1 的旧清单。
- `REQ-002` (`required_behavior`): 发现过程必须保存查询族、检索时间、候选 URL、仓库身份、排除原因和新旧差集，保证候选全集可复核。
- `REQ-003` (`required_behavior`): 每个进入全量审计的来源必须固定完整 lowercase Commit SHA；所有 Prompt、图片、计数和维护结论绑定该 Commit 或可验证的 Commit 历史。
- `REQ-004` (`required_behavior`): 全量案例审计必须覆盖来源内全部可识别案例，输出精确覆盖账；不能把展示图片数、README 条目数或 manifest 声明数直接当有效案例数。
- `REQ-005` (`required_behavior`): Prompt 与图片必须有确定性配对证据；只存在提示词、只存在图片、依赖动态网页、未固定外部 CDN、弱顺序推断或人工猜测的记录不得计入 strong valid case。
- `REQ-006` (`required_behavior`): `adapter_ready` 候选必须同时满足：canonical family role、至少 50 个唯一有效案例、strong pair rate 不低于 0.90、失效资产率不高于 0.05、来源内/家族重复率不高于 0.20、图片可在固定版本下稳定读取。
- `REQ-007` (`required_behavior`): 持续维护门槛为非 archived，最近一次实质案例内容更新距调查日不超过 180 天，且过去 365 天至少有 2 个不同日期的实质案例内容更新；仅 README、徽章、依赖或工作流更新不计入。
- `REQ-008` (`required_behavior`): 质量复核样本使用 `min(unique_valid, 50, max(20, ceil(unique_valid*0.10)))`，均匀覆盖目录/类别；必须检查 Prompt 完整性、图片可辨识性、语义对应、案例多样性与明显低质/水印/重复问题。
- `REQ-009` (`required_behavior`): 权利字段只记录可验证许可证、Prompt/资产证据和 `review_required/internal_only/blocked` 等证据状态；不得把仓库可访问、许可证存在或质量通过解释为人工公开批准。
- `REQ-010` (`required_behavior`): `adapter_ready` 只形成 TASK-0019 候选批次，现有 Phase 1 的 3 active 来源、312 internal、0 real public 和 fail-closed 边界保持不变。
- `INV-001`: source family 必须去重；镜像、备份、翻译和衍生仓库不得作为独立案例数或独立 Adapter 价值重复计算。
- `INV-002`: 搜索流行度、Stars、Forks、README 自述和模型标签只能用于候选排序，不能替代固定 Commit 和全量案例证据。
- `INV-003`: 调查产生的图片副本、仓库 clone、缓存和临时索引只能存在于工作区外运行目录，不得成为仓库交付物。
- `INV-004`: 未取得权利证据的来源仍可因内部研究价值进入 `adapter_ready`，但必须 `public_eligibility=review_required`、`auto_publish=false`，不得公开发布。
- `INV-005`: Phase 1 的 `source-audit-v1.*`、`sources-v1.yaml`、Schema、正式报告和历史 run 保持只读；Phase 2 产物使用独立命名空间。
- `material_ambiguities`: none；数量、门槛和状态语义已在本卡冻结。具体候选与最终排名由外部证据决定。
- `DEC-001`: 用户确认 Phase 2 先来源扩充与准入，后续才开发 Adapter、内部审核台和公共站。
- `decisions_and_authority`: `DEC-001` 来自用户对“先写并执行 TASK-0018 来源扩充与准入”的明确同意；准入数量与门槛是对用户“案例多、图文可提取、持续维护、质量高”要求的可验证合同化表达。

# 4. 业务场景与规则

- `SCN-001` 主路径: 旧 probation 全部复核，新候选满足数量覆盖，至少 8 个完成全量审计，至少 3 个得到可复核的 `adapter_ready` 结论。
- `SCN-002` 镜像/聚合边界: 搜索发现大量镜像、聚合或 Skill 项目，系统保留映射但不把其重复案例计入候选价值或准入批次。
- `SCN-003` 外部失败: 仓库消失、限流、网络中断、默认分支漂移、Git/资产不可读时，保留已确认事实和错误分类，不能用缓存摘要补成通过结论。
- `SCN-004` 高案例但不持续维护: 图文案例数量和质量达标，但维护门槛不达标，结论保持 probation，不得写为 `adapter_ready`。
- `SCN-005` 高质量但权利未知: 可进入内部 Adapter 候选，但 public eligibility 必须 fail closed，不改变真实 public count。
- `RULE-001`: 候选状态枚举为 `adapter_ready | probation | blocked | excluded`；只有全量审计、准入门槛和质量样本均闭合的 canonical 来源可为 `adapter_ready`。
- `RULE-002`: 新候选发现与全量案例审计是两个不同证据层；初筛通过不等于准入。
- `RULE-003`: `adapter_ready` 排序首先按唯一有效案例价值和质量，其次按维护稳定性、结构确定性与 Adapter 成本；Stars 只作为次要元数据。
- `FLOW-001`: Phase 1 候选/当前 Web 搜索 → 候选去重与 family 分类 → 固定 Commit 初筛 → 优先候选全量审计 → 质量样本 → `adapter_ready` 排序与 TASK-0019 handoff。
- `STATE-001`: discovered → triaged → full_audited → adapter_ready/probation/blocked/excluded；失败不得跳过中间证据层。
- `risk_sensitive_invariants`: `INV-001`至`INV-005`、固定 Commit、全量覆盖账、维护门槛、rights fail-closed、候选状态不冒充 active/public。
- `inapplicable_faces_with_reason`: 本任务无数据库、公开发布、用户权限变更和生产运行时写入；重复调用要求为相同固定证据产生相同 JSON 排序与分类。

# 5. 当前证据与目标差异

- `FACT-001`: `reports/source-audit-v1.json` 和 `config/sources-v1.yaml` 当前包含 3 个 active、8 个 probation 与 12 个 blocked case-source 候选，另有 out-of-scope exclusions。
- `FACT-002`: 8 个 probation 来源只有固定仓库身份和结构初判，`metrics_complete=false`，没有完整案例数、配对率、失效率、重复率或质量样本结论。
- `FACT-003`: Phase 1 已实现 3 个 active 来源的固定 Commit、Adapter、内部库存与同步闭环，共 312 internal Generation Examples；当前真实人工 rights approval 和 real public count 均为 0。
- `FACT-004`: `scripts/validate_source_registry.py` 和 `ingestion/registry.py` 仍是 Phase 1 三 pilot/已实现 Adapter 边界，不能直接把未实现 Adapter 的新来源写为 active。
- `ASM-001`: GitHub 仍是主要开源项目发现面；执行时必须用实际当前搜索和仓库证据验证，不能把该假设写成结果。
- `current_execution_path`: 维护者只能看到 2026-08-02 的 Phase 1 候选审计，无法判断哪些新项目或 probation 项目值得优先开发 Adapter。
- `target_delta`: 新增独立的 Phase 2 发现/准入机器报告、Schema、Validator、测试和 handoff 文档，不修改 Phase 1 registry 或 production。
- `evidence_gaps`: 当前候选发现覆盖、新项目差集、8 个 probation 的完整指标、维护证据、全量图文配对、质量复核、至少 3 个 Adapter 准入结论。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `reports/phase2/source-discovery-v1.md`
  - `reports/phase2/source-discovery-v1.json`
  - `schemas/phase2-source-discovery-v1.schema.json`
  - `scripts/validate_phase2_source_discovery.py`
  - `tests/phase2/test_source_discovery.py`
  - `docs/phase2/source-expansion-admission-v1.md`
  - 本卡对应的正式执行证据目录。
- `hard_protected_scope`: `1.md`、`config/sources-v1.yaml`、`reports/source-audit-v1.*`、现有 schemas/scripts/tests/docs、ingestion/inventory/content/sync/apps/migrations/fixtures、所有历史 tasks/formal states/reports/mirrors。
- `protected_contracts_and_invariants`: Phase 1 三来源合同、312 internal/0 public、registry active 语义、Adapter Output/Generation Example、rights/publication fail-closed、fixed Commit 和工作区外运行时规则。
- `authorization_limits`: 不授权新增 Adapter、真实 rights approval、公开发布、部署、外部账户写入、创建 GitHub issue/PR 或向候选仓库发送消息。
- `stop_if_scope_expands`: 需要修改第 7 个仓库文件、Phase 1 registry/schema/validator、生产代码或公开权利状态时停止并报告。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: 项目维护者启动调查；TASK-0019 执行者消费 `source-discovery-v1.json` 中有证据的 `adapter_ready` 排序批次。
- `current_execution_path`: source-audit-v1/sources-v1 提供旧候选与 family 基线；当前没有 Phase 2 discovery/admission consumer artifact。
- `target_delta`: 新增工作区外的可重复外部调查流程和工作区内 6 个只读研究交付物；不把调查结果连接到生产 ingestion。
- `expected_touchpoints_or_search_anchors`: `gpt-image-2-two-track-research-2026-08-01.*`、`reports/source-audit-v1.*`、`config/sources-v1.yaml`、source audit schemas/validator、GitHub repository/search/commit/tree/raw asset surfaces。
- `wiring_to_final_consumer`: discovery JSON 的 `adapter_ready_batch` 必须引用每个候选的固定 Commit、完整指标、family/rights/maintenance/quality evidence；Phase 2 handoff 文档把该批次作为 TASK-0019 唯一候选输入，不直接改 registry。
- `failure_and_recovery`: 所有 clone、下载和图像检查位于工作区外；请求有超时和有限重试；限流/不可用记录为 terminal evidence；重跑复用固定 Commit 时结果确定，HEAD 漂移只触发新调查证据，不改旧结论。
- `implementation_freedom`: 查询词、并发度、临时索引和内部解析器可调整，但候选数量、固定 Commit、全量审计、维护/质量/配对门槛、六文件范围和状态语义不可弱化。
- `selected_profile_obligations`:
  - `investigation`: 核心问题为“哪些当前开源仓库能作为高价值、持续维护、稳定提取图片+提示词的长期来源”；证据范围为 Phase 1 候选、当前 GitHub/网页搜索、固定 Commit tree/history/assets；竞争假设包括高 Stars 但无案例、案例多但镜像重复、图文多但不可稳定配对、质量高但停止维护；复现方法为 machine discovery/full audit 加质量样本；durable handoff 为六项交付物和 `adapter_ready_batch`。
  - `external-boundary`: GitHub/网页/Git/raw asset 访问必须设超时、有限重试、错误分类和无凭据输出；部分失败不得污染已完成候选；临时 clone/图片/cache 必须清理或只保留在正式外部 evidence root；不向外部系统写入。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`, `REQ-002`, `REQ-003`, `INV-001`, `INV-002`
- `owns_behavior`: 当前候选全集发现、旧 probation 复核、family 去重和初筛排序。
- `business_result`: 维护者获得一份当前、完整、可复核的新旧候选池，而不是依赖旧调研或搜索热度。
- `target_delta`: 2026-08-02 候选基线 → 至少 8 个旧 probation + 20 个新唯一候选的当前证据与分类。
- `behavior_faces`: normal=达到覆盖；boundary=镜像/聚合/Skill/工具；failure=网络/限流/仓库消失；empty=查询无新结果时保存查询证据并阻断数量 Gate；repeated=固定检索记录和排序确定；downstream=仅 full audit shortlist 可进入 TASK-002。
- `state_change`: candidate 未知 → discovered/triaged/excluded/blocked；失败候选保留原因，不伪造指标。
- `data_flow`: Phase 1 清单 + 当前搜索结果 + repository identity/history → discovery records → TASK-002 shortlist。
- `integration_edges`: GitHub/网页检索、Git repository identity、Phase 1 family baseline、machine JSON。
- `expected_touchpoints`: 本卡六项交付物中的 discovery JSON/Markdown、Schema/Validator/tests。
- `scope_boundary`: hard=不修改 Phase 1 registry、不下载进 workspace；soft=不做 Adapter 实现。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001` discovery 部分、`SCN-002`、`SCN-003`。
- `linked_tests`: `TEST-001`, `TEST-002`
- `stop_conditions`: 无法取得当前搜索/仓库固定身份，或需要外部写权限。

### TASK-002

- `links`: `OBJ-001`, `REQ-003`至`REQ-010`, `INV-001`至`INV-005`
- `owns_behavior`: 优先候选的固定 Commit 全量案例审计、质量/维护/权利分类和 Adapter 准入排序。
- `business_result`: 下一张 Adapter 实现卡获得至少 3 个真正值得接入、能够稳定解析图文且仍在维护的来源。
- `target_delta`: 初筛 shortlist → 至少 8 个 full_audited records + 至少 3 个 `adapter_ready` records 或真实不足阻断。
- `behavior_faces`: normal=门槛通过；boundary=50 cases/0.90 pair/0.05 broken/0.20 duplicate/maintenance；failure=资产不可读或结构不确定；permission=rights 只记录、不批准；empty=0 valid cases；repeated=相同 Commit 结果确定；downstream=TASK-0019 只消费 adapter_ready。
- `state_change`: triaged → full_audited → adapter_ready/probation/blocked；失败不改变 Phase 1 状态。
- `data_flow`: fixed Commit tree/history/assets → case coverage + quality sample + maintenance/rights evidence → ranked adapter_ready_batch。
- `integration_edges`: repository snapshots、prompt/image pairing、family dedupe、quality review、Phase 2 handoff 文档。
- `expected_touchpoints`: 本卡六项交付物。
- `scope_boundary`: hard=不实现 Adapter/registry/publication；soft=不设计内部审核 UI。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001` audit 部分、`SCN-003`至`SCN-005`。
- `linked_tests`: `TEST-003`, `TEST-004`
- `stop_conditions`: 需要弱化任一准入门槛、需要人工 rights 批准、或不足 3 个 adapter_ready。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`
- `end_to_end_entry`: Phase 1 候选基线和当前外部搜索。
- `shared_contract_state_data`: `REQ-001`至`REQ-010`、`INV-001`至`INV-005`、`FLOW-001`、`STATE-001`；discovery record 是 full audit 的唯一上游，full audit record 是 adapter_ready batch 的唯一上游。
- `final_consumer`: TASK-0019 Adapter 实现任务。
- `cross_task_failure_path`: discovery 数量、family 去重或固定身份不闭合时不得进入 full audit；full audit 不足 3 个通过时不生成虚假实现批次；已完成的来源记录保持可复核，失败候选保留错误状态。
- `linked_test_evidence_gate`: `TEST-005` / `EV-005` / `GATE-005`

# 9. 验证与验收

### RISK-001
- `description`: 搜索热度或 README 自述冒充真实案例质量，导致开发错误来源。

### RISK-002
- `description`: 镜像/聚合重复计算，造成案例数量虚高。

### RISK-003
- `description`: 只抽样不做全量覆盖，隐藏配对失败、失效资产和重复案例。

### RISK-004
- `description`: “可内部接入”被误写为“可公开发布”。

### RISK-005
- `description`: 维护证据只统计非内容 Commit，违背持续更新目标。
- `consumer_chain_validation`: JSON `adapter_ready_batch` → handoff doc → TASK-0019 输入必须一一对应；任何无 full audit record 的来源不得出现在批次。
- `real_integration_evidence`: 当前 GitHub/网页查询、固定 Commit Git tree/history、全部候选 case coverage、资产读取/哈希、质量样本和 deterministic rerun。

### TEST-001

- `links`: `TASK-001`, `REQ-001`, `REQ-002`, `RISK-001`, `RISK-002`
- `method`: machine validator 检查 8 个既有 probation 全覆盖、新候选差集不少于 20、查询族/时间/来源证据完整、candidate_key/repository_id/family 去重。
- `expected_observable_result`: 无旧 probation 遗漏，无新候选重复或 silent omission，排除分类可解释。
- `failure_path_covered`: 空查询、镜像、聚合、Skill/工具混入、repository identity 冲突。
- `cannot_prove`: 案例全量质量和 Adapter 可行性。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: 查询记录、候选新旧差集、repository identity/Commit 列表、family 映射和 machine summary。

### TEST-002

- `links`: `TASK-001`, `REQ-003`, `INV-002`, `RISK-001`
- `method`: live validator 对 triaged 候选重查仓库可访问性、Commit SHA、默认分支和 archive 状态，并验证失败分类不被当作通过。
- `expected_observable_result`: 所有进入 shortlist 的仓库都能由当前公开边界解析到固定 Commit；外部失败有 bounded error。
- `failure_path_covered`: timeout、rate limit、404、branch/HEAD 漂移、非 GitHub/非 repository URL。
- `cannot_prove`: 固定 Commit 内案例合同。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: 每个候选的请求方法、时间、终端状态、repository id/default branch/fixed SHA 和错误分类。

### TEST-003

- `links`: `TASK-002`, `REQ-003`至`REQ-008`, `RISK-002`, `RISK-003`, `RISK-005`
- `method`: 对至少 8 个 full_audited 来源验证全量 coverage accounting、Prompt/output strong pairing、unique/broken/duplicate 指标、Commit 历史维护判定和 Rule-008 质量样本。
- `expected_observable_result`: 每个计数可由 case records 重算，分母分子明确，maintenance 只计实质案例内容更新，sample IDs/结论完整。
- `failure_path_covered`: manifest 声明与实际树不符、弱配对、外部资产漂移、重复家族、非内容更新冒充维护。
- `cannot_prove`: 法律授权和未来维护行为。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: fixed tree/history summary、全量 case ledger 摘要、metric recomputation、asset terminal results、quality sample records 和 maintenance commit evidence。

### TEST-004

- `links`: `TASK-002`, `REQ-006`至`REQ-010`, `INV-004`, `RISK-004`
- `method`: Schema/semantic validator 对 `adapter_ready` 逐项执行准入门槛、状态/rights/publication 语义和排序规则的正反 mutation tests。
- `expected_observable_result`: 不达任一数量、配对、失效、重复、维护、质量或 family 门槛的来源不能为 adapter_ready；未知权利不能 public-ready。
- `failure_path_covered`: 50/0.90/0.05/0.20 边界、maintenance 伪造、rights/public 混淆、未全量审计直接准入。
- `cannot_prove`: Adapter 实现成功。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: validator JSON、mutation matrix、adapter_ready batch 与 rights fail-closed summary。

### TEST-005

- `links`: `ASSEMBLY-001`, `TASK-001`, `TASK-002`, `OBJ-001`, `REQ-001`至`REQ-010`
- `method`: 端到端交叉检查 discovery records、full audit records、adapter_ready_batch、中文报告和 handoff doc，并执行相同输入的 deterministic check。
- `expected_observable_result`: 至少 3 个排序后的 adapter_ready 来源具有完整 fixed Commit/metrics/maintenance/quality/rights 引用，且 TASK-0019 只消费这些记录。
- `failure_path_covered`: shortlist 断链、文档/JSON 数量不一致、排序不确定、候选状态越权。
- `cannot_prove`: TASK-0019 已开发或来源已进入 inventory/publication。

### EV-005

- `for`: `TEST-005`
- `required_evidence_shape`: cross-file reference matrix、deterministic digest、最终 source counts/status counts 和 TASK-0019 input list。

### 正式 Validator Manifest

```json
{"schema_version":1,"validators":[
  {"validator_id":"phase2-source-discovery-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q","tests/phase2/test_source_discovery.py"],"cwd":".","timeout_seconds":300,"invalidation_paths":["reports/phase2/source-discovery-v1.md","reports/phase2/source-discovery-v1.json","schemas/phase2-source-discovery-v1.schema.json","scripts/validate_phase2_source_discovery.py","tests/phase2/test_source_discovery.py","docs/phase2/source-expansion-admission-v1.md","reports/source-audit-v1.json","config/sources-v1.yaml"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"phase2-source-discovery-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase2_source_discovery.py","--audit","reports/phase2/source-discovery-v1.json","--schema","schemas/phase2-source-discovery-v1.schema.json","--live","--determinism-check","--json"],"cwd":".","timeout_seconds":3600,"invalidation_paths":["reports/phase2/source-discovery-v1.md","reports/phase2/source-discovery-v1.json","schemas/phase2-source-discovery-v1.schema.json","scripts/validate_phase2_source_discovery.py","tests/phase2/test_source_discovery.py","docs/phase2/source-expansion-admission-v1.md","reports/source-audit-v1.json","config/sources-v1.yaml","gpt-image-2-two-track-research-2026-08-01.md","gpt-image-2-two-track-research-2026-08-01.xlsx"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | 当前候选全集 | OBJ-001 / TASK-001 / TEST-001 | 8 个旧 probation 与至少 20 个新唯一候选被完整映射和去重 | EV-001 | 不证明案例质量 |
| GATE-002 | 外部身份与失败闭环 | OBJ-001 / TASK-001 / TEST-002 | shortlist 仓库当前可解析固定身份；外部失败 fail closed | EV-002 | 不证明全量案例 |
| GATE-003 | 全量案例与维护质量 | OBJ-001 / TASK-002 / TEST-003 | 至少 8 个候选具有可重算的全量指标、维护和质量证据 | EV-003 | 不证明法律权利 |
| GATE-004 | Adapter 准入语义 | OBJ-001 / TASK-002 / TEST-004 | 至少 3 个来源满足全部 adapter_ready 门槛，未知权利保持不可公开 | EV-004 | 不证明 Adapter 已实现 |
| GATE-005 | Phase 2 handoff 闭环 | OBJ-001 / ASSEMBLY-001 / TASK-001 / TASK-002 / TEST-005 | discovery→audit→batch→handoff 引用闭合且确定性通过 | EV-005 | 不证明后续任务完成 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `reports/phase2/source-discovery-v1.md`
  - `reports/phase2/source-discovery-v1.json`
  - `schemas/phase2-source-discovery-v1.schema.json`
  - `scripts/validate_phase2_source_discovery.py`
  - `tests/phase2/test_source_discovery.py`
  - `docs/phase2/source-expansion-admission-v1.md`
- `documentation_impact`: updated；新增 Phase 2 来源发现、准入和 TASK-0019 handoff 文档；`1.md` 已正确声明 Phase 2 待启动，无需修改。
- `repository_hygiene_requirement`: exact 6 files；所有 clone、图片、网页响应、缓存、质量复核临时资产位于工作区外正式 runtime/evidence root；不得保留凭据、下载图片、node_modules、Python cache 或新仓库 clone；Phase 1 文件和正式历史前后哈希一致。
- `external_review`: policy=never；reason=当前任务为公开来源的只读调查和本地准入合同，不执行外部写入或法律批准；L3 独立语义审查、真实外部证据和 mutation tests 足够。
- `non_completion_rules`:
  - 8 个旧 probation 任一遗漏不得完成。
  - 新唯一候选少于 20 且无完整检索耗尽证据时不得完成。
  - full_audited 少于 8 或 adapter_ready 少于 3 时不得完成；不得降低门槛凑数。
  - 任一 adapter_ready 缺固定 Commit、全量覆盖账、可重算指标、维护证据、质量样本、family 或 rights 状态时不得完成。
  - Skill/工具/镜像/聚合被重复计为 canonical 来源时不得完成。
  - Phase 1 registry/audit、production、rights/public 状态发生变化时不得完成。
  - 两项正式 Validator、exact6 hygiene、L3 independent review、freshness 和 Completion Report 任一未闭合时不得完成。

本卡完成只产生 TASK-0019 的 Adapter 候选批次，不表示这些来源已接入、已入库、已获公开权利或已部署。
