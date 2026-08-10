---
task_contract_version: 3
card_id: "TASK-0003"
title: "打通 g0dam 固定 Commit 到 Generation Example 的真实提取切片"
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
  - 用户目标模式授权：沿已确认方向持续执行，逐张建立并正式执行任务卡，完成 Phase 1 三类 pilot 的纵向验证闭环。
  - `D:/image2/1.md`，重点是第 3、5、6、7、8、9、15、16、18 节。
  - `D:/image2/config/sources-v1.yaml`，作为来源身份、active/pilot 状态、固定 Commit 和 Adapter 策略的权威配置。
  - `D:/image2/reports/source-audit-v1.json` 与 TASK-0001 只读历史证据，作为 g0dam 全量计数、Prompt/image hash 和固定 Commit 审计事实来源。
  - `D:/image2/schemas/adapter-output-v1.schema.json`、`D:/image2/schemas/generation-example-v1.schema.json` 与 `D:/image2/docs/contracts/content-contract-v1.md`，作为 TASK-0002 已冻结的生产者/消费者合同。
  - g0dam 固定 Commit `690c2d6969a65b406b17ba7d41f18695a652c3fe` 的公开 Git 内容；只读取，不执行仓库代码。
- `decision_owner`: 用户拥有来源、合同、不变量、发布边界和风险接受的最终决定权；执行者可在本卡文件布局与职责边界内选择具体 Python 实现、Git 命令细节和测试组织。
- `material_unknowns`:
  - 当前仓库没有应用代码、Python 项目配置或现成运行入口；本任务将建立最小 Python ingestion 包。
  - 本任务不建立数据库和对象存储，因此“提交”只表示一个外部运行目录中的提取包被原子发布，不表示生产库存已经持久化。
  - GitHub、网络或目标仓库在正式 live integration 时可能暂时不可用；该 Validator 标记为 environment-sensitive，失败时不得用旧结果伪装通过。
  - 权利证据仍为 unknown/review_required；本任务只提取并保存事实，不授权公开图片或 Prompt。

# 2. 业务目标

- `actor`: 后续 Source Manager、Adapter、资产处理和内部库存实施者。
- `workflow_and_trigger`: TASK-0002 已冻结内容合同；在引入数据库、对象存储和另外两个来源前，先用最简单的结构化 JSON pilot 打通真实固定 Commit 的完整提取、图片解析、合同投影、确定性和失败恢复。
- `single_outcome`: 提供一个可重复执行的 Python CLI，从 `sources-v1` 读取 `g0dam-work-prompts`，只处理登记的固定 Commit，完整解析 100 个案例、读取并验证 100 张输出图、生成合规 Adapter Output 和 Generation Example 提取包，并以原子方式写入工作区外输出目录。
- `observable_results`:
  - `RESULT-001`: CLI 能从一个安全的外部 data root 建立/更新只读 Git 镜像和临时快照，确认实际 Commit 等于 registry 固定 Commit。
  - `RESULT-002`: g0dam Adapter 对固定 Commit 的 100 个 `prompts[]` 记录生成 100 个 contract-valid Adapter 记录，原始 Prompt、图片路径、分类/标签、来源定位和 source-claimed 模型声明可追溯。
  - `RESULT-003`: 100 张输出图均通过路径边界、存在性、最小格式和 SHA-256 检查，并形成 100 个通过 Generation Example v1 的证据文档；不把图片字节复制到提取包。
  - `RESULT-004`: 两次相同输入运行的稳定文件集合、逐文件哈希、业务指标和 semantic digest 完全一致；运行时间只进入非身份 runtime metadata。
  - `RESULT-005`: 任一获取、解析、资产、Schema 或原子发布失败时，非零退出、记录稳定错误码、清理临时快照，并保持上一版成功输出不变。
- `non_goals`:
  - 不实现 JoeSai 或 ConardLi Adapter，不批量接入其他 active 来源。
  - 不实现 PostgreSQL、数据库迁移、MinIO/S3、队列、调度器、API、网页、搜索、分类、去重或 Publication Layer。
  - 不修改 TASK-0001/0002 交付物、来源名单、固定 Commit、Schema 或合同语义。
  - 不执行 g0dam 仓库中的任何脚本、构建、Hook、submodule、Git LFS 外部进程或包安装。
  - 不把完整上游仓库、100 张图片、镜像或运行输出写入 `D:/image2`。
  - 不根据仓库名或 README 把 source claim 提升为官方模型验证，也不作出公开权利结论。

# 3. 需求质疑与确认

