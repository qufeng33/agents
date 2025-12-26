"""审计日志 - Mixin 和事件监听"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.core.context import get_current_user_id
from app.core.database import Base, SimpleBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 字段级审计 - Mixin
# ============================================================


class AuditMixin:
    """
    审计字段 Mixin

    提供 created_by / updated_by 字段，记录操作者。
    需配合 UserContextMiddleware 使用。
    """

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )


# 自动填充审计字段
@event.listens_for(Base, "before_insert", propagate=True)
def set_created_by(mapper: Mapper, connection, target) -> None:
    """插入前自动填充 created_by"""
    if hasattr(target, "created_by") and target.created_by is None:
        target.created_by = get_current_user_id()
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()


@event.listens_for(Base, "before_update", propagate=True)
def set_updated_by(mapper: Mapper, connection, target) -> None:
    """更新前自动填充 updated_by"""
    if hasattr(target, "updated_by"):
        target.updated_by = get_current_user_id()


# ============================================================
# 表级审计 - 完整变更历史
# ============================================================


class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditLog(SimpleBase):
    """
    审计日志表

    记录所有实体的变更历史。
    """

    __tablename__ = "audit_logs"

    # 变更信息
    table_name: Mapped[str] = mapped_column(String(100), index=True)
    record_id: Mapped[str] = mapped_column(String(36), index=True)
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

    # 请求信息
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_audit_table_record", "table_name", "record_id"),
        Index("ix_audit_table_time", "table_name", "changed_at"),
    )


# ============================================================
# 敏感字段脱敏
# ============================================================

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
        k: "***REDACTED***" if k in SENSITIVE_FIELDS else v for k, v in values.items()
    }
