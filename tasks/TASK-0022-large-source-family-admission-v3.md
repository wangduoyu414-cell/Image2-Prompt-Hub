---
task_contract_version: 3
card_id: "TASK-0022"
title: "建立 Chaos 固定历史与 Goku 去重增量双通道准入 v3"
status: "ready"
work_kind: "investigation"
execution_target: "agent-executable"
complexity: "standard"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "investigation"
  - "external-boundary"
  - "public-contract"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户在 TASK-0021 完成后确认继续执行第二批大规模高质量来源审计；在对 Goku、tigerowo、ChaosRealmsAI、YouMind 的并行比较调研完成后，用户接受将范围收缩为 Chaos 固定历史 full candidate、Goku 去重增量 full candidate、YouMind 家族去重 comparator、tigerowo exclusion control；`1.md` 第 3.1、4、10、17、18 节；TASK-0018 至 TASK-0021；`config/sources-v1.yaml`、`reports/source-audit-v1.json`、`reports/phase2/source-expansion-admission-v2.*`、`docs/phase2/source-expansion-admission-v2.md`。
- `decision_owner`: 用户确认质量、稳定图文资产和独立贡献优先于来源数量；TASK-0022 可以产生空准入批次，可以把静态但高质量且可固定的来源归入“一次性固定历史”通道，并明确不再把 tigerowo 当作完整准入候选。
- `material_unknowns`: Goku 与 Chaos 在执行时的固定 revision、全量计数、资产可访问性、实质内容更新、过滤后质量和真实独立贡献必须 live 重算；Goku/YouMind 精确交集及 tigerowo 排除依据也必须绑定固定输入复核。这些是本任务调查结果，不阻断任务卡就绪，也不得由 README 宣称或本卡 seed observations 代替。

# 2. 业务目标

- `actor`: 项目维护者、来源审核者，以及后续 Adapter/固定历史导入任务执行者。
- `workflow_and_trigger`: 在当前 6 个 active 来源、1513 internal Source Cases、1930 outputs、2260 source files、1885 deduplicated asset objects、0 real public 不变的前提下，对 Goku 与 Chaos 两个 full candidates 执行固定版本、全量结构、内容质量、风险、来源权利、资产权威和独立贡献审计；YouMind 只提供 Goku 家族去重边界，tigerowo 只提供排除闭环。
- `single_outcome`: 产生独立的 `source-expansion-admission-v3`，只允许通过全部门槛的 Goku 过滤增量子集或 Chaos 固定历史子集进入 `continuous` / `fixed_history` handoff；YouMind 与 tigerowo 均不得进入 `adapter_ready_batch`，且不直接接入生产。
- `observable_results`:
  - `RESULT-001`: 从生产解析路径重建当前 6-source 基线并证明 1513/1930/2260/1885/0-public 未漂移。
  - `RESULT-002`: 精确固定 `Goku-OpenLab/gpt-image-2-prompts-datasets` 与 `ChaosRealmsAI/gpt-image-2-gallery` 的完整 repository/dataset identity、default branch、40 位 revision、树/文件清单和实质内容历史；固定 YouMind comparator 与 tigerowo exclusion control 所需的 identity/revision/evidence scope。
  - `RESULT-003`: Goku 与 Chaos 形成全量 case/asset/orphan ledger；YouMind 形成足够重算 Goku/YouMind/Atlas 家族精确交集、来源归因、远程资产和参考图依赖的 comparator ledger；tigerowo 形成可复核 exclusion record，不建立完整准入 ledger。所有 full candidate 的 raw、parseable、authority-valid、safety-eligible、quality-valid、within-family unique、current exact-new 数量分层保存。
  - `RESULT-004`: Git 普通资产以 fixed revision 下的安全相对路径、文件 bytes、媒体魔数和 SHA-256 为权威；Hugging Face LFS 资产以 fixed revision、path、LFS SHA-256 OID 和 size 为完整对象权威，并对确定性样本实际下载、解码和视觉检查；普通 CDN/CMS URL 仅为时点观测。
  - `RESULT-005`: Goku/Chaos 全量机器 lint、确定性准入样本和确定性排除样本共同证明 Prompt 完整性、图文语义对应、视觉完成度、多样性，以及名人、品牌/logo、去水印、成人、武器、未成年人、身份文档和参考图依赖等风险没有被舒适样本隐藏；control sources 不以质量样本竞争准入。
  - `RESULT-006`: 对当前 1513、Goku、Chaos 及 Goku/YouMind/Atlas 家族执行 exact source URL、Prompt SHA-256 和仅限固定资产的精确图片摘要审计；tigerowo/EvoLink 只保留足够阻止其被当作独立来源重新准入的 lineage/exclusion 证据。派生、聚合或镜像内容不得重复计算为独立贡献。
  - `RESULT-007`: `adapter_ready_batch` 只允许包含全部门槛通过的 Goku `continuous` 项或 Chaos `fixed_history` 项，并显式携带 fixed revision、case scope、结构策略、family role 和 exclusions；批次允许为空，来源与 mode 不得互换，YouMind 与 tigerowo 必须始终不在其中。
  - `RESULT-008`: v3 JSON、Schema、validator、tests、中文报告、handoff 和 `1.md` 一致；v1/v2 历史证据、registry、Adapter、库存、Canonical、Candidate v2、Public API/Web 和公开状态未改变。
- `non_goals`: 不实现 Adapter 或同步调度；不修改 registry/source-audit/v1/v2 冻结证据；不导入库存或 Canonical；不执行语义/视觉近似自动合并；不建立远程对象存储；不取得或录入真实 rights approval；不修改 Content/API/Web/publication；不把 Skill 项目或搜索工具本身当作独立内容源；不要求本轮必须产生非空 ready batch。

# 3. 需求质疑与确认