- `user_statement`: 沿固定高价值来源、图片与 Prompt 强绑定的方向持续执行，使用目标模式完成后续阶段。
- `REQ-001` (`required_behavior`): 建立 Python 3.12 项目和 `python -m ingestion extract` CLI，参数至少包括 registry、source_id、外部 data root、外部 output root 和 JSON 输出模式。
- `REQ-002` (`required_behavior`): registry loader 必须验证来源存在、状态为 active、pilot.selected=true、sync.enabled=true、family.role=canonical、ingestion_policy=full，并只使用完整 verified_commit_sha；不接受 HEAD、分支名或调用者覆盖 Commit。
- `REQ-003` (`required_behavior`): Git snapshot 边界必须在工作区外维护 source-specific mirror/cache，并为固定 Commit 创建临时只读快照；禁用仓库 Hook、submodule 和外部过滤器，不执行任何仓库代码。
- `REQ-004` (`required_behavior`): `g0dam` Adapter 必须完整读取固定 Commit 的 `data/prompts.json`，校验顶层 count 与 prompts 长度，按每条原生 id 生成稳定 source_case_key，逐字保存 `prompt.en`，保存 `image_path`、category、tags、license_note、source_reference_ids 和来源定位。
- `REQ-005` (`required_behavior`): 资产解析器必须将 image_path 约束在快照根目录，拒绝绝对路径、路径穿越和逃逸链接；读取图片字节，校验非 HTML、支持的图片 magic、大小大于 512 bytes，并计算 SHA-256。
- `REQ-006` (`required_behavior`): pipeline 必须生成一个 Adapter Output v1 批次和每个案例一个 Generation Example v1 文档，全部通过 TASK-0002 Schema 与语义 Validator；source model_target 只能保存为 `source_claimed`。
- `REQ-007` (`required_behavior`): 输出目录必须包含稳定 manifest、adapter-output、generation-examples 和 metrics；先写临时目录并完整验证，再以同文件系统原子替换/发布，失败时保留上一版。
- `REQ-008` (`required_behavior`): 相同 `source_id + revision_sha + adapter_version + contract_version` 是幂等键；相同输入重跑不得产生不同稳定身份、不同文件排序或重复案例。并发相同键运行必须由本地锁串行化或 fail fast，不能共同写同一输出。
- `REQ-009` (`required_behavior`): 提供最小固定结构 fixture、离线测试和 live fixed-commit Validator；正式 live integration 必须全量处理 100 个案例和 100 张图片，而不是从样本外推。
- `REQ-010` (`required_behavior`): 开发与正式执行必须将 `UV_PROJECT_ENVIRONMENT`、`UV_CACHE_DIR` 和其他依赖缓存指向 `C:/Users/admin/.codex/runtime/image2/TASK-0003` 下的外部目录；Python 使用 `-B`/禁用 bytecode，pytest 禁用 cacheprovider。
- `INV-001`: 原始 `prompt.en` 字节语义必须保留；NFC 和空白规范化只用于哈希或校验，不得改写交付的 raw_text。
- `INV-002`: `source_case_key` 由 `source_id + native id` 稳定生成；Prompt ID 基于原始 Prompt 规范化哈希；Asset ID 基于图片内容 SHA-256；运行时间、临时路径和请求顺序不得进入身份。
- `INV-003`: 每条 Adapter record 恰好绑定自己的 Prompt 和 image_path；不得通过数组位置跨记录配对，也不得把图片集合挂到批次而丢失逐案例关系。
- `INV-004`: 每个合法 Generation Example 至少有一个 output_primary；asset_id、content_sha256、source location 和 pairing evidence 必须闭合。
- `INV-005`: 顶层 `model_target` 可以映射为 `generation_claim.evidence_status=source_claimed` 和逐字 `model_raw`，但不得表述为 official_verified。
- `INV-006`: `license_note`、source_reference_ids 和 registry rights 默认值是证据/配置事实，不得转换为 mirror_allowed、quality_passed 或 auto_publish=true。
- `INV-007`: live run 指标必须与 TASK-0001 固定 Commit 审计相符：100 observed/valid/unique cases、100 exact prompts、100 paired outputs、broken assets=0、pair_rate=1.0，且 case fingerprint aggregate 为 `ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0`。
- `INV-008`: 输出 manifest 必须列出全部稳定文件及 SHA-256；同一输入两次运行的 manifest 稳定部分和 semantic digest 完全相同。
- `INV-009`: 临时镜像、worktree、下载字节、锁和输出不得位于 `D:/image2`；正式运行结束后临时 worktree 必须清理，persistent mirror 只能位于调用者提供的外部 data root。
- `INV-010`: 失败不得产生部分正式输出、不得覆盖上一成功包，也不得把 parse_error/unresolved asset 写入 contract-valid Generation Example。
- `INV-011`: `D:/image2` 内不得出现 `.venv`、`.pytest_cache`、`__pycache__`、uv cache、下载 cache 或构建产物；宿主无法安全清理的缓存必须在创建前通过外部路径配置避免。
- `material_ambiguities`:
  - `data/prompts.json` 同时含 `prompt.en` 和 `prompt.zh`。v1 主记录使用审计时计数的 `prompt.en` 作为 exact original Prompt；`prompt.zh` 与其他来源特有字段可保存在 namespaced extensions，但不能替代主 Prompt。
  - 上游顶层 `model_target` 是来源声明。执行者必须保存原文并标 source_claimed，不能因字符串包含 GPT Image 2 而提升证据等级。
  - 本任务输出是可验证提取包，不是生产数据库。后续持久化任务只能消费该包，不能把本任务描述为库存/发布已完成。
- `decisions_and_authority`:
  - `sources-v1` 中 g0dam 是 active canonical pilot，结构为 `structured_manifest_json`，Adapter 策略为 `g0dam_manifest_json_v1`，固定 Commit 是本任务唯一允许的 live 输入版本。
  - 文件布局采用短链路 `CLI → pipeline → registry/Git snapshot/Adapter/assets/contracts`；数据库、对象存储和发布职责不进入该包。
  - 运行数据与正式执行证据均位于工作区外，保持仓库只含代码、合同、最小 fixtures 和测试。

# 4. 业务场景与规则

