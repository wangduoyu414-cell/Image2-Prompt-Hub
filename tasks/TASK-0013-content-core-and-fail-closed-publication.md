---
task_contract_version: 3
card_id: "TASK-0013"
title: "建立Content Core与默认不发布的原子Publication Version"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "stateful-runtime"
  - "persistence-migration"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户要求沿`D:/image2/1.md`持续完成Phase 1纵向闭环；`1.md`第6、8、10、11、12、15、16节；现有`inventory`不可变Source/Evidence模型与`0001/0002`迁移。
- `decision_owner`: 用户拥有总体目标、公开范围和权利判断；执行者只实现Content Core、审核事件和发布版本机制，不代替人工作权利批准。
- `material_unknowns`: 当前三来源没有被用户提供任何可公开的人工权利审核决定，因此真实库存生成0条公开记录是预期结果，不得为制造非空页面而伪造批准。

# 2. 业务目标

- `actor`: 内容供应链维护者、后续只读API和公共网页。
- `workflow_and_trigger`: 已验证的Generation Example进入私有inventory后，系统需要保留全部来源证据，进行保守Canonical分组，保存版本化分类证据和独立权利审核事件，再从完整门禁结果构建不可变Publication Version并原子切换当前版本。
- `single_outcome`: 建立与不可变`inventory`分离的`content`责任边界，使“缺少明确公开许可即不发布”成为数据库和生产代码共同执行的默认行为，同时支持确定性构建、失败保留上一版和回滚。
- `observable_results`:
  - `RESULT-001`: 新增独立`content` schema；不修改、删除或向`inventory`证据表添加发布决策字段。
  - `RESULT-002`: 每个ready Generation Example保留独立membership；只有Prompt、输入、输出和模型声明等关键事实完全相同时才能自动归入同一Canonical Case。
  - `RESULT-003`: 相同Prompt但输出、输入或模型声明不同的Generation Example不会被自动合并；近似内容不自动合并。
  - `RESULT-004`: 分类保存taxonomy/classifier版本、来源层级、confidence和evidence；本卡仅导入明确上游标签和确定性系统Facet，不做推测式内容分类。
  - `RESULT-005`: 权利批准来自独立、追加式人工审核事件；缺失审核、unknown、internal_only或blocked一律不能进入公开版本。
  - `RESULT-006`: Publication Version只包含同时满足完整Prompt、output_primary、strong pairing、完整来源、verified资产、明确展示策略、无blocked标签和准确模型证据的条目。
  - `RESULT-007`: 构建先写staging/ready版本；激活在一个事务中切换current pointer并写outbox event，失败时上一active版本不变。
  - `RESULT-008`: 支持回滚到任一已完成版本；前台后续只需读取current completed Publication Version。
  - `RESULT-009`: Compose集成验证证明显式许可正路径、默认0条、精确重复、不同输出保留、失败保留上一版、回滚和重复构建。
- `non_goals`: 不实现FastAPI、网页、管理后台、图片二进制公开代理、搜索排序、向量相似、自动权利推断、人工审核UI、Git同步或三来源网络重拉取。

# 3. 需求质疑与确认

