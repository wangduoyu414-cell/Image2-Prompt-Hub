---
task_contract_version: 3
card_id: "TASK-0020R"
title: "建立多输出 Rights Review 队列与 Public Case Candidate v2 合同"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "stateful-runtime"
  - "persistence-migration"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户确认继续进入“真实人工 rights review 队列 + 多图公开合同”阶段；`1.md` 6.1、6.3、12.1 至 12.3 与 Phase 2 段落；TASK-0013、TASK-0016、TASK-0019 的完成事实；当前 `inventory`、`content`、迁移、CLI、验证器与文档。
- `decision_owner`: 用户拥有真实权利决定、最终公开策略和未来管理后台/公开 API 产品选择；本卡只实现内部审核事实、队列状态与版本化候选合同，不产生真实批准或公开激活。
- `material_unknowns`: 无阻断性未知。未来公共 URL、API v2 路径、管理后台交互和真实审核人身份不属于本卡；候选合同保留稳定 source identity 与内容 digest，避免提前冻结这些外部选择。

# 2. 业务目标
- `actor`: 未来人工 rights reviewer；当前由本地维护 CLI 与隔离验证器模拟其显式操作。
- `workflow_and_trigger`: reviewer 从当前选定 Source Revision 的待审 Source Case 队列读取完整 Prompt、所有输入/输出、来源与现有权利证据；一次提交覆盖该 Source Case Version 的 Prompt 和全部输出决策，并显式选择最多一个公开主图；系统追加不可变审核批次、计算派生队列状态，并可生成不激活的 Public Case Candidate v2 预览。
- `single_outcome`: 1513 个内部 Source Case 可按案例而非重复 Prompt 行进入可审计队列；单图和多图案例均能得到完整、幂等、并发安全、逐输出 fail-closed 的人工审核事实和确定性候选合同，同时真实 public catalog 仍为 0。
- `observable_results`:
  - `RESULT-001`: 当前六来源固定库存可投影为 1513 个 review subjects、1513 个 Prompt、1930 个输出；未提交真实审核时全部保持非 publishable。
  - `RESULT-002`: 一个 review batch 原子覆盖一个 `source_case_version_id` 的 Prompt 与全部 `generation_output_id`；漏项、重复项、跨 case 引用或额外输出均拒绝。
  - `RESULT-003`: 来源 `output_primary/output_secondary` 与人工 `public_primary/public_gallery/hidden` 分离；系统不得把 secondary 静默提升为公开主图。
  - `RESULT-004`: 重复相同 idempotency key 与相同规范化 payload 返回同一批次；相同 key 不同 payload、过期 expected-latest、并发提交或未来时间 fail closed，不覆盖历史。
  - `RESULT-005`: Public Case Candidate v2 保留一案例、多 Generation Examples、多输出、逐输出权利/展示决定和来源角色；只有完整显式审核且恰有一个可公开主图时为 publishable。
  - `RESULT-006`: 现有 `content.rights_review_events`、Publication v1、current pointer、Public API v1 和 Web v1 行为不变；本卡不写真实 review，不构建或激活真实 Publication Version。
- `non_goals`: 不录入真实人工批准；不激活任何真实公开版本；不修改 API/Web v1；不实现 API v2、公共多图页面、管理后台 UI、账户/角色系统、scheduler、部署、通知、投诉/下架工作流或法律判断；不改变 ingestion/inventory 证据合同和六来源数量；不自动推导许可证、作者或展示许可。