- `SCN-001` 首次成功: 外部 data/output root 为空，网络可用。CLI 获取固定 Commit，解析 100 个案例和图片，完整验证后发布第一版输出包。
- `SCN-002` 幂等重跑: mirror 和上一版输出已存在。CLI 复用/fetch mirror、读取相同 Commit，生成相同稳定内容，不重复案例，不改变上一版语义摘要。
- `SCN-003` 上游分支变化: 远端默认分支已经前进，但 registry Commit 未变。CLI 仍只读取固定 Commit；HEAD 变化不改变结果。
- `SCN-004` 内容失败: JSON 缺字段、count 不一致、重复 native id、Prompt 为空、image_path 缺失或合同投影失败。运行非零退出，上一成功包不变。
- `SCN-005` 资产失败: 图片不存在、路径穿越、链接逃逸、HTML 冒充图片、magic 不支持、字节过小或 hash/证据不一致。对应记录不得形成 Generation Example，整个本任务 live Gate 失败且不发布新包。
- `SCN-006` 网络/Git 失败: clone/fetch 超时、Commit 不存在或远端暂时不可用。记录稳定错误和阶段，清理临时资源；不得回退到 HEAD 或把历史收据当成本次通过。
- `SCN-007` 并发相同键: 两个进程同时请求同一 source/Commit/output。只有一个持有锁并可发布；另一个等待有界时间或以明确 `run_locked` 失败，不得发生交叉写入。
- `SCN-008` 发布前故障: 在生成 N 个资产后或原子替换前注入失败。临时目录可清理，上一正式输出目录的文件和 manifest hash 完全不变。
- `RULE-001`: registry 事实优先于 CLI 参数；source_id 以外的来源身份、Commit 和策略不得由调用者覆盖。
- `RULE-002`: mirror 与 worktree 按 source_id 隔离；临时工作区使用不可预测 run id，且解析只在确认 `git rev-parse HEAD == verified_commit_sha` 后开始。
- `RULE-003`: 不初始化 submodule，不运行 hooks，不安装依赖；Git 外部过滤器和 LFS 自动 smudge 必须禁用或 fail closed。
- `RULE-004`: Adapter 只解析静态数据文件，不导入上游 Python/JS，不启动上游应用，不读取网络动态页面作为案例数据。
- `RULE-005`: `input_case_count`、`extracted_candidate_count`、`contract_valid_count`、`quarantined_count` 和 parse_errors 必须守恒；本固定 Commit 期望 100/0/100/0 和零 errors。
- `RULE-006`: Adapter records 按 source_case_key 稳定排序；Generation Example 文件名由安全稳定 key 或其哈希生成，不能包含未净化路径片段。
- `RULE-007`: 图片只在内存或临时快照中读取并计算 hash；正式提取包仅保存 source location、content_sha256、格式/字节数等事实，不保存图片字节。
- `RULE-008`: 输出包至少包含 `manifest.json`、`adapter-output.json`、`generation-examples/*.json`、`metrics.json`；manifest 是发布完成标记，必须最后生成并参与最终校验。
- `RULE-009`: runtime metadata 与稳定内容分离；开始/结束时间、临时目录和重试次数可以记录，但不能改变稳定文件哈希或 semantic digest。
- `RULE-010`: 对同一幂等键，若已存在且 manifest/文件校验通过，可以重建并比较或返回 verified_existing；不得只因目录存在就宣称成功。
- `RULE-011`: live Validator 必须使用临时外部根目录、完整处理固定 Commit、运行至少两次、验证故障注入和清理，并在结束时删除其临时镜像/worktree/output。
- `RULE-012`: 正式 Validator 不改变 `sources-v1`、TASK-0002 合同或历史审计证据；任何指标漂移必须作为 blocker 报告，而不是修改期望值。
- `RULE-013`: 任何 `uv sync/lock/run` 和 pytest/Python 命令在运行前必须确认环境/缓存位于工作区外；正式命令使用 `--no-sync`、Python `-B` 和 pytest `-p no:cacheprovider`，不得边验证边修改依赖环境。
- `STATE-001` pipeline 状态: `registry_validated → mirror_ready → snapshot_ready → adapter_valid → assets_resolved → generation_valid → candidate_verified → published`；任一阶段失败进入 `failed`，不跳过中间 Gate。
- `STATE-002` output 状态: 正式输出只有 `published`；临时目录、缺 manifest 或 manifest/file hash 不一致均视为未提交，消费者不得读取。
- `FLOW-001`: `sources-v1 → safe Git snapshot → g0dam Adapter Output v1 → asset resolution → Generation Example v1 documents → verified manifest → external extraction package`。

### Dependency Relations

| id | source object | target object | relationship type | authority source | confirmation state | cannot imply | affects |
|---|---|---|---|---|---|---|---|
| `DEP-001` | TASK-0001 sources/audit | TASK-0003 live input与期望指标 | execution prerequisite | TASK-0001 交付物 | confirmed | 不表示运行时代码已实现 | source/Commit/100-case metrics |
| `DEP-002` | TASK-0002 schemas/contract | TASK-0003 Adapter/GE 输出 | public contract | TASK-0002 交付物 | confirmed | Schema 通过不表示数据库或发布完成 | 字段、引用、错误与状态 |
| `REL-001` | Git snapshot | g0dam Adapter | trusted data boundary | `1.md` 第 7/8 节 | confirmed | 不授权执行仓库代码 | 读取路径、Commit 和清理 |
| `REL-002` | Extraction package | 后续 persistence task | producer-to-consumer handoff | 目标模式 Phase 1 顺序 | confirmed | 不表示已进入内部库存 | manifest、稳定文件和幂等语义 |
| `PERM-001` | Adapter/extraction pipeline | Publication Layer | decision prohibition | `1.md` 第 3/7/12 节 | confirmed | 不得输出公开批准 | rights/model/quality 字段 |

- `risk_sensitive_invariants`:
  - 稳定 identity/hash 将成为后续持久化、去重和幂等依据；错误算法会形成长期重复或错误覆盖。
  - Git 与文件系统是外部边界；路径逃逸、过滤器、Hook、残留 worktree 和并发写必须 fail closed。
  - 原子发布与上一版保留是后续持续同步的恢复基础，不能用“最终命令成功”替代文件级完整性。
  - live 100-case 结果必须来自固定 Commit 全量运行，不能用 TASK-0002 的单条 fixture 或旧审计收据代替。
- `inapplicable_faces_with_reason`:
  - 数据库事务与迁移：下一任务实现，本任务只发布文件包。
  - 对象存储：下一任务消费资产 hash，本任务不持久保存图片字节。
  - UI/API/用户权限：本任务没有网页或外部服务入口。
  - 后台调度：当前通过显式 CLI 触发，不建立队列和周期任务。

# 5. 当前证据与目标差异

- `FACT-001`: 当前仓库只有设计、来源/内容合同、fixtures 和 Validator，没有 `pyproject.toml`、Python package、Adapter 或提取 CLI。
- `FACT-002`: 主机已验证 Python 3.12.10、Git 2.53、uv 0.11.28 和 Docker 29.2.1 可用；本任务不需要 Docker 服务。
- `FACT-003`: g0dam 固定 Commit 的 `data/prompts.json` 顶层包含 version、model_target、count=100、categories 和 prompts；每个 prompt 至少含 id、title、category、prompt.en/zh、tags、license_note、source_reference_ids 和 image_path。
- `FACT-004`: TASK-0001 已验证该 Commit 的 100 个案例、100 个 exact prompts、100 个 paired outputs、pair_rate=1.0、broken assets=0 和固定 aggregate hash。
- `FACT-005`: TASK-0002 已用真实案例证明 g0dam 可映射为 `explicit_structured_reference + strong`，并冻结 source location、Prompt、asset、source claim、rights evidence 和状态语义。
- `ASM-001`: GitHub 允许在 live Validator 执行期间读取公开固定 Commit；网络失败属于 environment-sensitive 非通过状态。
- `ASM-002`: 最小 fixture 可以保存少量固定 Commit Prompt 数据和来源路径，但不保存真实图片；图片路径/字节边界由临时测试数据和 live integration 共同验证。
- `current_execution_path`: 当前只有一条手工制作的 TASK-0002 g0dam 契约 fixture，没有可从 registry 和真实仓库全量生成该合同的代码。
- `target_delta`: 建立可安装 Python package、safe Git snapshot、g0dam Adapter、资产解析、合同投影、原子输出和正式测试链，使真实 100-case 数据能自动生成一致提取包。
- `evidence_gaps`:
  - 尚无 registry loader、Git snapshot 隔离、Adapter 实现和 CLI。
  - 尚无全量 live 100-case 运行、幂等输出、并发锁和故障注入证据。
  - 尚无后续 persistence task 可直接消费的文件级 manifest。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `D:/image2/pyproject.toml`
  - `D:/image2/uv.lock`
  - `D:/image2/ingestion/**`
  - `D:/image2/tests/ingestion/**`
  - `D:/image2/fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/**`
  - `D:/image2/docs/ingestion/g0dam-extraction-v1.md`
  - `D:/image2/scripts/validate_g0dam_extraction.py`
  - `C:/Users/admin/.codex/runtime/image2/TASK-0003/**` 作为开发期外部 mirror/worktree/output 根目录
  - `C:/Users/admin/.codex/task-state/image2/**`，仅限正式生命周期自动解析的唯一 TASK-0003 canonical run
