---
task_contract_version: 3
card_id: "TASK-0012R"
title: "重新验证并正式闭环三来源持久Git缓存"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "external-boundary"
  - "stateful-runtime"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户持续推进至Phase 1全部完成；TASK-0012 ready合同与3个现有deliverables；TASK-0012旧run的BLOCKED状态和GitHub cold-mirror RPC/curl56/early-EOF证据；TASK-0016已证明本地三adapter持续同步链。
- `decision_owner`: 用户授权在原3文件范围内重新执行真实三来源验证；旧TASK-0012 blocker、run和receipts只读，不改写为通过。
- `material_unknowns`: GitHub与本机网络当前是否可完成ConardLi cold/warm fetch是外部动态事实；必须由新run终端receipt据实决定。

# 2. 业务目标
- `actor`: Phase 1正式验证执行者与后续长期同步维护者。
- `workflow_and_trigger`: 从当前workspace建立独立formal run，使用持久source mirror cache fresh检测三来源固定Commit，运行两轮真实extract/import、failure/concurrency/replay/rights与cleanup，必要时仅在原3文件内修复validator/test/docs。
- `single_outcome`: 不修改旧BLOCKED历史，重新证明三来源持久Git mirror能稳定支撑100+50+162案例的真实固定Commit链，并形成新的合法Completion Report。
- `observable_results`:
  - `RESULT-001`: 三个source均fresh fetch注册Commit、rev-parse、安全树和只读worktree，persistent mirror保留且临时worktree清理。
  - `RESULT-002`: 两轮结果均为100/50/162、528 source files、312 Generation Examples，固定aggregates和自然键摘要一致。
  - `RESULT-003`: extraction/import复用同一stable mirror root但各自仍执行fresh exact-Commit验证；不创建run内镜像副本。
  - `RESULT-004`: failure injection、并发single writer、replay、rights/internal-only、DB/S3和Compose cleanup通过。
  - `RESULT-005`: cold/warm/partial cache错误保持source/error_code/message可诊断，不输出credentials或删除existing valid mirror。
  - `RESULT-006`: 新offline/live receipts、L4 review、freshness、旧历史保护和唯一Completion Report完整闭合。
- `non_goals`: 不改production adapters/contracts/inventory/content/API/web/sync，不更换固定Commit/count/aggregate，不宣称网络永久稳定，不删除持久cache。

# 3. 需求质疑与确认
- `user_statement`: 继续推进到全部完成；TASK-0012的外部验证不能永久悬空。
- `REQ-001` (`required_behavior`): 新卡/新run独立于旧TASK-0012 identity；旧BLOCKED run和全部evidence byte-preserving只读。
- `REQ-002` (`required_behavior`): exact 3 durable files；若需要production模块、registry/audit、固定Commit或第4个文件变化，停止并报告。
- `REQ-003` (`required_behavior`): source cache固定为workspace外task-neutral root；每次use仍fresh fetch registered commit、rev-parse、safe tree、detached worktree。
- `REQ-004` (`required_behavior`): existing mirror失败不盲删；只有本次新建且不完整的owned mirror可安全清理；所有worktree/package/Compose/DB/S3临时状态清理。
- `REQ-005` (`required_behavior`): live验证必须覆盖三个真实GitHub仓库、两轮extract/import、固定counts/aggregates、failure/concurrency/replay/rights与cache证据。
- `REQ-006` (`required_behavior`): offline验证覆盖shared root、900秒boundary、diagnostics、cold/warm/error cleanup和旧production合同保护。
- `REQ-007` (`required_behavior`): 任一source网络/Commit/shape/hash/count/cleanup失败均保持non-complete并保留底层诊断，不用缓存命中伪装fresh成功。
- `REQ-008` (`required_behavior`): 完成docs/hygiene/protected hash、L4 independent review、terminal freshness与唯一Completion Report。
- `INV-001`: persistent cache是性能状态，不是source authority；authority仍是registry exact Commit与fresh Git证据。
- `INV-002`: 三来源100/50/162、528/312、aggregates、schemas和rights不变。
- `INV-003`: GitHub credentials、Compose secrets和内部临时路径不得泄露到用户JSON。
- `INV-004`: 旧TASK-0012 BLOCKED历史不得被释放、删除或改写。
- `material_ambiguities`: 无；本卡只恢复外部验证和formal closure，不改变原设计。
- `decisions_and_authority`: 用户明确要求继续；独立恢复卡是保留旧阻断真实性时的最小路径。

# 4. 业务场景与规则
- `SCN-001` cold/warm pass: 新建或复用mirror，三source真实链两轮通过。
- `SCN-002` transient network: 新run输出精确source/error并保持non-complete，已有mirror不删。
- `SCN-003` partial owned cache: 只清理由本次创建且无法验证的新不完整mirror。
- `SCN-004` history isolation: 旧TASK-0012仍BLOCKED，新卡有独立receipts/report。
- `RULE-001`: fresh fetch和registered Commit验证不可跳过。
- `RULE-002`: cache保留与ephemeral cleanup必须同时成立。
- `STATE-001`: new run→offline→frozen candidate→live→docs/review/freshness→complete或blocked。
- `risk_sensitive_invariants`: `INV-001`至`INV-004`、exact Commit、existing cache保护、single writer、secret redaction和terminal receipt。
- `inapplicable_faces_with_reason`: 无UI/用户权限/公开写操作；权限面仅限task-owned external runtime清理。

