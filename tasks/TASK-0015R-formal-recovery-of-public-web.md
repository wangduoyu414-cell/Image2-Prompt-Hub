---
task_contract_version: 3
card_id: "TASK-0015R"
title: "重新冻结并正式闭环现有Next.js公共目录"
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
- `authority_sources`: 用户明确要求持续推进至全部完成；TASK-0015 ready合同；当前15个网页交付文件；TASK-0015正式run保留的`RESULT_UNKNOWN`与stale O1 operation事实。
- `decision_owner`: 用户授权在原15文件范围内重新冻结、验证和必要修复；旧operation/claim/receipt历史不得修改或伪装成通过。
- `material_unknowns`: 当前15文件是否已满足全部browser、accessibility、hygiene和review门必须由全新run的fresh证据决定，不能沿用中断命令的非终端状态。

# 2. 业务目标
- `actor`: 浏览GPT Image案例的普通用户与维护该公共目录的执行者。
- `workflow_and_trigger`: 从当前工作区重新冻结现有网页切片，fresh执行offline和synthetic API+Next production+真实浏览器验证；若发现缺陷，只在原15文件内修复并重跑，最后形成新的唯一Completion Report。
- `single_outcome`: 在不篡改TASK-0015未知历史的前提下，正式接管并证明现有Next.js公共目录完整可用，使Phase 1网页环节获得可信、可复核的complete证据。
- `observable_results`:
  - `RESULT-001`: 15个既定文件全部存在且保持API-only、current-only、Canonical列表、detail完整raw Prompt与精确复制。
  - `RESULT-002`: URL搜索/筛选/分页、图片/`link_only`、model/rights/source信息、empty/404/API error/image error均符合TASK-0015合同。
  - `RESULT-003`: desktop/mobile、键盘焦点、skip link、语义HTML、复制反馈和长Prompt显示通过真实浏览器验收。
  - `RESULT-004`: `npm run validate`和`scripts/validate_public_web.py --json`在全新operation/receipt下fresh通过；旧未知operation不参与通过判断。
  - `RESULT-005`: scope、protected files、docs、runtime cleanup、freshness、L3 independent review和Completion Report完整闭合。
- `non_goals`: 不释放或改写旧TASK-0015 claim，不修改API/Content/inventory/migrations/compose，不新增功能、部署、管理后台或production内容。

# 3. 需求质疑与确认
- `user_statement`: 持续推进到全部完成；可恢复的宿主中断不能成为项目终点。
- `REQ-001` (`required_behavior`): 新formal run必须以本卡身份和当前workspace为base，不能复用TASK-0015旧claim、operation或无终端receipt。
- `REQ-002` (`required_behavior`): 旧TASK-0015保持`RESULT_UNKNOWN`只读历史；新报告必须明确它未被改写，同时说明本卡用fresh证据替代其完成作用。
- `REQ-003` (`required_behavior`): 只允许原TASK-0015的15个durable文件；若验证需要后端、配置、依赖版本或第16个文件变化，停止并报告。
- `REQ-004` (`required_behavior`): 网页只消费TASK-0014 API；server fetch用内部base URL，浏览器图片用同源rewrite，不读取DB/S3或暴露secret。
- `REQ-005` (`required_behavior`): query string保存q/source/display_policy/tag/has_reference_input/page；列表不重算Canonical/rights；detail复制内容与API `raw_text`精确一致。
- `REQ-006` (`required_behavior`): `link_only`不得构造或请求私有asset route；unknown/source_claimed model和rights policy不得被UI改写。
- `REQ-007` (`required_behavior`): no_current/empty、404、503/invalid、copy denial和image failure提供稳定、脱敏、可恢复状态。
- `REQ-008` (`required_behavior`): offline validator必须覆盖test/type/build；live validator必须启动synthetic API、production Next和本地Chromium，覆盖list/filter/detail/copy/image/empty/error/mobile/console/network/cleanup。
- `REQ-009` (`required_behavior`): node_modules、`.next`、screenshots、logs和进程状态位于workspace外或完成后清理；不得引入工作区临时环境。
- `REQ-010` (`required_behavior`): 完成15文件scope/protected hash、docs、全回归、freshness、L3 independent review与唯一Completion Report。
- `INV-001`: 只有新run的终端receipt可证明通过；启动过、命令曾完成或旧截图都不能替代。
- `INV-002`: API是唯一内容authority；网页无写权限和rights决策权。
- `INV-003`: production空目录是合法状态，synthetic数据只属于validator。
- `INV-004`: link_only、精确复制、错误脱敏和无secret是不可放宽边界。
- `material_ambiguities`: 无；功能和文件范围已由TASK-0015固定，本卡只恢复正式证据链。
- `decisions_and_authority`: 用户明确授权安全重跑；新卡/新run是保留旧未知历史时的最小可信恢复路径。

