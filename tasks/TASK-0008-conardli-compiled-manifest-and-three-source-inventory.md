---
task_contract_version: 3
card_id: "TASK-0008"
title: "接入 ConardLi compiled-case pilot 并验证三来源库存闭环"
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
  - 用户目标模式授权：沿已确认的“长期固定高价值来源，稳定提取图片与对应 Prompt”方向持续执行，完成 Phase 1 三类 pilot 的纵向验证闭环。
  - `D:/image2/1.md`：固定版本来源、Adapter Output、资产/配对、Generation Example、内部库存及 rights/publication fail-closed 边界。
  - `D:/image2/config/sources-v1.yaml`：`conardli-gpt-image-2-101` 的固定 Commit `971b67dc8cbca8cf6eb32e196fea04bddd6abe99`、策略 `conardli_compiled_case_manifest_v1`、结构 `compiled_multi_category_case_gallery`、`auto_publish=false`、prompt/asset `review_required`、license unknown。
  - `D:/image2/reports/source-audit-v1.json`：ConardLi 162 observed/exact/paired/valid/unique cases、0 broken assets、pair rate 1.0、aggregate `36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573`，质量结论为带发布限制通过。
  - TASK-0002 冻结的 Adapter Output / Generation Example 合同；其中 ConardLi 示例的 Prompt 位置是早期说明性路径，真实 Adapter 必须使用仓库中的 `public/case/{prompt_path}`，不得为保持该说明性错误而输出不存在的路径，也不得改写已冻结 TASK-0002 fixture。
  - TASK-0003、TASK-0005、TASK-0007 已正式闭环的 g0dam legacy extraction、通用私有库存和 JoeSai neutral extraction；其输出、证据和 rights/publication 边界均是兼容基线。
  - 对固定 Commit 的只读结构核验：`src/data/cases.json` 顶层精确包含 `generated_at/summary/categories/templates/cases`；17 categories、79 templates、162 cases；158 JSON Prompt、4 TXT Prompt；全部 Prompt 文件内容与 `prompt_content` 精确一致；162 PNG 与 162 `-thumb.webp` 均存在。
  - `public/case/_mapping.json` 与 79 templates / 162 cases 一一一致；`public/case/INDEX.md` 的一处 161 统计已过时，只能作为允许存在的非权威说明文件，不能覆盖主清单或使正确快照失败。
- `decision_owner`: 用户拥有业务目标、风险和发布边界最终决定权；执行者只能按本卡接入第三 pilot，不得扩大为同步、发布、API 或网页实现。
- `material_unknowns`:
  - fresh live run 时 GitHub、Docker、PostgreSQL 或 S3-compatible service 可能暂时不可用；历史 TASK-0007 pass 不得替代本卡新证据。
  - 三来源图片 content hash 的全局去重数必须从三份真实 ImportPlan 求并集，不以“312 cases 必然等于 312 distinct assets”作未经验证的假设；但 312 asset sources、generation outputs 与 pairing records 必须闭合。
  - Windows 对 symlink 创建的权限若缺失，只能如实记录对应离线验证环境问题；不得删除 symlink 安全需求或把未执行测试写成通过。
  - ConardLi 内容包含品牌、公众人物或其他敏感/IP 题材；本任务只允许私有库存，不对案例内容做自动发布资格判断。

# 2. 业务目标

- `actor`: 项目协调者、固定来源抽取系统、内部库存维护者和后续发布/API 切片实施者。
- `workflow_and_trigger`: g0dam 与 JoeSai 已形成两个真实 fixed-commit extraction → private inventory 闭环；现在需要把第三类 compiled multi-category gallery 接入同一合同和库存消费者，证明来源异构但下游统一。
- `single_outcome`: 在不执行上游应用或 skill 代码、不改变既有两来源输出的前提下，严格解析 ConardLi 固定 Commit 的完整 compiled manifest、secondary mapping、Prompt/PNG/thumbnail 文件集，产出 162 个确定性 Adapter Output / Generation Example，并与 g0dam 100 + JoeSai 50 一起进入同一 fresh PostgreSQL/S3 私有库存，完成三来源 312-case 的正式可审计闭环。
- `observable_results`:
  - `RESULT-001`: 新的来源无关 snapshot 文件安全层同时服务 JoeSai 与 ConardLi；JoeSai expected Adapter Output / Generation Examples / metrics 及全部已有测试保持不变，g0dam legacy surface 保持不变。
  - `RESULT-002`: ConardLi fixture 严格证明主清单、category/template 索引、`_mapping.json`、真实 Prompt 文件、PNG 和 thumbnail 一一闭合；extra/missing/drift/path escape/symlink/invalid JSON 均 fail closed；`INDEX.md` 不参与权威计数。
  - `RESULT-003`: live 两次提取固定 Commit 均得到 162 records、162 Generation Examples、0 parse errors、0 broken assets、pair rate 1.0 和审计 aggregate；package/metrics 使用 neutral `extraction-package/v1` / `extraction-metrics/v1`。
  - `RESULT-004`: 同一 fresh inventory 中存在 3 projects/revisions/runs、528 source files、312 cases/versions/prompts/asset sources/Generation Examples/outputs/pairings/rights、0 inputs/parse errors；assets/objects 等于三份 plan 的 content-hash 并集，全部对象完成下载 hash 复核。
  - `RESULT-005`: ConardLi 五个 extraction failure points、same-key concurrency、三包 `verified_existing` replay、rights/publication fail-closed、随机 Compose/runtime 清理全部通过。
  - `RESULT-006`: 文档、工作区卫生、L4 独立语义审查、terminal freshness 和 Completion Report 全部闭合，canonical run 终态为 COMPLETE。
