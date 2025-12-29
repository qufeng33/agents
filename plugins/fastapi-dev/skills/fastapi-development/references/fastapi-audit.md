# FastAPI 审计日志

记录谁、在什么时候、对什么数据、做了什么操作。用于合规、问题追溯、数据恢复。

---

## 审计模式对比

| 模式 | 记录内容 | 适用场景 |
|------|----------|----------|
| **字段级** | `created_by`, `updated_by` 字段 | 简单追踪"谁创建/修改了" |
| **表级** | 独立审计表，记录完整变更历史 | 完整审计追踪、数据回溯 |

---

## 字段级审计

在业务表中增加 `created_by` / `updated_by` 字段，记录操作者。

> 审计字段的数据库设计（类型、外键、命名规范）请参考 [ORM 基类](./fastapi-database-orm.md)。

### 使用 contextvars 自动注入

使用 `contextvars` 存储当前请求的用户，避免在每个 Service 方法中显式传递。

```python
# core/context.py
from contextvars import ContextVar
from uuid import UUID

# 当前用户上下文
current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)


def get_current_user_id() -> UUID | None:
    """获取当前用户 ID"""
    return current_user_id.get()


def set_current_user_id(user_id: UUID | None) -> None:
    """设置当前用户 ID"""
    current_user_id.set(user_id)
```

### 中间件注入

```python
# core/middlewares.py
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import set_current_user_id
from app.core.security import decode_access_token


class RequestContextMiddleware(BaseHTTPMiddleware):
    """从 JWT 中提取用户 ID 并注入到上下文"""

    async def dispatch(self, request: Request, call_next):
        user_id: UUID | None = None

        # 从 Authorization header 提取
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = decode_access_token(token)

        set_current_user_id(user_id)

        response = await call_next(request)
        return response
```

```python
# main.py
from app.core.middlewares import RequestContextMiddleware

app.add_middleware(RequestContextMiddleware)
```

### 自动填充审计字段

```python
# core/audit.py（续）
from sqlalchemy import event
from sqlalchemy.orm import Mapper

from app.core.context import get_current_user_id
from app.core.database import Base


@event.listens_for(Base, "before_insert", propagate=True)
def set_created_by(mapper: Mapper, connection, target):
    """插入前自动填充 created_by"""
    if hasattr(target, "created_by") and target.created_by is None:
        target.created_by = get_current_user_id()
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()


@event.listens_for(Base, "before_update", propagate=True)
def set_updated_by(mapper: Mapper, connection, target):
    """更新前自动填充 updated_by"""
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()
```

### 完整模型示例

> AuditMixin 的字段定义见 [ORM 基类](./fastapi-database-orm.md)。

```python
# modules/post/models.py
from app.core.database import Base
from app.core.audit import AuditMixin


class Post(AuditMixin, Base):
    __tablename__ = "post"

    title: Mapped[str]
    content: Mapped[str]

    # 继承自 Base: id, created_at, updated_at, deleted_at
    # 继承自 AuditMixin: created_by, updated_by
```

---

## 表级审计

独立审计表记录所有变更，包含旧值/新值，支持数据回溯。

### AuditLog 模型

```python
# core/audit.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import SimpleBase, utc_now


class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditLog(SimpleBase):
    """
    审计日志表

    记录所有实体的变更历史。
    """

    __tablename__ = "audit_log"

    # 变更信息
    table_name: Mapped[str] = mapped_column(String(100), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)  # UUID as string
    action: Mapped[AuditAction] = mapped_column(String(10))

    # 变更内容
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    changed_fields: Mapped[list[str] | None] = mapped_column(JSONB, default=None)

    # 操作者
    changed_by: Mapped[UUID | None] = mapped_column(index=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )

    # 可选：请求信息
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
```

### SQLAlchemy 事件监听

