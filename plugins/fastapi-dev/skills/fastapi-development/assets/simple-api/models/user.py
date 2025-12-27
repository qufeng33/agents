"""用户模型"""

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """
    用户模型

    继承自 Base，自动获得：
    - id: UUIDv7 主键
    - created_at, updated_at: 时间戳
    - deleted_at: 软删除
    """

    __tablename__ = "user"

    email: Mapped[str] = mapped_column(String(255), index=True)
    username: Mapped[str] = mapped_column(String(50))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        # 部分唯一索引：只对未删除的记录强制唯一
        Index(
            "uq_user_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
