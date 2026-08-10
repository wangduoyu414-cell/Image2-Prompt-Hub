---
task_contract_version: 3
card_id: "TASK-0010"
title: "正式复验并闭环三来源 Phase 1 pilot"
status: "ready"
work_kind: "report"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "external-boundary"
  - "stateful-runtime"
  - "configuration"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`:
  - 用户持续执行授权：沿 `D:/image2/1.md` 与已确认的固定高价值来源方向继续推进，先完成 Phase 1 三来源纵向验证闭环，再进入发布/API、最小网页和 Commit 更新同步。
  - `D:/image2/1.md`、`config/sources-v1.yaml`、`reports/source-audit-v1.json` 与 TASK-0001/0002 已冻结的来源、权利、配对和 Generation Example 合同。
  - TASK-0003、TASK-0005、TASK-0007 已正式完成的 g0dam、通用私有库存和 JoeSai 两来源闭环。
  - `D:/image2/tasks/TASK-0009-corrected-conardli-contract-and-three-source-closure.md` 与其当前 workspace 实现、fixture、测试、文档；TASK-0009 candidate 3 offline formal receipt 已通过，但 live O1 operation 在启动后因协调窗口中断而没有与该 operation 严格绑定的 terminal receipt。
  - TASK-0009 canonical run `C:/Users/admin/.codex/task-state/image2/TASK-0009-e593a3831512ada1` 已诚实标记 `BLOCKED`；旧 claim/operation/card/receipts/blocker ledger 必须只读保留，不能手工删除、改写、降级风险或视为本卡通过证据。
  - 协调方于 2026-08-08 只读确认旧 runner identity 已消失、child PID 已被复用且 start token 不同；TASK-0009 runtime 中没有旧 live run directory，Docker 中没有名称匹配 `task0009` 的 container、volume 或 network。该对账只证明未发现残留资源，不证明旧 live operation 成功或失败。
- `decision_owner`: 用户拥有业务目标、发布边界和风险决定权；执行者仅复验并正式收口当前三来源实现，不得扩展到发布、API、网页、同步或新来源。
- `material_unknowns`:
  - fresh live run 时 GitHub、Docker、PostgreSQL 或 S3-compatible service 仍可能不可用；必须记录真实失败或 pending，不得复用 TASK-0009 历史 live 输出。
  - 本卡预期不修改仓库。如果 fresh 验证或独立审查发现实现缺陷，必须阻断并另建 remediation task，不得在本卡静默扩张为代码修复。
  - `scripts/validate_three_pilot_sources.py` 当前固定使用外部 runtime `C:/Users/admin/.codex/runtime/image2/TASK-0009`；本卡仅复用其 venv/cache/tmp 位置，fresh Git/package/Compose/DB/S3 状态仍必须随机新建并清理，TASK-0010 formal evidence 必须写入独立 canonical run root。

# 2. 业务目标

- `actor`: 项目协调者、后续发布/API实施者与 Completion Report 消费者。
- `workflow_and_trigger`: 三来源代码和文档已完成，candidate 2 曾产生完整 live pass，candidate 3 offline formal receipt 已通过；但 candidate 3 live operation 因中断缺少可采信 terminal receipt，TASK-0009 不能合法完成。需要以新任务 ID、全新 authority 和 fresh receipts 重新验证当前不变候选。
- `single_outcome`: 在不修改当前仓库内容、不触碰 TASK-0009 retained claim/operation 的前提下，fresh 运行三来源 offline 与真实 Compose live Validators，完成文档/卫生/新鲜度、L4 独立语义复核和 schema-valid Completion Report，使 g0dam 100 + JoeSai 50 + ConardLi 162 共 312 个内部案例的 Phase 1 pilot 正式闭环。
- `observable_results`:
  - `RESULT-001`: TASK-0010 canonical run、candidate、receipts、review 和 report 与 TASK-0009 完全分离；旧 blocked evidence 未修改、未导入、未被计为通过。
  - `RESULT-002`: fresh offline receipt 证明当前 strict adapters、shared snapshot safety、Generation Example/package consumer、legacy compatibility 和负向测试全部通过。
  - `RESULT-003`: fresh live receipt 证明三个固定 Commit 各提取两次并闭合 100/50/162 cases、固定 aggregates、ConardLi 五故障点和 same-key concurrency。
  - `RESULT-004`: 同一随机隔离 PostgreSQL/S3 中闭合 3 projects/revisions/runs、528 source files、312 cases/prompts/Generation Examples/outputs/pairings/rights、asset/object hash union、download hash verification、三包 replay `verified_existing`。
  - `RESULT-005`: source claims、rights 和 publication 继续 fail closed；随机 Compose、临时 Git/worktree/package/DB/S3、locks、credentials 和 runtime run directory均被清理。
  - `RESULT-006`: 当前 workspace 从 base 到 final 无生产内容变化，22 个精确交付文件、文档、hygiene、deterministic evidence、L4 semantic review、freshness 和 Completion Report 全部闭合，run 终态为 COMPLETE。
- `non_goals`:
  - 不修改 TASK-0009 card、run-state、claim、operation、receipts、blockers 或历史 evidence；不尝试伪造或推断旧 live 结果。
  - 不新增、修改或重构 Adapter、pipeline、inventory、tests、fixtures、Validator、schema、migration、registry、audit 或文档。
  - 不执行上游应用、Node、skill 或依赖，只读取固定 Commit 静态数据和媒体。
  - 不把内部库存等同公开目录，不提升 prompt/asset rights，不新增 publication decision 字段。
  - 不实现 rights review、publication、API、网页、调度、Commit update、增量同步或更多来源。

# 3. 需求质疑与确认

- `user_statement`: 按确定方向持续执行，严谨完成剩余任务；真实阻点必须保留，不能通过删状态或降低标准绕过。
- `REQ-001` (`required_behavior`): acquire 独立 TASK-0010 canonical run；task hash、writer、candidate cycle、claims、operations、receipts、review 和 report 不得复用 TASK-0009。
- `REQ-002` (`required_behavior`): TASK-0009 blocked run 和 retained O1 state 只读保护；本卡不对旧 operation 做 reconciliation、release、replay 或 outcome 推断。
- `REQ-003` (`required_behavior`): 在 freeze 前和 live 后分别只读审计名称匹配 `task0009`/本次随机 project 的 Docker container、volume、network 与 runtime run directories；发现残留或未知外部状态时不得完成。
- `REQ-004` (`required_behavior`): base、candidate 和 final workspace snapshots 必须证明除本任务卡在执行前已存在外，本卡执行期间仓库 bytes 不变；发现实现缺陷或漂移时停止并创建 remediation，不在本卡修复。
- `REQ-005` (`required_behavior`): fresh offline Validator 必须实际执行本卡 manifest 命令并生成 TASK-0010 receipt；不得引用 TASK-0009 offline receipt 替代。
- `REQ-006` (`required_behavior`): fresh live Validator 必须新建随机 Compose project、loopback-only ports、fresh Git/package/DB/S3 状态，完整执行两个 extraction runs per source、故障注入、并发、导入、下载、replay、rights/publication 和 cleanup。
- `REQ-007` (`required_behavior`): fixed source identities和aggregates保持：g0dam `690c2d...c3fe`/100/`ba7dbf...f0`，JoeSai `6f9b01...a9b`/50/`ea242f...293`，ConardLi `971b67...e99`/162/`36d03d...573`。
- `REQ-008` (`required_behavior`): global counts必须闭合为528 source files和312 source cases/versions/prompts/Generation Examples/outputs/pairings/rights；0 inputs、0 parse errors；assets/objects按三份 ImportPlan content-hash union计算并全部download hash复核。
- `REQ-009` (`required_behavior`): 三包 replay均为 `verified_existing` 且DB/S3不增长；g0dam 100 source claims保持`source_claimed`，JoeSai50+ConardLi162保持`unknown`；312 rights保持unknown；registry snapshots保持review_required/auto_publish=false。
- `REQ-010` (`required_behavior`): ConardLi五个控制故障不得改变上一发布包，same-key第二写者必须`run_locked`，所有 source-specific 和 shared safety/error semantics保持现状。
- `REQ-011` (`required_behavior`): 本卡 documentation impact为none；执行者仍需确认 `1.md`、三来源 extraction docs、internal inventory docs 与当前实现/验证结果一致。
- `REQ-012` (`required_behavior`): L4 independent semantic review必须检查固定来源、strict parsing、newline authority、mapping/files、legacy compatibility、package/idempotency、DB/S3 counts、rights/publication、failure/concurrency、cleanup、formal receipts 和 final freshness。
- `REQ-013` (`required_behavior`): Completion Report必须以 execution_status=complete通过官方 schema/freshness验证，required validators 2/2、required deliverables 22/22、remaining blockers为空；否则保持真实非完成状态。
- `INV-001`: TASK-0009 blocked历史是不可改写事实；旧 candidate2 live pass和candidate3 offline pass只能解释为何值得重验，不能证明本卡完成。
- `INV-002`: 本卡验证的仓库 bytes从base到final必须不变；任何代码/fixture/test/doc变化使本卡不再适用。
- `INV-003`: 上游仅固定Commit静态读取，不install/build/import/execute其代码。
- `INV-004`: g0dam legacy、JoeSai neutral和ConardLi neutral输出、schemas、errors、counts和pairing不变。
- `INV-005`: package/workspace不保存真实媒体、完整上游、live package、DB/S3状态、credentials、logs或cache。
- `INV-006`: private inventory与rights/publication fail-closed不变，不新增公开决策。
- `material_ambiguities`:
  - 旧 O1 操作结果不可知，但其随机临时状态未发现残留；执行生命周期明确不同 canonical tasks 不共享该 task fence，因此新 TASK-0010 可以在独立 authority 下进行 fresh 验证，而不能修改旧 TASK-0009 证据。
  - 外部 runtime path名称仍含TASK-0009只是现有Validator的依赖环境约定，不是formal authority或旧run复用；本卡要求所有可变 live state fresh、随机、可清理。
- `decisions_and_authority`:
  - 新 task id 是继续总体目标的最小正规路径；TASK-0009 保持 BLOCKED。
  - 本卡是formal adoption/closure，不授权功能修改；发现缺陷时 fail closed并另建任务。

# 4. 业务场景与规则

- `SCN-001` 主路径: 当前候选不变 → orphan precheck清洁 → fresh offline/live receipts → docs/hygiene/review/freshness → complete report。
- `SCN-002` 旧状态隔离: TASK-0009 retained claim继续存在且只读；TASK-0010仍使用独立task key完成，不把旧状态当本卡 fence或receipt。
- `SCN-003` workspace漂移: 任一候选文件改变、缺失或新增运行污染；阻断，不隐式修复。
- `SCN-004` live环境失败: Git/Docker/DB/S3不可用或超时；记录真实失败/pending，不复用旧pass。
- `SCN-005` live行为漂移: count/hash/schema/failure/concurrency/replay/rights/cleanup任一不匹配；阻断并另建remediation。
- `SCN-006` 外部残留: 旧/新Compose、volume、network或runtime run directory残留；清理证据不完整，不得完成。
- `SCN-007` formal证据错误: task/card/cycle/snapshot/receipt/review/report/freshness不一致；不得complete。
- `RULE-001`: 本卡只读仓库；formal evidence只写TASK-0010 canonical run root。
- `RULE-002`: 两个Validator必须来自本卡manifest并在同一冻结candidate cycle上fresh通过。
- `RULE-003`: TASK-0009 receipts/outputs不得进入required validator coverage或本卡Completion Report的pass依据。
- `RULE-004`: live资源随机、loopback-only、最小权限，只清理本次owned资源；禁止输出secret。
- `RULE-005`: counts既用固定期望值校验，也用真实ImportPlan和content-hash union交叉闭合。
- `RULE-006`: internal inventory不包含publication/visibility/auto_publish/mirror_allowed等发布决策。
- `RULE-007`: no workspace change、22 deliverables、documentation none、hygiene、L4 review和terminal freshness共同构成complete前提。
- `STATE-001`: `PRECHECK → DISCOVER_AND_PLAN → IMPLEMENT_AND_DEVELOPMENT_CHECKS（只读基线检查）→ FREEZE_CANDIDATE → RUN_FORMAL_VALIDATIONS → CHECK_DOCUMENTATION_AND_HYGIENE → DETERMINISTIC_EVIDENCE_INTEGRITY → SEMANTIC_INDEPENDENT_REVIEW → FINAL_FRESHNESS → BUILD/VALIDATE_COMPLETION_REPORT → FINALIZE`。
- `FLOW-001`: `current frozen repo → external orphan audit → fresh offline/live proof → documentation/hygiene/freshness → independent review → Completion Report`。
- `risk_sensitive_invariants`:
  - unknown旧结果不能转换成pass/fail；新鲜独立验证是唯一完成依据。
  - 新任务不修改旧任务运行状态，避免破坏审计链。
  - live validator的随机资源和fail-closed cleanup是可重跑安全性的组成部分。
- `inapplicable_faces_with_reason`: UI/permission page state不适用；本卡没有终端用户UI，也不改变访问角色。发布权限边界通过rights/publication fail-closed验证。

# 5. 当前证据与目标差异

- `FACT-001`: 当前仓库已有三来源实现、22个精确交付文件、ConardLi fixture/expected outputs、三来源live validator和同步文档。
- `FACT-002`: TASK-0009 candidate3 offline formal receipt通过；其live O1 operation为RUNNING journal、无terminal receipt，formal run已BLOCKED。
- `FACT-003`: 只读外部审计未发现TASK-0009 Docker container/volume/network或live runtime directory残留；这不证明旧command结果。
- `FACT-004`: execute lifecycle允许不同canonical task使用独立task fence；旧任务证据仍必须只读。
- `ASM-001`: 当前三来源候选与TASK-0009 candidate3 bytes一致；本卡正式base snapshot必须验证，若不一致则本假设失效并停止。
- `current_execution_path`: fixed registry/audit → production Git snapshot → g0dam/JoeSai/ConardLi adapters → assets/Generation Examples/packages → inventory import → PostgreSQL/S3 private inventory → validator JSON result。
- `target_delta`: 不改变执行路径；只补齐独立、fresh、可采信的TASK-0010 formal validation和closure evidence。
- `evidence_gaps`: 缺TASK-0010 fresh offline/live receipts、candidate/final evidence bundle、L4 independent review与complete Completion Report。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - repository: none after this ready card exists；任何仓库内容变化均阻断本卡。
  - external evidence: `C:/Users/admin/.codex/task-state/image2/TASK-0010-*` canonical run only。
  - external runtime: validator-owned随机临时目录、Compose project、DB/S3和Git worktree；必须清理。
- `hard_protected_scope`:
  - TASK-0001至TASK-0009 cards、`.task-runs`、所有旧canonical run/evidence、TASK-0009 retained claim/operation。
  - `config/sources-v1.yaml`、`reports/source-audit-v1.json`、schemas、migrations、production代码、tests、fixtures、docs和dependency files均只读。
  - 用户Docker/Git/环境配置及非本次owned资源。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、三固定Commit/aggregates、16-field ConardLi contract、newline-only reconciliation、528/312 counts、rights/publication fail-closed、idempotent replay和cleanup。
- `authorization_limits`: 任务卡不构成删除旧claim、修改外部权限、公开内容、安装上游依赖或变更生产数据的授权。
- `stop_if_scope_expands`: 需要任何仓库修复、task contract改义、外部残留的非owned破坏性清理、权限变更或发布决策时立即停止并另建任务或请求授权。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal coordinator调用本卡两个Validator；结果由Phase 1 Completion Report消费，随后发布/API任务只依赖TASK-0010 complete，不依赖TASK-0009无终态凭证的旧operation。
- `expected_touchpoints_or_search_anchors`: TASK-0009 task card与run state、22 required deliverables、`scripts/validate_three_pilot_sources.py`、三来源docs、formal run root；全部只读检查。
- `wiring_to_final_consumer`: fresh receipts进入TASK-0010 candidate evidence bundle和semantic review，最终生成唯一official Completion Report；该report作为后续publication/API任务的三来源库存基线。
- `failure_and_recovery`: validator失败或环境不可用则保持non-complete；workspace变化或实现缺陷另建remediation；外部owned资源残留时只清理精确owned目标并重新审计；旧TASK-0009状态永不作为恢复对象。
- `implementation_freedom`: 执行者可选择形式证据文件名和只读审计实现，但不得改变两个Validator声明、仓库内容、保护范围或验收语义。
- `selected_profile_obligations`:
  - `public-contract`: 验证Adapter Output、Generation Example、package schema/metrics和legacy compatibility。
  - `external-boundary`: 验证Git固定版本、Docker/PostgreSQL/S3、timeout/cleanup、loopback和secret边界。
  - `stateful-runtime`: 验证migration/import、counts、replay、concurrency、failure rollback和no-growth。
  - `configuration`: 验证registry/audit固定身份、runtime env约定、rights/publication snapshots和依赖锁。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`至`REQ-013`, `INV-001`至`INV-006`