```python
# core/audit.py（续）
import json
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.context import get_current_user_id


def get_changes(target) -> tuple[dict, dict, list[str]]:
    """获取对象的变更：旧值、新值、变更字段列表"""
    insp = inspect(target)
    old_values = {}
    new_values = {}
    changed_fields = []

    relationship_keys = {rel.key for rel in insp.mapper.relationships}
    for attr in insp.attrs:
        hist = attr.history
        if hist.has_changes():
            key = attr.key
            # 跳过关系和内部属性
            if key.startswith("_") or key in relationship_keys:
                continue

            old_val = hist.deleted[0] if hist.deleted else None
            new_val = hist.added[0] if hist.added else getattr(target, key)

            old_values[key] = serialize_value(old_val)
            new_values[key] = serialize_value(new_val)
            changed_fields.append(key)

    return old_values, new_values, changed_fields


def serialize_value(value) -> Any:
    """序列化值为 JSON 兼容格式"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def create_audit_log(
    session: Session,
    action: AuditAction,
    target,
    old_values: dict | None = None,
    new_values: dict | None = None,
    changed_fields: list[str] | None = None,
) -> None:
    """创建审计日志记录"""
    audit_log = AuditLog(
        table_name=target.__tablename__,
        record_id=str(target.id),
        action=action,
        old_values=old_values,
        new_values=new_values,
        changed_fields=changed_fields,
        changed_by=get_current_user_id(),
    )
    session.add(audit_log)


# 需要审计的表
AUDITED_TABLES = {"user", "post", "order"}


@event.listens_for(Session, "after_flush")
def audit_after_flush(session: Session, flush_context):
    """flush 后记录审计日志"""

    # 新增
    for target in session.new:
        if hasattr(target, "__tablename__") and target.__tablename__ in AUDITED_TABLES:
            create_audit_log(
                session,
                AuditAction.INSERT,
                target,
                new_values=target.to_dict(),
            )

    # 更新
    for target in session.dirty:
        if hasattr(target, "__tablename__") and target.__tablename__ in AUDITED_TABLES:
            old_values, new_values, changed_fields = get_changes(target)
            if changed_fields:  # 有实际变更
                create_audit_log(
                    session,
                    AuditAction.UPDATE,
                    target,
                    old_values=old_values,
                    new_values=new_values,
                    changed_fields=changed_fields,
                )

    # 删除
    for target in session.deleted:
        if hasattr(target, "__tablename__") and target.__tablename__ in AUDITED_TABLES:
            create_audit_log(
                session,
                AuditAction.DELETE,
                target,
                old_values=target.to_dict(),
            )
```

### 配置需要审计的表

```python
# 方式 1：全局配置
AUDITED_TABLES = {"user", "post", "order"}

# 方式 2：模型级标记
class Auditable:
    """标记为需要审计的 Mixin"""
    __auditable__ = True


class Order(Auditable, Base):
    __tablename__ = "order"
    # ...


# 事件监听中检查
if getattr(target, "__auditable__", False):
    create_audit_log(...)
```

---

## 查询审计日志

### AuditLogRepository

```python
# modules/audit/repository.py
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditAction, AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_record(
        self,
        resource: str,
        record_id: UUID,
    ) -> list[AuditLog]:
        """获取某条记录的变更历史"""
        stmt = (
            select(AuditLog)
            .where(AuditLog.table_name == resource)
            .where(AuditLog.record_id == str(record_id))
            .order_by(AuditLog.changed_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_time_range(
        self,
        start: datetime,
        end: datetime,
        resource: str | None = None,
        user_id: UUID | None = None,
    ) -> list[AuditLog]:
        """获取时间范围内的变更"""
        stmt = (
            select(AuditLog)
            .where(AuditLog.changed_at >= start)
            .where(AuditLog.changed_at <= end)
        )
        if resource:
            stmt = stmt.where(AuditLog.table_name == resource)
        if user_id:
            stmt = stmt.where(AuditLog.changed_by == user_id)
        stmt = stmt.order_by(AuditLog.changed_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """获取某用户的操作记录"""
        stmt = (
            select(AuditLog)
            .where(AuditLog.changed_by == user_id)
            .order_by(AuditLog.changed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
```

### 审计日志 API

