# FastAPI 审计日志
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

记录谁、在什么时候、对什么数据、做了什么操作。用于合规、问题追溯、数据恢复。

## 设计原则
- 选择合适审计模式，避免过度
- 审计逻辑集中且可追溯
- 敏感字段默认脱敏
- 审计数据可查询、可索引
- 高并发场景考虑异步写入

## 最佳实践
1. 简单场景用字段级审计
2. 完整追踪用表级审计
3. contextvars 注入请求上下文
4. 按需配置审计范围
5. 审计表必须建索引

## 目录
- `审计模式对比`
- `字段级审计`
- `表级审计`
- `敏感字段脱敏`
- `请求上下文扩展`
- `审计日志索引优化`
- `相关文档`

---

## 审计模式对比

| 模式 | 记录内容 | 适用场景 |
|------|----------|----------|
| **字段级** | `created_by`, `updated_by` 字段 | 简单追踪"谁创建/修改" |
| **表级** | 独立审计表，记录完整变更历史 | 完整审计追踪、数据回溯 |

---

## 字段级审计

在业务表中增加 `created_by` / `updated_by` 字段，记录操作者。

> 审计字段的数据库设计见 [ORM 基类](./fastapi-database-orm.md)。

### 使用 contextvars 自动注入

```python
# core/context.py
from contextvars import ContextVar
from uuid import UUID

current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)


def get_current_user_id() -> UUID | None:
    return current_user_id.get()


def set_current_user_id(user_id: UUID | None) -> None:
    current_user_id.set(user_id)
```

### 中间件注入

```python
# core/middlewares.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import set_current_user_id
from app.core.security import decode_access_token


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = decode_access_token(token)

        set_current_user_id(user_id)
        return await call_next(request)
```

### 自动填充审计字段

```python
# core/audit.py
from sqlalchemy import event
from sqlalchemy.orm import Mapper

from app.core.context import get_current_user_id
from app.core.database import Base


@event.listens_for(Base, "before_insert", propagate=True)
def set_created_by(mapper: Mapper, connection, target):
    if hasattr(target, "created_by") and target.created_by is None:
        target.created_by = get_current_user_id()
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()


@event.listens_for(Base, "before_update", propagate=True)
def set_updated_by(mapper: Mapper, connection, target):
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()
```

---

## 表级审计

独立审计表记录所有变更，包含旧值/新值，支持数据回溯。

```python
# core/audit.py
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import SimpleBase, utc_now


class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditLog(SimpleBase):
    __tablename__ = "audit_log"

    table_name: Mapped[str] = mapped_column(String(100), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[AuditAction] = mapped_column(String(10))
    changed_by: Mapped[UUID | None] = mapped_column(index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
```

> 旧值/新值/变更字段可按需追加 JSONB 字段（`old_values`, `new_values`, `changed_fields`）。

### 变更对比核心逻辑

```python
# core/audit.py (续)
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import inspect


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
            if key.startswith("_") or key in relationship_keys:
                continue

            old_val = hist.deleted[0] if hist.deleted else None
            new_val = hist.added[0] if hist.added else getattr(target, key)

            old_values[key] = serialize_value(old_val)
            new_values[key] = serialize_value(new_val)
            changed_fields.append(key)

    return old_values, new_values, changed_fields


def serialize_value(value: Any) -> Any:
    """序列化值为 JSON 兼容格式（时间统一 ISO8601 UTC）"""
    if value is None:
        return None
    if isinstance(value, datetime):
        # 统一转换为 UTC ISO8601 格式
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        utc_value = value.astimezone(timezone.utc)
        return utc_value.isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
```

### SQLAlchemy 事件监听

```python
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.context import get_current_user_id

AUDITED_TABLES = {"app_user", "post", "order"}  # 配置需要审计的表


@event.listens_for(Session, "after_flush")
def audit_after_flush(session: Session, flush_context):
    for target in session.new:
        if hasattr(target, "__tablename__") and target.__tablename__ in AUDITED_TABLES:
            session.add(AuditLog(
                table_name=target.__tablename__,
                record_id=str(target.id),
                action=AuditAction.INSERT,
                changed_by=get_current_user_id(),
            ))

    for target in session.dirty:
        if hasattr(target, "__tablename__") and target.__tablename__ in AUDITED_TABLES:
            old_values, new_values, changed_fields = get_changes(target)
            if changed_fields:
                session.add(AuditLog(
                    table_name=target.__tablename__,
                    record_id=str(target.id),
                    action=AuditAction.UPDATE,
                    changed_by=get_current_user_id(),
                    # old_values=old_values,  # 需要 JSONB 字段
                    # new_values=new_values,
                ))
```

> 可选方案：使用 `__auditable__ = True` 模型标记代替全局表配置。

---

## 敏感字段脱敏

```python
SENSITIVE_FIELDS = {"password", "hashed_password", "access_token", "refresh_token", "secret_key"}


def sanitize_values(values: dict | None) -> dict | None:
    if values is None:
        return None
    return {k: "***REDACTED***" if k in SENSITIVE_FIELDS else v for k, v in values.items()}
```

---

## 请求上下文扩展

需要记录 IP/User-Agent/Request-ID 时，可扩展 `RequestContext` 并在中间件填充。

---

## 审计日志索引优化

审计表常见索引：
- `table_name + record_id`
- `changed_at`
- `changed_by`

---

## 相关文档

- [ORM 基类与软删除](./fastapi-database-orm.md)
- [权限控制](./fastapi-permissions.md)
- [错误处理](./fastapi-errors.md)
