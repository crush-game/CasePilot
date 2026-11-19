# 开发记录

## 规范

2026-11-18 用户授权从 P00 开始实现。每个 P 单元全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 各完成后 push。本阶段未通过验收，不进入下一阶段。用户随后确定仓库为 [crush-game/CasePilot](https://github.com/crush-game/CasePilot)，本地目录暂保留 aftersales-agent。

当前进度：P00～P06 验收通过；P06 已完成真实硅基流动小集及完整回归，按约定中文提交；未进入 P07，未到大阶段 push 节点。

## P00：工程隔离、依赖兼容与框架试验

日期：2026-11-18。验收结论：通过。以下为 P00 当时的交付与限制，后续能力见对应阶段记录。

### 交付与边界

- 新建独立 `aftersales-agent` Git 工程，保留原 `aftersales` 仓库与其脚本，不复制生产账号或执行生产取数。
- FastAPI 配置校验、进程存活/数据库就绪端点；仅允许 Mock provider。业务 API、账号、Worker、业务图和 Alembic 迁移在后续阶段交付。
- Vue 3＋TypeScript＋Vite＋Element Plus 可构建页面骨架；页面明确工单功能尚未开放。
- Python 项目虚拟环境与完整 `requirements.lock`；npm `package-lock.json`；数据库镜像固定版本与 linux/amd64 manifest 摘要。
- Compose 仅绑定本机 55432；开发库 `aftersales` 与测试库 `aftersales_test` 分离。随机凭据写入被忽略的 `.env`。
- 测试使用临时向量表、测试库 `checkpoints` schema 和合成 thread；官方 Saver 串行 setup，同一独占连接同时持有 run 锁并保存检查点。
- 暂停与恢复由两个独立 Python 子进程执行；暂停进程先退出，恢复进程从 PostgreSQL 检查点继续，不依赖内存 Saver。

### 实际验证

以下均为本机实际执行结果，不代表后续业务功能或模型效果：

| 验证命令（工程根目录） | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found |
| `docker compose config --quiet` | 退出码 0 |
| `docker compose up -d --wait --wait-timeout 90` | 隔离数据库 Healthy |
| `.\.venv\Scripts\python.exe scripts/verify_p00.py` | 6 passed；覆盖 liveness/失败 readiness、PG 向量查询、SQLAlchemy/psycopg 查询、成功 readiness、跨进程暂停恢复、锁互斥及断连释放 |
| `npm ci --registry=https://registry.npmjs.org --no-audit`（frontend） | 从锁文件安装 73 个包成功 |
| `npm run build`（frontend，含 `vue-tsc --noEmit`） | 类型检查通过，生产构建成功 |
| `SELECT version()`、`SELECT extversion FROM pg_extension WHERE extname = 'vector'` | PostgreSQL 17.10，vector 0.8.2 |

环境实测：Python 3.13.7、Node 24.16.0、npm 11.13.0、Docker Engine 29.4.3。主要锁定版本：FastAPI 0.164.0、Pydantic 2.14.3、SQLAlchemy 2.1.9、Alembic 1.20.1、psycopg 3.3.9、LangGraph 1.2.22、PostgreSQL Saver 3.2.1、Vite 8.3.8、TypeScript 5.9.3；完整依赖以锁文件为准。

镜像：`pgvector/pgvector:0.8.2-pg17@sha256:e04af45eb526378554a24ed05b37d9ea56fd623feca9adf264d4f47d875c9a93`。当前固定 linux/amd64；其他平台需另外验证镜像与依赖。

### 环境问题与剩余限制

- 首次 venv 创建在 ensurepip 子步骤失败，独立执行 ensurepip 后安装成功；无全局 Python 版本或包修改。
- Docker 起初未启动，已启动 Docker Desktop 并创建本项目独立卷，未改动已有服务和数据库。
- 沙箱内 TestClient 测试未返回，同一测试在本机权限下通过；已停止对应的旧挂起测试进程。正式验收在本机环境执行。
- 默认 npm 镜像不支持 audit API，使用官方 registry 审计。报告 6 个 high 项，均归因于开发依赖链中的 `picomatch<=4.0.7`（[公告](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)）；查询当时最新版仍为 4.0.7。未执行 `audit fix --force`，未把此项描述为已修复。P00 页面不提供外部 glob 输入；后续需跟进上游修复并复验锁文件。
- GitHub 插件身份查询成功；本机 gh 凭据失效，旧公司 GitLab SSH 连接被关闭，不能据此声称 Git 推送可用。新工程未设置远程地址，P00 不到大阶段 push 节点。
- readiness 当前检查数据库/vector；业务 schema、检查点生产初始化与迁移版本检查随后续阶段补齐。
- 此试验验证框架持久化和锁组合，不代表 P02 的任务租约、业务待办投影、崩溃对账或工具副作用恰好执行一次已经实现。

### 后续阶段入口

P01 按技术方案实现业务数据、Alembic 迁移、账号和工单 API，验收包含空库迁移、幂等建单唯一性、列表与版本冲突。本轮不提前实现。

### 参考

实现时核对 [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[PostgreSQL 持久化](https://docs.langchain.com/oss/python/langgraph/add-memory)、[pgvector](https://github.com/pgvector/pgvector)、[Vite](https://vite.dev/guide/)。验收以本机测试输出为准。

## P01：业务数据、迁移、账号与工单 API

日期：2026-11-18。验收结论：通过。仅交付 P01，不包含 Worker 执行与人工恢复闭环。

### 修改与接口

- `backend/app/repositories/`：业务模型与 PostgreSQL 会话；`business` schema 下的账号、会话、工单、事实、run、任务、快照、事件、审计、幂等记录共 10 张业务表。
- `backend/alembic.ini`、`backend/migrations/`：冻结的 `0001_business` 初始迁移，使用事务级迁移锁；可对空库升级并重复执行；不改官方检查点 schema，不提供自动破坏性降级。
- `backend/app/domain/`：角色、优先级、工单/run/任务状态枚举及基础状态转移规则；终态不能任意重开。
- `backend/app/services/`：scrypt 密码摘要、随机数据库会话、事务建单和幂等响应；工单更新使用 `WHERE id AND version`，仅允许更新排队工单元数据，并同步 run/snapshot 的版本。
- `backend/app/api/`：登录、注销、当前用户；建单、列表、详情、增量事件、run 查询、元数据更新。业务角色与知识角色隔离，Cookie 为 httpOnly/SameSite=Lax，写请求校验 CSRF 与显式 Origin；统一错误响应含 request_id，不回传敏感输入或异常栈。
- `backend/app/manage.py`：本地交互创建账号及迁移入口；密码不从命令行参数传入，不设置默认账号密码。
- `backend/app/main.py`、`config.py`、`.env.example`：CasePilot 名称、会话/CORS 配置、业务迁移版本 readiness 检查。
- `backend/tests/`、`scripts/verify_backend.py`：完整后端回归；保留 P00 验收命令兼容入口。未新增 Python 依赖，锁文件保持不变。
- `README.md`、`AGENTS.md`、`docs/technical-plan.md`：同步远程仓库、P01 契约和可复制的启动命令；工作区父级技术方案同步相同契约。

主要数据库约束：每工单至多一个 queued/running/paused run；run 的 thread_id 唯一；任务 run/kind/action 唯一；actor/operation/idempotency-key 唯一；active_run 外键同时检查 run 属于本工单；事实与快照按版本留存。审计服务只追加，不提供公开修改或删除接口。

### 实际验收

| 命令或场景 | 实际结果 |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | 28 passed，14.61 秒；含 P00 回归与 P01 测试，pip check 通过 |
| 随机命名空库首次迁移、重复升级、Alembic `command.check` | 成功；模型与迁移无新增差异；仅清理该测试自己创建并核验名称的临时数据库 |
| 4 个独立客户端并发提交同一建单键 | 4 个 202 返回相同结果，只创建一个工单；普通重复建单核对 ticket/run/task/event/audit/snapshot 各一份 |
| 同键不同请求、不同账号相同键 | 前者 409；后者各自创建工单，无跨账号幂等结果复用 |
| 在快照插入点注入异常后重试 | 首次返回 500，工单和幂等记录均回滚；相同键可成功重试 |
| 同版本并发更新、重复 action、旧版本提交 | 并发仅一个 200，另一请求 409；重复动作不重复审计；旧版本不覆盖新值 |
| 账号停用、会话过期/替换、CSRF/Origin、知识角色访问工单 | 401/403 符合契约；数据库仅保存会话/CSRF 摘要 |
| 列表游标、筛选、增量事件、时间与非法输入 | 通过；原时区/精度保留，数据库时间转为 UTC，无时区输入拒绝 |
| `.\.venv\Scripts\python.exe -m app.manage migrate` | 本项目开发库成功升级至 `0001_business`，无删除或重建 |
| 开发库 `GET /health/ready` | 200；实际查询业务迁移版本为 `0001_business` |

开发中通过首次迁移测试发现并修正了生成代码中的 JSONB Text 命名空间与三个索引命名偏差；未通过清空数据库解决，开发库迁移在测试通过之后执行。

### 交付限制与下一阶段

- P01 建单保存 `QUEUED` 工单、queued run 和 start 任务；无 Worker 消费，不能把 202 视为已开始或已完成调查。
- 前端仍为 P00 骨架。HITL、节点/工具记录、停止与结案、崩溃对账在 P02，操作工作台在 P03；知识与经验表按后续所属阶段迁移新增。
- 附件接口尚未实现，非空 artifact_ids 返回 422。邮箱为常规格式校验，不声称覆盖所有 RFC 地址形式。
- 业务账号共享单一内部工单池，尚无多租户、SSO、密码找回或对外账号注册；日常使用账号需运行 README 的交互式命令自行创建。
- P00 已记录的开发依赖审计问题不在本轮改动范围内；未声称已修复。
- 下一阶段为 P02：独立 Worker、固定 Mock 图、HITL 与对账恢复。本轮停止在 P01 验收与提交边界，不 push。

## P02：Worker、固定 Mock 图、HITL 与对账恢复

日期：2026-11-18。验收结论：通过。交付无真实模型的工单闭环；不进入 P03 页面开发。

### 修改与数据契约

- `backend/migrations/versions/0002_runtime.py`：新增 human_tasks、human_actions、node_runs、tool_executions 共 4 表，以及方案、人工结果、停止请求、resume payload 的兼容字段；旧业务数据保留，初始迁移不改写。业务迁移与官方 Saver setup 分开执行。
- `backend/app/workers/`：独立 Worker、租约心跳、run 会话锁、节点与业务投影、独立对账命令。检查点连接失效停止当前尝试；不透明重连同一旧执行。默认租约 30 秒、约 10 秒心跳；对账读取到期任务的检查点后补业务状态或重排任务，不重新调查整张图。
- `backend/app/agents/graphs/mock.py`：固定 mock-v1 图，按设备/时间缺口暂停，资料齐全后执行两个固定只读 Mock 调查，生成并校验模拟方案。没有调用真实模型、真实企业 API 或语义检索。
- `backend/app/services/human.py`、`workflow_common.py`：认领、补充恢复、停止请求、方案审核、已联系记录、重新调查、显式结案；追加人工来源、审计、版本与快照。恢复保留同一 thread，关键事实修正新建 run/thread。
- `backend/app/api/workflow_routes.py`、`routes.py`、`schemas.py`：人工池、待办详情、人工操作和节点记录；工单详情显示方案、结果、开放待办、停止标识。所有写接口沿用 Cookie/CSRF、角色和 expected_version 校验。
- `backend/app/domain/`、`config.py`、`repositories/models.py`、`main.py`：状态转移、人工待办枚举、预算和租约配置、部分唯一索引及检查点就绪检查。
- `backend/tests/integration/test_p02.py`：Mock 闭环、子进程强制终止、旧执行权拒写、断连、人工权限、预算、图版本及心跳续租测试。测试故障注入仅对本机 aftersales_test 生效，不提供 HTTP 注入入口。
- `README.md`、`.env.example`、`docs/technical-plan.md`：同步 API/Worker/reconcile 启动命令、恢复步骤和 P02 细化契约；父级技术方案同步。未新增依赖，未修改前端源文件或旧 aftersales 仓库。

### 实际验收与证据

本轮最终完整回归为 **44 passed / 98.06 秒**；随后仅新增并单独执行心跳正向续租测试，**1 passed / 4.40 秒**。共 45 个不同测试用例通过；后续完整入口会包含全部 45 项。

| 命令或场景 | 实际结果 |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | 最终 44 项完整回归通过，含 P00/P01；pip check 通过 |
| 加载项目 `.env` 后单独执行 `pytest backend/tests/integration/test_p02.py::test_heartbeat_renews_owned_lease -q` | 1 passed；实际数据库租约被心跳延长，执行权保持有效 |
| 创建→暂停→认领→补充→恢复→方案→审核→已联系→明确解决 | 通过；同一 run/thread，审核通过仍待确认，联系记录后 WAITING_CUSTOMER，人工确认才 RESOLVED |
| 资料齐全的工单 | 固定 Mock 图直接形成 PENDING_CONFIRMATION；没有假装已经解决 |
| 任务认领后、首个检查点前强制终止独立 Worker | 到期对账仅重排任务；新 Worker 执行后出现一个人工待办 |
| 中断检查点已保存、人工待办投影前强制终止 | 对账直接补 WAITING_HUMAN 与唯一待办；重复对账不产生新待办 |
| 只读工具结果入库后、节点检查点前强制终止 | 恢复复用原逻辑工具记录；最终共两个 Mock 工具结果，无重复结果行 |
| 图完成后、方案投影前强制终止 | 对账直接补待确认方案，不重跑调查 |
| resume 已被检查点消费、业务任务尚未完成时强制终止 | 恢复继续剩余节点；旧 action 不提交给第二个暂停点，旧 HTTP 请求仅返回幂等历史结果 |
| 租约到期但旧 Worker 的 run 锁仍存活 | Worker 和对账均无法越过锁领取；旧 token 未被新执行替换 |
| 已生成方案后请求停止，旧执行尝试投影 | 旧执行抛 LeaseLost，方案未写入工单；锁释放后新 Worker 建立人工暂停 |
| 检查点连接断开 | 旧执行的业务写入被拒绝；到期恢复可建立待办 |
| 图版本不兼容 | 禁止直接 resume；原始请求保留，新 run 重新调查可生成模拟方案 |
| 认领权限、旧版本写入、重复恢复、人工未解决结案 | 403/409/幂等符合契约；终态清理活动指针及开放待办 |
| 步数预算/跨轮次上限、固定 Mock 工具失败 | 进入可见人工待办；不无限循环 |
| `.\.venv\Scripts\python.exe -m app.manage migrate` | 本项目开发库升级到 0002_runtime，仅新增表/兼容字段 |
| `.\.venv\Scripts\python.exe -m app.workers.runtime setup` | 官方检查点表串行初始化成功 |
| Worker 与 reconcile 的 `--once --run-id 00000000-0000-0000-0000-000000000000` | 命令启动成功，均返回 processed=false；未消费既有开发工单 |
| 开发库 `GET /health/ready` 与迁移版本查询 | 200，实际版本为 0002_runtime |

开发中还通过故障回归修正了“尚无 checkpoint_id 的初始配置”处理；对账补齐节点时接受空检查点，不把任务已认领误当成图已启动。节点 input_refs 保存执行时的 case_version，已通过断言核对。

### 边界与后续

- 本阶段是固定 Mock 工程闭环，无模型效果、真实诊断或业务收益结论。Mock 引用只是测试来源标记，不等于生产资料引用校验；真实证据治理在后续阶段建设。
- 前端仍为骨架，接口可用；日常账号需按 README 交互创建。P03 才实现业务人员工作台。
- 同 run 恢复只支持小范围设备/时间补充，真实反馈选择、附件、真实工具与模型在后续阶段接入。
- 节点记录为检查点中完成逻辑步骤的幂等投影；任务 attempt 保留重新领取次数，不宣称每个外部请求恰好执行一次。
- 对账覆盖该协议中“持久检查点已写、任务尚未提交业务投影”等到期运行任务；不承诺恢复数据库丢失、人工删表或存储整体不可用时成功处理。
- 没有外部发送接口；contacted 来自业务人员显式记录。结案不自动生成成功经验，经验候选在 P09 实施。
- 下一单元为 P03，当前停止在 P02 验收和中文提交边界，不 push。

## P03：前端最小工作台

日期：2026-11-19。验收结论：通过。基于已有未提交 P03 草稿补齐并验证，未覆盖或重置这批改动；本阶段不进入 P04。

### 修改与交付

- `frontend/src/views/`：登录、列表/筛选/分页、新建、详情时间线与来源抽屉、人工池；人工操作覆盖认领、补充恢复、审核、联系记录、重新调查、结案。
- `frontend/src/components/`、`App.vue`、`style.css`、`public/favicon.svg`：沿用草稿布局，补齐深色侧栏与浅色内容区、表单/表格/状态/反馈样式、375px/横屏适配、减少动画偏好和本地 SVG。未更换 Vue/Element Plus 栈，未使用外部字体或生产数据。
- `frontend/src/api/`、`stores/`、`router/`、`composables/`、`utils/`：Cookie/CSRF 会话、恢复与过期提示、错误/15 秒超时、稳定动作标识、前台/后台轮询、离线取消与重连、离开页面停止。409 保留草稿并阻止静默覆盖，未确认结果时不随轮询改动写版本。
- `backend/app/api/routes.py`、`schemas.py`：详情增加最新事实来源和 latest_run_id；终态仍返回最近 run。响应 OpenAPI 将序列化默认字段声明为必有字段，匹配实际响应；没有业务 schema/迁移变化。
- `scripts/export_openapi.py`、`frontend/scripts/generate-api.mjs`、`frontend/openapi.json`、`src/types/`：自动生成 API 类型与一致性检查，避免手写接口类型漂移。
- `frontend/tests/unit/`、`frontend/scripts/e2e.mjs`、`scripts/browser_fixture.py`：轮询与请求单测、独立测试服务和实际浏览器验收；后端增加 `test_p03.py` 核对新响应。
- `package.json/package-lock.json`：保留草稿已选择的 Vue Router 5.5.1、Pinia 4.1.0、Vitest 5.1.1、Playwright 1.65.1、openapi-typescript 7.13.0，并提供 api:generate/api:check/test:unit/test:e2e。
- README、技术方案与工作区父级技术方案同步启动、契约和验收方式；截图/临时浏览器文件加入 Git 忽略。

### 实际验证

| 命令或场景 | 结果 |
|---|---|
| `npm run api:generate`、`npm run api:check`（frontend） | 类型已生成；与当前后端 OpenAPI 一致 |
| `npm run typecheck` | 通过，包含页面与单元测试 TypeScript |
| `npm run test:unit` | 7 passed；覆盖动作幂等标识、CSRF/会话失效、超时/主动取消、前后台轮询、断网/重连、取消旧请求和停止轮询 |
| `npm run build` | 类型检查与 Vite 生产构建通过；按页面拆分产物 |
| `npm run test:e2e` | 9 个真实 Chrome 场景通过，无未捕获浏览器脚本错误 |
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | 45 项既有后端回归通过，100.26 秒 |
| 加载 `.env` 后单独执行 `pytest backend/tests/integration/test_p03.py -q` | 2 passed / 2.79 秒；终态 latest_run_id 与人工事实来源保留，重新调查后仅返回字段最新事实 |

后端共 47 个不同用例通过（45 项既有回归＋2 项新增响应契约）。浏览器 9 场景为：登录/错误密码/路由保护/刷新；分页筛选及离开页面停止轮询；表单校验与重复提交；人工池/认领/离线草稿；恢复/重连/增量时间线/来源抽屉；409 草稿保留后手动刷新重试；审核/联系/结案/终态轨迹；375px/横屏/减少动画；会话失效提示与知识角色权限。

已实际查看桌面详情、小屏详情及 CLI 登录页截图。报告、截图位于 `output/playwright/`，仅含模拟数据，不进入 Git。验收服务使用 18003/15173，执行完毕关闭自己创建的服务和浏览器；未连接生产。

开发中修复类型可选性/数组兼容问题，以及首次恢复时过期提示被路由守卫丢弃的问题。首轮浏览器脚本曾把登录页 redirect 参数误判成已登录 URL，已改为精确路径判断；不将脚本误判算作业务失败。

### 边界

- 工作台对接 P02 固定 Mock 图，未接真实模型、真实知识或日志；来源抽屉明确显示模拟引用，不称为已验证业务证据。
- 修改、接管、重新调查等前端入口沿用后端权限和版本限制。浏览器主闭环已验收，P02 的运行停止、断连、锁和崩溃恢复仍由后端回归覆盖。
- 没有账号自助注册和外部发送接口；本地账号需按 README 创建。日常使用需分别启动 API、Worker、reconcile 和前端。
- 草稿保留限当前页，不承诺重新加载/退出登录后保留。新标签页没有 CSRF 时需要登录，Cookie 令牌不在 JS 中读取。
- `ui-ux-pro-max` 附属搜索脚本在当前安装中是失效文本指针；按 SKILL 的布局/可访问性规则实施，并通过实际浏览器截图检查。未声称搜索脚本成功执行。
- P00 已记录的开发依赖审计问题未在本阶段宣称修复。本轮仅完成 P03、中文提交，不 push；下一单元为 P04。

## P04：Mock 场景、工具注册、模型统一接口

日期：2026-11-19。验收结论：通过。本阶段开始时仓库干净，基于 P03 提交 `1b0f370` 开发；仅完成 P04。

### 修改与交付

- `backend/app/tools/`：六个代码白名单工具、封闭 Pydantic 输入/输出、Mock Adapter、日志基础脱敏。返回 status、data_refs、error_code、retryable、来源记录/查询/模式与 fetched_at；分别表达无反馈、无匹配数据、无附件、下载/解析失败、认证、限流和超时。
- 客户引用必须匹配执行器绑定身份，关联邮箱不作为工具参数；已绑定设备不可被其他设备替换。下载/窗口使用受控会话句柄，不接收任意路径或 URL。反馈先设备/平台再时间筛选，多候选和缺字段保持人工缺口；同范围知识冲突返回双方。
- `backend/app/providers/`、`config.py`、`.env.example`：统一同步/异步模型入口、角色 profile、超时和结构化 JSON/schema 校验、证据引用白名单。实现确定性 Mock 的方案/领域输出，保留 parse/supervisor 角色配置；未配置供应商/模型明确失败，不回落。usage 标记 simulated，记录角色/模型/耗时，Token 和费用为 null。
- `workers/context.py`、`projection.py`、`agents/graphs/mock.py`：工作台固定图的两个内部步骤映射到注册工具，方案生成使用统一 Client；工具结果仍持久缓存，节点记录保存完成逻辑模型调用。保留 mock-v1 节点/暂停协议与旧缓存键，无业务迁移或公开 API 变化。
- `fixtures/runtime/` 与 `fixtures/evaluation/`：12 个独立场景族，公开资料/动作与隐藏标注分开；只有评测入口在执行结束后读取标签。模型只收到当前工单和本次工具允许返回的脱敏数据，不接收完整场景文件。
- `backend/app/eval/`：正式 smoke 命令和脱敏报告。S01～S10 覆盖咨询、缺型号/版本、日志、FAQ、多领域、降级、领域缺证据、异常、多设备和政策冲突；S11/S12 另调用真实 PostgreSQL/独立 Worker 的人工、幂等、迟到、预算和崩溃恢复测试。
- `test_tool_contracts.py`、`test_p04.py`：增加 46 项单元与 4 项集成验证；`test_p02.py` 增加未来任务回归并使测试等待符合真实轮询行为。
- README、fixtures 说明、技术方案及父工作区方案同步接口、数据边界和命令；报告路径加入 Git 忽略。未增加依赖或修改全局环境。

### 实际验证

| 命令或场景 | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | pip check 通过；98 passed / 118.22 秒，包含此前 47 项与本阶段 51 项不同用例 |
| `.\.venv\Scripts\python.exe -m app.eval replay --suite smoke` | 12/12 种子契约通过；S11 为 3 项、S12 为 7 项真实数据库/进程检查，全部通过；报告 passed=true |
| 隐藏标签隔离 | 12 场景回放时禁止读取 evaluation 目录，均完成；实际工具/模型轨迹不含隐藏探针或假敏感标记 |
| 工具边界 | 非白名单工具、额外邮箱/路径/URL、其他客户/设备、非法时间窗、类型不符与跨会话窗口均被拒绝；不回显异常私密文本 |
| 工具失败和证据 | 验证认证/限流/超时、无反馈/无匹配/无附件、下载/解析失败、领域不支持；来源和已查看范围保留，规则与模型分析分开 |
| 模型边界 | 验证实际异步超时、坏 JSON、缺字段/额外字段、真实模式伪装、越界引用和未配置 provider；Worker 的失败转可见人工待办 |
| 旧 mock-v1 兼容 | 旧最小工具结果缓存继续复用；P02/P03 原闭环、锁、失权、恢复与终态轨迹回归通过 |
| `npm run api:check`、`npm run typecheck`（frontend） | API 类型一致、TypeScript 通过 |
| `npm run test:unit`、`npm run build` | 7 passed；Vite 生产构建通过 |
| `npm run test:e2e` | 9 个真实 Chrome 场景全部通过，包含登录、列表、建单、人工恢复、离线/409、来源、审核/联系/结案、小屏与会话权限 |
| `git diff --check`、方案副本 SHA256 | 差异空白检查通过；项目与父工作区技术方案一致 |

smoke 的 10 项工程检查是完整后端回归中的子集，不另累计为新的不同测试。报告位于 `output/evaluation/smoke.json`，浏览器报告位于 `output/playwright/`，均不进入 Git；服务结束后关闭脚本自行启动的 API、前端和浏览器。

验收过程中先修正新增测试的语法笔误和同名模块收集冲突。后续捕获本机数据库时钟回拨现象：任务 available_at 为 13:44:15.202831 UTC，而子 Worker 查询时 clock_timestamp 为 13:44:15.041118 UTC，暂时无可领取候选。原测试把一次空轮询当成处理失败。先以“未来 5 秒才可领取”的确定性用例重现失败，再让故障注入使用正式轮询 Worker、一次性测试辅助函数对仍待执行任务有界等待；完成/暂停时的空轮询仍原样返回，原有业务、锁和幂等断言保留。该回归随后通过，最终完整回归及 smoke 均通过。临时生产代码诊断已移除，未改变 Worker 领取协议或系统时钟。

### 边界

- 这里是确定性 Mock 资料/动作脚本回放，不是模型自主工具选择、语义检索、真实根因诊断或真实业务效果评测；真实模型、知识入库和完整故障子图按后续阶段建设。
- 常规工作台仍是两个固定 Mock 调查步骤；六工具的完整组合在独立回放中执行，不把这一步说成已具备真实 Supervisor。
- 隐藏标注通过代码依赖和数据传递隔离，当前同账号本地文件没有 OS ACL 隔离。部署时 Agent 只挂载 runtime，评测进程另挂载 evaluation；当前工具不提供任意文件读取。
- 日志脱敏针对当前样例契约验证，不声称已覆盖所有企业日志格式。未配置真实模型、企业权限或生产凭据；未连接外部模型或生产取数。
- 记录的是完成逻辑节点中的 Mock 调用，不宣称崩溃重放下每个物理模型请求恰好执行一次，也不报告真实 Token、费用或业务收益。
- 本轮仅中文提交 P04，不 push、不进入 P05。下一单元为 P05：文档入库与 BM25。

## P05：文档入库与 BM25

日期：2026-11-19。验收结论：通过。基于 P04 提交 `48251ea` 开发，开始时仓库干净。本轮仅完成 P05，不进入 P06。

### 修改与交付

- `migrations/versions/0003_knowledge.py`、`repositories/models.py`：新增版本化文档、片段、持久化入库任务和知识索引快照四张表。原始字节/checksum 留存；doc_key/version 唯一、同键活动版本唯一，历史版本和引用保留。业务迁移版本更新为 `0003_knowledge`。
- `api/knowledge_routes.py`、`knowledge/schemas.py`、`services/knowledge.py`：multipart UTF-8 MD/TXT 上传与显式适用范围、上传幂等/同版去重、文档/失败任务分页查询、失效、失败重试、脱敏原文预览、检索和引用回源。写入仅 knowledge_admin，business 可检索/读引用；沿用 Cookie、CSRF、动作幂等和 revision 检查。
- `knowledge/text.py`：标题/条目上下文、代码围栏和行号识别，长段 600～1000 字符、100 字符重叠，保留父段范围与相邻引用。使用确定性汉字单字/二元词项和完整型号/错误码分词；BM25 固定 k1=1.2、b=0.75，正值 IDF，模式明确为 bm25。
- `workers/ingestion.py`、`config.py`：独立持久化入库队列、阶段、运行锁、租约/token、有限尝试和失败历史；解析/切块/索引/发布可追踪。新版本、旧版本替换、片段和索引快照同事务发布，失败保留旧活动版本；崩溃后重新领取到期任务，归档取消任务并阻止迟到发布。
- `knowledge/index.py`：PostgreSQL 持久快照，按发布版本/分词版本/算法/语料指纹/checksum 校验并重建。检索以数据库活动状态和适用范围/有效期为准；未知条件保留缺口，历史引用明确 usable=false。返回文档版本、原文/片段 hash、标题层级、行号和相邻来源。
- `knowledge/adapter.py`、`tools/contracts.py`、`registry.py`：数据库知识适配接入已有白名单工具；返回真实执行的 BM25 结果、索引版本、模式和引用，数据仍为 mock。固定 mock-v1 图保留原资料和检查点兼容行为，未把固定草稿说成基于新入库文档生成。
- `workers/context.py`、`agents/graphs/mock.py`：修复完整回归中暴露的 Saver 后台 pipeline 写入与连接探针并发问题；探针共享当前锁定版本官方 Saver 的连接锁，保留原运行锁、租约与失权校验，不升级 LangGraph/psycopg。
- 新增 13 项文本/分词单测、17 项 P05 集成用例与 1 项 P02 连接并发回归；新增公开模拟文档/元数据。前端重新生成 OpenAPI/TypeScript 类型，未重做工作台或增加知识管理页面。
- `python-multipart==0.0.34` 锁入 pyproject/requirements，仅安装到项目 `.venv`；README、配置示例、项目与父级技术方案同步接口、限制和使用方式。

### 实际验证

| 命令或场景 | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | pip check 通过；129 passed / 134.32 秒，包含此前 98 项和本阶段 31 项不同用例 |
| 空库/兼容迁移与 Alembic check | 通过，随完整后端回归执行；新增四表，不修改旧迁移，不破坏性降级 |
| MD/TXT 上传→排队→发布→关键词检索→引用/原文预览 | 通过；发布前不搜索，中文词项、型号、错误码可命中，回源版本/hash/行号对应，基础脱敏生效 |
| 版本/失效与失败任务 | 同版复用、不同内容拒绝覆盖；构建失败保留旧活动版本，新版原子替换；归档不再召回，历史引用保留；失败阶段/错误码可查，可重试故障经显式重试成功 |
| 元数据/权限/并发 | 未知型号/版本/地区/渠道不选特定范围；有效期/不兼容范围排除；业务角色不能上传/管理原文；并发重试仅一个成功、另一个409，旧排队版本不回滚新发布版本 |
| 索引重建 | 独立新进程检测损坏/旧版本快照后重建，命中引用和发布版本保持一致 |
| 入库进程故障 | 真正终止独立 Worker，覆盖领取后和发布前；到期任务重领成功，运行锁存活时不越权领取，无半成品索引；取消后的旧执行不能发布，尝试上限可见停止 |
| Saver 连接并发 | 确定性回归先捕获探针插入 Saver 临界区，再验证等待同一连接锁；原失权投影用例及全部 P02 恢复回归通过 |
| `npm run api:generate`、`npm run api:check`、`npm run typecheck`（frontend） | 契约/类型已更新，与后端一致，TypeScript 通过 |
| `npm run test:unit`、`npm run build` | 7 passed；Vite 构建通过 |
| `npm run test:e2e` | 9 个真实 Chrome 场景通过；登录、列表、新建、人工恢复、离线/409、来源、联系/结案、小屏和权限仍正常 |
| 本机开发库升级及 readiness | 核验 host 为本机、database 为 aftersales 后迁移；版本 `0003_knowledge`，既有 Ticket/Run 数量保持，readiness=200 |
| 示例与文档 | 示例 metadata 校验、MD 解析为3个片段、上传示例 PowerShell 语法检查通过；项目/父级方案 SHA256 一致 |

修正过两处测试期望：BM25 手算值经独立公式复核；Windows 上传路径由 multipart 库标准化为 basename，测试改为检查保存的文件名而非把它误判为服务器路径读取。并发重试发现 SQLAlchemy identity map 保留锁前旧对象，确定性回归先出现两个202，修复锁定后刷新后变为一个202/一个409。完整回归还复现了旧检查点连接并发错误，核对当前 Saver 源码后加共享锁，回归先失败后通过；最终完整129项通过。

浏览器验收结束后脚本关闭自行启动的 API、前端和浏览器；输出保留在 Git 忽略的 `output/playwright/`。没有创建日常账号或往开发库导入模拟文档，上传示例供使用者显式操作。

### 边界

- 只有 BM25 功能路径，尚无真实 embedding、向量融合或 rerank；分词为确定性字/二元词项，不声称达到词典分词或语义检索效果，也不报告召回率/业务收益。
- 语料仍按 mock 标记。知识管理通过 API 使用，工单固定 Mock 图未切换为自主知识调查，P07 再接入调查决策；当前结果不代表基于新文档的模型回答效果。
- 小规模原型采用数据库快照全量扫描和发布事务锁，未进行大规模吞吐评测。文件限制为1 MiB、单行4096字符、最多2000片段；不支持 PDF/DOCX/OCR。
- 原文不可变：无效编码等源文件错误上传新版本，暂时处理故障可显式重试，最多5次执行尝试；归档后不能被重试自动重新发布。
- 基础脱敏不宣称覆盖所有企业文档/日志格式。没有连接生产数据或外部模型；开发库仅新增兼容表，未删除既有业务数据。
- 本轮仅中文提交 P05，不 push。下一单元为 P06：真实模型、embedding、pgvector 与 rerank。

## P06：真实模型适配、pgvector 与混合检索

日期：2026-11-19。验收结论：通过。基于 P05 `22c65c9` 开发，开始时仓库干净。用户明确采用硅基流动并授权首次5元程序预算，随后在项目 `.env` 配置专用 Key；真实服务小集、本地契约及完整回归均通过。本轮仅完成 P06，中文提交，不 push、不进入 P07。

### 修改与交付

- `providers/configuration.py`、`config/providers.siliconflow.json`、`.env.example`：独立公开配置和项目 SecretStr 密钥；默认硅基流动聊天 Qwen3.5-35B-A3B、1024维 Pro/bge-m3 与 Pro/bge-reranker-v2-m3，可按角色覆盖模型。输入/输出上限、超时、币种、费率/配置版本显式校验，聊天关闭思考输出。该配置通过真实接口小集，作为后续效果评测基线，不作为效果结论。
- `providers/remote.py`、`client.py`：异步 HTTP 协议适配和 JSON/schema、data_source、引用白名单检查；错误安全编码、响应大小/维度/非有限值/重复索引校验。瞬时错误至多一次重试、JSON 至多一次修复；每次物理请求留记录，无密钥/预算不调用，不回落到 Mock。业务 data_source 与 inference_mode 分开，旧 mock-v1 检查点兼容。
- `providers/ledger.py`、`repositories/models.py`、`0004_providers.py`：共享预算、调用审计、向量 profile、向量和构建记录五张表。请求前锁预算并预留调用数/Token/费用，完成后对账；未知费用保留 null 和预留风险，不记成免费。审计不保存 Key、原始请求/响应正文，保留 hash、供应商请求 ID、公开配置和用量。调用排序使用预算内预留序号，不依赖可能回拨的时钟。
- `knowledge/hybrid.py`、`index.py`、`schemas.py`：按范围过滤的 BM25/pgvector 精确余弦各20候选、RRF k=60、预算内可选重排、最多6段。profile 包含端点/模型/维度/预处理/执行模式，契约和真实向量隔离；完整覆盖且语料版本不变才原子切换，失败保持旧发布。检索网络调用不持发布锁，返回前核对发布版本/profile，拒绝归档后的迟到结果。
- `workers/ingestion.py`、`knowledge/adapter.py`、`tools/contracts.py`：混合模式新文档先生成同 profile 向量、调用前续租，再与片段及发布版本同事务提交；失权或 profile 改变不发布。API 和白名单知识工具透传 profile、执行模式、候选数与用量，数据库适配名称更新为 knowledge-index-v1。
- `providers/manage.py`、`eval/live.py`：检查配置、显式共享预算/索引/审计命令；真实小集仅发送6份公开虚构资料，在单独本机验证库执行6个查询/重排和2份草稿，默认5元/60调用/50万Token/600秒。无 Key 在建库/网络前停止；契约执行始终 real_acceptance=false。真实小集的账本库与忽略的报告已留存，详情见下方实际验证。
- 前端 OpenAPI/TypeScript 重新生成；README、方案、配置示例同步。httpx 作为运行依赖使用已有锁定的0.28.1，无新增全局安装。

### 实际验证

| 命令或场景 | 结果 |
|---|---|
| `.\.venv\Scripts\python.exe scripts/verify_backend.py` | 最终 pip check 通过；158 passed / 146.64 秒，覆盖原129项及新增29项 |
| 工具追溯字段补齐后相关回归 | 75 passed / 13.82 秒；包含全部工具单测、P05 数据库工具调用和P06集成测试 |
| Provider 配置及无 Key 边界单测 | 8 passed / 1.79 秒；新增禁止数据库连接/建库/ProviderSession 的替身，确认无 Key 返回 PROVIDER_KEY_MISSING、real_acceptance=false |
| HTTP 契约与预算 | JSON一次修复/二次非法停止、401不重试、429/503/实际异步超时最多一次重试；预算并发只允许一次预留，Token/费用不足时零请求；重试预算耗尽保留首个调用费用，缺失 usage 不记零 |
| pgvector/发布边界 | 向量乱序回包归位/归一化、错误维度/零向量拒绝、profile/dimension 数据库约束、RRF去重、可选重排、重复 rerank 索引拒绝；切换失败保留旧活动索引、新文档同 profile 发布、重排期间归档后不返回旧结果 |
| 完整小集的 HTTP 模拟执行 | 6查询/2草稿完成，明确 inference_mode=contract、real_acceptance=false，不能当真实服务验收 |
| `npm run api:generate`、`npm run api:check`、`npm run test:unit`、`npm run build` | 契约一致，7单测通过，TypeScript及Vite构建通过 |
| `npm run test:e2e` | 9个实际 Chrome 场景通过；测试脚本关闭自行启动的 API/前端/浏览器 |
| 本机开发库迁移及 readiness | 核验本机 aftersales 后升级到0004_providers；Ticket/Run/知识文档数量保持，readiness=200 |
| `python -m app.providers.manage check-config` | 用户配置后 key_configured=true，仅打印公开模型名及布尔状态 |
| `python -m app.eval live --suite p06` | 真实硅基流动小集通过，passed=true、real_acceptance=true；6份资料/1024维向量、6次hybrid检索及rerank、2份JSON草稿；15次调用全部成功，无重试或JSON修复 |
| 真实费用/追溯 | 供应商全部返回usage，共10564 Token；配置费率估算CNY 0.00602264，低于5元预算；15条供应商请求ID、响应hash及调用账本齐全，未把程序估算当平台账单 |
| 真实数据库只读复核 | profile 为 real、维度1024、向量6条、调用15条、index_version=7；与报告一致 |

真实验收报告：`output/p06/aftersales_p06_live_c16befd0b25d4e68914712ad7cc43f3d.json`（Git忽略）。隔离审计库同名（去掉`.json`）；build_id=`e94cb8c0-38c6-4e99-b678-7dba58136433`，profile_id=`59a6b874-e537-46f1-9961-d3203a054d5d`。聊天/embedding响应模型名与配置一致；rerank响应不带模型名，保存请求profile及供应商请求ID，不补造served_model。草稿引用均来自本次检索白名单，data_source=mock、inference_mode=real、reviewed=false。

### 阶段出口与交接

- P06 验收条件均满足：真实服务小集通过；JSON校验/修复、超时、重试、共享费用预算和混合检索可追溯；无Key停机通过独立契约验证。密钥不输出、不提交；没有连接生产数据。
- 本轮真实验证只使用独立审计库，开发库保留原有资料与已发布模式，未把整个工作台切成真实模型。后续使用真实检索需显式建立索引并配置有效共享预算，不能复用已过期的小集预算。
- 仅中文提交 P06，不 push。下一开发单元为 P07：Supervisor 与知识调查子图，需另行继续该阶段。

限制：当前只验证原型契约与小语料索引机制，未测真实模型效果、吞吐或生产资料；pgvector 为精确扫描，无 HNSW。费用按公开配置估算，不等于平台账单硬封顶。显式全量索引构建被杀后可重跑复用缓存，旧构建可能保留 running，不声称有自动构建对账；正式入库任务仍沿用租约恢复。固定工单图仍是 Mock，未实现 P07 自主 Supervisor。
