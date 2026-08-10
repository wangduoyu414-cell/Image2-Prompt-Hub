---
task_contract_version: 3
card_id: "TASK-0016"
title: "交付三类正式来源的安全 Commit 更新与增量同步闭环"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "stateful-runtime"
  - "persistence-migration"
  - "external-boundary"
  - "public-contract"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户要求持续推进至Phase 1全部完成；`1.md`第3、4、5、8、12、15、16节；`config/sources-v1.yaml`三类active pilot；TASK-0012持久Git mirror、TASK-0013 fail-closed Publication Version、TASK-0014/0015 current-only公共消费链。
- `decision_owner`: 用户拥有长期来源、公开范围和权利判断；同步程序只发现、验证和保留修订证据，不自动批准rights、不改变来源准入结论。
- `material_unknowns`: 三个GitHub默认分支在执行时是否已有新Commit属于外部动态事实；本卡必须以本地受控双Commit仓库证明完整行为，真实GitHub检测留在本卡live或Phase 1最终统一验收中据实记录，不得伪造更新。

# 2. 业务目标
- `actor`: 维护高价值GPT Image案例来源的运营者与后续定时调度器。
- `workflow_and_trigger`: 对一个`active + sync.enabled + full ingestion + canonical`来源执行一次同步；系统读取远端默认分支、固定候选Commit、全量重解析当前仓库版本、计算集合差异、增量复用图片对象、写入不可变库存、构建候选发布并在安全门通过时原子切换。
- `single_outcome`: 交付可重复调用、可诊断、fail-closed的单来源Commit更新管线，使三类pilot从初始固定Commit能力升级为可长期更新，同时任何远端、解析、质量、rights、发布或并发失败都保留上一公开版本和历史证据。
- `observable_results`:
  - `RESULT-001`: 精确检测远端默认分支Commit；未变化返回`no_change`且不重复解析、入库或发布。
  - `RESULT-002`: 新Commit必须经fresh fetch、40位SHA、对象存在、安全树、fast-forward与只读worktree验证，并建立内部保留ref；Force Push/非快进进入人工处理状态。
  - `RESULT-003`: 当前仓库版本全量解析；与上次已入库版本按稳定case identity和语义指纹输出added/modified/removed/unchanged，删除形成持久tombstone，不物理删除旧证据。
  - `RESULT-004`: 图片仍按SHA-256内容寻址；重复对象验证但不覆盖，仅新增内容hash产生新对象写入。
  - `RESULT-005`: 零案例、低于来源准入最小数量、pair rate不足、broken asset、Schema/parse错误、任意案例数量下降或removed case均阻止自动发布并保留上一版。
  - `RESULT-006`: 新修订不继承或伪造旧Generation Example的人工rights approval；候选发布只使用新修订的显式review event，缺失审核保持排除。
  - `RESULT-007`: 候选Publication Version显式冻结各来源修订选择；build失败或候选会丢失已公开Canonical Case时不切换current；安全候选的publication pointer和outbox原子更新。
  - `RESULT-008`: 同一source+candidate Commit重复调用幂等；同来源并发只有一个writer；失败后可重试并从已验证的immutable package/inventory继续。
  - `RESULT-009`: CLI提供稳定JSON状态、Commit、diff、quality gate、inventory、publication和error code，不泄露凭据、内部对象路径或临时authority文件。
  - `RESULT-010`: 三种adapter均用本地受控两修订Git仓库走通detect→extract→import→canonicalize→build→activate/no-change，并覆盖非快进、删除、失败注入、并发、rights与cleanup。
- `non_goals`: 不实现定时器、队列worker、管理后台、GitHub webhook、自动rights审核、自动来源准入/退役、语义模型分类、生产部署或接入全部probation来源。

