---
task_contract_version: 3
card_id: "TASK-0021"
title: "建立第二批高质量新来源准入与独立贡献审计"
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
- `authority_sources`: 用户明确要求只固定“高价值案例多、能够稳定提取对应图片和提示词”的长期内容来源，并强调继续搜索时必须优先判断内容质量；`1.md` 第 3.1、4、10、15、17 节；`config/sources-v1.yaml`、`reports/source-audit-v1.json`；TASK-0018/TASK-0019 及 `reports/phase2/source-discovery-v1.*`、`docs/phase2/source-expansion-admission-v1.md`、`docs/phase2/phase2-adapter-activation-v1.md`。2026-08-10 并行外部调查只提供 shortlist/parser-design seed observations，未形成仓库内 authority artifact，必须在执行时 live 复核后才能成为结果证据。
- `decision_owner`: 用户确认 Skill/工具项目不属于本来源扩展范围；本轮按内容质量、图文可提取性、固定资产、来源证据、维护真实性和对现有内容的独立贡献决定准入，不按仓库数量或宣传案例数决定。
- `material_unknowns`: HiAPIAI 执行时的完整当前 Commit、默认分支和实质更新历史必须由执行流程重新固定；外部仓库或远程资产在执行时可能变化或不可访问。它们是调查输出与失败分支，不是任务卡就绪阻断；不得用本卡中的种子事实替代 live 证据。

# 2. 业务目标

- `actor`: 项目维护者、来源审核者，以及后续第二批 Adapter 实现任务的执行者。
- `workflow_and_trigger`: 在现有 6 个 active 来源、1513 个内部 Source Case、1930 个输出关系和 0 个真实公开案例不变的前提下，对 3 个已确认值得深入的新候选做固定快照、全量图文覆盖、内容质量、来源权利和只读独立贡献审计，形成只包含真实通过项的第二批 Adapter handoff。
- `single_outcome`: 产生一份独立于历史 v1 证据、可重复校验的 Phase 2 新来源准入 v2；它能回答 `ecomimagelab`、`HiAPIAI`、`imagineVid` 哪些真正具备高质量、稳定提取和来源可管理条件，并明确远程资产、质量、维护或权利阻断，而不直接修改 active registry、Adapter、库存、Canonical 内容或公开状态。
- `observable_results`:
  - `RESULT-001`: 当前 6 个 active 来源的只读基线由生产解析路径重建并固定为 1513 Source Cases、1930 outputs/Generation Examples、0 real public；新审计不得以内部预览展示结果代替生产证据。
  - `RESULT-002`: 对 `ecomimagelab/ecommerce-gpt-image-prompts`、`HiAPIAI/awesome-gpt-image-2-prompts`、`imagineVid/Awesome-gpt-image-2-prompts-and-skills` 三个必审候选完成 repository identity、default branch、固定 Commit、实质维护历史和 canonical/derived 初判。
  - `RESULT-003`: 每个候选具有全量 case ledger、Prompt/图片确定性配对、所有本地或远程资产覆盖账、孤立资产账、稳定 case ID、来源/权利证据和可重算指标；README 宣称数、弱顺序猜测或只抽样计数不能进入有效案例数。
  - `RESULT-004`: 所有候选执行全量机器质量 lint 与确定性视觉/语义样本，区分高质量案例、低信息量 Prompt、Prompt/图错配、明显水印/瑕疵及品牌、名人、身份文档、去水印、成人等需要额外审核的内容。
  - `RESULT-005`: 仅为来源准入评估，对候选与当前 1513 进行只读 exact-overlap 审计：canonical source URL/原帖键、标准化 Prompt SHA-256，以及只针对 fixed local assets 的精确图片 bytes SHA-256；输出 `unique_exact_contribution_count`，不创建或写入 Canonical Case、不自动合并或删除来源证据。
  - `RESULT-006`: `adapter_ready_batch` 只包含 canonical、固定资产、全量覆盖、维护与质量门槛全部通过且具有实际独立贡献的来源；批次允许为空，不得为了满足数量降低门槛。
  - `RESULT-007`: 机器 JSON、Schema、offline/live validator、测试、中文报告、设计状态和下一张 Adapter handoff 一致，且 v1 历史证据与当前 6-source production 合同未漂移。
- `non_goals`: 不处理 Mageia/tigerowo paired-subcorpus remediation；不开展 Canonical/内容级近似去重；不审计或接入 ChaosRealmsAI 历史大库、Goku/YouMind/Atlas 聚合池；不实现/修改生产 Adapter；不更新 registry/source-audit/v1 Phase 2 历史；不导入库存；不建立远程资产长期存储；不录入真实 rights approval；不修改 Content/API/Web/publication；不部署 scheduler；不把 Skill、工具、应用或备份镜像作为独立来源。

# 3. 需求质疑与确认