- `user_statement`: 继续寻找案例量大、图文可稳定提取且内容质量高的来源；比较调研后只继续深入 Goku 与 Chaos，YouMind 用于去重对照，tigerowo 不再作为准入来源，不能为了数量降低标准。
- `REQ-001` (`required_behavior`): 必审范围必须精确包含两个 full candidates：`Goku-OpenLab/gpt-image-2-prompts-datasets`、`ChaosRealmsAI/gpt-image-2-gallery`；一个 family comparator：`YouMind-OpenLab/gpt-image-2-prompts-search`；一个 exclusion control：`tigerowo/awesome-gpt-image-2-prompts`。只有两个 full candidates 可以进入质量准入和 ready batch；替换、静默遗漏或升级 comparator/exclusion control 必须先修订任务卡。
- `REQ-002` (`required_behavior`): 每个来源必须记录稳定 repository/dataset ID、canonical URL、default branch、完整 lowercase 40 位 revision、树/文件摘要和内容级维护历史；moving HEAD、更新时间戳或 README 数字不得成为解析权威。
- `REQ-003` (`required_behavior`): 来源家族必须显式记录 `family_id`、`canonical_source_id`、`family_role=canonical|mirror|aggregator|reserve`、admission role 和判定证据。Goku、YouMind、Atlas 相关内容不得被计为三个独立原创来源；tigerowo 自述 EvoLinkAI backup 必须保留为 lineage claim，不能冒充 Git fork 事实，也不能据此建立独立贡献。
- `REQ-004` (`required_behavior`): 每个 full candidate 必须生成确定性全量 ledger，包含稳定 case ID、Prompt、模型证据、来源位置/原帖、输出引用、配对证据、资产权威、风险标记、纳入/排除原因；所有计数必须可由 ledger 重算。
- `REQ-005` (`required_behavior`): strong pairing 只能来自结构化 manifest/JSON/meta、同 case 目录或稳定 ID/文件合同；README 视觉邻接、自然排序、目录猜配或无法固定的外链不得进入 strong-valid 计数。
- `REQ-006` (`required_behavior`): 对 Goku/Chaos full candidates 的普通 Git 本地图片逐一校验安全路径、常规文件、大小、魔数和 SHA-256，并枚举 orphan；Goku HF LFS 必须完整枚举 fixed revision 中的 path/OID/size 与 record references，缺 OID、路径、对象或引用即 fail-closed。HF 不要求为任务卡证明而盲目下载 5GB+ 全库，但质量样本、异常项和解码证据必须真实下载；不得把未下载的 LFS 对象写成已解码。YouMind 只记录 remote authority/comparator 边界，tigerowo 不执行全量资产校验。
- `REQ-007` (`required_behavior`): Goku/Chaos 允许形成确定性 filtered subcorpus，但 raw records、每条 exclusion reason、排除前后计数和 digest 必须完整保存。不得用人工随意删例、只保留好看案例或修改 Prompt/图片来制造通过；YouMind/tigerowo 不产生可准入 filtered subcorpus。
- `REQ-008` (`required_behavior`): 对 Goku/Chaos safety-eligible、authority-valid 的 within-source unique 集合按 `min(unique_valid, 60, max(30, ceil(unique_valid*0.15)))` 生成准入质量样本；另生成覆盖每种主要 exclusion/risk reason 的确定性排除样本。样本覆盖 category、Prompt 长短分位、单/多输出、reference-image 依赖、risk flags 和 overlap clusters。YouMind 只做 comparator 所需的确定性数据/远程边界样本，tigerowo 不做质量准入样本。
- `REQ-009` (`required_behavior`): Goku/Chaos 全库机器规则必须统计缺 Prompt/来源/图片、短或低信息量、品牌/logo、名人、去水印/透明抠图、成人、武器/血腥、未成年人、身份/官方文档、第三方 IP、参考图依赖和可疑乱码/水印；YouMind 只统计影响 comparator 可信度的缺 Prompt/来源/图片、reference-image 和归因字段，tigerowo 只保留排除依据。这些信号只能触发排除或 review_required，不能自动授予或否定法律权利。
- `REQ-010` (`required_behavior`): exact contribution 只允许标准化 original/source URL、标准化 Prompt SHA-256，以及 fixed Git SHA-256 或 HF LFS SHA-256 OID；remote/CDN bytes 不进入 authoritative image overlap 或 fixed-core digest。审计只影响来源价值和 handoff，不写 Canonical/Content 数据。
- `REQ-011` (`required_behavior`): 只有 Goku 可竞争 `continuous`，并沿用至少 50 个唯一有效案例、strong pair rate ≥0.90、broken authoritative asset rate ≤0.05、within-source duplicate rate ≤0.20、最近 180 天有实质内容更新且过去 365 天至少 2 个不同实质更新日期、质量样本全过、rights fail-closed 和固定资产可读等门槛；维护门槛失败时保持 non-ready，不得在本卡中改投 fixed_history。
- `REQ-012` (`required_behavior`): 只有 Chaos 可竞争 `fixed_history`；该通道沿用除持续维护外的所有质量、配对、资产、重复和 rights 门槛，并额外要求完整 immutable snapshot authority、固定 revision 可访问、无增量同步宣称、`sync_eligible=false`、`one_shot_import_only=true`。Chaos 不得进入 continuous/scheduler handoff，其他来源不得在本卡中改投 fixed_history。
- `REQ-013` (`required_behavior`): Goku 只审计精确 `model_info.name=gpt-image-2` 的记录；必须使用 fixed HF revision 的 `metadata.jsonl`/文件树或等价官方数据，排除缺 sourceLink、缺资产对象、模型证据不符和弱 Prompt，并对 Goku/YouMind/Atlas family 做 cross-source 去重。Dataset card 的 CC BY 4.0 仅为 package/source claim。
- `REQ-014` (`required_behavior`): tigerowo 不再执行 full ledger、质量抽样或 ready 判定；只需固定其 identity/revision，引用现有 family-mapping blocked 证据，并以最小可复核数据确认 EvoLink backup/mirror 特征、明显重复或结构不一致足以维持 `excluded`。若新证据实质推翻排除前提，必须停止并修订任务卡，不能在本次执行中静默升级。
- `REQ-015` (`required_behavior`): ChaosRealmsAI 必须按完整 meta+本地图片结构重算，不以单次大提交或 repository size 代替案例数；若质量和资产通过但维护门槛不满足，只能进入 fixed_history，不能伪造 continuous 活跃度。MIT repository license 不能自动覆盖案例权利。
- `REQ-016` (`required_behavior`): YouMind 只作为 Goku/Atlas family comparator，必须从 fixed revision 重算结构化 references、Prompt SHA-256 交集、CMS 图片权威、作者/原帖暴露程度和 reference-image 依赖；无论其内容增长如何，本任务均不得把它升级为 full candidate 或 ready batch 项。
- `REQ-017` (`required_behavior`): `adapter_ready_batch`、两个 full audits、YouMind comparator、tigerowo exclusion record、中文 handoff 和下一任务输入必须一一引用；下一任务只能消费 batch 中 Goku/Chaos 的 fixed revision、ingestion mode、structure strategy、case scope、family role 和 exclusions，不得重新按 HEAD、Stars、README 数或 raw count 选源，也不得自行加入 YouMind/tigerowo。
- `REQ-018` (`required_behavior`): 当前 6 active、1513/1930/2260/1885/0-public、Candidate v2 内部审核、Publication/API/Web v1 隔离、TASK-0021 v2 empty batch 和所有 v1/v2 冻结证据不得漂移。
- `INV-001`: `reports/phase2/source-expansion-admission-v2.*`、`schemas/phase2-source-expansion-admission-v2.schema.json`、`scripts/validate_phase2_source_expansion_admission.py`、`tests/phase2/test_source_expansion_admission.py`、`docs/phase2/source-expansion-admission-v2.md` 是 TASK-0021 冻结证据，默认只读。
- `INV-002`: `continuous` 与 `fixed_history` 是不同运行语义；固定历史来源不得被 scheduler、default-branch polling 或增量同步消费。
- `INV-003`: 没有 fixed Git/LFS/object snapshot authority 的远程图片来源不能进入 ready；“本次 HTTP 200”不构成长久资产权威。
- `INV-004`: 聚合或镜像关系不删除 provenance，但同一 source post/Prompt/asset family 不得重复计算独立贡献。
- `INV-005`: 来源准入、过滤子集、仓库 license、上游 SFW/approved 字段都不等于 public rights；所有新增案例继续 `review_required`、`auto_publish=false`，真实公开案例仍为 0。
- `INV-006`: 所有 clone、HF metadata/LFS sample、候选图片、HTTP 响应和质量样本位于 workspace 外 runtime/evidence root；仓库不保存第三方图片副本、LFS objects、凭据、`.venv` 或 cache。
- `material_ambiguities`: none；双通道语义、两个 full candidates、一个 family comparator、一个 exclusion control、质量优先、filtered-subcorpus 可审计边界、批次可为空、v2 保护范围均由用户确认。最终状态和计数由执行证据决定。
- `DEC-001`: 用户确认静态但高质量、可固定的 Chaos 类来源可进入 `fixed_history`，不再把持续更新作为所有来源的统一门槛。
- `DEC-002`: 用户确认 YouMind 暂作候补；其主要价值是内容增长和家族对照，不能因数量大直接进入 Adapter handoff。
- `DEC-003`: 用户确认继续以内容质量、稳定图文提取和独立贡献为准，不设置必须凑出 N 个 ready 来源的完成条件。
- `DEC-004`: TASK-0022 只产生 v3 evidence/handoff，不直接实现 Adapter、同步或公开消费。
- `DEC-005`: 用户接受比较调研结论，将 tigerowo 从 full candidate 移为 exclusion control，并将 YouMind 固定为 Goku 家族去重 comparator；本任务仅允许 Goku 与 Chaos 竞争 ready 状态。
- `decisions_and_authority`: `DEC-001`至`DEC-005`来自用户对上一轮建议及本轮比较调研结论的明确接受；固定版本、rights/publication、exact-only、current baseline 和 fail-closed 规则继承 `1.md`、TASK-0018 至 TASK-0021。