# 3. 需求质疑与确认
- `user_statement`: 用户接受下一阶段先处理 rights review 队列与多图公开合同，再推进部署和长期调度。
- `REQ-001` (`required_behavior`): review subject 必须是一个不可变 `source_case_version_id`；队列按选定 Source Revision 投影，一个 Source Case 只出现一次，多输出不复制 Prompt 或 case。
- `REQ-002` (`required_behavior`): review batch 必须显式包含 repository license、Prompt rights、作者/原始链接/证据链接、reviewer、带时区 reviewed_at、note，以及该 case 全部 generation outputs 的逐项 asset rights、display policy 与 public display role。
- `REQ-003` (`required_behavior`): 每个 generation output 必须恰好有一个决策；输入必须验证 output→Generation Example→Source Case Version 同域，不能只按数组位置或客户端数量相信关系。
- `REQ-004` (`required_behavior`): `public_primary` 恰好为 0 或 1；只有 Prompt approved、至少一个输出 approved 且采用公开 display policy、恰好一个该输出被显式标为 `public_primary`、其余输出均有明确 `public_gallery` 或 `hidden` 决策时，候选才可 publishable。
- `REQ-005` (`required_behavior`): `hidden` 可承载 unknown/internal_only/blocked 或 reviewer 明确不展示的输出；它不能出现在候选公开资产中。`public_primary/public_gallery` 只允许 approved + `mirror_allowed|attribution_required|link_only`。
- `REQ-006` (`required_behavior`): 来源角色必须保留在候选合同中；人工 public display role 是独立字段，不能回写 inventory 或伪装为上游事实。primary 来源图被隐藏时，只有 reviewer 显式选择另一 approved 输出为 `public_primary` 才可 publishable。
- `REQ-007` (`required_behavior`): review batch 和 output decisions 追加后不可更新/删除；同一 case 可追加后续 batch，effective decision 只取按 `reviewed_at, batch_id` 排序的最新完整批次。
- `REQ-008` (`required_behavior`): 提交必须携带稳定 idempotency key 和 expected latest batch（首批显式为 none）；数据库事务、唯一约束与 case 级锁共同防止丢失更新、重复批次和半写。
- `REQ-009` (`required_behavior`): 队列状态由当前 revision selection + immutable inventory + latest review batch 派生，至少区分 `pending`, `review_required`, `publishable`, `internal_only`, `blocked`；不得把 inventory `review_required` 或旧 revision review 继承为批准。
- `REQ-010` (`required_behavior`): Public Case Candidate v2 是不激活的内部版本化合同；包含 source case identity、Prompt、全部 Generation members、公开输出子集、隐藏输出计数、来源/人工角色、rights batch、provenance 和确定性 content digest，禁止对象凭据和未授权 object locator 泄漏。
- `REQ-011` (`required_behavior`): 当前 Publication v1 gate、rights event 表、current-only API/Web 和 0 real public 必须保持兼容；新表/服务不能被旧 build/activate 路径隐式读取。
- `REQ-012` (`required_behavior`): CLI 提供 JSON-only 的 queue list/inspect、review submit/inspect 和 candidate preview；所有写操作必须显式参数化，不提供“approve all”或自动填值。
- `REQ-013` (`required_behavior`): 文档必须明确这只是人工审核与候选合同基础，真实审核、公开 API/Web v2、管理后台和部署仍未完成。
- `REQ-014` (`required_behavior`): 完成全仓 offline、最新迁移下真实 PostgreSQL 六来源 queue/candidate live、失败/并发/幂等/回滚、旧 Content/API/Web 回归、scope/hygiene/freshness、L4 独立复核和唯一 Completion Report；本目录非 Git，不创建 commit。
- `DEC-001` (`confirmed_design`): `1.md` 已确认同一 Source Case 可包含多个 Generation Example 且不得丢失上下文；因此审核工作单按 Source Case Version 分组，权利决定仍逐输出保存。
- `DEC-002` (`confirmed_design`): `1.md` 与 TASK-0019 明确禁止 secondary 静默提升；因此 `public_display_role` 由 reviewer 显式选择并与 source role 分离。
- `DEC-003` (`confirmed_design`): 为保护已完成的 v1 公共合同，本卡新增 Public Case Candidate v2 内部合同，不替换或重解释 Publication/API/Web v1。
- `INV-001`: immutable Source/Evidence 与人工 review decision 分层；审核只能引用 inventory，不能修改来源事实。
- `INV-002`: 权利批准是权限事实，不从 license 字符串、仓库状态、模型声明、来源角色或旧 revision 自动推导。
- `INV-003`: 一个 review batch 必须全有或全无；批次头、全部输出决策和 idempotency 结果在一个事务提交。
- `INV-004`: 任何 publishable 候选必须有完整 Prompt rights、逐输出决策、一个显式 public primary、强配对、已验证资产和完整来源位置。
- `INV-005`: hidden/blocked/internal assets 不携带可公开对象定位，也不能通过候选 preview、日志或错误消息泄漏。
- `INV-006`: 新 Source Revision 产生新的 Source Case Version 和待审 subject；历史 batch 不迁移、不复制、不自动生效。
- `INV-007`: v1 Publication/current/API/Web 行为和真实 public=0 在本卡中不可改变。
- `material_ambiguities`: 未来公共 URL 与跨来源 Public Case v2 聚合方式尚未由 API/Web 消费任务确认。本卡只产生每个 Source Case Version 的稳定 identity、完整事实 digest 和候选 snapshot，不把 URL 或跨来源展示分组写成既成事实。
- `decisions_and_authority`: `DEC-001` 至 `DEC-003` 来自用户确认的阶段方向、`1.md` 已有数据/权利不变量和 TASK-0019 完成后明确记录的多图公开缺口。