# 3. 需求质疑与确认
- `user_statement`: 固定高价值且可稳定提取Prompt与图片的项目作为长期内容来源，持续维护更新；Phase 1必须完成Commit更新同步而非停在固定快照。
- `REQ-001` (`required_behavior`): 初始`verified_commit_sha`与source audit继续作为来源准入和历史基线，自动同步不得回写或悄悄移动`config/sources-v1.yaml`、`reports/source-audit-v1.json`或历史fixture。
- `REQ-002` (`required_behavior`): 候选修订authority必须由已注册source identity、default branch、fresh Git fetch所得SHA、fast-forward关系和run-scoped evidence组成；不得仅信任远端字符串、moving HEAD或调用者任意SHA。
- `REQ-003` (`required_behavior`): Git mirror仍是workspace外持久cache；不执行hook/submodule/build/install；候选成功入库后创建不可移动的内部保留ref，临时worktree始终清理。
- `REQ-004` (`required_behavior`): 提供新的`sync`边界负责detect、run state、diff、quality gate和跨现有extract/import/content编排；现有adapter仍只解析固定只读snapshot，不拥有同步状态或发布决策。
- `REQ-005` (`required_behavior`): run-scoped revision evidence可在workspace外生成，但必须可由静态registry+audit、fetched Commit和候选metrics确定性重建；不得持久化为新的来源准入事实或绕过v1 schema/semantic validators。
- `REQ-006` (`required_behavior`): 新Commit仍产生完整immutable extraction package和inventory revision；不得用Markdown局部diff直接拼接生产Generation Example。
- `REQ-007` (`required_behavior`): diff以`source_case_key`为集合identity，以Prompt、输入/输出hash、generation claim和强配对事实的稳定摘要判断modified；仅路径/运行时间不得制造modified。
- `REQ-008` (`required_behavior`): removed case写入sync tombstone并保留旧inventory/package/object；后续同identity恢复时可记录恢复，不删除历史。
- `REQ-009` (`required_behavior`): Phase 1自动质量门取现有registry的`minimum_valid_cases`和`minimum_pair_rate`；`broken_asset_count`必须为0；相对上次已入库修订的case count不得下降。任何下降或removed必须`review_required`，本卡不自行接受内容收缩风险。
- `REQ-010` (`required_behavior`): 通过质量门后才允许inventory import；S3/DB失败不得创建ready inventory，已存在对象不覆盖，重复包返回verified existing。
- `REQ-011` (`required_behavior`): Content build必须接受显式、完整的source revision selection并把它冻结在Publication Version；不能从“数据库最新revision”或所有ready runs隐式推断。
- `REQ-012` (`required_behavior`): 新/变更Generation Example没有新的显式rights review时必须排除；旧row的approval不得自动复制到新row。候选比current少任何已公开Canonical Case时自动activation阻断并标记`review_required`。
- `REQ-013` (`required_behavior`): 安全activation在同一PostgreSQL事务中更新Publication current、outbox和对应sync完成关联；注入pointer/outbox失败时全部回滚，API/web继续读取旧current。
- `REQ-014` (`required_behavior`): run状态至少覆盖detected/no_change/extracting/imported/gated/review_required/ready/completed/failed，并持久记录source、previous/candidate Commit、diff/metrics/reason和publication id；失败可诊断且可重试。
- `REQ-015` (`required_behavior`): 同一source+candidate Commit使用稳定idempotency key和数据库/advisory ownership；并发第二writer快速失败或读取已完成结果，不产生两次发布。
- `REQ-016` (`required_behavior`): 提供`python -m sync run-source ... --json`与`inspect-source`维护入口；一次命令只处理一个source，不隐式遍历或修改其他来源。
- `REQ-017` (`required_behavior`): 文档明确初始审计Commit、候选revision evidence、last ingested、tombstone、candidate publication、current publication和rights review的不同authority。
- `REQ-018` (`required_behavior`): 完成offline/live、L4独立语义复核、docs/hygiene/freshness和唯一Completion Report；非Git仓库不commit。
- `INV-001`: Source/Evidence历史不可变；自动同步只追加revision/run/case version/tombstone，不改写旧证据。
- `INV-002`: v1 contract仍绑定一个确定Commit；动态同步通过run-scoped确定Commit authority，不放宽为branch/HEAD。
- `INV-003`: 静态来源准入和动态修订处理是两种authority，不得混写。
- `INV-004`: public API/web只读current completed Publication Version；inventory最新数据不能直接公开。
- `INV-005`: rights approval按Generation Example row显式追加；程序不得推导或迁移批准。
- `INV-006`: 任何失败、质量下降、公开集合下降、非快进或并发冲突都不能改变上一current publication。
- `material_ambiguities`: 设计文档要求“允许下降阈值”但当前registry未提供数值；Phase 1采用最保守的0自动下降阈值，任何下降交人工复核，不新增未经用户确认的风险容忍配置。
- `decisions_and_authority`: `1.md`确认全量重解析、集合差异、内容寻址、tombstone、幂等、原子发布和失败保留上一版；本卡把这些落实为单来源one-shot管线，调度留Phase 4。

