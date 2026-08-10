---
task_contract_version: 3
card_id: "TASK-0014"
title: "提供只读Publication API与受权利策略约束的资产交付"
status: "ready"
work_kind: "code"
execution_target: "agent-executable"
complexity: "complex"
product_risk: "L4"
orchestration_risk: "O1"
execution_profiles:
  - "public-contract"
  - "external-boundary"
  - "stateful-runtime"
external_review_policy: "never"
repo_root: "D:/image2"
blocked_by: []
---

# 1. 任务身份与就绪状态
- `objective_id`: `OBJ-001`
- `readiness`: ready
- `authority_sources`: 用户持续完成Phase 1授权；`D:/image2/1.md`第12至16节；已正式完成的TASK-0013 Content Core合同与Completion Report。
- `decision_owner`: 用户拥有公开范围与产品目标；API只能投影current completed Publication Version，不拥有rights、去重或发布决策。
- `material_unknowns`: 当前真实三来源无人工rights review，因此真实API空目录是正确状态；positive路径仅用明确标注为synthetic的本地集成数据验证。

# 2. 业务目标
- `actor`: 公共网页、只读API用户和运行维护者。
- `workflow_and_trigger`: Content Core已原子激活Publication Version后，客户端需要稳定获取版本元数据、去重后的案例列表、搜索/Facet、详情和被授权的图片字节。
- `single_outcome`: 建立FastAPI只读边界，只从current active immutable snapshots读取；按Canonical Case去重公开列表，并只为`mirror_allowed|attribution_required`资产代理私有对象，`link_only`与未发布资产永不经本API输出字节。
- `observable_results`:
  - `RESULT-001`: `/api/v1/publication`返回current版本或合法`no_current`空状态。
  - `RESULT-002`: `/api/v1/cases`按Canonical Case唯一展示，支持分页、关键词、source、display policy、tag、是否有参考图筛选和Facets。
  - `RESULT-003`: `/api/v1/cases/{canonical_key}`返回完整原始Prompt、输入/输出、全部公开member来源血缘、rights、model warning和taxonomy；不存在或不在current版本返回404。
  - `RESULT-004`: exact duplicate多个membership只生成一个列表项，detail保留member_count与全部公开来源；相同Prompt不同输出仍为不同案例。
  - `RESULT-005`: `/api/v1/assets/{sha256}`仅在current版本中存在公开可镜像资产时从配置S3/MinIO流式返回；link_only、旧版本、未发布、错误hash和非图片均拒绝。
  - `RESULT-006`: API不返回bucket、object_key、凭据、数据库URL或内部行ID；资产响应有正确media type、ETag、Content-Length和immutable缓存头。
  - `RESULT-007`: DB/S3不可用、对象缺失/哈希或长度不符时fail-closed为结构化503/502，不把远端HTML或错误内容当图片。
  - `RESULT-008`: OpenAPI只有GET/HEAD型公共读取面，无review/build/activate/rollback/admin写接口。
  - `RESULT-009`: 本地Compose PostgreSQL+MinIO fresh验证覆盖空目录、3条synthetic公开entry、Canonical去重、搜索/Facet/详情、镜像资产、link_only拒绝、旧版本隔离和cleanup。
- `non_goals`: 不实现Next.js网页、管理后台、rights审核、Publication构建/激活、Git同步、推荐排序、pgvector、图片变换/CDN或外部部署。

