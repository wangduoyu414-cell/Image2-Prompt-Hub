---
task_contract_version: 3
card_id: "TASK-0017"
title: "统一验证并正式关闭Phase 1纵向闭环"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "investigation"
  - "external-boundary"
  - "stateful-runtime"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户持续推进至全部完成；`1.md`完整Phase 1目标与验收标准；TASK-0001至0016当前workspace和formal state；canonical恢复卡TASK-0012R、TASK-0015R及TASK-0013/0014/0016 Completion Reports。
- `decision_owner`: 用户拥有Phase 1完成目标和下一阶段方向；本卡只基于真实workspace/receipts/report/live结果确认状态，不隐藏历史失败、不宣称部署或rights批准。
- `material_unknowns`: 最终最新migration下API/web live是否仍通过、所有canonical reports是否与当前deliverables保持适用，必须由本卡fresh validator证明。

# 2. 业务目标
- `actor`: 项目维护者与准备进入Phase 2的执行者。
- `workflow_and_trigger`: 扫描当前Phase 0/1 canonical task runs、Completion Reports、deliverables和历史恢复关系；运行全仓offline regression与最新migration下的Content/API/Web live；生成一个机器可读的Phase 1 closure结果；同步设计文档实际状态和独立closure文档。
- `single_outcome`: 用一份可复核的统一证据证明“真实三来源→契约/资产/库存→Canonical/rights/publication→API→网页→Commit更新同步”Phase 1闭环已完成，同时明确真实公开数量仍为0、系统尚未部署、历史阻断已由哪些恢复卡替代。
- `observable_results`:
  - `RESULT-001`: canonical complete链至少包括TASK-0001至0005、TASK-0007、TASK-0012R、TASK-0013、TASK-0014、TASK-0015R、TASK-0016；每个run COMPLETE、唯一Completion Report有效、相关deliverables当前适用。
  - `RESULT-002`: TASK-0006、0008至0012的历史blocked attempts与TASK-0015 RESULT_UNKNOWN继续保留；恢复关系明确，不把旧状态改写或删除。
  - `RESULT-003`: 真实GitHub三source closure为100/50/162、528 files、312 Generation Examples/objects；持久mirrors保留，fixed authority/aggregates和cleanup有fresh TASK-0012R证据。
  - `RESULT-004`: Content Core、rights fail-closed、explicit revision selection、atomic publication、API asset授权、Next列表/详情/复制和增量同步报告链全部闭合。
  - `RESULT-005`: 全仓offline tests与最新0001至0004 migration下的Content/API/Web live fresh通过；新增sync schema不能破坏current-only API/web。
  - `RESULT-006`: 当前没有用户提供的真实人工rights approval，因此真实Publication/API/Web目录应为0条；synthetic批准只用于validators，不写production事实。
  - `RESULT-007`: `1.md`更新版本/日期/状态、Phase 1实际交付、当前限制和下一步；不再保留“实施前设计基线/立即先做Phase1”的过期表述。
  - `RESULT-008`: `docs/phase1/phase1-closure-v1.md`记录当前可运行产品状态、来源/案例数量、模块边界、报告索引、历史恢复、未部署/0公开与Phase 2进入条件。
  - `RESULT-009`: final validator JSON含task/report hash、supersession、source counts、regression/live results、documentation state和cleanup，不含secret。
- `non_goals`: 不新增Adapter/source、人工rights决定、部署、scheduler、管理后台、Phase 2/3/4功能，不修改生产业务模块或历史formal evidence。

