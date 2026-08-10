---
task_contract_version: 3
card_id: "TASK-0009"
title: "纠正 ConardLi 来源契约并完成三来源库存闭环"
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
  - `D:/image2/1.md`、`config/sources-v1.yaml`、`reports/source-audit-v1.json` 与 TASK-0001/0002 已冻结的来源、权利和内容合同。
  - TASK-0003、TASK-0005、TASK-0007 已正式闭环的 g0dam legacy extraction、通用私有库存和 JoeSai neutral extraction，是不可回归的兼容基线。
  - `D:/image2/tasks/TASK-0008-conardli-compiled-manifest-and-three-source-inventory.md` 与 blocked canonical run `C:/Users/admin/.codex/task-state/image2/TASK-0008-e8e9f43e41feb38a`：任务在实现阶段如实发现两项 task-contract 事实错误，未冻结 candidate、未运行 formal Validators、未生成 Completion Report；该卡、run state、blocker evidence 只读保留。
  - TASK-0008 `source-fact-field-count-discrepancy.json`：固定 Commit `971b67dc8cbca8cf6eb32e196fea04bddd6abe99` 的 162 个 case 均精确为 16 字段，不是旧卡误写的 17 字段。
  - TASK-0008 `source-fact-newline-discrepancy.json` 与协调者复核：Windows checkout 的全局 `core.autocrlf=true` 将 162 个 Prompt 工作树文件转换为 CRLF；Git blob 全部为 LF。162/162 Git blob UTF-8文本逐字节等于 `cases.json.prompt_content`，0/162 byte-preserving worktree文本直接相等，162/162 仅做 CRLF/CR→LF 后相等。
  - 固定 Commit 真实结构：`src/data/cases.json` 顶层 `generated_at/summary/categories/templates/cases`；17 categories、79 templates、162 cases；158 JSON Prompt、4 TXT Prompt；162 PNG、162 `-thumb.webp`；`public/case/_mapping.json` 与 79/162 一一一致；`INDEX.md` 存在非权威 161 统计漂移。
  - TASK-0008 blocked run 已产生部分未冻结实现：`snapshot_files.py`、`conardli.py` 及 JoeSai/dispatch/registry/contracts 改动；本卡以当前 workspace 为新基线，授权审查、纠正、完成或重写这些部分，但不得把旧 run 的未验证代码当作通过证据。
- `decision_owner`: 用户拥有业务目标、风险和发布边界最终决定权；执行者只按本卡纠正来源合同并完成第三 pilot，不得扩大为同步、发布、API 或网页。
- `material_unknowns`:
  - fresh live run 时 GitHub、Docker、PostgreSQL 或 S3-compatible service 可能不可用；只能记录真实 pending/failed，不得复用 TASK-0007/TASK-0008 历史输出。
  - 三来源 distinct asset/object 数必须从真实 ImportPlan content-hash union求得；312 case relations 不被未经验证地等同为312 distinct hashes。
  - 当前 workspace 有一个 TASK-0008 期间生成的 `.work/source-audit/validator-pycache/validate_source_registry.cpython-312.pyc`，本卡明确授权仅删除该缓存并验证无其他 workspace cache/runtime污染。

# 2. 业务目标

- `actor`: 项目协调者、固定来源抽取系统、内部库存维护者和后续发布/API 切片实施者。
- `workflow_and_trigger`: TASK-0008 的方向正确但权威描述有两处与固定 Commit 冲突；需要新的不可变任务卡纠正 16-field shape 和 checkout newline 语义，接续未完成实现并重新建立完整 formal evidence。
- `single_outcome`: 在保留 TASK-0008 blocked 历史事实、不执行上游应用/skill、不改变 g0dam/JoeSai 输出的前提下，以真实 16-field compiled contract 和明确 newline reconciliation 完成 ConardLi 162-case strict Adapter、neutral package及三来源 312-case private inventory闭环，并形成独立 TASK-0009 complete Completion Report。
- `observable_results`:
  - `RESULT-001`: TASK-0009 canonical run/hash/receipts 与 TASK-0008 完全分离；旧 card/run/evidence 未修改，partial code按本卡重新验证而非继承通过状态。
  - `RESULT-002`: shared snapshot helper保留 JoeSai既有逻辑文本读取、path/symlink/regular-file安全与稳定错误语义；JoeSai/g0dam frozen Adapter Output、Generation Examples和metrics不变。
  - `RESULT-003`: ConardLi fixture严格证明16字段、ready整数计数、中文category label、cases/mapping/files闭合；CRLF工作树Prompt与LF manifest只在换行归一化后允许相等，任何非换行差异仍fail closed；raw_text精确使用manifest `prompt_content`。
  - `RESULT-004`: live 两次固定 Commit提取均产生162 records/Generation Examples、0 parse errors/broken assets、pair rate 1.0、audit aggregate `36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573` 和 neutral package/metrics schema。
  - `RESULT-005`: 同一 fresh inventory 中3 projects/revisions/runs、528 source files、312 cases/versions/prompts/asset sources/Generation Examples/outputs/pairings/rights、0 inputs/parse errors；assets/objects等于三份plan hash union且全部下载复核。
  - `RESULT-006`: ConardLi五故障点、same-key concurrency、三包verified_existing replay、claims/rights/publication fail-closed、runtime/Compose/cache清理、文档、L4独立审查和Completion Report全部闭合。
