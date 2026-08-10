---
task_contract_version: 3
card_id: "TASK-0017R"
title: "重新执行并正式关闭Phase 1统一验收"
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
- `authority_sources`: 用户持续推进到全部完成；TASK-0017统一closure合同；TASK-0017旧BLOCKED证据；TASK-0017A migration-aware validator修复Completion Report；当前Phase0/1 canonical reports和workspace。
- `decision_owner`: 用户授权新run重新执行统一验收；旧TASK-0017 blocker/run/evidence只读保留。
- `material_unknowns`: none；Content/API migration blocker已由TASK-0017A正式修复，剩余结果均为本卡必须fresh生成的验证证据。

# 2. 业务目标
- `actor`: 项目维护者与准备进入Phase 2的执行者。
- `workflow_and_trigger`: 从当前workspace创建独立formal run，审计canonical/superseded task reports，运行全仓tests与最新0004 migration下Content/API/Web live，生成closure validator/tests/docs并把`1.md`回写为真实Phase1完成状态。
- `single_outcome`: 用新run和完整证据正式关闭Phase 1，同时保留所有历史失败/恢复关系并准确说明3来源、312 internal、0 real public和未部署状态。
- `observable_results`:
  - `RESULT-001`: canonical complete链包括TASK-0001至0005、0007、0012R、0013、0014、0015R、0016、0017A；run/report/validation/current applicability闭合。
  - `RESULT-002`: 历史恢复映射明确：0006→0007；0008/0009/0010/0011/0012→0012R；0015→0015R；0017→0017R；旧状态不改写。
  - `RESULT-003`: TASK-0012R真实source证据为100/50/162、528 files、312 Generation Examples/objects；TASK-0016三adapter增量同步证据有效。
  - `RESULT-004`: full pytest和fresh Content/API/Web live在0004下通过，current-only、rights、asset、public-loss、copy/link_only和cleanup不回归。
  - `RESULT-005`: 当前真实人工rights approval为0，真实public count为0；312只表示内部Generation Examples。
  - `RESULT-006`: `scripts/validate_phase1_closure.py`输出machine JSON，`tests/phase1`覆盖报告/supersession/stale/zero-public，`docs/phase1`记录最终状态。
  - `RESULT-007`: `1.md`更新为v1.1、2026-08-08、`Phase 1 已完成；Phase 2 待启动`，Phase1和当前下一步与事实一致。
  - `RESULT-008`: 4文件scope、L4 review、terminal freshness和唯一Completion Report闭合，Phase1正式关闭。
- `non_goals`: 不改production、migration、source、rights、部署、scheduler、管理后台或Phase2功能，不删除历史evidence。

# 3. 需求质疑与确认
- `user_statement`: 按已确认方向持续推进到全部完成，并严谨验证最终项目状态。
- `REQ-001` (`required_behavior`): 新TASK-0017R独立于旧TASK-0017；旧BLOCKED和TASK-0017A修复历史只读。
- `REQ-002` (`required_behavior`): 新增4个closure deliverables且只改这4个文件；production/report/run-state/mirrors不可写。
- `REQ-003` (`required_behavior`): closure validator读取task-state、Completion Report、report validation、receipts和workspace/candidate evidence，验证required canonical tasks与current applicability。
- `REQ-004` (`required_behavior`): 显式验证supersession map；mapping不改变旧状态，只证明当前交付职责由recovery/repair卡承担。
- `REQ-005` (`required_behavior`): 验证TASK-0012R real GitHub counts/aggregates/two runs/cleanup和TASK-0016 sync states/rights/public-loss/concurrency/object hashes。
- `REQ-006` (`required_behavior`): offline运行全仓pytest，closure unit tests拒绝missing/stale/wrong status/hash/bad supersession/312-public混淆。
- `REQ-007` (`required_behavior`): live fresh运行migration-aware Content Core、Public API和Public Web validators；child failure/timeout/secret/cleanup均fail closed。
- `REQ-008` (`required_behavior`): closure JSON与文档明确3个长期正式来源、312 internal、0 real public、系统实现/验证完成但未部署。
- `REQ-009` (`required_behavior`): `1.md`头部和Phase1/18节更新实际状态；下一步为Phase2来源扩展准入和人工rights审核准备，不重复Phase1计划。
- `REQ-010` (`required_behavior`): 完成docs consistency、hygiene、deterministic evidence、L4 independent review、freshness与唯一Completion Report。
- `INV-001`: Source/Evidence、rights、Publication、API/Web层级与fail-closed不变。
- `INV-002`: 312 internal不等于312 public；0 public是无人工批准时的正确结果。
- `INV-003`: Phase1 complete不表示部署、scheduler、全部候选来源或Phase2/3/4完成。
- `INV-004`: old blocked/unknown records必须存在且不可改；only explicit recovery map解释其当前含义。
- `INV-005`: current complete claim必须同时有current code regression、live consumers、reports、docs和cleanup证据。
- `material_ambiguities`: none；TASK-0017A已关闭唯一已知consumer migration阻断。
- `decisions_and_authority`: 用户的持续目标与TASK-0017原合同授权本恢复卡完成同一closure outcome。

