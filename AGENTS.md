# 售后工单系统开发约定

- 中文沟通，按 `docs/technical-plan.md` 顺序开发；进度与证据放在 `docs/development-log.md`。
- 每个 P 阶段全部验收通过后，用中文提交一次 Git，例如 `P00 完成工程隔离与框架兼容性验收`。
- 第一大阶段 P00～P10、第二大阶段 P11～P14 各完成后 push。阶段未通过不得进入下一阶段。
- 修改前检查 Git 状态，不覆盖用户改动。提交前展示摘要并运行相关验证。
- 使用项目 `.venv`、npm 锁文件和固定摘要的 PostgreSQL 17/pgvector 镜像，不修改全局环境。
- 默认 Mock；不复制旧脚本中的凭据，不连接生产，不提交 `.env`、日志、附件或数据库数据。
- 业务表由 Alembic 管理，检查点表由官方 Saver 串行初始化；不得以 SQLite 代替 PostgreSQL 验收。