- `hard_protected_scope`:
  - 不修改 `D:/image2/1.md`、TASK-0001/0002、`config/sources-v1.yaml`、`reports/source-audit-v1.*`、现有四个 Schema、`docs/contracts/content-contract-v1.md`、TASK-0002 fixtures 或现有 Validator。
  - `D:/image2/.task-runs/**` 与 `D:/image2/.work/source-audit/**` 全程只读。
  - 不创建数据库、对象存储、API、web、scheduler、queue、其他来源 Adapter 或生产部署代码。
  - 不把镜像、worktree、图片字节、运行输出、锁、日志、缓存或虚拟环境写入 `D:/image2`。
  - 不修改外部仓库，不创建 Issue/PR/评论，不使用凭据或登录态。
- `protected_contracts_and_invariants`:
  - Adapter Output v1 与 Generation Example v1 字段、状态、引用和禁止决策边界保持不变。
  - sources-v1 的 g0dam source_id、Commit、status、family、rights、ingestion_policy 和 pilot 状态不变。
  - 未知/来源声明不能升级为官方模型、权利或发布事实。
  - 失败必须保留上一版，不能通过删输出后重建掩盖非原子行为。
- `authorization_limits`: 本任务授权对 g0dam 公开仓库执行固定 Commit 的只读 Git 获取和图片字节读取/哈希，并授权在指定工作区外 runtime root 维护镜像、临时快照和提取输出。它不授权处理其他来源、持久化生产库存、保存公开图片副本、启动外部服务或作出发布决定。
- `stop_if_scope_expands`:
  - 需要修改 TASK-0002 Schema/合同或 TASK-0001 计数规则才能通过。
  - 固定 Commit 不再可读取，或实际结构/指标与权威审计发生不可解释冲突。
  - 需要数据库、对象存储、队列、网页或第二个 Adapter 才能完成当前目标。
  - 需要执行上游代码、启用 Git Hook/LFS 外部进程、使用凭据或保存完整图片集到仓库。
  - stable identity、幂等键或原子发布语义需要改变用户已确认的数据不变量。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`:
  - `caller`: 操作者或正式 Validator 调用 `python -m ingestion extract`。
  - `entry`: registry path、source_id、外部 data root、外部 output root。
  - `execution_path`: registry validation → safe mirror/fixed snapshot → g0dam parse → Adapter Output validation → asset read/hash → Generation Example projection/validation → metrics/manifest → atomic publish。
  - `final_consumer`: 下一阶段 persistence/asset-store task，只读取 manifest 校验通过的提取包。
- `expected_touchpoints_or_search_anchors`:
  - 新 Python package：`D:/image2/ingestion`。
  - 新 tests：`D:/image2/tests/ingestion`。
  - 新固定结构 fixture：`D:/image2/fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe`。
  - 既有只读合同：`schemas/adapter-output-v1.schema.json`、`schemas/generation-example-v1.schema.json`、`docs/contracts/content-contract-v1.md`。
- `wiring_to_final_consumer`:
  - `cli.py` 只解析参数、配置日志/JSON 结果并调用 pipeline。
  - `pipeline.py` 是状态机和失败/原子发布唯一所有者，不自行解析 source-specific 字段。
  - `registry.py` 只读取并验证来源配置。
  - `git_snapshot.py` 独占 Git/network/filesystem snapshot 副作用。
  - `adapters/g0dam.py` 只解析 g0dam 静态结构并产生 Adapter Output 候选。
  - `assets.py` 独占路径安全、图片读取、magic/size/hash。
  - `contracts.py` 独占 TASK-0002 Schema 加载、语义验证、稳定 digest 和 Adapter→GE 映射。
  - 正式 output manifest 是后续任务唯一可消费入口；不允许直接读取临时目录。
- `failure_and_recovery`:
  - registry/Commit 错误在网络前失败。
  - Git/网络失败清理临时 worktree，保留 mirror 和上一输出。
  - Adapter/asset/contract 错误产生稳定阶段/错误码，不写正式 manifest。
  - 原子发布使用同文件系统临时目录；替换失败时旧目录仍可校验读取。
  - 锁通过 finally/进程结束安全释放；陈旧锁不能仅按时间盲目接管，必须确认本地 owner 不存活或使用原子 OS lock。
- `compatibility_and_error_semantics`:
  - CLI 成功退出 0；合同/内容失败、网络环境失败、锁冲突和内部错误使用不同稳定 error code，具体非零值可由执行者确定并写入文档。
  - 不支持的 registry/contract schema version fail closed。
  - 上游新增未知可选字段保存在 namespaced extension 或忽略并记录；删除/改变必需字段 fail closed。
  - 输出 manifest version 独立于 Adapter/contract version，破坏性变更必须新版本。
- `implementation_freedom`: 满足合同和 Gate 时，执行者可以选择 Git mirror/worktree 具体命令、Python 数据结构、锁实现、原子目录替换方式和测试工具；不得新增没有当前消费者的 plugin framework、service/repository 层或通用 utils 包。
- `selected_profile_obligations`:
  - `public-contract`: CLI、提取包 manifest、Adapter Output 和 Generation Example 的版本、错误、字段、消费者和兼容语义必须明确并测试。
  - `external-boundary`: Git/GitHub 操作设置超时/有限重试、固定 Commit、无凭据、无仓库代码执行；网络失败不复用旧 live pass。
  - `configuration`: registry 是 source/Commit/rights 的权威配置；CLI 不覆盖权威字段；data/output、UV project environment、UV cache 和其他运行根必须在工作区外并校验路径。
  - `stateful-runtime`: 明确 pipeline 状态、幂等键、同键锁、临时/正式输出、失败清理和上一版保留；重复与故障注入测试必须覆盖。

### 文件布局决策

```yaml
decision:
  strategy: split
  target_area: "D:/image2/ingestion"
  repo_shape: mixed
  artifact_type: data-pipeline-step
  stack: python
  files:
    - path: "ingestion/cli.py"
      role: "entrypoint"
      responsibility: "CLI 参数、稳定退出/JSON 结果、调用 pipeline"
      reason: "框架入口与业务编排分离"
    - path: "ingestion/pipeline.py"
      role: "pipeline state machine"
      responsibility: "阶段推进、幂等锁、错误传播、候选验证和原子发布"
      reason: "集中维护完整执行/恢复路径"
    - path: "ingestion/registry.py"
      role: "configuration boundary"
      responsibility: "读取并验证 sources-v1 的目标来源合同"
      reason: "registry 语义与 Git/Adapter 变化原因不同"
    - path: "ingestion/git_snapshot.py"
      role: "external source adapter"
      responsibility: "mirror、固定 Commit、只读快照、清理与 Git 安全设置"
      reason: "独立外部副作用和失败恢复"
    - path: "ingestion/contracts.py"
      role: "contract mapper"
      responsibility: "Schema/语义验证、Adapter→Generation Example 投影、稳定摘要"
      reason: "共享公共合同且具有独立测试面"
    - path: "ingestion/assets.py"
      role: "asset boundary"
      responsibility: "路径安全、图片读取、magic/size/hash"
      reason: "文件 IO 与纯合同映射分离"
    - path: "ingestion/adapters/base.py"
      role: "adapter protocol"
      responsibility: "最小 Adapter 输入/输出协议"
      reason: "后续两个已确认 pilot 是真实第二消费者"
    - path: "ingestion/adapters/g0dam.py"
      role: "source adapter"
      responsibility: "g0dam 固定结构解析和来源特有 extensions"
      reason: "来源变化不应影响通用 pipeline"
  keep_inline:
    - "g0dam 私有字段解析、局部类型和小型 mapper 保持在 g0dam.py"
    - "pipeline 私有原子写 helper 保持在 pipeline.py"
  avoid:
    - "service.py / repository.py / utils.py 空壳层"
    - "通用 plugin discovery 或动态 Adapter 加载"
    - "数据库、对象存储和发布抽象"
  why_not_fewer: "Git、资产 IO、source-specific 解析和公共合同具有不同副作用、失败恢复和测试边界，合并会形成不可审查的大文件。"
  why_not_more: "当前只有一个 Adapter 和文件输出消费者；继续拆 identity、errors、models、manifest 等小文件会增加跳转而没有第二真实消费者。"
  risks:
    - "未来 persistence task 可能要求提取 manifest 扩展，但不能反向把数据库职责塞入本任务。"
  confidence: high
