---
task_contract_version: 3
card_id: "TASK-0019"
title: "接入Phase 2三项长期内容源并扩展多输出案例闭环"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "stateful-runtime"
  - "external-boundary"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户确认长期方向为“稳定固定高价值、可提取提示词与对应图片的项目作为长期内容源”；`1.md`当前产品架构；TASK-0018 Completion Report与`reports/phase2/source-discovery-v1.json`、`reports/phase2/source-discovery-v1.md`、`docs/phase2/source-expansion-admission-v1.md`确认的三项adapter-ready来源；当前ingestion、inventory、sync、Content/API/Web实现与测试。
- `decision_owner`: 用户拥有长期来源方向、内部收录目标及未来人工rights/publication决定；本卡只授权固定Commit内部接入与验证，不授权公开发布、部署或法律结论。
- `material_unknowns`: 无阻断性未知。三来源固定Commit、结构、数量和rights边界已由TASK-0018验证；具体字段解析细节必须以对应固定Commit静态结构为准并由全量提取验证，不能依赖仓库未来HEAD。

# 2. 业务目标
- `actor`: 项目维护者、内容审核者及后续长期同步执行者。
- `workflow_and_trigger`: 维护者为TASK-0018准入的三个固定来源运行统一提取/库存/同步流程时，系统按各自静态结构解析全部提示词与本地图像，保留一个提示词案例对应多张输出图的真实关系，稳定写入内部库存并继续禁止未经审核的公开内容。
- `single_outcome`: 将`freestylefly`、`erickkkyt`、`VigoZhao`三个高价值项目从“已准入、未接入”升级为可独立启停、可审计、可重复同步、可回滚的长期内部内容源，使当前内部来源从3个增至6个、提示词案例从312增至1513，并完整保存新来源1618个输出图关系。
- `observable_results`:
  - `RESULT-001`: 新增三个独立静态Adapter，分别绑定TASK-0018确认的固定Commit与结构，完整解析517、572、112个提示词案例；不得漏掉或合并来源案例。
  - `RESULT-002`: 新三源分别解析517、877、224个输出引用，共1618个；多图案例保持一个`source_case_key`和一个Prompt文档，但每个输出都有独立、可追溯、强配对的Generation Example。
  - `RESULT-003`: 共享提取边界从“每案恰好一个资产”升级为“每案一个或多个显式资产引用”，旧三Adapter的一案一图输出、稳定ID、package identity和现有fixtures保持兼容。
  - `RESULT-004`: `reports/source-audit-v1.json`与`config/sources-v1.yaml`吸收TASK-0018已确认事实，三来源成为canonical active、selected、sync enabled、full ingestion；所有prompt/asset仍`review_required`且`auto_publish=false`。
  - `RESULT-005`: 六来源全链路提取后，内部库存精确为1513 source cases、1513 prompt records、1930 Generation Examples和1930 generation output links；跨来源相同图片仍按内容哈希去重资产对象，因此不把1930误写为必须不同的asset object数量。
  - `RESULT-006`: 三新来源可分别首轮同步、同Commit重放、单源失败后恢复、独立禁用；任一来源失败不发布部分package、不破坏其既有ready revision，也不改变其他来源状态。
  - `RESULT-007`: 真实人工rights批准仍为0，Content publication、Public API和Public Web真实公开案例仍为0；内部1513不等于公开1513。
  - `RESULT-008`: 全量固定Commit验证、全仓回归、最新migration下inventory/sync/Content/API/Web消费者验证、文档同步、workspace hygiene和L4独立复核全部闭合。
- `non_goals`: 不新增TASK-0018以外来源；不跟随仓库HEAD；不实现scheduler、管理后台或部署；不进行人工rights批准或公开发布；不改变Public API/Web选择已完成Publication Version的规则；不新增数据库migration；不修复Mageia等未准入来源。

