"""请求上下文 - contextvars"""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass
class RequestContext:
    """请求上下文数据"""

    user_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


# 请求上下文
request_context: ContextVar[RequestContext] = ContextVar(
    "request_context",
    default=RequestContext(),
)


def get_request_context() -> RequestContext:
    """获取当前请求上下文"""
    return request_context.get()


def set_request_context(ctx: RequestContext) -> None:
    """设置当前请求上下文"""
    request_context.set(ctx)


def get_current_user_id() -> UUID | None:
    """获取当前用户 ID（快捷方法）"""
    return request_context.get().user_id


def set_current_user_id(user_id: UUID | None) -> None:
    """设置当前用户 ID（快捷方法）"""
    ctx = request_context.get()
    ctx.user_id = user_id
    request_context.set(ctx)
