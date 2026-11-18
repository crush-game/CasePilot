from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    yield


app = FastAPI(title="售后工单系统", version="0.0.1", lifespan=lifespan)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with psycopg.connect(
            get_settings().database_url.get_secret_value(), connect_timeout=3
        ) as conn:
            vector = conn.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
        if vector is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
    except psycopg.Error:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ok", "data_source": "mock"}
