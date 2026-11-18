"""仅供隔离测试子进程使用的故障注入，不提供 HTTP 入口。"""

import os
import threading

from sqlalchemy.engine import make_url

from app.config import get_settings


def failpoint(name: str):
    if os.environ.get("CASEPILOT_TEST_FAILPOINT") != name:
        return
    url = make_url(get_settings().database_url.get_secret_value())
    if url.database != "aftersales_test" or url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("故障注入仅允许独立本机测试库")
    print(f"P02_FAILPOINT:{name}", flush=True)
    threading.Event().wait(30)  # 父测试收到信号后强制终止此进程。
    raise RuntimeError("故障测试未在期限内终止子进程")
