---
task_contract_version: 3
card_id: "TASK-0015"
title: "交付可浏览搜索复制Prompt的最小Next.js公共目录"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L3"
orchestration_risk: "O1"
execution_profiles:
  - "ui-workflow"
  - "public-contract"
  - "external-boundary"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户持续完成Phase 1授权；`1.md`第13至16节；TASK-0014正式API合同与Completion Report。
- `decision_owner`: 用户拥有产品目标；网页只消费API，不拥有rights、发布、数据库或S3决策。
- `material_unknowns`: 真实目录当前可能为空；必须交付高质量空状态，synthetic API用于验证非空用户流程。

# 2. 业务目标
- `actor`: 浏览GPT Image提示词案例的普通用户。
- `workflow_and_trigger`: 用户打开公共目录，按图片浏览、搜索/筛选，进入详情查看原始Prompt、来源、rights、参考图和model warning，并复制原始Prompt。
- `single_outcome`: 交付一个可运行、响应式、无管理写面的Next.js公共网站，完整消费TASK-0014只读API并覆盖列表→筛选→详情→复制→来源/权利识别的核心流程。
- `observable_results`:
  - `RESULT-001`: 首页显示当前Publication Version、搜索、source/display policy/tag/reference筛选、结果数、分页和图片优先案例卡。
  - `RESULT-002`: exact duplicate只显示一个Canonical Case；卡片显示主图或link_only占位、Prompt摘要、来源和model warning。
  - `RESULT-003`: 详情显示完整原始Prompt、一键复制、输入/输出资产、全部公开members来源、rights/display policy、taxonomy与model warning。
  - `RESULT-004`: 清楚区分原始Prompt与未来翻译/模板；本卡只展示`raw_text`，不伪造其他版本。
  - `RESULT-005`: no_current/0 entries、404、API unavailable、图片加载失败均有可理解且不误导的状态。
  - `RESULT-006`: 网页不读取DB/S3，不包含review/build/activate/admin入口；所有数据和图片通过TASK-0014 API。
  - `RESULT-007`: 手机与桌面布局可用，键盘焦点、语义标签、对比度、复制反馈和长Prompt换行通过验收。
  - `RESULT-008`: `next build`、组件/数据测试及真实浏览器smoke通过；synthetic API验证list/filter/detail/copy/image/empty/error流程。
- `non_goals`: 不实现后台、登录、rights审核、发布、收藏、推荐、编辑Prompt、复杂视觉动画、CDN或部署。

# 3. 需求质疑与确认
- `user_statement`: 项目要形成长期稳定内容来源与实际可用产品，不只停在库存和API。
- `REQ-001` (`required_behavior`): 使用Next.js+TypeScript固定依赖，单独位于`apps/web`；不得修改Python API/Content Core。
- `REQ-002` (`required_behavior`): server fetch使用`IMAGE2_API_INTERNAL_BASE_URL`，浏览器图片通过同源`/backend/*` rewrite；不得把DB/S3凭据写入NEXT_PUBLIC变量。
- `REQ-003` (`required_behavior`): 首页query string承载q/source/display_policy/tag/has_reference_input/page，支持可分享、刷新和后退恢复。
- `REQ-004` (`required_behavior`): 列表只使用API返回的Canonical items/count/facets，不在网页重新去重或推断rights。
- `REQ-005` (`required_behavior`): detail以canonical key请求API；复制只复制`prompt.raw_text`并提供成功/失败可访问反馈。
- `REQ-006` (`required_behavior`): 图片只渲染API提供的authorized asset URL；link_only使用来源链接/占位，不构造asset hash路由。
- `REQ-007` (`required_behavior`): model unknown/source_claimed warning、rights display policy、source/Commit/URL、reference input在UI中明确展示。
- `REQ-008` (`required_behavior`): API 503/404/validation错误映射为稳定页面，不显示stack、内部URL或secret。
- `REQ-009` (`required_behavior`): 样式以内容可读和图片优先为主，避免复杂设计系统；响应式断点、focus-visible、skip link和语义HTML必须存在。
- `REQ-010` (`required_behavior`): tests覆盖API client映射、query构造、empty/error和复制组件；live用受控synthetic API+Next server+真实浏览器验证关键流程与无console error。
- `REQ-011` (`required_behavior`): 文档固定启动配置、页面、API依赖、空目录语义和验收命令。
- `REQ-012` (`required_behavior`): 完成offline/live、L3独立复核、docs/hygiene/freshness与唯一Completion Report。
- `INV-001`: 网页不绕过API或重算publication/rights。
- `INV-002`: link_only不请求私有asset route；unknown模型不误标。
- `INV-003`: 原始Prompt复制内容必须与API字节级一致。
- `INV-004`: URL state与显示筛选一致；重复/刷新不丢状态。
- `INV-005`: 无数据是合法状态，不使用fake内容填充production页面。
- `material_ambiguities`: 当前没有品牌视觉规范；采用克制、响应式、内容优先的最小样式，不引入设计系统依赖。
- `decisions_and_authority`: 管理后台推迟；Phase1只交付公共核心用户流程。