# 4. 业务场景与规则
- `Business Object`: Source Sync Run；关联Source、previous/candidate Source Revision、immutable package/inventory、case diff/tombstone、candidate Publication Version和current Publication Version。
- `User Workflow`: operator/未来scheduler调用一个source→检测→无变化结束，或固定新Commit→解析/门禁/入库→候选发布→安全激活或review_required。
- `STATE-001`: `detected → no_change | extracting → imported → gated → ready → completed`；任一阶段可`failed`，非快进/下降/rights/public-loss为`review_required`。
- `FLOW-001`: static registry+audit + remote default branch → fetched candidate authority → full extraction package → verified inventory revision → stable diff/quality gates → explicit revision-selected publication → atomic current/outbox。
- `REL-001`: 初始审计Commit与候选Commit是“准入基线→后续修订”的证据关系，不是自动批准或配置覆盖关系。
- `REL-002`: last ingested revision表示内部处理成功，不等于当前公开revision；公开状态只由Publication Version选择和current pointer定义。
- `PERM-001`: 只有显式rights review event可授予公开资格；sync writer没有批准权限。
- `SCN-001` 无变化: remote SHA等于last ingested/baseline，返回no_change，无新package/run side effect之外的内容写入。
- `SCN-002` 安全新增/修改: fast-forward、新数量不降、质量通过、公开集合不损失，完成新revision和publication原子切换。
- `SCN-003` 删除/下降/非快进: 新证据可保留或运行可诊断，但current publication不变，状态review_required。
- `SCN-004` 失败/并发: Git、adapter、asset、DB、publication和第二writer失败均保留旧current，清理临时状态，可安全重试。
- `RULE-001`: full-reparse + set-diff，禁止局部拼补。
- `RULE-002`: previously published case loss是自动发布阻断，不以“成功生成空版本”覆盖内容。
- `RULE-003`: no_change/retry/concurrent invocation必须确定性、幂等、可恢复。
- `risk_sensitive_invariants`: `INV-001`至`INV-006`、fast-forward、retained ref、explicit selection、rights row binding、atomic pointer/outbox、secret redaction。
- `inapplicable_faces_with_reason`: 本卡无UI、用户账户、定时调度或外部消息投递；CLI是唯一入口，scheduler只作为未来consumer。

## Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| DEP-001 | static active Source | candidate Commit | data derivation | registry default branch + fresh Git evidence | confirmed | 不意味着候选自动获准公开 | detect/extract |
| DEP-002 | previous inventory revision | candidate inventory revision | comparison | `1.md` 8.3/8.5 | confirmed | 不意味着局部patch | diff/gate |
| DEP-003 | candidate inventory selection | candidate Publication Version | data derivation | TASK-0013 + `1.md` 8.4 | confirmed | 不意味着current已切换 | build |
| PERM-001 | rights review event | publication entry | permission | TASK-0013 | confirmed | source license/旧review不能替代新row review | publication gate |
| DEP-004 | candidate Publication Version | current Publication Version | state transition | TASK-0013 | confirmed | ready不意味着active | activation/outbox |

