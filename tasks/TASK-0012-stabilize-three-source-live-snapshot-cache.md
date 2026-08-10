---
task_contract_version: 3
card_id: "TASK-0012"
title: "稳定三来源 live Validator 的固定版本镜像边界"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
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
- `authority_sources`: 用户持续执行授权；`D:/image2/1.md`的持久Git mirror、fixed Commit、失败保留上一版和Phase1纵向闭环；TASK-0011两次明确失败receipts与清理证据。
- `decision_owner`: 用户拥有总体目标和风险边界；执行者只修复three-source live Validator的source snapshot cache/timeout/diagnostic责任，不改变Adapter、inventory或发布合同。
- `material_unknowns`: 首次填充大型ConardLi持久mirror仍依赖当前网络；实现必须提供真实底层错误并安全保留/清理cache状态，不能保证外部网络永不失败。

# 2. 业务目标

- `actor`: formal coordinator、三来源live Validator维护者和后续长期同步实现者。
- `workflow_and_trigger`: TASK-0011 candidate1因g0dam在临时data root全量mirror clone超过90秒失败；唯一重试越过g0dam后，又在ConardLi临时fresh mirror preparation失败。两次均清理正常、workspace不变，说明业务链路没有被证伪，但Validator把持久mirror职责错误放入每次即删的run root，并且包装丢失底层Git错误。
- `single_outcome`: 将three-source live Validator改为使用task-neutral、workspace外的持久source Git cache，启动时以900秒边界依次fresh fetch并固定Commit校验全部三来源，后续extract和inventory import复用同一mirror root但仍执行各自fresh fetch/commit verification；临时worktree/output/Compose/DB/S3继续按run清理，并保留可诊断的source/error_code/message。
- `observable_results`:
  - `RESULT-001`: stable root固定为`C:/Users/admin/.codex/runtime/image2/source-git-v1`，不位于workspace或每次run root。
  - `RESULT-002`: g0dam、JoeSai、ConardLi在任何extract/import前均通过production `fixed_snapshot(... timeout_seconds=900)`预热；既有mirror保留，临时worktree清理。
  - `RESULT-003`: extraction和inventory import传入同一stable root，不再创建`run_root/extraction-git`和`run_root/import-git`全量mirror副本；每次production boundary仍fetch registered commit、rev-parse、safe-tree和detached worktree。
  - `RESULT-004`: Git失败对外错误包含source id、`GitSnapshotError.error_code`和bounded原始message；不得暴露credentials，不能只剩“fresh mirror preparation failed”。
  - `RESULT-005`: 若首次创建某source mirror失败，Validator只删除本次新建且不完整的owned mirror path；若mirror在运行前已存在则保留并报错，不盲删持久cache。
  - `RESULT-006`: offline tests覆盖stable root、三来源预热顺序/timeout、共享root wiring、错误透传与owned incomplete cleanup；fresh live最终重新闭合312-case链路。
- `non_goals`: 不提高或修改`ingestion.git_snapshot.fixed_snapshot`全局默认90秒；不改变Source Registry、fixed commits、Adapter Output、Generation Example、inventory schema/migrations、rights/publication、counts或web/API；不把mirror cache当发布数据；不删除已有有效mirror。

# 3. 需求质疑与确认