# 4. 业务场景与规则
- `SCN-001`: active非空→首页浏览、筛选、分页、详情、复制和图片成功。
- `SCN-002`: no_current/empty→明确“尚无可公开案例”，不显示错误或伪数据。
- `SCN-003`: link_only→占位与原始来源链接，无私有图片请求。
- `SCN-004`: API unavailable/invalid→可恢复错误页与重试入口，无内部信息。
- `SCN-005`: mobile/keyboard→导航、筛选、卡片、复制可操作。
- `RULE-001`: API response是唯一内容authority。
- `RULE-002`: 原始Prompt、rights和model warning不得被UI文案改写。
- `STATE-001`: URL params→server API fetch→loading/empty/error/success；detail→copy feedback。
- `risk_sensitive_invariants`: current-only、link_only、准确复制、错误脱敏、无写入口。
- `inapplicable_faces_with_reason`: 无认证和持久用户状态；公共只读网站无需账户。

# 5. 当前证据与目标差异
- `FACT-001`: TASK-0014已提供publication/list/detail/asset API并正式验证Canonical去重、rights和错误边界。
- `FACT-002`: 当前无`apps/web`、Node package或页面。
- `ASM-001`: bundled Node可运行固定Next版本；必须由install/build/live验证。
- `current_execution_path`: 用户只能直接调用JSON API。
- `target_delta`: API上方增加实际可用公共用户界面。
- `evidence_gaps`: 尚缺实现、tests、browser smoke、文档和Completion Report。