- `non_goals`:
  - 不执行、构建或依赖 ConardLi 的前端应用、Node 代码、skill 内容或 `references/*.md`；只读取固定 Commit 的静态数据和媒体文件。
  - 不把 `-thumb.webp` 作为第二资产导入；thumbnail 仅验证和保留来源元数据，主 PNG 才是 `output_primary`。
  - 不修改 `config/sources-v1.yaml`、`reports/source-audit-v1.json`、TASK-0001/0002/0003/0005/0006/0007 或其 formal evidence。
  - 不新增 inventory schema/migration，不改变事务、安全、对象存储或幂等语义。
  - 不实现定时同步、Commit 更新、Canonical/去重策略、rights review、内容审核、publication、API 或网页。
  - 不因 registry 的 `model_scope=gpt-image-2_claimed` 自动把 case-level `source_claim` 提升为 source_claimed；缺少逐案例证据时保持 unknown。

# 3. 需求质疑与确认

- `user_statement`: 按确定方向持续执行；稳定固定能提取高价值图片与对应 Prompt 的项目，严谨完成第三 pilot。
- `REQ-001` (`required_behavior`): 将 snapshot root、路径归一化、逐组件 symlink 拒绝、regular-file 读取和递归文件集枚举抽到 `ingestion/adapters/snapshot_files.py`；该层只拥有静态快照安全，不包含 JoeSai 或 ConardLi 业务语义，并允许调用方保留各自 AdapterError 类型和稳定 error code。
- `REQ-002` (`required_behavior`): JoeSai 改用共享安全层后，其现有 fixture 输出、Prompt identity、错误类/错误码、manifest/Markdown/file-set/symlink 行为必须不变；g0dam 代码和 legacy fixtures 不得修改。
- `REQ-003` (`required_behavior`): registry 只新增静态映射 `conardli_compiled_case_manifest_v1 → compiled_multi_category_case_gallery`，dispatch 只显式注册 `parse_conardli_snapshot`；unsupported 或 strategy/structure mismatch 继续在任何 Git/extraction side effect 前拒绝。
- `REQ-004` (`required_behavior`): ConardLi parser 以 `src/data/cases.json` 为主权威，要求精确顶层字段、非空 RFC3339 `generated_at`、内部守恒的 summary/categories/templates/cases，并在 live 固定 Commit 精确闭合 17/79/162。
- `REQ-005` (`required_behavior`): category 必须使用精确字段 `accent,cn,key,label,ready,templates,total`；template 必须使用精确字段 `cases_count,category,content,description,key,label,md_path,name`；键、slug、category/template 归属、列表成员、计数、case label/accent 均需交叉一致。`md_path` 只做安全相对路径与元数据校验，不读取或执行其指向内容。
- `REQ-006` (`required_behavior`): case 必须使用精确 17 字段，`id=category/template-name/idx`、idx 为正整数、format 仅 `json|txt`、`has_image=true`；id、prompt_path、prompt_url、image_url、thumb_url 必须由同一稳定 native mapping 精确对应且各自唯一。
- `REQ-007` (`required_behavior`): 真实 Prompt 路径必须是 `public/case/{prompt_path}`；UTF-8 文件文本必须与 `prompt_content` 精确相等并原样进入 `prompt.raw_text`，只允许 `prompt_sha256` 使用既有 NFC/newline/strip identity normalization；JSON format 必须解析为 object，TXT 必须为非空文本。
- `REQ-008` (`required_behavior`): 主 PNG `public/case/{case-id}.png` 必须作为唯一 `output_primary`；`public/case/{case-id}-thumb.webp` 必须是非空 regular file并与 `thumb_url` 精确一致，但不得生成第二 asset reference、generation input/output 或 inventory object。
- `REQ-009` (`required_behavior`): `_mapping.json` 必须精确包含 `summary/items`，item 和 nested case 字段必须与固定 compiled shape一致；79 template items / 162 nested cases 与主清单在 category/template/idx/title/brief/format/prompt_path 上一一对应。`source_md/template_md` 只保留和校验安全路径，不读取缺失的 skill/reference 源文件。
- `REQ-010` (`required_behavior`): `public/case` regular-file set 必须恰好等于 162 Prompt + 162 PNG + 162 thumbnail + `_mapping.json` + `INDEX.md`；任何 extra/missing/non-regular/symlink entry 失败。`INDEX.md` 内容、统计和排序不得参与 case 发现、计数或输出 identity。
- `REQ-011` (`required_behavior`): 每条 Adapter record 使用 source_case_locator `src/data/cases.json`，Prompt location 使用真实 `public/case/{prompt_path}`，asset location 使用 PNG，pairing method=`stable_native_mapping`、status=`strong`，证据精确包含 cases manifest、mapping、Prompt 和 PNG 四类 location；因此 ConardLi ImportPlan source files 精确为 326。
- `REQ-012` (`required_behavior`): `prompt.language=mixed`、raw_tags 仅 category；source claim 保持 unknown；prompt/asset rights 保持 unknown并明确 registry review_required 不构成发布授权。
- `REQ-013` (`required_behavior`): namespaced `conardli.source` 只保存必要的 case/category/template 原始元数据、manifest/mapping/thumbnail locator，不重复保存 `prompt_content`；Generation Example 仅显式传播 `joesai.source` 与 `conardli.source` 两个 non-legacy namespace，不传播 `g0dam.source`，确保 g0dam frozen GE 不变。
- `REQ-014` (`required_behavior`): ConardLi package/metrics schema 显式映射到 neutral v1；fixture 必须覆盖 JSON、TXT、idx=3 三类真实结构并冻结 expected Adapter Output / Generation Examples / metrics。
- `REQ-015` (`required_behavior`): live Validator 对三个 fixed Commit 各完整提取两次并验证 files/manifest/semantic hashes、case counts、schema、metrics 和 audit aggregate；只对本卡新增的 ConardLi 跑五故障点与 same-key concurrency，历史来源仍做完整正常路径回归。
- `REQ-016` (`required_behavior`): 三个 live packages 必须依次导入同一随机隔离 PostgreSQL/S3，per-run counts 不互相污染；global source_files 精确为 101 + 101 + 326 = 528，其余 312-case 关系按 plan 闭合，assets/objects 按 content-hash union闭合并逐个下载复核。
- `REQ-017` (`required_behavior`): 三来源同键 replay 都必须返回 `verified_existing` 且 DB/S3 snapshot 不增长；g0dam 100 case-level claims 保持 source_claimed，JoeSai 50 + ConardLi 162 保持 unknown；312 rights records 全部 unknown，3 registry snapshots 均保持 review_required/auto_publish=false，库存不得出现 publication decision 字段。
- `REQ-018` (`required_behavior`): live 使用随机 Compose project、loopback ports、外部 TASK-0008 runtime、无 secrets 输出，只清理自身 Git worktrees/candidates/locks/containers/networks/volumes；不得触碰用户其他 Docker 或 runtime 状态。
- `REQ-019` (`required_behavior`): 同步 `docs/ingestion/conardli-extraction-v1.md` 与 `docs/inventory/internal-inventory-v1.md`，说明权威层次、路径、thumbnail 非资产、neutral schema、三来源 counts 和 fail-closed 边界。
- `REQ-020` (`required_behavior`): 形成 TASK-0008 自有 fresh receipts、L4 independent review、documentation/hygiene/freshness evidence 和 schema-valid complete Completion Report；不得引用 TASK-0007 receipt 代替本卡验证。
- `INV-001`: 上游仓库只被 Git 固定 Commit checkout 和静态文件读取，任何 install/build/import/execute 都禁止。
- `INV-002`: `src/data/cases.json` 是 case discovery 主权威，`_mapping.json` 是一致性证据，`INDEX.md` 非权威；三者责任不得倒置。
- `INV-003`: Prompt raw text、stable native mapping、主 PNG content hash 和 source URL 必须来自同一固定 revision；不允许启发式配对或由文件名猜测缺失关系。
- `INV-004`: g0dam legacy package/metrics/GE identity 与 JoeSai neutral package/metrics/GE identity不变。
- `INV-005`: Adapter 输出和 package 只存 JSON；不得把真实 162 张 PNG/thumbnail、完整上游仓库或 live package 写入工作区。
- `INV-006`: inventory 仍是 private source-of-truth storage，不新增 visibility/publication/mirror/license approval 推断。
- `INV-007`: registry/audit 和已完成任务卡/evidence 是只读权威；发现与固定 Commit 不一致时 fail closed，不反向修改审计来适配实现。
- `material_ambiguities`:
  - TASK-0002 的 ConardLi illustrative fixture 将 Prompt source_path 写成未实际存在的 `academic-figures/.../1.json`；真实仓库文件位于 `public/case/...`。本卡以可验证真实文件路径为准，同时保持冻结 fixture 不变。
  - `_mapping.json` 指向未随 compiled repo 交付的 `references/*.md`。这些字段是来源元数据，不是本项目所需的 Prompt/图片 pair，也不是可执行依赖；本卡只验证路径安全与 compiled-case 对应关系。
  - `INDEX.md` 自身已有 161/162 漂移，因此“严格”不能等于盲信所有文本；严格边界是信任结构化主清单、交叉验证 mapping 和实际文件集，并显式把 INDEX 降为非权威。