```

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `OBJ-001`, `REQ-001`, `REQ-002`, `REQ-003`, `INV-009`, `SCN-001`, `SCN-003`, `SCN-006`, `SCN-007`
- `owns_behavior`: 建立 CLI、registry validation 和 safe fixed-Commit Git snapshot，使 pipeline 只在工作区外、正确来源身份和固定 Commit 上运行。
- `target_delta`: 从没有运行入口和 source snapshot 能力，变为可安全、可重复取得 g0dam 固定数据快照的最小 Python ingestion 基础。
- `business_result`: 后续 Adapter 不需要自己处理来源选择、Commit 漂移、Git 安全或运行目录边界。
- `behavior_faces`:
  - `normal`: 首次 mirror/fetch/快照成功。
  - `boundary`: mirror 已存在、远端 HEAD 前进、相同 Commit 重跑。
  - `failure`: registry 状态错误、Commit 不存在、网络超时、外部 root 在仓库内、Git 过滤器/Hook 安全条件无法满足。
  - `empty`: registry 不含目标来源时在网络前失败。
  - `repeated/concurrent`: mirror 重用稳定；同键锁阻止并发写。
  - `downstream_error`: snapshot 只有在 HEAD 精确匹配固定 Commit 时才能交给 Adapter。
- `state_change`: 无 mirror → mirror_ready；无 snapshot → snapshot_ready；失败不产生 Adapter 调用并清理临时 snapshot。
- `data_flow`: registry/source_id → verified source config → external mirror → detached fixed snapshot → TASK-002。
- `integration_edges`: CLI → pipeline → registry/git_snapshot → Adapter。
- `expected_touchpoints`: `pyproject.toml`、`uv.lock`、`ingestion/__main__.py`、`ingestion/cli.py`、`ingestion/pipeline.py`、`ingestion/registry.py`、`ingestion/git_snapshot.py`
- `scope_boundary`: 不解析业务记录、不保存图片、不创建数据库。
- `allowed_write_scope`: 第 6 节对应 package/config/test/doc/runtime 路径。
- `acceptance_scenarios`: registry 正常/错误、固定 Commit、HEAD 漂移、网络失败、根目录保护、锁冲突和临时清理。
- `linked_tests`: `TEST-001`, `TEST-004`
- `stop_conditions`: 需要修改 registry/Commit 或执行仓库代码。

### TASK-002

- `links`: `OBJ-001`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-009`, `INV-001`, `INV-002`, `INV-003`, `INV-004`, `INV-005`, `INV-006`, `INV-007`
- `owns_behavior`: 全量解析 g0dam 结构、验证/哈希图片、投影并验证 Adapter Output 与 100 个 Generation Example。
- `target_delta`: 将单条手工合同 fixture 转为从真实固定 Commit 自动生成的完整 100-case 合同输出。
- `business_result`: 后续持久化可以消费真实、完整、逐案例强绑定且来源可追溯的提取包，而不是继续依赖人工 fixture。
- `behavior_faces`:
  - `normal`: 100 个合法 records/images/GE。
  - `boundary`: mixed-language Prompt、source-specific extensions、source_claimed model、不同 category/tag。
  - `failure`: count/重复 id/空 Prompt/路径逃逸/图片无效/Schema 或语义失败。
  - `empty`: prompts 为空或零合法案例时不得成功。
  - `repeated`: 记录排序、identity、hash 和 aggregate 稳定。
  - `downstream_error`: 任一 invalid/unresolved 记录阻止最终 manifest 发布。