- `user_statement`: 只需要把高价值案例多、能够提取对应图片和提示词的项目稳定固定为长期内容来源；继续扩大候选时也必须先看内容质量，不能只追求数量。
- `REQ-001` (`required_behavior`): 必审集合必须精确覆盖 `ecomimagelab/ecommerce-gpt-image-prompts`、`HiAPIAI/awesome-gpt-image-2-prompts`、`imagineVid/Awesome-gpt-image-2-prompts-and-skills`；任何替换、遗漏或增加必须先修订任务卡，不能在执行报告中静默改变范围。
- `REQ-002` (`required_behavior`): 每个候选必须记录 repository ID、canonical URL、default branch、完整 lowercase 40 位 Commit SHA、树摘要和实质案例内容更新证据；所有计数、路径、Prompt、图片与维护结论绑定该固定 Commit。
- `REQ-003` (`required_behavior`): 全量 coverage ledger 必须为每条可识别记录保存稳定 source case key、Prompt 存在性、输出引用、来源位置、配对证据、资产终端结果和纳入/排除有效案例的理由；ledger 排序与 digest 必须确定。
- `REQ-004` (`required_behavior`): strong pairing 只能来自 manifest/JSON 的显式关系、同一 case 目录/ID 合同或同文件可验证结构；README 视觉邻接、文件自然排序、人工猜测或无法固定的外链不得计为 strong valid case。
- `REQ-005` (`required_behavior`): 固定 Commit 内本地图片必须逐一解析为安全仓库相对路径，校验常规文件、大小、图片魔数和 SHA-256；所有未被 case ledger 引用的图片必须进入 orphan ledger。远程图片即使当前 HTTP 200 也不等于固定资产。
- `REQ-006` (`required_behavior`): 每个候选先对全部记录执行机器 lint，再按 `min(unique_valid, 60, max(30, ceil(unique_valid*0.15)))` 选择确定性样本；样本必须覆盖目录/类别、Prompt 长短分位、单图/多图、风险标记和 exact-overlap 簇，并逐项检查 Prompt 完整性、图片可辨识性、语义对应、视觉完成度、水印/明显瑕疵和内容多样性。
- `REQ-007` (`required_behavior`): 所有被机器规则标记为缺 Prompt、短/低信息量、缺来源、资产异常、品牌/名人/身份文档/伪造证件/去水印/成人或其他明显高风险的记录必须计数并进入可复核 ledger；不能只检查舒适样本后把全库写为高质量。
- `REQ-008` (`required_behavior`): 独立贡献审计只允许三类 exact evidence：标准化 original/source URL key、标准化 Prompt SHA-256、fixed local asset 的精确图片 bytes SHA-256；保存算法版本、成员与摘要。remote/CDN bytes 不进入 authoritative image-overlap 或 deterministic contribution digest。该审计只影响来源排序和 duplicate-rate 证据，不写 Canonical/Content 数据，不做语义/视觉近似自动归组。
- `REQ-009` (`required_behavior`): `HiAPIAI` 必须同时核对结构化 manifest 声明的主图和目录中可归属的额外输出；孤立或无法确定归属的图片不能静默遗漏。其 CC BY、NOTICE 与来源字段只作为可验证证据，不能自动覆盖第三方 Prompt/图片权利。
- `REQ-010` (`required_behavior`): `ecomimagelab` 的上游 `reviewed/approved/original` 字段只作为 source claim；即使仓库声明原创和 CC BY，所有 Prompt/资产仍保持本项目 `review_required`、`auto_publish=false`。项目较新必须通过 `maintenance_maturity` 字段明确体现。
- `REQ-011` (`required_behavior`): `imagineVid` 的远程 `pbs.twimg.com` 图片必须作为 time-bound observational evidence 全量终端检查，记录 `observed_at`、URL、status、media type、observed bytes SHA-256 和失败分类；这些 volatile observations 存入 live receipt/独立 observation 区，不进入 fixed-core deterministic digest，也不作为 authoritative image-overlap。任务不授权建立持久资产存储，因此在没有既有可复用 immutable snapshot authority 时必须保持 probation/blocked，并生成后续依赖说明。
- `REQ-012` (`required_behavior`): `adapter_ready` 沿用 canonical、至少 50 个唯一有效案例、strong pair rate ≥0.90、broken asset rate ≤0.05、within-source duplicate rate ≤0.20、最近 180 天有实质更新且过去 365 天至少 2 个不同实质更新日期、质量样本通过、rights fail-closed、图片可在固定版本下稳定读取等现有门槛；独立贡献和质量风险只能增强排序/阻断，不能削弱旧门槛。
- `REQ-013` (`required_behavior`): `adapter_ready_batch`、中文 handoff 和每项 full audit 必须一一引用；下一张 Adapter 任务只能消费批次中的 fixed Commit、structure strategy、case scope 和 known exclusions，不得重新按 HEAD、Stars 或 raw case count 选源。
- `REQ-014` (`required_behavior`): 当前 6 active、1513/1930、2260 source files、1885 deduplicated asset objects、0 real public、Candidate v2 仅内部预览、Publication/API/Web v1 隔离等已完成合同不得改变。
- `INV-001`: 历史 `reports/phase2/source-discovery-v1.*`、`schemas/phase2-source-discovery-v1.schema.json`、`scripts/validate_phase2_source_discovery.py`、`tests/phase2/test_source_discovery.py` 和 `docs/phase2/source-expansion-admission-v1.md` 是 TASK-0018/0019 的冻结证据，只能读取/复用，不能重写。
- `INV-002`: 没有本地版本化图片或独立 immutable snapshot authority 的来源不能被标记为稳定可提取；“本次下载成功”不构成长久资产权威。
- `INV-003`: exact-overlap 审计用于准入价值判断，不改变 Source Family、Canonical Case、Content/Public Case Candidate 或现有 1513 的任何生产口径。
- `INV-004`: 来源准入、内容质量通过和仓库许可证都不等于 Prompt/资产公开权利获批；所有新候选 `auto_publish=false`，真实公开案例仍为 0。
- `INV-005`: 不得新增生产依赖、通用 Adapter、远程对象存储或数据库写入来完成调查；如果稳定图片需要新的持久化能力，必须形成后续任务依赖。
- `INV-006`: 所有 clone、下载图片、HTTP 响应、临时数据库和视觉样本位于 workspace 外正式 evidence/runtime root；仓库只保存结构化结果、摘要和文档，不保存候选图片副本或凭据。
- `material_ambiguities`: none；候选集合、准入门槛、exact-overlap 只读边界、当前 production 保护范围和“批次可以为空”均已明确。具体候选最终状态由 fixed Commit 的执行证据决定。
- `DEC-001`: 用户确认质量优先于来源数量，因此本卡不设置必须凑出 N 个 adapter-ready 来源的完成条件。
- `DEC-002`: Skill/工具项目不再作为内容来源；Mageia remediation、历史大库、聚合池和 Canonical 去重必须留在独立责任边界。
- `DEC-003`: 新来源准入只形成 Adapter handoff，不自动更新 registry、库存、审核或公共产品。
- `decisions_and_authority`: `DEC-001`至`DEC-003`来自用户连续确认和独立范围审查；准入阈值、rights/publication 与 fixed-Commit 规则继承 `1.md`、TASK-0018、TASK-0019 和当前 registry/audit 合同。