- `decisions_and_authority`:
  - 共享 snapshot helper 是本次唯一生产侧结构提取；它已有两个实际消费者，能消除重复安全逻辑且不引入未来占位抽象。
  - 新三来源 live Validator 独立成文件；不重构或改写 TASK-0007 已使用的 `validate_joesai_multi_source.py`，避免扩大已闭环证据面的回归风险。
  - thumbnail 只验证不入库；若未来网页需要 thumbnail pipeline，另建任务并重新定义资产角色与消费者。

# 4. 业务场景与规则

- `SCN-001` 主路径: 固定 Commit → strict compiled manifest parse → 162 Prompt/PNG pairs → neutral package → 三来源同库导入 → object hash复核 → 三包 replay → complete report。
- `SCN-002` 主清单漂移: 顶层/分类/模板/case 字段、计数、索引或 URL 任一不一致；Adapter 以稳定错误码失败且不发布 package。
- `SCN-003` mapping 漂移: missing/extra template/case、field mismatch、unsafe path；即使 cases.json 单独可解析，也必须失败。
- `SCN-004` 文件集漂移: Prompt/PNG/thumb missing、extra、non-regular 或 symlink；必须失败，不静默跳过。
- `SCN-005` Prompt 漂移: `prompt_content` 与真实文件不一致、JSON 非 object、TXT 空白；必须失败，不选择任一版本继续。
- `SCN-006` INDEX 漂移: INDEX 中计数或文本变化；只要结构化主权威、mapping 和文件集正确，输出必须完全不变。
- `SCN-007` legacy 回归: shared helper、dispatch 或 extension propagation 改变 JoeSai/g0dam expected bytes；offline Validator 失败。
- `SCN-008` live extraction 失败/并发: ConardLi 任一控制故障不污染已发布包，同键第二 writer 返回 `run_locked`，临时状态清理。
- `SCN-009` cross-source inventory: 三包进入同一库且 per-run/global counts、hash union、claims/rights 和重放闭合；任何 collision/partial import/growth 阻断。
- `SCN-010` live 环境不可用: 当前 validation pending/failed；不得以 mock、fixture、旧 receipt 或部分来源代替。
- `RULE-001`: parser 只使用显式静态 dispatch，不动态 import registry 中的任意模块名。
- `RULE-002`: `cases.json` 决定 case identity；mapping 只能验证，不新增、删除或重命名 case。
- `RULE-003`: normalized Prompt 只用于 ID/fingerprint；输出 `raw_text` 保留真实文件文本。
- `RULE-004`: pairing evidence 必须可追溯到真实固定 Commit URL，不得使用不存在的 illustrative 路径。
- `RULE-005`: neutral extension 必须 namespaced 且不进入基础 schema 决策；legacy g0dam extension传播规则保持冻结。
- `RULE-006`: live expected counts/aggregates来自卡内固定值，source-file/object counts同时由 ImportPlan 交叉计算；两者不一致即失败。
- `RULE-007`: formal evidence 写入外部 canonical run；workspace 只保留声明的代码、文本 fixtures、测试和文档。
- `STATE-001`: `PRECHECK → DISCOVER_AND_PLAN → IMPLEMENT_AND_DEVELOPMENT_CHECKS → FREEZE_CANDIDATE → RUN_FORMAL_VALIDATIONS → CHECK_DOCUMENTATION_AND_HYGIENE → INDEPENDENT_CHECK → FINALIZE`。
- `FLOW-001`: `fixed registry/audit → static snapshot → adapter output → asset resolution → Generation Examples → package → three-source private inventory → formal closure`。
- `risk_sensitive_invariants`:
  - strict parser 的目标是阻止静默错配，不是把非权威 INDEX 文本升级成结构合同。
  - 共享安全层必须减少重复 owner，同时保持 source-specific parser 和错误类型归各 Adapter 所有。
  - 三来源成功只证明 private ingestion，不构成内容质量复审、权利批准或公开发布授权。