# 3. 需求质疑与确认
- `user_statement`: Skill项目本身无需关注，应稳定固定高价值案例多、能提取对应图片与提示词的项目作为长期内容来源，并持续按该方向推进。
- `REQ-001` (`required_behavior`): 三来源必须分别使用`freestylefly_cases_json_v1`、`erickkkyt_prompts_json_v1`、`vigo_style_directory_v1`，仅解析固定Commit中的静态数据和资产，不执行来源代码、不请求运行时外部图片。
- `REQ-002` (`required_behavior`): 固定Commit必须精确为`76fcd0e6b3961ef2b041547aac654f1efd1ef270`、`1b5ec5f4f3409d2bf4cd2a4741070ce6c1429c6a`、`9fa17042b392db28bb495f7208d37f1b9c416368`；commit、repository identity或结构漂移必须fail closed。
- `REQ-003` (`required_behavior`): Adapter必须对完整固定数据集做确定性解析并验证唯一native identity、非空实质提示词、安全相对路径、资产存在/魔数/大小、显式Prompt-输出关系及完整文件覆盖；不得随机抽取、按目录顺序猜配或静默跳过异常记录。
- `REQ-004` (`required_behavior`): 共享`ParsedCase`与资产解析接口必须显式携带`asset_ref_id → source_path`关系；不得继续依赖单一`image_path`或仅靠数组位置隐式绑定。
- `REQ-005` (`required_behavior`): 一个案例可拥有多个输出引用；解析结果必须把第一项稳定标为`output_primary`、其余稳定标为`output_secondary`，并为每个输出生成独立pairing和Generation Example；输出ID从稳定case identity与稳定asset reference派生。
- `REQ-006` (`required_behavior`): `generation-example/v1`现有多asset/多generation能力优先复用；除非实现证据证明无法表达，否则不得升级schema version或新增migration。每个output asset必须且只能被同文档一个Generation Example消费。
- `REQ-007` (`required_behavior`): 保持旧三来源100/50/162案例和312个Generation Examples不变；现有单输出fixtures、语义摘要、idempotency与同步行为不得漂移。
- `REQ-008` (`required_behavior`): 更新source audit/registry及语义validator，使六个active canonical来源都有一致的source_id、repository_id、fixed Commit、structure、adapter、rights与audit绑定；TASK-0018报告继续作为新三源事实上游，不改写其原始结论。
- `REQ-009` (`required_behavior`): 三新源Adapter必须分别可dispatch、可配置启停、可单独提取与同步；禁用一源不得影响另外五源，unknown strategy和结构不匹配继续fail closed。
- `REQ-010` (`required_behavior`): 全量固定Commit运行必须证明517/572/112案例和517/877/224输出引用；重复运行产生相同case keys、prompt IDs、asset references、semantic digest和package identity。
- `REQ-011` (`required_behavior`): inventory/sync导入必须支持一案多generation输出，首轮与同Commit重放幂等；失败注入、锁冲突、已发布package冲突和恢复路径不得留下半成品、错误ready状态或workspace内运行残留。
- `REQ-012` (`required_behavior`): rights始终fail closed；新三源的Prompt、Asset和生成关系只进入内部Source/Evidence/Inventory，不自动创建真实Completed Publication Version，不进入API/Web公开列表。
- `REQ-013` (`required_behavior`): 文档必须明确6来源、1513内部提示词案例、1930输出关系、0真实公开、未部署，以及下一步是人工rights审核/来源更新运营而不是继续寻找Skill项目。
- `REQ-014` (`required_behavior`): 完成全仓offline、三源全量真实fixed-Commit live、六源inventory/sync及Content/API/Web消费者live、scope/hygiene/freshness、L4独立review和唯一Completion Report；本目录非Git，不创建commit。
- `INV-001`: Source/Evidence、rights decision、Publication、API/Web四层责任不合并；来源可接入不等于允许公开。
- `INV-002`: 稳定ID必须由固定来源identity和原生结构派生；同Commit重跑不依赖下载目录、时间、数组遍历偶然顺序或数据库自增ID。
- `INV-003`: 一个提示词案例在source/inventory中只出现一次；多输出只增加该案例内的Generation Examples/outputs，不复制Prompt/source case。
- `INV-004`: 每个asset reference都有唯一强pairing、固定来源位置和解析后的内容SHA-256；无配对、缺图、路径逃逸、HTML载荷、重复引用或不支持格式必须fail closed。
- `INV-005`: 六来源任一同步失败时，其他来源的ready/current状态和已发布package不回退；失败源可从上一个一致状态重试。
- `INV-006`: 旧三来源及Phase 1 closure事实保持有效：312 internal、0 public、未部署；新事实在其上增量扩展，不改写历史证据。
- `material_ambiguities`: TASK-0018的`unique_valid_case_count`统计逻辑提示词案例，而`image_reference_count`统计输出图。现有单图实现不能表达Erick 572→877和Vigo 112→224；本卡确认采用“一案例文档、多独立Generation Example”的兼容模型，不拆成重复source case，也不丢弃次要图片。
- `decisions_and_authority`: 该模型由现有`generation-example/v1`允许多assets与多generation、inventory按文档内generation计数的仓库事实，以及用户要求完整提取图片与提示词共同确定；未来若要改变公开呈现方式需另卡决定。

