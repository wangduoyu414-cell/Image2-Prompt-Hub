---
task_contract_version: 3
card_id: "TASK-0005"
title: "补强内部库存的私有对象、关系完整性与版本演进边界"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "external-boundary"
  - "configuration"
  - "stateful-runtime"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by:
  - "TASK-0004"
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`:
  - 用户目标模式授权：沿已确认的高价值案例长期来源方向持续执行，逐张建立并正式执行任务卡，完成 Phase 1 三类 pilot 的纵向闭环。
  - `D:/image2/1.md`，重点是第 3、5、6、8、9、12、14、15、16 节。
  - `D:/image2/config/sources-v1.yaml` 与 `D:/image2/reports/source-audit-v1.json`，作为来源身份、固定 Commit、来源家族、权利证据和固定指标的权威事实。
  - `D:/image2/docs/contracts/content-contract-v1.md`、`schemas/adapter-output-v1.schema.json`、`schemas/generation-example-v1.schema.json`，作为提取包内证据合同。
  - `D:/image2/docs/ingestion/g0dam-extraction-v1.md`、TASK-0003 代码与正式 Completion Report，作为已完成生产者、包格式、安全快照和真实 100-case 证据。
  - `D:/image2/tasks/TASK-0004-internal-inventory-and-content-addressed-assets.md`、`C:/Users/admin/.codex/task-state/image2/TASK-0004-9ea2c4131452cb59/completion-report.json` 与其实现产物，作为已完成内部库存基线；本任务只在该基线上补强已确认缺口并重新全量验收。
  - PostgreSQL 18.4 官方发布说明与 PostgreSQL advisory-lock/transaction 文档；Psycopg 3 transaction 文档；Docker Official `postgres:18.4` 镜像说明。
  - MinIO 官方仓库/发布说明：社区仓库已归档且社区预编译镜像属于 legacy。TASK-0005 只允许把固定旧镜像用于回环地址、随机凭据、短生命周期的 S3 兼容性测试，不得把它作为生产安全基线；生产目标仍是通用 S3/Cloudflare R2。
- `decision_owner`: 用户拥有数据模型、对象存储生产选型、权利/发布边界和风险接受的最终决定权；执行者可在本卡已冻结的模块边界内选择具体 SQL、Psycopg 和 boto3 实现细节。
- `material_unknowns`:
  - TASK-0003 正式 live 输出已按验证要求清理，因此 TASK-0005 live Validator 必须在外部目录重新生成一个真实固定 Commit 提取包，再将其导入库存；不得引用不存在的旧输出路径或 TASK-0004 历史收据替代本次验证。
  - 本任务只保存 original 原图，不生成 WebP/AVIF、缩略图或 EXIF 清理版本；派生图片管线属于后续任务。
  - 对象存储与 PostgreSQL 无跨资源原子事务。设计固定为“先校验并写入不可变内容寻址对象，再在一个 PostgreSQL 事务内提交全部可见库存记录”；数据库失败可能留下不可见、可复用的孤立对象，但不得留下部分数据库库存或引用缺失对象。
  - MinIO 当前不再是可直接推荐的生产社区发行版。本任务的业务代码必须只依赖标准 S3 API；Compose 中的 legacy MinIO 仅用于隔离集成验证，生产部署不在本卡授权范围内。

# 2. 业务目标

- `actor`: 后续 Canonical、分类、权利审核、发布、API 和网页实施者。
- `workflow_and_trigger`: TASK-0004 已交付可运行的内部 Source/Evidence 库存，但协调方在接受前发现三个会破坏长期运行的边界缺口：公开 bucket policy/object ACL 未 fail closed、数据库未在 DB 层阻断跨域引用、project 行锁死完整 registry snapshot 导致后续 Commit 无法共存。在开发第二个 Adapter 前必须先补强并重验。
- `single_outcome`: 在不改变 TASK-0002/0003 生产者合同和 TASK-0004 已验证核心行为的前提下，补强现有 inventory，使私有对象边界、数据库同域完整性和后续 Source Revision/registry snapshot 共存都由代码与真实 PostgreSQL/S3 验证闭合；同一包仍幂等，失败仍不产生部分可见库存。
- `observable_results`:
  - `RESULT-001`: migration CLI 在空 PostgreSQL 18.4 上创建版本化 `inventory` schema，再次执行不改变已应用 migration；已应用版本 SQL 哈希变化时 fail closed。
  - `RESULT-002`: importer 完整校验 package manifest、Adapter Output、100 个 Generation Example、metrics、registry source/Commit 和 semantic digest 后才访问持久化边界。
  - `RESULT-003`: importer 从同一安全固定 Commit 快照重新读取 100 张原图，逐张重新计算 SHA-256、字节数和 media type，并与 package 证据精确一致后写入私有对象桶。
  - `RESULT-004`: 100 张唯一原图以 `sha256/ab/cd/{full_sha256}` 存储一次；对象 metadata、下载后 SHA-256、数据库 `assets` 行和全部 `asset_sources` 引用闭合。
  - `RESULT-005`: PostgreSQL 中形成 1 source project、1 immutable revision、1 adapter run、100 source cases/versions/prompts/assets/asset sources/generation examples/outputs/pairing records/rights evidence，0 parse errors；所有原始 Prompt、source locator、source claim、extensions 和 rights evidence 可追溯。
  - `RESULT-006`: 同一 package 第二次导入返回 `verified_existing`，行数、自然键、对象数和稳定库存摘要不变；相同键并发运行只有一个 writer。
  - `RESULT-007`: package 篡改、固定 Commit 不一致、源图片漂移、对象冲突、数据库异常或受控故障均非零退出；数据库保持上一完整状态，对象存储中不得出现错误哈希键或公开对象。
  - `RESULT-008`: 同一稳定 source project 可新增另一个 immutable revision/run 并保存自己的完整 registry snapshot；旧 revision/run 及旧 snapshot 保持逐字不变。
- `non_goals`:
  - 不实现 JoeSai/ConardLi Adapter，不修改 g0dam Adapter 或 TASK-0003 提取合同。
  - 不实现 Canonical Case、跨来源去重、分类、搜索、权利决定、质量决定、Publication Version、API、网页、管理后台、队列或调度器。
  - 不生成 thumbnail/card/detail/blur 等派生图片，不删除 EXIF，不转码，不对图片内容作视觉分析。
  - 不公开 bucket、对象 URL、Prompt 或图片；不生成 presigned URL，不设置 public ACL，不把 `review_required` 提升为展示许可。
  - 不部署生产 PostgreSQL、生产 MinIO 或其他生产对象存储，不建立备份、复制、TLS、IAM、KMS 或多节点集群。
  - 不解决孤立内容寻址对象的垃圾回收；本任务只保证孤立对象不可被库存消费者看见且后续重跑可安全复用。

# 3. 需求质疑与确认

- `user_statement`: 按固定高价值案例来源与图片/Prompt 强绑定方向持续执行，使用目标模式完成后续阶段。
- `REQ-001` (`required_behavior`): 建立独立 `inventory` Python package，至少提供 `python -m inventory migrate`、`python -m inventory import-package` 和 `python -m inventory inspect` 三个入口；数据库和 S3 凭据只从环境变量读取，JSON 输出不得泄露凭据或带密码 DSN。
- `REQ-002` (`required_behavior`): package loader 必须调用 TASK-0003 的 published-package verifier，并再次校验 manifest 枚举、逐文件 SHA-256、package_state、idempotency_key、semantic_digest、Adapter Output v1、Generation Example v1、coverage/metrics 和跨文件引用；缺文件、额外文件或任一不一致时在 DB/S3 写入前失败。
- `REQ-003` (`required_behavior`): importer 必须从 registry 读取完整 source record，确认 source_id 为 active canonical selected pilot、sync enabled、ingestion full，且 package revision 精确等于 registry 完整 verified_commit_sha；不得接受调用者覆盖 Commit、HEAD、分支或标签。
- `REQ-004` (`required_behavior`): 建立版本化 SQL migration 和 checksum migration runner；migration 至少覆盖 Source/Evidence 层的 `source_projects`、`source_revisions`、`source_files`、`source_adapter_runs`、`source_parse_errors`、`source_cases`、`source_case_versions`、`prompt_records`、`assets`、`asset_sources`、`generation_examples`、`generation_inputs`、`generation_outputs`、`pairing_evidence`、`rights_records` 与 `schema_migrations`。
- `REQ-005` (`required_behavior`): 对每个 Generation Example 资产，必须使用既有安全 fixed snapshot 与 path containment 重新读取 repository-local source_path；实际 SHA-256、byte_size 和 media_type 必须与合同文档一致，source_url 不能替代固定快照字节。
- `REQ-006` (`required_behavior`): S3 writer 必须使用通用 boto3 S3 API，把 original bytes 写入 `sha256/{h0h1}/{h2h3}/{full_sha256}`；bucket policy、bucket ACL 和每个 existing/new object ACL 都必须确认非公开；新对象写后必须 HEAD 校验 metadata/size/type，既有对象必须下载并重新哈希。HTTP endpoint 只允许 loopback，非 loopback endpoint 必须 HTTPS。
- `REQ-007` (`required_behavior`): database importer 必须保留自然身份、原始 raw Prompt、source locations、完整 adapter record/Generation document、source claim、pairing evidence、extensions 和 rights evidence；规范化表与保留的原始 JSON 必须语义一致。数据库必须在 insert/update 边界阻断 source project/revision/run/file、case/prompt、case/asset-source 和 generation/prompt 或 generation/asset 的跨边界引用，不能只依赖当前 importer 的映射顺序。
- `REQ-008` (`required_behavior`): 数据库只记录 evidence/contract 状态，不得出现 canonical、classification、quality approval、rights approval、visibility、featured 或 publication 决策；local object-store harness 只能绑定 `127.0.0.1`，随机凭据和 Compose project 名由 Validator 在工作区外生成。
- `REQ-009` (`required_behavior`): package idempotency key 是跨进程唯一键。Importer 使用 PostgreSQL session advisory try-lock 覆盖对象校验/上传和最终事务；同一键并发第二 writer 必须得到稳定 `import_locked`，或在第一 writer 完成后只返回 `verified_existing`，不得重复写行或交叉提交。
- `REQ-010` (`required_behavior`): 全部数据库可见变更必须在一个显式 Psycopg transaction 内完成；任一 SQL/constraint/failure injection 触发 rollback，不能留下 staging/partial 行。对象先于 DB 写入且不可变；失败时不得删除可能已共享的正确内容寻址对象。
- `REQ-011` (`required_behavior`): 提供离线单元测试和 environment-sensitive live Compose Validator。live 必须实际启动 PostgreSQL 18.4 与隔离 S3-compatible service、重新生成 g0dam 100-case package、导入 100 张原图、下载复核全部对象、验证 DB 计数/引用、重跑、并发和故障恢复。
- `REQ-012` (`required_behavior`): Python venv/cache、Docker Compose credentials/env、Git mirror/worktree、extraction package、数据库导出、日志和临时文件全部位于 `C:/Users/admin/.codex/runtime/image2/TASK-0005` 或 Docker 管理空间；工作区不得出现运行数据、镜像、图片、volume、`.venv`、cache 或凭据。
- `INV-001`: `source_id + revision_sha` 是不可变 Source Revision；同一 source/revision 的原始 Prompt、source locator 和 Generation contract 不得被后续重跑 UPDATE 覆盖。
- `INV-002`: surrogate database IDs 和 timestamps 不参与业务身份或稳定摘要；自然键来自 source_id、revision_sha、source_case_key、prompt_id、generation_example_id、asset SHA-256 和 package idempotency key。
- `INV-003`: 原始 Prompt 必须逐字等于 Generation Example/Adapter Output `raw_text`；不能清洗、翻译、截断或以数据库编码转换改变语义。
- `INV-004`: 每个 `generation_outputs` 必须指向同一 source case version 的 `asset_source`，且该 asset source 指向已验证 `assets.content_sha256`；不存在 case-level 图片集合绕过 Generation Example。
- `INV-005`: `assets.content_sha256` 是主身份且与对象 key 一一对应；同一字节跨案例只存一个对象和一行 asset，不同来源关系保存在 `asset_sources`。
- `INV-006`: object key、bucket、byte_size、media_type 和 sha metadata 必须与 DB 一致；任何同 key 异内容/异 metadata 冲突 fail closed，不覆盖既有对象。
- `INV-007`: `source_claimed` 仍是来源声称，unknown 仍是 unknown；数据库和 inspect 输出不得转换为 official_verified。
- `INV-008`: prompt/asset rights 仍为 unknown/review_required evidence；不得创建 mirror_allowed、public、approved 或 auto_publish 状态。
- `INV-009`: 所有 100 个 package-valid case 必须整体提交或整体回滚；不能以“部分导入成功”完成本任务。
- `INV-010`: package manifest、semantic_digest 和固定 Commit 任一冲突不得通过修改期望值、删除既有库存或重写同一 revision 来解决。
- `INV-011`: 数据库失败后可能存在正确但不可见的内容寻址对象；这些对象不构成库存完成，不得由消费者枚举，重跑必须校验并复用。
- `INV-012`: local legacy MinIO 只作为 S3 compatibility test fixture；应用代码、数据库 schema、对象 key 和文档不得包含 MinIO 专属业务依赖或把它表述为生产批准。
- `INV-013`: `source_projects` 只保存跨 Commit 稳定的 source_id/repository_id 身份；完整 registry record 必须作为每个 immutable adapter run（或等价 revision-scoped record）的证据快照保存。registry 的 verified_commit_sha、status、rights 或 URL 变化不得重写历史，也不得阻止同一 repository_id 创建后续 Source Revision。
- `material_ambiguities`:
  - extraction package 不含图片字节。确认方案是由 importer 依据 package 的固定 source_path 与 registry Commit 重新打开安全 Git snapshot，并以 package hash 为强校验；不修改 TASK-0003 包格式。
  - PostgreSQL 与 S3 无全局事务。确认方案是 immutable object first + single DB transaction + DB-only visibility；失败对象可以成为不可见 orphan，不能产生 DB 引用缺失。
  - 当前 g0dam 每个 Generation document 只有一个 output_primary 且无 input，但 schema/表必须支持多 input/output；live 只断言实际 0 inputs/100 outputs。
  - legacy MinIO 预编译镜像晚于其官方归档前但早于最后 source-only security release。只允许 `minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e` 在回环、短生命周期、无多租户测试环境运行；生产必须另行选型和批准。
- `decisions_and_authority`:
  - 采用独立短链路 `inventory CLI → package loader → importer → PostgreSQL/S3`；`ingestion` 仍只负责来源提取和安全快照，不承载持久化逻辑。
  - Python S3 客户端采用 boto3 的标准 S3 API，以兼容 local harness、AWS S3 和 Cloudflare R2；不采用 MinIO 专属 SDK 作为业务合同。
  - PostgreSQL 固定 18.4；Compose image 固定 `postgres:18.4@sha256:3a82e1f56c8f0f5616a11103ac3d47e632c3938698946a7ad26da0df1334744a`。
  - 本任务只建 Source/Evidence inventory 和 original asset store；Canonical/Publication 不进入 schema。

# 4. 业务场景与规则

- `SCN-001` 首次成功: 空 DB/空私有 bucket，提供真实 published package。migration 完成后 importer 校验 package/固定快照、写入 100 原图并在一个事务中提交完整库存。
- `SCN-002` 幂等重跑: 相同 package、DB 和 bucket 已存在。Importer 重新验证自然键、DB 摘要和对象完整性，返回 `verified_existing`；行数、object count 和摘要不变。
- `SCN-003` 相同资产复用: 多个案例或未来来源引用同一 SHA-256。对象和 `assets` 只存在一次，`asset_sources` 保留全部来源关系；不得复制对象或丢失来源。
- `SCN-004` package 篡改: manifest/file hash、Adapter/GE schema、semantic digest、coverage 或 source/revision 不一致。运行在 advisory lock、snapshot、S3 和 DB 写之前失败。
- `SCN-005` source asset 漂移: source_path 缺失、路径逃逸、实际图片 hash/size/type 与 package 不同。不得上传错误对象，不得写数据库。
- `SCN-006` existing object conflict: 目标 hash key 已存在但下载 hash、size、content type 或 metadata 不一致。fail closed，不覆盖对象，不提交 DB。
- `SCN-007` 数据库故障: 对象已正确上传，但在任一 evidence table 写入或 commit 前失败。整个 DB transaction rollback；对象保留为不可见可复用 orphan，随后重跑可完成。
- `SCN-008` 并发同键: 两个进程同时导入相同 package。只有持有 advisory lock 的进程执行 writer 路径；第二进程 fail fast 或只读确认第一进程已完成，不产生重复。
- `SCN-009` migration 漂移: 已登记 migration version 对应 SQL checksum 改变。migration runner 非零退出，不执行后续 SQL。
- `SCN-010` 权利边界: 所有 g0dam prompt/asset rights 仍为 review_required/unknown。数据可进入内部库存和私有 bucket，但没有公开 URL、发布行或自动展示能力。
- `SCN-011` 后续 revision 边界: 同一 source_id/repository_id 的 registry record 因新 verified Commit、状态、URL 或 rights evidence 变化。旧 revision/run 保持不可变，新 revision/run 可以保存自己的 registry snapshot；不得因 project 行锁死旧 registry JSON 而 `source_conflict`。
- `RULE-001`: package root 必须位于工作区外且包含一个完整 published manifest；缺 manifest、candidate 目录或非 JSON 稳定文件不可消费。
- `RULE-002`: package loader 先完成静态校验，再建立任何外部连接；数据库/S3 的可用性不能使无效 package 产生副作用。
- `RULE-003`: registry record 与 package source/revision/adapter 必须闭合；source status/role/pilot/sync/ingestion 任一不符合均失败。
- `RULE-004`: `source_files` 对同一 revision/location 去重；case、prompt、asset source 和 pairing evidence 仍保存自己的 locator/evidence，不因 file 去重丢失 selector/native_id。
- `RULE-005`: 原始 contract JSON 以 JSONB 保存在 source case version 中，规范化表用于关系约束；两者在 importer 写入前做一致性检查。
- `RULE-006`: original object key 无扩展名，以 SHA-256 分层；media type 只来自实际 magic/合同一致结果，不信任文件扩展名或远端 Content-Type。
- `RULE-007`: 新对象上传后必须立即验证；既有对象不得盲目信任 HEAD/ETag，至少在首次复用或 formal Validator 中下载重新计算 SHA-256。
- `RULE-008`: S3 bucket 不创建 public policy/ACL，不调用 `put_object_acl`，不生成 presigned URL；读取已有 bucket 时必须 fail closed 检查 public bucket policy/ACL，读取/写入 object 时必须检查 public object ACL；Compose 端口仅绑定 loopback，remote plain HTTP endpoint无效。
- `RULE-009`: advisory key 由 package idempotency key 的稳定 hash 转为 PostgreSQL bigint；连接使用 autocommit 获取/释放 session lock，数据库写入使用显式 transaction，避免长期 idle-in-transaction。
- `RULE-010`: DB import 先检查同键 adapter run。相同 manifest+semantic digest 必须完整验证后返回 existing；同键不同 digest/manifest 必须 `package_conflict`。
- `RULE-011`: inventory `ready` 只存在于已 commit adapter run；没有 staging 行可供下游读取。对象本身不等于库存 ready。
- `RULE-012`: stable inspect summary 按自然键排序，排除 timestamps、surrogate IDs、endpoint、credentials、container/project 名和临时路径。
- `RULE-013`: live Validator 结束必须 `docker compose down -v --remove-orphans`，清理其外部临时 package/worktree/env/log；Docker image cache可保留但不计入仓库产物。
- `RULE-014`: 正式验证期间不得修改 TASK-0001/0002/0003、schemas、registry/audit、`ingestion/**` 或历史 `.task-runs/.work`；发现 producer 缺陷必须停止并建立变更任务。
- `RULE-015`: project identity 与 per-run registry evidence 分离；project equality 只比较稳定 repository identity，source/revision/run/file 与 case/prompt/asset/generation 的同域关系由 DB trigger、composite constraint 或等价 database-enforced check闭合。
- `STATE-001` import 状态: `package_verified → source_verified → snapshot_verified → assets_verified → objects_ready → database_transaction → inventory_ready`；任一失败进入 `failed`，不产生部分 DB ready。
- `STATE-002` object 状态: `absent → uploaded_verified` 或 `existing → content_verified`；冲突进入 `integrity_conflict`，禁止 overwrite。
- `STATE-003` database 状态: migration ready 后，adapter run 只可从不存在直接在单事务中成为 `ready`；没有外部可见 staging 状态。
- `FLOW-001`: `published extraction package + sources-v1 + fixed Git snapshot → original objects by SHA-256 → PostgreSQL Source/Evidence transaction → stable internal inventory summary`。

### Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| `DEP-001` | TASK-0003 package manifest/files | TASK-0005 hardened package loader/importer | producer-to-consumer contract | TASK-0003 docs/code/report + TASK-0004 baseline | confirmed | 不表示库存或对象已持久化 | manifest、idempotency、semantic digest |
| `DEP-002` | TASK-0002 schemas/semantics | DB evidence rows | public content contract | TASK-0002 deliverables | confirmed | contract_valid 不表示可公开 | Prompt/asset/GE/pairing/rights |
| `DEP-003` | sources-v1 fixed Commit | asset byte reacquisition | trusted source boundary | registry + TASK-0003 | confirmed | 不允许使用 source_url moving content | source/revision/path/hash |
| `REL-001` | content-addressed object | assets row | one object to one content hash | `1.md` 第 9 节 | confirmed | 对象存在不表示库存 ready | storage key/integrity |
| `REL-002` | asset_sources | generation_inputs/outputs | evidence reference | `1.md` 第 6 节 | confirmed | 不允许 case-level loose asset list | exact Prompt/output binding |
| `REL-003` | PostgreSQL adapter run | downstream Canonical/Publication | internal inventory handoff | Phase 1 sequence | confirmed | 不表示 canonical/rights/publish 已完成 | next task consumer boundary |
| `PERM-001` | review_required evidence | object storage/private inventory | storage permission boundary | `1.md` 第 3/12 节 | confirmed | 不授予公开展示 | bucket policy/public fields |

- `risk_sensitive_invariants`:
  - 数据库自然键和内容寻址 key 将成为后续去重、更新、回滚与发布依据；错误 identity 会造成长期重复或错误覆盖。
  - 对象存储和 PostgreSQL 是两个外部状态边界；必须明确可见性、锁、事务、孤立对象和恢复所有权。
  - 保存原始 JSON 与规范化表的双表示必须一致，不能一边通过 Schema、一边在 DB 关系映射中错配 Prompt/图片。
  - legacy MinIO 仅是隔离验证工具；任何无意的生产推广、公开端口或静态凭据都属于安全失败。
- `inapplicable_faces_with_reason`:
  - Canonical/duplicate/taxonomy：需要另外两个来源和真实跨来源存量，后续任务实现。
  - Publication/API/Web：当前 rights 不允许自动公开，且内部库存尚未完成发布门。
  - 图片派生规格：本任务先固定不可变 original 证据，转码和展示图另设媒体任务。
  - 定时同步/队列：仍使用显式 CLI；Commit 更新闭环在 pilot adapter 与发布链稳定后实现。

# 5. 当前证据与目标差异

- `FACT-001`: TASK-0003 已正式 COMPLETE，22/22 产物、17 个离线测试、真实固定 Commit 100-case 两次运行、aggregate、并发/故障恢复和 L4 独立审查均通过。
- `FACT-002`: TASK-0003 published package 只含 JSON；每个 Generation Example asset 有 content SHA-256、byte_size、media_type 和 repository source_path，但不保留图片字节。
- `FACT-003`: 现有 `ingestion.git_snapshot.fixed_snapshot` 与 `ingestion.assets.resolve_asset_path/read_asset` 已验证安全固定快照、路径 containment、magic、size 和 SHA-256，可作为只读 producer 能力复用。
- `FACT-004`: TASK-0004 已交付 database schema/migration、inventory package、generic S3 client、Compose harness、离线测试和 live Validator；其正式旧卡哈希为 `01ec2d8dc18b2326a578e321a5e55e61851e62be88450c32130a6f2143bcdac4`，旧 run 保持只读有效。
- `FACT-005`: 当前主机 Docker client/server 29.2.1、Docker Compose 5.0.2、uv 0.11.28 可用；正式 Python 运行使用外部 uv Python 3.12 环境，不能依赖系统 Python 3.8。
- `FACT-006`: g0dam 固定 Commit 指标为 100 valid/unique/exact/paired、pair_rate 1.0、broken 0、aggregate `ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0`。
- `FACT-007`: PostgreSQL 18.4 是当前已发布修复版本；官方 Docker image 支持 18.4。MinIO 社区仓库于 2026-04-25 归档，社区版转为 source-only，历史预编译镜像不再维护。
- `FACT-008`: 协调方对 TASK-0004 最终实现的代码级复核确认：当前对象层只检查 bucket ACL；当前 migration 只对 generation input/output 有局部 same-case trigger；当前 `source_projects` 保存并比较完整 registry record，无法自然接受后续 registry Commit/status/rights/URL 变化。
- `ASM-001`: formal live 执行期间 Docker registry、GitHub 和固定 Commit 可访问；任何不可用都属于 environment-sensitive 未通过，不得用旧收据替代。
- `ASM-002`: g0dam 当前 100 个有效案例的 output SHA-256 唯一，因此 live 期望 100 asset rows/objects；若真实 package 证据与 TASK-0001/0003 不同必须停止，而不是放宽计数。
- `current_execution_path`: 目前只能从 registry/固定 Commit 生成并校验外部 JSON package；没有将其持久化为可供后续内容层消费的内部库存路径。
- `target_delta`: 新增 generic S3 + PostgreSQL inventory consumer、migration、CLI、Compose harness、单元/真实集成验证，使 g0dam 的 100 个完整证据单元和 100 张原图形成稳定私有库存。
- `evidence_gaps`:
  - 尚无真实数据库 migration/constraints/immutability/transaction 证据。
  - 尚无内容寻址对象 upload/reuse/conflict/download-hash 证据。
  - 尚无 package → fixed snapshot → S3 → DB 的端到端 100-case 证据。
  - 尚无同键跨进程锁、DB rollback 与 orphan-object 安全重试证据。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `D:/image2/pyproject.toml`
  - `D:/image2/uv.lock`
  - `D:/image2/inventory/**`
  - `D:/image2/migrations/**`
  - `D:/image2/tests/inventory/**`
  - `D:/image2/docs/inventory/internal-inventory-v1.md`
  - `D:/image2/scripts/validate_internal_inventory.py`
  - `D:/image2/compose.yaml`
  - `D:/image2/.env.example`
  - `C:/Users/admin/.codex/runtime/image2/TASK-0005/**` 作为开发/验证 venv、cache、Git、package、Compose env/log 根目录
  - `C:/Users/admin/.codex/task-state/image2/**`，仅限正式生命周期自动解析的唯一 TASK-0005 canonical run
- `hard_protected_scope`:
  - 不修改 `D:/image2/1.md`、`config/sources-v1.yaml`、`reports/source-audit-v1.*`、现有 schemas、`docs/contracts/content-contract-v1.md`、`docs/ingestion/g0dam-extraction-v1.md`。
  - 不修改 `D:/image2/ingestion/**`、`tests/ingestion/**`、TASK-0003 fixtures/validator、TASK-0001/0002/0003/0004 卡片或其历史证据。
  - `D:/image2/.task-runs/**` 与 `D:/image2/.work/**` 只读。
  - 不写入真实云 S3/R2、外部生产数据库或用户现有 Docker Compose project/volume。
- `external_systems`:
  - Docker engine 与 registry：formal Validator 启停隔离 PostgreSQL/legacy MinIO test containers；使用唯一 project 名，结束删除其 containers/networks/volumes。
  - GitHub 固定 Commit：由 TASK-0003 安全 snapshot 能力读取，不执行来源代码。
  - PostgreSQL：只连接 Validator 创建的临时实例或调用者明确提供的 DSN。
  - S3-compatible API：只连接 Validator loopback endpoint 或调用者明确提供的 endpoint/bucket；凭据来自环境。
- `security_boundary`:
  - credentials 不进入 Git、命令行、JSON 输出、异常 message 或 Completion Report。
  - Compose ports 绑定 127.0.0.1，random high port；bucket private；不调用 public ACL/policy/presign。
  - package/source paths 必须 containment；S3 bucket/key/endpoint 严格配置，不接受 package 字段控制 bucket 或 endpoint。
  - SQL 全部参数化；migration 文件是仓库内受控 SQL，不执行 package 提供的 SQL。
- `data_boundary`:
  - 工作区只保存代码/SQL/docs/tests/compose，不保存真实 100 张图、数据库 volume、对象 volume、package 或凭据。
  - PostgreSQL 保存内部证据和原始 JSON；S3 保存原始图片字节；运行日志/收据保存在外部 canonical run。
- `stop_conditions`:
  - 需要修改 TASK-0002 schemas 或 TASK-0003 package/ingestion 才能闭合 importer。
  - 真实 package 无 repository-local source_path，必须新增外部 URL fetcher/SSRF 边界。
  - Docker/网络缺失影响 live evidence，可报告 validation pending；若影响依赖版本/架构则停止。
  - 需要引入 Canonical/Publication/公开 bucket 才能满足某个实现选择。
  - MinIO legacy harness 无法安全限制到 loopback/ephemeral，必须停止而不能改为生产部署。
- `protected_contracts_and_invariants`:
  - TASK-0002 Adapter Output v1 / Generation Example v1 字段、状态、引用、pairing 和禁止决策边界保持不变。
  - TASK-0003 published package 的 manifest、idempotency、semantic digest、固定 Commit、安全 snapshot 与失败恢复语义保持不变。
  - sources-v1 中 g0dam 的 source_id、repository_id/URL、Commit、status、family、pilot、sync、rights 和 ingestion policy 不变。
  - 原始 Prompt、source locations、source claim、rights evidence 和 asset content hash 不得在 DB 映射中被改写或升级。
  - private inventory、private object bucket 和“对象存在不等于库存 ready”的可见性边界保持不变。
  - 同一 source 的后续 Commit 必须能创建新 immutable revision/run；历史 registry snapshot 不被覆盖，project identity 不被 moving Commit/config 锁死。
- `authorization_limits`: 本任务授权在唯一外部 TASK-0005 runtime 下生成真实 g0dam package、只读获取登记的固定 Commit、启动并清理隔离 Docker Compose PostgreSQL/S3 test services、写入其临时数据库/私有 bucket，并修改 allowed_write_scope。它不授权连接或修改生产数据库/云 bucket、公开内容、选择生产 MinIO 替代品、处理其他来源或改变权威合同。
- `stop_if_scope_expands`:
  - 需要修改 TASK-0002 Schema、TASK-0003 package/producer、sources-v1 或固定审计指标才能通过。
  - 真实资产缺少 repository-local source_path，需要新增 URL fetcher、SSRF、重定向和远程缓存边界。
  - 需要图片转码/派生、Canonical、分类、去重、rights decision、Publication、API、Web、queue 或第二 Adapter。
  - 需要把 legacy MinIO 暴露到非 loopback、使用固定凭据、长期运行或描述为生产批准。
  - 需要停止、删除、复用或写入用户现有 Docker project/container/network/volume。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`:
  - `caller`: 操作者或正式 Validator 先调用 `python -m inventory migrate`，再调用 `python -m inventory import-package`；后续任务通过 `python -m inventory inspect` 或直接只读数据库消费 ready inventory。
  - `entry`: published package root、registry/audit、外部 Git data root，以及仅由环境变量提供的 PostgreSQL DSN 和 S3 endpoint/bucket/credentials。
  - `execution_path`: package/contract/source precheck → PostgreSQL session advisory lock → fixed snapshot asset revalidation → private content-addressed object verification/upload → one PostgreSQL transaction → committed ready adapter run → stable inspect summary。
  - `final_consumer`: 后续 Canonical/dedupe/taxonomy/rights/publication slice，以及 JoeSai/ConardLi Adapter 生成的同合同 package。
- `expected_touchpoints_or_search_anchors`:
  - 新 consumer package：`D:/image2/inventory`。
  - 新数据库 migration：`D:/image2/migrations/0001_internal_inventory.sql`。
  - 新测试/validator：`D:/image2/tests/inventory`、`D:/image2/scripts/validate_internal_inventory.py`。
  - 新本地基础设施/说明：`D:/image2/compose.yaml`、`D:/image2/.env.example`、`D:/image2/docs/inventory/internal-inventory-v1.md`。
  - 只读 producer anchors：`ingestion/pipeline.py::verify_published_package`、`ingestion/contracts.py`、`ingestion/registry.py`、`ingestion/git_snapshot.py::fixed_snapshot`、`ingestion/assets.py::resolve_asset_path/read_asset`。
- `wiring_to_final_consumer`:
  - `cli.py` 只处理命令、环境、稳定 JSON/exit code，不直接执行 SQL/S3/Git。
  - `package.py` 在任何 side effect 前建立不可变 ImportPlan，并保留 raw contract facts。
  - `object_store.py` 只管理 generic S3 original objects、内容完整性和 private bucket，不知道数据库 ready/publication。
  - `database.py` 独占 migration/checksum、session advisory lock、单事务关系写入、immutability 与 inspect query，不访问 Git/S3。
  - `importer.py` 是 package → snapshot → object → database 的唯一状态/恢复 owner；任何其他模块不得跨边界补偿写。
  - committed `source_adapter_runs.state=ready` 与完整 FK 关系是下游唯一可见库存入口；对象列表或临时运行不能替代。
- `failure_and_recovery`:
  - package/registry/contract 错误在 DB/S3/Git writer 前失败。
  - advisory lock 失败不等待无界时间；finally/连接关闭释放 session lock。
  - snapshot/asset/object 失败不启动 DB transaction；已正确写入的 immutable object 可以保留并在重跑强校验复用。
  - DB 写入全部位于一个显式 transaction；SQL、constraint、注入或 commit 失败统一 rollback，不留下 ready/staging partial rows。
  - existing object conflict 永不覆盖；existing package conflict 永不 UPDATE 同 revision；既有完整库存保持可读。
  - Validator 无论成功失败都清理其 worktree/package/tmp 和唯一 Compose project/volumes；不得广泛清理 Docker。
- `compatibility_and_error_semantics`:
  - CLI 成功退出 0；package/source、asset、object、migration、lock、database 和 internal error 使用不同稳定 error code，具体数值写入任务文档。
  - 不支持的 package/contract/migration version fail closed；破坏性 DB contract 变更必须新增 migration，不得改写已应用 migration。
  - generic S3 client 使用 path-style endpoint 配置兼容 local harness；AWS S3/R2 endpoint差异通过环境配置，不进入业务身份。
  - legacy MinIO test image/digest 是 validator 环境事实，不进入 DB/schema/object identity，也不构成生产兼容承诺。
- `implementation_freedom`: 在目标、表职责、自然键、私有边界和 Gate 不变时，执行者可选择 Python dataclass/typing 组织、SQL 索引名称、参数化批量插入方式、boto3 transfer primitive、advisory bigint 映射和测试 fake；不得新增没有当前消费者的 ORM、repository/service层、事件总线、通用 plugin system 或生产部署抽象。
- `selected_profile_obligations`:
  - `public-contract`: package consumer、migration/schema、CLI/inspect JSON、stable error/idempotency/object-key 与后续消费者语义必须明确并测试；不能用内部实现细节替代合同。
  - `external-boundary`: Git、Docker、PostgreSQL 和 S3 均设置有界连接/等待/清理；credentials不泄露；固定 Commit、对象内容和服务隔离必须由真实证据证明。
  - `configuration`: registry是source/Commit/rights权威；DB/S3/Compose/UV/TMP均由显式环境配置且路径/endpoint经过校验；package字段不能覆盖基础设施配置。
  - `stateful-runtime`: 明确 migration、session lock、object状态、transaction、ready visibility、orphan semantics、重跑/并发/故障恢复；正式测试必须覆盖每个状态窗口。

## 7.1 文件与职责布局

```text
python -m inventory
├── cli.py                 # 参数、环境加载、JSON/exit code；不含业务写入
├── package.py             # published manifest、合同、跨文件引用与 registry binding
├── object_store.py        # generic S3 content-addressed original object verify/put/get
├── database.py            # migration、advisory lock、单事务写入、inspect query
├── importer.py            # 唯一 orchestration owner 和状态推进
└── __main__.py

migrations/0001_internal_inventory.sql
compose.yaml               # isolated local integration harness only
scripts/validate_internal_inventory.py
```

- 不创建 service/repository/manager/utils 等空洞层；每个文件只有一个明确外部边界或 orchestration 责任。
- `inventory` 可以只读导入 `ingestion.pipeline.verify_published_package`、`ingestion.contracts`、`ingestion.registry`、`ingestion.git_snapshot` 和 `ingestion.assets`；不得修改 producer。
- `importer.py` 是唯一能组合 package、snapshot、S3、DB 的模块；object_store/database 不互相调用。

## 7.2 Database schema contract

- 所有表位于 `inventory` schema；`schema_migrations(version, checksum_sha256, applied_at)` 记录不可变 migration。
- 每个表使用 surrogate key 便于 FK，但必须建立本卡自然唯一键；stable inspect 不使用 surrogate/timestamps。
- `source_projects`: 只保存跨 Commit 稳定的 source_id、repository_id 身份；不得保存会随 revision/lifecycle 变化且又被 immutable equality 锁死的完整 registry record。
- `source_revisions`: source project + 40-char revision SHA，immutable unique。
- `source_files`: revision + source_path/source_url location unique。
- `source_adapter_runs`: revision、adapter id/version、contract version、package idempotency key、manifest hash、semantic digest、coverage/metrics/manifest、该次执行使用的完整 registry record JSONB，state 仅 `ready`。
- `source_parse_errors`: adapter run 下按 source_case_key 保存 quarantine error JSON。
- `source_cases`: project 下 stable source_case_key。
- `source_case_versions`: case + revision unique，指向 adapter run/source file，保存 locator、adapter record、Generation document JSONB 与 contract state。
- `prompt_records`: source case version + prompt_id unique，保存 original raw_text/language/source file/location/raw SHA。
- `assets`: content_sha256 PK、deterministic object key unique、byte_size/media_type/integrity state。
- `asset_sources`: source case version + asset_ref/natural locator unique，指向 asset/source file，保存 role/location。
- `generation_examples`: generation_example_id natural unique，指向同一 case version/prompt，保存 claim 和 contract state；DB 必须拒绝引用其他 case version 的 prompt。
- `generation_inputs`/`generation_outputs`: generation + ordinal unique，指向同 case version 的 asset_source；output 至少一条由 importer/constraint validation保证。
- `pairing_evidence`: generation + ordinal，保存 method/status/evidence JSON，只有合同允许的 strong pairing 可进入本次 ready inventory。
- `rights_records`: source case version unique，保存 prompt/asset evidence status、URLs、note；无 approval/publication 列。
- immutable evidence tables必须由数据库 trigger 或等价 DB-level约束拒绝 UPDATE/DELETE；migration 和后续显式管理任务除外。DB 还必须验证 case version 的 case/project、revision、adapter run、source file 同域，prompt/asset source 的 source file 与 case revision 同域，以及 generation 的 prompt/assets 与 case version 同域。

## 7.3 Import algorithm

1. 校验 runtime/package root 不在 workspace，读取环境但不输出 secrets。
2. 完整验证 published package、合同、metrics 和 registry binding，构造只读 ImportPlan；此阶段无 DB/S3 side effect。
3. 连接 PostgreSQL autocommit session，以 package idempotency key 获取 `pg_try_advisory_lock`；失败返回 `import_locked`。
4. 在锁内检查已存在 adapter run：若自然键、manifest、semantic digest 和 inspect/object integrity 全部一致，返回 `verified_existing`；有差异 `package_conflict`。
5. 通过 registry 固定 Commit 创建外部安全 snapshot。按 source_path 对 unique asset 排序，重新 hash/magic/size，与 package 对比。
6. 对每个 unique SHA object：若不存在则 put + head verify；若存在则 get/rehash verify；不 overwrite conflict。
7. 使用一个显式 PostgreSQL transaction 按 source → revision/files/run → cases/versions/prompts/assets/sources → generations/edges/pairings/rights 的确定顺序写入。
8. commit 前运行关系与计数断言：coverage 守恒、100 case/GE/output、0 unresolved/parse error、全部 FK/自然键闭合、全部对象已验证。
9. commit 后生成 stable inspect summary；finally 释放 advisory lock、清理 worktree；对象不因 DB failure 删除。

## 7.4 Compose harness

- PostgreSQL 使用固定 `postgres:18.4` manifest digest；MinIO 使用固定 legacy digest，只在 `127.0.0.1` 随机映射端口、随机强凭据、唯一 project/volume 下运行。
- `compose.yaml` 不含实际密码和固定宿主端口；由 Validator 外部 env 提供。
- `.env.example` 只列变量名与非秘密示例，不提供可复用生产凭据。
- Validator 自己轮询 PostgreSQL/S3 readiness，并在 `finally` 无条件执行 `down -v --remove-orphans`。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`, `REQ-002`, `REQ-003`, `INV-001`, `INV-003`, `INV-007`, `INV-008`
- `owns_behavior`: 建立 inventory CLI、published package/contract loader、registry binding 和稳定 ImportPlan。
- `target_delta`: 从“消费者自行相信 JSON 目录”变为“所有外部写入前完成完整 package/contract/source 校验”。
- `business_result`: 后续持久化只接收一个来源/版本/合同闭合的不可变计划。
- `behavior_faces`:
  - `normal`: 合法 package 解析成 100-case ImportPlan。
  - `boundary`: stable ordering、多 input/output schema支持、unknown/source_claimed原样保留。
  - `failure`: manifest/file/schema/reference/metrics/registry/commit 任一冲突。
  - `empty`: 空 records/GE 或无 output 不可进入 import。
  - `repeated`: 同 package plan digest 一致。
- `state_change`: untrusted package → package_verified/source_verified ImportPlan；失败无外部连接写入。
- `data_flow`: package JSON + registry/audit/schemas → validated plan。
- `integration_edges`: TASK-0003 verifier/contracts → inventory importer。
- `expected_touchpoints`: `inventory/cli.py`, `inventory/package.py`, unit tests。
- `scope_boundary`: 不创建 DB/S3 状态。
- `linked_tests`: `TEST-001`
- `stop_conditions`: package handoff缺失必须字段且需要修改 producer contract。

### TASK-002

- `links`: `OBJ-001`, `REQ-004`, `REQ-007`, `REQ-009`, `REQ-010`, `INV-001`, `INV-002`, `INV-004`, `INV-009`
- `owns_behavior`: 建立 PostgreSQL migration、自然键/FK/immutability、advisory lock、单事务 import 与 inspect summary。
- `target_delta`: 从无持久层变为可迁移、不可部分提交、可幂等检查的 Source/Evidence inventory。
- `business_result`: 后续内容层拥有稳定且可追溯的内部数据库消费面。
- `behavior_faces`:
  - `normal`: 空库 migration + 100-case transaction commit。
  - `boundary`: migration 重跑、同 package verified_existing、多 input/output表结构。
  - `failure`: checksum drift、constraint/SQL/failure injection、package conflict。
  - `empty`: 无 ready adapter run 不可 inspect 为完成。
  - `repeated/concurrent`: session advisory single writer，无重复自然键。
- `state_change`: schema absent → migrated；package absent → one ready adapter run + complete evidence rows。
- `data_flow`: ImportPlan + verified objects → one PostgreSQL transaction → stable summary。
- `integration_edges`: importer → database.py → PostgreSQL 18.4。
- `expected_touchpoints`: `migrations/**`, `inventory/database.py`, tests/docs。
- `scope_boundary`: 不建 Canonical/Publication/FTS/pgvector 表。
- `linked_tests`: `TEST-002`, `TEST-004`
- `stop_conditions`: 需要跨数据库或分布式 transaction 才能满足当前单库目标。

### TASK-003

- `links`: `OBJ-001`, `REQ-005`, `REQ-006`, `REQ-008`, `INV-005`, `INV-006`, `INV-011`, `INV-012`
- `owns_behavior`: 从固定 snapshot 重新验证 original bytes，并通过 generic S3 API 内容寻址存储/复用/冲突检测。
- `target_delta`: 从 package 仅有 hash/locator 变为私有对象桶中可由 hash 验证的原始资产。
- `business_result`: 后续媒体与发布任务可以引用稳定 original object，而不依赖上游仓库在线状态。
- `behavior_faces`:
  - `normal`: 100 absent objects 上传并验证。
  - `boundary`: 同 hash 多 source、existing correct object、不同 media types。
  - `failure`: path/hash/size/type 漂移、S3 error、existing conflict。
  - `empty`: asset set 为空不能完成 g0dam inventory。
  - `repeated`: object count不增长，内容 hash 不变。
- `state_change`: source-only asset evidence → private verified content-addressed original objects。
- `data_flow`: fixed snapshot bytes → local SHA/magic → S3 put/get/head → verified object facts。
- `integration_edges`: importer → ingestion snapshot/assets → object_store.py → S3 endpoint。
- `expected_touchpoints`: `inventory/object_store.py`, Compose, tests/validator/docs。
- `scope_boundary`: original only；不转码、不公开、不做 URL fetcher。
- `linked_tests`: `TEST-003`, `TEST-004`
- `stop_conditions`: 真实 pilot 资产不是 repository-local path，需要新增 SSRF/remote fetch架构。

### TASK-004

- `links`: `OBJ-001`, `REQ-011`, `REQ-012`, `SCN-001` 至 `SCN-010`
- `owns_behavior`: 建立离线测试、真实 Compose 100-case validator、故障/并发/清理证据和运行文档。
- `target_delta`: 从实现声明变为可重复的真实 DB/S3/固定 Git 集成证据。
- `business_result`: 确认内部库存边界可以供后续 pilot Adapter 共用。
- `behavior_faces`:
  - `normal`: Compose start → migrate → extract → import → inspect/download verify → cleanup。
  - `failure`: services/network/package/object/DB injections均真实报告。
  - `repeated/concurrent`: import idempotency、single writer、stable summary。
- `state_change`: TASK-0004 baseline → formally verified TASK-0005 hardened inventory completion。
- `data_flow`: validators → external runtime/containers → receipts/Completion Report。
- `integration_edges`: all task components + Docker/GitHub。
- `expected_touchpoints`: tests, `scripts/validate_internal_inventory.py`, docs。
- `scope_boundary`: validator管理的containers/volumes only，不碰用户现有服务。
- `linked_tests`: `TEST-001` 至 `TEST-004`
- `stop_conditions`: 无法安全隔离/清理 Docker project，或 live evidence 只能由 mock 代替。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`
- `end_to_end_entry`: `python -m inventory import-package --registry config/sources-v1.yaml --audit reports/source-audit-v1.json --package-root <external-package> --data-root <external-git-root> --json`
- `shared_contract_state_data`: package idempotency/manifest/semantic digest、source/revision/adapter、stable case/prompt/asset/generation IDs、object key、DB natural keys、rights evidence、import state。
- `final_consumer`: 后续 Canonical/dedupe/taxonomy/rights/publication slice；第二、第三 pilot Adapter 也复用本 inventory importer。
- `cross_task_failure_path`: package、snapshot、object、lock、SQL 或 constraint 任一失败均不得产生新的 ready adapter run；既有库存保持不变，正确 immutable objects可安全复用。
- `linked_test_evidence_gate`: `TEST-003`, `TEST-004` / `EV-003`, `EV-004` / `GATE-003`, `GATE-004`

# 9. 验证与验收

- `consumer_chain_validation`: 必须证明 published package → fixed snapshot assets → private content-addressed objects → PostgreSQL Source/Evidence rows → stable inspect summary 的完整链；单独 Schema、mock S3 或 SQL 文件存在不能替代 live assembly。
- `real_integration_evidence`: `TEST-003`/`TEST-004` 使用真实 PostgreSQL 18.4、隔离 S3-compatible container、公开固定 Commit 和完整 100-case package；不能用一条 fixture 外推。
- `failure_recovery_ownership_validation`: `package.py` 在 side effect 前拒绝无效输入；`object_store.py` 只管理不可变对象且不决定 DB ready；`database.py` 独占 advisory lock/transaction/constraints；`importer.py` 独占顺序和跨边界状态推进。故障注入必须证明没有遗漏或双重 owner。

### RISK-001

- `links`: `REQ-002`, `REQ-003`, `TEST-001`, `TEST-003`
- `description`: 消费者跳过 manifest/contract/registry 校验，把被篡改或错误 Commit package 持久化为权威库存。
- `mitigation`: 所有静态闭合先于外部写入，live/negative tests校验 DB/S3零副作用。

### RISK-002

- `links`: `REQ-005`, `INV-004`, `TEST-001`, `TEST-003`
- `description`: importer 仅信任 package hash，不重新绑定固定 source_path，导致错误图片仍进入正确数量的库存。
- `mitigation`: fixed snapshot重新读取、逐 asset hash/size/type与同 case locator闭合。

### RISK-003

- `links`: `REQ-006`, `INV-005`, `INV-006`, `TEST-003`
- `description`: 内容寻址 key 已有错误/公开对象，或 bucket policy/ACL、object ACL、metadata、传输协议被盲目信任，导致内部原图被覆盖或公开。
- `mitigation`: deterministic key + local hash + existing object download/rehash + bucket policy/ACL + object ACL + remote HTTPS检查 + conflict no-overwrite。

### RISK-004

- `links`: `REQ-009`, `REQ-010`, `SCN-007`, `SCN-008`, `TEST-004`
- `description`: 并发或中途失败产生重复自然键、部分 DB 行或 DB 引用缺失对象。
- `mitigation`: session advisory lock、objects-first、single transaction、commit前 closure checks、failure injection。

### RISK-005

- `links`: `INV-001`, `INV-003`, `REQ-007`, `TEST-002`
- `description`: JSONB 与规范化表映射不一致，或 DB 允许跨 project/revision/case 的 Prompt、file、asset、generation 引用，造成来源链在 importer bug 后仍可提交。
- `mitigation`: 写入前双表示对比、同域 database triggers/composite constraints、FK/unique/check/immutability、稳定 inspect与主动错误 insert 断言。

### RISK-006

- `links`: `REQ-008`, `INV-008`, `INV-012`, `TEST-003`
- `description`: 私有内部库存被误当发布，或 legacy MinIO test service 暴露/推广到生产。
- `mitigation`: schema无发布列、bucket无public操作、loopback/random credentials、文档明确legacy local-only、生产另行批准。

### RISK-007

- `links`: `INV-011`, `SCN-007`, `TEST-004`
- `description`: DB失败后的 orphan对象被误报为完成，或清理逻辑删除其他案例共享的正确对象。
- `mitigation`: readiness仅由 committed adapter run定义；失败不删除content-addressed final objects；重跑验证复用。

### RISK-008

- `links`: `REQ-011`, `REQ-012`, `TEST-003`
- `description`: live Validator 依赖 Docker/Git/registry，历史 pass 或 mock 被错误复用。
- `mitigation`: environment_sensitive=true，当前 formal run实际启动/下载/导入/清理；失败只报告真实pending/failed。

### RISK-009

- `links`: `INV-001`, `INV-013`, `SCN-011`, `RULE-015`, `TEST-002`, `TEST-003`
- `description`: immutable `source_projects` 锁死首个 registry JSON/Commit，使同一长期来源的下一 Commit 或 lifecycle/rights 更新无法创建新 revision。
- `mitigation`: project只存稳定repository identity；完整registry snapshot随每个adapter run/revision保存；测试证明不同registry snapshot可共存且历史不被更新。

### TEST-001

- `links`: `TASK-001`, `REQ-001`, `REQ-002`, `REQ-003`, `RISK-001`, `RISK-002`
- `method`: 离线构造 published package 正例与 manifest extra/missing/hash、schema/reference、metrics/source/commit、empty/duplicate/tamper 负例；使用 fake external boundaries断言任何负例不调用 DB/S3/snapshot writer；直接验证 ObjectStoreConfig 对非 loopback HTTP、带凭据/path/query 的 endpoint fail closed，并验证 public bucket policy/bucket ACL/object ACL 判定覆盖。
- `expected_observable_result`: 合法 sample 生成稳定 ImportPlan；每个非法输入返回稳定错误码且 side-effect call count 为零；非 loopback HTTP 和任一公开策略/ACL 都被稳定拒绝。
- `failure_path_covered`: untrusted package、contract drift、source mismatch、partial/extra files、不安全 endpoint、公开 bucket/object 配置。
- `cannot_prove`: 不证明真实 PostgreSQL/S3/GitHub 可用。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: pytest清单、正例plan summary/digest、每类负例error code、side-effect zero断言、endpoint与bucket policy/bucket/object ACL矩阵；实际结果进入正式 receipt/sidecar。

### TEST-002

- `links`: `TASK-002`, `REQ-004`, `REQ-007`, `INV-001`, `INV-002`, `INV-003`, `INV-004`, `INV-007`, `INV-008`, `RISK-005`
- `method`: 离线检查 migration顺序/checksum和 SQL contract；通过 fake DB transaction/repository覆盖自然键映射、project identity与per-run registry snapshot分离、JSONB/normalized一致性、input/output closure、rollback与stable inspect；真实同域约束由 TEST-003补足。
- `expected_observable_result`: mapping精确、source project不被moving Commit/config锁死、自然键稳定、timestamps/surrogate不进入digest、错误引用在commit前失败。
- `failure_path_covered`: migration drift、跨revision生命周期冻结、错配、identity pollution、partial mapping。
- `cannot_prove`: mock不能证明PostgreSQL DDL/trigger/transaction真实行为。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: migration checksums、project/per-run registry storage断言、mapping table/count、immutability/rollback fake assertions、两次 stable summary；实际结果进入正式 receipt/sidecar。

### TEST-003

- `links`: `OBJ-001`, `ASSEMBLY-001`, `TASK-002`, `TASK-003`, `REQ-004` 至 `REQ-008`, `INV-004` 至 `INV-008`, `RISK-002`, `RISK-003`, `RISK-005`, `RISK-006`
- `method`: live Validator 启动隔离 PostgreSQL 18.4/S3 service，应用 migration两次；重新执行 TASK-0003 extraction生成真实 package；首次 import后查询全部表并下载hash全部100 objects；确认新对象 ACL 非公开，再主动设置公开bucket policy和公开existing object ACL并要求 importer拒绝；直接插入 cross-project revision、cross-revision adapter run/source file/case、cross-case prompt/asset source、generation-to-foreign-prompt/asset 关系并要求数据库拒绝；证明同repository identity可保存另一revision/run及变化后的 Commit/status/rights/URL registry snapshot；运行 inspect并与package/固定指标逐项对比。
- `expected_observable_result`: 1 project/revision/run，101 source_files，100 cases/versions/prompts/assets/asset_sources/GE/outputs/pairings/rights，0 inputs/parse errors，100 private objects；新对象 ACL 私有，public policy/object ACL 与所有跨域引用被拒绝；project identity允许后续revision snapshot而不改写历史；原始 Prompt/locator/claims/rights不变；aggregate与Commit精确匹配。
- `failure_path_covered`: real DDL/同域constraints、长期revision、真实Git bytes、S3 policy/ACL/put/get/head、全量关系闭合、legacy harness isolation。
- `cannot_prove`: 不证明生产S3/R2、未来Commit、其他来源、公开发布或派生图片。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: Docker/image digests与loopback ports（不含secrets）、service health、migration receipts、package manifest/Commit/metrics、DB table counts/natural-key digest、100 object keys/metadata/download hashes/new-object ACL、public bucket policy/object ACL拒绝、逐类cross-domain DB insert拒绝、future revision与变化后registry snapshot共存证明、cleanup结果。

### TEST-004

- `links`: `ASSEMBLY-001`, `TASK-002`, `TASK-003`, `TASK-004`, `REQ-009`, `REQ-010`, `INV-009`, `INV-011`, `SCN-002`, `SCN-006`, `SCN-007`, `SCN-008`, `RISK-004`, `RISK-007`, `RISK-008`
- `method`: 在live环境对同一package重跑并比较 summary/row/object counts；并发启动两个import；分别注入 after-lock、after-first-object、after-all-objects、mid-DB、before-commit故障；预置同key错误对象验证no-overwrite；每次比较 DB前后snapshot与正确对象复用。
- `expected_observable_result`: 重跑 verified_existing且摘要不变；并发single writer；所有故障DB无partial ready/rows，正确objects可留存并在重跑复用，冲突对象不覆盖；最终完整导入成功。
- `failure_path_covered`: cross-boundary crash window、DB rollback、orphan semantics、same-key concurrency、object conflict。
- `cannot_prove`: 不证明跨数据库集群或多region锁/复制；本任务只保证单PostgreSQL协调域。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: idempotent two-run summaries、并发进程结果/advisory lock、failure matrix、每次DB table snapshot、object count/hash、conflict object before/after、successful recovery、container/volume/temp cleanup。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "internal-inventory-offline",
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
        "tests/inventory",
        "-q"
      ],
      "cwd": ".",
      "timeout_seconds": 240,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "reports/source-audit-v1.json",
        "schemas/adapter-output-v1.schema.json",
        "schemas/generation-example-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "docs/ingestion/g0dam-extraction-v1.md",
        "pyproject.toml",
        "uv.lock",
        "inventory",
        "migrations",
        "tests/inventory",
        "docs/inventory/internal-inventory-v1.md",
        "compose.yaml"
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
      "validator_id": "internal-inventory-compose-live",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "scripts/validate_internal_inventory.py",
        "--registry",
        "config/sources-v1.yaml",
        "--audit",
        "reports/source-audit-v1.json",
        "--source-id",
        "g0dam-work-prompts",
        "--expected-commit",
        "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "--expected-cases",
        "100",
        "--expected-aggregate",
        "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0",
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
        "docs/ingestion/g0dam-extraction-v1.md",
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "inventory",
        "migrations",
        "tests/inventory",
        "docs/inventory/internal-inventory-v1.md",
        "scripts/validate_internal_inventory.py",
        "compose.yaml"
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
| `GATE-001` | package/source pre-write closure | `TASK-001` / `TEST-001` | package/contract/registry全部闭合，所有负例零副作用 | `EV-001` | 不证明真实DB/S3 |
| `GATE-002` | migration与关系映射 | `TASK-002` / `TEST-002` | migration/checksum、稳定project identity/per-run registry、自然键、原文、引用、摘要与rollback逻辑通过 | `EV-002` | 不证明真实PostgreSQL DDL |
| `GATE-003` | 真实100-case库存与对象 | `TASK-003` / `TASK-004` / `ASSEMBLY-001` / `TEST-003` | 固定Commit全量导入，DB计数/同域关系、100 objects下载hash、bucket policy/object ACL、future revision与rights/private边界全部通过 | `EV-003` | 不证明生产对象存储或发布 |
| `GATE-004` | 幂等、并发、跨边界恢复 | `TASK-002` / `TASK-003` / `TASK-004` / `ASSEMBLY-001` / `TEST-004` | 重跑稳定、single writer、DB无partial、orphan可安全复用、object conflict不覆盖 | `EV-004` | 不证明多集群分布式事务 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `pyproject.toml`
  - `uv.lock`
  - `inventory/__init__.py`
  - `inventory/__main__.py`
  - `inventory/cli.py`
  - `inventory/package.py`
  - `inventory/importer.py`
  - `inventory/database.py`
  - `inventory/object_store.py`
  - `migrations/0001_internal_inventory.sql`
  - `compose.yaml`
  - `.env.example`
  - `docs/inventory/internal-inventory-v1.md`
  - `tests/inventory/test_package.py`
  - `tests/inventory/test_database_contract.py`
  - `tests/inventory/test_object_store.py`
  - `tests/inventory/test_importer.py`
  - `scripts/validate_internal_inventory.py`

### 必交产物

- `pyproject.toml`
- `uv.lock`
- `inventory/__init__.py`
- `inventory/__main__.py`
- `inventory/cli.py`
- `inventory/package.py`
- `inventory/importer.py`
- `inventory/database.py`
- `inventory/object_store.py`
- `migrations/0001_internal_inventory.sql`
- `compose.yaml`
- `.env.example`
- `docs/inventory/internal-inventory-v1.md`
- `tests/inventory/test_package.py`
- `tests/inventory/test_database_contract.py`
- `tests/inventory/test_object_store.py`
- `tests/inventory/test_importer.py`
- `scripts/validate_internal_inventory.py`

### 完成与回写规则

- `documentation_impact`: updated；新增内部库存 schema/migration、package consumer、S3 original-object contract、运行/恢复/legacy MinIO test-harness 说明，不修改上游设计基线或发布合同。
- `repository_hygiene_requirement`:
  - 只保存代码、SQL、Compose定义、无秘密env示例、文档和测试；不保存真实图片、package、DB dump/volume、object volume、container log、credentials或Docker export。
  - runtime/venv/cache/package/Git/Compose env/log固定在 `C:/Users/admin/.codex/runtime/image2/TASK-0005`；正式命令使用 `PYTHONDONTWRITEBYTECODE=1`、Python `-B`、pytest no cacheprovider。
  - `D:/image2/.task-runs` 与 `.work` 保持只读；正式证据使用工作区外 canonical run。
  - Compose formal project/containers/networks/volumes完成前必须清理；不得停止/删除用户其他Docker资源。
  - 当前工作区不是 Git repository，因此不要求 commit；Completion Report 必须覆盖全部 18 个必交文件和 protected scope未修改。
- `external_review`: policy=never；reason=任务要求 L4 独立语义审查与真实 DB/S3/Git integration，暂无额外外部模型审阅需要；MinIO生产替代选型不在本任务做决策。
- `non_completion_rules`:
  - 任一必交文件、两个正式 Validator、live 100-case DB/S3 证据、独立审查或 Completion Report 缺失时不得完成。
  - package/Commit/aggregate/100-case 指标不匹配时不得修改期望值或只导入部分。
  - DB缺任一核心表/约束/自然键/immutability，或 100-case引用不闭合时不得完成。
  - object key不是内容寻址、存在同key异内容被覆盖、未下载复核全部100 objects、bucket可公开或出现presigned/public ACL时不得完成。
  - 未检查 public bucket policy/public object ACL，或允许非loopback HTTP endpoint时不得完成。
  - DB允许跨project/revision/case的source file、adapter run、prompt或asset/generation引用时不得完成。
  - `source_projects` 锁死完整registry/verified Commit而使同一repository_id不能保存后续revision/run snapshot时不得完成。
  - 同 package 重跑增加行/object、同键并发多writer、failure injection留下partial ready DB或错误object时不得完成。
  - source claim/rights被提升、出现canonical/classification/publication/visibility字段或行为时不得完成。
  - 修改 protected producer/contract/registry/audit/history证据时不得完成。
  - venv/cache/package/images/DB/object volumes/credentials/log写入工作区，或Compose资源未清理时不得完成。
  - Docker/Git网络失败只能报告真实validation pending/failed；不得用mock/历史receipt替代live pass。
  - 需要URL fetcher、图片派生、第二Adapter、Canonical/Publication/API/Web/queue时停止并创建后续任务，不得扩张TASK-0005。

执行时将 `CODEX_TASK_STATE_ROOT` 固定为 `C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0005/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0005/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0005/tmp`。唯一 TASK-0005 canonical run 必须记录 package/Commit、Docker image digests、migration receipts、100-case DB/object evidence、并发/故障矩阵、legacy harness隔离与清理、L4独立审查、最终新鲜度和 Completion Report；不得把 secrets 写入任何证据。