- `state_change`: snapshot_ready → adapter_valid → assets_resolved → generation_valid；失败保留诊断并不进入 published。
- `data_flow`: fixed source file/image bytes → Adapter Output → resolved asset facts → GE documents/metrics。
- `integration_edges`: g0dam Adapter → assets/contracts → pipeline candidate directory。
- `expected_touchpoints`: `ingestion/contracts.py`、`ingestion/assets.py`、`ingestion/adapters/base.py`、`ingestion/adapters/g0dam.py`、fixtures 与 tests。
- `scope_boundary`: 不保存图片字节、不分类/去重/发布、不处理其他来源。
- `allowed_write_scope`: 第 6 节对应 package/fixture/test/doc/runtime 路径。
- `acceptance_scenarios`: 离线结构 fixture、图片安全负例、live 100-case 全量与 aggregate 对比。
- `linked_tests`: `TEST-002`, `TEST-003`
- `stop_conditions`: 真实结构与 TASK-0001/TASK-0002 合同不可兼容。

### TASK-003

- `links`: `OBJ-001`, `REQ-007`, `REQ-008`, `INV-008`, `INV-010`, `SCN-002`, `SCN-007`, `SCN-008`
- `owns_behavior`: 建立稳定提取包 manifest、幂等重跑、同键锁、故障注入和上一版保留。
- `target_delta`: 从一次性内存结果变为后续消费者可校验、可重复、失败不破坏的外部文件包。
- `business_result`: 后续 persistence task 可以只读取一个完整 manifest，并可安全忽略临时/失败运行。
- `behavior_faces`:
  - `normal`: 首次原子发布完整包。
  - `boundary`: 相同输入重跑、verified_existing、稳定 metadata 分离。
  - `failure`: 中途异常、manifest/hash 不一致、replace 失败、锁冲突。
  - `empty`: 缺 manifest 的目录不可消费。
  - `repeated/concurrent`: 相同键不重复、并发无交叉写。
  - `downstream_error`: 消费者校验失败时拒绝读取，不尝试修复。