# 4. 业务场景与规则
- `SCN-001` fresh pass: 当前实现无需修改，两个validator在新run通过并完成review/report。
- `SCN-002` bounded fix: fresh验证发现网页缺陷，仅修改15文件内相关项，冻结新candidate后全部重跑。
- `SCN-003` failure: browser/build/contract仍失败或需要越界，保持non-complete且输出真实阻点。
- `SCN-004` history: 旧claim/operation继续为RESULT_UNKNOWN，新run有独立operation/receipt/report。
- `RULE-001`: completion只由新run final revision的fresh证据决定。
- `RULE-002`: 旧未知历史不得删除、释放、覆盖或标记passed。
- `STATE-001`: current workspace→new base snapshot→candidate→offline/live→review/freshness→complete或blocked。
- `risk_sensitive_invariants`: `INV-001`至`INV-004`、exact 15 files、API-only、workspace外runtime、fresh receipt。
- `inapplicable_faces_with_reason`: 无账户/持久用户状态/写API；权限面仅为网页不得越过后端rights边界。

# 5. 当前证据与目标差异
- `FACT-001`: 15个TASK-0015 deliverables当前均已存在，网页实现和validator已落盘。
- `FACT-002`: TASK-0015旧run的O1 browser operation记录为RUNNING但runner/child均不存在，且无终端receipt；正式runner拒绝自动reclaim。
- `FACT-003`: 旧run没有Completion Report，不能宣称complete。
- `FACT-004`: TASK-0014 API已正式完成，仍是网页唯一后端合同。
- `ASM-001`: 新卡使用独立task identity和formal run时不会继承TASK-0015旧claim；必须由正式acquire结果验证，若仍冲突则本卡保持non-complete。
- `current_execution_path`: 网页代码可构建/运行，但正式完成证据被旧operation未知状态截断。
- `target_delta`: 用独立新卡和新run重新证明同一15文件用户流程并形成合法Completion Report。
- `evidence_gaps`: fresh offline/live receipts、review、hygiene/freshness和report。