# 4. 业务场景与规则

- `SCN-001` continuous 主路径: Goku 的确定性过滤子集在 fixed HF revision 下通过资产、质量、来源、维护和 Goku/YouMind/Atlas family 去重门槛，进入 `continuous` handoff；未通过时保持 probation/blocked。
- `SCN-002` fixed history 主路径: Chaos 的完整静态库质量和 immutable assets 通过，但没有持续维护；进入 `fixed_history`，并明确只允许一次性 fixed-commit 导入。
- `SCN-003` aggregation 主路径: Goku 提供大规模版本化 HF 资产，但包含 YouMind/Atlas 派生内容；报告保留聚合 provenance、过滤无来源/无资产项并按 family 去重后计算真实独立贡献。
- `SCN-004` comparator: YouMind 内容增长真实，但其任务角色仅是重算 Goku/Atlas family overlap、CMS/归因和参考图边界；始终保持非 ready。
- `SCN-005` filtered subset: Goku 或 Chaos 的高风险、缺来源、缺资产或低质量案例被确定性排除；剩余子集重新计算全部门槛，不能沿用 raw 库指标。
- `SCN-006` external failure: GitHub/HF revision、metadata、LFS tree 或远程样本不可读取、限流、路径漂移或 HEAD 更新时，保留 bounded failure 并判定非 ready，不用缓存摘要补通过。
- `SCN-007` empty batch: 所有来源至少一项门槛不闭合时，任务仍可完成为真实空 batch，但必须列出每个来源的最小阻断和后续条件。
- `SCN-008` excluded control: tigerowo 的 fixed identity 与既有/最小复核证据继续支持 backup/mirror、重复或结构不一致结论；报告维持 `excluded` 且不为其构建 full ledger。若证据冲突则停止而不是升级。
- `RULE-001`: 状态为 `continuous_ready | fixed_history_ready | probation | blocked | excluded | reserve`；状态不等于 active/public。
- `RULE-002`: raw、parseable、authority-valid、safety-eligible、quality-valid、within-source unique、within-family unique、current exact-new 分层计数，任一层不得互相冒充。
- `RULE-003`: 内容级实质更新由 record/asset/category 集合变化证明；README 时间、自动生成时间戳或相同总数刷新不算 substantive update。
- `RULE-004`: package license、source claim 和本项目 rights/publication 状态分层保存。
- `RULE-005`: v3 是下一张 Adapter/one-shot import 任务的只读 handoff，不改变任何生产来源状态。
- `FLOW-001`: current six-source baseline + Goku/Chaos full candidates + YouMind family comparator + tigerowo exclusion control → fixed identity/family/admission role → two full ledgers + comparator/exclusion evidence → filter/quality/rights → exact current/family contribution → dual-channel status → v3 handoff。
- `STATE-001`: shortlisted → identity_frozen → ledger_complete → quality_audited → family_contribution_audited → continuous_ready/fixed_history_ready/probation/blocked/excluded/reserve；失败不得跳过中间证据或回写生产状态。
- `risk_sensitive_invariants`: `INV-001`至`INV-006`、双通道不混用、HF LFS 与 remote URL 权威分离、full ledger、quality-first、exact-only、family dedupe、rights/publication 隔离和 current baseline no-drift。
- `inapplicable_faces_with_reason`: 本任务不写数据库、对象存储、外部仓库、registry、Canonical 或 public 状态，因此无生产事务/认证/并发写；重复执行要求相同 fixed inputs 产生相同 fixed-core ledgers、counts、digests、family mapping 和 status。time-bound remote observations 可变化，但不得改变无 immutable authority 的阻断。