# 4. 业务场景与规则
- `SCN-001` complete: reports/current hashes/full tests/three live/docs全部一致，Phase1关闭。
- `SCN-002` stale evidence: required report/receipt/hash不适用，精确阻断task/path。
- `SCN-003` live regression: Content/API/Web任一失败，不写Phase1 complete报告。
- `SCN-004` history: TASK-0017旧BLOCKED和其他attempt保留，新卡独立报告。
- `RULE-001`: docs不能先于machine evidence决定完成。
- `RULE-002`: implementation complete、runtime deployed、public data approved是三个不同状态。
- `STATE-001`: current evidence→audit→full regression→live→docs/freshness/review→complete。
- `FLOW-001`: task reports/workspace + fresh validators → closure JSON → docs/1.md → Completion Report。
- `risk_sensitive_invariants`: `INV-001`至`INV-005`、history isolation、current applicability、zero-public、cleanup/redaction。
- `inapplicable_faces_with_reason`: 无production写/用户权限；外部边界仅本地Compose/Chromium和formal state读取。

# 5. 当前证据与目标差异
- `FACT-001`: TASK-0012R、0013、0014、0015R、0016、0017A均COMPLETE；真实source、Content/API/Web、sync的分层证据已存在。
- `FACT-002`: TASK-0017旧run只因两个validator过期而BLOCKED，workspace未改、无closure deliverables；TASK-0017A已修复并fresh证明Content/API live。
- `FACT-003`: `1.md`仍为v1.0/2026-08-02/实施前设计基线，Phase1与第18节过期。
- `ASM-001`: TASK-0017A后当前production和canonical evidence未被其他任务修改；本卡必须实际比较验证。
- `current_execution_path`: 维护者仍需手工拼接分散reports，设计文档未反映实际完成。
- `target_delta`: machine closure、unit tests、closure doc和准确`1.md`状态。
- `evidence_gaps`: 4文件、full pytest、fresh Web live、统一JSON、review/report。

# 6. 范围与责任边界
- `allowed_write_scope`: `scripts/validate_phase1_closure.py`、`tests/phase1/test_phase1_closure.py`、`docs/phase1/phase1-closure-v1.md`、`1.md`、本卡formal evidence root。
- `hard_protected_scope`: 所有production/config/audit/schema/fixture/migration/other scripts/tests/docs/tasks/formal state/reports/mirrors，包括TASK-0017/0017A。
- `protected_contracts_and_invariants`: `INV-001`至`INV-005`、canonical reports、supersession history、source fixed facts、rights/current-only、TASK-0017A validator修复。
- `authorization_limits`: 不授权production修复、history/report修改、rights批准、部署或Phase2实现。
- `stop_if_scope_expands`: fresh audit/live发现需第5文件或production修复。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal runner/maintainer调用closure validator；用户和Phase2规划消费JSON/docs。
- `expected_touchpoints_or_search_anchors`: task-state run-state/report/validation/receipts；TASK-0012R/0016 live JSON；migration-aware Content/API validators；Public Web validator；`1.md` 15/18节。
- `wiring_to_final_consumer`: evidence audit→full pytest→Content/API/Web live→closure JSON→docs/1.md→formal report。
- `failure_and_recovery`: bounded child outputs；existing validators清理Compose/Chromium；missing/stale/mismatch阻断；本卡不越界修。
- `implementation_freedom`: 报告解析/JSON内部可选，但4文件、canonical set、supersession、full pytest、three live、zero-public和文档语义固定。
- `selected_profile_obligations`:
  - `investigation`: 问题为“当前reports与workspace是否足以关闭Phase1”；范围限定canonical/old task-state、current files、full pytest、three live；假设为stale evidence、bad recovery map、312/public混淆、consumer regression；复现为unit+machine validator；durable handoff为closure JSON/doc。
  - `external-boundary`: 覆盖child processes、Compose、Chromium、timeout/error、cleanup和secret redaction。
  - `stateful-runtime`: 覆盖formal run/report freshness、重复审计确定性和失败时不改变历史/完成状态。

