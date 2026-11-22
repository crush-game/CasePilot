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

创建账号时交互输入并确认密码（10～128 字符，不回显），账号名使用 3～64 位小写字母、数字、下划线、点或短横线。已有账号不会被覆盖。`business` 可处理内部工单池；`knowledge_admin` 通过 P05 接口管理文档、任务和失效，不能访问工单接口。当前前端工作台仍以工单处理为主，知识管理先使用接口。仓库无默认明文密码。

验收脚本自动迁移独立测试库，并以随机命名的空数据库测试首次迁移，结束后仅清理其自行创建的临时库；测试不清空开发库。P00 命令 `scripts/verify_p00.py` 保留兼容入口，现同样执行完整后端回归。

启动 API 和前端分别使用两个终端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev
```

`GET /health/live` 只检查进程；`GET /health/ready` 检查数据库、vector 扩展、业务迁移版本和检查点表。前端工作台默认访问 `http://127.0.0.1:5173`，与 API、Worker、对账循环配合即可处理工单。默认运行固定 Mock 图和模拟业务资料。启用可选 Supervisor 图及外部模型的条件见 P06～P08。

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

固定 Mock 图依次检查设备和发生时间，缺失时进入 `WAITING_HUMAN`。这只是工程闭环的规则流程，尚无真实模型、语义检索或真实日志诊断。Mock 方案和回复均带模拟标记；`[MOCK_ERROR]` 测试文本可触发固定工具失败路径，扩展场景回放见 P04。

1. 建单后启动 Worker；有完整设备/时间时直接生成待确认方案，否则持久暂停并建立人工待办。
2. `GET /human-tasks` 查询人工池，默认返回开放待办，可用 status/assignee_id 筛选，cursor 为返回的 UUID 游标。`GET /human-tasks/{id}` 返回缺口、认领状态、当前 expected_version。
3. `POST /human-tasks/{id}/claim` 认领，JSON 为 action_id＋expected_version；其他人已认领或版本失效返回 409。
4. `POST /human-tasks/{id}/resume` 补充后排队恢复，只有认领人可操作。除 action_id、expected_version 外，facts_patch 支持 device_ref、occurred_at、occurred_at_precision；补充设备和时间可一次完成，也可以分两次暂停完成。替换已有关键事实请重新调查；`supervisor-v2` 的多反馈待办可以提交 `selected_feedback_ref`，见 P08。
5. Worker 使用同一 run/thread 和 `Command(resume=...)` 继续。恢复动作已被检查点消费时不会再次提交给后续暂停点。生成方案后为 `PENDING_CONFIRMATION`，详情返回 solution_json，run 详情返回节点记录与检查点摘要。
6. `POST /tickets/{id}/review` 用 decision=approve/revise 审核或修改 reply_draft，审核通过仍为待确认；`POST /tickets/{id}/customer-feedback` 用 outcome=contacted＋reason 记录业务人员已联系客户，此时才进入 `WAITING_CUSTOMER`。系统没有外部发送接口。
7. `POST /tickets/{id}/close` 明确 outcome=resolved/unresolved＋reason，分别进入已解决/未解决结案，清理活动指针、开放待办和待执行任务。暂停中的工单先认领；运行中的工单先请求停止。

上述写操作都携带 action_id、expected_version 和 CSRF，重复同一动作返回原结果。`customer-feedback` 的 resolved 显式调用结案规则，unresolved 创建新调查 run；均保留人工来源和原因。明确确认解决后可生成待人工审阅的候选经验，见 P09。

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

## P04 工具、模型接口与场景回放

工具注册表固定为 `search_knowledge`、`get_feedbacks`、`download_log`、`extract_log_window`、`diagnose_wifi`、`analyze_domain`，每项公开封闭的 Pydantic 输入/输出 schema。工具参数中的 customer_ref 必须与系统绑定身份一致，邮箱从工单关联，不允许调用方替换邮箱、传任意 URL 或磁盘路径。反馈按设备/平台、时间筛选，多候选不默认选最新；下载句柄、提取窗口和分析窗口只能在当前授权会话使用。