- `user_statement`: skill项目无需关注，目标是固定高价值、能提取图片与Prompt的长期来源，并持续完成可验证产品链路。
- `REQ-001` (`required_behavior`): 新增`migrations/0003_content_core_publication.sql`，创建独立`content` schema及Canonical、membership、taxonomy assignment、rights review event、publication version/entry、current pointer和outbox所需最小表与约束。
- `REQ-002` (`required_behavior`): migration只能新增Content Core对象；不得改变`inventory`表、不可变trigger、自然键或现有数据。
- `REQ-003` (`required_behavior`): production canonical key必须由规范化原始Prompt、按ordinal的输入/输出内容哈希和稳定序列化的原始model/source claim共同决定；不得只按Prompt合并。
- `REQ-004` (`required_behavior`): Canonical操作只新增或复用分组与membership，永不删除Generation Example、Source Case、Prompt、Asset或来源血缘。
- `REQ-005` (`required_behavior`): exact duplicate可自动同组；不同output/input/model claim必须不同组；近似重复只可记录为待审核候选，本卡不得自动合并。
- `REQ-006` (`required_behavior`): taxonomy assignment记录`taxonomy_version`、`classifier_version`、`tag_source`、`confidence`和`evidence`；优先级和来源必须可区分，blocked标签拥有发布阻断语义。
- `REQ-007` (`required_behavior`): 权利记录必须是Content Core独立追加式review event，至少记录repository license、prompt rights、asset rights、author、original URL、evidence URL、reviewer、reviewed_at和display policy；inventory中的unknown/review_required事实不能升级为批准。
- `REQ-008` (`required_behavior`): display policy只允许`mirror_allowed|attribution_required|link_only|internal_only|blocked`；自动公开候选只接受具有明确人工证据的前三种，其中`link_only`不得产生可镜像资产路径。
- `REQ-009` (`required_behavior`): 发布门逐条验证`1.md`第12.2节最低条件；任一条件缺失均以稳定reason code排除，不能静默降级或自动补事实。
- `REQ-010` (`required_behavior`): Publication Entry保存后续API所需的稳定公开快照和字段级provenance，包括原始Prompt、输出/输入资产描述、来源项目/Commit/位置、rights/display policy、model claim/warning和taxonomy；不得依赖未来可变join改变历史版本含义。
- `REQ-011` (`required_behavior`): build必须在事务中生成完整版本、计算确定性content digest、完成门禁后标记ready；activate在同一事务中更新单一current pointer并追加outbox，任何异常保留上一active版本。
- `REQ-012` (`required_behavior`): rollback只能指向已完成且条目闭合的历史版本，并追加outbox；版本和entry一旦ready/active后禁止修改或删除。
- `REQ-013` (`required_behavior`): 提供稳定Python/CLI边界以执行`canonicalize`、`record-rights-review`、`build-publication`、`activate-publication`、`rollback-publication`和`inspect-publication`；JSON输出含version、digest、included/excluded counts及reason counts，不泄露数据库凭据。
- `REQ-014` (`required_behavior`): offline tests不依赖网络/Docker；live Validator仅使用本地Compose PostgreSQL，直接建立有代表性的不可变inventory seed，不访问GitHub或S3。
- `REQ-015` (`required_behavior`): 文档明确当前三来源无人工批准时真实公开目录应为空；后续API/web不得绕过current completed version或权利门。
- `INV-001`: `inventory`继续是不可变Source/Evidence authority；`content`只能引用它，不能覆盖它。
- `INV-002`: 公开批准必须是显式人工review event；程序、来源license字段或旧`auto_publish=false`不能自行推导批准。
- `INV-003`: Canonical Case是展示分组，不是删除或隐藏Generation Example的手段。
- `INV-004`: 精确去重不得吞掉相同Prompt的不同输出、输入或模型声明。
- `INV-005`: 任何失败都不得留下半成品current版本；上一active版本保持可读。
- `INV-006`: Publication Version历史、entry和outbox是可审计事实；完成后不可原地改写。
- `INV-007`: 本卡不依赖TASK-0012的ConardLi网络验证，因此可在其`Implementation complete; validation pending`期间独立完成。
- `material_ambiguities`: 初始内容语义分类尚无人工标注样本；本卡只建立版本化taxonomy机制并保存明确来源/确定性Facet，不虚构高置信度语义标签。
- `decisions_and_authority`: Content Core与API拆为不同任务，因为写模型/发布事务与公开读取/HTTP缓存具有不同权限、失败和验证边界。

# 4. 业务场景与规则