- `non_goals`:
  - 不修改或恢复 TASK-0008 card/run/blockers，不把其 partial implementation或source-fact文件登记为本卡validator pass。
  - 不全局修改 Git `core.autocrlf`、`ingestion/git_snapshot.py` 或用户 Git 配置；text newline reconciliation 属于静态 Adapter 文件读取边界，媒体仍按bytes处理。
  - 不执行/构建 ConardLi 前端、Node、skill 或 `references/*.md`；只读取固定 Commit 静态数据与媒体。
  - 不把thumbnail作为资产导入，不修改inventory schema/migration/production code，不实现sync/Commit更新/rights review/publication/API/web。
  - 不修改registry/audit、TASK-0002 fixtures或历史任务/evidence，不因registry model_scope自动提升case-level source claim。

# 3. 需求质疑与确认

- `user_statement`: 按确定方向持续执行，遇到真实问题严谨修正后继续，不通过降低质量或伪造证据绕过。
- `REQ-001` (`required_behavior`): acquire全新 TASK-0009 canonical run；task hash、writer、candidate cycle、receipts、independent review和report不得复用TASK-0008。旧blocked authority保持只读。
- `REQ-002` (`required_behavior`): 以当前partial workspace为新base，逐文件审查TASK-0008改动；只保留满足本卡的实现，允许在allowed scope内纠正/重写。删除精确缓存 `.work/source-audit/validator-pycache/validate_source_registry.cpython-312.pyc`，不删除其他`.work`历史证据。
- `REQ-003` (`required_behavior`): `ingestion/adapters/snapshot_files.py`只拥有固定快照root、safe path、逐组件symlink拒绝、regular-file读取和递归文件集枚举；调用方保留source-specific AdapterError类/码。UTF-8 decode failure必须经调用方data error稳定失败。
- `REQ-004` (`required_behavior`): shared text reader采用logical text semantics：将工作树CRLF和lone CR解释为LF，除此之外不trim、不NFC、不改字符；此行为与JoeSai原先`Path.read_text` universal-newline语义兼容，不引入byte-preserving raw_text承诺。
- `REQ-005` (`required_behavior`): registry只显式新增 `conardli_compiled_case_manifest_v1 → compiled_multi_category_case_gallery`，dispatch静态注册`parse_conardli_snapshot`；unsupported/mismatched strategy仍在Git/extraction side effect前拒绝。
- `REQ-006` (`required_behavior`): ConardLi主权威为`src/data/cases.json`，顶层精确字段、RFC3339 generated_at、summary/categories/templates/cases内部守恒；live固定Commit精确17 categories/79 templates/162 cases。
- `REQ-007` (`required_behavior`): category精确字段为`accent,cn,key,label,ready,templates,total`，其中`ready`与`total`均为正整数并精确等于该category实际case count；template精确字段为`cases_count,category,content,description,key,label,md_path,name`，所有键、slug、索引、归属和计数交叉一致。
- `REQ-008` (`required_behavior`): case精确使用以下16字段且不得多/少：`brief,category,category_accent,category_label,format,has_image,id,idx,image_url,prompt_content,prompt_path,prompt_url,template_key,template_label,thumb_url,title`。`category_label==category.cn`、`category_accent==category.accent`、`template_label==template.label`。
- `REQ-009` (`required_behavior`): case identity必须为`category/template-name/idx`，idx正整数、format仅json|txt、has_image=true；prompt_path/prompt_url/image_url/thumb_url由同一native id精确映射且各自唯一。
- `REQ-010` (`required_behavior`): 真实Prompt路径为`public/case/{prompt_path}`。先以UTF-8 logical text读取文件，仅统一CRLF/CR为LF后与manifest `prompt_content`精确相等；任何其他字符、空白、顺序或内容差异失败。`prompt.raw_text`直接使用manifest `prompt_content`，与固定Git blob一致；仅prompt ID使用既有normalize_prompt。
- `REQ-011` (`required_behavior`): JSON Prompt必须解析为object但不得重序列化，TXT必须非空；fixture必须显式覆盖CRLF file/LF manifest pass、非换行差异fail、invalid UTF-8稳定data error和raw_text保持LF manifest。
- `REQ-012` (`required_behavior`): 主PNG是唯一output_primary；thumbnail是非空regular `-thumb.webp`并与thumb_url一致，只保存locator，不生成asset reference/input/output/object。
- `REQ-013` (`required_behavior`): `_mapping.json`精确summary/items、item/nested字段，79/162与主清单在category/template/idx/title/brief/format/prompt_path一一对应；source_md/template_md仅安全路径元数据，不读取目标。
- `REQ-014` (`required_behavior`): `public/case` file set恰为162 Prompt+162 PNG+162 thumbnail+mapping+INDEX=488；extra/missing/non-regular/symlink失败。INDEX内容完全非权威，改变其161/162文本不得改变输出。
- `REQ-015` (`required_behavior`): record使用cases manifest locator、真实Prompt/PNG locators，pairing=`stable_native_mapping/strong`，证据精确含manifest、mapping、Prompt、PNG；ConardLi ImportPlan source_files精确326。
- `REQ-016` (`required_behavior`): prompt.language=mixed、raw_tags仅category；source claim unknown；prompt/asset rights unknown并保留review_required不等于发布授权。
- `REQ-017` (`required_behavior`): `conardli.source`只保留必要case/category/template metadata（不重复prompt_content）、manifest/mapping/thumbnail locator；mapping item不得为每条case重复保存全部siblings，可保存去除`cases`的item metadata加当前nested case。GE仅显式传播joesai/conardli non-legacy namespace，g0dam frozen GE不变。
- `REQ-018` (`required_behavior`): ConardLi package/metrics映射neutral v1；fixture覆盖JSON、TXT、idx=3并冻结expected Adapter Output/GE/metrics；offline运行全部ingestion和inventory package tests。
- `REQ-019` (`required_behavior`): live对g0dam/JoeSai/ConardLi固定Commit各完整提取两次，验证schemas/files/semantic hashes/counts/aggregates；只对新增ConardLi执行五故障点和same-key concurrency。
- `REQ-020` (`required_behavior`): 三包依次导入同一随机隔离PostgreSQL/S3；per-run不污染；global source_files=101+101+326=528，312-case关系闭合，assets/objects按hash union闭合且全部download hash复核。
- `REQ-021` (`required_behavior`): 三包replay均verified_existing且DB/S3不增长；g0dam 100 source_claimed，JoeSai50+ConardLi162 unknown；312 rights unknown；3 registry snapshots review_required/auto_publish=false；无publication decision字段。
- `REQ-022` (`required_behavior`): live使用随机Compose project、loopback ports、外部TASK-0009 runtime、无secret输出，只清理自身worktree/candidate/lock/container/network/volume和临时文件。
- `REQ-023` (`required_behavior`): 更新ConardLi extraction与internal inventory文档，明确16-field、newline authority、INDEX非权威、thumbnail非资产、neutral schema、326/528 counts及rights/publication边界。
- `REQ-024` (`required_behavior`): 完成TASK-0009 fresh validators、documentation/hygiene/freshness、L4 independent semantic review和schema-valid complete Completion Report；发现新实现缺陷必须修复后重跑失效验证，不得转用旧receipt。
- `INV-001`: 上游只做固定Commit checkout与静态读取，不install/build/import/execute其代码。
- `INV-002`: cases.json决定case identity与canonical raw prompt，mapping只做一致性证据，INDEX非权威。
- `INV-003`: newline reconciliation只允许CRLF/CR→LF；不能掩盖其他字节/字符差异。
- `INV-004`: g0dam legacy和JoeSai neutral fixtures/package/metrics/GE/error semantics不变。
- `INV-005`: package/workspace不保存真实媒体、完整上游、live packages、DB/S3状态、credentials、logs或cache。
- `INV-006`: private inventory和rights/publication fail-closed不变，不新增公开决策。
- `material_ambiguities`:
  - “raw text”在本来源有manifest logical text、Git blob bytes和Windows worktree bytes三种表示。固定Commit证据证明前两者相同，第三者仅受checkout EOL转换影响；因此本卡指定manifest/Git blob为canonical raw text，worktree文件只做newline-reconciled交叉校验。
  - 修改全局Git snapshot配置会扩大所有来源影响且不是解决语义等价的必要条件；本卡选择最小正确责任边界，不触碰用户Git设置。