# 3. 需求质疑与确认
- `user_statement`: 继续完整纵向闭环，来源和发布边界必须长期稳定而非只做案例统计。
- `REQ-001` (`required_behavior`): 新增`apps.api` FastAPI应用，配置通过环境变量注入，启动时不得执行migration、canonicalize、review、build或activate。
- `REQ-002` (`required_behavior`): repository只能读取`content.publication_current`指向且state=`active`的immutable entries；禁止从inventory或latest rights rows重新计算公开资格。
- `REQ-003` (`required_behavior`): list以canonical_key分组；代表entry按generation_example_row_id稳定选择，同时合并公开members/source provenance并保持确定排序。
- `REQ-004` (`required_behavior`): q搜索至少覆盖raw Prompt、source id、author与taxonomy tag；筛选和分页顺序确定，参数有Pydantic边界和上限。
- `REQ-005` (`required_behavior`): facets与总数必须基于筛选后的current Canonical集合，不因duplicate membership重复计数。
- `REQ-006` (`required_behavior`): response models明确区分原始Prompt、model warning、reference input、display policy和source provenance；不得伪称unknown模型为GPT Image 2实测。
- `REQ-007` (`required_behavior`): asset lookup必须先在current snapshots中授权hash与storage locator；只接受`mirror_allowed|attribution_required`，`link_only`永远无storage读取。
- `REQ-008` (`required_behavior`): S3 endpoint仅允许HTTPS或loopback HTTP；使用私有凭据服务端读取，响应前验证对象content length、content type和SHA-256；不得透传S3错误正文/凭据。
- `REQ-009` (`required_behavior`): 空current或0 entries为200稳定空响应；DB/S3 unavailable为结构化503，非法参数422，未知case/asset为404，完整错误不暴露secret。
- `REQ-010` (`required_behavior`): health只证明进程；readiness真实检查DB schema/current查询边界但不要求非空publication。
- `REQ-011` (`required_behavior`): 添加固定FastAPI/Pydantic/Uvicorn及测试依赖并更新lock；不得引入未使用框架。
- `REQ-012` (`required_behavior`): offline tests使用fake repository/store；live只用隔离Compose seed，执行真实ASGI HTTP请求与真实MinIO字节校验。
- `REQ-013` (`required_behavior`): 文档固定端点、参数、response/error、cache、rights与空目录语义，为TASK-0015网页提供权威consumer合同。
- `REQ-014` (`required_behavior`): 正式完成offline/live、L4 independent review、docs/hygiene/freshness和唯一Completion Report。
- `INV-001`: API只读current completed Publication Version，不能绕过Content Core。
- `INV-002`: Canonical去重不删除或隐藏detail中的公开membership血缘。
- `INV-003`: link_only、internal_only、blocked、unknown或非current资产不返回字节。
- `INV-004`: 不暴露storage locator、credentials、内部DB结构或stack trace。
- `INV-005`: 所有搜索、facets、详情与资产都绑定同一current version，切换版本后新请求原子看到新版本。
- `INV-006`: TASK-0013生产文件与migration受保护；API不得要求修改其合同才能工作。
- `material_ambiguities`: Phase1数据规模小，首版允许在repository读取current snapshots后进行确定性分组/筛选；只有真实性能证据出现时才引入搜索索引migration。
- `decisions_and_authority`: 资产字节交付属于公共API而非网页；没有可用图片的页面不算纵向闭环，因此本卡包含受策略约束的S3代理。

# 4. 业务场景与规则
- `SCN-001`: no current/empty active → publication和cases均200空，readiness仍可通过。
- `SCN-002`: exact duplicate → list一项、detail多个members；不同输出→多项。
- `SCN-003`: q/filter/facet/page组合返回确定性结果与正确总数。
- `SCN-004`: mirror_allowed/attribution_required当前资产→200真实图片；ETag/长度/hash正确。
- `SCN-005`: link_only/old/unpublished/unknown hash→404且不调用S3。
- `SCN-006`: DB/S3/Object integrity错误→503/502且无secret/错误字节。
- `SCN-007`: publication pointer切换→后续请求只读新current，旧case/asset消失。
- `RULE-001`: API是read model，不是发布决策者。
- `RULE-002`: 空目录合法；不得为非空结果推断rights。
- `RULE-003`: 所有公开聚合以Canonical key为身份，以snapshot为事实。
- `STATE-001`: request→load current version→group/filter/project→respond；asset request额外authorize current snapshot→private get→integrity verify→stream。
- `risk_sensitive_invariants`: rights隔离、版本一致性、secret redaction、对象完整性、去重计数、只读HTTP。
- `inapplicable_faces_with_reason`: 无登录、写操作、后台或网页视觉；公共内容无需账户权限，本任务只处理发布后读取。

