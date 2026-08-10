---
task_contract_version: 3
card_id: "TASK-0017A"
title: "修复Content与API live validator对0004 migration的兼容性"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "standard"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "persistence-migration"
  - "external-boundary"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: TASK-0017 fresh blocker evidence；repository `migrations/0001`至`0004`；现有Content Core/Public API validators和tests；用户持续完成Phase1授权。
- `decision_owner`: 用户授权修复过期验收器；production migration与业务合同不改。
- `material_unknowns`: none；修正后Content/API live结果属于本卡必须生成的验证证据，不改变已确定目标、范围或合同。

# 2. 业务目标
- `actor`: Phase1 formal validator与维护者。
- `workflow_and_trigger`: Content Core/Public API live对fresh database应用repository全部migration并重放；validator根据当前repository migration集合判断，而不是硬编码3条。
- `single_outcome`: 让两项受保护live validator正确验证0001至0004完整、不可变、可重放，并继续发现真实Content/API缺陷，不因过期数量断言误阻断Phase1 closure。
- `observable_results`:
  - `RESULT-001`: 两个validator从repository migration files建立期望manifest，首次apply和replay都逐项验证version/checksum/status。
  - `RESULT-002`: 当前0001至0004全部被证明，缺失、额外未记录、checksum drift或非verified replay仍失败。
  - `RESULT-003`: Content Core live和Public API PostgreSQL+MinIO+ASGI live在0004下fresh通过，原有rights/current/asset/failure/cleanup门不减弱。
  - `RESULT-004`: offline tests锁定动态manifest和无硬编码3条回归。
- `non_goals`: 不改migration SQL、Content/API production、sync、web、1.md、formal history或新增功能。

# 3. 需求质疑与确认
- `user_statement`: 继续推进全部完成；真实验收缺陷必须修复而不能绕过。
- `REQ-001` (`required_behavior`): 修复`validate_content_core.py`和`validate_public_api.py`中“恰好3条migration”的断言。
- `REQ-002` (`required_behavior`): expected migrations必须来自当前`migrations/*.sql`的合法有序repository manifest，并与apply/replay结果逐项比较；不得改成“数量>=3”或跳过checksum。
- `REQ-003` (`required_behavior`): 第一次apply允许`applied|verified_existing`，同一DB replay必须全部`verified_existing`且version/checksum与repository一致。
- `REQ-004` (`required_behavior`): 0004 schema实际存在与关键表/列仍由现有Content/API运行路径间接/直接验证；不能只改错误文案使命令通过。
- `REQ-005` (`required_behavior`): tests覆盖4 migration、未来添加一条时动态扩展、缺失/重复/错误version/checksum失败，以及不残留硬编码三条语义。
- `REQ-006` (`required_behavior`): fresh offline、Content live、API live、L3 review、hygiene/freshness和Completion Report全部通过。
- `INV-001`: migration repository files是期望authority；数据库记录不能反向定义仓库期望。
- `INV-002`: migration drift、缺失或replay非verified必须fail closed。
- `INV-003`: Content/API原有业务、rights、current-only、asset authorization和cleanup断言不变。
- `material_ambiguities`: 无；TASK-0017已给出精确失败原因和两个受影响validator。
- `decisions_and_authority`: 使用动态repository manifest是最小且可持续的修复，不新增第五migration或修改production。

# 4. 业务场景与规则
- `SCN-001` current pass: 0001至0004首次apply/replay及业务live通过。
- `SCN-002` future additive: repository新增合法migration时validator自动纳入期望而无需修改数字。
- `SCN-003` drift/failure: checksum/version/missing/replay状态不一致仍阻断。
- `RULE-001`: 适配新增migration不能降低immutable replay验证强度。
- `STATE-001`: repository manifest→apply results→replay results→business live→terminal receipt。
- `risk_sensitive_invariants`: `INV-001`至`INV-003`、full manifest、checksum、fresh DB、cleanup。
- `inapplicable_faces_with_reason`: 无用户权限/UI；外部边界为PostgreSQL/MinIO/ASGI validator runtime。

# 5. 当前证据与目标差异
- `FACT-001`: 0004已由TASK-0016正式迁移并在sync live通过。
- `FACT-002`: TASK-0017 Content live实际应用0004后，仅因validator错误文案`all three immutable repository migrations`失败。
- `FACT-003`: Public API validator存在同类三条migration断言，尚未进入其live阶段。
- `ASM-001`: 修复后若业务live仍失败则为新真实缺陷，本卡不得掩盖。
- `current_execution_path`: validator应用全部SQL，但结果检查仍固定旧数量。
- `target_delta`: 结果检查与repository migration manifest同步。
- `evidence_gaps`: 4文件修改、tests、两项live、review/report。

# 6. 范围与责任边界
- `allowed_write_scope`: `scripts/validate_content_core.py`、`scripts/validate_public_api.py`、`tests/content/test_content_database.py`、`tests/api/test_public_api.py`、本卡formal evidence root。
- `hard_protected_scope`: migrations、Content/API production、sync/web、其他scripts/tests/docs/tasks/formal state、1.md。
- `protected_contracts_and_invariants`: `INV-001`至`INV-003`、0001至0004 SQL/checksums、原Content/API live行为矩阵。
- `authorization_limits`: 不授权改生产或migration、弱化断言、部署或历史evidence。
- `stop_if_scope_expands`: 发现production defect、需第5文件或migration变化。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: formal runner调用两个validator；TASK-0017R/Phase1 closure消费终端receipts。
- `expected_touchpoints_or_search_anchors`: 两validator migration apply/replay断言；两个existing test modules。
- `wiring_to_final_consumer`: repository manifest helper/logic→apply/replay assertions→existing live scenarios→Phase1 closure。
- `failure_and_recovery`: mismatch输出具体version/status/checksum；existing validators负责Compose cleanup；失败不生成complete。
- `implementation_freedom`: helper可各自局部或一致实现，但不得新增文件/共享抽象；四文件与语义固定。
- `selected_profile_obligations`:
  - `persistence-migration`: 定义repository manifest、first apply、replay、checksum drift、未来additive compatibility和fresh DB live。
  - `external-boundary`: 覆盖PostgreSQL/MinIO/ASGI启动、失败传播、timeout、secret redaction和cleanup。

