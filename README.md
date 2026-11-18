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

`GET /health/live` 只检查进程；`GET /health/ready` 检查数据库、vector 扩展和业务迁移版本。前端仍为 P00 骨架；P01 的工单能力通过 API 提供。Worker 尚未实现，新建工单会保持 `QUEUED`，不表示调查已经开始。模型和企业数据只能配置为 `mock`，不请求外部模型或生产业务接口。

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

## 提交与阶段

每个 P 阶段全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 分别完成后 push。当前阶段未验收通过时不进入下一阶段。远程仓库固定为 `crush-game/CasePilot`，本地目录保留 `aftersales-agent`。