## Module Boundary

| module | owns | reads | writes | emits | consumes | must not do | authority source |
|---|---|---|---|---|---|---|---|
| `ingestion.git_snapshot` | Git mirror、fetch、safe tree、worktree、retained ref | registered repo/branch/SHA | workspace外Git cache | verified SHA/ref facts | sync revision detector、extract/import | 解析内容或批准发布 | TASK-0012/current code |
| `sync.revision` | candidate revision evidence与fast-forward判定 | static registry/audit + Git facts | workspace外run evidence | deterministic candidate authority | sync pipeline | 回写静态准入文件 | `REQ-001`至`REQ-005` |
| `sync.database` | sync run/idempotency/diff/tombstone状态 | inventory/content identity | `sync` schema | stable inspect data | sync pipeline/CLI | 改写inventory历史或publication snapshot | `INV-001`, `STATE-001` |
| `sync.pipeline` | one-shot orchestration和quality/loss gates | revision/package/inventory/content results | run state；调用现有owners | CLI JSON result | CLI/未来scheduler | 自己解析adapter、直接写S3或绕过rights | `FLOW-001` |
| `content.database` | explicit selection Publication build与atomic activation | selected ready inventory + rights | immutable publication/current/outbox | active snapshot | API/web | 选择任意latest inventory或复制rights | TASK-0013/0014 |

# 5. 当前证据与目标差异
- `FACT-001`: `ingestion.git_snapshot.fixed_snapshot`已使用workspace外mirror、fresh exact-Commit fetch、安全树和finally worktree cleanup，但没有默认分支更新检测、fast-forward判定或保留ref公共边界。
- `FACT-002`: `ingestion.pipeline.extract`、`inventory.importer.import_package`已对一个registry fixed Commit提供完整package→asset→ready inventory幂等链；静态audit metrics要求精确匹配初始Commit。
- `FACT-003`: inventory保存多Source Revision且不改写历史，但没有同步run、last ingested、case diff或tombstone状态。
- `FACT-004`: `content.database`当前对所有ready Generation Example canonicalize/build，Publication Version未保存显式source revision selection，也没有candidate-vs-current公开集合损失门。
- `FACT-005`: API/web只读current Publication Version，因此只要current pointer不变，内部新revision或失败不会直接公开。
- `FACT-006`: 当前三个pilot最低valid cases为50、minimum pair rate为0.9、default branch均为main、sync enabled且auto_publish=false。
- `ASM-001`: 本地Git双Commit仓库足以证明revision detection、fast-forward、retained ref和三adapter更新行为；真实GitHub网络只证明外部可达性和当前SHA。
- `current_execution_path`: operator分别调用fixed extract/import/content命令；没有一个入口检测Commit或协调候选发布。
- `target_delta`: 新增`sync`控制面，复用现有fixed boundaries，并让Publication Version显式绑定修订选择与安全切换。
- `evidence_gaps`: 尚缺实现、migration、三adapter双revision live、非快进/删除/并发/失败/rights/loss证据、文档与Completion Report。