# 8. TASK 与 ASSEMBLY 计划
### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-006`, `INV-001`至`INV-003`
- `owns_behavior`: migration-aware Content/API validation。
- `target_delta`: hardcoded 3→exact current repository manifest。
- `integration_edges`: migration files→DB apply/replay→Content/API live→Phase1 closure。
- `expected_touchpoints`: section 6的4文件。
- `business_result`: 最新migration下真实消费者可以被诚实验收。
- `behavior_faces`: normal=4 migrations；boundary=future additive；failure=drift/missing/status/live；repeated=replay；downstream=TASK-0017R。
- `state_change`: invalid validator→fresh passed validator；生产状态不变。
- `data_flow`: SQL filenames/checksums→result rows→assertions/receipts。
- `integration_point`: caller=formal runner；callee=Content/API live；consumer=closure。
- `scope_boundary`: hard=no production/migration；soft=no refactor。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-003`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: live证实生产缺陷或scope扩张。
- `assembly_not_required_reason`: 同一migration-validation兼容修复切片。

# 9. 验证与验收
- `consumer_chain_validation`: 必须实际运行Content和API live；unit检查字符串不足。
- `real_integration_evidence`: fresh PostgreSQL/MinIO/ASGI、0001至0004 apply/replay与原场景矩阵。
- `failure_recovery_ownership_validation`: validators清理Compose；本卡不改production state。
### RISK-001
- `description`: 仅把3改4会在下一migration再次失效。
### RISK-002
- `description`: 动态数量但不比较version/checksum会掩盖drift。
### RISK-003
- `description`: 断言修复可能暴露真实0004 consumer兼容问题。
### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-005`, `RISK-001`, `RISK-002`
- `method`: pytest两个目标test modules，验证manifest/apply/replay/drift与原合同。
- `expected_observable_result`: tests通过，缺失/错误fixture失败。
- `failure_path_covered`: future additive、checksum/status/version mismatch。
- `cannot_prove`: services live。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: pytest terminal receipt和case matrix。
### TEST-002
- `links`: `TASK-001`, `REQ-002`至`REQ-006`, `INV-001`至`INV-003`, `RISK-003`
- `method`: fresh执行Content Core和Public API live validators。
- `expected_observable_result`: 0001至0004 apply/replay、业务场景和cleanup全部通过。
- `failure_path_covered`: real DB/S3/ASGI/migration compatibility。
- `cannot_prove`: Web/Phase1总体。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: 两项terminal receipts、JSON和cleanup。
### TEST-003
- `links`: `TASK-001`, `REQ-006`
- `method`: exact4 scope/protected hashes、L3 review、freshness和Completion Report。
- `expected_observable_result`: 4/4、3 validators、review 0 findings、report complete。
- `failure_path_covered`: scope/stale evidence/runtime residue。
- `cannot_prove`: Phase1 closure doc。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/review/freshness/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"migration-validator-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","tests/content/test_content_database.py","tests/api/test_public_api.py","-q"],"cwd":".","timeout_seconds":300,"invalidation_paths":["migrations","scripts/validate_content_core.py","scripts/validate_public_api.py","tests/content/test_content_database.py","tests/api/test_public_api.py"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"content-core-migration-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_content_core.py","--json"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["migrations","content","inventory","scripts/validate_content_core.py","tests/content","docs/content/content-core-publication-v1.md"],"validation_kind":"behavior","environment_sensitive":true},
  {"validator_id":"public-api-migration-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_public_api.py","--json"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["migrations","content","inventory","apps/api","scripts/validate_public_api.py","tests/api","docs/api/public-api-v1.md"],"validation_kind":"behavior","environment_sensitive":true}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | manifest/replay tests | OBJ-001 / TASK-001 / TEST-001 | dynamic exact manifest tests通过 | EV-001 | live |
| GATE-002 | latest migration consumers | OBJ-001 / TASK-001 / TEST-002 | Content/API live与cleanup通过 | EV-002 | Web/Phase1 |
| GATE-003 | formal repair | OBJ-001 / TASK-001 / TEST-003 | 4文件/review/freshness/report闭合 | EV-003 | closure doc |

# 10. 产物与完成回写
- `required_deliverables`:
  - `scripts/validate_content_core.py`
  - `scripts/validate_public_api.py`
  - `tests/content/test_content_database.py`
  - `tests/api/test_public_api.py`
- `documentation_impact`: none；现有Content/API文档已声明repository migrations与live命令，本卡只修验收器实现，理由写入Completion Report。
- `repository_hygiene_requirement`: exact4 files；Compose/runtime/log workspace外清理；production/migrations/history只读。
- `external_review`: policy=never；两项fresh live+L3 independent review足够。
- `non_completion_rules`: 4/4、dynamic exact manifest、offline、Content live、API live、原业务断言、cleanup/review/freshness/report任一缺失不得完成。

### 必交产物
- `scripts/validate_content_core.py`
- `scripts/validate_public_api.py`
- `tests/content/test_content_database.py`
- `tests/api/test_public_api.py`

完成后创建并执行TASK-0017R重新关闭Phase1。