# 6. 范围与责任边界
- `allowed_write_scope`: `apps/web/package.json`、`apps/web/package-lock.json`、`apps/web/next.config.ts`、`apps/web/tsconfig.json`、`apps/web/next-env.d.ts`、`apps/web/app/layout.tsx`、`apps/web/app/page.tsx`、`apps/web/app/cases/[canonicalKey]/page.tsx`、`apps/web/app/globals.css`、`apps/web/lib/api.ts`、`apps/web/components/case-card.tsx`、`apps/web/components/copy-prompt.tsx`、`apps/web/tests/api.test.ts`、`scripts/validate_public_web.py`、`docs/web/public-web-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: Python项目与lock、apps/api、content、inventory、migrations、compose、1.md、TASK-0001至0014及历史evidence。
- `protected_contracts_and_invariants`: `INV-001`至`INV-005`、TASK-0014 API合同与completion hash。
- `authorization_limits`: 不授权部署、外部发布、修改API、伪造production内容或公开未授权图片。
- `stop_if_scope_expands`: 若需要修改API/Content、增加管理写面、引入新服务或放宽rights，停止并报告。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: 浏览器访问Next页面；server components调用API；client copy component只处理剪贴板。
- `expected_touchpoints_or_search_anchors`: TASK-0014 docs/OpenAPI；Next App Router；same-origin backend rewrite。
- `wiring_to_final_consumer`: 首页筛选→case cards→detail→copy/source/asset；API错误→页面状态。
- `failure_and_recovery`: fetch设置timeout/no-store；错误生成稳定页面；复制失败反馈；图片on-error回退。
- `implementation_freedom`: 可调整组件拆分，但15个文件、页面功能、URL state、API-only和验证不可改变。
- `selected_profile_obligations`: `ui-workflow`覆盖loading/empty/error/success/accessibility；`public-contract`覆盖API schema mapping；`external-boundary`覆盖timeout/error/redaction/browser integration。

# 8. TASK 与 ASSEMBLY 计划
### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-012`, `INV-001`至`INV-005`
- `owns_behavior`: 最小公共网站核心用户流程。
- `target_delta`: 从API可用到用户可浏览、筛选、查看、复制。
- `integration_edges`: Next server→TASK-0014 API；browser→Next→API asset rewrite。
- `expected_touchpoints`: section 6的15个文件。
- `business_result`: Phase1首次具备实际用户界面。
- `behavior_faces`: success/empty/error/mobile/keyboard/link_only/copy/image failure。
- `state_change`: 仅URL和浏览器复制反馈，无持久写状态。
- `data_flow`: API JSON/image→server rendering/client interaction。
- `integration_point`: caller=browser；callee=API；return=HTML/CSS/JS/image。
- `scope_boundary`: hard=不改后端；soft=无后台/推荐。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-005`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: API合同不足需后端变化、需要写权限或rights放宽。
- `assembly_not_required_reason`: 一个完整公共UI纵向切片。

# 9. 验证与验收
- `consumer_chain_validation`: 必须用真实Next server和浏览器从首页进入detail并复制Prompt/加载图片；仅build或组件单测不足。
- `real_integration_evidence`: synthetic API server+Next production server+browser截图/DOM/网络/console证据，同时覆盖empty与非空。
- `failure_recovery_ownership_validation`: Next拥有fetch/error/empty/copy/image fallback；API拥有数据/rights；Validator拥有进程和临时目录清理。
### RISK-001
- `description`: UI重算或改写API事实会破坏rights/model/Canonical合同。
### RISK-002
- `description`: link_only构造asset route会越权请求图片。
### RISK-003
- `description`: 复制文本与原文不一致会直接损害核心用户价值。
### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-010`, `RISK-001`至`RISK-003`
- `method`: npm test与Next type/build，测试API mapping/query/error/copy和静态可访问性约束。
- `expected_observable_result`: tests/build通过，无protected后端依赖。
- `failure_path_covered`: empty/503/404/invalid/link_only/copy failure。
- `cannot_prove`: 不证明真实浏览器。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: npm install/test/build logs与test matrix。
### TEST-002
- `links`: `TASK-001`, `REQ-002`至`REQ-012`, `INV-001`至`INV-005`
- `method`: `scripts/validate_public_web.py --json`启动synthetic API和Next production server，用真实浏览器覆盖desktop/mobile、filter/detail/copy/image/empty/error、console/network和cleanup。
- `expected_observable_result`: 核心流程通过、截图/DOM正确、无secret/console error、进程临时目录清理。
- `failure_path_covered`: API down、image error、link_only、empty、copy denial。
- `cannot_prove`: 不证明生产部署或真实rights非空。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: JSON、screenshots、browser assertions、process cleanup。
### TEST-003
- `links`: `TASK-001`, `REQ-011`, `REQ-012`
- `method`: 15文件scope、protected hashes、docs/hygiene/freshness、L3 independent review和Completion Report。
- `expected_observable_result`: 15/15、2 validators、review 0 findings、report complete。
- `failure_path_covered`: scope/doc/stale evidence。
- `cannot_prove`: 不证明sync。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/review/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"public-web-offline","command":["npm","run","validate"],"cwd":"apps/web","timeout_seconds":900,"invalidation_paths":["apps/web","docs/web/public-web-v1.md","docs/api/public-api-v1.md"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["node","--version"],"preflight_timeout_seconds":30},
  {"validator_id":"public-web-browser-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_public_web.py","--json"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["apps/web","apps/api","docs/api/public-api-v1.md","docs/web/public-web-v1.md","scripts/validate_public_web.py"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["node","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | offline/build | TASK-001/TEST-001 | test/type/build通过 | EV-001 | browser |
| GATE-002 | browser live | TASK-001/TEST-002 | list/detail/copy/image/empty/error通过 | EV-002 | deploy |
| GATE-003 | closure | TASK-001/TEST-003 | scope/docs/review/report闭合 | EV-003 | sync |

# 10. 产物与完成回写
- `required_deliverables`:
  - `apps/web/package.json`
  - `apps/web/package-lock.json`
  - `apps/web/next.config.ts`
  - `apps/web/tsconfig.json`
  - `apps/web/next-env.d.ts`
  - `apps/web/app/layout.tsx`
  - `apps/web/app/page.tsx`
  - `apps/web/app/cases/[canonicalKey]/page.tsx`
  - `apps/web/app/globals.css`
  - `apps/web/lib/api.ts`
  - `apps/web/components/case-card.tsx`
  - `apps/web/components/copy-prompt.tsx`
  - `apps/web/tests/api.test.ts`
  - `scripts/validate_public_web.py`
  - `docs/web/public-web-v1.md`
- `documentation_impact`: updated；记录页面、配置、API依赖、空状态与验证。
- `repository_hygiene_requirement`: 仅15文件；`node_modules/.next/screenshots/logs`不得入workspace；运行状态在外部TASK-0015 runtime；旧任务只读。
- `external_review`: policy=never；browser live+L3 independent review足够。
- `non_completion_rules`: 15/15、build/tests/browser、copy精确、link_only、empty/error、accessibility、docs/review/freshness/report任一缺失不得完成。

### 必交产物
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/next.config.ts`
- `apps/web/tsconfig.json`
- `apps/web/next-env.d.ts`
- `apps/web/app/layout.tsx`
- `apps/web/app/page.tsx`
- `apps/web/app/cases/[canonicalKey]/page.tsx`
- `apps/web/app/globals.css`
- `apps/web/lib/api.ts`
- `apps/web/components/case-card.tsx`
- `apps/web/components/copy-prompt.tsx`
- `apps/web/tests/api.test.ts`
- `scripts/validate_public_web.py`
- `docs/web/public-web-v1.md`

完成后继续TASK-0016 Commit更新与增量同步。