- `user_statement`: 继续推进，真实阻点要从正确责任边界修复，不能无限重试或伪造通过。
- `REQ-001` (`required_behavior`): 新增task-neutral常量`EXPECTED_SOURCE_GIT_ROOT=C:/Users/admin/.codex/runtime/image2/source-git-v1`，并经`_must_be_external`验证不在workspace。
- `REQ-002` (`required_behavior`): `run()`将persistent source root与ephemeral `run_root`分离；source root可跨formal candidate/task保留mirrors，run root仍承载packages、compose.env和临时输出并最终删除。
- `REQ-003` (`required_behavior`): 在任何extract/Compose/import前，按g0dam、JoeSai、ConardLi顺序加载registry config并逐一调用production `fixed_snapshot`，timeout=900；每次context正常退出后不得残留`worktrees/<source>/run-*`。
- `REQ-004` (`required_behavior`): `_prewarm_source_mirror`捕获`GitSnapshotError`后产生稳定`ValidationFailure`，message必须含source id、error_code和bounded原始错误文本。
- `REQ-005` (`required_behavior`): prewarm前记录目标mirror是否已存在；失败时仅当本次开始前不存在且当前path出现时删除该owned incomplete mirror，保留其父级其他mirrors/config/hooks。
- `REQ-006` (`required_behavior`): 三来源production extraction的`data_root`全部使用persistent source root；ConardLi failure/concurrency同样使用该root。
- `REQ-007` (`required_behavior`): initial inventory imports和verified_existing replays的`--data-root`全部使用同一persistent source root，不能再用`run_root/import-git`。
- `REQ-008` (`required_behavior`): cleanup验证覆盖全部三来源worktrees、candidate/locks、Compose和ephemeral run root；persistent `mirrors/*.git`、isolated git config和empty-hooks是允许保留的cache，不得被误判为污染。
- `REQ-009` (`required_behavior`): live JSON新增或更新证据字段，明确persistent mirror root、三个prewarmed source ids、cache retained、temporary worktrees cleaned；不得输出remote credentials或Compose secrets。
- `REQ-010` (`required_behavior`): tests使用monkeypatch/tmp_path，不访问网络/Docker；证明三来源预热均900秒、stable root不在run root、extraction/import共享root、error detail和new-only cleanup。
- `REQ-011` (`required_behavior`): 更新internal inventory文档的live validation说明，区分可保留的source mirror cache与必须清理的worktree/package/Compose/DB/S3状态。
- `REQ-012` (`required_behavior`): formal offline和live Validators fresh通过后完成L4 independent review、docs/hygiene/freshness和Completion Report；失败保持真实non-complete。
- `INV-001`: 每次使用cache仍必须执行production fresh fetch、fixed commit rev-parse、safe-tree和detached worktree；cache不是跳过远端/合同校验。
- `INV-002`: 只有mirrors/config/hooks可跨run保留；worktrees、packages、locks、DB/S3、Compose、credentials和logs不可保留。
- `INV-003`: partial/new mirror cleanup只作用于本次owned path；已有mirror和其他source cache受保护。
- `INV-004`: 三来源100/50/162、528/312、fixed aggregates、schemas、failure/concurrency、replay、rights/publication全部不变。
- `INV-005`: 上游代码不执行、不构建、不安装；Git安全配置和file protocol边界不变。
- `INV-006`: TASK-0009/0010/0011 cards/runs/evidence只读，不把历史receipts作为本卡pass。
- `material_ambiguities`: 首次持久cache创建仍可能受网络影响；本卡解决重复全量clone和诊断丢失，不将网络失败改写为成功，也不引入离线跳过fetch模式。
- `decisions_and_authority`: 最小正确边界是live Validator orchestration与其tests/docs；`git_snapshot.py`已支持传入持久data_root和自定义timeout，本卡不修改其生产默认或接口。

# 4. 业务场景与规则

- `SCN-001` cold cache: 三来源依次以900秒production snapshot创建/验证mirrors，worktrees清理，随后完整live通过。
- `SCN-002` warm cache: 保留mirrors，仍fresh fetch固定Commit并验证；不全量重克隆，live通过。
- `SCN-003` new mirror失败: error detail完整，本次新建partial mirror删除，其他cache不变，run cleanup。
- `SCN-004` existing mirror fetch失败: existing mirror保留，error detail完整，不进入extract/import。
- `SCN-005` cleanup失败: worktree/Compose/runtime残留即Validator失败，不因业务counts通过而完成。
- `SCN-006` regression: 三来源counts/hash/schema/replay/rights任一变化阻断。
- `RULE-001`: persistent source cache与ephemeral run state分离。
- `RULE-002`: cache reuse不等于receipt/output reuse；每次formal live仍fresh执行全部行为。
- `RULE-003`: production fixed_snapshot是唯一Git fetch/commit/safety/worktree owner，Validator只选择root/timeout并处理诊断/owned partial cache。
- `RULE-004`: source root在workspace外且不得包含secrets。
- `RULE-005`: no global Git config、registry或dependency changes。
- `STATE-001`: `cold|warm cache → prewarm each source → extraction/fault/concurrency → Compose/import/replay → cleanup → evidence`；任一步失败不进入后续。
- `FLOW-001`: `stable mirrors → fresh fixed snapshots → ephemeral packages → private DB/S3 → formal receipt`。
- `risk_sensitive_invariants`: existing cache不盲删；fixed commit不放宽；临时状态完全清理；底层错误可诊断；history evidence只读。
- `inapplicable_faces_with_reason`: 无UI、用户权限或production publication动作；权限面保持internal-only/rights fail-closed。