# 4. 业务场景与规则

## Business Object / State / Data Flow
- `Business Object`: Rights Review Subject、Rights Review Batch、Output Decision、Public Case Candidate v2。
- `STATE-001`: 无 batch=`pending`；最新 batch 含 unknown 或缺公开条件=`review_required`；Prompt 或整体明确 internal=`internal_only`；Prompt blocked 或全部输出 blocked=`blocked`；满足 `REQ-004`=`publishable`。提交失败保持原状态。
- `FLOW-001`: selected Source Revisions → ready Source Case Versions → grouped Prompt/generations/outputs/provenance → queue subject → atomic review batch + output decisions → effective state → deterministic Candidate v2 preview；不进入 Publication v1 current。
- `RULE-001`: queue 与 candidate 都从数据库同域关系重建，客户端提交的标题、计数、source role、hash 或路径不作为 authority。
- `RULE-002`: candidate digest 排除数据库自增 id、时间之外的运行噪声、临时路径与对象凭据；reviewed_at 和 batch identity作为审核事实保留但不得导致相同 batch 重放漂移。
- `SCN-001` 单输出主路径: reviewer 完整提交一个 approved 输出并显式选择 public_primary，queue 变为 publishable，preview 含一张公开输出。
- `SCN-002` 多输出主路径: reviewer 对同 case 的所有输出逐项决定，一张 public_primary、多张 public_gallery 或 hidden，preview 只含允许展示的输出并保留来源 role。
- `SCN-003` 非公开决定: unknown/internal_only/blocked 或没有显式 public_primary 时，batch 可保留为审核事实，但 candidate 不可 publishable，Publication v1/current 不变。
- `SCN-004` 重复与并发: 同 key 同 payload 幂等；同 key 不同 payload、stale expected-latest、第二并发 writer 或跨 case output 拒绝且无半状态。
- `SCN-005` revision 更新: 新 Source Case Version 重新进入 pending；旧 batch 仅保留历史，不自动复制批准。
- `SCN-006` 空与错误: 空 selection、无 ready cases、缺 output、重复/漏 output、未来时间、非法 policy/role、object locator 注入均 fail closed。
- `risk_sensitive_invariants`: `INV-001` 至 `INV-007`、append-only、idempotency、optimistic concurrency、case/output domain closure、public/hidden data separation、v1 compatibility。
- `inapplicable_faces_with_reason`: 本卡无用户账户、网络 HTTP 写接口、浏览器 UI、生产部署或真实外部写；reviewer 身份为必填事实文本但身份认证/授权系统留待管理后台任务。

## Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| `DEP-001` | selected Source Revision | Rights Review Subject | data derivation | TASK-0016 explicit revision selection + inventory schema | confirmed | ready inventory 不等于权利批准 | queue membership |
| `REL-001` | Source Case Version | Generation Outputs | parent-child grouping | inventory FK/domain triggers + TASK-0019 | confirmed | 分组不等于输出共享同一 rights 状态 | batch coverage |
| `PERM-001` | latest complete Review Batch | Candidate publishable state | permission | `1.md` 12 + TASK-0013 explicit review rule | confirmed | publishable candidate 不等于已激活公开 | preview gate |
| `REL-002` | source role | public display role | display mapping | TASK-0019 + `DEC-002` | confirmed | output_secondary 不自动成为 public_primary | candidate projection |
| `DEP-002` | Candidate v2 | future API/Web v2 | future consumer dependency | 用户确认阶段路线 | confirmed for handoff | 本卡通过不代表 API/Web v2 已完成 | next task |

## Module Boundary

| module | owns | reads | writes | emits | consumes | must not do | authority source |
|---|---|---|---|---|---|---|---|
| `inventory` | immutable source/case/prompt/generation/asset facts | source package | existing inventory tables | ready revision facts | ingestion imports | 接受人工批准或 public display role | current schema/docs |
| `content review` | review queue projection、batch、output decisions、effective state | inventory + selected revisions | new additive content tables | review/candidate JSON | CLI/validator | 修改 inventory 或自动批准 | target `REQ-001..009` |
| `content candidate policy` | Candidate v2 validation、digest、redaction | grouped inventory + effective review | no v1 publication write | deterministic preview | future API/Web v2 | 激活 v1 current 或泄漏 hidden locator | target `REQ-004..011` |
| `content CLI` | explicit operator boundary | content review/candidate services | only through service transactions | bounded JSON | human reviewer/validator | 自动填 approval、遍历 approve-all、打印凭据 | current CLI pattern + `REQ-012` |
| `Public API/Web v1` | current immutable Publication v1 read | active v1 snapshot | none | existing responses/pages | public consumer | 读取 review queue 或 Candidate v2 | protected TASK-0014/0015 |