# 3. 需求质疑与确认
- `user_statement`: 按确定方向持续推进到全部完成，并严谨校验；最终必须说明项目真实状态，而非只报任务数量。
- `REQ-001` (`required_behavior`): 新增独立Phase1 closure validator与tests，不能仅凭文档或手工列表宣布完成。
- `REQ-002` (`required_behavior`): validator必须读取formal run-state、Completion Report和report validation，验证canonical complete任务与current deliverable applicability。
- `REQ-003` (`required_behavior`): 定义并验证历史恢复映射：`TASK-0006 → TASK-0007`；`TASK-0008/0009/0010/0011/0012 → TASK-0012R`；`TASK-0015 → TASK-0015R`。映射只表示完成职责由新卡证明，不改变旧状态。
- `REQ-004` (`required_behavior`): 从TASK-0012R fresh live evidence验证三个真实source的固定Commit、100/50/162、528/312、两轮、failure/concurrency/replay/rights/cleanup。
- `REQ-005` (`required_behavior`): 从TASK-0013/0014/0015R/0016报告验证Content、API、Web、sync的终端receipts、review 0 findings、scope和cleanup；过期或hash不匹配阻断。
- `REQ-006` (`required_behavior`): offline validator运行全仓pytest和Phase1 closure unit tests，防止只检查报告而漏当前代码回归。
- `REQ-007` (`required_behavior`): live validator在当前0001至0004 migrations和workspace代码上fresh运行Content Core、Public API和Public Web live，验证sync新增migration与现有消费者兼容。
- `REQ-008` (`required_behavior`): validator确认真实rights批准不存在/未被仓库或报告伪造，文档与状态明确真实公开数量0；不得生成fake production内容。
- `REQ-009` (`required_behavior`): `1.md`头部更新到v1.1、日期2026-08-08、状态`Phase 1 已完成；Phase 2 待启动`，并更新Phase 1/18节为当前事实和下一步。
- `REQ-010` (`required_behavior`): closure文档区分“实现/验证完成”“运行时未部署”“真实公开0”“历史attempt仍保留”，避免把代码完成写成线上服务已运营。
- `REQ-011` (`required_behavior`): machine JSON和文档列出当前正式长期来源仅3个；312是内部Generation Examples，不是312个已公开案例。
- `REQ-012` (`required_behavior`): 完成4文件scope/protected hash、docs/hygiene/freshness、L4 independent review与唯一Completion Report；非Git不commit。
- `INV-001`: Source/Evidence、rights和Publication分层不变；最终文档不能放宽fail-closed。
- `INV-002`: canonical complete状态由fresh reports/live证明；旧blocked/unknown状态保留且不计为当前未完成，只因明确恢复卡承担同一交付职责。
- `INV-003`: API/web仍只读current completed Publication Version；inventory或latest revision不能直接公开。
- `INV-004`: 0真实公开条目是当前正确结果，不是Phase 1失败；公开内容需未来人工rights审核。
- `INV-005`: Phase 1完成不意味着部署、scheduler、全部候选来源、管理后台或Phase 4运营完成。
- `material_ambiguities`: 早期多个blocked attempt与后续recovery并存；本卡采用显式supersession map而非删除历史，保持审计真实性。
- `decisions_and_authority`: 用户持续执行授权与`1.md`Phase1路线确认本卡可正式关闭Phase1；后续只进入Phase2范围，不扩写本卡。

# 4. 业务场景与规则
- `SCN-001` complete: canonical reports和current hashes适用，全仓/live通过，文档状态一致，Phase1关闭。
- `SCN-002` stale report: 任一required report、validation、receipt或deliverable hash不适用，阻断并指出task/path。
- `SCN-003` consumer regression: 0004 migration后Content/API/Web live失败，保持non-complete并在4文件外修复需求处停止。
- `SCN-004` historical truth: old blocked/unknown states仍存在，supersession只在closure文档/JSON解释，不修改历史。
- `RULE-001`: “完成”同时要求实现、当前回归、真实source证据、consumer live、文档状态和无未披露风险。
- `RULE-002`: 312 internal != 312 public；0 public != 0 internal。
- `STATE-001`: current Phase1 evidence→audit/regression/live→closure docs→final report→Phase1 closed。
- `FLOW-001`: task states/reports + workspace + fresh tests/live → machine closure result → `1.md`/closure doc → Completion Report。
- `risk_sensitive_invariants`: `INV-001`至`INV-005`、supersession honesty、report freshness、zero-public semantics、consumer compatibility和secret redaction。
- `inapplicable_faces_with_reason`: 无生产数据写、账户或外部发布；外部边界仅本地Compose/Chromium和读取已有formal evidence。

# 5. 当前证据与目标差异
- `FACT-001`: TASK-0012R已真实GitHub live COMPLETE，100/50/162、528/312；TASK-0016已三adapter sync COMPLETE；TASK-0015R已网页fresh browser COMPLETE。
- `FACT-002`: TASK-0013/0014分别正式闭合Content/Publication和API/S3；当前真实rights无人工批准，default publication为0。
- `FACT-003`: `1.md`仍标记v1.0、2026-08-02、实施前设计基线，Phase1/第18节仍是未来计划，已与workspace事实不一致。
- `FACT-004`: 当前无Phase1总控validator、closure doc或一个统一报告证明报告链/当前代码/最新migration消费者仍一致。
- `ASM-001`: TASK-0012R/0015R/0016完成后生产相关文件未再被本卡之外修改；validator必须实际比较而非假设。
- `current_execution_path`: 各层有独立formal reports，但维护者需手工拼接整体状态。
- `target_delta`: 新增可执行总控审计与权威Phase1状态文档，消除手工推断和过期设计状态。
- `evidence_gaps`: 4文件实现、full regression、Content/API/Web latest-migration live、L4 review与report。