返回统一含 status、data_refs、error_code、retryable、source（模式、记录 ID、查询条件）和 fetched_at。没有客户反馈、没有匹配时间数据、没有附件、下载/解析失败、认证失败、超时分别表达。日志片段在返回前脱敏；规则分析与 Mock 模型分析分别标记，不把 WiFi 记录当 OTA 根因。

模型入口为 `app.providers.client.ModelClient`，支持同步 Worker 和异步调用、按角色选 profile、超时、JSON/schema 与证据白名单检查。目前仅实现 `solution`/`domain` 的 `mock/deterministic-v1`；`parse`/`supervisor` 角色配置预留，尚无模型自主路由。可选的 `AFTERSALES_MODEL_PROFILES` 为 JSON 对象，格式见 `.env.example`；未配置角色使用固定 Mock 默认值。选择未实现的供应商/模型明确失败并转人工，不静默回落。Mock usage 标记 simulated，Token 和费用为 null，不伪造真实消耗。

工作台仍使用 `mock-v1` 固定图：两个内部 Mock 步骤映射到注册工具，生成方案节点调用统一 Mock Client，节点记录保存逻辑模型调用次数。节点与暂停语义、旧工具缓存键保持兼容；已保存的 P02 工具结果可以继续复用。此接入不代表真实模型、RAG 或真实日志故障调查已实现，六工具的完整脚本组合通过下列独立回放入口执行。

```powershell
# 项目根目录；只使用已配置的本机 aftersales_test
.\.venv\Scripts\python.exe -m app.eval replay --suite smoke
```

12 个独立种子场景分别放在 `fixtures/runtime/`；隐藏标注在 `fixtures/evaluation/`，仅评测入口执行结束后读取。公开动作脚本驱动回放，工具/模型仅接收当前允许的数据；这是确定性契约检查，不是自主 Agent 或真实模型效果评测。S11/S12 另执行 PostgreSQL 和独立 Worker 的真实幂等、迟到结果、预算及强制终止/恢复检查。此命令需要开发依赖和可用测试库；不会创建生产任务或调用外部模型。

报告保存为 `output/evaluation/smoke.json`（Git 忽略），包含脱敏实际轨迹和检查结论，不保存隐藏答案。`fixtures/README.md` 说明场景族和目录边界；当前本地同账号不做 OS 级权限隔离，部署时 Agent 仅挂载 runtime，评测进程另挂载 evaluation。

## P05 文档入库、版本与 BM25