# 4. 业务场景与规则
- `SCN-001` 单输出主路径: freestylefly案例解析一个Prompt与一个primary输出，生成一个Generation Example并稳定导入。
- `SCN-002` 多输出主路径: Erick/Vigo案例解析一个Prompt与N个显式输出，生成同一案例文档内N个资产和N个独立Generation Examples，所有pairing闭合。
- `SCN-003` 重复执行: 同一固定Commit重复提取/同步返回verified existing或no-op，case/generation/output计数和digest不变。
- `SCN-004` 来源结构失败: 缺字段、重复native ID、未知多图项、孤立文件、资产缺失/损坏/逃逸、重复asset ref或关系不闭合时，不发布该来源package。
- `SCN-005` 状态恢复: 在adapter后、asset后、manifest前、replace前或inventory transaction中失败，清理temporary/lock并保留上次ready revision；修正环境后可安全重试。
- `SCN-006` 单源控制: 将任一新来源改为非active或sync disabled后，其运行被拒绝/跳过，其他来源仍可独立运行且已有库存不被隐式删除。
- `SCN-007` rights/public边界: 六源内部库存可查询，但没有真实人工approval时Publication/API/Web结果仍为0。
- `RULE-001`: 案例数按唯一Prompt/source case计；输出关系数按Generation Example/output link计；asset object数按内容哈希去重，三种数量不得混称。
- `RULE-002`: 第一输出的选择必须由来源结构中的稳定顺序或明确变体规则决定并写入Adapter测试；若来源结构无法给出稳定规则则阻断而非猜测。
- `RULE-003`: 全量计数是固定Commit合同：freestylefly `517 cases/517 outputs`、erickkkyt `572/877`、Vigo `112/224`；任何漂移先视为结构/authority变化，不自动接受新HEAD。
- `RULE-004`: source audit与registry只能采用TASK-0018已验证的事实；rights未知或license缺失不得被推导为可公开。
- `STATE-001`: adapter-ready probation → audit/registry active internal → fixed-Commit package published → inventory revision ready → sync completed；publication仍为空。
- `FLOW-001`: registry+audit → fixed Git snapshot → source Adapter → explicit asset resolution → Adapter Output → Generation documents → atomic package → inventory import → sync report → Content/API/Web consumer validation。
- `risk_sensitive_invariants`: `INV-001`至`INV-006`、multi-output reference closure、fixed-Commit identity、transaction/idempotency、cross-source isolation、rights/publication fail-closed。
- `inapplicable_faces_with_reason`: 不含账户权限、支付、用户输入或线上外部写；外部边界仅只读Git固定Commit及本地测试基础设施；不需数据库migration，因为当前表和文档合同已支持一个source case对应多个generation rows。

# 5. 当前证据与目标差异
- `FACT-001`: `reports/phase2/source-discovery-v1.json`的`adapter_ready_batch`确认三来源、固定Commit、推荐Adapter与1201唯一有效案例；full audits确认输出引用为517、877、224且pair rate均1.0。
- `FACT-002`: 当前`ingestion/adapters/__init__.py`与`ingestion/registry.py`只支持Phase 1三种Adapter；新三源无法进入真实执行路径。
- `FACT-003`: 当前`ParsedCase.image_path`、pipeline的`assets_by_case_key`、`resolved_adapter_output`和`generation_example_for`强制一案一图；schema与inventory实际上已允许一个文档包含多个assets和多个Generation Examples。
- `FACT-004`: 当前`reports/source-audit-v1.json`有freestylefly/Vigo旧probation记录但缺TASK-0018完整事实，Vigo仍是旧Commit；Erick未进入Phase 1 registry authority。`config/sources-v1.yaml`尚未将三源全部active。
- `FACT-005`: 当前Content Contract fixture manifest及source registry validator硬编码三pilot；扩展生产来源时必须把“Phase 1兼容fixtures”与“当前active source集合”分开，不能要求每个active来源都成为旧fixture manifest pilot。
- `FACT-006`: inventory database按adapter records计source cases/prompt records，按Generation documents内数组计generation rows/outputs；因此无需migration即可保持1201案例并导入1618新generation outputs。
- `FACT-007`: TASK-0018正式状态已complete且独立review无Blocking/Major；所有新来源仍`review_required`、`auto_publish=false`，Phase 1保持312 internal/0 public。
- `ASM-001`: 固定Commit源结构与TASK-0018全量ledger一致；执行时必须通过真实全量验证确认，若不一致则停止而非调整期望数量。
- `current_execution_path`: 三个旧Adapter可由registry驱动完成fixed snapshot→package→inventory→sync；新三源停留在发现报告，且共享资产映射无法处理多输出。
- `target_delta`: 以最小共享边界扩展multi-output能力，新增三个source-specific Adapter并把其接入现有六源内部同步闭环；不改变数据库和公开层合同。
- `evidence_gaps`: 新Adapter/fixtures/tests、multi-output共享合同回归、source audit/registry集成、三源全量live、六源inventory/sync totals、消费者0-public、文档、hygiene、独立review和Completion Report。