# 6. 范围与责任边界
- `allowed_write_scope`: `scripts/validate_phase1_closure.py`、`tests/phase1/test_phase1_closure.py`、`docs/phase1/phase1-closure-v1.md`、`1.md`、本卡formal evidence root。
- `hard_protected_scope`: 所有production代码/config/audit/schemas/fixtures/migrations/other tests/scripts/docs、TASK-0001至0016 cards与formal state/evidence、persistent mirrors。
- `protected_contracts_and_invariants`: `INV-001`至`INV-005`、all canonical Completion Reports、old history states、fixed source/count/aggregate、rights fail-closed、API/web current-only。
- `authorization_limits`: 不授权修production、改历史reports/run-state、rights批准、部署、外部写入或开始Phase2实现。
- `stop_if_scope_expands`: final validation发现production defect、report corruption、缺失authority或需修改第5个durable文件时停止并创建后续修复卡。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal runner/maintainer调用Phase1 validator；结果供`1.md`、closure文档和后续Phase2规划消费。
- `expected_touchpoints_or_search_anchors`: task-state image2 roots、completion-report/validation、candidate snapshots/receipts；existing `validate_content_core.py`、`validate_public_api.py`、`validate_public_web.py`；`1.md` sections 15/18。
- `wiring_to_final_consumer`: report/state audit→full pytest→Content/API/Web live→closure JSON→docs status→formal report。
- `failure_and_recovery`: child validator失败捕获bounded stdout/stderr和code；Compose/browser由existing validators清理；任何stale/missing/mismatch阻断；本卡不越界修production。
- `implementation_freedom`: 可选择报告解析和hash比较内部结构，但4文件、canonical task set、supersession、full regression、three live consumers、zero-public/status语义不可改变。
- `selected_profile_obligations`:
  - `investigation`: 问题是“canonical reports与当前workspace是否共同证明完整Phase1”；证据范围限定task-state/reports/current files/full regression/三consumer live；竞争假设包括stale report、错误supersession、312/public混淆和migration consumer regression；复现方法为closure unit+machine validator；durable handoff为Phase1 closure JSON/doc。
  - `external-boundary`: 覆盖child validators、Compose、Chromium、错误传播、timeout、cleanup与secret redaction。
  - `stateful-runtime`: 覆盖formal run/report/current evidence freshness、重复审计确定性和失败时不关闭Phase1。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-012`, `INV-001`至`INV-005`
- `owns_behavior`: Phase1统一审计、live回归和权威状态回写。
- `target_delta`: 从分散报告+过期设计文档到机器可验证、用户可读的Phase1 closed状态。
- `integration_edges`: formal reports/workspace→pytest/Content/API/Web validators→closure JSON/docs。
- `expected_touchpoints`: section 6的4文件。
- `business_result`: 用户可以明确知道当前项目已具备什么、案例为何未公开、下一步做什么。
- `behavior_faces`: normal=all complete；boundary=0 public/312 internal；failure=stale report/live regression；permission=no rights/history writes；empty=missing task/report block；repeated=deterministic audit；downstream=Phase2 planning。
- `state_change`: Phase1 implemented→verified/closed；失败保持not closed且旧状态不变。
- `data_flow`: reports/receipts/hashes+current tests/live→closure result→docs/report。
- `integration_point`: caller=formal runner；callee=filesystem/pytest/existing live validators；return=JSON；consumer=user/Phase2。
- `scope_boundary`: hard=4 files/no production/history mutation；soft=不做Phase2。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-004`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: production fix、missing canonical evidence、rights ambiguity或scope expansion。
- `assembly_not_required_reason`: 一个Phase1 closure控制切片；各业务子链已由canonical tasks完成。

# 9. 验证与验收
- `consumer_chain_validation`: 必须fresh运行latest migrations下Content/API/Web live；只读旧reports不能证明当前消费者兼容。
- `real_integration_evidence`: TASK-0012R真实GitHub receipt适用性 + TASK-0016 sync receipt适用性 + fresh Content/API/Web live + full pytest。
- `failure_recovery_ownership_validation`: existing validators拥有Compose/Chromium cleanup；closure validator只聚合、验证和redact；历史evidence只读。

### RISK-001
- `description`: 分散任务均complete但current code/report已漂移，会产生虚假总完成。
### RISK-002
- `description`: 把旧blocked/unknown删除或当作仍未完成都会歪曲真实恢复历史。
### RISK-003
- `description`: 把312 internal写成312 public或把实现完成写成已部署会误导产品状态。
### RISK-004
- `description`: 0004 migration可能破坏API/web旧读取路径，必须fresh consumer live。

### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-006`, `RISK-001`至`RISK-003`
- `method`: 执行full pytest及Phase1 closure unit tests，覆盖required tasks、supersession、report/hash、doc状态、zero-public和错误脱敏。
- `expected_observable_result`: 全仓通过；stale/missing/misreported fixture被tests拒绝。
- `failure_path_covered`: missing report、wrong status/hash、bad supersession、312/public混淆。
- `cannot_prove`: Compose/API/web live。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: full pytest terminal receipt、test count与closure unit matrix。

### TEST-002
- `links`: `TASK-001`, `REQ-002`至`REQ-011`, `INV-001`至`INV-005`, `RISK-001`至`RISK-004`
- `method`: `scripts/validate_phase1_closure.py --json`验证task/report chain并fresh执行Content Core、Public API、Public Web live；核对cleanup和docs状态。
- `expected_observable_result`: canonical/supersession/source counts/report hashes/current migration consumers/0 public/docs/cleanup全部passed。
- `failure_path_covered`: child failure、timeout、stale evidence、secret、cleanup、consumer regression。
- `cannot_prove`: production deploy、human rights或Phase2来源。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: machine JSON含tasks/reports/supersession/source/internal-public counts/child results/cleanup/docs，无secret。

### TEST-003
- `links`: `TASK-001`, `REQ-009`至`REQ-012`, `RISK-001`至`RISK-004`
- `method`: exact4 files/protected hashes、documentation consistency、deterministic evidence、L4 independent review、terminal freshness和Completion Report validation。
- `expected_observable_result`: 4/4、2 validators、review 0 findings、report complete、Phase1状态与证据一致。
- `failure_path_covered`: scope drift、stale docs/evidence、history mutation和runtime residue。
- `cannot_prove`: Phase2/3/4完成。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/docs check/review/freshness/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"phase1-closure-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["1.md","pyproject.toml","uv.lock","apps","config","content","docs","fixtures","ingestion","inventory","migrations","reports","schemas","scripts","sync","tests"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["uv","run","--frozen","--no-sync","python","-B","-c","import pytest, fastapi, psycopg, boto3; print('ready')"],"preflight_timeout_seconds":30},
  {"validator_id":"phase1-closure-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase1_closure.py","--json"],"cwd":".","timeout_seconds":2400,"invalidation_paths":["1.md","apps","content","docs/api","docs/content","docs/phase1/phase1-closure-v1.md","docs/web","ingestion","inventory","migrations","scripts/validate_content_core.py","scripts/validate_public_api.py","scripts/validate_public_web.py","scripts/validate_phase1_closure.py","sync","tests/phase1/test_phase1_closure.py"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["node","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | full regression | OBJ-001 / TASK-001 / TEST-001 | 全仓tests与closure unit通过 | EV-001 | live consumers |
| GATE-002 | unified closure live | OBJ-001 / TASK-001 / TEST-002 | reports/source counts/Content/API/Web/docs/cleanup通过 | EV-002 | deploy/rights/Phase2 |
| GATE-003 | formal Phase1 close | OBJ-001 / TASK-001 / TEST-003 | 4文件、docs/review/freshness/report闭合 | EV-003 | 后续Phase |

# 10. 产物与完成回写
- `required_deliverables`:
  - `scripts/validate_phase1_closure.py`
  - `tests/phase1/test_phase1_closure.py`
  - `docs/phase1/phase1-closure-v1.md`
  - `1.md`
- `documentation_impact`: updated；`1.md`转为Phase1完成状态并新增独立closure文档，明确3来源/312 internal/0 public/未部署/下一步。
- `repository_hygiene_requirement`: exact4 files；child runtime/Compose/Chromium/log在workspace外并清理；所有task-state/reports/mirrors只读；无cache/secret入workspace。
- `external_review`: policy=never；fresh full regression+three consumer live+L4 independent review足够。
- `non_completion_rules`: 4/4、canonical reports/supersession、TASK-0012R真实source、TASK-0016 sync、full pytest、Content/API/Web live、312 internal/0 public、docs consistency、cleanup/review/freshness/report任一缺失不得关闭Phase1。

### 必交产物
- `scripts/validate_phase1_closure.py`
- `tests/phase1/test_phase1_closure.py`
- `docs/phase1/phase1-closure-v1.md`
- `1.md`

本卡完成后，Phase 1正式关闭；后续工作从Phase 2来源扩展/人工rights审核准备开始，不自动属于本目标。