# 6. 范围与责任边界
- `allowed_write_scope`: `migrations/0004_incremental_sync.sql`、`sync/__init__.py`、`sync/__main__.py`、`sync/cli.py`、`sync/revision.py`、`sync/database.py`、`sync/pipeline.py`、`ingestion/git_snapshot.py`、`content/database.py`、`tests/sync/test_revision_sync.py`、`tests/sync/test_sync_database.py`、`tests/ingestion/test_registry_and_snapshot.py`、`tests/content/test_content_database.py`、`scripts/validate_incremental_sync.py`、`docs/sync/incremental-sync-v1.md`、`docs/content/content-core-publication-v1.md`、`docs/inventory/internal-inventory-v1.md`、`docs/contracts/content-contract-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: `config/sources-v1.yaml`、`reports/source-audit-v1.json`、schemas、fixtures、adapters、ingestion contracts/pipeline/registry/assets/CLI、inventory production modules、migrations 0001至0003、apps/api、apps/web、compose、1.md、TASK-0001至0015与历史evidence、fixed counts/aggregates。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、三个adapter v1 outputs、312 baseline inventory、default-zero real publication、API/web current-only、S3 private/content-addressed、no secret。
- `authorization_limits`: 不授权自动rights批准、接受内容下降、改来源准入、部署、调度外部任务、删除Git mirror/package/inventory/object或写外部系统。
- `stop_if_scope_expands`: 若必须改adapter/schema/static registry/audit、放宽v1 fixed revision语义、自动继承rights、允许公开集合下降、物理删除历史或修改API/web，停止并报告。

# 7. 实现蓝图与文件边界
- `blueprint_status`: confirmed
- `caller_entry_consumer`: operator调用`python -m sync run-source`；未来scheduler复用同一one-shot入口；最终consumer仍是API/web读取的current Publication Version。
- `expected_touchpoints_or_search_anchors`: `fixed_snapshot/_ensure_mirror`、`extract`、`import_package`、`InventoryDatabase.inspect`、`ContentDatabase.canonicalize/build_publication/activate_publication/inspect_publication`、0001至0003 migration。
- `wiring_to_final_consumer`: CLI→sync pipeline→Git candidate→existing extraction/import→sync DB diff/gate→content explicit-selection build/activate→API/web current read。
- `failure_and_recovery`: 每阶段先写可诊断run state；candidate package/inventory是immutable并可复用；build/activation失败不改current；并发使用稳定lock；临时authority/worktree cleanup；retry对同key返回既有状态或继续未完成阶段。
- `implementation_freedom`: 可选择run-scoped authority envelope的具体序列化和内部函数，只要静态authority不变、候选Commit由Git证明、现有v1 validators未放宽、18个文件边界和全部门禁成立。
- `selected_profile_obligations`: `stateful-runtime`覆盖状态/幂等/并发/恢复；`persistence-migration`覆盖sync tables与Publication selection/backfill/rollback；`external-boundary`覆盖Git/S3/DB timeout/error/cleanup/redaction；`public-contract`覆盖CLI JSON、Publication Version selection和API current兼容。

### 文件布局决策

- `strategy`: split；`target_area`: TASK-0016 Commit更新与增量同步。
- `production_files`: `sync/revision.py`只拥有Git候选authority；`sync/database.py`只拥有持久run/diff/tombstone；`sync/pipeline.py`拥有跨边界编排与门禁；`sync/cli.py`是入口；`ingestion/git_snapshot.py`保留Git副作用owner；`content/database.py`保留Publication持久化owner。
- `why_not_fewer`: 把Git、同步状态、业务门禁和Publication SQL塞进一个文件会混合四类失败/恢复与测试边界。
- `why_not_more`: diff、quality、types和JSON mapper当前只有sync pipeline一个consumer，保持局部；不创建service/repository/utils层或scheduler抽象。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-010`, `INV-001`至`INV-003`, `SCN-001`至`SCN-004`
- `owns_behavior`: 候选Commit检测、fast-forward/retention、full extraction/import、diff/quality/tombstone和run幂等。
- `target_delta`: 从只能处理registry baseline Commit到可安全处理后续确定Commit并形成ready内部revision。
- `integration_edges`: Git mirror→run-scoped revision evidence→existing extract/import→sync schema。
- `expected_touchpoints`: migration、sync package、`ingestion/git_snapshot.py`及对应tests/docs。
- `business_result`: active source的新内容可进入可追溯内部库存，异常和删除不会破坏历史。
- `behavior_faces`: normal=new fast-forward；boundary=no_change/minimum count；failure=Git/adapter/S3/DB/non-fast-forward/drop；permission=无rights写权；empty=zero block；repeated/concurrent=idempotent single writer；downstream=候选revision供TASK-002。
- `state_change`: baseline/last ingested→candidate run→imported/gated或no_change/review_required/failed；失败不改变public current。
- `data_flow`: static authority+Git→package→inventory→diff/tombstone/run state。
- `integration_point`: caller=CLI；callee=Git/extract/import/PostgreSQL/S3；return=stable JSON；consumer=TASK-002/未来scheduler。
- `scope_boundary`: hard=不改adapters/static authority/old evidence；soft=无scheduler/admin。
- `allowed_write_scope`: section 6中除`content/database.py`和content docs/tests外的同步相关文件。
- `acceptance_scenarios`: `SCN-001`, `SCN-002`的内部部分, `SCN-003`, `SCN-004`的Git/import部分。
- `linked_tests`: `TEST-001`, `TEST-002`
- `stop_conditions`: 需要移动static Commit、放宽contract或删除历史。