# 5. 当前证据与目标差异

- `FACT-001`: `config/sources-v1.yaml` 当前有 6 个 active 来源；TASK-0021 live evidence 固定 1513 cases、1930 outputs、2260 source files、1885 asset objects、0 real public，v2 `adapter_ready_batch=[]`。
- `FACT-002`: 现有 `scripts/validate_phase2_source_expansion_admission.py` 已实现 fixed Git、case/asset ledger、quality sample、remote observation、current exact sets、deterministic digest 和 protected baseline 校验，但以 v2 schema/TASK-0021/三个旧候选为固定合同；v3 必须复用已验证能力而不是覆盖 v2 证据。
- `FACT-003`: 2026-08-10 Hugging Face API 返回 Goku dataset revision `c4e79e9e11b3e754ec64f6400c7f94de6a5f103d`、28296 个 siblings、`lastModified=2026-08-03T07:50:54Z`、dataset card license `cc-by-4.0`；Dataset Viewer `preview=true` 但 `viewer/search/filter/statistics=false`，`size` endpoint 无可用行数，因此执行不能依赖 Viewer 分页作为全量权威。
- `ASM-001`: seed observation：Goku fixed dataset 曾观察到约 16759 条精确 gpt-image-2 records、22756 outputs 和 28293 个版本化图片文件；存在少量缺 sourceLink、弱 Prompt、重复 Prompt 和资产异常。执行必须从 fixed revision 直接重算，不能把 seed 数字写为结果。
- `FACT-004`: tigerowo repo ID `1284712193`，2026-07-25 current seed Commit `60e9c65baecfd6d6d51ac4e4d87f146af834bb64`；官方 data file seed 为 926 records，tree seed 为 1233 image blobs，且存在 README/record 数量差、缺 `image_dir`/`tweet_url`/`case_anchor` 和 category 漂移。README 自述其为 EvoLinkAI backup，GitHub metadata 不是 fork；`reports/source-audit-v1.md` 已将其 `family_mapping` 判为 blocked。本轮比较调研进一步支持备份/镜像特征、重复和数据不一致，因此不再为其承担 full audit 成本。
- `FACT-005`: Chaos repo ID `1219036815`、default branch `main`、未归档；2026-04-23 至 04-24 集中提交，current seed Commit `5296db8c996e38776c83a0bc8c64f848dcd512b3`，repository size 约 2.1 GB，当前 license history 指向 MIT。单次提交规模不证明案例数或质量。
- `ASM-002`: seed observation：Chaos 曾观察到约 3798 个 gpt-image-2 records、443 themes、结构化 meta 和本地图片；比较调研保守估计约 1223 条可进入后续人工复核，内容质量和独立性较高但缺持续增长。执行必须从 fixed revision 完整重算，不能把 1223 写成最终准入结果。
- `FACT-006`: YouMind repo ID `1218575008`，default branch `main`，README 表示 twice-daily references update；2026-08-10 seed Commit `d654184a667bcc8b96ae973494e638ad5b970d0d`。仓库主要是搜索/Skill 与 references 数据，README license 为 MIT package claim，不能代表聚合 Prompt/图片权利。
- `ASM-003`: seed observation：YouMind 曾观察到约 14724 个结构化图文记录，图片主要位于 CMS，约 68% 需要参考图，作者/原帖暴露不足；执行必须重算并与 Goku/Atlas 做 family overlap。
- `FACT-007`: 2026-08-10 比较调研在其固定观察输入上发现 Goku 与 YouMind 至少 10097 条 Prompt 完全相同；该结果足以确认两者不能作为独立新增来源累计，但 v3 执行仍必须从记录中的 fixed revisions 重算精确交集和 digest。
- `current_execution_path`: 维护者只能从 v2 empty batch 和内部预览看到现有六源，无法获得 Goku/Chaos 的双通道 eligibility、filtered corpus、Goku/YouMind family dedupe 和 next Adapter handoff，也缺少 tigerowo 不应再次进入候选池的 durable exclusion record。
- `target_delta`: 新增 v3 machine report/schema/validator/tests/中文报告/handoff 并更新 `1.md`；v2 和生产消费者保持只读。
- `evidence_gaps`: Goku/Chaos current fixed revisions、完整结构/资产账、HF LFS OID 覆盖、质量与 exclusion samples、Goku/YouMind/Atlas family overlap、当前 1513 exact overlap、真实独立贡献、双通道状态、tigerowo exclusion freshness 和 handoff。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `reports/phase2/source-expansion-admission-v3.md`
  - `reports/phase2/source-expansion-admission-v3.json`
  - `schemas/phase2-source-expansion-admission-v3.schema.json`
  - `scripts/validate_phase2_source_expansion_admission_v3.py`
  - `tests/phase2/test_source_expansion_admission_v3.py`
  - `docs/phase2/source-expansion-admission-v3.md`
  - `1.md`
  - 如避免复制 v2 引擎确有必要，可新增一个只服务 admission validator 的 cohesive helper module 及对应测试；不得因此修改生产 ingestion/apps/content 或改变 v2 输出。
  - 本卡正式 execution evidence/sidecar，位于 canonical run root，不计入产品文件。
