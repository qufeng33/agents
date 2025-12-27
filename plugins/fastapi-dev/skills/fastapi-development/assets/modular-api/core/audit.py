"""审计日志 - Mixin 和事件监听"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, event, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Mapper, Session, mapped_column

from app.core.context import get_current_user_id, get_request_context
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
    需配合 RequestContextMiddleware 使用。
    """

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        default=None,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
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

    __tablename__ = "audit_log"

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


# ============================================================
# 表级审计 - 事件监听
# ============================================================

# 需要审计的表名（可按需调整）
# 示例：AUDITED_TABLES = {"user", "order"}
AUDITED_TABLES: set[str] = set()


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


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {k: serialize_value(v) for k, v in values.items()}


def _get_exclude_fields(target) -> set[str]:
    exclude = getattr(target, "__audit_exclude__", set())
    return set(exclude) if exclude else set()


def _filter_excluded(values: dict[str, Any], exclude_fields: set[str]) -> dict[str, Any]:
    if not exclude_fields:
        return values
    return {k: v for k, v in values.items() if k not in exclude_fields}


def _model_to_dict(target) -> dict[str, Any]:
    if hasattr(target, "__table__"):
        return {c.name: getattr(target, c.name) for c in target.__table__.columns}
    return {}


def get_changes(target) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """获取对象的变更：旧值、新值、变更字段列表"""
    insp = inspect(target)
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    changed_fields: list[str] = []

    relationship_keys = {rel.key for rel in insp.mapper.relationships}
    exclude_fields = _get_exclude_fields(target)
    for attr in insp.attrs:
        hist = attr.history
        if hist.has_changes():
            key = attr.key
            if key.startswith("_") or key in relationship_keys or key in exclude_fields:
                continue

            old_val = hist.deleted[0] if hist.deleted else None
            new_val = hist.added[0] if hist.added else getattr(target, key)

            old_values[key] = serialize_value(old_val)
            new_values[key] = serialize_value(new_val)
            changed_fields.append(key)

    return old_values, new_values, changed_fields


def _is_audited(target) -> bool:
    if isinstance(target, AuditLog):
        return False
    if getattr(target, "__auditable__", False):
        return True
    table_name = getattr(target, "__tablename__", None)
    return bool(table_name and table_name in AUDITED_TABLES)


def create_audit_log(
    session: Session,
    action: AuditAction,
    target,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    changed_fields: list[str] | None = None,
) -> None:
    """创建审计日志记录"""
    ctx = get_request_context()
    audit_log = AuditLog(
        table_name=target.__tablename__,
        record_id=str(getattr(target, "id", "")),
        action=action,
        old_values=sanitize_values(old_values),
        new_values=sanitize_values(new_values),
        changed_fields=changed_fields,
        changed_by=get_current_user_id(),
        changed_at=utc_now(),
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
    )
    session.add(audit_log)


@event.listens_for(Session, "after_flush")
def audit_after_flush(session: Session, flush_context) -> None:
    """flush 后记录审计日志"""
    for target in session.new:
        if _is_audited(target):
            exclude_fields = _get_exclude_fields(target)
            values = _filter_excluded(_model_to_dict(target), exclude_fields)
            create_audit_log(
                session,
                AuditAction.INSERT,
                target,
                new_values=_serialize_values(values),
            )

    for target in session.dirty:
        if _is_audited(target):
            old_values, new_values, changed_fields = get_changes(target)
            if changed_fields:
                create_audit_log(
                    session,
                    AuditAction.UPDATE,
                    target,
                    old_values=old_values,
                    new_values=new_values,
                    changed_fields=changed_fields,
                )

    for target in session.deleted:
        if _is_audited(target):
            exclude_fields = _get_exclude_fields(target)
            values = _filter_excluded(_model_to_dict(target), exclude_fields)
            create_audit_log(
                session,
                AuditAction.DELETE,
                target,
                old_values=_serialize_values(values),
            )