### TASK-002
- `links`: `OBJ-001`, `REQ-011`至`REQ-018`, `INV-004`至`INV-006`, `SCN-002`至`SCN-004`
- `owns_behavior`: 显式revision selection候选发布、rights/public-loss门和原子activation/outbox。
- `target_delta`: Publication build从隐式所有ready inventory改为显式修订集合；sync失败或内容损失不切current。
- `integration_edges`: imported candidate revision→canonicalize→candidate Publication Version→atomic current/outbox→API/web。
- `expected_touchpoints`: migration、`content/database.py`、sync pipeline及content/sync tests/docs。
- `business_result`: 更新成功时网站原子看到新安全版本，任何风险时继续看到上一版。
- `behavior_faces`: normal=safe activation；boundary=current empty/candidate equal；failure=build/activation/outbox/loss；permission=rights row only；empty=合法0但不得覆盖非0；repeated=already-current/retry；downstream=API/web current-only。
- `state_change`: imported/gated→ready publication→completed，或review_required/failed；current只在最终事务改变。
- `data_flow`: explicit source revision selection+rights→immutable snapshot→pointer/outbox→API。
- `integration_point`: caller=sync pipeline；callee=ContentDatabase；return=version/digest/count/reasons；consumer=API/web和sync inspect。
- `scope_boundary`: hard=不改API snapshot shape、rights语义或旧publication；soft=无人工审核UI。
- `allowed_write_scope`: `migrations/0004_incremental_sync.sql`、`content/database.py`、相关tests/docs与sync pipeline。
- `acceptance_scenarios`: `SCN-002`, `SCN-003`, `SCN-004`的publication部分。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: 需要rights继承、允许公开集合下降或API变化。

### ASSEMBLY-001
- `participating_tasks`: `TASK-001`, `TASK-002`
- `end_to_end_entry`: `python -m sync run-source`。
- `shared_contract_state_data`: `FLOW-001`, `STATE-001`, `INV-001`至`INV-006`所定义的source/candidate revision、run state、diff/tombstone、explicit publication selection、rights和current/outbox。
- `final_consumer`: TASK-0014 API与TASK-0015网页读取新的current Publication Version。
- `cross_task_failure_path`: candidate Git/package/inventory可以保留并重试；quality/rights/public-loss/build/activation失败不得改变current；run state必须解释停点。
- `linked_test_evidence_gate`: `TEST-002` / `EV-002` / `GATE-002`