# 5. 当前证据与目标差异

- `FACT-001`: `fixed_snapshot`的mirror位于调用方`data_root/mirrors`，每次都会fetch registered commit并验证；worktree在context finally清理，mirror保留。
- `FACT-002`: 当前three-source Validator把`extraction_data`设为`run_root/extraction-git`，inventory imports用`run_root/import-git`，finally删除整个run root，因此每次formal live都重新全量clone。
- `FACT-003`: 当前仅预热ConardLi且错误包装丢失`GitSnapshotError`code/message；TASK-0011 candidate1失败于g0dam 90秒clone，candidate2失败于ConardLi prewarm。
- `FACT-004`: 当前offline test只证明ConardLi prewarm调用900秒，不覆盖stable cache、全部三来源、import wiring或诊断。
- `ASM-001`: production `fixed_snapshot`在warm mirror上对registered commit执行fetch可在900秒预热后稳定完成；fresh live必须验证，若不成立则本卡保持non-complete并保留底层诊断。
- `current_execution_path`: ephemeral run root → clone mirrors → extracts → separate import mirrors → Compose DB/S3 → delete all。
- `target_delta`: stable external source root拥有mirrors；ephemeral run root只拥有outputs/Compose状态；all source operations共享stable root并保持fresh verification。
- `evidence_gaps`: 尚缺实现、unit tests、fresh live receipt、docs/review/report。

# 6. 范围与责任边界