# 5. 当前证据与目标差异
- `FACT-001`: `content.rights_review_events` 当前按 `generation_example_row_id` 追加单条 Prompt+Asset 决定，没有按 Source Case 分组的 queue、完整输出覆盖、idempotency key 或 expected-latest 冲突保护。
- `FACT-002`: TASK-0019 将 Erick 572 cases 投影为 877 Generation Examples、Vigo 112 cases 投影为 224；当前 publication gate 对每个 Generation Example 要求 `output_primary`，因此 417 个 secondary generation rows 即使未来有 rights 也会因 `output_primary_missing` 排除。
- `FACT-003`: inventory 已有 `source_case_version_id`、`generation_output_id`、`generation_example_row_id`、`asset_source_id` 与同 case domain trigger，足以建立 case-level batch 和逐输出引用，无需修改 inventory 表。
- `FACT-004`: `content.publication.py` 与 `content.database.py` 当前只构建 Publication Entry v1；API/Web 只读 active v1 snapshot，且真实 active/public 数据为 0。
- `FACT-005`: `content.cli` 已有 JSON-only 单条 review 命令，但没有 queue/inspect/batch/candidate preview；不存在管理后台或 reviewer 认证。
- `FACT-006`: 最新迁移为 `0004_incremental_sync.sql`；本卡若持久化 batch/idempotency/effective relationships，必须新增 additive `0005`，不得改写 0001 至 0004。
- `ASM-001`: 六来源固定 inventory 能提供真实 1513 cases/1930 outputs 的 queue coverage；isolated synthetic reviewer inputs可验证权限逻辑，但不构成真实批准。
- `current_execution_path`: maintainer 手工知道 generation row id → `record-rights-review` 追加一条 v1 event → build Publication v1；没有案例级上下文、待审列表、完整多输出决策或显式 public primary。
- `target_delta`: selected revisions → case-level queue → atomic complete review batch → derived status → Candidate v2 preview；旧 v1 path 保持隔离。
- `evidence_gaps`: 实现前尚无 0005 schema、candidate v2 schema、queue/service/CLI、full six-source live 或 future API/Web v2 consumer；本卡只关闭前四项，最后一项明确交接。

