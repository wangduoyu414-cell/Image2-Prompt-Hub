---
task_contract_version: 3
card_id: "TASK-0007"
title: "正式复验并闭环 JoeSai 双来源切片"
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
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`:
  - 用户目标模式授权：沿已确认方向持续推进并为每个阶段产生可验证交付物与正式 Completion Report。
  - `D:/image2/1.md`、`config/sources-v1.yaml`、`reports/source-audit-v1.json` 与 TASK-0001/0002 已冻结的来源和内容合同。
  - TASK-0003/0005 已完成的 g0dam extraction 与通用私有库存边界。
  - `D:/image2/tasks/TASK-0006-joesai-markdown-adapter-and-multi-source-inventory.md` 的业务目标、实现边界与 Validator 声明。
  - TASK-0006 blocked run `C:/Users/admin/.codex/task-state/image2/TASK-0006-831b3d84a199b8d7`：两项正式 Validator 已通过，独立只读审查未发现实现缺陷；唯一 blocker 是任务卡把 `source-files/prompts/**` 写成必交产物，而正式工具按字面路径校验。
  - 当前 `D:/image2` 中 TASK-0006 已冻结实现及文档；本卡只建立新的、可满足的形式权威与新鲜验证，不复用 TASK-0006 receipt。
- `decision_owner`: 用户拥有业务目标、风险和发布边界的最终决定权；执行者只能按本卡复验并正式收口，不能借此扩展功能。
- `material_unknowns`:
  - GitHub、Docker、PostgreSQL 或 S3-compatible service 在本次 fresh live run 时仍可能暂时不可用；历史 TASK-0006 pass 不得替代本次证据。
  - 本卡预期不修改仓库。如果新鲜验证或独立复核发现实现缺陷，必须如实阻断并另建 remediation task，不得在本卡静默扩张为新实现任务。
  - live Validator 当前显式绑定外部 runtime `C:/Users/admin/.codex/runtime/image2/TASK-0006`；复用的是依赖缓存/脚本约定，不是旧 receipt、旧 Docker 状态、旧 package 或旧数据库。

# 2. 业务目标

- `actor`: 项目协调者、后续第三 pilot 实施者与 Completion Report 消费者。
- `workflow_and_trigger`: TASK-0006 的实现和真实双来源验证均已完成，但其 formal completion 被一个不可满足的 deliverable glob 声明阻断；需要新的精确任务卡重新建立完整、独立、可审计的完成链。
- `single_outcome`: 在不改变当前实现的前提下，以精确文件级必交产物清单重新冻结候选，fresh 运行 JoeSai/g0dam 离线与真实双来源 live Validators，完成 L4 独立语义审查、文档/卫生/新鲜度检查和 `complete` Completion Report，使 JoeSai 第二 pilot 正式闭环。
- `observable_results`:
  - `RESULT-001`: 24 个必交文件均按真实文件路径存在、可哈希、无 glob、无目录枚举歧义。
  - `RESULT-002`: 新 TASK-0007 receipt 证明离线 ingestion/package tests 全部通过，不引用 TASK-0006 receipt。
  - `RESULT-003`: 新 TASK-0007 live receipt 重新完成 g0dam 100 + JoeSai 50 固定 Commit 提取、JoeSai failure/concurrency、同一隔离 PostgreSQL/S3 双来源导入、150 object download hashes、双包 verified_existing、rights/publication fail-closed 和清理。
  - `RESULT-004`: 当前仓库候选在本卡执行期间无生产文件变化，protected scopes 未触碰，文档状态保持已同步，工作区无缓存/运行产物。
  - `RESULT-005`: deterministic evidence、L4 independent review、terminal freshness 与 Completion Report 全部绑定本卡 hash、TASK-0007 canonical run 和本次 fresh receipts；终态为 COMPLETE。
- `non_goals`:
  - 不新增、修改或重构 Adapter、pipeline、inventory、tests、fixtures、Validator 或文档。
  - 不修改 TASK-0006 卡或其 blocked run，不伪造 `**` 路径，不把旧 blocked report 改成 complete。
  - 不复用 TASK-0006 claims、operations、receipts、candidate cycle、independent review 或 Completion Report 作为本卡通过证据。
  - 不实现 ConardLi、同步调度、Canonical、rights review、publication、API 或网页。
  - 不修改 registry/audit、TASK-0002 contracts、inventory migrations/security/transactions 或历史任务卡。

# 3. 需求质疑与确认

- `user_statement`: 按确定好的方向一直执行，保持严谨、持续和可验证。
- `REQ-001` (`required_behavior`): acquire 独立 TASK-0007 canonical run，task card hash、writer、candidate cycle 和 receipts 必须与 TASK-0006 完全分离。
- `REQ-002` (`required_behavior`): base/candidate/final workspace snapshots 必须证明本卡没有仓库内容变化；若出现变化即停止，不得把本卡转为隐式实现任务。
- `REQ-003` (`required_behavior`): 必交产物只使用 `# 10` 中 24 个精确文件路径；不得包含 glob、目录或动态展开规则。
- `REQ-004` (`required_behavior`): fresh offline Validator 必须实际运行卡内命令并产生新 receipt；期望覆盖 shared dispatch、JoeSai strict parser、g0dam compatibility、package consumer 和 symlink边界测试。
- `REQ-005` (`required_behavior`): fresh live Validator 必须实际创建新的随机 Compose project、临时 Git/package/DB/S3 状态并完成全部四个 Gate；历史 stdout 不得复制或导入。
- `REQ-006` (`required_behavior`): live 结果必须再次精确闭合：g0dam 100 case、JoeSai 50 case、2 projects/revisions/runs、150 cases/prompts/GE/outputs/pairings/rights、202 source files、150 assets/objects、0 inputs/parse errors。
- `REQ-007` (`required_behavior`): 两来源 package schema 必须分别保持 g0dam legacy 与 JoeSai neutral；两个 fixed aggregate、两次独立提取和同键 replay 必须一致。
- `REQ-008` (`required_behavior`): JoeSai 五个 extraction failure points、same-key `run_locked`、两包 inventory `verified_existing`、全部 150 object download hashes 和 Compose/runtime cleanup 必须再次通过。
- `REQ-009` (`required_behavior`): registry snapshots 必须保持 `auto_publish=false` 与 prompt/asset `review_required`，库存 rights 保持 unknown，不能出现 publication/visibility/mirror_allowed 决策。
- `REQ-010` (`required_behavior`): 文档 impact 记录为 none，理由是 TASK-0006 已同步三份权威文档且本卡无行为变化；仍需正式检查文档引用和 final hashes。
- `REQ-011` (`required_behavior`): L4 independent review 必须独立检查 Adapter dispatch、Markdown/manifest/image/symlink、package schema/idempotency、双来源 inventory、rights/publication、formal receipts 和 final freshness。
- `REQ-012` (`required_behavior`): Completion Report 必须以 execution_status=complete 通过 schema 与 freshness 验证，required deliverables 24/24、required validators 2/2、remaining blockers 为空。
- `INV-001`: TASK-0006 blocked run 是历史事实，只能作为问题来源与已实现候选背景，不能授权本卡通过。
- `INV-002`: 本卡验证的仓库 bytes 必须与 acquire 时基线完全一致；任何代码/测试/fixture/doc变化均使本卡不再适用。
- `INV-003`: TASK-0007 formal evidence 只能引用自己的 run-root receipts/reviews/report；源代码证据可引用当前 repo 文件。
- `INV-004`: g0dam legacy稳定身份和 JoeSai neutral package identity 不变。
- `INV-005`: fixed source、strong pairing、content hash、source domain、private inventory 和 rights/publication fail-closed 不变。
- `INV-006`: external venv/cache 可复用，但 live run 的 packages、Git worktrees、Compose project、DB、bucket/object state 必须新建并清理。
- `material_ambiguities`:
  - TASK-0006 独立审查建议“声明真实 prompts directory 或支持的 glob”。由于 `D:/image2` 不是 Git repository，formal report 对 directory deliverable 也不能安全枚举，因此本卡选择逐文件显式声明。
  - 本卡 `work_kind=report` 表示正式复验/收口，不表示弱化行为验收；L4 风险和两个真实 Validators 保持不变。
- `decisions_and_authority`:
  - 不更改 TASK-0006 authority；新 task id 是唯一正规修复路径。
  - 发现实现缺陷时本卡 fail closed，后续另建代码任务；本卡没有修复授权。

# 4. 业务场景与规则

- `SCN-001` 主路径: 当前候选不变，24 files存在，两项 fresh Validators、独立审查和 report 全部通过，run COMPLETE。
- `SCN-002` 交付物缺失/漂移: 任一精确文件不存在或 candidate/final hash变化；立即阻断。
- `SCN-003` offline失败: 测试失败或旧 receipt 被误引用；不得进入完成。
- `SCN-004` live环境失败: Git/Docker/DB/S3 当前不可用；真实 validation pending/failed，不使用 TASK-0006 pass。
- `SCN-005` live行为漂移: case/count/hash/schema/failure/concurrency/replay/rights/cleanup 任一不匹配；阻断并另建 remediation。
- `SCN-006` formal证据错误: claim/cycle/card/hash/freshness不一致或 Completion Report 有 blocker；不得 complete。
- `RULE-001`: 本卡只读仓库；正式 run state、receipts、reviews 和 report 写入 `C:/Users/admin/.codex/task-state/image2/TASK-0007-*`。
- `RULE-002`: 两个 Validator 命令必须来自本卡 manifest，且都在同一冻结 candidate cycle 上通过。
- `RULE-003`: TASK-0006 receipts只能用于解释为何新建本卡，不能进入 required validator coverage。
- `RULE-004`: required deliverables 是精确文件，不用 wildcard、directory或“等价文件”替代。
- `RULE-005`: live 使用随机隔离资源，只清理自身 labels/resources。
- `RULE-006`: no workspace change、documentation none、hygiene passed、protected scope passed 和 terminal freshness 是 complete 的共同前提。
- `RULE-007`: independent review 不得把“TASK-0006曾通过”当本卡结论，必须读取本卡 fresh receipts。
- `STATE-001`: `PRECHECK → DISCOVER_AND_PLAN → IMPLEMENT_AND_DEVELOPMENT_CHECKS（只读基线检查）→ FREEZE_CANDIDATE → RUN_FORMAL_VALIDATIONS → CHECK_DOCUMENTATION_AND_HYGIENE → INDEPENDENT_CHECK → FINALIZE`。
- `FLOW-001`: `current frozen repo → exact deliverable coverage → fresh offline/live receipts → documentation/hygiene/freshness → L4 review → complete report`。
- `risk_sensitive_invariants`:
  - 本卡是在修复 formal authority，而不是绕过 TASK-0006 blocker；receipt/candidate隔离必须真实。
  - 无代码 diff 不能降低验证强度；最终消费者仍依赖真实双来源端到端 evidence。
  - 任何隐藏修改都会让“formal adoption”失真，因此 no-change 是硬性不变量。
- `inapplicable_faces_with_reason`:
  - 实现/修复：未授权；发现缺陷另建任务。
  - Git commit：工作区不是 Git repository，且本卡不修改文件。
  - API/UI/publication/sync：超出当前 formal closure。

# 5. 当前证据与目标差异

- `FACT-001`: TASK-0006 run 已正式 BLOCKED/FINALIZE，Completion Report schema validation通过，唯一 blocker 是 literal `source-files/prompts/**`。
- `FACT-002`: TASK-0006 formal offline receipt 为 44 passed；formal live receipt记录100+50 cases、150 objects、2 projects/revisions/runs、202 source files、五故障点、run_locked、双 verified_existing 和 cleanup。
- `FACT-003`: TASK-0006 independent blocked notes 明确“未确认其他 source-adapter、package、concurrency、security、inventory integration 或 hygiene 缺陷”。
- `FACT-004`: 当前 workspace 保留该 frozen candidate，未因 blocked 收口而修改实现。
- `ASM-001`: 本次 fresh Git/Docker/DB/S3 环境预期可用；不可用时只报告真实状态。
- `current_execution_path`: 业务实现已存在，但没有一份 deliverable declaration可满足且 execution_status=complete 的正式报告。
- `target_delta`: 新 canonical run、精确 deliverables、fresh receipts、完整 independent review 和 complete report。
- `evidence_gaps`:
  - 尚无 TASK-0007 base/candidate/final no-change snapshots。
  - 尚无 TASK-0007 fresh validator receipts。
  - 尚无 TASK-0007 semantic review 和 complete Completion Report。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `C:/Users/admin/.codex/task-state/image2/TASK-0007-*/**`，仅正式生命周期证据。
  - `C:/Users/admin/.codex/runtime/image2/TASK-0006/**`，仅既有 validator 的外部依赖缓存和本次自动清理的临时 live state。
- `hard_protected_scope`:
  - `D:/image2/**` 全部仓库内容，包括当前24个deliverables。
  - `C:/Users/admin/.codex/task-state/image2/TASK-0001-*` 至 `TASK-0006-*`。
  - 用户其他 Docker containers/networks/volumes、其他 runtime/task-state。
- `protected_contracts_and_invariants`: 当前 workspace bytes、registry/audit、TASK-0002 contracts、g0dam legacy identity、JoeSai neutral identity、inventory security/transaction、rights/publication fail-closed。
- `authorization_limits`: 本卡只授权 read-only verification 和 TASK-0007 evidence writes；不授权仓库修改、外部发布或旧 evidence改写。
- `stop_if_scope_expands`:
  - 任何 repo file需要修改。
  - 任何 Validator需要修改才能通过。
  - 需要绕过、复用或手工伪造 formal receipt/review/report。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: current repo candidate → formal runner → exact deliverable checker → offline/live Validators → independent check → Completion Report。
- `expected_touchpoints_or_search_anchors`: task card hash、base/candidate/final snapshots、24 deliverable files、two validator receipts、documentation/hygiene/freshness artifacts、semantic review、completion report。
- `wiring_to_final_consumer`: COMPLETE report 将成为后续 ConardLi task 的第二 pilot prerequisite；源代码行为仍由当前 extraction/inventory 路径提供。
- `failure_and_recovery`: 任一失败保持 workspace不变并将run真实阻断；不在本卡修复。
- `implementation_freedom`: 可选择只读检查和 evidence组织细节，但不能改变命令、deliverables、候选bytes或风险边界。
- `selected_profile_obligations`:
  - public-contract: fresh验证legacy/neutral schema与TASK-0002输出闭合。
  - external-boundary: fresh Git/Docker/DB/S3、全部hash和cleanup。
  - stateful-runtime: canonical run/candidate/claims/receipts/freshness/report一致。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `REQ-001` 至 `REQ-003`, `INV-001` 至 `INV-003`
- `owns_behavior`: acquire独立run、no-change snapshots和24-file精确覆盖。
- `target_delta`: 消除TASK-0006 deliverable authority缺陷，不修改candidate。
- `integration_edges`: task card → snapshots → deliverable coverage。
- `expected_touchpoints`: current repo与TASK-0007 run-root。
- `linked_tests`: `TEST-001`
- `stop_conditions`: 任一repo byte变化或deliverable缺失。

### TASK-002

- `links`: `REQ-004` 至 `REQ-009`, `INV-004` 至 `INV-006`
- `owns_behavior`: fresh offline和live全量行为证据。
- `target_delta`: 以TASK-0007 authority重建2/2 formal receipts。
- `integration_edges`: frozen candidate → pytest / two-source live assembly。
- `expected_touchpoints`: validator commands与external runtime only。
- `linked_tests`: `TEST-002`, `TEST-003`
- `stop_conditions`: 任一行为/环境 Gate未通过。

### TASK-003

- `links`: `REQ-010` 至 `REQ-012`
- `owns_behavior`: documentation none、hygiene、freshness、independent review与complete report。
- `target_delta`: 形成无blocker终态。
- `integration_edges`: candidate+receipts → evidence bundle/review/report。
- `expected_touchpoints`: TASK-0007 run-root only。
- `linked_tests`: `TEST-004`
- `stop_conditions`: evidence不新鲜、不独立或report不能complete。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`
- `end_to_end_entry`: TASK-0007 formal lifecycle。
- `shared_contract_state_data`: card hash、workspace snapshot、deliverable hashes、candidate cycle、validator receipts、Git/DB/S3 evidence、review/report refs。
- `final_consumer`: 第三 pilot task与后续 Phase 1 publication/API/web slices。
- `cross_task_failure_path`: 任一前置Gate失败时不生成complete report，workspace保持原样。
- `linked_test_evidence_gate`: `TEST-001` 至 `TEST-004` / `EV-001` 至 `EV-004` / `GATE-001` 至 `GATE-004`

# 9. 验证与验收

- `consumer_chain_validation`: 必须以当前 frozen repo 重新证明 fixed source → extraction package → existing private inventory → per-run/global inspect 的双来源完整消费者链；TASK-0006 历史 receipt 不替代本卡 fresh evidence。
- `real_integration_evidence`: live 使用公开固定 Commit、完整 100+50 case/image、真实 PostgreSQL/S3 containers、150 object downloads 和随机隔离 Compose project；mock 或旧 stdout 不可接受。
- `failure_recovery_ownership_validation`: 当前 Adapter、pipeline、importer、DB/S3 owner不变；本卡用 JoeSai五故障点、same-key lock、双包replay和cleanup重新证明没有遗漏或并列 owner，且本卡自身不修改实现。

### RISK-001

- `links`: `REQ-001`, `REQ-003`, `TEST-001`
- `description`: 通过修改旧卡、伪造路径或复用旧receipt绕过TASK-0006 blocker。
- `mitigation`: 新task id/hash/run、24 explicit files、旧run hard protected。

### RISK-002

- `links`: `REQ-002`, `INV-002`, `TEST-001`, `TEST-004`
- `description`: formal adoption期间发生隐藏repo修改，使验证对象与TASK-0006 candidate不再相同。
- `mitigation`: base/candidate/final no-change snapshots与terminal freshness。

### RISK-003

- `links`: `REQ-004` 至 `REQ-009`, `TEST-002`, `TEST-003`
- `description`: 历史pass掩盖当前环境或实现回归。
- `mitigation`: fresh receipts、new Compose project/temp state、current fixed Commit/full objects。

### RISK-004

- `links`: `REQ-011`, `REQ-012`, `TEST-004`
- `description`: report结构通过但缺失业务闭环、独立性或新鲜度。
- `mitigation`: deterministic integrity、L4 semantic review、2/2 receipt coverage、24/24 deliverable coverage、no blockers。

### TEST-001

- `links`: `TASK-001`, `REQ-001` 至 `REQ-003`, `RISK-001`, `RISK-002`
- `method`: acquire后记录base snapshot；逐一验证24个精确文件存在并可哈希；冻结candidate与final snapshot，比较repo file set/hash完全不变；检查旧TASK-0006 run/card只读。
- `expected_observable_result`: 24/24存在，0 repo changes，0 protected violations。
- `failure_path_covered`: missing deliverable、glob/dir歧义、hidden mutation、old evidence rewrite。
- `cannot_prove`: 不证明运行行为。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: card/hash/run identity、24 deliverable refs/hashes、snapshot comparisons、protected scope结果。

### TEST-002

- `links`: `TASK-002`, `REQ-004`, `RISK-003`
- `method`: 执行正式 offline manifest命令并保存TASK-0007 receipt。
- `expected_observable_result`: ingestion与package tests全部通过，expected outputs/strict negatives/symlink/legacy兼容闭合。
- `failure_path_covered`: parser/dispatch/schema/package离线回归。
- `cannot_prove`: 不证明真实Git/DB/S3。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: current command/preflight、exit 0、pytest pass count、candidate/card/cycle绑定。

### TEST-003

- `links`: `TASK-002`, `REQ-005` 至 `REQ-009`, `RISK-003`
- `method`: 执行正式live manifest命令，fresh建立固定Commit提取和随机Compose inventory。
- `expected_observable_result`: 100+50 cases、202 source files、150关系/objects、5 failures、run_locked、2 verified_existing、rights/publication fail-closed、cleanup全部通过。
- `failure_path_covered`: real source drift、legacy/neutral schema、concurrency、idempotency、cross-source persistence、object integrity、environment cleanup。
- `cannot_prove`: 不证明生产环境、未来Commit或第三来源。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: new receipt/stdout、Commit/schema/digest/counts、150 download hashes、failure/concurrency/replay、Docker digests和cleanup。

### TEST-004

- `links`: `TASK-003`, `REQ-010` 至 `REQ-012`, `RISK-002`, `RISK-004`
- `method`: documentation/hygiene检查后创建terminal freshness、deterministic bundle和L4 independent review；构建并验证complete Completion Report。
- `expected_observable_result`: documentation none有理由、hygiene/protected/freshness通过、independent findings=0、2/2 validators、24/24 deliverables、blockers=0、run COMPLETE。
- `failure_path_covered`: stale receipt、scope drift、missing evidence、false report completion。
- `cannot_prove`: 不证明未声明的后续产品功能。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: documentation/hygiene/freshness artifacts、deterministic integrity、semantic review、completion report + validation、terminal run-state。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "joesai-multi-source-offline",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "tests/ingestion",
        "tests/inventory/test_package.py",
        "-q"
      ],
      "cwd": ".",
      "timeout_seconds": 300,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "reports/source-audit-v1.json",
        "schemas/adapter-output-v1.schema.json",
        "schemas/generation-example-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "inventory/package.py",
        "tests/ingestion",
        "tests/inventory/test_package.py",
        "fixtures/adapters/g0dam-work-prompts",
        "fixtures/adapters/joesai-commercial-prompts",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/inventory/internal-inventory-v1.md"
      ],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "-c",
        "import pytest, jsonschema, psycopg, boto3; print('ready')"
      ],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "joesai-multi-source-compose-live",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "scripts/validate_joesai_multi_source.py",
        "--registry",
        "config/sources-v1.yaml",
        "--audit",
        "reports/source-audit-v1.json",
        "--g0dam-source-id",
        "g0dam-work-prompts",
        "--g0dam-expected-commit",
        "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "--g0dam-expected-cases",
        "100",
        "--g0dam-expected-aggregate",
        "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0",
        "--joesai-source-id",
        "joesai-commercial-prompts",
        "--joesai-expected-commit",
        "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b",
        "--joesai-expected-cases",
        "50",
        "--joesai-expected-aggregate",
        "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293",
        "--runs",
        "2",
        "--failure-injection",
        "--concurrency",
        "--json"
      ],
      "cwd": ".",
      "timeout_seconds": 2400,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "reports/source-audit-v1.json",
        ".task-runs/TASK-0001",
        "schemas/adapter-output-v1.schema.json",
        "schemas/generation-example-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "inventory",
        "migrations",
        "compose.yaml",
        "scripts/validate_joesai_multi_source.py",
        "fixtures/adapters/g0dam-work-prompts",
        "fixtures/adapters/joesai-commercial-prompts",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/inventory/internal-inventory-v1.md"
      ],
      "validation_kind": "behavior",
      "environment_sensitive": true,
      "preflight_command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "-c",
        "import psycopg, boto3, jsonschema; print('python-ready')"
      ],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | 独立authority与精确交付物 | `TASK-001` / `TEST-001` | 新run、24/24 files、repo no-change、旧run只读 | `EV-001` | 不证明行为 |
| `GATE-002` | fresh offline | `TASK-002` / `TEST-002` | 新receipt、全部tests通过 | `EV-002` | 不证明外部系统 |
| `GATE-003` | fresh双来源live | `TASK-002` / `TEST-003` | 100+50/150 objects/全部Gate/cleanup通过 | `EV-003` | 不证明生产环境 |
| `GATE-004` | 独立复核与complete报告 | `TASK-003` / `ASSEMBLY-001` / `TEST-004` | docs/hygiene/freshness/review/report全部通过且无blocker | `EV-004` | 不证明后续功能 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `ingestion/adapters/base.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/adapters/g0dam.py`
  - `ingestion/adapters/joesai.py`
  - `ingestion/registry.py`
  - `ingestion/pipeline.py`
  - `ingestion/contracts.py`
  - `tests/ingestion/test_joesai_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `tests/ingestion/test_g0dam_adapter.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `tests/inventory/test_package.py`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-adapter-output.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-generation-examples.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-metrics.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/data/prompts.sample.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/README.md`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/beauty/beauty-campaign-kv-editorial.md`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/hospitality/boutique-hotel-lobby-editorial.md`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/jewelry/luxury-jewelry-campaign.md`
  - `scripts/validate_joesai_multi_source.py`
  - `docs/ingestion/joesai-extraction-v1.md`
  - `docs/ingestion/g0dam-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`

### 必交产物

- `ingestion/adapters/base.py`
- `ingestion/adapters/__init__.py`
- `ingestion/adapters/g0dam.py`
- `ingestion/adapters/joesai.py`
- `ingestion/registry.py`
- `ingestion/pipeline.py`
- `ingestion/contracts.py`
- `tests/ingestion/test_joesai_adapter.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `tests/ingestion/test_g0dam_adapter.py`
- `tests/ingestion/test_registry_and_snapshot.py`
- `tests/inventory/test_package.py`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-adapter-output.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-generation-examples.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-metrics.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/data/prompts.sample.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/README.md`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/beauty/beauty-campaign-kv-editorial.md`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/hospitality/boutique-hotel-lobby-editorial.md`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/jewelry/luxury-jewelry-campaign.md`
- `scripts/validate_joesai_multi_source.py`
- `docs/ingestion/joesai-extraction-v1.md`
- `docs/ingestion/g0dam-extraction-v1.md`
- `docs/inventory/internal-inventory-v1.md`

### 完成与回写规则

- `documentation_impact`: none
- `documentation_impact_reason`: 本卡不改变行为或文档；TASK-0006 candidate 已同步 JoeSai extraction、g0dam compatibility 和 multi-source inventory 文档，正式检查只需确认这些文档仍存在且与候选hash一致。
- `repository_hygiene_requirement`:
  - `D:/image2` 0 changes；不得产生 `.venv`、`__pycache__`、`.pytest_cache`、下载仓库、package、images、DB/S3数据、env、credentials或logs。
  - formal run写入 `C:/Users/admin/.codex/task-state/image2/TASK-0007-*`；validator的venv/cache/tmp继续使用 `C:/Users/admin/.codex/runtime/image2/TASK-0006`，live临时状态和Docker资源必须清理。
  - TASK-0001至TASK-0006 state/card/history只读。
  - 当前不是Git repository，不要求commit。
- `external_review`: policy=never；reason=要求L4独立语义审查与真实双来源integration，不需额外外部模型复核。
- `non_completion_rules`:
  - repo出现任何修改、24 files任一缺失、protected scope触碰时不得完成。
  - 任一正式 Validator未在TASK-0007新candidate上fresh通过时不得完成。
  - 复用TASK-0006 receipt/review/report或修改其证据时不得完成。
  - live缺100+50 fixed cases、202 source files、150 objects/download hashes、failure/concurrency/replay/rights/cleanup任一证据时不得完成。
  - documentation/hygiene/freshness/deterministic integrity/L4 independent review任一未通过时不得完成。
  - Completion Report不是complete、24/24 deliverables或2/2 validators未闭合、remaining blockers非空时不得完成。
  - 需要任何代码/测试/fixture/doc修复时停止并创建remediation task。

执行时 `CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2`；formal Validator环境继续使用 `UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0006/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0006/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0006/tmp` 与 `PYTHONDONTWRITEBYTECODE=1`。TASK-0007必须产生自己的canonical run、candidate、receipts、L4 review和complete report。