- `hard_protected_scope`: TASK-0021 v2 六项证据与测试、全部 v1 evidence、`config/sources-v1.yaml`、`reports/source-audit-v1.*`、production ingestion/adapters/inventory/sync/content/apps/migrations、Canonical/fixtures、现有 tasks/history；外部仓库/HF 只读。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、current 6-source 生产计数、0-public、rights/publication fail-closed、v2 empty batch、fixed_history 不进入 scheduler、exact-only 不写 Canonical。
- `authorization_limits`: 本任务卡只授权仓库内调查证据和文档实现；不授权外部写入、长期镜像、第三方媒体再分发、生产数据写入、来源激活、真实 rights 决策、部署或公开发布。
- `stop_if_scope_expands`: 若完成需要修改 production Adapter/registry/database/API/Web、创建持久第三方图片仓、改变 v2 合同、执行 near-duplicate canonical merge、接受新的法律风险或把 fixed_history 接入 scheduler，停止并修订任务卡。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: 当前维护者通过 v2 validator/report 得到旧三候选 empty batch；目标入口是 v3 validator CLI，输入 current six-source production evidence、Goku/Chaos fixed full inputs、YouMind fixed comparator input 与 tigerowo fixed exclusion evidence，输出 v3 JSON/MD/handoff；最终消费者只能是后续 Adapter 或 one-shot fixed-history import 任务。
- `expected_touchpoints_or_search_anchors`: v2 admission validator 的 fixed Git/ledger/quality/exact/determinism helpers；GitHub fixed tree/data parsers；HF Hub dataset API、`metadata.jsonl` 和 LFS tree metadata；current internal-preview production rebuild；v3 report/schema/test/docs/`1.md`。优先复用已有 helper，不复制整份 v2 validator；具体 helper 文件边界由执行前 bounded layout decision 决定。
- `wiring_to_final_consumer`: v3 `adapter_ready_batch` 每项必须携带下一任务可直接消费的 source ID、fixed revision、ingestion mode、structure strategy、case scope、family role、asset authority 和 exclusions；不在 batch 的来源不能由后续任务自行升级。
- `failure_and_recovery`: 所有 clone/metadata/sample 下载使用 workspace 外 task runtime root；revision/asset/network failure产生 bounded non-ready evidence；重复运行清理临时目录并重建 fixed-core；remote observations 与 deterministic core 分离；失败不得留下外部媒体或修改生产状态。
- `implementation_freedom`: 满足目标、双通道合同、v2 保护、全量 ledger、质量/family/exact 边界和验收时，parser 组织、缓存方式、并发度与局部算法由执行者选择。
- `selected_profile_obligations`:
  - `investigation`: 固定问题、候选集合、竞争状态、可复核证据和下一 Adapter 决策 handoff。
  - `external-boundary`: 明确 GitHub/HF/CDN 合同、timeout/retry、限流/失败、临时数据清理、凭据与第三方数据不入库。
  - `public-contract`: v3 JSON Schema、runtime semantic validator、Markdown/handoff 和下游 batch consumer 必须等价；v2 compatibility 不变。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-003`, `REQ-011`至`REQ-016`, `INV-001`, `INV-002`
- `owns_behavior`: 固定 Goku/Chaos 的完整 identity/revision/tree/content history，固定 YouMind comparator 与 tigerowo exclusion control 的必要输入，并形成 family/admission-role map 与 continuous/fixed_history eligibility inputs。
- `target_delta`: 从未分角色的四源候选调查，收敛为两个 full candidates、一个 comparator、一个 exclusion control 的固定输入合同；任何控制源都不能进入后续 full ledger 或 ready 路径。
- `business result`: 任何后续计数都绑定可复核 fixed revision，自动更新时间戳和镜像关系不会制造虚假活跃度或独立来源数。
- `behavior_faces`: normal=fixed identity/history；boundary=HF dataset 与普通 Git、continuous 与 static；failure=revision/metadata/history 不可访问；empty=来源无可识别内容；repeated=相同 revision 产生相同 identity/tree digest；downstream=TASK-002 只能消费成功冻结项。permission N/A：外部只读。
- `state_change`: shortlist → identity_frozen/fail-closed；失败仅记录状态，不回写外部或生产。
- `data_flow`: GitHub/HF authority → fixed revision/tree/history → family/maintenance facts → TASK-002/003。
- `integration_edges`: current v2 evidence/read-only source facts → v3 identity layer → ledger parser and dual-channel classifier。
- `expected_touchpoints`: v3 validator identity/history layer；官方 GitHub/HF APIs；workspace 外 snapshots。
- `scope_boundary`: 不按 README/HEAD/Stars 判定；不修改 v2/registry。
- `allowed_write_scope`: v3 validator/tests/report JSON；workspace 外 runtime evidence。
- `linked_tests`: `TEST-001`
- `stop_conditions`: repository identity 冲突、revision 非 40 位 commit、家族 authority 无法区分或需要新的范围来源时停止。

### TASK-002
- `links`: `OBJ-001`, `REQ-004`至`REQ-007`, `REQ-013`至`REQ-016`, `INV-003`, `INV-006`
- `owns_behavior`: 为 Goku 与 Chaos 建立全量 case/asset/orphan/filter ledger，为 YouMind 建立 family comparator ledger，并为 tigerowo 建立最小 exclusion record；严格区分 Git bytes、HF LFS OID 和 remote observation。
- `target_delta`: 新增两个可重算 full ledgers、一个限定用途 comparator ledger 和一个 bounded exclusion record；删除对 tigerowo full ledger/质量抽样的旧执行意图。
- `business result`: 每个有效或排除案例都能追溯 Prompt、来源、输出与资产权威；5GB+ HF 数据无需盲目全量下载也不能被写成已解码。
- `behavior_faces`: normal=两个 full candidates 的强配对与完整资产账；boundary=multi-output、LFS、translated/legacy rows、reference images、comparator/exclusion evidence depth；failure=unsafe/missing/bad asset、missing OID/source、orphan、tigerowo 排除证据冲突；empty=filtered corpus 为空；repeated=ledger/digest 稳定；downstream=TASK-003 只消费 authority-valid full ledgers 和 bounded control evidence。permission N/A。
- `state_change`: identity_frozen → ledger_complete/probation/blocked；失败不生成 ready 指标。
- `data_flow`: fixed metadata/tree/assets → normalized case ledger + asset ledger + exclusions → quality/contribution。
- `integration_edges`: TASK-001 fixed authority → candidate parsers → TASK-003 quality/family contribution。
- `expected_touchpoints`: v3 candidate parsers、path/media/LFS validators、complete tree reconciliation、unit mutations。
- `scope_boundary`: 不保存第三方图片；不把 remote availability 当 fixed authority；不改 Prompt。
- `allowed_write_scope`: v3 validator/schema/tests/report JSON；workspace 外 sample/runtime。
- `linked_tests`: `TEST-002`
- `stop_conditions`: strong pairing 需要人工猜测、LFS authority 无法完整枚举、或完成需新增长期存储时停止并记录后续依赖。

### TASK-003
- `links`: `OBJ-001`, `REQ-007`至`REQ-012`, `REQ-017`, `INV-002`至`INV-005`
- `owns_behavior`: 执行全量 lint、准入/排除视觉样本、within-source/current/family exact dedupe，并按双通道门槛生成真实状态与 batch。
- `target_delta`: 从 raw 大规模数量转为 Goku family-unique continuous eligibility 与 Chaos fixed-history eligibility；batch 只接受来源与 mode 精确匹配的通过项。
- `business result`: 高风险与低质量内容不能被大规模数量掩盖；Goku/YouMind 聚合内容不重复计数；静态高质量源只进入 fixed_history；YouMind/tigerowo 不会越权进入 batch。
- `behavior_faces`: normal=Goku/Chaos filtered eligible set 通过；boundary=部分排除、Goku/YouMind 全 family overlap、static source；failure=质量样本失败、source/asset/risk 缺证据、远程 authority、control source 被错误升级；empty=真实空 batch；repeated=fixed-core counts/digests/status 稳定；downstream=TASK-004 和下一 Adapter 只消费 batch。permission=rights remains review_required。
- `state_change`: ledger_complete → quality/family audited → continuous_ready/fixed_history_ready/probation/blocked/excluded/reserve。
- `data_flow`: ledger + current 1513 exact sets + family evidence + visual results → contribution waterfall/status/batch。
- `integration_edges`: TASK-002 ledgers → quality/exact classifier → TASK-004 schema/report/handoff。
- `expected_touchpoints`: risk lint、sample selector、exact normalization、family waterfall、dual-channel threshold validator。
- `scope_boundary`: 不做 semantic near-duplicate merge；不写 Canonical/rights/publication；不降低门槛。
- `allowed_write_scope`: v3 validator/schema/tests/report JSON；workspace 外 visual sample evidence。
- `linked_tests`: `TEST-003`
- `stop_conditions`: 分类需要未授权法律判断、近似自动归组或改变 production 数据时停止。

### TASK-004
- `links`: `OBJ-001`, `REQ-017`, `REQ-018`, `INV-001`至`INV-006`
- `owns_behavior`: 生成 Schema/runtime 等价的 v3 machine report、中文报告、Adapter handoff 和 `1.md` 状态，并证明 protected baseline/no-drift。
- `target_delta`: 新增唯一 v3 durable handoff，把两条准入主线及两个控制角色固化为机器可验证合同，同时保持 v1/v2/production/public 消费者不变。
- `business result`: 下一任务获得唯一、可验证的 ready 输入；未通过项不会因 Markdown、README 或人工选择被偷偷升级。
- `behavior_faces`: normal=cross-file 一致；boundary=batch 为空或含两种 mode；failure=Schema/runtime/report drift、protected hash drift；empty=明确写出无 ready 项；repeated=canonical digest 稳定；downstream=后续 Adapter/one-shot task。permission=不激活来源。
- `state_change`: audited → handoff_ready；不改变 production state。
- `data_flow`: v3 fixed-core result → JSON/Schema/MD/handoff/`1.md` → next task consumer。
- `integration_edges`: TASK-003 status/batch → durable artifacts → protected consumer check。
- `expected_touchpoints`: seven v3 product files、cross-file semantic checks、current production rebuild、repository hygiene。
- `scope_boundary`: v1/v2/production files只读；不创建 Adapter 或 registry diff。
- `allowed_write_scope`: 第 6 节 v3 七项产品文件。
- `linked_tests`: `TEST-004`
- `stop_conditions`: 任何文档要求宣称已接入/已公开或结果需要改 protected scope 时停止。

### ASSEMBLY-001
- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`
- `end_to_end_entry`: v3 validator CLI 对 current baseline、Goku/Chaos 两个 fixed full candidates、YouMind comparator 与 tigerowo exclusion control 执行 build/live validate。
- `shared_contract_state_data`: `FLOW-001`、`STATE-001`、`REQ-010`至`REQ-018`、`INV-001`至`INV-006`；共同数据对象为 fixed authority inputs、full/comparator/exclusion ledgers、quality/contribution waterfall、dual-channel status 和 `adapter_ready_batch`。
- `final_consumer`: v3 `adapter_ready_batch` 和中文 handoff；后续任务不得绕过。
- `cross_task_failure_path`: 任一 identity/ledger/quality/family/role/Schema/protected check 失败即对应 full candidate non-ready、控制源维持非 ready 或全任务失败；不得用下游文档补写绕过上游失败，workspace 外临时资源必须清理，生产状态不变。
- `linked_test_evidence_gate`: `TEST-004` / `EV-004` / `GATE-004`。