# 6. 范围与责任边界
- `allowed_write_scope`: `ingestion/adapters/`、`ingestion/assets.py`（仅共享资产引用解析确有需要时）、`ingestion/contracts.py`、`ingestion/pipeline.py`、`ingestion/registry.py`、`config/sources-v1.yaml`、`reports/source-audit-v1.json`、相关source/content schemas与validators、`fixtures/`中的小型固定结构测试夹具、`tests/ingestion/`、`tests/inventory/`、`tests/sync/`、必要的Content/API/Web回归测试、`scripts/`中的本卡validator、`docs/ingestion/`、`docs/inventory/`、`docs/sync/`、`docs/phase2/`、`1.md`、本卡formal evidence root。
- `hard_protected_scope`: 数据库migration与生产表语义；TASK-0018报告/receipts/Completion Report原始字节；Phase 1 fixed source Commit与历史formal evidence；真实rights审批/Publication数据；API/Web公开选择规则；未准入候选和外部仓库；workspace外持久mirror中其他来源数据。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`；generation-example/v1向后兼容；Phase 1旧fixtures与312计数；atomic package publication；inventory transaction/idempotency；sync current/previous revision规则；0真实公开。
- `authorization_limits`: 用户已授权继续执行本项目既定长期来源路线；本卡将实施权限限定为仓库内代码/配置/文档/测试和本地验证状态，本卡不构成外部仓库写入、线上部署、rights决定、批量删除既有库存或改用TASK-0018清单外Commit的额外授权。
- `stop_if_scope_expands`: 若必须新增migration、改变Public API schema/网页产品行为、修改TASK-0018事实、接入第四来源、采用非固定外部资产或作人工rights判断，停止并创建独立任务卡。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: extraction CLI/sync pipeline读取source registry并选择Adapter；Adapter向Content Contract提供source cases与显式asset refs；inventory导入Generation documents；Content/API/Web只消费已完成Publication Version。
- `expected_touchpoints_or_search_anchors`: `ingestion/adapters/base.py::ParsedCase`、三个现有Adapter构造点、`ingestion/adapters/__init__.py::adapter_for_strategy`、`ingestion/pipeline.py::extract`、`ingestion/contracts.py::{resolved_adapter_output,generation_example_for,generation_examples,extraction_metrics}`、`ingestion/registry.py::SUPPORTED_ADAPTER_STRUCTURES`、`scripts/validate_content_contracts.py`、`scripts/validate_source_registry.py`、`inventory/package.py`、`inventory/database.py`、`sync/pipeline.py`。
- `wiring_to_final_consumer`: source-specific parser输出`source_case_key + prompt + ordered explicit asset refs`；共享pipeline逐ref读取资产事实；contract按ref闭合并生成一个case document内N个generation；inventory按现有transaction写入；sync记录来源revision；public消费者继续因无approval返回0。
- `failure_and_recovery`: Adapter与asset解析fail closed；candidate package只在全部记录/资产/合同通过后原子替换；inventory单transaction；same-key锁和semantic conflict拒绝；失败清理temporary/lock且不改变上次ready/current；单源恢复通过重跑同Commit完成。
- `implementation_freedom`: 可选择共享asset-binding数据类和Adapter内部辅助函数，但必须显式以asset_ref identity连接路径与合同；不得依赖数组zip的未验证位置关系。可为旧`ParsedCase.image_path`提供短期只读兼容属性，若这样能减少风险，但最终执行路径必须使用多ref接口。
- `selected_profile_obligations`:
  - `public-contract`: 当前合同是每record恰好一个asset且每document一个generation；目标合同是一record一个或多个显式assets、一document一个或多个独立generation，旧单图序列化完全兼容；错误语义覆盖缺ref、重复ref、未解析ref、dangling pairing和重复output消费；contract tests覆盖旧/新消费者。
  - `stateful-runtime`: authority为source registry+audit+fixed Commit与published package/inventory revision；覆盖candidate→published→ready→sync completed、并发锁、same-commit replay、冲突、partial failure、previous/current保持和单源隔离。
  - `external-boundary`: 只读Git snapshot必须固定repository identity/Commit并在workspace外；覆盖clone/fetch错误、timeout、结构漂移、路径/符号链接、异常资产、无凭据泄漏、可复核full-run receipt和mirror/runtime cleanup。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-004`至`REQ-007`, `INV-002`至`INV-004`
- `owns_behavior`: 共享一案多输出解析、资产解析、合同映射、metrics与旧单图兼容。
- `target_delta`: 从单一`image_path`/单asset限制到显式多asset refs，并在一个case document内生成逐输出强配对Generation Examples。
- `integration_edges`: Adapter ParsedCase → asset reader → Adapter Output → Generation Example documents → inventory package。
- `expected_touchpoints`: base/assets/contracts/pipeline、content-contract validator与共享tests。
- `business_result`: 新来源的多张图不会被丢弃或复制成伪案例，旧来源行为不变。
- `behavior_faces`: normal=1或N outputs；boundary=最大实测多图记录；failure=缺/重复/dangling refs与相同内容重复；empty=无输出拒绝；repeated=stable serialization；downstream=inventory counts。
- `state_change`: parsed → all assets resolved → contract valid；任一资产失败则整源candidate不发布。
- `data_flow`: ordered ref bindings + file bytes → asset facts → per-ref resolved records → one case document/N generation rows。
- `integration_point`: caller=pipeline；callee=assets/contracts；return=adapter output+generation docs+metrics；consumer=package/inventory/sync。
- `scope_boundary`: 不改schema version、migration或公开消费者规则。
- `allowed_write_scope`: section 6中共享ingestion/contracts/validator/tests部分。
- `acceptance_scenarios`: `SCN-001`至`SCN-005`。
- `linked_tests`: `TEST-001`, `TEST-002`
- `stop_conditions`: 需要migration或无法保持旧fixtures/digests兼容。

