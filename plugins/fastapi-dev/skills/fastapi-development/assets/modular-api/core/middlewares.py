"""中间件配置"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from uuid_utils import uuid7

from app.config import get_settings
from app.core.context import RequestContext, set_request_context
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
            request_id=request.headers.get("X-Request-ID", str(uuid7())),
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


def setup_middlewares(app: FastAPI) -> None:
    """注册中间件（注册顺序与执行顺序相反）"""

    # 请求上下文（最先执行）
    app.add_middleware(RequestContextMiddleware)

    # GZip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS: 不配置=无限制，配置后启用限制+credentials
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
