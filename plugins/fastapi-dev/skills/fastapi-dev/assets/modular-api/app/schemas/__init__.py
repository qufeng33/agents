"""全局 Schema"""

from .datetime_types import UTCDateTime
from .response import ApiResponse, ApiPagedResponse, ErrorResponse

__all__ = ["UTCDateTime", "ApiResponse", "ApiPagedResponse", "ErrorResponse"]