# 8. TASK 与 ASSEMBLY 计划
### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-010`, `INV-001`至`INV-005`
- `owns_behavior`: Phase1最终统一closure recovery。
- `target_delta`: 分散证据+过期文档→machine-verified Phase1 closed。
- `integration_edges`: task reports/workspace→pytest/Content/API/Web→docs/report。
- `expected_touchpoints`: section 6的4文件。
- `business_result`: 项目状态可直接理解和复核，下一阶段边界明确。
- `behavior_faces`: normal=complete；boundary=312 internal/0 public；failure=stale/live；permission=no rights/history writes；empty=missing evidence；repeated=deterministic；downstream=Phase2。
- `state_change`: Phase1 evidence-ready→closed；失败保持open且旧状态不变。
- `data_flow`: states/reports/hashes/results→closure JSON/docs。
- `integration_point`: caller=formal runner；callee=filesystem/pytest/existing validators；consumer=user/Phase2。
- `scope_boundary`: hard=4 files/history/production protected；soft=no future phases。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-004`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: production defect、missing authority或scope expansion。
- `assembly_not_required_reason`: 业务子链已由canonical tasks完成，本卡只拥有统一closure。

# 9. 验证与验收
- `consumer_chain_validation`: fresh Content/API/Web live必须全部通过；reports alone不足。
- `real_integration_evidence`: TASK-0012R real source、TASK-0016 sync适用性、full pytest、fresh latest-migration consumers。
- `failure_recovery_ownership_validation`: existing validators拥有runtime cleanup；closure validator只读聚合并redact。
### RISK-001
- `description`: stale reports/current drift会造成虚假完成。
### RISK-002
- `description`: recovery map或历史修改会歪曲审计。
### RISK-003
- `description`: 312/public/部署状态文案错误会误导用户。
### RISK-004
- `description`: Web可能在最新后端/migration下回归。
### TEST-001
- `links`: `TASK-001`, `REQ-002`至`REQ-006`, `RISK-001`至`RISK-003`
- `method`: full pytest，包含closure unit tests。
- `expected_observable_result`: 全仓通过，bad fixture拒绝。
- `failure_path_covered`: missing/stale/status/hash/supersession/count semantics。
- `cannot_prove`: live。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: terminal receipt/test count/matrix。
### TEST-002
- `links`: `TASK-001`, `REQ-003`至`REQ-010`, `INV-001`至`INV-005`, `RISK-001`至`RISK-004`
- `method`: `scripts/validate_phase1_closure.py --json`审计reports并fresh执行Content/API/Web live。
- `expected_observable_result`: task/report/supersession/source/sync/consumer/312 internal/0 public/docs/cleanup passed。
- `failure_path_covered`: child error/timeout/stale/secret/cleanup/regression。
- `cannot_prove`: deploy/rights/Phase2。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: machine JSON和three child terminal evidence。
### TEST-003
- `links`: `TASK-001`, `REQ-001`, `REQ-009`, `REQ-010`
- `method`: exact4/protected hashes/docs/deterministic evidence/L4 review/freshness/report。
- `expected_observable_result`: 4/4、2 validators、review 0、report complete。
- `failure_path_covered`: scope/history/stale/docs/runtime。
- `cannot_prove`: later phases。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/docs/review/freshness/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"phase1-recovery-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["1.md","pyproject.toml","uv.lock","apps","config","content","docs","fixtures","ingestion","inventory","migrations","reports","schemas","scripts","sync","tests"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"phase1-recovery-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase1_closure.py","--json"],"cwd":".","timeout_seconds":2400,"invalidation_paths":["1.md","apps","content","docs/api","docs/content","docs/phase1/phase1-closure-v1.md","docs/web","ingestion","inventory","migrations","scripts/validate_content_core.py","scripts/validate_public_api.py","scripts/validate_public_web.py","scripts/validate_phase1_closure.py","sync","tests/phase1/test_phase1_closure.py"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["node","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | full regression | OBJ-001 / TASK-001 / TEST-001 | 全仓tests通过 | EV-001 | live |
| GATE-002 | unified live | OBJ-001 / TASK-001 / TEST-002 | reports/source/sync/three consumers/docs/cleanup通过 | EV-002 | deploy/rights/Phase2 |
| GATE-003 | Phase1 closure | OBJ-001 / TASK-001 / TEST-003 | 4文件/review/freshness/report闭合 | EV-003 | later phases |

# 10. 产物与完成回写
- `required_deliverables`:
  - `scripts/validate_phase1_closure.py`
  - `tests/phase1/test_phase1_closure.py`
  - `docs/phase1/phase1-closure-v1.md`
  - `1.md`
- `documentation_impact`: updated；v1.1/Phase1完成状态、3来源/312 internal/0 public/未部署/下一步。
- `repository_hygiene_requirement`: exact4；child runtime/Compose/Chromium清理；all formal state/reports/mirrors只读；无secret/cache。
- `external_review`: policy=never；full regression+three live+L4 independent review足够。
- `non_completion_rules`: 4/4、canonical/supersession、real source/sync、full pytest、Content/API/Web live、312/0语义、docs/cleanup/review/freshness/report任一缺失不得关闭Phase1。

### 必交产物
- `scripts/validate_phase1_closure.py`
- `tests/phase1/test_phase1_closure.py`
- `docs/phase1/phase1-closure-v1.md`
- `1.md`

本卡完成即Phase 1正式关闭，当前持续目标达到终态。
