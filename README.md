# 售后工单系统

面向企业售后场景的课题原型，正式名称待定。开发基线见 [技术方案](docs/technical-plan.md)，阶段证据见 [开发记录](docs/development-log.md)。旧 `aftersales` 仓库仍作为只读参考，不在此工程中执行其生产取数脚本。

## P00 本地启动（PowerShell）

环境：Python 3.13、Node 24、Docker Desktop（Linux 容器）。依赖仅安装到本工程；数据库端口默认 55432，仅绑定 127.0.0.1。开发库 `aftersales` 与测试库 `aftersales_test` 独立。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e ./backend
pwsh -File scripts/bootstrap.ps1
docker compose config --quiet
docker compose up -d --wait
Push-Location frontend
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe scripts/verify_p00.py
```

首次建库由 Docker 初始化脚本创建 vector 扩展和独立测试库；已有卷不会重复执行初始化脚本。不要为修复迁移删除数据库卷。P00 试验只在测试库使用临时向量表与 `checkpoints` schema；Saver 的 `setup()` 串行运行。业务迁移与业务 Worker 在后续 P 阶段实现。

启动 API 和前端分别使用两个终端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev
```

`GET /health/live` 只检查进程；`GET /health/ready` 检查数据库与 vector 扩展。P00 尚无业务表和业务图，后续阶段补充其 schema 与迁移版本就绪检查。页面仅为构建骨架，尚不能创建工单。模型和企业数据只能配置为 `mock`，不请求外部模型或生产业务接口。

停止本项目数据库：`docker compose stop`（保留数据）。不执行 `down -v`。

## 提交与阶段

每个 P 阶段全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 分别完成后 push。当前阶段未验收通过时不进入下一阶段。远程仓库与正式名称待用户确定。