- `owns_behavior`: 对当前不变三来源候选建立独立TASK-0010 fresh formal proof和complete closure。
- `target_delta`: 从“代码存在但TASK-0009 live结果不可知”变为“TASK-0010两个fresh Validators和完整closure evidence可采信”。
- `integration_edges`: fixed sources → adapters/packages → private inventory → formal evidence → Phase 1 Completion Report。
- `expected_touchpoints`: 本卡、22 required deliverables、formal scripts、TASK-0010 external run root；repository只读。
- `business_result`: 312-case Phase 1 private inventory成为可由后续publication/API任务正式依赖的已验证基线。
- `behavior_faces`: normal=fresh双Validator通过；boundary=100/50/162、528/312和hash union；failure=环境/contract/count/cleanup失败阻断；permission=rights/publication不提升；empty/initial=fresh随机DB/S3从空状态建立；concurrent/repeated=ConardLi run_locked与三包verified_existing；downstream error=无complete report则后续任务不得把Phase 1视为闭合。
- `state_change`: entry=TASK-0010 acquired且workspace与base一致；exit=COMPLETE report；failure=run保持真实non-complete、仓库不变、owned资源清理。
- `data_flow`: 输入为registry/audit/fixed commits/current packages；source of truth为固定Commit+严格contracts；写目标仅随机private DB/S3和formal evidence；消费者为Completion Report及后续publication/API任务。
- `integration_point`: current evidence=production pipeline和live validator已存在；target wiring=两个fresh receipts进入TASK-0010 report；caller=formal coordinator；trigger=本卡执行；callee=offline pytest/live validator；return=receipts/evidence bundle；consumer=Phase 1 closure。
- `scope_boundary`: hard=不改仓库/旧task state/rights/publication；soft=不做后续产品功能和更多来源。
- `allowed_write_scope`: 仅TASK-0010 run root与本次owned临时外部资源。
- `acceptance_scenarios`: `SCN-001`主路径、`SCN-003`workspace漂移、`SCN-004/005`live失败、`SCN-006`残留、`SCN-007`formal错误。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: 任何repository byte变化、需要代码修复、旧TASK-0009状态被修改、外部结果无法判定或protected scope触碰。