- `state_change`: candidate_verified → published；失败保持 old published + failed diagnostics。
- `data_flow`: validated in-memory docs → temp output → manifest/hash verify → atomic publish → final consumer。
- `integration_edges`: pipeline → filesystem manifest → future persistence task。
- `expected_touchpoints`: `ingestion/pipeline.py`、`ingestion/cli.py`、`tests/ingestion/test_extraction_pipeline.py`、`docs/ingestion/g0dam-extraction-v1.md`。
- `scope_boundary`: 只实现文件包原子性，不实现数据库事务或对象存储。
- `allowed_write_scope`: 第 6 节对应 package/test/doc/runtime 路径。
- `acceptance_scenarios`: 首次/重跑/并发/故障注入/旧版保留/临时清理。
- `linked_tests`: `TEST-004`
- `stop_conditions`: 需要引入数据库或跨机器锁才能满足当前文件输出目标。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`
- `end_to_end_entry`: `python -m ingestion extract --source-id g0dam-work-prompts ...`
- `shared_contract_state_data`: registry source/Commit、pipeline state、adapter_version、contract_version、stable ids、asset hashes、metrics、manifest 和 idempotency key。
- `final_consumer`: 下一阶段 persistence + content-addressed asset-store task。
- `cross_task_failure_path`: snapshot、Adapter、asset、contract 或 publish 任一失败均不得产生新的正式 manifest；旧包保持可校验。
- `linked_test_evidence_gate`: `TEST-003`, `TEST-004` / `EV-003`, `EV-004` / `GATE-003`, `GATE-004`

# 9. 验证与验收

- `consumer_chain_validation`: 必须验证 registry → fixed snapshot → Adapter Output → asset hash → 100 个 Generation Example → manifest 的完整链；单元测试或 Schema 单独通过不能替代 live assembly。
- `real_integration_evidence`: `TEST-003` 使用公开固定 Commit 全量运行两次并比较 TASK-0001 指标/aggregate；`TEST-004` 使用故障注入和并发运行证明原子/幂等/恢复。
- `failure_recovery_ownership_validation`: `pipeline.py` 独占状态推进、幂等锁和原子发布；`git_snapshot.py` 独占 mirror/worktree 创建与清理；`assets.py` 只报告资产失败而不发布；`contracts.py` 只判定合同结果。TEST-001/004 必须通过故障点、owner/lock、临时资源和旧输出前后哈希证明各责任边界没有遗漏、双写或错误接管。

### RISK-001

- `links`: `REQ-002`, `SCN-003`, `TEST-001`, `TEST-003`
- `description`: 实现误用远端 HEAD，导致结果随时间漂移并与审计 Commit 不一致。
- `mitigation`: registry Commit 是唯一输入；开始解析前验证 HEAD，live test 在默认分支变化下仍比较固定 Commit。

### RISK-002

- `links`: `REQ-003`, `RULE-003`, `TEST-001`
- `description`: Git checkout、LFS、Hook 或 submodule 触发上游代码/外部进程。
- `mitigation`: 禁用 hooks/submodules/filters，仅读取固定树；无法建立安全边界则 fail closed。

### RISK-003

- `links`: `INV-003`, `REQ-004`, `TEST-002`, `TEST-003`
- `description`: Prompt 与错误 image_path 跨记录配对，仍能产生数量正确的错误结果。
- `mitigation`: 使用单一结构记录内显式绑定、source locator 和逐案例 hash；sample 与 live 断言 native id/Prompt/image 同记录。

### RISK-004

- `links`: `REQ-005`, `SCN-005`, `TEST-002`, `TEST-003`
- `description`: 路径穿越、逃逸链接或 HTML 内容被当作图片读取。
- `mitigation`: 规范化相对路径、根目录 containment、链接策略、magic/size 检查和负例。

### RISK-005

- `links`: `INV-002`, `INV-008`, `REQ-008`, `TEST-002`, `TEST-003`
- `description`: 动态字段、遍历顺序或临时路径污染 identity/manifest，造成重跑漂移。
- `mitigation`: 稳定排序、内容寻址、runtime metadata 分离和两次 full-run digest 对比。

### RISK-006

- `links`: `INV-010`, `REQ-007`, `SCN-008`, `TEST-004`
- `description`: 中途失败覆盖上一版或留下消费者误读的半成品。
- `mitigation`: temp directory、最后 manifest、完整 hash 校验、原子发布和故障注入前后快照比较。

### RISK-007

- `links`: `SCN-007`, `REQ-008`, `TEST-004`
- `description`: 两个相同运行交叉写 mirror/worktree/output，产生损坏或不可判断结果。
- `mitigation`: source/idempotency-key 锁、独立 temp run root、明确 lock 冲突和无时间盲抢占。

### RISK-008

- `links`: `SCN-006`, `TEST-003`
- `description`: live Validator 依赖网络，历史 pass 被错误复用到新的外部环境。
- `mitigation`: live Validator 标记 environment_sensitive=true，当前运行必须实际执行；失败报告 validation pending/failed，不能引用旧 pass 完成。

### TEST-001

- `links`: `TASK-001`, `REQ-001`, `REQ-002`, `REQ-003`, `SCN-003`, `SCN-006`, `RISK-001`, `RISK-002`
- `method`: 离线测试 registry 正常/错误组合；在临时本地 Git repo 中测试 mirror/fixed snapshot、HEAD 漂移、缺 Commit、根目录保护、无 hooks/submodules/filters 和失败清理。
- `expected_observable_result`: 仅合格 g0dam config 可进入 snapshot；读取的 HEAD 精确等于固定 Commit；错误在 Adapter 前失败，临时资源清理且工作区无写入。
- `failure_path_covered`: 错误状态、移动 HEAD、Git 失败、不安全 runtime root、外部执行风险。
- `cannot_prove`: 离线临时 repo 不能证明 GitHub 当前可访问。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: pytest case 清单/结果、临时 Git commit/HEAD 对比、错误码、路径 containment、hook/filter/submodule 禁用和清理断言；实际结果写入执行 sidecar。

### TEST-002

- `links`: `TASK-002`, `REQ-004`, `REQ-005`, `REQ-006`, `INV-001`, `INV-002`, `INV-003`, `INV-004`, `INV-005`, `INV-006`, `RISK-003`, `RISK-004`, `RISK-005`
- `method`: 使用最小固定结构 fixture 验证 g0dam 字段映射、extensions、source_claimed、稳定 ids、逐案例配对和 Adapter/GE Schema；使用临时图片数据覆盖路径穿越、逃逸、HTML、bad magic、小文件、空 Prompt、重复 id 和 count drift。
- `expected_observable_result`: 正例输出与 expected fixtures 一致；所有非法内容产生预期稳定错误且不形成 contract-valid GE；相同输入两次稳定摘要一致。
- `failure_path_covered`: 结构变化、错配、未知字段、非法图片和不确定身份。
- `cannot_prove`: 小 fixture 不能证明真实 100-case 仓库全部成功。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: source sample/expected files哈希、Schema 结果、字段映射矩阵、负例错误码、identity/排序/摘要两次对比；实际结果写入执行 sidecar。

### TEST-003

- `links`: `OBJ-001`, `ASSEMBLY-001`, `TASK-001`, `TASK-002`, `REQ-009`, `INV-007`, `INV-008`, `RISK-001`, `RISK-003`, `RISK-004`, `RISK-005`, `RISK-008`
- `method`: live Validator 在新的临时外部根目录获取固定 Commit，完整执行两次 extraction；校验 100 Adapter records、100 images、100 GE、零 errors、全部 contracts、逐文件 manifest、TASK-0001 指标和 aggregate；确认输出不包含图片字节。
- `expected_observable_result`: 两次运行所有 Gate 通过，稳定 manifest/digest 完全一致，Commit 与 aggregate 精确匹配，临时资源最终清理。
- `failure_path_covered`: 真实网络/Git、完整数据结构、100 图片读取、指标漂移、dynamic identity 和工作区污染。
- `cannot_prove`: 不证明未来 Commit 或其他来源继续兼容，也不证明数据库/对象存储已接入。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: Git URL/Commit、环境指纹、两次 run summary、100-case 指标、aggregate、manifest/digest 对比、图片格式/size/hash 统计、contracts 结果、工作区/临时目录清理结果；实际输出写入正式 receipt/sidecar。

### TEST-004

- `links`: `ASSEMBLY-001`, `TASK-001`, `TASK-003`, `REQ-007`, `REQ-008`, `INV-010`, `SCN-007`, `SCN-008`, `RISK-006`, `RISK-007`
- `method`: 在离线 fixture pipeline 中先发布成功包并记录 manifest/file hashes；分别注入 Adapter 后、部分 asset 后、manifest 前和 replace 前失败，验证旧包不变；并发启动同键运行，验证锁和独立 temp roots。
- `expected_observable_result`: 所有故障非零退出、无新正式 manifest、旧包逐文件 hash 不变、临时目录按策略清理；并发只有一个 writer，另一个有界等待或 run_locked。
- `failure_path_covered`: 部分写、替换失败、进程/异常清理、并发交叉写和陈旧输出误读。
- `cannot_prove`: 本地文件锁不证明跨机器分布式协调；跨机器调度属于后续任务。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: 故障点矩阵、故障前后 manifest/文件 hash、退出码/错误码、temp/lock 清理、并发进程结果和单 writer 证明；实际结果写入执行 sidecar。

### 正式 Validator Manifest

以下两个 Validator 分别证明离线行为合同和 live 固定 Commit 真实集成。live Validator 的环境依赖不能由离线测试或旧收据替代。

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "g0dam-extraction-offline",
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
        "-q"
      ],
      "cwd": ".",
      "timeout_seconds": 180,
      "invalidation_paths": [
        "1.md",
        "config/sources-v1.yaml",
        "schemas/adapter-output-v1.schema.json",
        "schemas/generation-example-v1.schema.json",
        "docs/contracts/content-contract-v1.md",
        "pyproject.toml",
        "uv.lock",
        "ingestion",
        "tests/ingestion",
        "fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "docs/ingestion/g0dam-extraction-v1.md"
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
        "import pytest, jsonschema; print('ready')"
      ],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "g0dam-fixed-commit-live-integration",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "scripts/validate_g0dam_extraction.py",
        "--registry",
        "config/sources-v1.yaml",
        "--audit",
        "reports/source-audit-v1.json",
        "--prior-source-evidence-root",
        ".task-runs/TASK-0001",
        "--source-id",
        "g0dam-work-prompts",
        "--expected-commit",
        "690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "--runs",
        "2",
        "--failure-injection",
        "--json"
      ],
      "cwd": ".",
      "timeout_seconds": 900,
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
        "tests/ingestion",
        "fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe",
        "docs/ingestion/g0dam-extraction-v1.md",
        "scripts/validate_g0dam_extraction.py"
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
        "import jsonschema; print('ready')"
      ],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | 配置与安全快照 | `OBJ-001` / `TASK-001` / `TEST-001` | registry、固定 Commit、工作区外路径、Git 安全、HEAD 漂移和失败清理全部通过 | `EV-001` | 不证明 GitHub 当前可访问 |
| `GATE-002` | g0dam Adapter 与资产/合同 | `OBJ-001` / `TASK-002` / `TEST-002` | fixture 正例、负例、稳定 identity、source claim、资产安全和两个合同全部通过 | `EV-002` | 不证明全量真实仓库 |
| `GATE-003` | 真实 100-case 纵向提取 | `OBJ-001` / `ASSEMBLY-001` / `TASK-001` / `TASK-002` / `TEST-003` | 固定 Commit 全量两次运行达到 100/100/100、零错误、aggregate/manifest/digest 一致且工作区无污染 | `EV-003` | 不证明持久化与其他来源 |
| `GATE-004` | 幂等、并发与失败恢复 | `OBJ-001` / `ASSEMBLY-001` / `TASK-001` / `TASK-003` / `TEST-004` | 重跑稳定、同键单 writer、故障不产生新正式包、上一版逐文件不变、临时资源正确处理 | `EV-004` | 不证明跨机器分布式锁 |

# 10. 产物与完成回写

- `required_deliverables`:
  - `pyproject.toml`
  - `uv.lock`
  - `ingestion/__init__.py`
  - `ingestion/__main__.py`
  - `ingestion/cli.py`
  - `ingestion/pipeline.py`
  - `ingestion/registry.py`
  - `ingestion/git_snapshot.py`
  - `ingestion/contracts.py`
  - `ingestion/assets.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/adapters/base.py`
  - `ingestion/adapters/g0dam.py`
  - `docs/ingestion/g0dam-extraction-v1.md`
  - `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/source-files/data/prompts.sample.json`
  - `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-adapter-output.json`
  - `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-generation-examples.json`
  - `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-metrics.json`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `tests/ingestion/test_g0dam_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `scripts/validate_g0dam_extraction.py`