### TASK-002
- `links`: `OBJ-001`, `REQ-001`至`REQ-003`, `REQ-005`, `REQ-009`, `REQ-010`, `INV-002`至`INV-004`
- `owns_behavior`: freestylefly固定Commit Adapter与517/517完整解析。
- `target_delta`: `data/cases.json`与`data/images/`成为可独立提取的长期来源。
- `integration_edges`: fixed snapshot → freestyle parser → shared multi-output boundary → package。
- `expected_touchpoints`: 新Adapter、dispatch/registry mapping、source fixture/unit/full-run tests。
- `business_result`: 新增517个稳定内部提示词案例。
- `behavior_faces`: normal=完整517；failure=manifest/count/id/path/orphan/asset异常；repeated=stable IDs/digest；downstream=inventory/sync。
- `state_change`: probation adapter-ready → active internal source。
- `data_flow`: structured JSON record → Prompt+one image ref+provenance/extensions。
- `integration_point`: caller=adapter dispatch；callee=shared parser/assets；consumer=contract/package。
- `scope_boundary`: 只解析固定结构，不泛化为任意JSON Adapter。
- `allowed_write_scope`: section 6中freestyle相关代码/config/audit/fixtures/tests/docs。
- `acceptance_scenarios`: `SCN-001`, `SCN-003`至`SCN-007`。
- `linked_tests`: `TEST-003`, `TEST-006`
- `stop_conditions`: 固定Commit全量计数或结构与TASK-0018不一致。

### TASK-003
- `links`: `OBJ-001`, `REQ-001`至`REQ-005`, `REQ-009`至`REQ-012`, `INV-001`至`INV-005`
- `owns_behavior`: Vigo固定Commit Adapter与112/224完整解析。
- `target_delta`: `styles/*/style.json`及两个固定比例preview成为112个一案双输出的长期来源。
- `integration_edges`: style directory → deterministic aspect ordering → shared multi-output boundary → package。
- `expected_touchpoints`: 新Adapter、dispatch/registry mapping、source fixture/unit/full-run tests。
- `business_result`: 新增112个提示词案例并完整保留224张横竖预览图。
- `behavior_faces`: normal=每style双输出；failure=缺style/preview、孤立目录、重复style ID、比例文件异常；repeated=stable variant IDs；downstream=inventory/sync。
- `state_change`: 旧probation/旧Commit → TASK-0018 fixed Commit active internal。
- `data_flow`: style.json Prompt → `preview-16x9` primary + `preview-9x16` secondary → two pairings/generations。
- `integration_point`: caller=adapter dispatch；callee=shared multi-output；consumer=contract/package。
- `scope_boundary`: 不把风格配置解释为公开许可或通用模板执行。
- `allowed_write_scope`: section 6中Vigo相关代码/config/audit/fixtures/tests/docs。
- `acceptance_scenarios`: `SCN-002`至`SCN-007`。
- `linked_tests`: `TEST-004`, `TEST-006`
- `stop_conditions`: 固定Commit不是112 styles/224 previews或稳定变体规则不成立。

### TASK-004
- `links`: `OBJ-001`, `REQ-001`至`REQ-005`, `REQ-009`至`REQ-012`, `INV-001`至`INV-005`
- `owns_behavior`: erickkkyt固定Commit Adapter与572/877完整解析。
- `target_delta`: `prompts/prompts.json`与本地assets成为572个多输出提示词案例的长期来源。
- `integration_edges`: structured prompts/image lists → stable per-image refs → shared multi-output boundary → package。
- `expected_touchpoints`: 新Adapter、dispatch/registry mapping、source fixture/unit/full-run tests。
- `business_result`: 新增572个提示词案例并完整保留877张输出图，不把license缺失误判为可公开。
- `behavior_faces`: normal=单/多图混合；failure=空列表、重复/未知图片、孤立资产、重复native ID、结构漂移；repeated=filename/identity稳定；downstream=inventory/sync。
- `state_change`: discovered adapter-ready → active internal source。
- `data_flow`: prompt record → one Prompt + ordered local image refs → N pairings/generations。
- `integration_point`: caller=adapter dispatch；callee=shared multi-output；consumer=contract/package。
- `scope_boundary`: repository license保持unknown/NOASSERTION语义，绝不推导公开权利。
- `allowed_write_scope`: section 6中Erick相关代码/config/audit/fixtures/tests/docs。
- `acceptance_scenarios`: `SCN-002`至`SCN-007`。
- `linked_tests`: `TEST-005`, `TEST-006`
- `stop_conditions`: 固定Commit不是572 prompts/877 refs或存在无法稳定消歧的关系。