- `assembly_not_required_reason`: 本卡只有一个formal adoption行为切片；offline、live和closure是同一TASK的验收层，不是独立产品行为。

# 9. 验证与验收

- `consumer_chain_validation`: fresh fixed-source输入必须经过production snapshot、三个Adapter、Generation Example/package、同一private inventory与Completion Report全链；仅unit fixture或旧receipt不能满足。
- `real_integration_evidence`: 必须由本卡live Validator的新terminal receipt证明真实Git fetch、随机Compose、PostgreSQL/S3导入、312案例、对象下载校验、replay、rights/publication和cleanup。
- `failure_recovery_ownership_validation`: Validator只拥有本次随机project、runtime run directory、Git worktree、DB/S3和locks；失败时由Validator finally与formal process containment清理，执行者前后只读审计；旧TASK-0009 retained state和任何非owned资源不得触碰。

### RISK-001

- `description`: 复用旧receipt或推断旧O1结果会伪造完成；必须fresh TASK-0010 receipts。

### RISK-002

- `description`: live随机外部状态可能部分残留；必须前后审计和owned cleanup。

### RISK-003

- `description`: no-change adoption可能掩盖当前workspace漂移；base/candidate/final snapshots必须一致。

### RISK-004

- `description`: 内部库存被误当公开授权；rights/publication必须继续fail closed。