# 4. 业务场景与规则

- `SCN-001` 主路径: ecomimagelab 或 HiAPIAI 在 fixed Commit 下证明全量强配对、资产固定、质量稳定、维护合格且具有独立贡献，进入排序后的 `adapter_ready_batch`。
- `SCN-002` 新但优质: ecomimagelab 内容质量和结构通过，但维护历史较短；报告保存 `maintenance_maturity` 和风险，依据冻结门槛给出 adapter_ready/probation，不把项目年龄隐藏在简单 pass 中。
- `SCN-003` 远程资产: imagineVid Prompt、来源和视觉质量很好，但图片全部为外链；终端检查形成可行性证据，不能代替持久快照，因此保持非 adapter-ready 并交接明确依赖。
- `SCN-004` 额外/孤立图片: HiAPIAI manifest 只声明主图，但目录中还有额外输出；明确可归属的输出进入同一 case ledger，无法确定归属的文件进入 orphan ledger，不得静默遗漏或猜配。
- `SCN-005` exact overlap: 候选与当前 1513 存在相同原帖、Prompt 或图片；审计保留两边 provenance，只降低 `unique_exact_contribution_count`，不写 canonical group、不删除任何记录。
- `SCN-006` 外部失败: repository/Commit 不可访问、限流、下载失败、路径漂移或 HEAD 改变时，保留已确认 fixed evidence 和 bounded error；不得用搜索缓存、README 摘要或旧默认分支补成通过。
- `SCN-007` 空准入批次: 三个候选都至少有一项门槛不闭合时，任务仍可完成为真实空 batch，但必须提供每个候选的最小阻断条件和后续建议。
- `RULE-001`: 候选状态继续使用 `adapter_ready | probation | blocked | excluded`；准入状态不等于 active/public。
- `RULE-002`: raw case count、quality-valid count、within-source unique count 和 unique exact contribution count 分开；排序优先独立高质量案例价值，再看维护稳定性与 Adapter 成本。
- `RULE-003`: 上游 `approved/reviewed/SFW/original` 只保存为 source claim；本项目 rights/publication 状态由自身合同决定。
- `RULE-004`: source URL/Prompt/image exact match 可自动计数；语义或视觉近似不属于本卡，不能自动合并或影响现有 Canonical 层。
- `RULE-005`: v2 调查只生成后续 Adapter 输入，不把来源写为 active，也不把案例写入 inventory/publication。
- `FLOW-001`: 当前 6-source production baseline + 3 个必审候选 → identity/Commit freeze → 全量 case/asset ledger → 质量/维护/rights → exact-overlap contribution → status/ranking → Adapter handoff。
- `STATE-001`: discovered/known → identity_frozen → full_audited → contribution_audited → adapter_ready/probation/blocked/excluded；失败不得跳过证据层或回写 v1/current 状态。
- `risk_sensitive_invariants`: `INV-001`至`INV-006`、固定版本、完整覆盖、远程资产 fail-closed、quality-first、exact-overlap read-only、rights/publication 隔离和 current 6-source no-drift。
- `inapplicable_faces_with_reason`: 本任务不写数据库/对象存储/外部仓库，不存在生产事务、用户认证、Canonical merge 或公开发布；重复执行要求相同 fixed inputs 产生同一 fixed-core 排序、ledger digest、exact-overlap counts 和状态结论。time-bound remote observations 可随 `observed_at` 变化，必须与 deterministic core 分离且不得改变无 immutable asset authority 的阻断结论。