- `decisions_and_authority`:
  - TASK-0008不能原地修改或resume，因为其canonical run已绑定旧hash并BLOCKED；新TASK-0009是唯一正式纠正路径。
  - partial code没有通过状态；本卡可复用代码bytes但所有claims/receipts必须fresh。

# 4. 业务场景与规则

- `SCN-001` 主路径: corrected authority → strict parse → 162 pairs → neutral package → three-source inventory → formal complete。
- `SCN-002` CRLF checkout: file logical text等于LF prompt_content；接受，raw_text保持manifest LF，output跨host确定。
- `SCN-003` 非换行Prompt差异/invalid UTF-8: 稳定失败，不发布package。
- `SCN-004` 16-field/ready/中文label漂移: exact shape或cross-index失败。
- `SCN-005` mapping/file/symlink漂移: cases.json单独有效也不得继续。
- `SCN-006` INDEX漂移: 不影响case发现、计数、identity或output。
- `SCN-007` legacy回归: JoeSai/g0dam expected bytes或错误语义变化，offline失败。
- `SCN-008` live故障/并发: ConardLi控制故障不污染，第二writer run_locked，临时状态清理。
- `SCN-009` 三来源同库: counts/hash/claims/rights/replay闭合，否则阻断。
- `SCN-010` 环境失败: validation真实pending/failed，不用mock/旧receipt代替。
- `RULE-001`: static dispatch only；不动态执行registry模块名。
- `RULE-002`: normalized newline只用于worktree cross-check；raw_text来自prompt_content，不trim/NFC/JSON rewrite。
- `RULE-003`: 四类pairing evidence均使用固定Commit真实URL，不使用TASK-0002说明性错误路径。
- `RULE-004`: package只存JSON，thumbnail不成为库存资产。
- `RULE-005`: expected fixed counts与ImportPlan-derived counts/hash union双重校验。
- `RULE-006`: TASK-0008 run/card/evidence hard protected，TASK-0009 evidence只写新run root。
- `STATE-001`: `PRECHECK → DISCOVER_AND_PLAN → IMPLEMENT_AND_DEVELOPMENT_CHECKS → FREEZE_CANDIDATE → RUN_FORMAL_VALIDATIONS → CHECK_DOCUMENTATION_AND_HYGIENE → INDEPENDENT_CHECK → FINALIZE`。
- `FLOW-001`: `fixed authority → static snapshot logical text → adapter/asset/GE/package → private inventory → formal closure`。
- `risk_sensitive_invariants`:
  - 纠正事实错误不是降低strictness；非换行差异、shape/mapping/files仍全部fail closed。
  - source-neutral helper只解决两个当前consumer共同的文件安全/文本语义，不引入未来占位抽象。
  - 三来源通过仅证明private ingestion，不构成权利、质量或公开发布批准。