- `inapplicable_faces_with_reason`:
  - Git commit：`D:/image2` 不是 Git repository，本卡不创建 commit；formal snapshot/hash 提供变更与新鲜度证据。
  - 外部模型审查：用户未要求；本卡使用 L4 independent semantic review 和真实 Git/DB/S3 integration。
  - API/UI：当前消费者是 private inventory，公开消费面另卡实现。

# 5. 当前证据与目标差异

- `FACT-001`: registry/audit 已固定第三 pilot 身份、Commit、完整指标和 review_required 权利边界，但 registry loader/dispatch 尚不支持其策略。
- `FACT-002`: 当前 production Adapter 只有 g0dam 与 JoeSai；JoeSai 内含可复用但来源局部的 snapshot path/symlink/file-set helpers。
- `FACT-003`: `generation_example_for` 仅传播 `joesai.source`，package/metrics schema mapping 仅含 g0dam/JoeSai。
- `FACT-004`: ConardLi 固定快照真实结构为 17 categories、79 templates、162 cases、488 个 `public/case` files；其中允许文件只有 162 Prompt、162 PNG、162 thumbnail、mapping 和 INDEX。
- `FACT-005`: 全部 162 `prompt_content` 与真实文件精确一致；158 JSON 可解析为 object，4 TXT 非空；case/mapping/category/template 交叉核验无结构问题。
- `FACT-006`: INDEX 已出现 161 文本计数漂移，证明其不能作为机器主权威。
- `FACT-007`: generic inventory 已接收 g0dam legacy 与 JoeSai neutral packages，不需要新 schema/migration即可接收第三个 neutral package。
- `ASM-001`: 当前 GitHub/Docker/DB/S3 环境预期可完成 fresh live run；失败时必须保留真实状态。
- `current_execution_path`: ConardLi 只有审计和合同样例，没有 production static parser、真实 package 或三来源 inventory evidence。
- `target_delta`: shared snapshot boundary + ConardLi strict adapter + neutral package mapping + fixtures/tests + three-source live validator + docs + formal completion。
- `evidence_gaps`:
  - 无 ConardLi production Adapter 和固定 fixture expected outputs。
  - 无 162-case 两次 live extraction、fault/concurrency evidence。
  - 无三来源 312-case 同库 counts、object union、replay 和 rights evidence。
  - 无 TASK-0008 fresh formal receipts、independent review 和 Completion Report。

# 6. 范围与责任边界

- `allowed_write_scope`:
  - `ingestion/adapters/snapshot_files.py`
  - `ingestion/adapters/conardli.py`
  - `ingestion/adapters/joesai.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/registry.py`
  - `ingestion/contracts.py`
  - `tests/ingestion/test_conardli_adapter.py`
  - `tests/ingestion/test_joesai_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/**`，仅卡内列出的文本 fixture 文件；测试运行时生成的假 PNG/WebP 不写回仓库。
  - `scripts/validate_three_pilot_sources.py`
  - `docs/ingestion/conardli-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`
  - `C:/Users/admin/.codex/task-state/image2/TASK-0008-*/**` formal evidence。
  - `C:/Users/admin/.codex/runtime/image2/TASK-0008/**` validator-owned external runtime。