# 5. 当前证据与目标差异

- `FACT-001`: `config/sources-v1.yaml` 当前有 6 个 active 来源；`docs/phase2/phase2-adapter-activation-v1.md` 记录 1513 Source Cases、1930 outputs/Generation Examples、2260 source files、1885 SHA-256 资产对象和 0 real public。
- `FACT-002`: TASK-0018 的 v1 调查完成 24 个新候选和 9 个 full audit，TASK-0019 只接入其中 freestylefly、erickkkyt、VigoZhao 三项；v1 文件不包含 2026-08-10 三个新候选的当前全量审计，也没有与 current 1513 的 exact contribution 账。
- `ASM-002`: 非权威 seed observation：`ecomimagelab/ecommerce-gpt-image-prompts` 曾在 Commit `6f63eadc6a1ac594a6304e9a3e1eb3e201812d58` 观察到约 284 个结构化 variant、本地资产和较完整来源字段，且未观察到与 current 1513 的 exact Prompt 重复。它只用于 shortlist/parser design；执行时必须重取 fixed identity、全量 counts、quality 和 contribution，不能直接写为最终事实。
- `ASM-003`: 非权威 seed observation：`imagineVid/Awesome-gpt-image-2-prompts-and-skills` 曾在 Commit `b9f27f91bf46de939d8caf0e8142e7932f49c666` 观察到约 95 个 Prompt、207 个 remote output URLs 和较完整来源/作者/模型字段；图片位于 `pbs.twimg.com`。它只用于重新打开调查，不能成为稳定资产或准入证据。
- `ASM-004`: 非权威 seed observation：`HiAPIAI/awesome-gpt-image-2-prompts` 曾观察到约 189 个结构化案例、202 个本地图片文件和约 32 条 current exact Prompt overlaps，manifest 主图之外可能存在额外输出。执行时必须重新取得完整 fixed Commit并全量重算，不能直接复用这些数字。
- `FACT-006`: current registry/source audit 尚未把 ecomimagelab、HiAPIAI 作为正式 candidate records，imagineVid 当前位于 exclusion mapping；本任务只生成新的 v2 evidence，不直接改写状态。
- `ASM-001`: 现有 `scripts/validate_phase2_source_discovery.py`、`scripts/validate_phase2_adapters.py` 和 production ingestion path 可复用 fixed Git、ledger、质量样本和 current 6-source baseline 的部分能力；执行者必须先确认复用边界，不能复制一套不一致语义。
- `current_execution_path`: 维护者可在 `/internal-preview` 浏览 current 6 sources，但无法从现有 v1 evidence判断三个候选的全库质量、稳定资产和 exact independent contribution，也没有第二批 Adapter machine handoff。
- `target_delta`: 新增独立 v2 machine report/schema/validator/tests/中文报告/handoff，并同步 `1.md` 来源扩展状态；不改变 current registry、Adapter、库存、Canonical 和公开消费者。
- `evidence_gaps`: 三个候选的 current fixed identity、全量 ledger、所有资产终端结果、质量 lint/样本、实质维护历史、对 current 1513 的 source URL/Prompt/image exact overlap、unique contribution 和最终 handoff。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `reports/phase2/source-expansion-admission-v2.md`
  - `reports/phase2/source-expansion-admission-v2.json`
  - `schemas/phase2-source-expansion-admission-v2.schema.json`
  - `scripts/validate_phase2_source_expansion_admission.py`
  - `tests/phase2/test_source_expansion_admission.py`
  - `docs/phase2/source-expansion-admission-v2.md`
  - `1.md`
  - 本卡对应正式 execution evidence/sidecar；不计入产品文件数。
