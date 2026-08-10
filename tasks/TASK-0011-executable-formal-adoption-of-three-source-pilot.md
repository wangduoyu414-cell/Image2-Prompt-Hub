---
task_contract_version: 3
card_id: "TASK-0011"
title: "以可执行交付清单正式闭环三来源 Phase 1 pilot"
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
- `authority_sources`: 用户持续执行授权；`D:/image2/1.md`；TASK-0001/0002/0003/0005/0007完成基线；TASK-0009当前三来源实现与BLOCKED运行事实；TASK-0010语义合同及其PRECHECK兼容性证据。
- `decision_owner`: 用户拥有业务目标、发布边界与风险决定权；执行者只做当前三来源候选的fresh复验和正式收口。
- `material_unknowns`: fresh Git/Docker/PostgreSQL/S3环境可能失败；若实现缺陷或workspace漂移出现，本卡必须阻断并另建remediation，不得扩张为代码修复。
- `successor_reason`: TASK-0010卡内22项位于`required_deliverables`字段列表，v3 ready校验通过，但formal lifecycle只从独立“必交产物 / required deliverables”标题提取路径，得到0项并在PRECHECK正确阻断；本卡仅增加生命周期可解析的显式标题清单，业务目标、零仓库改动范围、两个Validator和验收含义不变。

# 2. 业务目标

- `actor`: 项目协调者、后续publication/API实施者与Completion Report消费者。
- `workflow_and_trigger`: 三来源生产实现、fixtures、tests、docs已存在；TASK-0009因中断的live O1 operation无terminal receipt不能完成，TASK-0010又因交付清单解析兼容性在PRECHECK停止，需要新authority执行fresh验证。
- `single_outcome`: 不改当前仓库内容、不触碰TASK-0009 retained state，以独立TASK-0011 fresh offline/live receipts证明g0dam100+JoeSai50+ConardLi162共312个内部案例完整进入同一private inventory，并完成L4 review、freshness和schema-valid Completion Report。
- `observable_results`:
  - `RESULT-001`: TASK-0011 run/candidate/receipts/review/report与TASK-0009/0010完全分离，旧card/run/evidence只读。
  - `RESULT-002`: formal lifecycle精确提取22个必交文件，coverage为22/22而不是0/0。
  - `RESULT-003`: fresh offline证明strict adapters、shared snapshot safety、Generation Example/package和legacy compatibility通过。
  - `RESULT-004`: fresh live证明三个固定Commit各提取两次、100/50/162、固定aggregates、ConardLi五故障点和same-key concurrency。
  - `RESULT-005`: 同一随机PostgreSQL/S3闭合3 sources、528 source files、312 cases及关系、object hash downloads、三包verified_existing replay、rights/publication fail closed和cleanup。
  - `RESULT-006`: repository从base到final零内容变化，docs/hygiene/deterministic evidence/L4 review/final freshness/report全部通过，run COMPLETE。
- `non_goals`: 不修改代码、tests、fixtures、schema、migration、registry、audit或docs；不修复/释放/重放TASK-0009旧operation；不实现dedupe/taxonomy/publication/API/web/sync/Commit update或更多来源；不公开rights未明确的图片。

# 3. 需求质疑与确认