# 6. 范围与责任边界
- `allowed_write_scope`: `apps/web/package.json`、`apps/web/package-lock.json`、`apps/web/next.config.ts`、`apps/web/tsconfig.json`、`apps/web/next-env.d.ts`、`apps/web/app/layout.tsx`、`apps/web/app/page.tsx`、`apps/web/app/cases/[canonicalKey]/page.tsx`、`apps/web/app/globals.css`、`apps/web/lib/api.ts`、`apps/web/components/case-card.tsx`、`apps/web/components/copy-prompt.tsx`、`apps/web/tests/api.test.ts`、`scripts/validate_public_web.py`、`docs/web/public-web-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: TASK-0015旧run/claim/operation/ledger、Python/lock、apps/api、content、inventory、migrations、compose、1.md、其他tasks/evidence。
- `protected_contracts_and_invariants`: TASK-0014 API合同、TASK-0015 `INV-001`至`INV-005`、本卡`INV-001`至`INV-004`。
- `authorization_limits`: 不授权手工编辑formal history、释放旧claim、外部部署、后端变化或伪造validation。
- `stop_if_scope_expands`: 需要第16个durable文件、后端变化、rights放宽或无法获得新run终端receipt。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: 浏览器→Next pages/server components→TASK-0014 API；client copy只操作剪贴板。
- `expected_touchpoints_or_search_anchors`: section 6的15文件；TASK-0014 docs/OpenAPI；旧TASK-0015只作需求authority不作receipt。
- `wiring_to_final_consumer`: 首页→筛选/分页→Canonical卡片→detail→copy/source/asset；错误/空状态由同一browser live验证。
- `failure_and_recovery`: 新run独立claim；candidate每次变更后重跑；browser进程/临时目录由validator清理；失败不产生complete report。
- `implementation_freedom`: 当前实现可保持不变；只有fresh evidence暴露缺陷时才在15文件内作最小修复。
- `selected_profile_obligations`: `ui-workflow`覆盖用户状态/accessibility；`public-contract`覆盖API映射；`external-boundary`覆盖synthetic API/Next/Chromium/cleanup/redaction。

# 8. TASK 与 ASSEMBLY 计划

### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-010`, `INV-001`至`INV-004`
- `owns_behavior`: 现有15文件网页切片的fresh formal adoption与闭环。
- `target_delta`: 从代码存在但旧结果未知，变为新run证据完整且可复核的完成状态。
- `integration_edges`: Next→TASK-0014 API；browser→Next→same-origin asset rewrite。
- `expected_touchpoints`: section 6的15文件。
- `business_result`: Phase 1网页环节获得可信complete报告。
- `behavior_faces`: success/empty/error/link_only/copy/image/mobile/keyboard；repeated=fresh rerun；downstream=API/web user flow。
- `state_change`: new base→candidate→validated/reviewed→complete；失败保持non-complete。
- `data_flow`: API JSON/image→Next render/client interaction→browser assertions。
- `integration_point`: caller=browser validator；callee=synthetic API+production Next；return=DOM/network/console/screenshots/JSON；consumer=formal report。
- `scope_boundary`: hard=15文件/旧history只读；soft=无新功能。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-004`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: scope expansion、无法生成新终端receipt或后端合同不足。
- `assembly_not_required_reason`: 一个完整网页纵向恢复切片。

# 9. 验证与验收
- `consumer_chain_validation`: 必须由真实production Next和Chromium从首页进入detail并复制/加载；只看源代码、build或旧命令状态不足。
- `real_integration_evidence`: 新operation的synthetic API+Next+Chromium JSON/screenshots/DOM/network/console/cleanup。
- `failure_recovery_ownership_validation`: validator拥有进程/临时目录；网页拥有fetch/error/copy/image fallback；API拥有内容/rights。

### RISK-001
- `description`: 将旧无receipt operation当passed会污染正式证据。
### RISK-002
- `description`: 新run若受TASK-0015旧claim影响或修改越界，恢复仍不可信。
### RISK-003
- `description`: build通过但browser用户流程断开会形成表面完成。

### TEST-001
- `links`: `TASK-001`, `REQ-003`至`REQ-009`, `RISK-003`
- `method`: 在`apps/web`执行`npm run validate`，覆盖tests/type/build与静态合同。
- `expected_observable_result`: test/type/build fresh通过，node产物不留在workspace。
- `failure_path_covered`: API mapping/query/empty/error/copy/link_only静态路径。
- `cannot_prove`: 真实浏览器和进程cleanup。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: 新run terminal receipt、npm logs、test/build summary。

### TEST-002
- `links`: `TASK-001`, `REQ-004`至`REQ-010`, `INV-002`至`INV-004`, `RISK-003`
- `method`: 在根目录执行`uv run --frozen --no-sync python -B scripts/validate_public_web.py --json`，使用fresh synthetic API、production Next和Chromium。
- `expected_observable_result`: desktop/mobile、filter/detail/copy/image/link_only/empty/error/console/network/cleanup全部通过。
- `failure_path_covered`: API unavailable、404、invalid、copy denial、image failure和secret redaction。
- `cannot_prove`: production deploy或真实非空rights。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: 新operation终端receipt、JSON、screenshots、assertions、process/runtime cleanup。

### TEST-003
- `links`: `TASK-001`, `REQ-001`至`REQ-003`, `REQ-009`, `REQ-010`, `RISK-001`, `RISK-002`
- `method`: exact15 files、old history只读、protected hash、docs/hygiene/full regression、L3 independent review、final freshness和Completion Report validation。
- `expected_observable_result`: 15/15、2 validators、旧unknown未改、review 0 findings、report complete。
- `failure_path_covered`: stale receipt、scope drift、workspace runtime、旧history污染。
- `cannot_prove`: Commit更新同步。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/receipts/history check/review/freshness/report。

### 正式 Validator Manifest
```json
{"schema_version":1,"validators":[
  {"validator_id":"public-web-recovery-offline","command":["npm","run","validate"],"cwd":"apps/web","timeout_seconds":900,"invalidation_paths":["apps/web","docs/web/public-web-v1.md","docs/api/public-api-v1.md"],"validation_kind":"behavior","environment_sensitive":false,"preflight_command":["node","--version"],"preflight_timeout_seconds":30},
  {"validator_id":"public-web-recovery-browser-live","command":["uv","run","--frozen","--no-sync","python","-B","scripts/validate_public_web.py","--json"],"cwd":".","timeout_seconds":1200,"invalidation_paths":["apps/web","apps/api","docs/api/public-api-v1.md","docs/web/public-web-v1.md","scripts/validate_public_web.py"],"validation_kind":"behavior","environment_sensitive":true,"preflight_command":["node","--version"],"preflight_timeout_seconds":30}
]}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| GATE-001 | fresh offline | OBJ-001 / TASK-001 / TEST-001 | test/type/build新receipt通过 | EV-001 | browser |
| GATE-002 | fresh browser | OBJ-001 / TASK-001 / TEST-002 | 完整用户流程与cleanup新receipt通过 | EV-002 | deploy |
| GATE-003 | recovery closure | OBJ-001 / TASK-001 / TEST-003 | 15文件、旧history只读、docs/review/freshness/report闭合 | EV-003 | sync |

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
- `documentation_impact`: updated only if fresh validation exposes missing runtime/contract guidance；否则none，因为现有web文档本身是必交且需验证。
- `repository_hygiene_requirement`: exact15 durable files；node_modules/.next/screenshots/logs/process state在workspace外或清理；TASK-0015旧run与其他task只读。
- `external_review`: policy=never；fresh browser live+L3 independent review足够。
- `non_completion_rules`: 15/15、fresh offline/live terminal receipts、旧RESULT_UNKNOWN只读、API-only/link_only/copy/empty/error/accessibility、cleanup、docs/review/freshness/report任一缺失不得完成。

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

本卡完成后执行TASK-0016 Commit更新与增量同步。