# 5. 当前证据与目标差异
- `FACT-001`: TASK-0013提供`ContentDatabase.inspect_publication()`，只读active snapshot并返回version与entries。
- `FACT-002`: snapshot已包含canonical key、raw Prompt、asset ordinal/role/hash/media/length/source location、rights/model/taxonomy；link_only不含bucket/object_key。
- `FACT-003`: 当前无FastAPI/apps目录、HTTP合同或公共资产交付。
- `FACT-004`: pyproject已有boto3/psycopg，Compose已有PostgreSQL和私有MinIO。
- `ASM-001`: current Phase1规模可在单请求读取后确定性分组；live必须验证行为，后续性能优化另立任务。
- `current_execution_path`: Content CLI inspect JSON只能本地维护者使用。
- `target_delta`: 稳定公共HTTP read model与rights-safe图片字节边界。
- `evidence_gaps`: 尚缺依赖、API实现、tests、live Validator、文档与Completion Report。

# 6. 范围与责任边界
- `allowed_write_scope`: `pyproject.toml`、`uv.lock`、`apps/__init__.py`、`apps/api/__init__.py`、`apps/api/main.py`、`apps/api/models.py`、`apps/api/repository.py`、`apps/api/assets.py`、`tests/api/test_public_api.py`、`scripts/validate_public_api.py`、`docs/api/public-api-v1.md`、本卡formal evidence root。
- `hard_protected_scope`: `content`、`inventory`、`ingestion`、全部migrations、compose.yaml、registry/audit/schemas/fixtures、TASK-0001至0013及历史evidence、1.md。
- `protected_contracts_and_invariants`: `INV-001`至`INV-006`、TASK-0013 complete report/hash、当前无审批即空公开目录。
- `authorization_limits`: 不授权rights批准、发布激活、外部部署、公开真实未批准资产、修改数据库或删除对象。
- `stop_if_scope_expands`: 若必须修改Content Core/migration/Compose、添加写接口、推断rights或公开link_only字节，停止并报告。

# 7. 实现蓝图
- `blueprint_status`: confirmed
- `caller_entry_consumer`: TASK-0015 Next.js与外部只读客户端调用FastAPI；API repository读取current snapshots；asset service读取已授权私有对象。
- `expected_touchpoints_or_search_anchors`: `ContentDatabase.inspect_publication`、snapshot v1字段、inventory object-store安全配置、现有Compose随机项目Validator模式。
- `wiring_to_final_consumer`: publication metadata→case list/facets→detail/copy→authorized image route；网页不直接连接DB/S3。
- `failure_and_recovery`: 每个请求无副作用；DB/S3失败返回稳定错误；pointer切换无需API缓存失效以外的状态迁移；Validator总清理Compose/runtime。
- `implementation_freedom`: 可调整内部类与路由依赖注入，但端点、只读current、Canonical分组、asset authorization/integrity、错误和11文件边界不可改变。
- `selected_profile_obligations`:
  - `public-contract`: versioned routes/models/errors/OpenAPI、向后兼容和consumer tests。
  - `external-boundary`: DB/S3 timeout/failure/observability/no-secret/真实integration。
  - `stateful-runtime`: current pointer切换、请求一致性、empty/old-version和重复读取。

