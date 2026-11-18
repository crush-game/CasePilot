# 开发记录

## 规范

2026-11-18 用户授权从 P00 开始实现。每个 P 单元全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 各完成后 push。本阶段未通过验收，不进入下一阶段。用户随后确定仓库为 [crush-game/CasePilot](https://github.com/crush-game/CasePilot)，本地目录暂保留 aftersales-agent。

当前进度：P00～P02 验收通过，尚未开始 P03；未到大阶段 push 节点。

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