- `SCN-001` 默认关闭: inventory存在完整案例但没有人工rights review，构建成功且公开条目数为0，excluded reason明确。
- `SCN-002` 正常公开: 显式`mirror_allowed`或`attribution_required`审核且质量门全部满足，条目进入新版本并保留provenance。
- `SCN-003` link only: 显式`link_only`可保留来源链接和Prompt元数据，但publication snapshot不得给出可镜像资产路径。
- `SCN-004` 精确重复: 两个完全相同的Generation Example归入一个Canonical Case但保留两个membership和全部血缘。
- `SCN-005` 不同生成事实: 相同Prompt、不同输出/输入/model claim保持不同Canonical Case与Generation Example。
- `SCN-006` 阻断: blocked/internal/unknown rights、blocked tag、无output_primary、非strong pairing、资产未verified或来源不完整均被排除。
- `SCN-007` 原子失败: 注入build/activate失败后current pointer、旧版本entry和outbox一致，半成品不对consumer可见。
- `SCN-008` 回滚: 激活新版后可事务性切回旧completed版本，consumer只看到回滚目标。
- `SCN-009` 重复执行: 相同输入产生相同canonical keys、entry set和content digest，不产生重复membership或错误多current状态。
- `RULE-001`: 默认拒绝公开；空公开版本是合法产品状态。
- `RULE-002`: 仅current completed version可被后续API读取。
- `RULE-003`: rights review event与publication snapshot分离；新审核只影响新版本，不改写旧版本。
- `RULE-004`: 所有公开字段保存field provenance；未知模型只能以unknown/unverified准确展示。
- `STATE-001`: `inventory ready → canonicalized → classified/reviewed → publication building → ready → active|superseded`；失败版本不可成为current。
- `FLOW-001`: immutable evidence → mutable review decisions → immutable publication snapshot → atomic current pointer/outbox。
- `risk_sensitive_invariants`: 默认关闭、证据不可变、精确而非模糊自动去重、原子激活、可回滚、历史不改写。
- `inapplicable_faces_with_reason`: 无HTTP/UI、公共资产传输或用户认证；这些由后续API/web任务处理。

# 5. 当前证据与目标差异

- `FACT-001`: `0001/0002`已有不可变source_projects、revisions、files、Generation Example、inputs/outputs、pairing和rights evidence，且tests明确禁止publication字段进入inventory。
- `FACT-002`: 当前没有`content`目录、Canonical表、taxonomy表、人工review event或Publication Version。
- `FACT-003`: 当前三来源rights facts均为unknown/review_required且`auto_publish=false`，没有授权公开的人工review event。
- `FACT-004`: `InventoryDatabase.apply_migrations`按文件顺序应用新增SQL，现有迁移机制可承载独立`0003`。
- `FACT-005`: `1.md`要求精确来源追踪、相同Prompt不同结果保留、近似内容不自动合并、原子发布、上一版保留与回滚。
- `ASM-001`: PostgreSQL 18 Compose环境可执行本任务新增约束、transaction和JSONB snapshot；必须由fresh live Validator验证。
- `current_execution_path`: ready inventory止于私有Source/Evidence库存，没有正式公开读取模型。
- `target_delta`: 新增Content Core写模型和current immutable publication read model，为后续API提供唯一合法读取入口。
- `evidence_gaps`: 尚缺迁移、production代码、offline/live tests、正式文档和Completion Report。

# 6. 范围与责任边界

- `allowed_write_scope`: `migrations/0003_content_core_publication.sql`、`content/__init__.py`、`content/database.py`、`content/publication.py`、`content/cli.py`、`content/__main__.py`、`tests/content/test_publication_policy.py`、`tests/content/test_content_database.py`、`scripts/validate_content_core.py`、`docs/content/content-core-publication-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: `inventory`production modules、`0001/0002`、ingestion/adapters/contracts/schemas/fixtures/source registry/audit、TASK-0001至0012及其历史runs、Compose服务定义、三来源counts/commits/aggregates、Git cache。
- `protected_contracts_and_invariants`: `INV-001`至`INV-007`、312 Generation Examples与全部Source/Evidence行不丢失、当前无审批即0公开记录。
- `authorization_limits`: 不授权执行或伪造人工rights批准、不公开真实图片、不写外部系统、不更改权限或删除任何inventory/history数据。
- `stop_if_scope_expands`: 若实现需要修改inventory生产模块/旧migration、改变Compose服务、添加HTTP/API、推断真实权利或删除历史数据，停止并报告新证据。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: 维护者或后续同步任务调用Content CLI/service；生产代码读取ready inventory和latest review events；后续API只读取current completed Publication Version。
- `expected_touchpoints_or_search_anchors`: 新`content`包；`0003` migration；`InventoryDatabase.apply_migrations`无需修改；live Validator用现有Compose PostgreSQL和随机资源名。
- `wiring_to_final_consumer`: `canonicalize → rights/taxonomy evidence → build → activate/rollback → inspect current snapshot`；TASK-0014 API消费inspect/read repository，不重新计算权利门。
- `failure_and_recovery`: DB constraint/门禁/注入失败均回滚当前事务；building/failed版本不对consumer可见；已有active pointer与outbox保持一致；重试幂等。
- `implementation_freedom`: 可调整内部类和SQL局部命名，但文件边界、独立schema、exact key组成、append-only review、fail-closed门、immutable version、atomic pointer/outbox和CLI行为不可改变。
- `selected_profile_obligations`:
  - `stateful-runtime`: 版本状态、current单例、重试、失败回滚、历史版本与outbox一致性。
  - `persistence-migration`: additive migration、重放/漂移、旧表保护、约束和trigger真实验证。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-015`, `INV-001`至`INV-007`