# 6. 范围与责任边界
- `allowed_write_scope`: 新 additive migration `migrations/0005_*`；`content/` 中 review/candidate policy、database、CLI/export；`schemas/` 的 Candidate v2 schema；相关 `tests/content/`、必要 inventory/sync regression tests；`scripts/validate_rights_review_queue.py` 及其直接复用的 validator glue；`docs/content/`、`1.md`；本卡 formal evidence root。
- `hard_protected_scope`: `migrations/0001` 至 `0004` 原始字节；inventory 表/Generation Example v1/Adapter 合同；六来源 registry/audit/fixed Commit/1513/1930事实；现有 `content.rights_review_events` 和 Publication v1/current/outbox 语义；Public API/Web v1 routes/models/pages；任何真实 review/publication 数据；外部仓库、部署和账号权限。
- `protected_contracts_and_invariants`: `INV-001` 至 `INV-007`；TASK-0013/0016/0019 完成事实；current-only public reads；0 real public；hidden/blocked资产不可公开传输。
- `authorization_limits`: 仅授权仓库内代码、迁移、Schema、测试、文档和隔离本地验证；不授权代表任何人作出真实权利结论、写入生产数据库、部署、公开发布、通知外部人员或获取额外凭据。
- `stop_if_scope_expands`: 若必须修改 inventory 证据模型、重解释/替换 v1 public contract、引入真实身份认证、录入真实 approval、改变 public=0、实现 API/Web v2 或修改 0001 至 0004，则停止并拆分/修订任务卡。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: 当前 caller=本地维护者/验证器；entry=`python -m content` 新 queue/review/preview 子命令；state/data owner=Content review tables与纯 Candidate v2 policy；consumer=审核者 JSON 输出和后续 API/Web v2 任务。
- `expected_touchpoints_or_search_anchors`: `content.database.ContentDatabase`、`content.cli._parser/main`、`content.publication` 的纯策略模式、`inventory.source_case_versions/generation_examples/generation_outputs/asset_sources`、migration checksum/immutability tests、`scripts/validate_phase2_adapters.py` 的六来源真实装配、Content/API/Web现有 validators。
- `wiring_to_final_consumer`: CLI list/inspect 从 selected revisions 读取 queue；submit 调用单个事务写 batch/decisions；inspect/preview 重新从 DB authority 构建 effective state和 Candidate v2；validator 从真实六来源 inventory 调用同一入口并确认旧消费者仍为 0 public。
- `failure_and_recovery`: validation 在写前完成；case lock + expected-latest + idempotency unique 防并发/重放；事务失败回滚全部行；immutable rows拒绝更新/删除；retry 可使用相同 key；preview 是只读且不写 Publication v1。
- `implementation_freedom`: 满足合同和边界时，新模块具体文件拆分、dataclass/SQL query组织和 CLI 参数分组由执行者选择；不得为了省迁移把批次 JSON 塞入旧 v1 event 或绕过关系约束。
- `selected_profile_obligations`:
  - `public-contract`: Candidate v2 字段、来源/公开角色、hidden redaction、错误码、v1兼容和 Schema/consumer tests必须明确。
  - `stateful-runtime`: queue状态、latest batch、重复/并发、expected-latest、事务回滚和 revision 重审必须验证。
  - `persistence-migration`: additive 0005、旧数据空兼容、不可变触发器、FK/domain/unique/check约束、migration drift和最新数据库集成必须验证。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-004`至`REQ-006`, `REQ-010`, `DEC-001`至`DEC-003`, `INV-004`, `INV-005`
- `owns_behavior`: 定义并实现 Public Case Candidate v2 的纯验证、投影、redaction与确定性 digest。
- `target_delta`: 从“每个 Generation Example 独立 Publication Entry v1”增加一个不激活的 case-level Candidate v2 合同，完整表达同 Source Case 的全部generation/output review结果。
- `integration_edges`: grouped Source Case facts + effective Review Batch → Candidate v2 policy/schema → CLI preview/validator/future API v2。
- `expected_touchpoints`: `content.publication`纯策略模式、`content/`中新candidate职责、`schemas/public-case-candidate-v2.schema.json`、相关fixtures/tests/docs。
- `business_result`: 一案例多输出可被完整表达，来源 role 与 public display role同时保留，未授权输出不进入公开资产子集。
- `behavior_faces`: normal=单图/多图；boundary=一主图、多gallery、hidden混合；failure=无主图/多主图/漏决策/locator泄漏；permission=只有effective review可授予candidate；empty=0 public outputs不可publishable；repeated=相同事实同digest；downstream=CLI preview/future API v2。
- `state_change`: grouped facts + review → publishable/nonpublishable candidate result；纯策略无持久副作用。
- `data_flow`: inventory case facts + effective batch → Candidate v2 policy/schema → preview JSON。
- `integration_point`: current evidence=v1 pure policy pattern；target=新的case-level v2 policy由TASK-002/003调用；consumer=CLI/validator/future API。
- `scope_boundary`: 不修改 Publication Entry v1、canonical v1或API models。
- `allowed_write_scope`: `content/` candidate policy、`schemas/`、tests/docs。
- `acceptance_scenarios`: `SCN-001`至`SCN-003`, `SCN-006`。
- `linked_tests`: `TEST-001`
- `stop_conditions`: 公共 URL、API路由和v1 canonical语义明确不属于该slice；若实现触及这些边界则停止并创建后续卡。

### TASK-002
- `links`: `OBJ-001`, `REQ-001`至`REQ-009`, `INV-001`至`INV-003`, `INV-006`
- `owns_behavior`: additive review batch/output decision persistence、queue projection、effective latest、idempotency、optimistic concurrency与不可变性。
- `target_delta`: 从单条generation rights event扩展为case-level完整批次和逐generation-output决策，同时保持旧event表只读兼容。
- `integration_edges`: selected revisions/inventory domain → queue query → atomic batch/decisions → effective review state → Candidate v2。
- `expected_touchpoints`: additive `migrations/0005_*`、`ContentDatabase`事务/查询边界或同责新模块、migration/content integration tests与docs。
- `business_result`: reviewer 能一次完整审核一个案例及全部输出，任何失败不留下半批次，revision变化重新待审。
- `behavior_faces`: normal=atomic submit；boundary=1930输出/1513 subjects、0/1 primary；failure=漏/重复/跨case/future time/DB rollback；permission=explicit fields only；empty=no selection/no cases；concurrent=stale expected/duplicate key/lock；downstream=Candidate v2。
- `state_change`: pending/review_required/internal_only/blocked → append batch → derived effective state；失败状态不变。
- `data_flow`: selected revisions + inventory → queue rows；submission → new content tables；latest batch → policy consumer。
- `integration_point`: current evidence=ContentDatabase transaction pattern与inventory FK；target=queue/submit/inspect methods；caller=CLI/validator；consumer=TASK-001/003。
- `scope_boundary`: additive 0005 only；不改 inventory/v1 events。
- `allowed_write_scope`: `migrations/0005_*`、`content/database.py`或等责新模块、tests/docs。
- `acceptance_scenarios`: `SCN-001`至`SCN-006`。
- `linked_tests`: `TEST-002`
- `stop_conditions`: 需要 mutable draft/lease、账户权限或修改旧 migration。

### TASK-003
- `links`: `OBJ-001`, `REQ-010`至`REQ-013`, `INV-004`, `INV-005`, `INV-007`
- `owns_behavior`: JSON-only queue/review/preview维护入口与明确 handoff；不激活任何 Publication。
- `target_delta`: 从必须预先知道单个generation row id的命令，扩展为可发现、检查、原子提交和预览一个完整Source Case的维护工作流。
- `integration_edges`: CLI validated args → queue/review/candidate services → bounded JSON/exit codes → reviewer与validator。
- `expected_touchpoints`: `content/cli.py::_parser/main`、`content/__main__.py`/exports、CLI contract tests、维护文档。
- `business_result`: reviewer 能发现待审案例、查看完整上下文、显式提交和复查结果；future consumer获得稳定 Candidate v2。
- `behavior_faces`: normal=list/inspect/submit/preview；boundary=pagination/filter/多输出；failure=bad id/selection/conflict/schema；permission=无approve-all/无默认批准；empty=1513 pending前及0 selection；repeated=idempotent submit；downstream=bounded JSON和future API。
- `state_change`: CLI只通过TASK-002提交改变review state；list/inspect/preview只读。
- `data_flow`: CLI args → validated service calls → stable non-sensitive JSON。
- `integration_point`: current evidence=`content.cli` JSON pattern；target=新子命令接入 `python -m content`；consumer=人工维护者/validator。
- `scope_boundary`: 无HTTP/UI/认证/真实数据。
- `allowed_write_scope`: `content/cli.py`、exports、tests/docs。
- `acceptance_scenarios`: `SCN-001`至`SCN-006`。
- `linked_tests`: `TEST-003`
- `stop_conditions`: 需要 HTTP/admin UI 或凭据处理。

### TASK-004
- `links`: `OBJ-001`, `REQ-011`, `REQ-014`, `INV-001`至`INV-007`
- `owns_behavior`: 六来源真实 inventory 上的 queue/candidate集成、旧 v1消费者回归、失败清理和正式验证入口。
- `target_delta`: 在TASK-0019六来源真实装配之后增加review queue/candidate验证阶段，并将旧Content/API/Web 0-public回归纳入同一最终consumer gate。
- `integration_edges`: fixed Git sources → ingestion/inventory → review queue/batch/candidate → existing Content/API/Web v1 validators → cleanup evidence。
- `expected_touchpoints`: `scripts/validate_rights_review_queue.py`、现有Phase2/Content/API/Web validator可复用入口、相关integration tests/docs。
- `business_result`: 新审核基础连接真实1513/1930数据并证明不改变真实公开状态。
- `behavior_faces`: normal=真实全量queue + synthetic isolated review；boundary=multi-output最大记录/asset dedupe；failure=transaction/idempotency/concurrency/schema；permission=no real approval；empty=0 public；repeated=same review key；downstream=Content/API/Web v1 regression。
- `state_change`: 隔离DB从无review→synthetic batch/candidate；结束后全部runtime清理，workspace与真实数据不变。
- `data_flow`: six-source fixed Git → inventory → review queue → synthetic batch → candidate preview → v1 consumer validation。
- `integration_point`: caller=正式 validator；callee=existing Phase2/inventory/content/api/web validators + new services；consumer=Completion evidence与下一任务。
- `scope_boundary`: 不向生产/真实DB写入，不启动长期服务。
- `allowed_write_scope`: `scripts/validate_rights_review_queue.py`、直接测试glue、docs。
- `acceptance_scenarios`: `SCN-001`至`SCN-006`。
- `linked_tests`: `TEST-004`
- `stop_conditions`: 真实public非0、旧v1 drift、runtime residue或需要API/Web v2。

### ASSEMBLY-001
- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`
- `end_to_end_entry`: `scripts/validate_rights_review_queue.py --json` 从六来源当前固定 inventory 建立 queue，经同一生产service完成isolated synthetic review和Candidate v2 preview，再运行旧Content/API/Web回归。
- `shared_contract_state_data`: source_case_version/output domain、complete batch、idempotency、latest effective state、source/public roles、hidden redaction、Candidate v2 digest、v1 isolation。
- `final_consumer`: 人工审核维护者与后续 API/Web v2 实现任务。
- `cross_task_failure_path`: policy/schema失败不得写batch；batch失败回滚；CLI不得绕过service；candidate失败不写v1 publication；旧消费者仍读0-public current。
- `linked_test_evidence_gate`: `TEST-004` / `EV-004` / `GATE-004`

