from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings


@lru_cache
def get_engine():
    url = make_url(get_settings().database_url.get_secret_value())
    if url.get_backend_name() != "postgresql":
        raise ValueError("业务数据库必须为 PostgreSQL")
    return create_engine(
        url.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "options": "-c timezone=UTC"},
    )


def get_db():
    # 写服务在返回成功之前显式 commit；异常和只读事务随连接关闭回滚。
    with Session(get_engine(), expire_on_commit=False) as db:
        yield db