### TASK-005
- `links`: `OBJ-001`, `REQ-008`至`REQ-014`, `INV-001`至`INV-006`
- `owns_behavior`: 六来源audit/registry激活、inventory/sync装配、公开边界与文档闭合。
- `target_delta`: 三个孤立Adapter能力成为六来源可运营内部闭环，并有精确数量与恢复证据。
- `integration_edges`: audit/registry → dispatch → extraction packages → inventory revisions → sync reports → Content/API/Web。
- `expected_touchpoints`: source audit/registry/schema/validators、inventory/sync integration tests、final validator、docs/`1.md`。
- `business_result`: 项目拥有6个稳定长期来源、1513个内部提示词案例、1930个输出关系，公开仍由人工审核控制。
- `behavior_faces`: normal=六源完整；boundary=0 public与asset hash dedupe；failure=单源/transaction/lock/conflict；permission=rights fail closed；repeated=six-source replay；downstream=Content/API/Web 0。
- `state_change`: 三源active config → package/import/sync complete；失败源保持旧一致状态。
- `data_flow`: TASK-0018 facts + source runtime outputs → audit/registry → DB totals/sync receipts → docs/report。
- `integration_point`: caller=maintainer/final validator；callee=ingestion/inventory/sync/content/api/web validators；consumer=长期运营与下一任务。
- `scope_boundary`: 无deployment、scheduler、rights approval或第四来源。
- `allowed_write_scope`: section 6中集成、validator和文档部分。
- `acceptance_scenarios`: `SCN-003`至`SCN-007`。
- `linked_tests`: `TEST-006`, `TEST-007`, `TEST-008`
- `stop_conditions`: 需要改数据库/public contract、真实public非0、Phase 1回归漂移或scope超出。

### ASSEMBLY-001
- `participating_tasks`: `TASK-001`, `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`
- `end_to_end_entry`: `scripts/validate_phase2_adapters.py --json`从六来源registry/audit和三个新来源固定Git Commit启动完整提取、库存、同步与消费者验证。
- `shared_contract_state_data`: fixed repository/Commit/adapter identity、source_case_key、Prompt ID、显式asset_ref binding、逐输出pairing、asset SHA-256、Generation document、package idempotency/semantic digest、inventory revision、sync current/previous、rights snapshot和Publication状态。
- `final_consumer`: 长期内容源维护者、内部内容审核者，以及只读取Completed Publication Version的Content/Public API/Public Web消费者。
- `cross_task_failure_path`: 共享multi-output合同失败时三个新Adapter不得启用；任一source-specific全量计数或关系失败时该源不得active/import；package、inventory或sync失败由TASK-005保持旧一致状态并隔离其他来源；public边界失败时整卡不得完成。
- `linked_test_evidence_gate`: `TEST-006`, `TEST-007`, `TEST-008` / `EV-006`, `EV-007`, `EV-008` / `GATE-003`, `GATE-004`, `GATE-005`

# 9. 验证与验收

- `consumer_chain_validation`: 必须从真实固定Commit执行到inventory/sync，并在最新migration上运行Content Core、Public API和Public Web验证；只跑Adapter unit不能证明长期来源已接入最终消费者。
- `real_integration_evidence`: 三来源全量只读Git固定Commit；六来源本地Postgres/对象存储/同步运行；Content/API/Web真实0-public验证；所有runtime目录在workspace外并可清理。
- `failure_recovery_ownership_validation`: Adapter/asset/contract失败不发布candidate；inventory transaction回滚；sync保留previous/current；每项失败由对应TASK测试并在ASSEMBLY中至少验证一个单源恢复。

### RISK-001
- `description`: 为追求数量把多张图拆成重复Prompt案例，会扭曲1513案例口径、搜索质量与长期去重。
### RISK-002
- `description`: 共享单图合同升级可能改变旧三源stable package/digest或破坏inventory/sync消费者。
### RISK-003
- `description`: 仅按数组位置关联路径、asset ref和pairing会在排序/去重后形成错误图片-提示词关系。
### RISK-004
- `description`: source audit/registry若直接信任HEAD或旧probation记录，会产生Commit、结构、数量或rights authority漂移。
### RISK-005
- `description`: 全量1930输出关系会放大下载、事务、失败恢复和workspace residue风险。
### RISK-006
- `description`: 把内部active误当作public approved会使未经人工审核内容进入API/Web。

### TEST-001
- `links`: `TASK-001`, `REQ-004`至`REQ-007`, `RISK-001`至`RISK-003`
- `method`: 共享multi-output unit/contract tests覆盖单输出、双输出、多输出、稳定ref identity、逐输出pairing、asset排序、generation IDs、metrics，以及缺失/重复/dangling/unresolved/同文档重复内容失败。
- `expected_observable_result`: 一case/N refs生成一Adapter record、一Generation document、N assets与N Generation Examples；旧单图serialized fixtures和semantic digest不变。
- `failure_path_covered`: 隐式位置错配、重复ref、输出未消费、资产被多generation消费、空输出与部分解析。
- `cannot_prove`: 真实source结构和数据库消费者。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: pytest receipt、旧fixture hash/digest比较、新multi-output golden fixtures与negative matrix。