# 9. 验证与验收

- `risk_sensitive_invariants`: `INV-001`至`INV-007`、case/output domain closure、complete atomic batch、append-only、idempotency/expected-latest、hidden redaction、Candidate v2 digest和v1 current/public隔离。
- `consumer_chain_validation`: 必须从真实六来源selected revisions和latest migration生成1513个queue subjects/1930 outputs，经过生产queue/submit/preview入口，再运行旧Content Core、Public API和Public Web 0-public消费者验证；只跑policy unit或SQL测试不能关闭本卡。
- `real_integration_evidence`: workspace外真实固定Git、PostgreSQL、对象存储和六来源inventory；isolated synthetic review只写短生命周期验证DB；覆盖单/多输出、真实Erick/Vigo案例、旧v1 build/current/API/Web、全部runtime cleanup。
- `failure_recovery_ownership_validation`: 输入/schema/domain校验由review service；batch/decisions原子性、锁、idempotency与immutability由Content DB/0005约束；Candidate v2由纯policy fail closed；CLI只编排；旧Publication/current回滚与读取继续由既有Content/API owners负责。

### RISK-001
- `description`: 把case-level review简化为一条generation review会丢失其他输出或让未审图片随同公开。
### RISK-002
- `description`: 把source secondary自动提升为public primary会伪造上游角色和reviewer决定。
### RISK-003
- `description`: 并发/重放若无expected-latest与idempotency，会产生覆盖、冲突或不确定effective rights。
### RISK-004
- `description`: 新candidate逻辑若被v1 build隐式读取，可能改变0-public或破坏已完成Public API/Web合同。
### RISK-005
- `description`: hidden/link-only资产若携带object locator，可能绕过公开授权边界。
### RISK-006
- `description`: 新revision若继承旧review会把历史批准错误应用到变化后的Prompt或图片。