# 8. TASK 与 ASSEMBLY 计划
### TASK-001
- `links`: `OBJ-001`, `REQ-001`至`REQ-014`, `INV-001`至`INV-006`
- `owns_behavior`: current Publication Version的只读HTTP投影与授权资产交付。
- `target_delta`: 从本地CLI inspect升级为网页可消费的稳定公共合同。
- `integration_edges`: FastAPI→Content current snapshots→Canonical projection；FastAPI→authorized locator→private S3→HTTP image。
- `expected_touchpoints`: section 6的11个文件。
- `business_result`: Phase1案例可以被网页安全浏览、搜索、查看Prompt/来源并加载获授权图片。
- `behavior_faces`: normal=list/detail/image；boundary=empty/page/duplicate；failure=DB/S3/integrity；permission=display policy；repeated=idempotent GET；downstream=TASK-0015。
- `state_change`: request前后无持久状态变化；current publication由Content Core外部切换。
- `data_flow`: immutable snapshot→API model→web；authorized storage locator→verified bytes→client。
- `integration_point`: caller=web；trigger=GET；callee=PostgreSQL/S3；return=JSON/image；consumer=browser。
- `scope_boundary`: hard=无写/无Content修改；soft=无CDN/resize/ranking。
- `allowed_write_scope`: section 6。
- `acceptance_scenarios`: `SCN-001`至`SCN-007`。
- `linked_tests`: `TEST-001`, `TEST-002`, `TEST-003`
- `stop_conditions`: 需要写发布状态、放宽rights、暴露locator/secret、修改protected scope。
- `assembly_not_required_reason`: API与资产交付共同构成一个公共读取切片；网页由后续任务装配。

# 9. 验证与验收
- `consumer_chain_validation`: 必须从current active PostgreSQL snapshots走到真实ASGI list/detail/facet响应，并从同一current snapshot授权locator后走到MinIO图片字节；只验证route函数或fake store不足。
- `real_integration_evidence`: fresh隔离Compose PostgreSQL+MinIO、真实migration/seed、ASGI HTTP请求、current版本切换、对象完整性和post-cleanup共同构成集成证据。
- `failure_recovery_ownership_validation`: API拥有DB/S3错误映射、secret redaction、link_only/old version拒绝和请求级无副作用；Content Core拥有pointer/rights，MinIO拥有对象，Validator拥有隔离资源清理。

### RISK-001
- `description`: 绕过current snapshot会公开被撤回或未审核内容。
### RISK-002
- `description`: link_only或storage locator泄漏会越权公开私有资产。
### RISK-003
- `description`: membership重复会造成前台重复案例与错误facet计数。
### RISK-004
- `description`: S3错误/HTML/损坏对象被当图片会造成安全和完整性问题。
### RISK-005
- `description`: HTTP错误泄露凭据、DSN或stack trace。

### TEST-001
- `links`: `TASK-001`, `REQ-001`至`REQ-011`, `RISK-001`至`RISK-005`
- `method`: pytest offline，依赖注入fake repository/store并通过ASGI client覆盖routes/models/group/filter/facet/errors/asset authorization与OpenAPI只读面。
- `expected_observable_result`: empty、duplicate、detail、filters、link_only拒绝、integrity failure和secret redaction断言通过。
- `failure_path_covered`: invalid params、no current、unknown case/asset、DB/S3 unavailable、wrong hash/type/length。
- `cannot_prove`: 不证明真实PostgreSQL/MinIO。
### EV-001
- `for`: `TEST-001`
- `required_evidence_shape`: fresh pytest receipt与route/risk matrix。

### TEST-002
- `links`: `TASK-001`, `REQ-002`至`REQ-014`, `INV-001`至`INV-006`
- `method`: 隔离Compose PostgreSQL+MinIO seed，启动真实ASGI app并发起HTTP请求，验证current切换、Canonical聚合、search/facet/detail、图片字节/headers、link_only/old拒绝与cleanup。
- `expected_observable_result`: 0目录与synthetic正路径均闭合；所有数据来自current snapshots；MinIO对象hash/length/type匹配；无残留。
- `failure_path_covered`: DB/S3/object/pointer/version错误和cleanup。
- `cannot_prove`: 不证明真实三来源rights批准、外网或生产部署。
### EV-002
- `for`: `TEST-002`
- `required_evidence_shape`: live JSON、HTTP断言、DB/S3/current审计、no-secret和post-cleanup。