- `inapplicable_faces_with_reason`:
  - Git commit：D:/image2非Git repository；以formal snapshots/hashes证明。
  - external model review：用户未要求；使用L4 independent review和真实integration。
  - API/UI/sync：超出当前inventory消费者闭环。

# 5. 当前证据与目标差异

- `FACT-001`: TASK-0008 run状态BLOCKED、generation 3，无candidate/receipts/report；两份source-fact和blockers有效保留。
- `FACT-002`: 当前partial代码已创建snapshot_files/conardli并改动JoeSai/dispatch/registry/contracts，但未有fixture/tests/live/docs或正式验证。
- `FACT-003`: partial ConardLi实现已纠正ready整数和category_label=cn，但shared reader仍采用byte-preserving newline，导致固定worktree首case失败；还需恢复logical newline语义并补完整tests。
- `FACT-004`: 当前workspace有一个新pyc cache；无其他已知runtime/media/package写入。
- `FACT-005`: 162 Git blobs与prompt_content逐字节一致，证明选择manifest raw_text没有内容降级；worktree差异完全由autocrlf line endings解释。
- `ASM-001`: 当前GitHub/Docker/PostgreSQL/S3和Windows symlink测试能力预期可用于fresh验证；任何实际不可用条件必须在TASK-0009 evidence中如实记录。
- `current_execution_path`: partial adapter尚未接通经过验证的fixture/live/inventory消费者，formal status无通过证据。
- `target_delta`: corrected code + fixtures/tests + live validator + docs + clean workspace + independent complete report。
- `evidence_gaps`: 无offline pass、无162-case live、无三来源DB/S3、无TASK-0009 review/report。

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
  - 卡内列出的ConardLi文本fixtures；测试运行时假PNG/WebP不写回仓库。
  - `scripts/validate_three_pilot_sources.py`
  - `docs/ingestion/conardli-extraction-v1.md`
  - `docs/inventory/internal-inventory-v1.md`
  - 删除精确缓存 `.work/source-audit/validator-pycache/validate_source_registry.cpython-312.pyc`。
  - `C:/Users/admin/.codex/task-state/image2/TASK-0009-*/**` formal evidence。
  - `C:/Users/admin/.codex/runtime/image2/TASK-0009/**` validator-owned runtime。
- `hard_protected_scope`:
  - TASK-0008 card及`C:/Users/admin/.codex/task-state/image2/TASK-0008-e8e9f43e41feb38a/**`。
  - `config/sources-v1.yaml`、`reports/source-audit-v1.json`、`1.md`、schemas、migrations、inventory production code、compose、pyproject/lock、`ingestion/git_snapshot.py`、g0dam adapter/fixtures、JoeSai expected fixtures、旧validators和历史任务/evidence。
  - `.work`中除上述单一pyc外的所有历史文件，用户其他Git/Docker/runtime/credentials/external systems。