### TEST-001
- `links`: `TASK-001`, `REQ-004`至`REQ-006`, `REQ-010`, `RISK-001`, `RISK-002`, `RISK-005`
- `method`: Candidate v2 schema/policy unit与mutation matrix，覆盖单/多输出、显式主图、gallery/hidden、来源role保留、digest稳定、locator redaction和非法组合。
- `expected_observable_result`: 一case生成一Candidate；允许展示输出完整且恰一public primary；hidden不含公开定位；相同事实稳定序列化/digest。
- `failure_path_covered`: 0/2主图、approved与policy/role冲突、漏输出、重复输出、跨case、unknown字段、object locator注入。
- `cannot_prove`: PostgreSQL事务与真实六来源。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: pytest receipt、positive golden、negative matrix、schema/digest重复比较和redaction断言。

### TEST-002
- `links`: `TASK-002`, `REQ-001`至`REQ-009`, `RISK-001`, `RISK-003`, `RISK-006`
- `method`: 最新migration PostgreSQL integration覆盖1513/1930形状的代表性单/多output cases；提交、latest、状态、idempotency、stale expected、并发、rollback、immutable triggers和新revision pending。
- `expected_observable_result`: 批次与全部decisions同事务；same key同payload verified existing；冲突无新行；旧review不跨revision；派生状态正确。
- `failure_path_covered`: partial write、duplicate/missing/cross-domain output、future time、DB injection、two writers、mutation/delete。
- `cannot_prove`: 全量固定Git与旧最终消费者。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: migration checksum、pre/post counts、batch/decision natural keys、rollback/concurrency结果、queue state和revision isolation。