# 9. 验证与验收
- `consumer_chain_validation`: 必须从真实Git repository双Commit、真实adapter、PostgreSQL、MinIO走到current Publication Version，并用现有API repository或inspect确认current选择；纯diff/unit或只测migration不足。
- `real_integration_evidence`: 三adapter本地Git更新、no_change、object reuse/new hash、312 baseline兼容、candidate selection、rights default-zero、synthetic approved positive、removed/loss block、non-fast-forward、failure injection、concurrency、retry、cleanup。
- `failure_recovery_ownership_validation`: Git cleanup/retention由Git owner；package/inventory由现有owners；sync run/diff/tombstone由sync DB；publication rollback/current/outbox由Content DB。

### RISK-001
- `description`: 将branch/HEAD当authority会产生TOCTOU和不可重放证据。
### RISK-002
- `description`: 隐式选择所有ready revisions会把旧/新或被删除案例混入候选发布。
### RISK-003
- `description`: 自动继承rights或允许候选公开集合下降会越过人工授权并导致网站内容无声消失。
### RISK-004
- `description`: activation与sync state/outbox非原子或并发无锁会产生current与运行结果不一致。

### TEST-001
- `links`: `TASK-001`, `TASK-002`, `REQ-001`至`REQ-018`, `RISK-001`至`RISK-004`
- `method`: 运行sync/Git/content offline pytest，覆盖authority构造、稳定diff、quality gates、state transition、tombstone、selection、rights/loss、idempotency、failure和redaction。
- `expected_observable_result`: unit/contract测试通过，旧fixed-Commit/312/API/web contracts未改变。
- `failure_path_covered`: invalid SHA、non-fast-forward、zero/drop、duplicate run、build/activation failure、missing review。
- `cannot_prove`: 不证明真实PostgreSQL/MinIO/进程/Git集成。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: pytest log、scenario matrix、protected regression结果。

### TEST-002
- `links`: `ASSEMBLY-001`, `TASK-001`, `TASK-002`, `REQ-002`至`REQ-018`, `INV-001`至`INV-006`
- `method`: `scripts/validate_incremental_sync.py --json`创建workspace外三类本地Git双Commit源和runtime，启动fresh PostgreSQL+MinIO，执行baseline→new→no_change，并注入removed/non-fast-forward/Git/import/build/activation/concurrency场景。
- `expected_observable_result`: 三adapter均完成full chain；diff/count/hash/selection/outbox/current正确；已有对象不覆盖、新对象一次写入；风险场景current不变；临时repo/worktree/package/Compose/DB/S3清理，persistent test mirror按owned root处理。
- `failure_path_covered`: external Git、adapter drift、asset/DB、quality、rights/loss、transaction、concurrency、retry和cleanup。
- `cannot_prove`: 不证明真实GitHub当日可达、scheduler或全部active来源。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: machine JSON含每source previous/candidate、diff、metrics、objects、inventory/publication IDs、current before/after、outbox、failure assertions、concurrency和cleanup；不得含secret。

