"""中间件配置"""

import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.context import RequestContext, set_request_context
from app.core.error_codes import ErrorCode
from app.core.security import decode_access_token

settings = get_settings()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求上下文中间件：注入用户信息到 contextvars"""

    async def dispatch(self, request: Request, call_next):
        # 提取用户 ID
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = decode_access_token(token)

        # 设置请求上下文
        ctx = RequestContext(
            user_id=user_id,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            request_id=request.headers.get("X-Request-ID", uuid4().hex[:8]),
        )
        set_request_context(ctx)

        response = await call_next(request)
        response.headers["X-Request-ID"] = ctx.request_id
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """获取客户端真实 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件（Loguru）"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:8]
        start_time = time.perf_counter()

        with logger.contextualize(request_id=request_id):
            logger.info("{} {}", request.method, request.url.path)
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            logger.info("Completed {} in {:.3f}s", response.status_code, duration)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        return response


class ExceptionMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled exception")
            return JSONResponse(
                status_code=500,
                content={
                    "code": ErrorCode.SYSTEM_ERROR,
                    "message": "Internal server error",
                    "data": None,
                    "detail": None,
                },
            )


def setup_middlewares(app: FastAPI) -> None:
    """注册中间件（注册顺序与执行顺序相反）"""
    # CORS（最内层）
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # GZip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 异常处理
    app.add_middleware(ExceptionMiddleware)

    # 请求日志
    app.add_middleware(LoggingMiddleware)

    # 请求上下文（最外层，最先执行）
    app.add_middleware(RequestContextMiddleware)