- `hard_protected_scope`: `config/sources-v1.yaml`、`reports/source-audit-v1.*`、全部 Phase 2 v1 discovery/admission 文件、production ingestion/adapters/inventory/sync/content/apps/migrations、Canonical data、fixtures、现有 tasks/formal history；外部仓库只读。
- `protected_contracts_and_invariants`: current 6 active 与 1513/1930/2260/1885/0-public；fixed Commit 与 Source Family；Adapter Output/Generation Example；Canonical 层责任；Candidate v2 与 Publication/API/Web v1 隔离；review_required/auto_publish=false；历史任务证据不可变。
- `authorization_limits`: 只授权仓库内 v2 调查产物、测试、文档和 workspace 外的只读 external evidence；不授权 GitHub 写入、长期保存第三方图片、改变 registry/production/Canonical、录入真实 rights、部署、公开发布或联系来源作者。
- `stop_if_scope_expands`: 如果准入必须新增/修改 production Adapter、production dependency、registry、对象存储、数据库、Canonical/API/Web、真实 rights 数据，或需要把远程图片下载为长期资产，则停止并拆出后续任务。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: caller=项目维护者/正式 validator；entry=`scripts/validate_phase2_source_expansion_admission.py` 的 offline/live/determinism 模式；authority=current registry/audit、6-source production ingestion 和候选 fixed snapshots；consumer=第二批 Adapter 任务与维护者。
- `expected_touchpoints_or_search_anchors`: `scripts/validate_phase2_source_discovery.py`、`schemas/phase2-source-discovery-v1.schema.json`、`tests/phase2/test_source_discovery.py`、`scripts/validate_phase2_adapters.py`、`config/sources-v1.yaml`、`reports/source-audit-v1.json`、`reports/phase2/source-discovery-v1.json`、`docs/phase2/phase2-adapter-activation-v1.md`、production `ingestion/` fixed-snapshot/parser path，以及三个候选的 Git tree/history/raw files。
- `wiring_to_final_consumer`: v2 JSON 的 candidate/full audit/contribution records引用 fixed Commit和 ledger digest；`adapter_ready_batch` 只引用 full audit pass 项；中文 handoff列出推荐 Adapter structure、known exclusions、rights 和 remote-asset dependency；下一张 Adapter 卡只能消费这些引用。
- `failure_and_recovery`: external requests有超时、有限重试和错误分类；clone/download/cache 位于 workspace 外按 run 隔离；候选部分失败不污染其他记录；同 fixed revision 的 core ledger/quality/contribution 重跑 deterministic；remote observations 按 `observed_at` 单独记录并排除在 core digest之外；HEAD 变化只形成新 observed fact，不改旧 revision evidence；结束清理运行时资产并保留结构化 receipt。
- `implementation_freedom`: 优先复用 v1 validator、existing fixed Git/ingestion 和标准库；仅在不足时在唯一新 validator 内增加最小 candidate parser。不得为近似去重新增依赖；本卡只要求 exact URL/Prompt/image hashes。
- `selected_profile_obligations`:
  - `investigation`: 核心问题为“三个新候选是否真正提供高质量、稳定、独立的案例”；竞争假设包括新仓结构好但维护未成熟、manifest 漏额外图片、质量高但远程资产不固定；证据必须来自 fixed Commit full ledger、quality sample、maintenance history 和 exact contribution；durable handoff 为本卡 7 项产品交付物。
  - `external-boundary`: Git/raw asset 访问必须 bounded、read-only、无凭据输出；HTTP 200、default HEAD 和 CDN current bytes 不构成 immutable authority；临时 clone/图片/响应在 workspace 外，部分失败 fail closed，不向 external system 写入。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`, `REQ-002`, `INV-001`
- `owns_behavior`: 固定三个候选的 repository identity、Commit、tree/history、canonical/derived 初判和实质维护 evidence。
- `business_result`: 调查全集和 fixed authority 清晰，后续 case/asset metrics不会跟随 moving HEAD 或错误仓库身份。
- `target_delta`: seed facts → unique repository authority records with full Commit、tree/history、maintenance 和 bounded error。
- `behavior_faces`: normal=fixed current Commit；boundary=new repo/previous exclusion；failure=404/limit/HEAD drift/Commit unreadable；empty=no revision；repeated=same revision same authority；downstream=只有 identity_frozen 可进 TASK-002。
- `state_change`: known/discovered → identity_frozen 或 blocked/unavailable；不修改 registry。
- `data_flow`: current evidence + repository metadata/history → authority records → TASK-002。
- `integration_edges`: GitHub/Git tree、current candidate mapping、v2 JSON/schema。
- `expected_touchpoints`: 新 v2 report/schema/validator/tests；v1 artifacts read-only。
- `integration_point`: caller=live validator；callee=bounded Git readers；consumer=full audit parsers。
- `scope_boundary`: 不更新 registry，不以 HEAD 作为 case authority。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-002`, `SCN-003`, `SCN-006`。
- `linked_tests`: `TEST-001`
- `stop_conditions`: 触发任一条件即停止并报告：需要 external write/credential；repository identity 存在冲突或不唯一；fixed Commit 不可读取而只剩 moving HEAD。

### TASK-002