- `hard_protected_scope`:
  - `config/sources-v1.yaml`、`reports/source-audit-v1.json`、`1.md`、schemas、migrations、inventory production code、compose definition、pyproject/lock。
  - `ingestion/adapters/g0dam.py`、g0dam/JoeSai frozen expected fixtures、TASK-0001 至 TASK-0007 cards/runs/reports。
  - `scripts/validate_joesai_multi_source.py` 及旧 Validator evidence。
  - 用户其他 Git repositories、Docker resources、runtime、credentials 和外部系统。
- `protected_contracts_and_invariants`: TASK-0002 schema/semantics、g0dam legacy identity、JoeSai neutral identity、inventory transaction/security/idempotency、fixed registry/audit、rights/publication fail-closed。
- `authorization_limits`: 只授权本卡声明的第三 Adapter、共享安全 helper、验证/fixture/doc 和外部测试状态；不授权外部发布、registry/audit变更或生产数据库写入。
- `stop_if_scope_expands`:
  - 需要执行上游 app/skill 或读取未随 compiled repo 交付的 reference 源文件。
  - 需要修改 schema/migration/inventory production semantics 或既有来源 expected outputs。
  - 需要改变 fixed Commit、audit metrics、rights/publication policy。
  - 需要把 thumbnail 变成独立资产或实现 API/UI/sync。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: `ingestion.pipeline.extract` → static strategy dispatch → `parse_conardli_snapshot` → existing asset resolver/contracts/package writer → `inventory.package.build_import_plan` → existing inventory CLI/PostgreSQL/S3。
- `expected_touchpoints_or_search_anchors`:
  - `ingestion/adapters/snapshot_files.py`: fixed snapshot root、safe regular file、byte-preserving UTF-8 text、recursive regular-file set、symlink rejection；错误类型由 caller 注入。
  - `ingestion/adapters/conardli.py`: exact cases/category/template/mapping/file-set contract、record mapping、namespaced extension。
  - `ingestion/adapters/joesai.py`: 删除本地重复 helper 并调用 shared layer；业务 parser 不重写。
  - `ingestion/adapters/__init__.py` / `ingestion/registry.py`: 第三种显式 strategy/structure。
  - `ingestion/contracts.py`: ConardLi neutral package/metrics mapping和显式 non-legacy extension allowlist；g0dam不变。
  - ConardLi fixture/tests、三来源 live Validator、两份文档。
- `wiring_to_final_consumer`: production extraction 生成标准 package；generic inventory 未经适配层分支直接消费，三来源在同一 schema/DB/S3 路径共存；Completion Report 成为后续 publication/API/web 任务前置证据。
- `failure_and_recovery`: shape/data/asset/contract/Git/DB/S3 任一失败沿既有 error owner 回滚/清理；不发布 partial package、不写 partial inventory、不提升 rights；环境失败可 validation pending但不得声称完成。
- `implementation_freedom`: 可调整函数名和内部数据结构，但必须维持上述文件责任、真实路径、四类 pairing evidence、326 source files、legacy bytes 和全部 observable results；不得通过放宽测试适配错误实现。
- `selected_profile_obligations`:
  - public-contract: Adapter/GE/package schema与legacy/neutral compatibility。
  - external-boundary: fixed Git source、path/symlink/media、Docker/DB/S3/hash/cleanup。
  - configuration: strategy/structure/rights/publication registry boundary。
  - stateful-runtime: atomic package、single writer、inventory transaction/idempotency、formal lifecycle。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `REQ-001` 至 `REQ-003`, `REQ-013`, `INV-001`, `INV-004`
- `owns_behavior`: shared snapshot safety、JoeSai compatibility、third dispatch/registry/schema mapping。
- `target_delta`: 建立两个 static adapters 共用的最小安全责任边界，并接通 ConardLi 策略而不改变 legacy 输出。
- `integration_edges`: registry → dispatch → parser；record extensions → Generation Example；strategy → package/metrics schema。
- `expected_touchpoints`: shared helper、JoeSai、adapter exports、registry、contracts、compatibility tests。
- `linked_tests`: `TEST-001`
- `stop_conditions`: JoeSai/g0dam fixture漂移、错误类型/码变化、动态 dispatch、helper包含来源语义。

### TASK-002

- `links`: `REQ-004` 至 `REQ-014`, `INV-002`, `INV-003`, `INV-005`, `INV-007`
- `owns_behavior`: ConardLi strict compiled manifest parser、fixture和全部负例。
- `target_delta`: 从真实结构稳定生成三条代表性 fixture 输出，并为 live 162-case 提供无启发式生产路径。
- `integration_edges`: cases.json + mapping + files → ParsedCase → resolved Adapter Output → Generation Examples → metrics。
- `expected_touchpoints`: conardli adapter、fixture source files/expected docs、adapter/pipeline tests。
- `linked_tests`: `TEST-002`
- `stop_conditions`: 依赖 INDEX、容忍 silent drift、使用不存在路径、读取/执行 source_md、thumbnail入库或 source claim升级。

### TASK-003

- `links`: `REQ-015` 至 `REQ-019`, `INV-005`, `INV-006`
- `owns_behavior`: 三来源 fresh extraction/private inventory live assembly和权威文档同步。
- `target_delta`: 形成 100+50+162 的真实统一消费者证据，证明第三种来源结构无需修改 inventory core。
- `integration_edges`: three packages → ImportPlans → migrations → one DB/private bucket → inspect/hash/replay/rights → cleanup。
- `expected_touchpoints`: new live Validator、ConardLi extraction doc、inventory doc。
- `linked_tests`: `TEST-003`, `TEST-004`
- `stop_conditions`: 任一来源非固定 Commit、使用 mock/旧 package、修改 inventory core、counts/hash/rights/replay/cleanup不闭合。

### TASK-004