# 9. 验证与验收

- `consumer_chain_validation`: `TEST-004` 必须从真实 v3 CLI 入口验证 fixed inputs → identity/admission role → ledgers → quality/family contribution → status/batch → JSON/Schema/Markdown/handoff → 后续任务消费边界，并证明 YouMind/tigerowo 无法成为 batch consumer input。
- `real_integration_evidence`: 使用官方 fixed revisions 的 live build、HF LFS/Git 真实样本解码、current six-source production rebuild、重复 fixed-core determinism、cross-file batch 一致性和 protected hashes 共同形成 `EV-004`；纯 unit/schema 或 README 检查不能替代。

### RISK-001
- `description`: 大规模聚合库可用 raw count、镜像或缺 provenance 内容制造虚假独立价值。

### RISK-002
- `description`: Goku 5GB+ HF/LFS 若盲目 clone 会造成不必要磁盘/时间成本；若只看 metadata 又可能虚报资产可解码。

### RISK-003
- `description`: filtered subcorpus 可被滥用为人工挑好案例而隐藏失败项。

### RISK-004
- `description`: continuous 与 fixed_history 语义混用会让静态来源进入 scheduler、让高质量历史库被活跃度误杀或让来源与 mode 错配。

### RISK-005
- `description`: repository/package license 被错误解释为第三方 Prompt/图片 public rights。

