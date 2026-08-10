---
task_contract_version: 3
card_id: "TASK-0006"
title: "接入 JoeSai Markdown pilot 并验证双来源库存共存"
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
blocked_by: []
---

# 1. 任务身份与就绪状态

- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`:
  - 用户目标模式授权：沿已确认的“固定高价值来源、可提取图片和对应 Prompt”方向持续执行，逐个完成 Phase 1 pilot 的真实纵向闭环。
  - `D:/image2/1.md`，重点是来源固定、Adapter、Generation Example、内部库存、权利与发布 fail-closed 边界。
  - `D:/image2/config/sources-v1.yaml`：JoeSai 与 g0dam 的来源身份、固定 Commit、Adapter 策略、pilot/sync/publication/rights 配置。
  - `D:/image2/reports/source-audit-v1.json` 与 TASK-0001 只读历史证据：两个来源的全量固定 Commit 指标与 aggregate。
  - TASK-0002 已冻结的 Adapter Output v1、Generation Example v1 Schema、语义 Validator 和三类 pilot fixture。
  - TASK-0003 已验证的 g0dam fixed-commit extraction package；TASK-0004/0005 已验证并加固的通用 PostgreSQL/S3 内部库存。
  - JoeSai 固定 Commit `6f9b01fd21efbc05cfdde1176fc988013d3c4a9b` 的公开 Git 内容；只读取静态文件，不执行上游代码。
- `decision_owner`: 用户拥有来源、合同、发布和风险边界的最终决定权；执行者可在本卡确认的职责与文件范围内选择局部实现细节。
- `material_unknowns`:
  - 当前 extraction pipeline、registry eligibility 和异常捕获仍硬编码 g0dam；必须先以最小边界泛化后才能真实接入第二来源。
  - 现有 package/metrics `schema_version` 名称带 g0dam 历史前缀。新来源必须使用中性版本名，同时保持 g0dam 既有稳定输出完全不变。
  - Docker、GitHub 或公开固定 Commit 在 live Validator 时可能暂时不可用；该验证为 environment-sensitive，失败不得用历史结果或 mock 冒充通过。
  - JoeSai repository license 为 MIT，但 Prompt 与资产 publication policy 均为 review_required；本任务只进入私有库存，不授权公开发布。

# 2. 业务目标

- `actor`: Source Manager、Adapter pipeline、内部库存消费者与后续第三 pilot 实施者。
- `workflow_and_trigger`: g0dam 已打通且库存已加固；现在用结构不同的 manifest + Markdown 来源验证 extraction 与 inventory 确实是多来源架构，而非只对单一 JSON 样本成立。
- `single_outcome`: 从 registry 中 JoeSai 固定 Commit 全量提取 50 个 manifest→Markdown Prompt→example image 强配对案例，生成确定性 published package，并与 g0dam 100-case package 一起导入同一隔离 PostgreSQL/S3 库存，证明两个来源可共存、可独立追溯、可幂等重放且不提升权利或发布状态。
- `observable_results`:
  - `RESULT-001`: registry 与 Adapter dispatch 支持 g0dam 和 JoeSai 两个已实现策略，未实现的策略在任何 Git/网络副作用前 fail closed。
  - `RESULT-002`: JoeSai Adapter 从 `data/prompts.json` 的 50 个唯一 slug 精确定位 50 个 Markdown 页和 50 个 manifest 指定图片，逐字保留英文 fenced Prompt，并保留中文 Prompt 与来源元数据。
  - `RESULT-003`: 50 个 Adapter records、50 个 resolved Generation Examples、50 张真实图片和 audit 指标全部闭合；两次完整提取的稳定文件、manifest 和 semantic digest 相同。
  - `RESULT-004`: g0dam 的 legacy package/metrics schema 名、稳定内容、100-case 指标和 aggregate 不发生回归；JoeSai 使用中性 extraction package/metrics schema。
  - `RESULT-005`: 同一隔离 PostgreSQL/S3 中同时存在 g0dam 与 JoeSai 两个 project/revision/run；150 个 case/prompt/generation 关系按来源隔离，内容寻址资产按真实 hash union 存储，两个 package 重放均返回 verified_existing 且全局状态不增长。
  - `RESULT-006`: JoeSai 的 manifest/Markdown/图片解析、提取故障、同键并发、package 导入和资源清理都有本次新鲜证据；无公开 bucket、publication、rights approval、API 或网页副作用。
- `non_goals`:
  - 不实现 ConardLi 或其他来源 Adapter。
  - 不实现分类、去重决策、Canonical Example、Rights Review UI、Publication Layer、API、搜索或网页。
  - 不修改来源名单、固定 Commit、TASK-0001/0002 Schema 与合同语义、TASK-0001 至 TASK-0005 卡片或历史执行证据。
  - 不改变 g0dam 既有 published package 的稳定 JSON 内容、schema 名、semantic digest 算法或 live 指标。
  - 不迁移或重构 PostgreSQL schema、对象存储安全策略、导入事务与故障矩阵；本任务消费 TASK-0005 已验证的通用能力。
  - 不执行 JoeSai 仓库脚本、Node/Python 代码、Hook、submodule、Git LFS filter 或包安装。

# 3. 需求质疑与确认

- `user_statement`: skill 项目无需考虑，稳定固定高价值案例多且能提取对应图片和提示词的项目作为长期内容来源，按已确认方向持续严谨执行。
- `REQ-001` (`required_behavior`): 将 prompt 规范化/hash 和 Adapter 错误基类放入来源中立边界；`G0damAdapterError` 保持兼容，g0dam 输出不可因重构改变。
- `REQ-002` (`required_behavior`): registry loader 必须继续验证 active、pilot、sync、canonical、full ingestion、auto_publish=false 和完整固定 Commit，并按“支持的 adapter_strategy → 唯一 structure_type”映射接受 g0dam/JoeSai；未实现或结构不匹配的策略在 snapshot 前拒绝。
- `REQ-003` (`required_behavior`): extraction pipeline 必须通过一个显式、小型 Adapter dispatch 选择 parser，不再直接 import/call g0dam；不得引入插件系统、动态 import 或上游可执行扩展点。
- `REQ-004` (`required_behavior`): JoeSai Adapter 必须把 `data/prompts.json` 作为 case discovery 与配对清单权威源，要求唯一 slug、固定字段和类型、安全 category/slug/example_image，并精确解析 `prompts/{category}/{slug}.md`。
- `REQ-005` (`required_behavior`): 每个 Markdown 页必须有与 manifest `title` 一致的 H1，随后依次为 `Best For`、唯一 `Prompt (EN)` text fence、唯一中文 Prompt text fence，并只允许可选的 `Why It Works`；缺失、重复、歧义、顺序错误、额外 case 页或未登记 example image 必须 fail closed。
- `REQ-006` (`required_behavior`): 主 Prompt 为 `Prompt (EN)` fence 内文本，统一换行到 LF 但不改写内部内容；NFC/trim 只用于长度和 hash。中文 Prompt、Best For、可选 Why It Works 及完整 manifest 字段进入 `joesai.source` namespaced extensions。
- `REQ-007` (`required_behavior`): 每条 case 由同一 manifest row 明确绑定 slug、Markdown 页和 `example_image`；source_case_key 基于 source_id+slug，Prompt ID 基于中立规范化 hash，图片由现有安全资产解析器读取并形成 output_primary。
- `REQ-008` (`required_behavior`): JoeSai source claim 保持 unknown，rights 保持 unknown/review_required evidence，不因仓库名、README、MIT license 或 registry model_scope 提升为模型验证、mirror_allowed 或 publishable。
- `REQ-009` (`required_behavior`): 新 JoeSai package/metrics 使用 `extraction-package/v1` 与 `extraction-metrics/v1`；现有 g0dam 继续生成 `g0dam-extraction-package/v1` 与 `g0dam-extraction-metrics/v1`。验证器只接受明确支持的版本与对应内容。
- `REQ-010` (`required_behavior`): 提供真实形状最小 fixture、严格正负例、通用 dispatch/registry 测试和 g0dam 全量回归；所有离线测试禁用工作区 bytecode/cache。
- `REQ-011` (`required_behavior`): live Validator 必须对 JoeSai 固定 Commit 全量处理 50 case/50 images、运行两次、执行 extraction failure/concurrency 检查，并与 audit 指标和 aggregate `ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293` 完全一致。
- `REQ-012` (`required_behavior`): 同一 live Validator 必须新鲜提取 g0dam 100-case legacy package，并将两包导入同一隔离 PostgreSQL/S3；逐 run、逐来源和全局关系计数、全部对象下载 hash、重放幂等、registry snapshot 与 rights fail-closed 全部闭合。
- `REQ-013` (`required_behavior`): runtime、venv、uv cache、Git mirror/worktree、packages、Compose env/log 和临时文件只写入 `C:/Users/admin/.codex/runtime/image2/TASK-0006`；正式生命周期只写入统一 task-state root。
- `INV-001`: TASK-0002 Adapter Output/Generation Example Schema 与语义不变；JoeSai 输出必须通过现有 Validator，不得为适配来源放宽合同。
- `INV-002`: g0dam published package 的稳定文件、schema 名、指标和身份算法保持向后兼容。
- `INV-003`: manifest 是发现与配对权威源；Markdown 文件名相似、目录顺序或图片数组位置不得代替同一 manifest row 的显式绑定。
- `INV-004`: 50 个 manifest row、50 个 case Markdown、50 个登记 image 必须一一对应；`prompts/README.md` 是唯一允许的非 case Markdown，任何漂移阻断本版本 Adapter。
- `INV-005`: 英文 Prompt 交付文本与 fenced block 语义一致；不得返回中文翻译、标题、Best For 或 Why It Works 作为主 Prompt。
- `INV-006`: pairing evidence 至少闭合 manifest row、英文 Markdown block 和 manifest image path；每个 Generation Example 恰有一个 output_primary，不能跨 slug 配对。
- `INV-007`: JoeSai live 指标固定为 50 observed/exact/paired/valid/unique、0 broken、pair_rate=1.0 和指定 aggregate；g0dam 保持 100-case 指标及 aggregate `ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0`。
- `INV-008`: 两来源 project/revision/run、case、prompt、asset source、generation、pairing 和 rights 关系按真实外键域隔离；相同内容 hash 可以共享一个 asset object，但不得共享错误来源关系。
- `INV-009`: inventory ready 只表示私有 Source/Evidence 库存完成；registry snapshot 中 review_required/auto_publish=false 和 rights records unknown 不得被改写。
- `INV-010`: 失败、并发或重放不得留下部分 published package、重复 ready run、增长的自然键行或未清理的 validator-owned Docker 资源。
- `material_ambiguities`:
  - 固定 Commit 的 50 页中 28 页有 `Why It Works`、22 页没有；它是可选来源元数据，不影响 Prompt/asset 强配对。
  - manifest 的 `example_image` 文件名并不总与 slug 相同，因此必须使用字段值，不能推导图片名。
  - g0dam 历史 schema 名不适合新来源，但改变旧输出会破坏已验证幂等身份；本任务采用“旧来源保留 legacy 名，新来源使用中性名”的兼容边界。
- `decisions_and_authority`:
  - Adapter dispatch 只登记本任务已实现的两个静态 parser；第三来源另建任务扩展同一映射。
  - JoeSai package 仍使用 TASK-0003 的稳定文件布局与 TASK-0004/0005 的现有 importer，不新增第二套消费者。
  - live 双来源共存是本任务的最终消费者证据；单独 parser 单测或 50-case extraction 不能替代库存 assembly。

# 4. 业务场景与规则

- `SCN-001` 首次 JoeSai 提取: 固定 Commit 可达，50 个 manifest row、Markdown 与图片完整；发布 50-case 中性 schema package。
- `SCN-002` 幂等提取: 同输入在独立输出根运行两次产生相同稳定 manifest/files/digest；同键同输出重跑为 verified_existing。
- `SCN-003` manifest 文件名例外: `example_image` 与 slug 不同；系统仍读取 manifest 指定图片并得到 audit hash。
- `SCN-004` Markdown 漂移: 标题、heading、fence、语言块、顺序、额外页或重复 slug 任一不满足；Adapter 返回稳定错误且不发布 package。
- `SCN-005` 路径/资产失败: category、slug、Markdown 或 image path 逃逸，图片缺失/额外/HTML/坏 magic/过小；整个 run fail closed。
- `SCN-006` 双来源同库: 先后导入 g0dam 与 JoeSai，两个 ready run 可独立 inspect，全局计数等于两个 plan 的并集/总和。
- `SCN-007` 双来源重放: 两包再次导入均 verified_existing；DB 全局快照和 S3 object union 不增长。
- `SCN-008` extraction 故障与并发: JoeSai 在既有故障点失败不改写上一 package；同键并发只有一个 writer。
- `SCN-009` 网络/环境失败: Git clone/fetch、Docker、PostgreSQL 或 S3 不可用；本次 Validator 失败或 validation pending，不复用旧 receipt。
- `RULE-001`: registry 只提供来源身份与已审计配置，不允许 CLI 覆盖 Commit、strategy、structure、rights 或 publication。
- `RULE-002`: dispatch 为代码内固定映射，key 是 adapter_strategy；parser 不由来源仓库提供，也不执行动态代码。
- `RULE-003`: JoeSai manifest exact field set 为 `slug/category/title/title_zh/use_case/asset_type/languages/featured/example_image`；类型和安全字符不符即拒绝。
- `RULE-004`: case Markdown 集合必须等于 manifest 推导集合加 allowlisted `prompts/README.md`；example image 集合必须等于 manifest 登记集合。
- `RULE-005`: Markdown parser 按结构解析，不使用“第一个 fence”或模糊正则猜测；两语言 fence 均必须为 `text` 且内容非空，英文非空白字符不少于 80。
- `RULE-006`: manifest row 定位、Markdown Prompt 定位和 image 定位均进入 source locations/pairing evidence；extensions 不能替代合同主字段。
- `RULE-007`: 输出排序、文件名、hash、semantic digest 与 idempotency 不含运行时间、路径、请求顺序或 DB surrogate key。
- `RULE-008`: package verifier 明确检查支持的 package schema；metrics 重建必须得到与源对应的 legacy/neutral schema。
- `RULE-009`: live inventory 期望由两个已验证 ImportPlan 推导 source_files 与 asset hash union；case/prompt/generation 等一对一关系固定总数 150。
- `RULE-010`: 每个来源的 inspect summary 必须只统计自己的 run；global counts 不得掩盖跨来源错绑。
- `RULE-011`: 全部 union objects 必须从 S3 下载并重算 SHA-256；不能只信 HEAD、数据库或 package metadata。
- `RULE-012`: live Validator 复用 TASK-0005 私有 bucket、ACL、事务和约束实现，但只管理本次随机 Compose project/containers/volumes。
- `RULE-013`: 无 publication/API/web 字段或操作；任何公开策略、rights 提升或 auto_publish=true 都是失败。
- `STATE-001` extraction: `registry_validated → snapshot_ready → adapter_valid → assets_resolved → generation_valid → candidate_verified → published`；失败不得产生部分正式包。
- `STATE-002` inventory: `package_verified → source_verified → lock_acquired → assets_verified → objects_ready → inventory_ready|verified_existing`。
- `FLOW-001`: `sources-v1 → fixed Git snapshot → strategy dispatch → JoeSai manifest/Markdown Adapter → asset resolution → Generation Examples → published package → existing inventory importer → same private DB/S3 as g0dam`。
- `risk_sensitive_invariants`:
  - 这是第一次真实多来源 producer/consumer assembly；错误 dispatch、schema 兼容或 source-domain 关系会污染长期库存。
  - Markdown 的可读相似性不能代替确定性结构与 manifest 绑定，否则持续更新时会静默错配。
  - legacy g0dam identity 已被 TASK-0003/0005 消费，不能为“泛化命名”重写历史输出。
  - publication 与 repository license 仍是独立边界，私有库存通过不产生公开授权。
- `inapplicable_faces_with_reason`:
  - 数据库 migration/schema 修改：TASK-0005 已完成，本任务只证明第二来源消费。
  - 分类/去重/Canonical：尚未进入内容决策层。
  - API/UI/权限：后续单独任务实现，避免把来源接入与公开消费边界混合。
  - 后台调度/Commit 更新同步：本任务只验证当前固定 Commit；三 pilot 完成后再实现同步编排。

### Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| `DEP-001` | sources-v1 / source-audit-v1 | JoeSai/g0dam fixed input 与指标 | execution prerequisite | TASK-0001 | confirmed | 不表示 Adapter 已实现 | Commit、策略、50/100 case |
| `DEP-002` | TASK-0002 contract | JoeSai Adapter/GE 输出 | public contract | schemas + validator + fixture | confirmed | 不表示 inventory/publication 完成 | 字段、引用、配对、rights |
| `DEP-003` | TASK-0003 pipeline/package | TASK-0006 multi-source producer | compatibility dependency | existing ingestion code/docs/tests | confirmed | 不授权改变 g0dam 稳定输出 | dispatch、package、metrics |
| `DEP-004` | TASK-0005 inventory | 双来源 assembly | producer-to-consumer | inventory package/importer/DB/S3 | confirmed | 不表示公开发布 | multi-project persistence |
| `PERM-001` | extraction/inventory | publication | decision prohibition | 1.md + registry | confirmed | 不得公开 Prompt/原图 | rights、visibility、API |

# 5. 当前证据与目标差异

- `FACT-001`: `ingestion/pipeline.py` 当前直接 import/call `parse_g0dam_snapshot`，并只捕获 `G0damAdapterError`。
- `FACT-002`: `ingestion/registry.py` 当前显式拒绝所有非 `g0dam-work-prompts` 来源。
- `FACT-003`: `ingestion/contracts.py` 从 g0dam 模块导入 prompt hash，且 package/metrics schema 名写死为 g0dam；现有 g0dam fixtures/tests依赖该输出。
- `FACT-004`: JoeSai registry 记录固定 Commit `6f9b...a9b`、strategy `joesai_manifest_markdown_v1`、structure `markdown_prompt_pages_with_manifest`、active canonical pilot/full ingestion/auto_publish=false。
- `FACT-005`: 固定 Commit `data/prompts.json` 是 50 项数组，50 个唯一 slug，所有记录拥有同一 9 字段形状，覆盖 13 个 category。
- `FACT-006`: manifest 精确映射 50 个 `prompts/{category}/{slug}.md` 和 50 个 `assets/examples/*.png`；`prompts/README.md` 是唯一额外 Markdown，example image 无额外/缺失文件。
- `FACT-007`: 50 个 case 页均按 H1/Best For/Prompt EN/中文 Prompt 排列；28 页另有 Why It Works、22 页没有；英文 Prompt 703–1175 字符，中文 Prompt 237–397 字符。
- `FACT-008`: TASK-0002 JoeSai fixture 已确认 source_case_key、Markdown Prompt source location、manifest image location、`explicit_markdown_block + strong`、unknown source claim/rights 的合法映射。
- `FACT-009`: TASK-0005 inventory consumer 依据 manifest/source/adapter/Generation Example 通用合同建 plan，并在 source_project/revision/run 域内持久化；尚无第二真实来源同库存证据。
- `ASM-001`: GitHub/Docker/本地主机资源在正式 live 时可用；如果不可用，只能形成真实环境失败。
- `current_execution_path`: 只有 g0dam 能通过 CLI 进入 package 和 inventory；JoeSai 只能作为手工 TASK-0002 fixture 被合同验证。
- `target_delta`: 把 g0dam 单来源硬编码收敛为两个显式静态 Adapter 的通用路径，并用真实双来源 DB/S3 assembly 证明消费者闭环。
- `evidence_gaps`:
  - 无 JoeSai parser、fixtures、负例或 50-case live package。
  - 无 g0dam legacy schema 与 JoeSai neutral schema 同时受支持的回归证据。
  - 无两个真实来源在同一 inventory 中的 count/hash/idempotency/rights 隔离证据。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `D:/image2/ingestion/adapters/base.py`
  - `D:/image2/ingestion/adapters/__init__.py`
  - `D:/image2/ingestion/adapters/g0dam.py`
  - `D:/image2/ingestion/adapters/joesai.py`
  - `D:/image2/ingestion/registry.py`
  - `D:/image2/ingestion/pipeline.py`
  - `D:/image2/ingestion/contracts.py`
  - `D:/image2/tests/ingestion/**`
  - `D:/image2/tests/inventory/test_package.py`
  - `D:/image2/fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/**`
  - `D:/image2/scripts/validate_joesai_multi_source.py`
  - `D:/image2/docs/ingestion/joesai-extraction-v1.md`
  - `D:/image2/docs/ingestion/g0dam-extraction-v1.md`，仅限兼容/dispatch说明
  - `D:/image2/docs/inventory/internal-inventory-v1.md`，仅限双来源已验证说明
  - `C:/Users/admin/.codex/runtime/image2/TASK-0006/**`
  - `C:/Users/admin/.codex/task-state/image2/**`，仅限正式生命周期产生的 TASK-0006 canonical run
- `hard_protected_scope`:
  - `D:/image2/1.md`
  - `D:/image2/config/sources-v1.yaml`
  - `D:/image2/reports/source-audit-v1.json`
  - `D:/image2/schemas/**`
  - `D:/image2/docs/contracts/**`
  - `D:/image2/fixtures/contracts/**`
  - `D:/image2/fixtures/adapters/g0dam-work-prompts/**`
  - `D:/image2/inventory/**`
  - `D:/image2/migrations/**`
  - `D:/image2/compose.yaml` 与 `D:/image2/.env.example`
  - `D:/image2/scripts/validate_g0dam_extraction.py` 与 `D:/image2/scripts/validate_internal_inventory.py`
  - `D:/image2/tasks/TASK-0001-*.md` 至 `D:/image2/tasks/TASK-0005-*.md`
  - `D:/image2/.task-runs/**` 与 `D:/image2/.work/**`
- `protected_contracts_and_invariants`: TASK-0002 schema/semantics；g0dam stable output；TASK-0005 inventory schema/security/transaction；registry/audit fixed facts；publication fail-closed。
- `authorization_limits`: 本卡不构成修改来源事实、公开发布、外部写入或 Git commit 的额外授权；当前工作区不是 Git repository。
- `stop_if_scope_expands`:
  - JoeSai 真实结构与权威审计不一致，或必须修改 TASK-0002 Schema/语义才能接入。
  - 必须修改 inventory schema/migration、安全策略或事务语义才能支持第二来源。
  - 需要动态插件、第三 Adapter、URL fetcher、图片派生、分类/去重/publication/API/web。
  - 无法保持 g0dam legacy package 稳定兼容。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: `python -m ingestion extract --source-id <source>` → published package → `inventory.importer.import_package` → PostgreSQL/S3 → per-run inspect。
- `expected_touchpoints_or_search_anchors`:
  - Adapter shared boundary: `ParsedCase`、prompt normalization/hash、`AdapterError`。
  - Static dispatch: `adapter_strategy` → `parse_g0dam_snapshot|parse_joesai_snapshot`。
  - Registry support matrix: two strategy/structure pairs only。
  - JoeSai parser: manifest discovery、strict Markdown section parser、extensions、pairing locations。
  - Compatibility: source/adapter-aware package and metrics schema selection plus verifier allowlist。
  - Tests/docs/live assembly as listed in allowed scope。
- `wiring_to_final_consumer`:
  - JoeSai parser returns the same `ParsedCase` boundary consumed by existing asset resolution/contracts/publisher。
  - published package remains the same file layout consumed by existing `build_import_plan`；no inventory code changes。
  - live validator imports both real packages into one isolated DB/S3 and reads per-run/global evidence。
- `failure_and_recovery`:
  - Unsupported source shape fails before Git side effects；Markdown/manifest drift fails before package publish。
  - existing pipeline candidate cleanup/local lock semantics remain shared；JoeSai must pass the same failure/concurrency matrix。
  - inventory errors retain TASK-0005 transaction/object semantics；this task proves idempotent reimport and cleanup without changing ownership。
- `implementation_freedom`: 满足目标、合同、边界和验收时，局部 parser helper、测试拆分与文档组织由执行者选择；不得改变 confirmed file/responsibility boundary。
- `selected_profile_obligations`:
  - public-contract: legacy/neutral schema compatibility and TASK-0002 output closure must be explicit and tested。
  - external-boundary: Git, Markdown paths, image bytes, Docker/S3/DB and cleanup fail closed。
  - configuration: registry facts authoritative，no CLI identity override。
  - stateful-runtime: package atomicity、inventory idempotency、same-key locking and resource cleanup observable。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `REQ-001` 至 `REQ-003`, `INV-001`, `INV-002`
- `owns_behavior`: 中立 Adapter boundary、支持矩阵、静态 dispatch 与 legacy schema 兼容。
- `target_delta`: pipeline 不再知道 g0dam parser，registry 只接受已实现策略，g0dam 输出不变。
- `integration_edges`: registry → dispatch → parser → contracts/publisher。
- `expected_touchpoints`: `ingestion/adapters/base.py`、`__init__.py`、`g0dam.py`、`registry.py`、`pipeline.py`、`contracts.py`。
- `linked_tests`: `TEST-001`, `TEST-003`
- `stop_conditions`: 泛化需要动态加载或改变 g0dam stable output。

### TASK-002

- `links`: `REQ-004` 至 `REQ-008`, `INV-003` 至 `INV-006`
- `owns_behavior`: JoeSai manifest + strict Markdown Adapter、source locations、metadata extensions 与强配对。
- `target_delta`: 50 个真实结构案例可确定性映射到 TASK-0002 合同。
- `integration_edges`: manifest → Markdown EN prompt → manifest image → ParsedCase。
- `expected_touchpoints`: `ingestion/adapters/joesai.py`、JoeSai fixtures/tests/docs。
- `linked_tests`: `TEST-001`, `TEST-002`
- `stop_conditions`: 固定 Commit 结构无法无歧义解析或 audit aggregate 不可复现。

### TASK-003

- `links`: `REQ-009` 至 `REQ-013`, `INV-007` 至 `INV-010`
- `owns_behavior`: 两来源 full extraction、同库存 assembly、idempotent reimport、object hash 与 cleanup evidence。
- `target_delta`: 从单来源实现提升为经真实第二来源证明的 producer/consumer 闭环。
- `integration_edges`: g0dam/JoeSai packages → existing importer → same PostgreSQL/S3 → per-run/global inspect。
- `expected_touchpoints`: `scripts/validate_joesai_multi_source.py`、docs、相关 tests。
- `linked_tests`: `TEST-003`, `TEST-004`
- `stop_conditions`: 只能用 mock/历史 receipt，或必须修改 protected inventory boundary。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`
- `end_to_end_entry`: 新 live Validator 的 g0dam + JoeSai 双提取和双导入流程。
- `shared_contract_state_data`: source/Commit/adapter/schema、source_case_key、Prompt/asset hash、pairing evidence、package idempotency、registry snapshot、DB natural keys、S3 content address。
- `final_consumer`: 后续 ConardLi 第三 pilot、Canonical/rights/publication/API slices。
- `cross_task_failure_path`: 任一 dispatch/parser/package/import/object/DB Gate 失败时不产生第二个错误 ready run，既有 g0dam/JoeSai 成功状态保持可验证。
- `linked_test_evidence_gate`: `TEST-003`, `TEST-004` / `EV-003`, `EV-004` / `GATE-003`, `GATE-004`

# 9. 验证与验收

- `consumer_chain_validation`: 必须证明真实 JoeSai static source → contract-valid package → existing generic inventory，并与真实 g0dam package 同库共存；只验证 parser 或 package Schema 不足以完成。
- `real_integration_evidence`: live 使用公开固定 Commit、完整 50+100 case/image、真实 PostgreSQL/S3 containers 和全部 union object 下载 hash。
- `failure_recovery_ownership_validation`: Adapter owns source parsing；pipeline owns atomic package/lock；existing importer owns snapshot/object/DB ordering；无新增并列 owner。

### RISK-001

- `links`: `REQ-002` 至 `REQ-005`, `TEST-001`, `TEST-002`
- `description`: 模糊 dispatch 或 Markdown 猜测解析使未实现来源被接受、Prompt 错块或 manifest 图片错配。
- `mitigation`: fixed support matrix、exact headings/fences/file sets、manifest row binding、负例零发布。

### RISK-002

- `links`: `REQ-001`, `REQ-009`, `INV-002`, `TEST-001`, `TEST-003`
- `description`: 泛化过程中改变 g0dam prompt hash、metrics/package schema 或 stable JSON，破坏历史幂等和库存 consumer。
- `mitigation`: shared helper behavior equivalence、legacy conditional schema、fixture + full live g0dam regression。

### RISK-003

- `links`: `REQ-006` 至 `REQ-008`, `INV-005`, `INV-006`, `TEST-002`
- `description`: Markdown normalization 改写原 Prompt，或把中文/README/license/model_scope 错当主 Prompt、模型验证或发布授权。
- `mitigation`: exact EN block projection、source-specific extensions、unknown claim/rights、contract fixture equivalence。

### RISK-004

- `links`: `REQ-012`, `INV-008`, `TEST-004`
- `description`: 两来源在同库存发生 source-domain 错绑、generation ID 冲突或对象计数被错误去重。
- `mitigation`: per-run inspect + global plan-derived counts、source/revision keys、asset hash union、全部 objects 下载复核。

### RISK-005

- `links`: `REQ-011` 至 `REQ-013`, `INV-010`, `TEST-003`, `TEST-004`
- `description`: live 环境失败、并发或清理缺失被历史 evidence 掩盖，或删除用户 Docker 资源。
- `mitigation`: environment-sensitive fresh run、random Compose project、owned-resource labels、bounded cleanup、失败不复用旧 pass。

### TEST-001

- `links`: `TASK-001`, `REQ-001` 至 `REQ-003`, `REQ-009`, `RISK-001`, `RISK-002`
- `method`: 离线验证 shared prompt hash 与原 g0dam 等价；registry 接受两个支持策略并拒绝 unsupported/mismatched structure；dispatch 精确选择 parser；g0dam fixtures 的 adapter output、GE、metrics 和 legacy package schema 逐字稳定。
- `expected_observable_result`: 两来源配置可解析，未实现 ConardLi 在 snapshot 前拒绝，g0dam expected JSON/hash 无变化，JoeSai package 使用 neutral schema。
- `failure_path_covered`: strategy spoof、structure mismatch、wrong parser、legacy identity drift。
- `cannot_prove`: 不证明真实 Git、图片、DB/S3。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: pytest case list、supported mapping、stable g0dam expected file/hash comparison、JoeSai schema assertions、error codes。

### TEST-002

- `links`: `TASK-002`, `REQ-004` 至 `REQ-008`, `INV-003` 至 `INV-006`, `RISK-001`, `RISK-003`
- `method`: 使用真实形状最小 fixture 检查 manifest/Markdown/image 一一映射、Prompt exact text、extensions 和 TASK-0002 contract；参数化破坏 duplicate slug、字段类型、路径、title、heading/fence/order、missing/extra page/image。
- `expected_observable_result`: 正例稳定生成预期 ParsedCase/Adapter Output/GE；所有歧义与漂移返回稳定 Adapter/asset错误且无 published package。
- `failure_path_covered`: case discovery 漂移、错 Prompt、错图片、路径逃逸、静默忽略额外内容。
- `cannot_prove`: fixture 不证明完整 50-case fixed Commit。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: fixture manifest/Markdown清单、expected output hashes、每类负例 error_code、contract validation results。

### TEST-003

- `links`: `TASK-001`, `TASK-002`, `REQ-011`, `INV-007`, `RISK-002`, `RISK-005`
- `method`: live 从两个 registry fixed Commit 各运行两次完整 extraction；JoeSai 执行五个共享 failure points 与同键 concurrency；逐包验证 stable files/manifest/schema/metrics/aggregate、50/100 records/images/GE 和无图片字节输出。
- `expected_observable_result`: JoeSai 两次 50-case 输出完全一致、audit aggregate 精确；g0dam 两次 legacy 输出与 100-case aggregate 精确；故障不改前包、并发 single writer、临时 worktree/candidate/locks 清理。
- `failure_path_covered`: Git/shape/asset/publish故障、legacy regression、same-key writer race。
- `cannot_prove`: 不单独证明 inventory consumer。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: 两来源 Commit、package/metrics schema、两次 semantic/manifest/file hashes、50/100 counts与aggregate、failure code matrix、concurrency result、Git/runtime cleanup。

### TEST-004

- `links`: `ASSEMBLY-001`, `TASK-003`, `REQ-012`, `INV-008` 至 `INV-010`, `RISK-004`, `RISK-005`
- `method`: 同一隔离 Compose 环境应用 migrations两次，依次导入两个 live packages；对每个 idempotency key inspect；查询全局 source/project/revision/run/case/prompt/asset-source/generation/pairing/rights counts；按两个 ImportPlan 计算 source-file 总和和 content-hash union，下载复核全部 union objects；重导两包并比较前后 DB/S3 snapshot；检查 registry snapshots、unknown rights、auto_publish=false、无 publication 状态；最后清理 owned resources。
- `expected_observable_result`: 2 projects/revisions/runs；每来源 100/50 case闭合，总计150 case/version/prompt/GE/output/pairing/rights；source_files与plan总和一致，assets/objects与hash union一致；两包重放均 verified_existing且全局快照不变；资源完全清理。
- `failure_path_covered`: cross-source collision/contamination、false dedupe、partial second import、idempotent growth、rights/publication elevation、container/volume leak。
- `cannot_prove`: 不证明生产 PostgreSQL/S3、未来 Commit、第三来源或公开服务。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: Docker image digests/loopback ports（无秘密）、migration receipts、per-run inspect、global DB counts、plan-derived union、全部 object keys/download hashes、reimport statuses与前后 snapshot、rights/registry assertions、cleanup结果。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "joesai-multi-source-offline",
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
        "tests/ingestion",
        "tests/inventory/test_package.py",
        "-q"
      ],
      "cwd": ".",
      "timeout_seconds": 300,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "reports/source-audit-v1.json",
        "schemas/adapter-output-v1.schema.json",
        "schemas/generation-example-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "inventory/package.py",
        "tests/ingestion",
        "tests/inventory/test_package.py",
        "fixtures/adapters/g0dam-work-prompts",
        "fixtures/adapters/joesai-commercial-prompts",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/inventory/internal-inventory-v1.md"
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
      "validator_id": "joesai-multi-source-compose-live",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "scripts/validate_joesai_multi_source.py",
        "--registry",
        "config/sources-v1.yaml",
        "--audit",
        "reports/source-audit-v1.json",
        "--g0dam-source-id",
        "g0dam-work-prompts",
        "--g0dam-expected-commit",
        "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "--g0dam-expected-cases",
        "100",
        "--g0dam-expected-aggregate",
        "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0",
        "--joesai-source-id",
        "joesai-commercial-prompts",
        "--joesai-expected-commit",
        "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b",
        "--joesai-expected-cases",
        "50",
        "--joesai-expected-aggregate",
        "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293",
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
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "inventory",
        "migrations",
        "compose.yaml",
        "scripts/validate_joesai_multi_source.py",
        "fixtures/adapters/g0dam-work-prompts",
        "fixtures/adapters/joesai-commercial-prompts",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/inventory/internal-inventory-v1.md"
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
| `GATE-001` | shared boundary 与 legacy兼容 | `TASK-001` / `TEST-001` | 两策略正确分发，unsupported拒绝，g0dam稳定输出不变 | `EV-001` | 不证明真实来源 |
| `GATE-002` | JoeSai严格映射 | `TASK-002` / `TEST-002` | manifest/Markdown/image一一闭合，全部漂移负例fail closed | `EV-002` | 不证明50-case live |
| `GATE-003` | 两来源完整提取 | `TASK-001` / `TASK-002` / `TEST-003` | 50/100 case真实固定Commit、确定性、aggregate、故障与并发通过 | `EV-003` | 不证明库存 |
| `GATE-004` | 双来源同库 assembly | `TASK-003` / `ASSEMBLY-001` / `TEST-004` | 两run/150关系/hash union/重放/rights/cleanup全部闭合 | `EV-004` | 不证明公开服务或第三来源 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `ingestion/adapters/base.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/adapters/g0dam.py`
  - `ingestion/adapters/joesai.py`
  - `ingestion/registry.py`
  - `ingestion/pipeline.py`
  - `ingestion/contracts.py`
  - `tests/ingestion/test_joesai_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `tests/ingestion/test_g0dam_adapter.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `tests/inventory/test_package.py`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-adapter-output.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-generation-examples.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-metrics.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/data/prompts.sample.json`
  - `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/**`
  - `scripts/validate_joesai_multi_source.py`
  - `docs/ingestion/joesai-extraction-v1.md`
  - `docs/ingestion/g0dam-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`

### 必交产物

- `ingestion/adapters/base.py`
- `ingestion/adapters/__init__.py`
- `ingestion/adapters/g0dam.py`
- `ingestion/adapters/joesai.py`
- `ingestion/registry.py`
- `ingestion/pipeline.py`
- `ingestion/contracts.py`
- `tests/ingestion/test_joesai_adapter.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `tests/ingestion/test_g0dam_adapter.py`
- `tests/ingestion/test_registry_and_snapshot.py`
- `tests/inventory/test_package.py`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-adapter-output.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-generation-examples.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/expected-metrics.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/data/prompts.sample.json`
- `fixtures/adapters/joesai-commercial-prompts/6f9b01fd21efbc05cfdde1176fc988013d3c4a9b/source-files/prompts/**`
- `scripts/validate_joesai_multi_source.py`
- `docs/ingestion/joesai-extraction-v1.md`
- `docs/ingestion/g0dam-extraction-v1.md`
- `docs/inventory/internal-inventory-v1.md`

### 完成与回写规则

- `documentation_impact`: updated；记录 shared dispatch、JoeSai manifest/Markdown contract、legacy/neutral package schema compatibility、双来源 inventory 验证与仍然 fail-closed 的 rights/publication 边界。
- `repository_hygiene_requirement`:
  - 工作区只保存代码、文本 fixture、测试和文档；不保存真实 50/100 图片、完整上游仓库、packages、DB/S3 volumes、Compose env、credentials 或 logs。
  - `UV_PROJECT_ENVIRONMENT`、`UV_CACHE_DIR`、`TMP`、`TEMP`、Git/runtime/output 固定在 `C:/Users/admin/.codex/runtime/image2/TASK-0006`；`PYTHONDONTWRITEBYTECODE=1`、Python `-B`、pytest no cacheprovider。
  - 不修改 protected `.task-runs`/`.work`；formal evidence 只进入工作区外 canonical run。
  - validator-owned Docker project/containers/networks/volumes 必须清理，不停止或删除用户其他资源。
  - 当前 `D:/image2` 不是 Git repository，因此不要求 commit；Completion Report 必须声明并证明 protected scope 未修改。
- `external_review`: policy=never；reason=本任务要求 L4 独立语义审查和真实双来源 Git/DB/S3 integration，未要求额外外部模型复核。
- `non_completion_rules`:
  - 任一必交产物、两个正式 Validator、L4 独立审查或 Completion Report 缺失时不得完成。
  - JoeSai 不是固定 Commit 全量 50-case，或指标/aggregate 与 audit 不一致时不得完成。
  - g0dam stable fixture/package/metrics/schema/100-case aggregate 发生变化时不得完成。
  - registry 接受 unsupported/mismatched strategy，或 pipeline 仍直接硬编码来源 parser 时不得完成。
  - Markdown parser 允许歧义 heading/fence、静默忽略 extra/missing case/image、推导图片名或改写主 Prompt 时不得完成。
  - source claim/rights/model/license 被提升，或出现 publication/API/web 行为时不得完成。
  - 双来源未进入同一 fresh inventory，或 per-run/global counts、asset hash union、全部 object download hashes、两包 verified_existing 重放任一未闭合时不得完成。
  - 为通过第二来源而修改 inventory schema/migration、安全/事务语义、TASK-0002 contract、registry/audit/history证据时不得完成。
  - live Git/Docker/DB/S3 失败只能报告真实 pending/failed；不得使用 mock 或历史 receipt 替代。
  - 工作区出现 runtime/cache/venv/完整上游/图片/package/credentials/log，或 validator-owned Docker 资源未清理时不得完成。
  - 需要第三 Adapter、同步调度、分类/Canonical/rights review/publication/API/web 时停止并创建后续任务。

执行时将 `CODEX_TASK_STATE_ROOT` 固定为 `C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0006/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0006/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0006/tmp`。唯一 TASK-0006 canonical run 必须记录两来源 package/Commit/schema/metrics、50/100-case extraction、failure/concurrency、双来源 DB/S3 counts与全部 object hashes、幂等重放、rights/publication断言、cleanup、L4独立审查、最终新鲜度与 Completion Report；不得记录 secrets。