- `links`: `REQ-020`
- `owns_behavior`: documentation/hygiene/freshness、L4 independent review和Completion Report。
- `target_delta`: 把实现与两项 fresh Validators 绑定到 TASK-0008 canonical complete run。
- `integration_edges`: candidate + receipts + docs/hygiene → independent review → report validation → terminal state。
- `expected_touchpoints`: TASK-0008 external run root only。
- `linked_tests`: `TEST-005`
- `stop_conditions`: stale/foreign receipt、deliverable缺失、review finding、blocker或report schema/freshness失败。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`
- `end_to_end_entry`: `python -B -m ingestion extract --source-id conardli-gpt-image-2-101 ...` 和三来源 live Validator。
- `shared_contract_state_data`: registry/audit identity、safe snapshot paths、Adapter Output/GE schemas、package manifests、ImportPlans、DB/S3 state、rights snapshots、formal receipts。
- `final_consumer`: 后续三来源 publication/API/minimal-web 与 fixed-Commit update任务。
- `cross_task_failure_path`: 任一 compatibility/parser/live/formal Gate失败时不生成 complete report；package/inventory/runtime按 owner清理并保留可审计 blocker。
- `linked_test_evidence_gate`: `TEST-001` 至 `TEST-005` / `EV-001` 至 `EV-005` / `GATE-001` 至 `GATE-005`

# 9. 验证与验收

- `consumer_chain_validation`: 必须证明 fixed Commit 静态文件实际进入 production parser、existing asset resolver、Generation Example/package和未经 ConardLi 分支修改的 inventory consumer；仅比较 fixture 或 schema 不足。
- `real_integration_evidence`: live 必须 clone/check out 三个公开固定 Commit、读取完整 312 Prompt/PNG pairs、使用真实随机 PostgreSQL/S3 containers、下载复核全部 content-addressed objects，并清理 owned resources。
- `failure_recovery_ownership_validation`: Adapter拥有 shape/data错误，asset resolver拥有 PNG内容，pipeline拥有 package lock/atomic publish，inventory拥有事务/replay，validator拥有 Compose/runtime cleanup；不得新增并列 owner或绕过既有恢复路径。

### RISK-001

- `links`: `REQ-001`, `REQ-002`, `TEST-001`
- `description`: 提取共享 helper 时改变 JoeSai错误/路径行为或 g0dam/GE legacy bytes。
- `mitigation`: source-neutral helper + caller error class + frozen expected fixtures +全量现有 ingestion tests。

### RISK-002

- `links`: `REQ-004` 至 `REQ-011`, `TEST-002`
- `description`: compiled manifest、mapping、实际文件三者之一漂移时仍生成看似有效但错配的 pair。
- `mitigation`: exact fields、双索引守恒、四 location evidence、完整 file-set和系统化负例。

### RISK-003

- `links`: `REQ-007`, `REQ-013`, `TEST-002`
- `description`: Prompt 被重排/重序列化或 metadata重复大文本，导致来源忠实度和package体积问题。
- `mitigation`: byte-preserving UTF-8 equality、raw_text原样、JSON仅校验不重写、extension不复制prompt_content。

### RISK-004

- `links`: `REQ-015` 至 `REQ-018`, `TEST-003`, `TEST-004`
- `description`: 单来源pass掩盖cross-source collision、partial import、idempotent growth、rights提升或资源泄漏。
- `mitigation`: 一库三包、plan-derived全局counts/hash union、逐对象下载、三包replay、SQL rights/publication断言、label-scoped cleanup。

### RISK-005

- `links`: `REQ-019`, `REQ-020`, `TEST-005`
- `description`: 代码通过但文档、formal evidence或最终新鲜度不闭合。
- `mitigation`: authoritative docs更新、exact deliverables、fresh receipts、L4 independent review、terminal report validation。

### TEST-001

- `links`: `TASK-001`, `REQ-001` 至 `REQ-003`, `REQ-013`, `RISK-001`
- `method`: 运行现有和新增 ingestion/package tests；比较 g0dam/JoeSai expected Adapter Output、Generation Examples和metrics；验证第三 strategy dispatch/registry/schema、unsupported/mismatch pre-side-effect拒绝；覆盖 shared helper root/directory/file symlink与path escape。
- `expected_observable_result`: g0dam/JoeSai frozen outputs逐字节不变；ConardLi正确分发；所有不安全路径和unsupported config fail closed。
- `failure_path_covered`: helper regression、legacy extension leak、dynamic dispatch、strategy mismatch、symlink traversal。
- `cannot_prove`: 不证明 ConardLi完整162-case或真实 DB/S3。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: pytest receipt、frozen fixture equality、dispatch/schema assertions、共享helper symlink/path negative matrix。

### TEST-002

- `links`: `TASK-002`, `REQ-004` 至 `REQ-014`, `RISK-002`, `RISK-003`
- `method`: 从固定 Commit 选取 `academic-figures/qualitative-comparison-grid/1.json`、`academic-figures/scientific-schematic/1.txt`、`poster-and-campaigns/banner-hero/3.json` 三条真实 Prompt元数据形成缩小 fixture；测试运行时生成假 PNG/WebP。验证 expected output/GE/metrics，并逐项变异主清单、category/template、mapping、Prompt、URLs、file-set、INDEX和symlinks。
- `expected_observable_result`: JSON/TXT/idx3三类输出确定；真实路径、326-source-file设计、unknown rights/claim和thumbnail非资产规则闭合；全部有害漂移失败，仅INDEX文本漂移不改变输出。
- `failure_path_covered`: malformed JSON、prompt mismatch、mapping drift、extra/missing media、unsafe md_path/source_md、duplicate ids/paths、INDEX false authority。
- `cannot_prove`: 不证明固定 Commit全部162 cases/images当前可取。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: 3-case source fixtures、expected Adapter Output/Generation Examples/metrics hashes、negative matrix和contract validation结果。

### TEST-003

- `links`: `TASK-003`, `REQ-015`, `REQ-018`, `RISK-004`
- `method`: live 从 g0dam/JoeSai/ConardLi 固定 Commit各独立提取两次；逐包验证 schema/files/semantic digest/metrics/aggregate和无图片bytes；对 ConardLi 执行 after_adapter、after_assets、before_manifest、before_publish、before_replace 及 same-key concurrency；检查 worktree/candidate/lock清理。
- `expected_observable_result`: 100/50/162 case提取、三个audit aggregate和legacy/neutral schemas精确；两次结果稳定；五故障不污染，第二并发writer为`run_locked`，临时提取状态清理。
- `failure_path_covered`: Git/source drift、shape/media/contract/publish故障、nondeterminism、same-key race。
- `cannot_prove`: 不单独证明三包同库消费者。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: 三个 Commit、case counts、schema/aggregate、两次manifest/file/semantic hashes、ConardLi fault matrix/concurrency和Git/runtime cleanup。

### TEST-004

- `links`: `TASK-003`, `ASSEMBLY-001`, `REQ-016` 至 `REQ-018`, `RISK-004`
- `method`: 同一随机 Compose 环境应用 migrations两次，依次导入三包；按 ImportPlan 校验per-run/global counts、精确528 source files和312关系；计算asset hash union并下载复核全部objects；查询claims/rights/registry snapshots/forbidden publication fields；重导三包并比较DB/S3前后snapshot；最终label-scoped cleanup。
- `expected_observable_result`: 3 projects/revisions/runs、528 source files、312 cases等关系、0 inputs/parse errors；asset/object union全量复核；100 source_claimed + 212 unknown claims、312 unknown rights、三包verified_existing、无状态增长、无资源残留。
- `failure_path_covered`: cross-source contamination/collision、partial third import、false dedupe、object corruption、rights/publication elevation、replay growth、Docker leak。
- `cannot_prove`: 不证明生产环境、未来Commit、公开服务或权利批准。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: Docker digests/loopback配置（无秘密）、migration receipts、per-run/global counts、plan source-file和hash union、全部download hashes、SQL rights/claim/publication断言、三包replay和cleanup。

### TEST-005

- `links`: `TASK-004`, `REQ-019`, `REQ-020`, `RISK-005`
- `method`: 检查两份权威文档、exact deliverables、workspace/protected scopes和外部runtime卫生；创建candidate/terminal snapshots、deterministic evidence、L4 independent review；构建并验证complete Completion Report。
- `expected_observable_result`: 文档与实现/live counts一致，工作区无runtime/media/cache/secrets，independent findings=0，2/2 validators和全部deliverables通过，remaining blockers为空，run COMPLETE。
- `failure_path_covered`: stale/foreign evidence、doc drift、scope污染、false completion、cleanup omission。
- `cannot_prove`: 不证明未声明的后续产品功能。

### EV-005

- `for`: `TEST-005`
- `required_evidence_shape`: documentation impact、hygiene/protected/freshness artifacts、deterministic bundle、semantic independent review、Completion Report与official validation。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "conardli-three-source-offline",
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
      "timeout_seconds": 420,
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
        "fixtures/adapters/conardli-gpt-image-2-101",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/ingestion/conardli-extraction-v1.md",
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
      "validator_id": "conardli-three-source-compose-live",
      "command": [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "python",
        "-B",
        "scripts/validate_three_pilot_sources.py",
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
        "--conardli-source-id",
        "conardli-gpt-image-2-101",
        "--conardli-expected-commit",
        "971b67dc8cbca8cf6eb32e196fea04bddd6abe99",
        "--conardli-expected-cases",
        "162",
        "--conardli-expected-aggregate",
        "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573",
        "--runs",
        "2",
        "--failure-injection",
        "--concurrency",
        "--json"
      ],
      "cwd": ".",
      "timeout_seconds": 3600,
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
        "scripts/validate_three_pilot_sources.py",
        "fixtures/adapters/g0dam-work-prompts",
        "fixtures/adapters/joesai-commercial-prompts",
        "fixtures/adapters/conardli-gpt-image-2-101",
        "docs/ingestion/g0dam-extraction-v1.md",
        "docs/ingestion/joesai-extraction-v1.md",
        "docs/ingestion/conardli-extraction-v1.md",
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
| `GATE-001` | shared safety 与 legacy兼容 | `TASK-001` / `TEST-001` | JoeSai/g0dam frozen outputs不变，第三策略正确分发，path/symlink fail closed | `EV-001` | 不证明162-case live |
| `GATE-002` | ConardLi严格静态映射 | `TASK-002` / `TEST-002` | cases/mapping/Prompt/PNG/thumb闭合，INDEX非权威，负例全部拒绝 | `EV-002` | 不证明真实完整来源当前可取 |
| `GATE-003` | 三来源完整提取 | `TASK-003` / `TEST-003` | 100/50/162固定Commit、schema/aggregate/确定性、ConardLi故障与并发通过 | `EV-003` | 不证明同库状态 |
| `GATE-004` | 三来源同库 assembly | `TASK-003` / `ASSEMBLY-001` / `TEST-004` | 3 runs/528 source files/312关系/hash union/三包replay/rights/cleanup闭合 | `EV-004` | 不证明公开服务或权利批准 |
| `GATE-005` | 正式收口 | `TASK-004` / `TEST-005` | docs/hygiene/freshness、independent review、2/2 receipts、deliverables和report完整 | `EV-005` | 不证明后续API/UI/sync |

# 10. 产物与完成回写

- `required_deliverables`:
  - `ingestion/adapters/snapshot_files.py`
  - `ingestion/adapters/conardli.py`
  - `ingestion/adapters/joesai.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/registry.py`
  - `ingestion/contracts.py`
  - `tests/ingestion/test_conardli_adapter.py`
  - `tests/ingestion/test_joesai_adapter.py`
  - `tests/ingestion/test_extraction_pipeline.py`
  - `tests/ingestion/test_registry_and_snapshot.py`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-adapter-output.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-generation-examples.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-metrics.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/src/data/cases.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/_mapping.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/INDEX.md`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/qualitative-comparison-grid/1.json`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/scientific-schematic/1.txt`
  - `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/poster-and-campaigns/banner-hero/3.json`
  - `scripts/validate_three_pilot_sources.py`
  - `docs/ingestion/conardli-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`