- `user_statement`: 持续严谨推进剩余任务，不能用删状态、旧结果或降低标准绕过真实阻点。
- `REQ-001` (`required_behavior`): acquire独立TASK-0011 canonical run；不得复用TASK-0009/0010的task key、candidate、claim、operation、receipt、review或report。
- `REQ-002` (`required_behavior`): TASK-0009 card/run/retained claim/operation/receipts/blockers与TASK-0010 blocked run全部只读；旧O1结果不作成功或失败推断。
- `REQ-003` (`required_behavior`): lifecycle必须从本卡`### 必交产物`标题精确解析22条唯一文件路径，全部存在；任何0/0、glob、目录或缺失均阻断。
- `REQ-004` (`required_behavior`): base/candidate/final snapshots证明本卡执行期间repository bytes不变；出现变化或缺陷时另建remediation。
- `REQ-005` (`required_behavior`): fresh offline Validator实际运行本卡命令并生成TASK-0011 passed receipt；旧offline receipt不能替代。
- `REQ-006` (`required_behavior`): fresh live Validator新建随机Compose project、loopback ports、Git/package/DB/S3状态，完整执行两次extraction per source、fault/concurrency、imports、downloads、replays、rights/publication和cleanup。
- `REQ-007` (`required_behavior`): fixed identities保持：g0dam commit `690c2d6969a65b406b17ba7d41f18695a652c3fe`/100/aggregate `ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0`；JoeSai `6f9b01fd21efbc05cfdde1176fc988013d3c4a9b`/50/`ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293`；ConardLi `971b67dc8cbca8cf6eb32e196fea04bddd6abe99`/162/`36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573`。
- `REQ-008` (`required_behavior`): global inventory为528 source files、312 source cases/versions/prompts/Generation Examples/outputs/pairings/rights、0 inputs、0 parse errors；assets/objects按三ImportPlans的content-hash union计算并全部download hash复核。
- `REQ-009` (`required_behavior`): 三包replay均`verified_existing`且DB/S3不增长；g0dam100 source claims为source_claimed，JoeSai50和ConardLi162为unknown evidence state；312 rights保持unknown；registry snapshots保持review_required/auto_publish=false。
- `REQ-010` (`required_behavior`): ConardLi五个failure points不改变上一package；same-key第二writer为`run_locked`；g0dam/JoeSai frozen outputs、schemas与error semantics不变。
- `REQ-011` (`required_behavior`): live前后只读审计TASK-0009和本次owned Docker container/volume/network及runtime run directory；任何残留、survivor或cleanup证据不足不得完成。
- `REQ-012` (`required_behavior`): documentation impact为none但仍检查`1.md`、三来源extraction docs和internal inventory docs与当前行为一致；workspace无pyc/cache/media/package/log/secret污染。
- `REQ-013` (`required_behavior`): L4 independent semantic review检查source authority、strict parse/newline/mapping、legacy compatibility、package/idempotency、DB/S3 counts、rights/publication、failure/concurrency、cleanup、formal evidence和final freshness。
- `REQ-014` (`required_behavior`): 唯一Completion Report必须official validation通过，required validators=2/2、deliverables=22/22、remaining blockers=0、execution_status=complete。
- `INV-001`: 旧blocked任务只提供背景，不提供本卡pass证据。
- `INV-002`: repository在本卡执行期间零内容变化。
- `INV-003`: 上游仅固定Commit静态读取，不执行、构建或安装其代码。
- `INV-004`: 每张输出图仍通过Generation Example绑定确切Prompt与strong pairing evidence。
- `INV-005`: private inventory、content-addressed assets、idempotency与失败回滚不变。
- `INV-006`: rights/publication fail closed，不把unknown/internal-only内容公开。
- `material_ambiguities`: 外部runtime路径仍名为`TASK-0009`，只作为现有Validator的venv/cache/tmp约定；TASK-0011 live的Git/package/Compose/DB/S3必须fresh随机，formal evidence写入TASK-0011 root。
- `decisions_and_authority`: TASK-0011是修正deliverable extractor兼容性的最小正规后继；发现实现问题时本卡fail closed，不修改业务合同。

# 4. 业务场景与规则