### TEST-001

- `links`: `TASK-001`, `REQ-001`至`REQ-005`, `RISK-001`, `RISK-003`
- `method`: acquire新canonical run；比较base/candidate；验证22 exact deliverables和旧TASK-0009只读；fresh执行offline validator。
- `expected_observable_result`: TASK-0010独立authority成立，workspace不变，offline新receipt passed，未引用旧receipt。
- `failure_path_covered`: foreign/stale receipt、workspace漂移、deliverable缺失、旧state被改写。
- `cannot_prove`: 不证明真实Git/Docker/DB/S3链路。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: acquisition/precheck、base/candidate snapshots/comparison、22/22 manifest、offline receipt/log、旧TASK-0009 hash/mtime保护证据。

### TEST-002

- `links`: `TASK-001`, `REQ-003`, `REQ-006`至`REQ-010`, `RISK-002`, `RISK-004`
- `method`: 前置orphan audit后fresh执行live validator；检查固定Commit、两次extract、fault/concurrency、同库counts、object downloads、replay、rights/publication和cleanup JSON。
- `expected_observable_result`: 100/50/162、528/312、fixed aggregates、五故障点、run_locked、三replays、hash downloads、fail-closed rights/publication和cleanup全部通过；前后无Docker/runtime残留。
- `failure_path_covered`: Git/Docker/DB/S3不可用、partial run、count/hash漂移、残留资源、secret或publication提升。
- `cannot_prove`: 不证明公开展示许可或后续API/UI。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: pre/post external orphan audit、fresh live receipt/log、validator JSON、operation terminal proof、cleanup和no-secret检查。