### 必交产物

- `ingestion/adapters/snapshot_files.py`
- `ingestion/adapters/conardli.py`
- `ingestion/adapters/joesai.py`
- `ingestion/adapters/__init__.py`
- `ingestion/registry.py`
- `ingestion/contracts.py`
- `tests/ingestion/test_conardli_adapter.py`
- `tests/ingestion/test_joesai_adapter.py`
- `tests/ingestion/test_extraction_pipeline.py`
- `tests/ingestion/test_registry_and_snapshot.py`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-adapter-output.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-generation-examples.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/expected-metrics.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/src/data/cases.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/_mapping.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/INDEX.md`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/qualitative-comparison-grid/1.json`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/academic-figures/scientific-schematic/1.txt`
- `fixtures/adapters/conardli-gpt-image-2-101/971b67dc8cbca8cf6eb32e196fea04bddd6abe99/source-files/public/case/poster-and-campaigns/banner-hero/3.json`
- `scripts/validate_three_pilot_sources.py`
- `docs/ingestion/conardli-extraction-v1.md`
- `docs/inventory/internal-inventory-v1.md`

### 完成与回写规则

- `documentation_impact`: updated；新增 ConardLi extraction 权威说明，并把 internal inventory 文档从双来源更新为三来源，记录 326/528 source-file闭合、thumbnail非资产、neutral schema和rights/publication fail-closed。
- `repository_hygiene_requirement`:
  - 工作区只保存声明的 Python、测试、文本 fixture和文档；不保存真实 PNG/WebP、完整上游仓库、packages、DB/S3 volumes、Compose env、credentials、logs、`.pytest_cache`、`__pycache__` 或 venv。
  - `UV_PROJECT_ENVIRONMENT`、`UV_CACHE_DIR`、`TMP`、`TEMP`、Git/runtime/output 固定在 `C:/Users/admin/.codex/runtime/image2/TASK-0008`；`PYTHONDONTWRITEBYTECODE=1`、Python `-B`、pytest no cacheprovider。
  - formal evidence 只进入 `C:/Users/admin/.codex/task-state/image2/TASK-0008-*`；不写旧 `.task-runs`、旧 task-state 或历史 Completion Report。
  - validator-owned Docker project/containers/networks/volumes 和 Git worktrees/candidates/locks 必须清理，不停止或删除用户其他资源。
  - 当前 `D:/image2` 不是 Git repository，因此不要求 commit；Completion Report 必须记录 `git_commit: not_applicable`、protected scope和workspace snapshot证据。
- `external_review`: policy=never；reason=用户未要求外部模型复核，本卡以 L4 independent semantic review和真实三来源 Git/PostgreSQL/S3 evidence完成质量闭环。
- `non_completion_rules`:
  - 任一必交文件、两个正式 Validator、L4 independent review或Completion Report缺失时不得完成。
  - ConardLi 非固定 Commit全量162 cases，或aggregate/schema/files/metrics/两次确定性任一不一致时不得完成。
  - cases/mapping/file-set未一一闭合、Prompt被重写、真实路径错误、INDEX被当主权威、thumbnail入库或source claim被提升时不得完成。
  - JoeSai或g0dam frozen output、错误语义、legacy/neutral schema发生变化时不得完成。
  - registry接受unsupported/mismatched strategy、pipeline执行上游代码或parser依赖动态module name时不得完成。
  - 三来源未进入同一 fresh inventory，或528 source files、312关系、hash union、全部 object downloads、三包verified_existing、claims/rights/publication任一未闭合时不得完成。
  - 为通过第三来源而修改 registry/audit、schema/migration、inventory production code、安全/事务、compose、依赖锁或历史任务/evidence时不得完成。
  - live Git/Docker/DB/S3失败只能报告真实pending/failed；不得用 mock、fixture、TASK-0007 receipt或部分来源替代。
  - 工作区出现真实上游媒体/runtime/cache/venv/package/credentials/log，或validator-owned资源未清理时不得完成。
  - 需要同步调度、Commit更新、Canonical/rights review/publication/API/web时停止并创建后续任务。

执行时将 `CODEX_TASK_STATE_ROOT` 固定为 `C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0008/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0008/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0008/tmp`。唯一 TASK-0008 canonical run 必须记录三来源 Commit/package/schema/metrics、100/50/162-case extraction、ConardLi failure/concurrency、三来源 DB/S3 counts与全部 object hashes、三包幂等重放、rights/publication断言、cleanup、L4 independent review、最终新鲜度与 Completion Report；不得记录 secrets。