- `SCN-001` 主路径: 22 deliverables解析 → orphan precheck清洁 → fresh offline/live → docs/hygiene/review/freshness → complete report。
- `SCN-002` 交付解析: 22/22通过；0/0、重复、glob、directory或missing立即阻断。
- `SCN-003` workspace漂移: 任一repository byte变化阻断，不在本卡修复。
- `SCN-004` live环境或行为失败: Git/Docker/DB/S3不可用，或counts/hashes/fault/replay/rights/cleanup漂移；真实failed/pending，不用旧pass替代。
- `SCN-005` 外部残留: old/new Compose、volume、network、runtime目录或子进程残留；不得完成。
- `SCN-006` formal错误: foreign/stale receipt、snapshot/card/cycle不一致、review/report/freshness不闭合；不得complete。
- `RULE-001`: repository只读，formal evidence仅写TASK-0011 canonical run root。
- `RULE-002`: 两Validator来自本卡manifest并在同一candidate cycle上fresh通过。
- `RULE-003`: fixed expectations与真实ImportPlan/content-hash union双重校验。
- `RULE-004`: live资源随机、loopback-only、最小权限、无secret输出，仅清理精确owned资源。
- `RULE-005`: internal inventory不得包含publication/visibility/auto_publish/mirror_allowed决策字段。
- `RULE-006`: 22 deliverables、2 receipts、no-change、docs/hygiene、L4 review、freshness共同构成complete。
- `STATE-001`: `PRECHECK → DISCOVER_AND_PLAN → IMPLEMENT_AND_DEVELOPMENT_CHECKS(read-only) → FREEZE_CANDIDATE → RUN_FORMAL_VALIDATIONS → CHECK_DOCUMENTATION_AND_HYGIENE → DETERMINISTIC_EVIDENCE_INTEGRITY → SEMANTIC_INDEPENDENT_REVIEW → FINAL_FRESHNESS → BUILD/VALIDATE_COMPLETION_REPORT → FINALIZE`。
- `FLOW-001`: `current frozen repo → exact deliverables → external orphan audit → fresh offline/live → evidence/review/freshness → Completion Report`。
- `risk_sensitive_invariants`: 旧无终态结果不能转成pass；新任务不得修改旧任务状态；外部owned资源完全清理；公开边界继续fail closed。
- `inapplicable_faces_with_reason`: 无UI页面、用户角色或生产发布动作；权限面由rights/publication SQL断言覆盖。

# 5. 当前证据与目标差异

- `FACT-001`: 当前三来源实现和22个文件存在，TASK-0009 candidate3 offline formal receipt通过，但live O1无terminal receipt。
- `FACT-002`: TASK-0010在PRECHECK发现formal deliverable extractor只识别独立标题，0项解析会形成虚假0/0，因此已BLOCKED且未运行Validators。
- `FACT-003`: TASK-0010 pre-audit未发现匹配TASK-0009的Docker/runtime残留；只证明当前未见残留，不证明旧command outcome。
- `ASM-001`: 当前workspace与TASK-0010 acquire时一致；TASK-0011 base snapshot必须验证，否则停止。
- `current_execution_path`: registry/audit/fixed Git snapshot → adapters/assets/Generation Examples/packages → PostgreSQL/S3 private inventory → validator JSON/receipts。
- `target_delta`: 不变更产品执行路径；补齐可执行的22项deliverable authority与fresh TASK-0011 formal closure。
- `evidence_gaps`: TASK-0011 fresh receipts、evidence bundle、semantic review、final freshness和complete report尚未产生。

# 6. 范围与责任边界