新增迁移为 `0003_knowledge`，只增加 kb_documents、kb_chunks、ingestion_jobs、kb_index_state。升级现有环境时先安装锁文件中的新增轻量依赖，再执行迁移；不用删除数据库卷。入库由独立 Worker 处理，不在 HTTP 请求中执行模型或索引构建：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
.\.venv\Scripts\python.exe -m app.manage migrate
.\.venv\Scripts\python.exe -m app.manage create-user --login librarian --role knowledge_admin
.\.venv\Scripts\python.exe -m app.workers.ingestion
# 排查单个任务可另行执行：
.\.venv\Scripts\python.exe -m app.workers.ingestion --once --job-id <job_uuid>
```

`POST /api/v1/knowledge/documents` 接收 multipart：`file` 为 UTF-8 `.md`/`.txt`，`metadata` 为 JSON 字符串，并携带 Idempotency-Key 和 CSRF。文件上限 1 MiB，单行最多 4096 字符、最多 2000 片段。原始字节和 SHA256 存数据库，服务不按文件名读取服务器路径；解析器可能将 Windows 上传文件名标准化为 basename。文件上传返回 202 和 document_id/job_id，索引提交前 status=pending，不可搜索。

元数据必须声明 doc_key、正整数 version、title、product_scope、firmware_versions、regions、channels；范围数组不可为空，只有明确通用时使用 `["*"]`。source_type 支持 manual/faq/policy，data_source 固定 mock；有效期可选，时间必须带时区，结束时间不包含在有效区间中。样例见 `fixtures/knowledge/`。

以下为 PowerShell 7 上传示例，需要 API 已启动；口令只在当前会话内用于登录，不写文件：

```powershell
$kbAccount = Read-Host '知识管理员账号'
$kbPassword = Read-Host '密码' -MaskInput
$kbLoginBody = @{ login = $kbAccount; password = $kbPassword } | ConvertTo-Json -Compress
$kbSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
$kbLogin = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/login' -ContentType 'application/json' -Body $kbLoginBody -WebSession $kbSession
$kbPassword = $null
$kbLoginBody = $null
$kbHeaders = @{ 'X-CSRF-Token' = $kbLogin.csrf_token; 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$kbCreated = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/knowledge/documents' -WebSession $kbSession -Headers $kbHeaders -Form @{ file = Get-Item -LiteralPath 'fixtures/knowledge/connection-guide.md'; metadata = Get-Content -LiteralPath 'fixtures/knowledge/metadata.json' -Raw }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/knowledge/jobs/$($kbCreated.job_id)" -WebSession $kbSession
$kbSearch = @{ query = 'E_WIFI_401'; product_ref = 'PILOT-01'; firmware_version = '1.0' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/knowledge/search' -WebSession $kbSession -Headers $kbHeaders -ContentType 'application/json' -Body $kbSearch
```

管理与读取接口：

| 接口 | 用途与权限 |
|---|---|
| `GET /knowledge/documents`、`GET /knowledge/documents/{id}` | knowledge_admin 查看文档版本、revision、状态与 checksum；列表支持 cursor/limit、status/doc_key |
| `GET /knowledge/documents/{id}/source` | knowledge_admin 查看脱敏原文预览；source_checksum 对应留存原始字节，预览不是原始字节下载 |
| `GET /knowledge/jobs`、`GET /knowledge/jobs/{id}` | knowledge_admin 查看 queued/running/succeeded/failed/cancelled、阶段、attempt/revision、error_code/retryable 与历史；列表支持 status/document_id |
| `POST /knowledge/jobs/{id}/retry` | knowledge_admin 对可重试失败任务提交 action_id、expected_revision、reason；重复动作幂等，旧版本409，至多5次执行尝试 |
| `POST /knowledge/documents/{id}/archive` | knowledge_admin 提交 action_id、expected_revision、reason；立即取消检索资格，保留版本/原文/引用并取消未完成任务 |
| `POST /knowledge/search` | business/knowledge_admin；query、可选 product_ref/firmware_version/region/channel/as_of、limit≤20 |
| `GET /knowledge/chunks/{chunk_id}` | business/knowledge_admin；可带上述适用条件，返回回源信息及当前 usable/missing_fields/unavailable_reasons |

除只读 GET 外，写入和 POST 检索都沿用 Cookie/CSRF。ID 均为 UUID，列表后续请求保持筛选不变。业务角色只能检索和读取引用，不能管理文档/任务/原文预览。缺失条件返回 missing_fields，特定范围文档不会在条件未知时被当作适用；历史引用仍可回源，archived/superseded 或过期时 usable=false。

同一 doc_key/version 的内容和适用范围不可覆盖；重复相同内容复用原任务，变更请上传新版本。新版本发布成功才把旧活动版本改为 superseded；切块、替换和索引快照同事务提交，任何构建失败保留旧版本。无效 UTF-8、空内容等不可修复源文件失败应上传新版本；暂时处理失败可显式重试。等待行锁后重新读取任务 revision，防止并发重试同时使用旧状态。入库任务每阶段续租，默认60秒；进程崩溃后由同一 Worker 扫描过期任务恢复，旧进程仍持运行锁时不会并发领取，归档后的迟到结果不能重新发布。

当前检索为 `retrieval_mode=bm25`，数据标记 mock。`zh-bigram-v1` 使用汉字单字/二元词项及完整型号/错误码，不是词典分词；k1=1.2、b=0.75，正值 IDF 形式可对照 [Lucene BM25 说明](https://lucene.apache.org/core/10_3_1/core/org/apache/lucene/search/similarities/BM25Similarity.html)。评分对象为片段及标题路径，分数不是置信度。快照保存于 PostgreSQL，每次检索核对发布版本、算法/分词版本、语料指纹和 checksum，不一致即重建；状态过滤以数据库为准。该实现面向小规模原型，尚无真实 embedding、RRF 或重排序效果结论。

`DatabaseKnowledgeAdapter` 将同一检索服务接到 P04 白名单工具，工具结果带 BM25 模式、索引版本和完整引用。为保持旧检查点和工作台闭环兼容，mock-v1 图仍使用原固定资料；P07 再让知识调查根据事实调用已发布资料。P05 不把固定 Mock 草稿说成基于新文档生成的回答。

验收仍运行 `scripts/verify_backend.py`，包含 MD/TXT、引用、失效、坏文件、原子发布、并发重试/版本、快照重建、独立进程终止与租约恢复。公开 API 更新后需运行 `npm run api:generate` 与 `npm run api:check`。

## P06 Provider 与混合检索接入

默认配置见 `config/providers.siliconflow.json`：聊天 `Qwen/Qwen3.5-35B-A3B`（关闭思考输出），embedding `Pro/BAAI/bge-m3`（1024维），rerank `Pro/BAAI/bge-reranker-v2-m3`。这是首轮验证基线，模型效果以实际小集为准。公开配置包括地址、模型、输入/输出上限、超时、币种、费率版本与角色覆盖；密钥只在本项目 `.env` 设置 `AFTERSALES_PROVIDER_API_KEY`。可用 `AFTERSALES_PROVIDER_CONFIG_PATH` 指定其他配置，路径相对项目根目录。

```powershell
# 检查只输出 Key 是否存在和公开模型名，不输出 Key
.\.venv\Scripts\python.exe -m app.providers.manage check-config
# 首次真实接口小集：需要本项目 Key、本机 PostgreSQL 和已配置的 aftersales_test
.\.venv\Scripts\python.exe -m app.eval live --suite p06
```

真实小集先创建独立的 `aftersales_p06_live_<随机值>` 数据库并迁移，导入6份公开虚构资料，执行向量构建、6次混合检索/重排和2次结构化草稿。程序共享预算为5元、60次物理调用、50万Token、600秒；重试和 JSON 修复均计数。报告保存于 Git 忽略的 `output/p06/`，验证库留存调用账本供审计。无 Key 则在创建数据库或网络请求前返回 `PROVIDER_KEY_MISSING`、`real_acceptance=false`。HTTP 模拟契约测试仅标记 `contract`，不能算真实验收；此小集也不代表 Agent 决策或诊断准确率评测。

业务迁移新增 `0004_providers`：共享预算、调用审计、embedding profile、向量和索引构建五张表，兼容原 BM25 文档。`httpx` 作为运行依赖使用既有锁定版本。升级本地开发环境先执行 `python -m app.manage migrate`，不要删除数据库卷。以下命令用于显式把已有活动语料切到真实混合检索，会将脱敏片段发送给配置服务：

```powershell
.\.venv\Scripts\python.exe -m app.providers.manage create-budget --max-cost 5 --max-calls 60 --max-tokens 500000 --seconds 600
# 使用上一步输出的 UUID；不要照抄占位符
.\.venv\Scripts\python.exe -m app.providers.manage build-index --budget-id <budget_uuid>
.\.venv\Scripts\python.exe -m app.providers.manage report --budget-id <budget_uuid>
```

发布后 API/入库 Worker 还需要 `AFTERSALES_PROVIDER_BUDGET_ID` 指向一个未到期、有余量的共享预算；修改 `.env` 后重启相应进程。预算不会自动补充，API 不接受调用者随意重置预算。当前固定 `mock-v1` 工单图仍使用 Mock；真实 `ModelClient` 通过显式 `ProviderSession` 接入，自主调查在 P07 接入。

`POST /knowledge/search` 可指定 `retrieval_mode=bm25/hybrid`；省略时使用当前已发布模式，`rerank` 默认 false。BM25 始终可显式查询，重排只用于 hybrid；模型失败不静默回落。混合路径按适用范围过滤，BM25和 pgvector 精确余弦检索各取20候选，RRF（k=60）融合，再按预算可选重排，最多返回6段。返回 profile、模式、发布版本、候选数及调用用量；`data_source=mock` 表示虚构业务资料，`inference_mode=real` 表示真实接口，含义独立。

向量 profile 由端点、模型、维度、预处理版本和执行模式确定，费用配置不改变向量语义。数据库约束保证片段/profile唯一、维度匹配；真实与契约向量不可混用。切换模型先完整构建，校验语料版本未变后原子发布；失败保留旧活动索引。新文档在发布前完成同 profile 的 embedding，失败不替换旧版本；网络调用不占用发布事务锁，返回前再次核对发布版本，拒绝归档/替换后的迟到检索结果。构建进程中断后可显式重跑复用已完成向量，原构建审计行可能仍为 running，不宣称已有自动构建对账 Worker。

调用前在数据库锁内预留调用数、Token和费用，完成后按供应商 usage 对账。每个只读请求最多1次瞬时重试、结构化 JSON 最多1次修复；引用和 data_source 必须通过校验。未知用量/费用保持 null，保留预留风险额度；审计只保存公开 profile、请求/响应 hash、供应商请求 ID 和用量，不保存 Key 或原始请求/响应正文。费率是带版本的配置估算，程序预算不等于平台账单的硬封顶，费用核对以平台为准。当前小规模向量检索未建 HNSW 索引，未验证规模性能。

配置依据：[硅基流动价格](https://www.siliconflow.cn/pricing)、[聊天接口](https://docs.siliconflow.cn/docs/api/chat-completions-post)、[embedding 接口](https://docs.siliconflow.cn/docs/api/embeddings-post)、[rerank 接口](https://docs.siliconflow.cn/docs/api/rerank-post)、[BGE-M3 模型卡](https://huggingface.co/BAAI/bge-m3)。实际验收状态见 `docs/development-log.md`。

## P07 Supervisor 与知识调查子图

`supervisor-v1` 是独立于固定 `mock-v1` 的模型编排图。保持默认 Mock，已有运行始终按保存的图版本执行；需要启用新图时，在项目 `.env` 设置 `AFTERSALES_WORKFLOW_GRAPH_VERSION=supervisor-v1`，重启 API/Worker，新建工单才使用新图。真实调用沿用本项目硅基流动 Key。启用前先完成知识索引构建；缺服务、预算或适用资料会留下人工待办，不静默改走固定 Mock。

```powershell
# 在项目根目录，启动既有持久 Worker
.\.venv\Scripts\python.exe -m app.workers.runtime worker
# 人工触发真实图小集：只发送公开虚构资料，需要明确调用授权
.\.venv\Scripts\python.exe -m app.eval.p07 --max-cost 1
```

新图由解析节点、Supervisor、知识子图、方案节点及人工暂停组成。模型以封闭 schema 选择知识调查、方案、故障调查或人工；程序校验动作、证据白名单、适用范围和预算，不允许模型扩展权限。P07 的故障调查入口返回 FAULT_TOOLS_NOT_READY，故障工具在 P08 接入。所有方案仍为待人工审核草稿，业务资料标记 mock，真实/契约推理模式分别标记，生成草稿不触发联系或结案。

知识子图作为真正的 LangGraph 子图挂载，继承父图 PostgreSQL Saver，节点为 begin/search/assess/rewrite/context/finish。委派保存目标、输入引用、允许工具、预算和完成条件；返回逐条带引用及适用条件的发现、缺口、冲突、停止原因与原检索动作引用。父图保留多次委派的结构化发现，按引用重新取得原文，不只保存最后一句总结。对原问题的充分性仍是模型判断，程序校验不能证明语义正确，效果需要后续回放评测。

每个子任务至多一次改写和一次相邻段补取；相邻段只能从已返回片段的数据库邻接信息取得，不能传任意路径或网页。发送模型前按输入额度选取完整片段，保留正文/标题/版本/适用范围，记录 context_refs 和 omitted_refs；补取段优先，未知条件保留缺口。冲突立即转人工；无新材料、重复相同动作、补救耗尽、非法引用、服务异常或预算耗尽都有明确停止原因。引用在检查、方案生成和方案投影前的校验节点重新核对活动状态与适用性；生成期间资料失效不会发布方案。

默认每轮300秒、至多20次供应商物理请求（聊天/embedding/rerank与重试共用）、10万Token、0.5元配置费率额度、12个只读工具动作、2个知识子任务；跨轮默认最多5轮、100调用、50万Token、2.5元。模型/费率/策略快照在建单时固定，预算ID和累计量持久保存在 run；重启不刷新本轮截止时间或额度。人工补充进入新预算轮次，保留前轮成本并重新校验证据；调整已有事实走重新调查。程序保留风险预留，费用估算不等于平台账单硬封顶。

每个模型/工具逻辑动作先持久记录再调用，成功结果在检查点落盘前崩溃可复用；若只留下执行中记录而无法确认结果，返回 ACTION_OUTCOME_UNKNOWN 交人工，不自动重复收费请求。网络调用前后检查租约、版本和停止请求，外部网络不在业务事务锁内执行。NodeRun 与 `GET /runs/{id}` 返回主/子节点、结构化输入输出引用与用量，不提供原始思维链。子图的完成步骤在父节点完成后投影到业务时间线，执行中的子图状态由 Saver 保留，暂不承诺每个子节点实时推送。

建单和人工补充可显式填写 product_ref、firmware_version、region、channel，作为带来源的事实；产品型号与设备ID分开，不根据设备ID猜型号。已有值的修改必须重新调查。工作台支持这些字段及知识引用回源，显示文档版本、行号和当前适用状态；旧 Mock 来源说明保持兼容。

真实图小集在单独的 `aftersales_p07_live_<随机值>` 数据库执行两条工单，分别核验有依据草稿和无依据人工。索引预算为总额20%，两工单各40%，总配置费率额度最多1元；可用 `--max-cost` 下调。结果及审计库保留，报告在 Git 忽略的 `output/p07/`。重复试跑应计入同次授权的累计额度；未经授权不运行真实服务。契约测试只验证工程路由，不当作模型决策效果。

子图实现依据 [LangGraph 官方子图说明](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)，锁与检查点语义以当前锁定版本的本地测试为准。实际验收状态见 `docs/development-log.md`。

## P08 故障调查与日志证据

独立图 `supervisor-v2` 挂载故障调查子图，保留旧 `mock-v1`/`supervisor-v1` 运行的检查点行为。默认仍为 `mock-v1`；显式启用 v2 会使用配置的模型服务，费用沿用P07持久预算。企业侧始终只读公开样例 `fixtures/enterprise/p08-demo.json`，没有连接真实后台。样例键由 `AFTERSALES_ENTERPRISE_MOCK_FIXTURE` 指定，建单时固定校验和，不能悄悄替换同一次调查的数据。

建单/人工补充支持 Android/iOS 与 App版本，反馈按客户、设备、平台、已知版本和时间前后30分钟筛选；多条候选进入人工待办，人工选择后才能下载。详细日志缺失且仅调查WiFi时可看埋点，结果仍转人工；认证/超时/下载/解析失败不能当成无日志，OTA不能用WiFi记录替代。确定性WiFi规则报告事件，领域模型按实际日志返回未确认候选、支持/反证和待验证事项，不能凭时间相邻确认因果。

新增兼容迁移 `0005_faults`，在 PostgreSQL 保存原始附件及脱敏证据；原字节不返回API或写入图状态。附件句柄/引用绑定ticket和run，支持进程恢复；源checksum、事实范围hash和复合外键防止串用。ZIP在内存读取，限制路径、成员数、大小及压缩比；文本为带时区的UTF-8 JSONL。查看窗口默认前后5分钟，最多扩大至前后15分钟；超过40条明确转人工。详情展示已查看领域、范围、限制和日志行号；来源接口仅返回脱敏片段。读取日志后修正关联事实需重新调查。

```powershell
# 本地模拟验收：独立PostgreSQL测试库，HTTP模型契约替身，无付费请求
.\.venv\Scripts\python.exe scripts/verify_p08.py
# 全量回归，包含旧图兼容和迁移一致性
.\.venv\Scripts\python.exe scripts/verify_backend.py
```

P08验收报告写入Git忽略的 `output/p08/contract-summary.json` 和 `contract-tests.xml`，标记 `data_source=mock`、`inference_mode=contract`、`real_acceptance=false`。场景包含WiFi/OTA跨领域、无数据/下载错误、多反馈人工恢复、跨工单/版本隔离、脱敏、坏ZIP、预算、无进展和真实进程强杀恢复。它验证工程闭环，不报告模型诊断准确率。真实企业接口需取得授权并核验契约后单独适配；后续阶段不自动启用或花费真实模型预算。

## P09 方案校验与经验审阅

工单详情分别展示已确认的调查范围、有引用的调查观察和建议操作。草稿入库、人工审核通过及记录已联系客户时，都按工单范围重新读取知识或日志引用。引用缺失、失效、跨运行或校验和变化时，需要重新调查。人工审核负责判断建议是否确由材料支持及是否适合发给客户。

业务人员选择已解决并填写结案说明后，系统在同一事务登记经验提取任务。可选填经过核验的有效操作，系统从结案记录和调查来源提取脱敏候选，保留确认方式、适用条件、来源工单、运行、结果版本和引用。仅有联系记录、草稿审核或未解决结案时不会登记成功经验。历史终态不自动补录。

升级本地 PostgreSQL 时运行 `python -m app.manage migrate`，迁移 `0006_experiences` 新增经验表。日常运行 `python -m app.workers.runtime worker` 会同时处理工单和待提取经验。工作台「经验候选」可查看、审阅或归档，`GET /api/v1/experiences` 可按工单和状态筛选。审阅使用版本检查、幂等操作标识和审计记录。发布与检索复用安排在 P13。

## P10 一期演示与验收

1. 按本页启动数据库、迁移、初始化检查点，再启动 API、前端、Worker 和对账进程。
2. 使用工单工作台新建一个公开虚构反馈，例如邮箱 `demo@example.test`、问题「设备反复断连」。先留空设备和发生时间。待状态变为「待人工处理」后认领，填设备 `DEMO-01` 与发生时间并恢复。
3. 在详情中查看调查轨迹和来源。审核模拟草稿，记录已联系。人工确认解决时可填已核验操作，正常 Worker 会生成经验候选。也可结为未解决，验证这一路径没有成功候选。
4. 模拟故障用 `[MOCK_ERROR]` 建单。需要实际中断恢复验证时，运行测试脚本，故障注入只针对独立测试库与测试子进程。对账与单次运行命令见 P02。

```powershell
.\.venv\Scripts\python.exe scripts/verify_p10.py
```

验收按顺序检查 Compose 配置、全量后端、12 个模拟场景、前端契约、单测、构建和浏览器工作台。各步骤退出码与日志保存在 `output/p10/`。S01～S04 另核对知识路径、日志路径和两种证据合并的持久工单。真实模型接入证据来自先前授权的 P06/P07 小集，企业反馈和日志在一期使用模拟适配器。

## P11 消费者客服

迁移后用 `python -m app.manage create-user --login demo-consumer --role consumer` 交互创建本地消费者账号。登录后进入 `/support`。试问「怎么查看 App 版本？」可收到带来源的样例 FAQ。问「怎么连接设备？」会要求型号与版本，填写 `DEMO-01` 和 `1.0` 后返回相应指引。允许直接选择转人工。未知问题和不适用的型号版本也交给人工，并返回工单号。

公开自动回复保存在 `fixtures/support/app-faq-v1.json`，以审核过的样例问法及范围匹配。客服只读取自己会话与关联工单状态。人工待办先与会话、工单和回执一起提交。一个会话对应一个问题，可另开会话处理新问题。人工转接后可补充信息，业务工作台的时间线会保留该信息。未收到确认时重试沿用原动作标识，离线输入保留在同一浏览器标签页。

## P12 模拟渠道和消息回传

业务账号可调用 `POST /api/v1/channels/mock/events` 导入模拟事件。发送人须为有效的本地消费者账号。事件编号用 UUID，使用 `conversation_ref` 与 `issue_ref` 区分会话和问题，用 `sequence` 记录顺序。重复编号且内容相同返回原回执；重复编号且内容不同返回 409。迟到事件和编辑单独保存，已有问题继续关联原工单。将 `simulated_failures` 设为 1 可演示重试后送达，设为 3 可演示最终失败。在 `GET /api/v1/channels/deliveries/{id}` 看发送状态、尝试数和模拟回执。

消费者工单被认领后，处理人可从详情页把人工回复加入发送队列。App 回复由正常 Worker 写入对应会话。结束状态显示「已送达」或「发送失败」，失败不撤销工单。外部渠道只提供本地模拟适配器。模拟送达表示本地模拟回执写入成功。

人工服务日历通过 `AFTERSALES_SERVICE_CALENDAR` 配置，北京时间，星期一为 0，可设置关闭日期。示例见 `.env.example`。未配置时回执提供通用人工服务提示。开放时间仅说明何时开始人工服务，具体进度可查工单。

## P13 已发布经验与声明实验

业务账号审核已确认解决的案例后，知识管理员可在 `GET /api/v1/experience-release-candidates` 取候选 ID，通过 `POST /api/v1/experiences/{id}/publications` 提交 `action_id` 和 `reason` 发布。须有已核验措施、确定型号和固件版本。相同问题适用范围重叠时先复核已有版本。发布记录可查询历史，通过 `POST /api/v1/experiences/{id}/publications/{revision}/withdraw` 撤回指定版本，重发产生新版本。

业务工单有型号及固件时，「已发布历史案例」可以按范围召回。其他已记录条件必须同样匹配。召回显示历史措施和来源工单，作为人工排查参考。撤回或归档会从后续召回移除。知识库检索及当前工单的证据引用仍来自各自的正式来源。

`app.eval.structured` 是独立的检索实验入口。同一份模拟原文提供普通片段和结构化声明，两种路径共用型号、固件、有效期及可见状态约束。声明按属性召回不同值的来源并报告冲突。实际对照数据与结果留在 P14。

## P14 复现评测和最终验收

```powershell
.\.venv\Scripts\python.exe -m app.eval.p14
.\.venv\Scripts\python.exe scripts/verify_p10.py --stage p14
```

第一条运行冻结的知识、调查、经验三组离线对照。输入与标签分文件，全部运行后再读取标签，逐例结果、分组、调用与成本写入 `output/evaluation/p14.json`。第二条串行验证整个系统，报告在 `output/p14/`。可引用结果和误差分析见 [开发记录](docs/development-log.md#p14固定对照错误分析与项目证据)。评测使用模拟业务资料，外部真实模型先前仅小集验证，外部渠道仍为本地模拟。

## 提交与阶段

每个 P 阶段全部验收通过后用中文提交一次；第一大阶段 P00～P10、第二大阶段 P11～P14 分别完成后 push。当前阶段未验收通过时不进入下一阶段。远程仓库固定为 `crush-game/CasePilot`，本地目录保留 `aftersales-agent`。
## 网页报障与 Wi-Fi 首诊

消费者从 `/support` 发起咨询，可在确认卡片补充设备标识、型号、平台、固件和 App 版本以及发生时间。配置中存在当前消费者的样例设备、字段齐全且属于 Wi-Fi 问题时，「提交故障」会自动排队调查。「确认转人工」直接建立人工待办。普通咨询沿用样例 FAQ。

样例绑定通过 `AFTERSALES_SUPPORT_DEMO_DEVICES` 配置。JSON 顶层键为登录消费者的 UUID，值为设备数组，字段为 `device_ref`、`customer_email`、`product_ref`、`firmware_version`、`platform` 和 `app_version`。仅接受虚构的 `.test` 邮箱，设备数据来自已固定校验和的企业样例。Chrome 验收自动生成本地测试绑定，并使用 HTTP 契约替身推进首诊。正式使用模型需要先准备项目现有模型配置与预算。

## 结案会话质检

新版网页会话的关联工单结案时保存质检快照。客服在工作台处理正式回复投递，再执行结案。Worker 自动做规则初筛。「服务质检」页面可安排抽样精检，查看原消息证据，并由另一位业务人员确认或改判。受评客服可对已确认结果提出申诉。新规则版本由知识管理账号发布，用独立复评记录应用到历史快照。语义判定默认使用本地模拟契约，适合验收计分与复核流程。

## 售后周报与知识缺口

业务账号可在 `/reports` 生成或重算周报，查看分子分母、历史版本和投递结果。留空日期生成上个北京时间自然周。质检复核可提交带原消息引用的知识缺口，知识管理账号通过同一入口核对。

群报默认走本地模拟。部署时使用 `AFTERSALES_WEEKLY_REPORT_ENABLED` 开启定时生成，配置 `AFTERSALES_WEEKLY_REPORT_ORIGIN` 为可访问的面板地址。若要接入飞书，按租户要求授权配置目标群，并设置 `AFTERSALES_WEEKLY_REPORT_GROUP` 和 `AFTERSALES_WEEKLY_REPORT_WEBHOOK`。地址作为本地密钥配置保存。定时 Worker 在周一 09:00（北京时间）之后安排上周汇总，每周每群只安排一次自动投递。手工投递按报表版本与群去重。结果未知时保留待核对记录。
