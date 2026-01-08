"""全局异常处理器注册"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.exceptions import ApiError


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """业务异常处理"""
    logger.warning(
        "业务异常: {} | code={} path={}",
        exc.message,
        exc.code,
        request.url.path,
    )
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
            "detail": exc.detail,
        },
        headers=headers,
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """请求验证异常处理"""
    errors = []
    for error in exc.errors():
        loc = error["loc"]
        field = ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else str(loc[0])
        errors.append(
            {
                "field": field,
                "message": error["msg"],
                "type": error["type"],
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.INVALID_PARAMETER,
            "message": "请求参数验证失败",
            "data": None,
            "detail": {"errors": errors},
        },
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """HTTP 异常处理"""
    code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        500: ErrorCode.SYSTEM_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    code = code_map.get(exc.status_code, ErrorCode.SYSTEM_ERROR)

    headers = dict(exc.headers or {})
    if exc.status_code == 401 and "WWW-Authenticate" not in headers:
        headers["WWW-Authenticate"] = "Bearer"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": str(exc.detail),
            "data": None,
            "detail": None,
        },
        headers=headers or None,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常处理"""
    logger.exception(
        "未捕获异常 {method} {path}", method=request.method, path=request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.SYSTEM_ERROR,
            "message": "服务器内部错误",
            "data": None,
            "detail": None,
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