- `protected_contracts_and_invariants`: TASK-0002 schemas、g0dam legacy、JoeSai neutral、inventory security/transaction/idempotency、registry/audit、rights/publication fail-closed。
- `authorization_limits`: 只允许纠正/完成声明文件与外部测试状态；不授权Git配置、外部发布、registry/audit、inventory core或历史evidence修改。
- `stop_if_scope_expands`:
  - 需要全局Git设置、git_snapshot、schema/migration/inventory core或既有fixtures变化。
  - 需要执行上游应用/skill或读取缺失reference源文件。
  - 需要改变fixed Commit/audit/rights/publication或实现thumbnail资产、sync/API/UI。

# 7. 实现蓝图

- `blueprint_status`: confirmed
- `caller_entry_consumer`: existing `pipeline.extract` → static ConardLi parser → asset resolver/contracts/package → generic `build_import_plan` → existing inventory CLI/PostgreSQL/S3。
- `expected_touchpoints_or_search_anchors`:
  - shared helper：safe root/path/symlink/files，universal-newline logical UTF-8 text与stable decode errors。
  - ConardLi parser：16 exact case fields、ready count、category.cn、manifest/mapping/file set、canonical prompt_content raw_text。
  - dispatch/registry/contracts：第三static strategy、neutral schemas、explicit joesai/conardli extension allowlist。
  - 3-case fixture/tests：JSON、TXT、idx3、CRLF/LF reconciliation、invalid UTF-8和全负例。
  - new three-source live validator和两份docs。
- `wiring_to_final_consumer`: standard package无需inventory source-specific分支即可导入；formal complete report成为下一publication/API/web任务前置。
- `failure_and_recovery`: existing Adapter/asset/pipeline/inventory owners处理错误/rollback；validator清理owned state；环境失败不complete。
- `implementation_freedom`: 可重写partial实现内部细节，但不得改变文件责任、canonical raw text、四证据、326/528 counts、legacy bytes或fail-closed边界。
- `selected_profile_obligations`:
  - public-contract: exact Adapter/GE/package identity和legacy/neutral兼容。
  - external-boundary: fixed Git paths/EOL/symlink/media、DB/S3/hash/cleanup。
  - configuration: static strategy/structure/rights/publication。
  - stateful-runtime: atomic package、single writer、transaction/replay、formal freshness。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001

- `links`: `REQ-001` 至 `REQ-005`, `INV-003`, `INV-004`
- `owns_behavior`: 新formal authority、partial代码审查、shared logical-text安全和legacy compatibility。
- `target_delta`: 消除旧卡冲突并建立可执行、可验证的新基线。
- `integration_edges`: current partial workspace → shared helper → JoeSai/ConardLi → dispatch/registry/contracts。
- `expected_touchpoints`: helper、JoeSai、ConardLi、exports、registry、contracts、compat tests、single cache cleanup。
- `linked_tests`: `TEST-001`
- `stop_conditions`: 旧evidence被改、Git配置扩大、legacy output漂移、decode/path errors失稳。

### TASK-002

- `links`: `REQ-006` 至 `REQ-018`, `INV-001` 至 `INV-005`
- `owns_behavior`: corrected ConardLi strict parser、fixtures和offline negatives。
- `target_delta`: 以真实16-field/newline contract产生确定性3-case fixture和162-case生产路径。
- `integration_edges`: cases+mapping+files → ParsedCase → resolved output → GE → metrics/package plan。
- `expected_touchpoints`: adapter、fixture files、adapter/pipeline tests。
- `linked_tests`: `TEST-002`
- `stop_conditions`: byte-preserving checkout要求复发、非换行差异被忽略、INDEX主权威、thumbnail入库或claim提升。

### TASK-003

- `links`: `REQ-019` 至 `REQ-023`, `INV-005`, `INV-006`
- `owns_behavior`: three-source live extraction/inventory与docs。
- `target_delta`: 形成100+50+162真实同库消费者证据和权威说明。
- `integration_edges`: three packages → one DB/bucket → counts/hash/claims/rights/replay → cleanup。
- `expected_touchpoints`: live validator、ConardLi doc、inventory doc。
- `linked_tests`: `TEST-003`, `TEST-004`
- `stop_conditions`: mock/旧package、非fixed source、inventory core变化、counts/hash/rights/cleanup不闭合。

### TASK-004

- `links`: `REQ-024`
- `owns_behavior`: docs/hygiene/freshness、L4 review、complete report。
- `target_delta`: 将corrected candidate和fresh evidence绑定TASK-0009终态。
- `integration_edges`: candidate+2 receipts+docs/hygiene → review → report validation。
- `expected_touchpoints`: TASK-0009 run root only。
- `linked_tests`: `TEST-005`
- `stop_conditions`: deliverable/receipt/review/freshness/report任一缺失或blocker未清。