- `allowed_write_scope`: `scripts/validate_three_pilot_sources.py`、`tests/ingestion/test_extraction_pipeline.py`、`docs/inventory/internal-inventory-v1.md`、本卡formal evidence root；external runtime仅task-neutral source cache和owned ephemeral resources。
- `hard_protected_scope`: `ingestion/git_snapshot.py`、pipeline/adapters/contracts、inventory production modules/migrations、registry/audit/schemas/fixtures、其他docs/tasks/历史runs、用户其他Docker/Git/runtime状态。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、fixed commits/aggregates、100/50/162、528/312、rights/publication、safe Git和cleanup。
- `authorization_limits`: 不授权删除existing mirrors、修改权限、公开内容、改变global timeout/default、清理nonowned resources或执行上游代码。
- `stop_if_scope_expands`: 若需要修改`git_snapshot.py`接口/默认、registry、inventory CLI、schema/migration或非owned external state，停止并报告新证据。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal live command调用`validate_three_pilot_sources.run`；run选择stable source root并调用production fixed_snapshot/extract/import；最终JSON和receipt由Completion Report消费。
- `expected_touchpoints_or_search_anchors`: `EXPECTED_RUNTIME_ROOT`、`_prewarm_fresh_mirror`、`run()`中的`extraction_data`和两处`run_root/import-git`、cleanup/result JSON；对应pipeline tests与inventory doc。
- `wiring_to_final_consumer`: stable source root传给prewarm、three extracts、ConardLi failure/concurrency、initial imports和replays；fresh live receipt证明最终312-case consumer链。
- `failure_and_recovery`: prewarm失败在Compose前终止并输出详细错误；new partial owned mirror清理；existing mirror保留；run finally清理ephemeral state；formal failed receipt要求新candidate。
- `implementation_freedom`: helper命名与局部结构可调整，但stable path、900 timeout、all-source order/shared root、new-only cleanup、diagnostic shape和protected scope不可改变。
- `selected_profile_obligations`:
  - `external-boundary`: Git network timeout/error/cancellation、cache ownership、no-secret、Docker cleanup和真实integration receipt。
  - `stateful-runtime`: cold/warm cache、partial failure、worktree cleanup、repeated execution和DB/S3 replay。
  - `configuration`: fixed root、timeout、registry source order、runtime外置和Git安全配置。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-012`, `INV-001`至`INV-006`
- `owns_behavior`: stable source mirror cache与ephemeral live run分离，并保留fresh fixed-commit verification和可诊断失败。
- `target_delta`: 移除每次run的重复full clone边界，all extraction/import共享stable root。
- `integration_edges`: Validator → fixed_snapshot/extract → inventory CLI → final live receipt。
- `expected_touchpoints`: 三个allowed files。
- `business_result`: Phase1 live闭环不再因每次重复大仓库clone而系统性不稳定。
- `behavior_faces`: normal=cold/warm cache；boundary=3 sources/900s；failure=new/existing mirror errors；permission=owned cache only；empty=cold root；repeated=warm reuse；downstream error=无passed receipt则Phase1不完成。
- `state_change`: entry=current ephemeral design；exit=stable cache design+passing evidence；failure=repo candidate不complete、external state安全。
- `data_flow`: registry configs → stable mirrors → temporary worktrees → packages → DB/S3；mirror是cache，fixedCommit/registry是authority。
- `integration_point`: caller=live command；trigger=run；callee=fixed_snapshot/extract/import；return=JSON/receipt；consumer=TASK-0013 formal adoption或本卡Completion Report。
- `scope_boundary`: hard=不改production modules/contracts；soft=不做sync scheduler/publication/web。
- `allowed_write_scope`: section 6三文件。
- `acceptance_scenarios`: `SCN-001`至`SCN-006`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: protected file需要修改、existing mirror需删除、fixed verification需放宽或live仍因相同责任边界失败。

- `assembly_not_required_reason`: 一个纵向行为切片，代码/tests/docs与live是同一TASK验收层。

# 9. 验证与验收

- `consumer_chain_validation`: stable root必须真实连通prewarm、extract、failure/concurrency、import/replay和最终live JSON；仅helper unit test不足。
- `real_integration_evidence`: fresh live receipt必须证明cold或warm cache下三个fixed sources、312-case DB/S3、replay/rights/cleanup全部通过。
- `failure_recovery_ownership_validation`: new-only partial mirror cleanup、existing mirror preservation、temporary worktree/Compose/run-root cleanup和formal process containment必须有tests/live/post-audit证据。

### RISK-001
- `description`: stable cache若跳过fetch会把陈旧/损坏mirror当authority；每次仍production fixed_snapshot。
### RISK-002
- `description`: failure cleanup若误删existing mirror会破坏长期source state；只清理本次new path。
### RISK-003
- `description`: shared root wiring遗漏import会继续重复clone；extract和两类import必须同root。
### RISK-004
- `description`: 错误包装丢失细节会使环境与实现问题不可区分；code/message必须保留且无secret。

### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-010`, `RISK-001`至`RISK-004`
- `method`: pytest offline，monkeypatch fixed_snapshot/extract/import与tmp external roots，覆盖cold/warm/error/cleanup/wiring。
- `expected_observable_result`: all source order、900、stable root、shared wiring、diagnostic和new-only cleanup断言通过，既有ingestion/package tests无回归。
- `failure_path_covered`: partial mirror、existing fetch fail、wrong root、lost error、worktree residue。
- `cannot_prove`: 不证明真实Git/Docker。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: fresh offline receipt/log与测试名称覆盖矩阵。

### TEST-002
- `links`: `TASK-001`, `REQ-003`至`REQ-009`, `INV-001`至`INV-005`
- `method`: fresh live三来源command，前后orphan/cache audit，检查JSON、counts、hashes、cache/worktree/Compose状态。
- `expected_observable_result`: 3 prewarmed、persistent cache retained、temporary clean、100/50/162、528/312、fault/concurrency/replay/rights passed。
- `failure_path_covered`: real network/Git/cache/DB/S3/cleanup错误。
- `cannot_prove`: 不证明未来远端永远可用。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: terminal live receipt/log/JSON、mirror inventory、no-worktree/no-Compose/no-secret post-audit。

