from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.domain.errors import AppError


def error_response(request: Request, status: int, code: str, message: str, details=None):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(status_code=status, content={
        "request_id": request_id,
        "error": {"code": code, "message": message, "details": details or {}},
    }, headers={"X-Request-ID": request_id})


def install_error_handlers(app):
    @app.exception_handler(AppError)
    async def application_error(request, exc):
        return error_response(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # 不回传 input/ctx，避免错误响应携带密码、客户原文或数据库内容。
        fields = [{"loc": list(item["loc"]), "type": item["type"]} for item in exc.errors()]
        return error_response(request, 422, "VALIDATION_ERROR", "请求参数不符合要求", {"fields": fields})

    @app.exception_handler(IntegrityError)
    async def constraint_error(request, exc):
        return error_response(request, 409, "DATA_CONFLICT", "数据约束冲突，请刷新后重试")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return error_response(request, 503, "STORAGE_UNAVAILABLE", "存储服务暂不可用，请稍后重试")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(request, exc.status_code, "HTTP_ERROR", "请求地址或方法不可用")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error_response(request, 500, "INTERNAL_ERROR", "服务处理失败，请通过请求编号排查")