### RISK-006
- `description`: v3 修改或复用方式导致 TASK-0021 v2、current 1513/1930 或 public consumer 漂移。

### RISK-007
- `description`: admission role 漂移导致 YouMind/tigerowo 被错误升级、重复计数或承担无价值的 full audit，偏离质量与独立贡献优先的用户决策。

### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-003`, `REQ-011`至`REQ-016`, `RISK-001`, `RISK-004`, `RISK-007`
- `method`: 从官方 GitHub/HF authority 固定 Goku/Chaos 完整 repository/dataset ID、default branch、revision、tree/file manifest 与 content-level history，并固定 YouMind comparator 与 tigerowo exclusion control 的必要 identity/revision/evidence；mutations 覆盖 moving HEAD、timestamp-only、mirror-as-canonical、control-as-ready、static-as-continuous 和 missing revision。
- `expected_observable_result`: 两个 full、一个 comparator、一个 exclusion control 的角色与输入完整；所有后续 evidence 绑定对应 fixed revision；family role、admission role 和 dual-channel maintenance facts 可重算。
- `failure_path_covered`: repo/revision drift、API failure、假活跃、家族冲突、静态源误分类。
- `cannot_prove`: case quality、asset decodability、legal rights。

### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: per-source authority URL/ID/branch/revision/tree digest、content-history dates/deltas、family matrix、failure classifications 和 fixed input manifest。

### TEST-002
- `links`: `TASK-002`, `REQ-004`至`REQ-007`, `REQ-013`至`REQ-016`, `RISK-002`, `RISK-003`
- `method`: candidate-specific parsers重算 Goku/Chaos 全部 records/references/files；Git assets逐文件校验，HF LFS完整核对 path/OID/size 并下载确定性 media sample；YouMind 重算 comparator 所需 records/Prompt hashes/reference-image 边界；tigerowo 仅验证 exclusion record；所有 orphan/exclusion/multi-output/reference-image/control-role 路径执行正负 mutations。
- `expected_observable_result`: 两个 full candidates 的 raw→authority-valid→filtered counts与ledger一致；Git/HF/remote authority不混淆；所有 full 引用和 orphan 有终端状态；YouMind/tigerowo 没有伪造 full-ledger 或 ready 结果。
- `failure_path_covered`: missing/unsafe path、bad magic、missing LFS OID/object、weak pairing、orphan、duplicate ID、README count drift、remote-only image。
- `cannot_prove`: full-corpus semantic quality、future Hub/CDN availability、legal rights。

### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: Goku/Chaos complete case/asset/orphan/exclusion ledgers与digests、YouMind comparator ledger/digest、tigerowo exclusion record、authority algorithm/version、Git SHA-256 rows、HF LFS path/OID/size rows、sample download/decode results和count arithmetic。

### TEST-003
- `links`: `TASK-003`, `REQ-007`至`REQ-012`, `REQ-017`, `RISK-001`, `RISK-003`至`RISK-005`, `RISK-007`
- `method`: 对 Goku/Chaos 执行 full machine lint、确定性准入样本与排除样本逐项视觉/语义审查；重算 current/Goku/Chaos/Goku-YouMind-Atlas exact URL/Prompt/fixed-image waterfall；threshold/status/batch mutations验证 Goku-only continuous、Chaos-only fixed_history、control-source non-ready 和 rights fail-closed。
- `expected_observable_result`: Goku/Chaos quality/risk/filter证据覆盖全库；unique contribution不重复计算聚合家族；Goku 只有满足 continuous 全部门槛才可 ready，Chaos 只有满足 fixed_history 全部门槛才可 ready，YouMind/tigerowo 始终不在 batch。
- `failure_path_covered`: comfort-only sample、漏 exclusion、near-duplicate 自动 merge、remote bytes overlap、static-as-continuous、license-as-rights、强制非空 batch。
- `cannot_prove`: 法律授权、未来质量、后续 Adapter 正确性。

### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: Goku/Chaos lint/version与全量 IDs/counts、admission/exclusion sample formula/IDs/digest/per-item results、exact normalization/version、Goku/YouMind/Atlas family与current contribution waterfall、control-role matrix、rights matrix、source-to-mode decision trace和negative mutations。

### TEST-004
- `links`: `ASSEMBLY-001`, `TASK-004`, `OBJ-001`, `REQ-017`, `REQ-018`, `RISK-006`
- `method`: offline Schema/unit/mutation tests；live fixed-revision build；重复 fixed-core determinism；重建 current six-source production；交叉校验 JSON/Schema/MD/handoff/`1.md`/batch；检查 v1/v2/protected hashes 与 repository hygiene。
- `expected_observable_result`: v3 artifacts一致，下一任务只能消费真实batch；current 1513/1930/2260/1885/0-public和v2 empty batch不变；临时第三方数据不留在workspace。
- `failure_path_covered`: Schema/parser drift、report mismatch、batch越权、protected drift、temp/cache residue、live result与fixed core不一致。
- `cannot_prove`: Adapter/同步/公开发布已实现或外部来源未来持续可用。

### EV-004
- `for`: `TEST-004`
- `required_evidence_shape`: offline/live formal receipts、fixed-core digest repetition、current baseline receipt、cross-file matrix、protected hashes、hygiene manifest、independent semantic review和Completion Report。

