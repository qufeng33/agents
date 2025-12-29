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


# 请求上下文（避免可变默认值导致跨请求污染）
request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def get_request_context() -> RequestContext:
    """获取当前请求上下文"""
    ctx = request_context.get()
    if ctx is None:
        ctx = RequestContext()
        request_context.set(ctx)
    return ctx


def set_request_context(ctx: RequestContext) -> None:
    """设置当前请求上下文"""
    request_context.set(ctx)


def get_current_user_id() -> UUID | None:
    """获取当前用户 ID（快捷方法）"""
    return get_request_context().user_id


def set_current_user_id(user_id: UUID | None) -> None:
    """设置当前用户 ID（快捷方法）"""
    ctx = get_request_context()
    ctx.user_id = user_id
    request_context.set(ctx)