### TEST-002
- `links`: `TASK-001`, `REQ-006`, `REQ-007`, `REQ-011`, `RISK-002`, `RISK-005`
- `method`: inventory package/database integration导入一个多输出case并重放，核对1 source case/1 prompt/N generations/N outputs、asset hash dedupe、transaction rollback和已有ready状态保持。
- `expected_observable_result`: 无migration即可正确计数；同key重放幂等，冲突/失败不产生半状态。
- `failure_path_covered`: partial DB write、same-key mismatch、duplicate asset object和replay drift。
- `cannot_prove`: 三真实来源全量数量。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: DB前后counts、revision状态、idempotency结果、failure rollback与cleanup receipt。

### TEST-003
- `links`: `TASK-002`, `REQ-001`至`REQ-003`, `REQ-009`, `REQ-010`, `RISK-004`
- `method`: freestyle小型固定结构fixtures覆盖正常/坏shape/孤立文件/资产异常；真实fixed-Commit全量运行并复跑。
- `expected_observable_result`: 517 cases、517 refs、0 parse errors、stable IDs/digest；异常fixture fail closed。
- `failure_path_covered`: count/id/path/orphan/missing/bad image/structure drift。
- `cannot_prove`: 其他来源与六源持久化。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: unit matrix、fixed Commit identity、full counts、ledger/digest与repeat equality receipt。

### TEST-004
- `links`: `TASK-003`, `REQ-001`至`REQ-005`, `REQ-009`, `REQ-010`, `RISK-001`, `RISK-003`, `RISK-004`
- `method`: Vigo fixtures覆盖style目录、双比例顺序、缺preview/孤立目录/重复ID；真实fixed-Commit全量运行并复跑。
- `expected_observable_result`: 112 cases、224 refs/generations，16x9 primary与9x16 secondary稳定，0静默丢图。
- `failure_path_covered`: variant错配、缺图、额外目录、路径/格式、顺序漂移。
- `cannot_prove`: Erick与六源装配。
### EV-004
- `for`: `TEST-004`
- `required_evidence_shape`: unit/golden/negative receipts、112/224 ledger、variant role mapping和repeat digest。

### TEST-005
- `links`: `TASK-004`, `REQ-001`至`REQ-005`, `REQ-009`至`REQ-012`, `RISK-001`, `RISK-003`, `RISK-004`, `RISK-006`
- `method`: Erick fixtures覆盖单/多图数组、稳定filename refs、空/重复/未知/孤立图和license unknown；真实fixed-Commit全量运行并复跑。
- `expected_observable_result`: 572 cases、877 refs/generations，所有图片有强pairing且rights仍review_required/auto_publish false。
- `failure_path_covered`: 多图丢失/复制、关系错配、重复图片项、orphan asset、rights弱化。
- `cannot_prove`: 六源数据库总量与public消费者。
### EV-005
- `for`: `TEST-005`
- `required_evidence_shape`: unit/golden/negative receipts、572/877 ledger、per-case ref closure、rights assertions和repeat digest。

### TEST-006
- `links`: `TASK-002`至`TASK-005`, `ASSEMBLY-001`, `REQ-008`至`REQ-012`, `RISK-002`至`RISK-006`
- `method`: source audit/registry/content-contract validators与全仓pytest；在workspace外运行六来源fixed-Commit提取、inventory import和sync，覆盖same-commit replay、单新源disable、failure injection/recovery和并发锁。
- `expected_observable_result`: 六active canonical来源合同一致；旧三源312不变；新三源1201 cases/1618 generations；总计1513 source cases/prompts、1930 generations/output links；replay no-op且失败无残留。
- `failure_path_covered`: audit/registry mismatch、unsupported adapter、部分package/DB、锁冲突、单源失败影响其他来源、旧源回归。
- `cannot_prove`: 公开消费者与人工rights结论。
### EV-006
- `for`: `TEST-006`
- `required_evidence_shape`: full pytest、六source per-source counts/digests、DB totals、sync reports、disable/replay/failure/concurrency、runtime cleanup与secret redactionreceipt。

### TEST-007
- `links`: `TASK-005`, `ASSEMBLY-001`, `REQ-012`, `REQ-013`, `INV-001`, `INV-006`, `RISK-006`
- `method`: 最新migrations下fresh运行Content Core、Public API和Public Web live；核对内部inventory totals与真实Publication/API/Web 0，并检查文档数字/状态。
- `expected_observable_result`: 内部1513/1930可审计，completed real Publication=0，API/Web list/detail不泄露未批准内容；`1.md`和Phase2/ingestion/inventory/sync文档一致。
- `failure_path_covered`: inventory直接公开、fake approval、文档把internal当public、consumer migration regression。
- `cannot_prove`: 未来人工审核质量或线上部署。
### EV-007
- `for`: `TEST-007`
- `required_evidence_shape`: Content/API/Web live receipts、internal/public counts、HTTP/browser断言、docs consistency与no-fake-approval检查。