### TEST-003
- `links`: `TASK-002`, `REQ-017`, `REQ-018`, `RISK-001`至`RISK-004`
- `method`: 18文件scope/protected hash、全回归、docs/hygiene/freshness、L4 independent semantic review和Completion Report official validation。
- `expected_observable_result`: 18/18、2/2 formal validators、旧合同/网页无回归、review 0 findings、report complete。
- `failure_path_covered`: scope expansion、文档authority混淆、stale evidence、漏清理。
- `cannot_prove`: 不证明Phase 4长期调度。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: file/protected manifests、receipts、docs check、review、freshness和Completion Report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"incremental-sync-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","tests/sync","tests/ingestion/test_registry_and_snapshot.py","tests/content/test_content_database.py","-q"],"cwd":".","timeout_seconds":900,"invalidation_paths":["migrations","sync","ingestion/git_snapshot.py","content/database.py","tests/sync","tests/ingestion/test_registry_and_snapshot.py","tests/content/test_content_database.py","docs/sync/incremental-sync-v1.md","docs/content/content-core-publication-v1.md","docs/inventory/internal-inventory-v1.md","docs/contracts/content-contract-v1.md"],"validation_kind":"behavior","environment_sensitive":false},
  {"validator_id":"incremental-sync-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_incremental_sync.py","--json"],"cwd":".","timeout_seconds":2400,"invalidation_paths":["compose.yaml","config/sources-v1.yaml","reports/source-audit-v1.json","migrations","sync","ingestion","inventory","content","scripts/validate_incremental_sync.py","fixtures/adapters","schemas","docs/sync/incremental-sync-v1.md","docs/content/content-core-publication-v1.md","docs/inventory/internal-inventory-v1.md","docs/contracts/content-contract-v1.md"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | offline contracts/state | OBJ-001 / TASK-001 / TASK-002 / TEST-001 | authority/diff/gates/selection/rights/idempotency测试通过 | EV-001 | live services |
| GATE-002 | three-adapter full assembly | OBJ-001 / ASSEMBLY-001 / TASK-001 / TASK-002 / TEST-002 | Git→inventory→publication全链与全部风险场景通过 | EV-002 | scheduler/全部来源 |
| GATE-003 | formal closure | OBJ-001 / TASK-001 / TASK-002 / TEST-003 | 18文件、regression、docs、review、freshness、report闭合 | EV-003 | Phase 4运营 |

# 10. 产物与完成回写
- `required_deliverables`:
  - `migrations/0004_incremental_sync.sql`
  - `sync/__init__.py`
  - `sync/__main__.py`
  - `sync/cli.py`
  - `sync/revision.py`
  - `sync/database.py`
  - `sync/pipeline.py`
  - `ingestion/git_snapshot.py`
  - `content/database.py`
  - `tests/sync/test_revision_sync.py`
  - `tests/sync/test_sync_database.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `tests/content/test_content_database.py`
  - `scripts/validate_incremental_sync.py`
  - `docs/sync/incremental-sync-v1.md`
  - `docs/content/content-core-publication-v1.md`
  - `docs/inventory/internal-inventory-v1.md`
  - `docs/contracts/content-contract-v1.md`
- `documentation_impact`: updated；区分static admission、run-scoped revision authority、last ingested、tombstone、explicit publication selection、rights和current。
- `repository_hygiene_requirement`: 只改18个durable文件；runtime Git/worktree/package/log/Compose状态必须在workspace外并清理owned ephemeral；不删除已有persistent source cache；旧task/evidence只读。
- `external_review`: policy=never；三adapter真实services live加L4 independent semantic review足够，不调用外部模型。
- `non_completion_rules`: 18/18产物、2/2 validators、三adapter双revision、no_change/diff/object reuse、zero/drop/remove/non-fast-forward、rights/public-loss、build/activation failure、concurrency/retry/cleanup、protected regression、docs/review/freshness/report任一缺失不得完成；真实GitHub网络若仅影响外部可达验证，记录并留到Phase 1统一验收，不得宣称已通过。

### 必交产物
- `migrations/0004_incremental_sync.sql`
- `sync/__init__.py`
- `sync/__main__.py`
- `sync/cli.py`
- `sync/revision.py`
- `sync/database.py`
- `sync/pipeline.py`
- `ingestion/git_snapshot.py`
- `content/database.py`
- `tests/sync/test_revision_sync.py`
- `tests/sync/test_sync_database.py`
- `tests/ingestion/test_registry_and_snapshot.py`
- `tests/content/test_content_database.py`
- `scripts/validate_incremental_sync.py`
- `docs/sync/incremental-sync-v1.md`
- `docs/content/content-core-publication-v1.md`
- `docs/inventory/internal-inventory-v1.md`
- `docs/contracts/content-contract-v1.md`

本卡完成后执行Phase 1统一验收：补跑TASK-0012真实GitHub live、验证当前三来源/Publication/API/Web/Sync装配，并更新`1.md`实际完成状态。
