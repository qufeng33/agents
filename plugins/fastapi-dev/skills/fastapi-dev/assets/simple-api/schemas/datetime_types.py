"""日期时间类型定义"""

from datetime import datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, PlainSerializer

# 默认时区：东8区（北京时间）
DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")


def ensure_utc_aware(dt: datetime) -> datetime:
    """
    确保 datetime 是 UTC aware

    - naive datetime: 假定为东8区，转换为 UTC
    - aware datetime: 转换为 UTC
    """
    if dt.tzinfo is None:
        # naive datetime 假定为东8区
        dt = dt.replace(tzinfo=DEFAULT_TIMEZONE)
    return dt.astimezone(timezone.utc)


def serialize_to_iso8601z(dt: datetime) -> str:
    """序列化为 ISO8601 UTC 格式（Z 后缀）"""
    utc_dt = ensure_utc_aware(dt)
    return utc_dt.isoformat().replace("+00:00", "Z")


# 统一的 datetime 类型
# - 输入时：naive datetime 按东8区处理，统一转换为 UTC
# - 输出时：序列化为 ISO8601 UTC 格式（Z 后缀）
UTCDateTime = Annotated[
    datetime,
    AfterValidator(ensure_utc_aware),
    PlainSerializer(serialize_to_iso8601z),
]