### TEST-003
- `links`: `TASK-001`, `REQ-013`, `REQ-014`
- `method`: full regression、lock一致性、11文件scope、protected hashes、docs/hygiene/freshness、L4 independent review和Completion Report。
- `expected_observable_result`: 11产物、2 validators、review 0 findings、报告complete。
- `failure_path_covered`: dependency drift、scope/doc drift、stale receipt和错误完成声明。
- `cannot_prove`: 不证明网页或同步任务。
### EV-003
- `for`: `TEST-003`
- `required_evidence_shape`: manifests/hashes、receipts、review、official report。

### 正式 Validator Manifest
```json
{
  "schema_version": 1,
  "validators": [
    {
      "validator_id": "public-api-offline",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-m", "pytest", "-p", "no:cacheprovider", "tests/api", "tests/content", "tests/inventory", "tests/ingestion", "-q"],
      "cwd": ".",
      "timeout_seconds": 700,
      "invalidation_paths": ["1.md", "pyproject.toml", "uv.lock", "apps", "content", "inventory", "tests", "docs/api/public-api-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": false,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import fastapi, pydantic, httpx, psycopg, boto3; print('ready')"],
      "preflight_timeout_seconds": 30
    },
    {
      "validator_id": "public-api-compose-live",
      "command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "scripts/validate_public_api.py", "--json"],
      "cwd": ".",
      "timeout_seconds": 1000,
      "invalidation_paths": ["1.md", "pyproject.toml", "uv.lock", "compose.yaml", "apps", "content", "inventory", "migrations", "scripts/validate_public_api.py", "docs/api/public-api-v1.md"],
      "validation_kind": "behavior",
      "environment_sensitive": true,
      "preflight_command": ["uv", "run", "--frozen", "--no-sync", "python", "-B", "-c", "import fastapi, httpx, psycopg, boto3; print('python-ready')"],
      "preflight_timeout_seconds": 30
    }
  ]
}
```

| ID | 场景 | 关联 | 通过条件 | 证据 | 不能证明 |
|---|---|---|---|---|---|
| `GATE-001` | API contract/offline | `TASK-001` / `TEST-001` | routes/models/filter/security tests通过 | `EV-001` | 不证明live |
| `GATE-002` | PostgreSQL+MinIO live | `TASK-001` / `TEST-002` | current/Canonical/asset/integrity/cleanup闭合 | `EV-002` | 不证明生产部署 |
| `GATE-003` | formal closure | `TASK-001` / `TEST-003` | scope/docs/review/freshness/report闭合 | `EV-003` | 不证明网页/sync |

# 10. 产物与完成回写
- `required_deliverables`:
  - `pyproject.toml`
  - `uv.lock`
  - `apps/__init__.py`
  - `apps/api/__init__.py`
  - `apps/api/main.py`
  - `apps/api/models.py`
  - `apps/api/repository.py`
  - `apps/api/assets.py`
  - `tests/api/test_public_api.py`
  - `scripts/validate_public_api.py`
  - `docs/api/public-api-v1.md`
- `documentation_impact`: updated；固定公共API、资产、错误、空目录和rights边界。
- `repository_hygiene_requirement`: 仅11个声明文件；无数据库/对象/Compose/runtime/log/secret进workspace；formal evidence写TASK-0014 root；旧任务只读。
- `external_review`: policy=never；真实Compose HTTP/S3加L4 independent review足够。
- `non_completion_rules`: 11/11产物、2/2 validators、Canonical去重、current-only、link_only拒绝、object integrity、secret redaction、docs/review/freshness/report任一缺失不得完成。

### 必交产物
- `pyproject.toml`
- `uv.lock`
- `apps/__init__.py`
- `apps/api/__init__.py`
- `apps/api/main.py`
- `apps/api/models.py`
- `apps/api/repository.py`
- `apps/api/assets.py`
- `tests/api/test_public_api.py`
- `scripts/validate_public_api.py`
- `docs/api/public-api-v1.md`

本卡完成后立即执行TASK-0015最小Next.js公共网页。