```python
# modules/audit/router.py
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import require_admin
from app.schemas.response import ApiResponse
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/records",
    response_model=ApiResponse[list[AuditLogResponse]],
    dependencies=[Depends(require_admin)],
)
async def list_audit_records(
    start: datetime,
    end: datetime,
    resource: str | None = None,
    user_id: UUID | None = None,
    repo: AuditLogRepository = Depends(),
):
    """按时间范围查询审计日志（主入口）"""
    records = await repo.get_by_time_range(
        start,
        end,
        resource=resource,
        user_id=user_id,
    )
    return ApiResponse(data=records)

# 说明：
# resource 表示业务资源名（如 users、orders），建议用资源名到表名的映射表（users -> user, orders -> order）。


@router.get(
    "/records/{resource}/{record_id}",
    response_model=ApiResponse[list[AuditLogResponse]],
    dependencies=[Depends(require_admin)],
)
async def get_record_history(
    resource: str,
    record_id: UUID,
    repo: AuditLogRepository = Depends(),
):
    """追溯单条记录的变更历史（管理员场景）"""
    records = await repo.get_by_record(resource, record_id)
    return ApiResponse(data=records)
```

---

## 敏感字段脱敏

某些字段（如密码、token）不应记录在审计日志中。

### 配置脱敏字段

```python
# core/audit.py
SENSITIVE_FIELDS = {
    "password",
    "hashed_password",
    "access_token",
    "refresh_token",
    "secret_key",
    "api_key",
}


def sanitize_values(values: dict | None) -> dict | None:
    """脱敏敏感字段"""
    if values is None:
        return None
    return {
        k: "***REDACTED***" if k in SENSITIVE_FIELDS else v
        for k, v in values.items()
    }


# 在 create_audit_log 中使用
def create_audit_log(...):
    audit_log = AuditLog(
        ...
        old_values=sanitize_values(old_values),
        new_values=sanitize_values(new_values),
        ...
    )
```

### 模型级配置

```python
class User(Base):
    __tablename__ = "user"
    __audit_exclude__ = {"hashed_password", "reset_token"}  # 排除的字段

    email: Mapped[str]
    hashed_password: Mapped[str]
    reset_token: Mapped[str | None]
```

```python
# 在 get_changes 中检查
exclude_fields = getattr(target, "__audit_exclude__", set())
if key in exclude_fields:
    continue
```

---

## 请求上下文扩展

记录更多请求信息用于审计。

```python
# core/context.py（扩展）
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass
class RequestContext:
    user_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


request_context: ContextVar[RequestContext] = ContextVar(
    "request_context",
    default=RequestContext(),
)


def get_request_context() -> RequestContext:
    return request_context.get()


def set_request_context(ctx: RequestContext) -> None:
    request_context.set(ctx)
```

```python
# core/middlewares.py（扩展）
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ctx = RequestContext(
            user_id=extract_user_id(request),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            request_id=request.headers.get("X-Request-ID", str(uuid7())),
        )
        set_request_context(ctx)

        response = await call_next(request)
        response.headers["X-Request-ID"] = ctx.request_id
        return response


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

---

## 审计日志索引优化

```python
class AuditLog(SimpleBase):
    __tablename__ = "audit_log"
    __table_args__ = (
        # 按记录查询
        Index("ix_audit_table_record", "table_name", "record_id"),
        # 按时间范围查询
        Index("ix_audit_changed_at", "changed_at"),
        # 按用户查询
        Index("ix_audit_changed_by", "changed_by"),
        # 复合查询
        Index("ix_audit_table_time", "table_name", "changed_at"),
    )
```

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **选择合适的模式** | 简单场景用字段级，完整追踪用表级 |
| **contextvars 注入** | 避免显式传递用户，代码更干净 |
| **敏感字段脱敏** | 永远不记录密码、token 等 |
| **按需审计** | 不是所有表都需要审计，配置 `AUDITED_TABLES` |
| **索引优化** | 审计表数据量大，必须建立合适索引 |
| **定期归档** | 审计日志增长快，考虑分区或归档策略 |
| **异步写入** | 高并发场景可考虑消息队列异步写入 |