- `owns_behavior`: 从immutable inventory构建保守Canonical、版本化分类/rights review和fail-closed Publication Version。
- `target_delta`: 私有库存之后新增唯一、可审计、可回滚的公开快照责任边界。
- `integration_edges`: PostgreSQL migration → content service/CLI → current publication read model → TASK-0014 API。
- `expected_touchpoints`: section 6列出的10个仓库文件。
- `business_result`: 在不虚构权利许可的前提下，项目首次具备安全发布和回滚能力。
- `behavior_faces`: normal=显式许可；boundary=0 entries/exact duplicate；failure=gate/transaction/activation；permission=review event only；empty=无审批；repeated=幂等；downstream=API只能读current completed。
- `state_change`: entry=ready inventory；exit=active immutable publication或合法空版本；failure=旧active不变。
- `data_flow`: inventory facts + latest explicit reviews + versioned tags → canonical/publication snapshots → pointer/outbox。
- `integration_point`: caller=CLI/sync；trigger=inventory ready/review change；callee=PostgreSQL；return=stable JSON；consumer=API任务。
- `scope_boundary`: hard=不改inventory/HTTP/真实rights；soft=不做高级语义分类、搜索或管理UI。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-009`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: 需要放宽fail-closed、修改旧证据、自动批准rights、模糊自动合并或跨入API责任。

- `assembly_not_required_reason`: 本卡只有一个Content Core发布写链；API和web作为后续独立任务接入其稳定consumer边界。

# 9. 验证与验收

- `consumer_chain_validation`: 必须从真实PostgreSQL inventory seed走到current publication snapshot和inspect JSON；仅测试纯函数不足。
- `real_integration_evidence`: fresh Compose Validator证明migration、constraints、canonical membership、review event、gate、build/activate、failure retention、rollback和migration replay。
- `failure_recovery_ownership_validation`: current pointer、ready/active immutable版本、outbox和旧active在注入失败、重复执行和rollback下保持事务闭合。

### RISK-001
- `description`: 把inventory unknown误当许可会公开未经审核内容；仅独立显式review event可授权。
### RISK-002
- `description`: 仅按Prompt去重会吞掉不同生成结果；exact key必须包含input/output/model facts。
### RISK-003
- `description`: 原地修改active版本会让前台读取半成品；entry冻结后只通过atomic pointer切换。
### RISK-004
- `description`: publication snapshot依赖可变join会改写历史含义；公开字段和provenance必须版本内固化。
### RISK-005
- `description`: Content Core污染inventory会破坏证据边界；migration和protected tests必须证明完全additive。

### TEST-001
- `links`: `TASK-001`, `REQ-003`至`REQ-010`, `RISK-001`, `RISK-002`, `RISK-004`
- `method`: pytest offline，使用纯值和fake repository验证canonical key、gate reason、rights policy、snapshot/provenance、digest和CLI JSON redaction。
- `expected_observable_result`: exact duplicate同key，不同output/input/model不同key；无显式许可/blocked/质量缺失均稳定排除；相同输入digest稳定。
- `failure_path_covered`: unknown rights、link_only镜像泄漏、blocked tag、缺失输出/来源/model evidence、近似误合并。
- `cannot_prove`: 不证明真实PostgreSQL transaction/constraints。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: fresh pytest log及test-to-requirement matrix。

### TEST-002
- `links`: `TASK-001`, `REQ-001`至`REQ-014`, `INV-001`至`INV-007`, `RISK-001`至`RISK-005`
- `method`: `scripts/validate_content_core.py --json`启动隔离Compose project/DB，应用全部migration，直接seed代表性immutable inventory，执行production CLI/service正向、默认0、重复、失败注入和rollback，再清理资源。
- `expected_observable_result`: migration重放verified_existing；unknown-only版本0条；显式批准版本包含预期条目；exact duplicate保留2 memberships；不同输出独立；failure后old current不变；rollback成功；无orphan Compose/DB状态。
- `failure_path_covered`: migration/constraint错误、半成品版本、current双指针、outbox缺失、review缺失、blocked、事务失败、重复执行。
- `cannot_prove`: 不证明GitHub、S3、HTTP、真实人工权利判断或当前312-case live网络链。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: fresh JSON receipt、versions/entries/reasons/digests、pointer/outbox检查、migration replay与cleanup audit。

### TEST-003
- `links`: `TASK-001`, `REQ-015`, `INV-001`至`INV-007`
- `method`: protected scope、docs/hygiene、full regression、freshness、L4 independent review和Completion Report validation。
- `expected_observable_result`: 仅10个声明文件变化；旧inventory migration/module与历史证据不变；全部回归通过；文档声明真实三来源默认0公开；review findings=0。
- `failure_path_covered`: scope drift、doc drift、旧表污染、stale receipts和错误完成声明。
- `cannot_prove`: 不证明后续API/web/sync或TASK-0012外部Git验证。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: file manifest/hash、protected diff、regression log、docs check、review与正式Completion Report。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "content-core-offline",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "tests/content", "tests/inventory", "tests/ingestion", "-q"],
      "cwd": ".",
      "timeout_seconds": 600,
      "invalidation_paths": ["1.md", "pyproject.toml", "uv.lock", "migrations", "content", "inventory", "ingestion", "tests", "docs/content/content-core-publication-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import pytest, psycopg; print('ready')"],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "content-core-compose-live",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_content_core.py", "--json"],
      "cwd": ".",
      "timeout_seconds": 900,
      "invalidation_paths": ["1.md", "compose.yaml", "migrations", "content", "inventory", "tests/content", "scripts/validate_content_core.py", "docs/content/content-core-publication-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": true,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import psycopg; print('python-ready')"],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | offline policy/dedupe | `OBJ-001` / `TASK-001` / `TEST-001` | exact key、fail-closed、snapshot/digest测试通过 | `EV-001` | 不证明DB |
| `GATE-002` | PostgreSQL纵向链 | `OBJ-001` / `TASK-001` / `TEST-002` | migration、0/positive版本、原子失败、回滚和cleanup闭合 | `EV-002` | 不证明网络/HTTP |
| `GATE-003` | formal closure | `OBJ-001` / `TASK-001` / `TEST-003` | scope/docs/regression/review/report闭合 | `EV-003` | 不证明后续任务 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `migrations/0003_content_core_publication.sql`
  - `content/__init__.py`
  - `content/database.py`
  - `content/publication.py`
  - `content/cli.py`
  - `content/__main__.py`
  - `tests/content/test_publication_policy.py`
  - `tests/content/test_content_database.py`
  - `scripts/validate_content_core.py`
  - `docs/content/content-core-publication-v1.md`
- `documentation_impact`: updated；新增Content Core/Canonical/taxonomy/review/publication合同，并明确无显式审核时三来源公开数量为0。
- `repository_hygiene_requirement`: 仅10个声明文件变化；无数据库数据、Compose volume、log、cache、secret或generated receipt进入workspace；formal evidence写TASK-0013 root；旧tasks/runs只读。
- `external_review`: policy=never；fresh PostgreSQL integration加L4 independent review足够，不调用外部模型。
- `non_completion_rules`: 10/10产物、2/2 validators、protected scope、default-zero、positive explicit-rights、dedupe preservation、atomic failure、rollback、docs/review/freshness/report任一缺失不得完成；不得把网络待验证改写为本卡阻点。

### 必交产物

- `migrations/0003_content_core_publication.sql`
- `content/__init__.py`
- `content/database.py`
- `content/publication.py`
- `content/cli.py`
- `content/__main__.py`
- `tests/content/test_publication_policy.py`
- `tests/content/test_content_database.py`
- `scripts/validate_content_core.py`
- `docs/content/content-core-publication-v1.md`

本卡完成后立即创建并执行TASK-0014只读API；TASK-0012的ConardLi网络live验证保留到Phase 1最终统一验收，不阻断本卡。