### TEST-008
- `links`: `TASK-001`至`TASK-005`, `ASSEMBLY-001`, `REQ-014`, `RISK-001`至`RISK-006`
- `method`: final allowed/protected scope hashes、TASK-0018 authority hash、workspace hygiene、terminal freshness、deterministic evidence、L4独立review、唯一Completion Report验证。
- `expected_observable_result`: 仅本卡允许范围修改；TASK-0018事实与Phase 1历史未被改写；无`.venv`/cache/runtime/secret污染；review无Blocking/Major；report complete。
- `failure_path_covered`: scope drift、stale receipts、authority mutation、runtime residue、未披露风险和重复/无效report。
- `cannot_prove`: 部署、法律授权或后续HEAD更新运营。
### EV-008
- `for`: `TEST-008`
- `required_evidence_shape`: pre/post manifests、protected hashes、hygiene listing、freshness/integrity receipts、independent review findings与Completion Report validation。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"phase2-adapters-offline","command":["uv","run","--frozen","--no-sync","python","-B","-m","pytest","-p","no:cacheprovider","-q"],"cwd":".","timeout_seconds":1800,"invalidation_paths":["1.md","pyproject.toml","uv.lock","config","docs","fixtures","ingestion","inventory","reports","schemas","scripts","sync","tests"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["uv","run","--frozen","--no-sync","python","-B","-c","import pytest, jsonschema, psycopg, boto3; print('ready')"],"preflight_timeout_seconds":30},
  {"validator_id":"phase2-adapters-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_phase2_adapters.py","--json"],"cwd":".","timeout_seconds":5400,"invalidation_paths":["1.md","apps","config","content","docs","ingestion","inventory","migrations","reports/phase2/source-discovery-v1.json","reports/source-audit-v1.json","schemas","scripts/validate_phase2_adapters.py","sync","tests"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["git","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | multi-output兼容 | TASK-001 / TEST-001 / TEST-002 | 一案多输出闭合且旧三源字节/行为兼容 | EV-001 / EV-002 | 真实三新源 |
| GATE-002 | 三Adapter全量 | TASK-002..004 / TEST-003..005 | 517/517、112/224、572/877与重复确定性通过 | EV-003..005 | 六源持久化 |
| GATE-003 | 六来源内部闭环 | TASK-005 / ASSEMBLY-001 / TEST-006 | 六源合同、1513/1930、replay/failure/isolation通过 | EV-006 | public消费者 |
| GATE-004 | rights/public消费者 | TASK-005 / TEST-007 | internal 1513、真实public/API/Web 0、文档一致 | EV-007 | 人工审核/部署 |
| GATE-005 | 正式关闭 | TASK-001..005 / ASSEMBLY-001 / TEST-008 | scope/hygiene/freshness/review/report闭合 | EV-008 | 后续HEAD运营 |

# 10. 产物与完成回写
- `required_deliverables`:
  - `ingestion/adapters/freestylefly.py`
  - `ingestion/adapters/erickkkyt.py`
  - `ingestion/adapters/vigozhao.py`
  - `ingestion/adapters/base.py`
  - `ingestion/contracts.py`
  - `ingestion/pipeline.py`
  - `ingestion/adapters/__init__.py`
  - `ingestion/registry.py`
  - `config/sources-v1.yaml`
  - `reports/source-audit-v1.json`
  - `scripts/validate_phase2_adapters.py`
  - 三来源与multi-output相关fixtures/tests
  - `docs/phase2/phase2-adapter-activation-v1.md`
  - 必要的ingestion/inventory/sync文档与`1.md`状态更新
- `documentation_impact`: updated；记录六来源、固定Commit/Adapter、1201新增提示词案例、1618新增输出关系、总计1513内部案例/1930输出、0真实公开、未部署、独立启停/同步/恢复与后续人工rights运营。
- `repository_hygiene_requirement`: 外部Git mirrors、全量图片、数据库/对象存储/runtime/log/temporary/locks全部在workspace外；测试使用`-B`和禁用pytest cache；不得留下`.venv`、`__pycache__`、`.pytest_cache`、下载资产、secret或临时报告；保留用户既有`.task-runs`/`.work`内容且不把它们误算为本卡新增污染。
- `external_review`: policy=never；reason=无需Claude/外部第二意见；L4由独立内部review、真实fixed-Commit全量、六源stateful live与最终消费者验证闭合。
- `non_completion_rules`: 任一Adapter非全量、1201/1618或1513/1930不符、旧三源漂移、多输出关系不闭合、rights/public非0、same-commit/failure/recovery未证、scope/hygiene/freshness/review/report不完整时不得完成。

执行run ID、candidate/history、manifest/receipt hash、实际命令结果、final workspace snapshot和终态只写入正式执行sidecar/Completion Report，不回写本任务卡。本目录不是Git仓库，不创建commit。