- `allowed_write_scope`: repository none；external仅`C:/Users/admin/.codex/task-state/image2/TASK-0011-*`与本次Validator-owned随机临时资源。
- `hard_protected_scope`: TASK-0001至TASK-0010 cards/runs/evidence、TASK-0009 retained state、所有repository生产代码/tests/fixtures/docs/config/schema/migrations/dependencies、用户非owned Docker/Git/environment。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、fixed commits/aggregates、ConardLi16-field与newline-only reconciliation、528/312、replay、rights/publication、cleanup。
- `authorization_limits`: 不授权修改权限、公开内容、删除旧claim、清理非owned外部状态或执行上游代码。
- `stop_if_scope_expands`: 需要repository修复、权限变更、非owned破坏性清理、发布决定或合同改义时停止并另建任务/请求授权。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal coordinator调用本卡offline/live Validators；fresh receipts进入TASK-0011 evidence和Completion Report；后续publication/API任务只依赖TASK-0011 complete。
- `expected_touchpoints_or_search_anchors`: 本卡`### 必交产物`、22 files、two validator declarations、TASK-0009/0010 protected evidence、formal scripts和TASK-0011 run root。
- `wiring_to_final_consumer`: two fresh receipts + deliverable manifest + docs/hygiene + semantic review + final snapshot组成唯一official report，作为Phase1后续Content Core/publication/API的库存基线。
- `failure_and_recovery`: validator或环境失败保持non-complete；workspace变化/实现缺陷另建remediation；owned残留精确清理后重审计；旧任务state不作为恢复对象。
- `implementation_freedom`: 可选择sidecar文件名和只读审计方法；不得改变validator commands、仓库bytes、22项清单、保护范围或验收语义。
- `selected_profile_obligations`:
  - `public-contract`: 验证Adapter Output、Generation Example、package schemas/metrics、legacy compatibility。
  - `external-boundary`: 验证fixed Git、Docker/PostgreSQL/S3、timeout/containment/cleanup、loopback和secret边界。
  - `stateful-runtime`: 验证migration/import/counts/replay/concurrency/failure rollback/no-growth。
  - `configuration`: 验证registry/audit、runtime env、rights/publication snapshots和dependency lock。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`至`REQ-014`, `INV-001`至`INV-006`
- `owns_behavior`: 为当前不变三来源候选建立22项可解析deliverables和独立fresh formal completion。
- `target_delta`: 从“实现存在但旧live结果不可采信且TASK-0010 deliverables为0”变为“22/22、2/2和完整report可采信”。
- `integration_edges`: fixed sources → adapters/packages → private inventory → formal receipts → Completion Report。
- `expected_touchpoints`: 22 files、live validator、formal run root；repository只读。
- `business_result`: 312-case Phase1 private inventory成为后续publication/API可正式依赖的完成基线。
- `behavior_faces`: normal=fresh双Validator；boundary=22/22、100/50/162、528/312；failure=环境/contract/count/cleanup失败；permission=rights不提升；empty=fresh DB/S3；concurrent/repeated=run_locked与verified_existing；downstream error=无complete report则后续不得视为闭环。
- `state_change`: entry=TASK-0011 acquired且base一致；exit=COMPLETE；failure=run非完成、repository不变、owned资源清理。
- `data_flow`: 输入为fixed sources/current repo；source of truth为fixed commits和contracts；写入仅随机private DB/S3与formal evidence；消费者为Completion Report/后续任务。
- `integration_point`: current evidence=production pipeline存在；target wiring=fresh receipts进入TASK-0011 report；caller=formal coordinator；trigger=本卡执行；callee=pytest/live validator；return=evidence；consumer=Phase1 closure。
- `scope_boundary`: hard=不改repo/旧runs/rights；soft=不做后续功能。
- `allowed_write_scope`: TASK-0011 run root和owned随机runtime。
- `acceptance_scenarios`: `SCN-001`至`SCN-006`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: 0/0 deliverables、repo变化、代码缺陷、旧state修改、外部结果不可判定或protected scope触碰。

- `assembly_not_required_reason`: 单一formal adoption行为；offline/live/closure是同一TASK的验证层。

# 9. 验证与验收

- `consumer_chain_validation`: fixed source必须真实经过production snapshot、three adapters、Generation Example/package、同一private inventory和Completion Report；fixture-only、0/0 deliverables或旧receipt均不足。
- `real_integration_evidence`: 本卡live terminal receipt必须证明Git fetch、随机Compose、PostgreSQL/S3、312 cases、object downloads、replays、rights/publication和cleanup。
- `failure_recovery_ownership_validation`: Validator只拥有本次随机project/runtime/Git/DB/S3/locks，finally与formal containment负责清理；执行者前后审计；旧TASK-0009 retained state与非owned资源不得触碰。

### RISK-001
- `description`: deliverable解析失败会让0/0虚假通过；必须22/22。

### RISK-002
- `description`: 旧receipt或旧O1推断会伪造完成；必须fresh TASK-0011 receipts。

### RISK-003
- `description`: live外部状态可能残留；必须前后orphan audit与owned cleanup。

### RISK-004
- `description`: internal inventory可能被误当公开授权；rights/publication必须fail closed。

### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-005`, `RISK-001`, `RISK-002`
- `method`: acquire、22-item extraction/exists/unique、base/candidate no-change、旧state保护、fresh offline validator。
- `expected_observable_result`: 22/22、独立authority、workspace一致、offline新receipt passed。
- `failure_path_covered`: 0/0、missing/duplicate、stale receipt、workspace drift、旧state修改。
- `cannot_prove`: 不证明live。

### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: acquisition/precheck、22-item manifest、base/candidate snapshots、protected hashes、offline receipt/log。

### TEST-002
- `links`: `TASK-001`, `REQ-006`至`REQ-011`, `RISK-003`, `RISK-004`
- `method`: pre-audit后fresh live validator；检查fixed counts/hashes/two runs/fault/concurrency/import/download/replay/rights/cleanup；post-audit。
- `expected_observable_result`: 100/50/162、528/312、fixed aggregates、五failures、run_locked、3 replays、hash downloads、fail-closed rights和clean resources。
- `failure_path_covered`: external unavailable、partial run、count/hash drift、leftovers、secret/publication elevation。
- `cannot_prove`: 不证明公开许可/API/UI。

### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: pre/post orphan audits、live receipt/log/JSON、terminal operation、cleanup/no-secret evidence。

### TEST-003
- `links`: `TASK-001`, `REQ-012`至`REQ-014`, `RISK-001`至`RISK-004`
- `method`: docs/hygiene/protected/candidate integrity、L4 review、final freshness、build+official validate唯一Completion Report。
- `expected_observable_result`: documentation none理由成立；repo无变化污染；2/2、22/22、0 findings、0 blockers、complete report。
- `failure_path_covered`: stale evidence、doc drift、false completion、old receipt混入、final drift。
- `cannot_prove`: 不证明后续功能。

### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: docs/hygiene/protected/freshness、deterministic bundle、semantic review、Completion Report及official validation。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "executable-three-source-adoption-offline",
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
      "validator_id": "executable-three-source-adoption-compose-live",
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
| `GATE-001` | deliverables/offline | `OBJ-001` / `TASK-001` / `TEST-001` | 22/22、独立run、no-change、fresh offline | `EV-001` | 不证明live |
| `GATE-002` | three-source live | `OBJ-001` / `TASK-001` / `TEST-002` | 100/50/162、528/312、fault/concurrency/replay/rights/cleanup | `EV-002` | 不证明公开授权 |
| `GATE-003` | formal closure | `OBJ-001` / `TASK-001` / `TEST-003` | docs/hygiene/review/freshness/2 receipts/22 files/report | `EV-003` | 不证明后续功能 |

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
- `documentation_impact`: none；本卡不改变行为，已有ConardLi extraction和three-source inventory docs与当前实现一致，执行期只做验证。
- `repository_hygiene_requirement`: repository无内容变化和cache/media/package/log/secret污染；formal evidence仅写TASK-0011 root；随机runtime/Compose/Git/DB/S3完全清理；D:/image2非Git repo，report使用workspace snapshots证明freshness并记录git_commit not_applicable。
- `external_review`: policy=never；fresh真实Git/Docker/DB/S3与L4 independent semantic review足以闭环。
- `non_completion_rules`: 22/22、2/2、orphan audits、no-change、docs/hygiene、L4 review、freshness或report任一缺失不得完成；旧TASK状态被修改/复用、live失败被mock/推断、counts/hashes/replay/rights/cleanup不闭合、workspace或owned外部资源残留均不得完成。

### 必交产物

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

执行时设置`CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0009/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0009/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0009/tmp`、`PYTHONDONTWRITEBYTECODE=1`。TASK-0011 run必须记录22/22、fresh two receipts、orphan audits、counts/hashes/fault/concurrency/replay/rights/cleanup、docs/hygiene/review/freshness/report，且不得记录secrets或修改旧task state。