- `links`: `OBJ-001`, `REQ-003`至`REQ-007`, `REQ-009`至`REQ-011`, `INV-002`, `INV-005`, `INV-006`
- `owns_behavior`: 三个 fixed candidates 的全量 case/asset ledger、strong pairing、orphan coverage、quality、rights/provenance 和 candidate-specific failures。
- `business_result`: 每个候选的真实有效案例、内容质量和稳定提取能力可重算，而不是依赖 README、raw file count 或当前 CDN 可用性。
- `target_delta`: identity_frozen candidates → deterministic fixed-core full audits with ledger/digest、quality lint/sample、local asset summary、maintenance/rights evidence，以及独立 time-bound remote observation receipts。
- `behavior_faces`: normal=structured local cases；boundary=multi-output/extra assets/remote assets；failure=missing prompt/image/orphan/bad image/ID collision/mismatch/remote drift；permission=source claims only；empty=0 valid；repeated=same revision same ledger；downstream=TASK-003。
- `state_change`: identity_frozen → full_audited 或 probation/blocked/excluded；无 production side effect。
- `data_flow`: fixed tree/files/assets/history → candidate parser/ledger → metrics/quality/rights records。
- `integration_edges`: v1 audit helpers、fixed snapshots、image terminal validation、candidate structure、schema/tests。
- `expected_touchpoints`: 新 validator/parser、JSON/MD/schema/tests。
- `integration_point`: caller=TASK-001 authority；callee=fixed readers/quality sampler；consumer=contribution/status。
- `scope_boundary`: 不实现 production Adapter；remote assets不写 durable store。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-004`, `SCN-006`。
- `linked_tests`: `TEST-002`, `TEST-003`
- `stop_conditions`: 触发任一条件即停止并报告：需要 persistent asset snapshot；source structure 只支持人工猜配；quality sample 终端读取失败；full ledger 不能闭合。

### TASK-003

- `links`: `OBJ-001`, `REQ-008`, `REQ-012`至`REQ-014`, `INV-003`, `INV-004`
- `owns_behavior`: 三个候选对 current 1513 的 exact contribution audit、status/ranking、adapter_ready batch 和 handoff/no-drift assembly。
- `business_result`: 维护者知道每个候选真正增加多少 exact-new 高质量案例，并获得唯一可执行的第二批 Adapter 输入或真实空批次。
- `target_delta`: full audits + current production ledger → exact URL/Prompt/image overlap counts、unique exact contribution、status/ranking、batch/handoff/design sync。
- `behavior_faces`: normal=nonempty batch；boundary=exact duplicate/remote blocker/empty batch；failure=hash缺失/current baseline drift/cross-file mismatch/rights越权；repeated=stable counts/digest；downstream=next Adapter task only。
- `state_change`: full_audited → contribution_audited → adapter_ready/probation/blocked/excluded；current production unchanged。
- `data_flow`: production current ledger + candidate ledgers → exact hashes/counts → decision/batch → JSON/MD/handoff/`1.md`。
- `integration_edges`: production ingestion baseline、v2 artifacts、next Adapter consumer、protected v1/current hashes。
- `expected_touchpoints`: section 6 全部 7 项产品交付物。
- `integration_point`: caller=TASK-002；callee=current six-source reader；consumer=maintainer/next task。
- `scope_boundary`: 不写 Canonical/Content/registry/inventory，不做 near-duplicate merge。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`, `SCN-005`至`SCN-007`。
- `linked_tests`: `TEST-004`
- `stop_conditions`: current 1513不能从production path重建、exact算法/成员不可复核、protected drift或为凑batch降低门槛。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`
- `end_to_end_entry`: current 6-source production registry/fixed snapshots 与三个必审 candidate repositories。
- `shared_contract_state_data`: fixed identity/Commit、case/asset ledger、quality/maintenance/rights、exact URL/Prompt/image contribution、status、adapter_ready batch、1513/1930/0-public protected baseline。
- `final_consumer`: 第二批来源 Adapter 任务与项目维护者。
- `cross_task_failure_path`: identity不闭合不得 full audit；ledger/asset/quality不闭合不得 contribution/admission；decision失败不得 handoff；handoff不修改 current production；候选部分失败保持独立错误记录。
- `linked_test_evidence_gate`: `TEST-004` / `EV-004` / `GATE-004`

# 9. 验证与验收

- `risk_sensitive_invariants`: `INV-001`至`INV-006`、fixed Commit、全量覆盖、remote asset fail-closed、quality-first、exact contribution read-only、rights/publication 隔离和 current 6-source no-drift。
- `consumer_chain_validation`: 必须从 current registry/production parsers 重建1513/1930，读取三个 fixed candidate ledgers，形成 quality/contribution/status/batch，再由中文 handoff与`1.md`消费同一 machine records；只验证Schema或只看报告不能关闭本卡。
- `real_integration_evidence`: workspace外真实 fixed Git revisions、候选全部 case/asset refs、deterministic quality samples、time-bound remote observation receipts、current 6-source production extraction、fixed-local-only exact image hashes、URL/Prompt hashes和fixed-core deterministic rerun。
- `failure_recovery_ownership_validation`: external reader负责 timeout/retry/error；candidate parser负责 coverage/pair/orphan；quality layer负责 lint/sample；contribution layer负责 versioned exact keys/hashes；admission/assembly负责status/batch/cross-file/no-drift/hygiene，不能互相绕过。

### RISK-001
- `description`: README 宣传数、upstream reviewed 字段或局部样本冒充全库内容质量与稳定性。

### RISK-002
- `description`: current-accessible CDN images被误当fixed assets，导致 imagineVid 后续无法复现。

### RISK-003
- `description`: HiAPIAI/ecomimagelab extra/orphan images被静默遗漏，case/output counts和pair rate虚高。

### RISK-004
- `description`: 未与current 1513做exact contribution audit，导致重复内容被当作高价值新增来源。

### RISK-005
- `description`: 质量样本偏向舒适案例，短Prompt、身份/品牌/名人/成人、水印或错配记录未进入结论。

### RISK-006
- `description`: repository license、source claim或source admission被误写成real public rights approval。

### RISK-007
- `description`: v2调查重写v1 evidence或current registry/production/Canonical，破坏已完成供应链和0-public边界。

### TEST-001

- `links`: `TASK-001`, `REQ-001`, `REQ-002`, `RISK-001`, `RISK-007`
- `method`: offline schema/semantic fixtures覆盖三个必审候选、repository identity/full Commit/tree/history/maintenance和bounded errors；live mode重新解析当前repository identity、fixed Commit与archive/default-branch状态。
- `expected_observable_result`: 三个candidate均有唯一 authority record；moving HEAD、缺SHA、候选遗漏或identity conflict fail closed。
- `failure_path_covered`: 404、rate limit、branch drift、noncanonical URL、empty/unreadable Commit。
- `cannot_prove`: case-level content、asset和quality。

### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: authority records、repository IDs、full Commit、tree/history/maintenance summary、terminal error classifications和deterministic authority digest。

### TEST-002

- `links`: `TASK-002`, `REQ-003`至`REQ-005`, `REQ-009`至`REQ-011`, `RISK-002`, `RISK-003`
- `method`: candidate-specific fixed parsers对全部可识别records、image refs和repository image files重算ledger、pair/valid/broken/orphan/ID metrics；remote URLs执行bounded terminal checks但不提升为fixed assets。
- `expected_observable_result`: 每个count可由ledger重算；local asset paths/SHA完整；HiAPI extras和ecom assets无silent omission；imagineVid无snapshot authority时非adapter-ready。
- `failure_path_covered`: missing prompt/image、bad magic、unsafe path/symlink、orphan、duplicate ID、weak pairing、remote 404/content drift。
- `cannot_prove`: content semantic quality、legal rights和future maintenance。

### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: per-candidate fixed-core ledger/digest、fixed source paths、local asset ref/file/orphan counts、pair arithmetic、stable ID proof，以及与 core digest 分离的 remote `observed_at`/status/media type/observed hash receipts。

### TEST-003

- `links`: `TASK-002`, `REQ-006`, `REQ-007`, `REQ-010`至`REQ-012`, `RISK-001`, `RISK-005`, `RISK-006`
- `method`: 全量machine lint；按冻结公式/风险分层生成deterministic sample IDs，终端读取图片并逐项记录Prompt完整性、semantic correspondence、visual quality、diversity、defects和risk flags；mutations验证sample偏置、漏flag和source-claim越权失败。
- `expected_observable_result`: sample可复现并覆盖category/length/risk/output structure；所有machine flags有全量counts；quality和rights独立，上游reviewed/SFW不会产生public-ready。
- `failure_path_covered`: comfort-only sample、short prompt漏计、wrong image/watermark/high-risk漏记、sample digest drift、rights auto-approval。
- `cannot_prove`: legal permission、future quality和human final review。

### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: lint rule/version、full flag counts/IDs、sample formula/IDs/digest、per-item visual results、quality summary、rights/source-claim matrix和negative mutations。

### TEST-004

- `links`: `ASSEMBLY-001`, `TASK-003`, `OBJ-001`, `REQ-008`, `REQ-012`至`REQ-014`, `RISK-004`, `RISK-007`
- `method`: 从production six-source extraction重建current 1513/1930；对candidate ledgers计算versioned exact source URL/Prompt hashes和fixed-local-only image hashes，得到unique contribution；remote observations排除在image overlap与fixed-core digest外；交叉校验status/batch/JSON/MD/handoff/`1.md`，重复运行core determinism并检查protected hashes/hygiene。
- `expected_observable_result`: 每个candidate raw/within-source unique/current exact overlap/unique exact contribution分开；batch只含full pass项且允许为空；current production/v1/Canonical/0-public不变。
- `failure_path_covered`: normalization drift、missing hash、near-duplicate自动merge、report/JSON mismatch、non-pass batch item、threshold weakening、protected drift、temp asset residue。
- `cannot_prove`: production Adapter已实现、future maintenance、real rights或deployment。

### EV-004
- `for`: `TEST-004`
- `required_evidence_shape`: current baseline receipt、exact normalization/version、per-candidate contribution waterfall/digests、final status/batch/cross-file matrix、protected hashes、hygiene manifest和formal validator receipts。

### 正式 Validator Manifest

```json
{"schema_version":1,"validators":[
  {"validator_id":"phase2-new-source-admission-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q","tests/phase2/test_source_expansion_admission.py"],"cwd":".","timeout_seconds":600,"invalidation_paths":["reports/phase2/source-expansion-admission-v2.md","reports/phase2/source-expansion-admission-v2.json","schemas/phase2-source-expansion-admission-v2.schema.json","scripts/validate_phase2_source_expansion_admission.py","tests/phase2/test_source_expansion_admission.py","docs/phase2/source-expansion-admission-v2.md","1.md","config/sources-v1.yaml","reports/source-audit-v1.json","reports/phase2/source-discovery-v1.json","scripts/validate_phase2_source_discovery.py","scripts/validate_phase2_adapters.py"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"phase2-new-source-admission-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase2_source_expansion_admission.py","--audit","reports/phase2/source-expansion-admission-v2.json","--schema","schemas/phase2-source-expansion-admission-v2.schema.json","--live","--determinism-check","--json"],"cwd":".","timeout_seconds":5400,"invalidation_paths":["reports/phase2/source-expansion-admission-v2.md","reports/phase2/source-expansion-admission-v2.json","schemas/phase2-source-expansion-admission-v2.schema.json","scripts/validate_phase2_source_expansion_admission.py","tests/phase2/test_source_expansion_admission.py","docs/phase2/source-expansion-admission-v2.md","1.md","config/sources-v1.yaml","reports/source-audit-v1.json","reports/phase2/source-discovery-v1.json","reports/phase2/source-discovery-v1.md","docs/phase2/source-expansion-admission-v1.md","docs/phase2/phase2-adapter-activation-v1.md","schemas/phase2-source-discovery-v1.schema.json","scripts/validate_phase2_source_discovery.py","scripts/validate_phase2_adapters.py","ingestion"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | candidate identity/Commit | OBJ-001 / TASK-001 / TEST-001 | 三个必审candidate全部固定current repository authority，失败fail closed | EV-001 | 不证明case quality |
| GATE-002 | full case/asset coverage | OBJ-001 / TASK-002 / TEST-002 | 每个candidate的case/asset/orphan/ID ledger可重算；remote assets未冒充fixed assets | EV-002 | 不证明semantic quality/legal rights |
| GATE-003 | content quality/rights | OBJ-001 / TASK-002 / TEST-003 | full lint、deterministic risk sample和visual review闭合，source claims不越权 | EV-003 | 不证明future quality/human approval |
| GATE-004 | contribution/admission handoff | OBJ-001 / ASSEMBLY-001 / TASK-003 / TEST-004 | current 1513/1930与exact contribution、status/batch/handoff/design/protected baseline一致；batch允许为空 | EV-004 | 不证明Adapter/publication已完成 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `reports/phase2/source-expansion-admission-v2.md`
  - `reports/phase2/source-expansion-admission-v2.json`
  - `schemas/phase2-source-expansion-admission-v2.schema.json`
  - `scripts/validate_phase2_source_expansion_admission.py`
  - `tests/phase2/test_source_expansion_admission.py`
  - `docs/phase2/source-expansion-admission-v2.md`
  - `1.md`
- `documentation_impact`: updated；新增三个高价值新来源的v2 admission evidence与Adapter handoff，并在`1.md`记录来源扩展并行工作流、current 6 active/1513/1930/0-public不变和后续Adapter依赖；不得写成来源已接入。
- `repository_hygiene_requirement`: exact 7 product files；所有clone、candidate images、Git/HTTP responses、temporary DB、quality samples和cache位于workspace外formal evidence/runtime root；不得保留`.venv`、`__pycache__`、`.pytest_cache`、node_modules、candidate clone、third-party images或credentials；v1/hard-protected files前后hash一致。
- `external_review`: policy=never；reason=任务是public-source read-only investigation和local admission evidence，不执行external write、production mutation或legal approval；L3 independent semantic review、live fixed-snapshot evidence、mutation tests和consumer-chain validation足够。
- `non_completion_rules`:
  - 三个必审candidate任一静默遗漏时不得完成。
  - 任一full audit缺full Commit、complete case/asset/orphan ledger、stable ID、pair arithmetic、quality/maintenance/rights或deterministic digest时不得完成。
  - remote CDN current availability被写为immutable asset authority，或imagineVid无snapshot authority仍进入adapter-ready时不得完成。
  - HiAPIAI/ecomimagelab extra/orphan assets被静默遗漏，或只看manifest主图/README counts时不得完成。
  - 未与current 1513做exact source URL/Prompt/image contribution audit，或raw count被写为unique contribution时不得完成。
  - 执行semantic/visual near-duplicate merge、写Canonical/Content data或用近似结果自动删除/阻断时不得完成。
  - 质量只做random/comfort sample、full risk flags未计数、upstream reviewed/SFW/license被解释为real rights approval时不得完成。
  - 为凑数量降低既有adapter-ready门槛或强制生成nonempty batch时不得完成；真实empty batch允许。
  - `config/sources-v1.yaml`、production、Canonical、v1 evidence、1513/1930/0-public或Public API/Web v1发生drift时不得完成。
  - 两项formal validators、exact7 hygiene、L3 independent review、freshness和Completion Report任一未闭合时不得完成。

本卡完成只产生第二批新来源Adapter的fixed evidence和handoff；不表示任何来源已成为active、已导入inventory、已取得real public rights、已进入Canonical/公共网页或已部署同步。
