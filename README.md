# CasePilot 售后工单系统

面向企业售后场景的课题原型，采用模拟数据。[GitHub 仓库](https://github.com/crush-game/CasePilot)。开发基线见 [技术方案](docs/technical-plan.md)，阶段证据见 [开发记录](docs/development-log.md)。旧 `aftersales` 仓库仍作为只读参考，不在此工程中执行其生产取数脚本。

## 本地启动（PowerShell）

环境：Python 3.13、Node 24、Docker Desktop（Linux 容器）。依赖仅安装到本工程；数据库端口默认 55432，仅绑定 127.0.0.1。开发库 `aftersales` 与测试库 `aftersales_test` 独立。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e ./backend
pwsh -File scripts/bootstrap.ps1
docker compose config --quiet
docker compose up -d --wait
.\.venv\Scripts\python.exe -m app.manage migrate
.\.venv\Scripts\python.exe -m app.workers.runtime setup
.\.venv\Scripts\python.exe -m app.manage create-user --login operator --role business
Push-Location frontend
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe scripts/verify_backend.py
```

首次建库由 Docker 初始化脚本创建 vector 扩展和独立测试库；已有卷不会重复执行初始化脚本。业务迁移使用 `business` schema，并在事务内串行升级；重复 migrate 保留现有数据。迁移不执行官方 Saver setup，不自动降级或删除数据。不要为修复迁移删除数据库卷。

创建账号时交互输入并确认密码（10～128 字符，不回显），账号名使用 3～64 位小写字母、数字、下划线、点或短横线。已有账号不会被覆盖。`business` 可处理内部工单池；`knowledge_admin` 可登录，但不能访问工单接口，知识管理能力在后续阶段开放。仓库无默认明文密码。

验收脚本自动迁移独立测试库，并以随机命名的空数据库测试首次迁移，结束后仅清理其自行创建的临时库；测试不清空开发库。P00 命令 `scripts/verify_p00.py` 保留兼容入口，现同样执行完整后端回归。

启动 API 和前端分别使用两个终端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev
```

`GET /health/live` 只检查进程；`GET /health/ready` 检查数据库、vector 扩展、业务迁移版本和检查点表。前端工作台默认访问 `http://127.0.0.1:5173`，与 API、Worker、对账循环配合即可处理工单。模型和企业数据只能配置为 `mock`，不请求外部模型或生产业务接口。

另开两个终端分别启动 Worker 和独立对账循环：

```powershell
.\.venv\Scripts\python.exe -m app.workers.runtime worker
```

```powershell
.\.venv\Scripts\python.exe -m app.workers.runtime reconcile
```

启动前只运行一次 `setup`，官方 Saver 会串行初始化/升级 `checkpoints` schema；不要让每个 Worker 自行 setup。Worker 从数据库领取任务，默认租约 30 秒，心跳约 10 秒。对账扫描租约到期的运行任务，先取得 run 锁再读检查点：已暂停/完成则补业务状态，未完成则重新排队。对账本身不执行调查图。`Ctrl+C` 停止循环；异常终止后重启同一命令即可，租约未到期时需等待对账。

排查单个 run 时可单次执行，不输出客户内容或凭据：

```powershell
.\.venv\Scripts\python.exe -m app.workers.runtime reconcile --once --run-id <run_uuid>
.\.venv\Scripts\python.exe -m app.workers.runtime worker --once --run-id <run_uuid>
```

返回的 `processed` 表示本次是否取得任务进行处理，最终业务状态以工单查询结果为准。

## P01 API 使用

完整字段与响应可在启动后的 `/docs` 查看。统一前缀 `/api/v1`：

- `POST /auth/login`：JSON `login`、`password`，返回 `user` 和 `csrf_token`，设置 httpOnly 会话 Cookie；客户端保存 Cookie 并在写请求携带 `X-CSRF-Token`。会话默认 8 小时；重新登录会替换当前 Cookie 对应的旧会话。
- `GET /auth/me`、`POST /auth/logout`：查询当前账号、注销会话。注销同样要求 CSRF。
- `POST /tickets`：携带 `Idempotency-Key`，JSON 至少含 `feedback_text` 与 `customer_email`，返回 202 和唯一的 ticket/run/task 标识。同账号同键同请求返回原结果，同键不同内容返回 409。
- `GET /tickets`：cursor/limit 分页，limit 默认 20、最大 100，支持 status/priority/assignee_id 筛选。使用 next_cursor 时保持筛选条件一致。
- `GET /tickets/{id}`、`GET /tickets/{id}/events?after_id=0`、`GET /runs/{id}`：工单详情、增量事件、运行详情。
- `PATCH /tickets/{id}`：仅排队状态可修改 priority/assignee_id；需 `action_id`（UUID）、`expected_version`。重复动作返回原结果，旧版本返回 409；同步更新待执行 run 的版本与快照。优先级为 low/normal/high/urgent，assignee_id 为 null 可取消分配。

P01 尚无附件上传，`artifact_ids` 只接受空数组。`occurred_at` 必须带时区，可用 `occurred_at_precision` 声明 minute/second 精度。禁止通过建单或更新输入直接设置工单状态、真实数据模式或任意事实。

本地 HTTP 开发默认 `AFTERSALES_COOKIE_SECURE=false`；HTTPS 部署须配置为 true，且配置明确的 `AFTERSALES_ALLOWED_ORIGINS`。该变量为 JSON 数组，默认只允许本机 5173/8000，不接受通配符。

停止本项目数据库：`docker compose stop`（保留数据）。不执行 `down -v`。

## P02 人工闭环与恢复

固定 Mock 图依次检查设备和发生时间，缺失时进入 `WAITING_HUMAN`。这只是工程闭环的规则流程，尚无真实模型、语义检索或真实日志诊断。Mock 方案和回复均带模拟标记；`[MOCK_ERROR]` 测试文本可触发固定工具失败路径，后续场景回放在 P04 建设。

1. 建单后启动 Worker；有完整设备/时间时直接生成待确认方案，否则持久暂停并建立人工待办。
2. `GET /human-tasks` 查询人工池，默认返回开放待办，可用 status/assignee_id 筛选，cursor 为返回的 UUID 游标。`GET /human-tasks/{id}` 返回缺口、认领状态、当前 expected_version。
3. `POST /human-tasks/{id}/claim` 认领，JSON 为 action_id＋expected_version；其他人已认领或版本失效返回 409。
4. `POST /human-tasks/{id}/resume` 补充后排队恢复，只有认领人可操作。除 action_id、expected_version 外，facts_patch 支持 device_ref、occurred_at、occurred_at_precision；补充设备和时间可一次完成，也可以分两次暂停完成。替换已有关键事实请重新调查；非空 selected_feedback_ref 尚不支持。
5. Worker 使用同一 run/thread 和 `Command(resume=...)` 继续。恢复动作已被检查点消费时不会再次提交给后续暂停点。生成方案后为 `PENDING_CONFIRMATION`，详情返回 solution_json，run 详情返回节点记录与检查点摘要。
6. `POST /tickets/{id}/review` 用 decision=approve/revise 审核或修改 reply_draft，审核通过仍为待确认；`POST /tickets/{id}/customer-feedback` 用 outcome=contacted＋reason 记录业务人员已联系客户，此时才进入 `WAITING_CUSTOMER`。系统没有外部发送接口。
7. `POST /tickets/{id}/close` 明确 outcome=resolved/unresolved＋reason，分别进入已解决/未解决结案，清理活动指针、开放待办和待执行任务。暂停中的工单先认领；运行中的工单先请求停止。

上述写操作都携带 action_id、expected_version 和 CSRF，重复同一动作返回原结果。`customer-feedback` 的 resolved 显式调用结案规则，unresolved 创建新调查 run；均保留人工来源和原因。首版不自动生成成功经验。

`POST /tickets/{id}/takeover` 携带 reason 请求停止并撤销旧执行权。详情先显示 cancel_requested，待 run 锁释放且 Worker 保存人工暂停后才能修改关键事实。不会在锁仍被旧执行占有时强行接管。运行停止后可用 `POST /tickets/{id}/reinvestigate`（reason＋可选 facts_patch）修正关键型号或时间，旧 run 标 superseded，新 run 使用新 thread；旧记录仍可查询。

Mock 每轮默认最长 300 秒、24 个完成节点，最多 5 个自动轮次。等待人工不计入下一轮时间；每次恢复建立新预算轮次并保留历史。预算耗尽、固定工具失败或框架异常都会转人工。检查点缺失或图版本不兼容的待办禁止直接 resume，可人工结案或重新调查。

运行回归：`.\.venv\Scripts\python.exe scripts/verify_backend.py`。P02 测试会启动独立 Worker 子进程并真正强制终止，覆盖认领后、工具写入后、检查点中断/完成后、resume 已消费后的故障点；故障注入仅允许本机独立测试库。

## P03 工作台与前端验收

页面包含登录、工单列表、新建、详情时间线、人工待办和结果确认。业务账号可认领、补充恢复、审核/修改回复、记录已联系客户、重新调查及明确结案；知识管理账号仅显示当前无工单处理权限。界面固定标明模拟数据，不把审核通过显示成已解决，也不显示未实际发送的消息。

详情保留当前事实来源与最近一次 run；终态工单仍可查看原调查轨迹。页面每约 2 秒刷新，隐藏后退避到 30 秒，离开页面停止。断网时保留已显示数据、暂停写操作，恢复后按事件游标补取。人工输入不会被后台轮询覆盖；409 时保留当前页草稿，显式刷新状态后再提交。草稿仅在当前页内存中保留，不承诺刷新/退出登录后保留。

会话使用后端 httpOnly Cookie，CSRF Token 仅保存于当前标签页 sessionStorage。刷新可恢复同一会话；会话失效跳回登录并显示提示。新标签页未携带 CSRF 时需要重新登录。请求默认 15 秒超时，结果未知时沿用相同操作标识重试，或先刷新确认；不自动将写操作改成新的请求。

API 类型从后端 OpenAPI 生成；修改公开响应后运行生成命令。详情响应增加 latest_run_id 和当前 facts，无数据库迁移变化。

```powershell
Set-Location frontend
npm run api:generate
npm run api:check
npm run typecheck
npm run test:unit
npm run build
npm run test:e2e
```

`test:e2e` 用 Playwright 启动实际浏览器、独立 API 18003 和前端 15173；仅操作配置中的本机 `aftersales_test`，生成随机模拟账号和列表工单，结束后关闭自行创建的服务。需 PostgreSQL 测试库可用、Python 虚拟环境已安装依赖，并保证两个端口空闲。Windows 自动优先使用已安装 Chrome/Edge；也可用 `CASEPILOT_BROWSER_CHANNEL` 指定已安装通道。其他环境未安装 Playwright 浏览器时，先运行 `npx playwright install chromium`。

浏览器报告和截图保存在 `output/playwright/`（Git 忽略），包括 workbench-list.png、workbench-detail.png、workbench-mobile.png 和 e2e-report.json；不保存测试口令、Cookie 或浏览器认证状态。测试账号和模拟工单留在独立测试库供排查，不删除或清空开发数据。

前端锁定 Vue Router、Pinia、Vitest、Playwright 和 OpenAPI 生成器。页面采用现有 Vue/Element Plus 栈，系统字体与本地 SVG，不依赖外部字体服务。后端回归入口仍为 `scripts/verify_backend.py`。

## 提交与阶段

每个 P 阶段全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 分别完成后 push。当前阶段未验收通过时不进入下一阶段。远程仓库固定为 `crush-game/CasePilot`，本地目录保留 `aftersales-agent`。