### TEST-003

- `links`: `TASK-001`, `REQ-011`至`REQ-013`, `RISK-001`至`RISK-004`
- `method`: documentation impact/hygiene/protected scope、candidate evidence integrity、L4 semantic independent review、final freshness、build和official validate唯一Completion Report。
- `expected_observable_result`: documentation_impact=none且理由成立；workspace无变化/污染；2/2 receipts、22/22 deliverables、review findings=0、remaining blockers=0、report complete。
- `failure_path_covered`: stale evidence、doc drift、false completion、旧TASK receipt混入、final workspace变化。
- `cannot_prove`: 不证明Phase 2功能。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: documentation/hygiene/protected/freshness receipts、deterministic evidence bundle、semantic review、Completion Report与official validation output。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "three-source-formal-adoption-offline",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "tests/ingestion", "tests/inventory/test_package.py", "-q"],
      "cwd": ".",
      "timeout_seconds": 420,
      "invalidation_paths": ["1.md", "config/sources-v1.yaml", "reports/source-audit-v1.json", "schemas/adapter-output-v1.schema.json", "schemas/generation-example-v1.schema.json", "docs/contracts/content-contract-v1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory/package.py", "tests/ingestion", "tests/inventory/test_package.py", "fixtures/adapters/g0dam-work-prompts", "fixtures/adapters/joesai-commercial-prompts", "fixtures/adapters/conardli-gpt-image-2-101", "docs/ingestion/g0dam-extraction-v1.md", "docs/ingestion/joesai-extraction-v1.md", "docs/ingestion/conardli-extraction-v1.md", "docs/inventory/internal-inventory-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import pytest, jsonschema, psycopg, boto3; print('ready')"],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "three-source-formal-adoption-compose-live",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_three_pilot_sources.py", "--registry", "config/sources-v1.yaml", "--audit", "reports/source-audit-v1.json", "--g0dam-source-id", "g0dam-work-prompts", "--g0dam-expected-commit", "690c2d6969a65b406b17ba7d41f18695a652c3fe", "--g0dam-expected-cases", "100", "--g0dam-expected-aggregate", "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0", "--joesai-source-id", "joesai-commercial-prompts", "--joesai-expected-commit", "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b", "--joesai-expected-cases", "50", "--joesai-expected-aggregate", "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293", "--conardli-source-id", "conardli-gpt-image-2-101", "--conardli-expected-commit", "971b67dc8cbca8cf6eb32e196fea04bddd6abe99", "--conardli-expected-cases", "162", "--conardli-expected-aggregate", "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573", "--runs", "2", "--failure-injection", "--concurrency", "--json"],
      "cwd": ".",
      "timeout_seconds": 3600,
      "invalidation_paths": ["1.md", "config/sources-v1.yaml", "reports/source-audit-v1.json", ".task-runs/TASK-0001", "schemas/adapter-output-v1.schema.json", "schemas/generation-example-v1.schema.json", "docs/contracts/content-contract-v1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory", "migrations", "compose.yaml", "scripts/validate_three_pilot_sources.py", "fixtures/adapters/g0dam-work-prompts", "fixtures/adapters/joesai-commercial-prompts", "fixtures/adapters/conardli-gpt-image-2-101", "docs/ingestion/g0dam-extraction-v1.md", "docs/ingestion/joesai-extraction-v1.md", "docs/ingestion/conardli-extraction-v1.md", "docs/inventory/internal-inventory-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": true,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import psycopg, boto3, jsonschema; print('python-ready')"],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | authority/offline | `OBJ-001` / `TASK-001` / `TEST-001` | 独立run、workspace不变、22 files、fresh offline通过 | `EV-001` | 不证明live |
| `GATE-002` | three-source live | `OBJ-001` / `TASK-001` / `TEST-002` | 100/50/162、528/312、hash/fault/concurrency/replay/rights/cleanup闭合 | `EV-002` | 不证明公开授权 |
| `GATE-003` | formal closure | `OBJ-001` / `TASK-001` / `TEST-003` | docs/hygiene/review/freshness/2 receipts/22 deliverables/report完整 | `EV-003` | 不证明后续API/UI/sync |

# 10. 产物与完成回写

- `required_deliverables`:
  - `ingestion/adapters/snapshot_files.py`
  - `ingestion/adapters/conardli.py`
  - `ingestion/adapters/joesai.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/registry.py`
  - `ingestion/contracts.py`
  - `tests/ingestion/test_conardli_adapter.py`
  - `tests/ingestion/test_joesai_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-adapter-output.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-generation-examples.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-metrics.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/src/data/cases.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/_mapping.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/INDEX.md`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/qualitative-comparison-grid/1.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/scientific-schematic/1.txt`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/poster-and-campaigns/banner-hero/3.json`
  - `scripts/validate_three_pilot_sources.py`
  - `docs/ingestion/conardli-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`
- `documentation_impact`: none；本卡不改变行为，TASK-0009已同步ConardLi extraction与三来源inventory文档；仍需验证其与当前候选一致。
- `repository_hygiene_requirement`:
  - repository从base到final无内容变化，无pyc/cache/venv/package/media/log/secret/runtime污染。
  - formal evidence只写`C:/Users/admin/.codex/task-state/image2/TASK-0010-*`；TASK-0009及更早task states只读。
  - runtime复用`C:/Users/admin/.codex/runtime/image2/TASK-0009`的venv/cache/tmp约定；每次live的run directory、Git worktree、Compose/DB/S3必须fresh且清理。
  - D:/image2非Git repo，Completion Report记录`git_commit: not_applicable`并以workspace snapshots/protected evidence证明freshness。
- `external_review`: policy=never；reason=用户未要求外部模型，fresh真实Git/Docker/DB/S3证据与L4 independent semantic review足以闭环。
- `non_completion_rules`:
  - 任一22 deliverables、2 fresh validators、orphan audits、L4 review、freshness或Completion Report缺失不得完成。
  - TASK-0009 retained state被修改、释放、重放或作为本卡pass证据不得完成。
  - repository bytes在本卡执行期间变化不得完成；发现缺陷必须另建remediation。
  - fixedCommit/count/aggregate、ConardLi failure/concurrency、三来源528/312、hash downloads、replays、rights/publication、cleanup任一不闭合不得完成。
  - live环境失败只能真实failed/pending；不得mock、旧receipt、candidate2输出或人工推断替代。
  - workspace或外部owned Docker/Git/runtime资源残留、secret泄漏或非owned状态被改动不得完成。
  - 需要publication/API/web/sync/Commit update或新来源时另建后续任务。

执行时设置 `CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0009/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0009/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0009/tmp`、`PYTHONDONTWRITEBYTECODE=1`。唯一TASK-0010 canonical run必须记录新fresh receipts、external orphan audits、three-source counts/hashes/fault/concurrency/replay/rights/cleanup、documentation/hygiene、semantic review、freshness和Completion Report；不得记录secrets或修改旧TASK状态。
