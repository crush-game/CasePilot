# 开发记录

## 规范

2026-11-18 用户授权从 P00 开始实现。每个 P 单元全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 各完成后 push。本阶段未通过验收，不进入下一阶段。正式名称与远程仓库待定。

## P00：工程隔离、依赖兼容与框架试验

日期：2026-11-18。验收结论：通过。当前仅完成 P00，尚未开始 P01。

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
