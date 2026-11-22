from contextlib import asynccontextmanager
from uuid import uuid4

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.experience_routes import router as experience_router
from app.api.channel_routes import router as channel_router
from app.api.routes import router
from app.api.support_routes import router as support_router
from app.api.workflow_routes import router as workflow_router
from app.api.knowledge_routes import router as knowledge_router
from app.api.quality_routes import router as quality_router
from app.api.report_routes import router as report_router
from app.config import get_settings
from app.repositories.models import SCHEMA_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    yield


app = FastAPI(title="CasePilot 售后工单系统", version="0.0.1", lifespan=lifespan)


class ConfiguredCORS(CORSMiddleware):
    def __init__(self, app):
        super().__init__(
            app, allow_origins=get_settings().allowed_origins,
            allow_credentials=True, allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
            expose_headers=["X-Request-ID"],
        )


app.add_middleware(ConfiguredCORS)
app.include_router(router)
app.include_router(workflow_router)
app.include_router(experience_router)
app.include_router(support_router)
app.include_router(channel_router)
app.include_router(knowledge_router)
app.include_router(quality_router)
app.include_router(report_router)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    return response


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
            schema_exists = conn.execute("SELECT to_regclass('business.alembic_version')").fetchone()[0]
            version = conn.execute("SELECT version_num FROM business.alembic_version").fetchone() if schema_exists else None
            checkpoints = conn.execute("SELECT to_regclass('checkpoints.checkpoints')").fetchone()[0]
        if vector is None or version is None or version[0] != SCHEMA_VERSION or checkpoints is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
    except psycopg.Error:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ok", "data_source": "mock"}
