"""用户模型"""

from sqlalchemy import Boolean, Index, String
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

    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(50))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        # 全局唯一索引（软删除后仍不可复用）
        Index("uq_user_username", "username", unique=True),
    )