### 正式 Validator Manifest

```json
{"schema_version":1,"validators":[
  {"validator_id":"phase2-large-source-admission-v3-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q","tests/phase2/test_source_expansion_admission_v3.py"],"cwd":".","timeout_seconds":900,"invalidation_paths":["reports/phase2/source-expansion-admission-v3.md","reports/phase2/source-expansion-admission-v3.json","schemas/phase2-source-expansion-admission-v3.schema.json","scripts/validate_phase2_source_expansion_admission_v3.py","tests/phase2/test_source_expansion_admission_v3.py","docs/phase2/source-expansion-admission-v3.md","1.md","config/sources-v1.yaml","reports/source-audit-v1.json","reports/phase2/source-expansion-admission-v2.json","scripts/validate_phase2_source_expansion_admission.py"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"phase2-large-source-admission-v3-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase2_source_expansion_admission_v3.py","--audit","reports/phase2/source-expansion-admission-v3.json","--schema","schemas/phase2-source-expansion-admission-v3.schema.json","--live","--determinism-check","--json"],"cwd":".","timeout_seconds":7200,"invalidation_paths":["reports/phase2/source-expansion-admission-v3.md","reports/phase2/source-expansion-admission-v3.json","schemas/phase2-source-expansion-admission-v3.schema.json","scripts/validate_phase2_source_expansion_admission_v3.py","tests/phase2/test_source_expansion_admission_v3.py","docs/phase2/source-expansion-admission-v3.md","1.md","config/sources-v1.yaml","reports/source-audit-v1.json","reports/phase2/source-discovery-v1.json","reports/phase2/source-expansion-admission-v2.json","docs/phase2/source-expansion-admission-v2.md","scripts/validate_phase2_source_expansion_admission.py","scripts/validate_phase2_adapters.py","apps/internal_preview/repository.py","ingestion"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | fixed identity/family/mode inputs | OBJ-001 / TASK-001 / TEST-001 | 两个full、一个comparator、一个exclusion control范围完整，revision/tree/history/family/admission role可重算，假活跃和控制源不越权 | EV-001 | 不证明内容质量 |
| GATE-002 | full ledger/asset authority | OBJ-001 / TASK-002 / TEST-002 | Goku/Chaos full ledgers、YouMind comparator ledger与tigerowo exclusion record完整；Git/LFS/remote权威分离且无silent omission | EV-002 | 不证明全库视觉质量/legal rights |
| GATE-003 | quality/contribution/dual channel | OBJ-001 / TASK-003 / TEST-003 | Goku/Chaos full lint、双样本、family/current exact waterfall闭合；batch只允许Goku-continuous或Chaos-fixed_history且允许为空 | EV-003 | 不证明Adapter已实现 |
| GATE-004 | integrated v3 handoff/no drift | OBJ-001 / TASK-004 / ASSEMBLY-001 / TEST-004 | v3 cross-file一致；current baseline、v1/v2、production/public不变；正式证据闭合 | EV-004 | 不证明未来来源可用或公开权利 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `reports/phase2/source-expansion-admission-v3.md`
  - `reports/phase2/source-expansion-admission-v3.json`
  - `schemas/phase2-source-expansion-admission-v3.schema.json`
  - `scripts/validate_phase2_source_expansion_admission_v3.py`
  - `tests/phase2/test_source_expansion_admission_v3.py`
  - `docs/phase2/source-expansion-admission-v3.md`
  - `1.md`
- `documentation_impact`: updated；新增 v3 大规模来源、family dedupe、filtered corpus 和 continuous/fixed_history handoff，并在 `1.md` 记录真实结果；不得写成来源已接入或已公开。
- `repository_hygiene_requirement`: 只保留本卡授权的 v3 产品文件和必要的单一 cohesive helper；所有 clone、HF metadata/LFS samples、第三方图片、HTTP responses、temporary DB、quality samples、cache 位于 workspace 外 canonical runtime/evidence root；不得保留 `.venv`、`__pycache__`、`.pytest_cache`、node_modules、候选 clone、媒体副本或 credentials。
- `external_review`: policy=never；reason=本任务为只读外部调查和本地共享合同证据，不执行外部写入、生产状态变化或法律批准；L3 independent semantic review、live fixed-revision evidence、Schema/runtime equivalence、failure mutations和consumer-chain检查足够。
- `non_completion_rules`:
  - Goku/Chaos 两个 full candidates、YouMind comparator 或 tigerowo exclusion control 任一静默遗漏或角色漂移时不得完成。
  - Goku/Chaos 任一 full candidate 缺 fixed revision、完整 ledger、asset authority、orphan/exclusion账、质量/来源/family/contribution或deterministic digest时不得完成。
  - HF LFS 未完整枚举却写成全量资产通过，或未下载样本写成已解码时不得完成。
  - remote/CMS 当前可读被写为 immutable authority，或 YouMind/tigerowo 进入 ready batch 时不得完成。
  - filtered subcorpus 缺 raw账、exclusion IDs/reasons/digest，或人工只挑好案例时不得完成。
  - Goku/YouMind/Atlas 聚合内容被重复计算独立贡献，或 tigerowo/EvoLink lineage/exclusion 证据被忽略时不得完成。
  - tigerowo 被执行 full ledger/质量准入或被升级为 candidate，而未先因新证据修订任务卡时不得完成。
  - Chaos 因静态被直接排除而未评估 fixed_history，或被错误写为 continuous/scheduler-ready时不得完成。
  - 上游 license/SFW/approved 被解释为 real public rights，或真实 public count 不再为0时不得完成。
  - 为凑数量降低门槛、强制非空 batch、执行 near-duplicate auto merge、修改 Canonical/Content/registry/Adapter 时不得完成。
  - v1/v2证据、current 1513/1930/2260/1885、production/public consumers或protected scope发生drift时不得完成。
  - 两项formal validators、documentation/hygiene、L3 independent semantic review、final freshness和唯一Completion Report任一未闭合时不得完成。

本卡完成只表示产生了第三批来源准入 v3 和可消费 handoff；不表示任何来源已成为 active、已导入 inventory、已接入 scheduler、已取得真实公开权利或已出现在公共页面。