### TEST-003
- `links`: `TASK-003`, `REQ-012`, `REQ-013`, `RISK-003`, `RISK-005`
- `method`: CLI contract tests调用list/inspect/submit/preview，验证参数、稳定JSON/error codes、分页、无默认批准、秘密/locator redaction和重放。
- `expected_observable_result`: reviewer无需知道内部SQL即可完成显式工作流；错误可诊断且不写半状态；输出无DB URL/object credentials。
- `failure_path_covered`: bad id/selection/payload、conflict、empty、unsupported role/policy、service unavailable。
- `cannot_prove`: 真实源总量与浏览器UI。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: CLI argv/exit/status matrix、stdout JSON schema、stderr/secret scan、idempotent response比较。

### TEST-004
- `links`: `ASSEMBLY-001`, `TASK-001`至`TASK-004`, `REQ-011`, `REQ-014`, `RISK-001`至`RISK-006`
- `method`: workspace外真实六来源fixed-Commit extraction/inventory + 最新migration；核对1513 queue subjects/1930 outputs；isolated synthetic单/多图reviews、candidate previews、failure/recovery/concurrency；随后运行现有Content/API/Web live且真实public仍0。
- `expected_observable_result`: queue全量闭合；Erick/Vigo多图预览不丢图且显式主图；旧v1 build/current/API/Web行为和312历史兼容；无真实review/public写入或workspace residue。
- `failure_path_covered`: source/output count drift、跨case、hidden leak、transaction/lock、v1 coupling、cleanup。
- `cannot_prove`: 法律正确性、真实人工接受、API/Web v2、管理后台或生产部署。
### EV-004
- `for`: `TEST-004`
- `required_evidence_shape`: six-source counts、queue state counts、review/candidate snapshots、DB pre/post与failure receipts、v1 0-public consumer结果、cleanup/secret scan。

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | Candidate v2合同 | `OBJ-001` / `TASK-001` / `TEST-001` | 多输出、角色、权限和redaction全部闭合 | `EV-001` | 数据库/全量源 |
| `GATE-002` | review persistence/state | `OBJ-001` / `TASK-002` / `TEST-002` | migration、原子性、幂等、并发、revision隔离通过 | `EV-002` | 全量固定Git |
| `GATE-003` | reviewer CLI workflow | `OBJ-001` / `TASK-003` / `TEST-003` | 所有入口可达、显式、稳定且不泄密 | `EV-003` | UI/真实review |
| `GATE-004` | 六来源装配与v1保护 | `OBJ-001` / `TASK-004` / `ASSEMBLY-001` / `TEST-004` | 1513/1930、synthetic review/candidate、v1 0-public、清理和回归全部通过 | `EV-004` | API/Web v2/生产 |

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"rights-review-queue-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q"],"cwd":".","timeout_seconds":1800,"invalidation_paths":["1.md","pyproject.toml","uv.lock","content","docs","inventory","migrations","schemas","scripts","tests"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["uv","run","--frozen","--no-sync","python","-B","-c","import pytest, jsonschema, psycopg; print('ready')"],"preflight_timeout_seconds":30},
  {"validator_id":"rights-review-queue-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_rights_review_queue.py","--json"],"cwd":".","timeout_seconds":5400,"invalidation_paths":["1.md","apps","config","content","docs","ingestion","inventory","migrations","reports","schemas","scripts","sync","tests"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

# 10. 产物与完成回写
- `required_deliverables`:
  - `migrations/0005_rights_review_queue_and_public_case_v2.sql`
  - `schemas/public-case-candidate-v2.schema.json`
  - Content review queue/batch/candidate production implementation under `content/`
  - `content/cli.py` queue/review/preview入口
  - `scripts/validate_rights_review_queue.py`
  - rights queue/Candidate v2相关tests与fixtures
  - `docs/content/rights-review-and-public-case-v2.md`
  - `1.md`阶段状态同步
- `documentation_impact`: updated；同步Content review/candidate合同、迁移、CLI、六来源队列口径、0 real public和下一步API/Web v2/admin handoff。
- `repository_hygiene_requirement`: runtime、DB、source mirrors、packages、venv、cache、logs与凭据全部在workspace外；只保留任务交付物；旧migration/protected authority哈希不变。
- `external_review`: policy=never；真实PostgreSQL/六来源/旧消费者验证加L4独立语义复核足够，不调用外部模型。
- `non_completion_rules`: 任一 deliverable、4个GATE、2项正式validator、1513/1930全量queue、原子/幂等/并发/revision隔离、hidden redaction、v1 0-public保护、docs/hygiene/freshness/独立review/唯一Completion Report缺失时不得完成；任何真实rights/publication变化立即停止。

执行 run ID、candidate/history、manifest/receipt hash、实际命令结果、final revision 和终态写入执行 sidecar 或 Completion Report，不写回本任务卡。