### TEST-003
- `links`: `TASK-001`, `REQ-011`, `REQ-012`
- `method`: docs/hygiene/protected scope、candidate evidence、L4 review、final freshness、Completion Report official validation。
- `expected_observable_result`: 3 files闭合、protected files不变、2 validators passed、review findings=0、report complete。
- `failure_path_covered`: doc drift、scope expansion、stale receipt、false completion。
- `cannot_prove`: 不证明publication/web/sync。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: documentation/hygiene/protected/freshness、deterministic bundle、review、report validation。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "stable-three-source-cache-offline",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "tests/ingestion", "tests/inventory/test_package.py", "-q"],
      "cwd": ".",
      "timeout_seconds": 420,
      "invalidation_paths": ["1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory/package.py", "scripts/validate_three_pilot_sources.py", "scripts/validate_joesai_multi_source.py", "tests/ingestion", "tests/inventory/test_package.py", "docs/inventory/internal-inventory-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import pytest, jsonschema, psycopg, boto3; print('ready')"],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "stable-three-source-cache-compose-live",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_three_pilot_sources.py", "--registry", "config/sources-v1.yaml", "--audit", "reports/source-audit-v1.json", "--g0dam-source-id", "g0dam-work-prompts", "--g0dam-expected-commit", "690c2d6969a65b406b17ba7d41f18695a652c3fe", "--g0dam-expected-cases", "100", "--g0dam-expected-aggregate", "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0", "--joesai-source-id", "joesai-commercial-prompts", "--joesai-expected-commit", "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b", "--joesai-expected-cases", "50", "--joesai-expected-aggregate", "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293", "--conardli-source-id", "conardli-gpt-image-2-101", "--conardli-expected-commit", "971b67dc8cbca8cf6eb32e196fea04bddd6abe99", "--conardli-expected-cases", "162", "--conardli-expected-aggregate", "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573", "--runs", "2", "--failure-injection", "--concurrency", "--json"],
      "cwd": ".",
      "timeout_seconds": 3600,
      "invalidation_paths": ["1.md", "config/sources-v1.yaml", "reports/source-audit-v1.json", ".task-runs/TASK-0001", "schemas", "docs/contracts/content-contract-v1.md", "docs/ingestion", "docs/inventory/internal-inventory-v1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory", "migrations", "compose.yaml", "scripts/validate_three_pilot_sources.py", "scripts/validate_joesai_multi_source.py", "fixtures/adapters"],
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
| `GATE-001` | stable cache/offline | `OBJ-001` / `TASK-001` / `TEST-001` | all-source 900、shared root、diagnostic/cleanup tests通过 | `EV-001` | 不证明live |
| `GATE-002` | real live | `OBJ-001` / `TASK-001` / `TEST-002` | cache retained、temporary clean、312链路完整 | `EV-002` | 不证明网络永远可用 |
| `GATE-003` | formal closure | `OBJ-001` / `TASK-001` / `TEST-003` | 3 files/docs/review/freshness/report闭合 | `EV-003` | 不证明后续功能 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `scripts/validate_three_pilot_sources.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `docs/inventory/internal-inventory-v1.md`
- `documentation_impact`: updated；记录persistent source mirror cache与ephemeral worktree/package/Compose/DB/S3的不同生命周期及fresh fetch不变量。
- `repository_hygiene_requirement`: 仅3个声明文件变化；无cache/media/package/log/secret入workspace；external stable root只保留mirrors/config/hooks，无worktrees；formal evidence写TASK-0012 root；历史tasks/runs只读。
- `external_review`: policy=never；真实live+L4 independent review足够。
- `non_completion_rules`: 3/3 files、2/2 validators、cold/warm/error tests、live cache/worktree evidence、docs/review/freshness/report任一缺失不得完成；若需修改protected production modules或删除existing cache不得完成。

### 必交产物

- `scripts/validate_three_pilot_sources.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `docs/inventory/internal-inventory-v1.md`

执行时继续使用TASK-0009 venv/cache/tmp环境，但source Git cache固定为`C:/Users/admin/.codex/runtime/image2/source-git-v1`。首次cold cache可耗时；所有结论必须由fresh receipts产生，不复用TASK-0011失败证据。