### ASSEMBLY-001

- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`
- `end_to_end_entry`: production ConardLi extract与card-declared three-source live command。
- `shared_contract_state_data`: fixed source identity、logical prompt text、Adapter/GE/package、ImportPlans、DB/S3、rights snapshots、formal evidence。
- `final_consumer`: 后续三来源publication/API/minimal-web和Commit update slice。
- `cross_task_failure_path`: 任一Gate失败不complete；owned state清理并记录真实blocker。
- `linked_test_evidence_gate`: `TEST-001` 至 `TEST-005` / `EV-001` 至 `EV-005` / `GATE-001` 至 `GATE-005`

# 9. 验证与验收

- `consumer_chain_validation`: 必须由真实fixed snapshot经过production parser、asset resolver、GE/package和generic inventory；fixture/schema单独不足。
- `real_integration_evidence`: 三个公开fixed Commit、312完整Prompt/PNG pairs、真实random PostgreSQL/S3、全object downloads和owned cleanup。
- `failure_recovery_ownership_validation`: Adapter shape/text、asset bytes、pipeline lock/atomic publish、inventory transaction/replay和validator cleanup owner保持单一。

### RISK-001

- `links`: `REQ-001` 至 `REQ-004`, `TEST-001`
- `description`: 直接续用blocked partial代码或错误newline语义，造成false authority或legacy回归。
- `mitigation`: new run/base、explicit logical newline、fresh fixtures/receipts、old run protected。

### RISK-002

- `links`: `REQ-006` 至 `REQ-017`, `TEST-002`
- `description`: shape/mapping/files之一漂移仍生成错配pair，或newline normalization掩盖真实内容差异。
- `mitigation`: exact16 fields、dual indexes、four evidence、file set、only-EOL normalization和negative matrix。

### RISK-003

- `links`: `REQ-019` 至 `REQ-022`, `TEST-003`, `TEST-004`
- `description`: 单来源pass掩盖cross-source collision、partial import、rights提升、replay增长或资源泄漏。
- `mitigation`: one DB/bucket、plan counts/hash union、downloads、SQL assertions、three replays、scoped cleanup。

### RISK-004

- `links`: `REQ-023`, `REQ-024`, `TEST-005`
- `description`: 实现通过但docs/cache/protected scope/formal freshness不闭合。
- `mitigation`: exact docs/deliverables、workspace snapshot、independent review、official report validation。

### TEST-001

- `links`: `TASK-001`, `REQ-001` 至 `REQ-005`, `RISK-001`
- `method`: 验证new run identity和old run只读；运行g0dam/JoeSai frozen fixture equality；测试shared root/path/symlink/UTF-8 errors、CRLF logical read；验证third strategy和unsupported/mismatch pre-side-effect拒绝；确认单一pyc移除。
- `expected_observable_result`: old evidence不变、legacy bytes不变、shared safety稳定、ConardLi分发正确、workspace cache清理。
- `failure_path_covered`: stale authority、helper regression、dynamic dispatch、unsafe path、decode leak、cache污染。
- `cannot_prove`: 不证明ConardLi完整live。

### EV-001

- `for`: `TEST-001`
- `required_evidence_shape`: run/card identity、protected comparison、pytest compatibility、helper negative matrix、cache cleanup。

### TEST-002

- `links`: `TASK-002`, `REQ-006` 至 `REQ-018`, `RISK-002`
- `method`: 使用真实三条Prompt metadata（qualitative-comparison-grid/1 JSON、scientific-schematic/1 TXT、banner-hero/3 JSON idx3），fixture文件故意采用CRLF而manifest为LF，测试时生成假PNG/WebP；验证expected output/GE/metrics与contract。逐项变异16字段、ready/label、mapping、Prompt非EOL字符、invalid UTF-8、URLs/files/INDEX/symlinks。
- `expected_observable_result`: CRLF/LF accepted且raw_text=manifest LF；非EOL差异/invalid UTF-8失败；16-field/category/template/mapping/file set/thumbnail/rights/326-source-file设计闭合。
- `failure_path_covered`: old17-field assumption、ready bool、wronglabel、prompt rewrite、mapping drift、extra/missing/symlink、INDEX false authority。
- `cannot_prove`: 不证明162 live当前可取。

### EV-002

- `for`: `TEST-002`
- `required_evidence_shape`: 3-case source/expected fixtures、newline assertions、negative matrix、contract/package plan validation。

### TEST-003

- `links`: `TASK-003`, `REQ-019`, `REQ-022`, `RISK-003`
- `method`: live三来源各提取两次；验证100/50/162 counts、schemas/files/digests/aggregates、无媒体bytes；ConardLi五故障点和same-key concurrency；检查worktree/candidate/lock cleanup。
- `expected_observable_result`: 三个fixed aggregates和legacy/neutral identities精确，两次稳定，ConardLi faults不污染、second writer run_locked、临时状态清理。
- `failure_path_covered`: source/EOL/shape/media/publish drift、nondeterminism、race。
- `cannot_prove`: 不单独证明同库状态。

### EV-003

- `for`: `TEST-003`
- `required_evidence_shape`: commits/counts/schemas/aggregates、two-run hashes、fault/concurrency、Git/runtime cleanup。

### TEST-004

- `links`: `TASK-003`, `ASSEMBLY-001`, `REQ-020` 至 `REQ-022`, `RISK-003`
- `method`: random Compose中migrate twice、import three、per-run/global DB counts、528 source files、312 relations、hash union全部download、claims/rights/publication SQL、three replays前后DB/S3 snapshot和cleanup。
- `expected_observable_result`: 3 projects/revisions/runs、528 files、312 relations、0 inputs/errors；100 source_claimed+212 unknown、312 unknown rights、three verified_existing、无增长/泄漏。
- `failure_path_covered`: contamination/collision、partial import、object corruption、rights elevation、replay growth、Docker leak。
- `cannot_prove`: 不证明生产环境/未来Commit/公开授权。

### EV-004

- `for`: `TEST-004`
- `required_evidence_shape`: Docker/loopback、migration/import/inspect counts、source-file/hash union/downloads、SQL assertions、replays、cleanup。

### TEST-005

- `links`: `TASK-004`, `REQ-023`, `REQ-024`, `RISK-004`
- `method`: docs/deliverables/workspace/protected/hygiene检查；candidate/terminal snapshots、deterministic evidence、L4 independent review、complete report official validation。
- `expected_observable_result`: docs与corrected contract/live一致，workspace无cache/runtime/media/secrets，review findings=0，2/2 receipts、22/22 deliverables、0 blockers、run COMPLETE。
- `failure_path_covered`: doc drift、foreign/stale receipt、scope污染、false report completion。
- `cannot_prove`: 不证明后续功能。

### EV-005

- `for`: `TEST-005`
- `required_evidence_shape`: documentation/hygiene/protected/freshness、deterministic bundle、semantic review、Completion Report+official validation。

### 正式 Validator Manifest

```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "corrected-conardli-three-source-offline",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "tests/ingestion", "tests/inventory/test_package.py", "-q"],
      "cwd": ".",
      "timeout_seconds": 420,
      "invalidation_paths": ["1.md", "config/sources-v1.yaml", "reports/source-audit-v1.json", "schemas/adapter-output-v1.schema.json", "schemas/generation-example-v1.schema.json", "docs/contracts/content-contract-v1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory/package.py", "tests/ingestion", "tests/inventory/test_package.py", "fixtures/adapters/g0dam-work-prompts", "fixtures/adapters/joesai-commercial-prompts", "fixtures/adapters/conardli-gpt-image-2-101", "docs/ingestion/g0dam-extraction-v1.md", "docs/ingestion/joesai-extraction-v1.md", "docs/ingestion/conardli-extraction-v1.md", "docs/inventory/internal-inventory-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import pytest, jsonschema, psycopg, boto3; print('ready')"],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "corrected-conardli-three-source-compose-live",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_three_pilot_sources.py", "--registry", "config/sources-v1.yaml", "--audit", "reports/source-audit-v1.json", "--g0dam-source-id", "g0dam-work-prompts", "--g0dam-expected-commit", "690c2d6969a65b406b17ba7d41f18695a652c3fe", "--g0dam-expected-cases", "100", "--g0dam-expected-aggregate", "ba7dbf0154f4d77317ec4a2b5044fbd6b3ef80ffb06b7ecacd2655dcfae8dbf0", "--joesai-source-id", "joesai-commercial-prompts", "--joesai-expected-commit", "6f9b01fd21efbc05cfdde1176fc988013d3c4a9b", "--joesai-expected-cases", "50", "--joesai-expected-aggregate", "ea242f29b82c8149e43132d208cc67ae55c49cbb3d19ed80b2c3d2676e943293", "--conardli-source-id", "conardli-gpt-image-2-101", "--conardli-expected-commit", "971b67dc8cbca8cf6eb32e196fea04bddd6abe99", "--conardli-expected-cases", "162", "--conardli-expected-aggregate", "36d03d248e8a844fa31db4290f395acbcd37c1c25ce9205d634cace4d7c8e573", "--runs", "2", "--failure-injection", "--concurrency", "--json"],
      "cwd": ".",
      "timeout_seconds": 3600,
      "invalidation_paths": ["1.md", "config/sources-v1.yaml", "reports/source-audit-v1.json", ".task-runs/TASK-0001", "schemas/adapter-output-v1.schema.json", "schemas/generation-example-v1.schema.json", "docs/contracts/content-contract-v1.md", "pyproject.toml", "uv.lock", "ingestion", "inventory", "migrations", "compose.yaml", "scripts/validate_three_pilot_sources.py", "fixtures/adapters/g0dam-work-prompts", "fixtures/adapters/joesai-commercial-prompts", "fixtures/adapters/conardli-gpt-image-2-101", "docs/ingestion/g0dam-extraction-v1.md", "docs/ingestion/joesai-extraction-v1.md", "docs/ingestion/conardli-extraction-v1.md", "docs/inventory/internal-inventory-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": true,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import psycopg, boto3, jsonschema; print('python-ready')"],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | corrected authority与legacy | `TASK-001` / `TEST-001` | new run、old run只读、logical text和JoeSai/g0dam compatibility通过 | `EV-001` | 不证明162 live |
| `GATE-002` | corrected ConardLi mapping | `TASK-002` / `TEST-002` | 16 fields、newline reconciliation、mapping/files/negative matrix闭合 | `EV-002` | 不证明完整来源当前可取 |
| `GATE-003` | three fixed extractions | `TASK-003` / `TEST-003` | 100/50/162、schemas/aggregates/two runs/fault/concurrency通过 | `EV-003` | 不证明同库 |
| `GATE-004` | three-source inventory | `TASK-003` / `ASSEMBLY-001` / `TEST-004` | 3 runs/528 files/312 relations/hash union/replays/rights/cleanup闭合 | `EV-004` | 不证明公开授权 |
| `GATE-005` | formal closure | `TASK-004` / `TEST-005` | docs/hygiene/freshness/review/2 receipts/22 deliverables/report完整 | `EV-005` | 不证明后续API/UI/sync |

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

- `documentation_impact`: updated；新增corrected ConardLi extraction说明并把inventory文档更新为三来源，明确16 fields、manifest/Git blob canonical raw text、checkout newline reconciliation、INDEX非权威、thumbnail非资产、326/528 counts和rights/publication边界。
- `repository_hygiene_requirement`:
  - workspace只保存声明代码/测试/文本fixture/docs；无真实PNG/WebP、完整上游、package、DB/S3、Compose env、credentials、logs、pyc/cache/venv。
  - 精确删除TASK-0008生成的单一pyc；不触碰其他`.work`历史文件。
  - `UV_PROJECT_ENVIRONMENT`、`UV_CACHE_DIR`、`TMP/TEMP`和Git/output固定`C:/Users/admin/.codex/runtime/image2/TASK-0009`；`PYTHONDONTWRITEBYTECODE=1`、Python `-B`、pytest no cacheprovider。
  - formal evidence只写`C:/Users/admin/.codex/task-state/image2/TASK-0009-*`；old task states hard protected。
  - owned Docker/Git/runtime资源必须清理，不触碰用户其他状态。
  - D:/image2非Git repo，Completion Report记录`git_commit: not_applicable`及snapshot/protected证据。
- `external_review`: policy=never；reason=用户未要求外部模型；L4 independent semantic review和真实三来源Git/DB/S3足以完成本卡闭环。
- `non_completion_rules`:
  - 任一22个deliverables、2 validators、L4 review或Completion Report缺失不得完成。
  - 旧TASK-0008 card/run/evidence被修改或receipt被复用不得完成。
  - 16-field、ready count、category.cn、newline-only reconciliation、canonical raw_text任一不符合不得完成。
  - 非换行差异/invalid UTF-8未fail closed，或INDEX被当权威、thumbnail入库、claim/rights提升不得完成。
  - g0dam/JoeSai frozen output/schema/error semantics变化不得完成。
  - ConardLi非fixed162 cases/audit aggregate/two runs，或三来源未同库528/312/hash/replay/rights闭合不得完成。
  - 修改Git配置/git_snapshot、registry/audit、schema/migration/inventory core、dependencies/history evidence不得完成。
  - live环境失败只能真实pending/failed；不得mock/旧receipt/partial source替代。
  - workspace cache/runtime/media/package/secrets/log或owned Docker/Git资源残留不得完成。
  - 需要sync/Commit update/rights review/publication/API/web时另建任务。

执行时将 `CODEX_TASK_STATE_ROOT=C:/Users/admin/.codex/task-state/image2`；`UV_PROJECT_ENVIRONMENT=C:/Users/admin/.codex/runtime/image2/TASK-0009/venv`、`UV_CACHE_DIR=C:/Users/admin/.codex/runtime/image2/TASK-0009/uv-cache`、`TMP/TEMP=C:/Users/admin/.codex/runtime/image2/TASK-0009/tmp`。唯一TASK-0009 canonical run必须记录corrected contract、三来源Commit/package/schema/metrics、100/50/162 extraction、ConardLi failure/concurrency、三来源DB/S3 counts/object hashes/replays、rights/publication、cleanup、L4 review、freshness和Completion Report；不得记录secrets。