### 必交产物

- `pyproject.toml`
- `uv.lock`
- `ingestion/__init__.py`
- `ingestion/__main__.py`
- `ingestion/cli.py`
- `ingestion/pipeline.py`
- `ingestion/registry.py`
- `ingestion/git_snapshot.py`
- `ingestion/contracts.py`
- `ingestion/assets.py`
- `ingestion/adapters/__init__.py`
- `ingestion/adapters/base.py`
- `ingestion/adapters/g0dam.py`
- `docs/ingestion/g0dam-extraction-v1.md`
- `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/source-files/data/prompts.sample.json`
- `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-adapter-output.json`
- `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-generation-examples.json`
- `fixtures/adapters/g0dam-work-prompts/690c2d6969a65b406b17ba7d41f18695a652c3fe/expected-metrics.json`
- `tests/ingestion/test_registry_and_snapshot.py`
- `tests/ingestion/test_g0dam_adapter.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `scripts/validate_g0dam_extraction.py`

### 完成与回写规则

- `documentation_impact`: updated；新增 Python ingestion package、g0dam extraction 运行合同和固定结构 fixtures，不修改上游设计/合同。
- `repository_hygiene_requirement`:
  - 只提交代码、lockfile、文档、少量 JSON fixture 和测试；不提交镜像、worktree、图片、运行 output、`.venv`、`.pytest_cache`、`__pycache__`、日志或凭据。
  - runtime data/output 必须在 `C:/Users/admin/.codex/runtime/image2/TASK-0003` 或 formal Validator 的临时外部目录；完成前确认 `D:/image2` 未出现运行残留。
  - `UV_PROJECT_ENVIRONMENT` 与 `UV_CACHE_DIR` 必须固定到上述工作区外 runtime root；不得在仓库生成 `.venv` 或依赖缓存。
  - `D:/image2/.task-runs` 与 `.work/source-audit` 保持只读；正式证据使用工作区外 canonical run。
  - 当前工作区不是 Git 仓库，因此不要求 commit；Completion Report 必须覆盖全部 22 个明确文件并列出保护文件未修改。
- `external_review`: policy=never；reason=任务要求正式 L4 独立语义审查和真实 live integration，暂无额外外部模型审阅需要；任何合同/风险变更仍由用户决定。
- `non_completion_rules`:
  - 任一必交文件、两个正式 Validator、live 100-case 证据或 Completion Report 缺失时不得完成。
  - 实际 Commit 不是 registry 固定 Commit、处理数不是 100、pair_rate 不为 1.0、broken assets 非零或 aggregate 不匹配时不得完成。
  - 任何 Prompt/image 跨记录错配、路径逃逸、HTML/非法图片通过、source claim 被提升或发布决策字段出现时不得完成。
  - 相同输入两次稳定 manifest/digest 不一致、并发存在多 writer、故障覆盖上一版或留下可误读半成品时不得完成。
  - mirror/worktree/image/output/cache 写入 `D:/image2`，或历史 `.task-runs/.work` 被修改时不得完成。
  - `.venv`、`.pytest_cache`、`__pycache__`、uv cache 或其他宿主难以清理的生成物出现在工作区时不得完成。
  - live Validator 因环境失败时只能报告真实 validation pending/failed；不得以离线测试或历史网络结果替代。
  - 需要数据库、对象存储、第二 Adapter、网页、队列或修改 TASK-0001/0002 合同时必须停止并创建后续任务/变更，不得扩张 TASK-0003。

执行时将 `CODEX_TASK_STATE_ROOT` 固定为 `C:/Users/admin/.codex/task-state/image2`；run/candidate、正式命令、环境指纹、live 网络/Git 结果、文件/manifest hash、Validator receipt、L4 独立审查、最终状态和跳过项写入正式生命周期自动解析的唯一 TASK-0003 canonical run，不写回本卡或仓库内 `.task-runs`。