# 5. 当前证据与目标差异
- `FACT-001`: 原3个实现文件已落盘，offline开发检查曾通过；旧formal live在ConardLi cold mirror fetch出现RPC/curl56 early EOF并在三次尝试后BLOCKED。
- `FACT-002`: `C:/Users/admin/.codex/runtime/image2/source-git-v1`是既定persistent mirror root；旧validator明确区分mirror retained和worktree/package/Compose cleanup。
- `FACT-003`: TASK-0010/0011历史已证明三来源固定输出和312库存，但旧实现重复clone导致不稳定；TASK-0012修复只缺可信live closure。
- `ASM-001`: 当前外部网络可能已变化；新run必须自行证明，静态文件和旧失败记录不能替代。
- `current_execution_path`: 旧TASK-0012实现存在，但正式状态BLOCKED且无Completion Report。
- `target_delta`: 用独立新run fresh验证同一3文件并形成合法complete报告。
- `evidence_gaps`: 新offline/live receipts、L4 review、freshness和report。

# 6. 范围与责任边界
- `allowed_write_scope`: `scripts/validate_three_pilot_sources.py`、`tests/ingestion/test_extraction_pipeline.py`、`docs/inventory/internal-inventory-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: TASK-0012旧run/evidence、config/audit/schemas/fixtures、ingestion/inventory production、migrations、compose、content/API/web/sync、1.md、其他tasks/evidence。
- `protected_contracts_and_invariants`: `INV-001`至`INV-004`、fixed Commit/count/aggregate、312 inventory、private rights、persistent cache root。
- `authorization_limits`: 不授权删除existing mirror、修改source authority、放宽Git验证、外部发布或手工伪造receipt。
- `stop_if_scope_expands`: 需要production修复、第4文件、固定事实变化、cache destructive cleanup或GitHub权限。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal runner调用offline pytest和`validate_three_pilot_sources.py`；最终consumer是Phase 1统一验收。
- `expected_touchpoints_or_search_anchors`: 原TASK-0012三文件、persistent cache root、three-source validator CLI。
- `wiring_to_final_consumer`: registry/audit→persistent mirrors→fixed snapshots→three adapters→packages→PostgreSQL/MinIO inventory→JSON receipt→formal report。
- `failure_and_recovery`: 新candidate fresh重跑；network/partial cache输出诊断；existing mirror保留；ephemeral状态finally清理；失败不生成complete report。
- `implementation_freedom`: 当前实现可不改；只有fresh检查暴露原3文件缺陷时作最小修复。
- `selected_profile_obligations`: `external-boundary`覆盖GitHub timeout/error/redaction/cleanup；`stateful-runtime`覆盖persistent cache、concurrency、replay和恢复。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-008`, `INV-001`至`INV-004`
- `owns_behavior`: 三来源持久mirror真实验证与formal recovery。
- `target_delta`: 从旧run BLOCKED到新run fresh complete或新外部阻断。
- `integration_edges`: GitHub→persistent mirrors→extract/import→PostgreSQL/MinIO→formal evidence。
- `expected_touchpoints`: section 6的3文件。
- `business_result`: Phase 1真实来源链不再有未闭合的网络验证债务。
- `behavior_faces`: normal=cold/warm；boundary=3 sources/900s；failure=network/cache/shape/count/DB/S3；permission=owned cache only；repeated=2 runs/replay；downstream=Phase1 closure。
- `state_change`: new run→validated/complete或真实blocked；旧run不变。
- `data_flow`: real Git source→fixed package→inventory facts→machine JSON/receipts。
- `integration_point`: caller=formal runner；callee=Git/Docker/PostgreSQL/MinIO；consumer=Phase1 final audit。
- `scope_boundary`: hard=3 files/old history read-only；soft=无生产功能变化。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-004`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: scope expansion、source authority drift或连续真实网络失败。
- `assembly_not_required_reason`: 一个真实三来源验证恢复切片。

# 9. 验证与验收
- `consumer_chain_validation`: live必须使用真实三个GitHub source并完成DB/S3 inventory；unit/fake或warm object existence不足。
- `real_integration_evidence`: fresh Git fetch、100/50/162、528/312、two runs、failure/concurrency/replay/rights和cleanup JSON。
- `failure_recovery_ownership_validation`: Git owner保护mirror/worktree；validator清理packages/Compose；inventory owners保证DB/S3事务。

### RISK-001
- `description`: warm cache若跳过fresh fetch会把离线成功误报为真实来源成功。
### RISK-002
- `description`: network失败时删除existing mirror会损坏后续恢复能力。
### RISK-003
- `description`: 旧blocked evidence被当pass会污染Phase1最终结论。

### TEST-001
- `links`: `TASK-001`, `REQ-002`至`REQ-006`, `RISK-001`, `RISK-002`
- `method`: 执行原TASK-0012 offline validator，覆盖ingestion/inventory相关tests。
- `expected_observable_result`: stable root、timeout、diagnostic、cold/warm/error/cleanup与旧合同测试通过。
- `failure_path_covered`: unsafe root、partial cache、run lock和cleanup。
- `cannot_prove`: GitHub live。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: 新run terminal receipt和pytest summary。

### TEST-002
- `links`: `TASK-001`, `REQ-003`至`REQ-008`, `INV-001`至`INV-003`, `RISK-001`至`RISK-003`
- `method`: 执行原TASK-0012 exact three-source Compose live命令，两轮、failure injection、concurrency和JSON。
- `expected_observable_result`: 三source fresh通过、100/50/162、528/312、aggregates/replay/rights/cleanup闭合。
- `failure_path_covered`: source-specific network、Git、adapter、DB/S3和cleanup。
- `cannot_prove`: 网络永久可用或后续publication/web。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: 新operation terminal receipt、machine JSON、cache/worktree/package/Compose cleanup。

### TEST-003
- `links`: `TASK-001`, `REQ-001`, `REQ-002`, `REQ-008`, `RISK-003`
- `method`: exact3 files、旧TASK-0012 history hash、docs/hygiene/freshness、L4 independent review和Completion Report validation。
- `expected_observable_result`: 3/3、2 validators、旧BLOCKED只读、review 0 findings、report complete。
- `failure_path_covered`: stale receipt、scope drift、history mutation和runtime residue。
- `cannot_prove`: Phase1其他层。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/history check/review/freshness/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"three-source-cache-recovery-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","tests/ingestion","tests/inventory/test_package.py","-q"],"cwd":".","timeout_seconds":420,"invalidation_paths":["pyproject.toml","uv.lock","ingestion","inventory/package.py","scripts/validate_three_pilot_sources.py","scripts/validate_joesai_multi_source.py","tests/ingestion","tests/inventory/test_package.py","docs/inventory/internal-inventory-v1.md"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["uv","run","--frozen","--no-sync","python","-B","-c","import pytest, jsonschema, psycopg, boto3; print('ready')"],"preflight_timeout_seconds":30},
  {"validator_id":"three-source-cache-recovery-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_three_pilot_sources.py","--registry","config/sources-v1.yaml","--audit","reports/source-audit-v1.json","--g0dam-source-id","g0dam-work-prompts","--g0dam-expected-commit","690c2d6969a65b406b17ba7d41f18695a652c3fe","--g0dam-expected-cases","100","--g0dam-expected-aggregate","ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0","--joesai-source-id","joesai-commercial-prompts","--joesai-expected-commit","6f9b01fd21efbc05cfdde1176fc988013d3c4a9b","--joesai-expected-cases","50","--joesai-expected-aggregate","ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293","--conardli-source-id","conardli-gpt-image-2-101","--conardli-expected-commit","971b67dc8cbca8cf6eb32e196fea04bddd6abe99","--conardli-expected-cases","162","--conardli-expected-aggregate","36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573","--runs","2","--failure-injection","--concurrency","--json"],"cwd":".","timeout_seconds":3600,"invalidation_paths":["config/sources-v1.yaml","reports/source-audit-v1.json","schemas","docs/contracts/content-contract-v1.md","docs/ingestion","docs/inventory/internal-inventory-v1.md","pyproject.toml","uv.lock","ingestion","inventory","migrations","compose.yaml","scripts/validate_three_pilot_sources.py","scripts/validate_joesai_multi_source.py","fixtures/adapters"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["uv","run","--frozen","--no-sync","python","-B","-c","import psycopg, boto3, jsonschema; print('python-ready')"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | recovery offline | OBJ-001 / TASK-001 / TEST-001 | cache/diagnostic/cleanup tests通过 | EV-001 | live |
| GATE-002 | real GitHub live | OBJ-001 / TASK-001 / TEST-002 | 3 sources、312 inventory、两轮与cleanup闭合 | EV-002 | 网络永久稳定 |
| GATE-003 | formal recovery | OBJ-001 / TASK-001 / TEST-003 | 3文件、旧history、docs/review/freshness/report闭合 | EV-003 | Phase1其他层 |

# 10. 产物与完成回写
- `required_deliverables`:
  - `scripts/validate_three_pilot_sources.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `docs/inventory/internal-inventory-v1.md`
- `documentation_impact`: updated only if fresh evidence exposes missing cache/runtime guidance；否则none但文档仍需验证。
- `repository_hygiene_requirement`: exact3 files；无cache/media/package/log/secret入workspace；persistent root只保留mirrors/config/hooks，无worktrees；旧TASK-0012只读。
- `external_review`: policy=never；fresh real GitHub live+L4 independent review足够。
- `non_completion_rules`: 3/3、fresh offline/live、real three-source counts/aggregates、cache/worktree evidence、旧BLOCKED只读、docs/review/freshness/report任一缺失不得完成。

### 必交产物
- `scripts/validate_three_pilot_sources.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `docs/inventory/internal-inventory-v1.md`

本卡完成后执行Phase 1统一验收和`1.md`状态回写。
