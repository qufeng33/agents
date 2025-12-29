# FastAPI 配置管理
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/app_users`。

> pydantic-settings 最佳实践

## 核心原则

1. **使用 .env 文件** - 管理开发环境配置
2. **敏感信息用 SecretStr** - 避免日志泄露密钥
3. **必填字段无默认值** - 启动时强制验证
4. **类型验证用 Field** - 利用 `ge`、`le` 等参数约束
5. **全局单例** - 配置类实例化一次（`@lru_cache`）
6. **使用 SettingsConfigDict** - 替代旧的 `class Config`

---

## 完整示例

```python
# app/config.py
from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# 嵌套配置模型（使用 BaseModel，不是 BaseSettings）
# ============================================================

class DatabaseConfig(BaseModel):
    """数据库配置"""
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = "mydb"
    user: str = "postgres"
    password: SecretStr

    @computed_field
    @property
    def url(self) -> str:
        """构建数据库连接 URL"""
        user = quote(self.user, safe="")
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"

    @computed_field
    @property
    def sync_url(self) -> str:
        """构建同步数据库连接 URL（psycopg，用于任务/同步场景）"""
        user = quote(self.user, safe="")
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql+psycopg://{user}:{password}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseModel):
    """Redis 配置"""
    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)


# ============================================================
# 主配置类
# ============================================================

class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",   # 嵌套分隔符：DB_HOST -> db.host
        env_nested_max_split=1,     # 只分割第一个 _，避免 DB_USER_NAME -> db.user.name
        extra="ignore",             # 忽略 .env 中未定义的变量
    )

    # ----------------------------------------------------------
    # 必填字段：无默认值，启动时验证
    # ----------------------------------------------------------
    secret_key: SecretStr

    # ----------------------------------------------------------
    # 可选字段：有默认值
    # ----------------------------------------------------------
    debug: bool = False
    app_name: str = "MyApp"
    log_level: str = "INFO"

    # ----------------------------------------------------------
    # 带约束的字段
    # ----------------------------------------------------------
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=32)

    # ----------------------------------------------------------
    # 列表字段：支持逗号分隔或 JSON 格式
    # ----------------------------------------------------------
    cors_origins: list[str] = []

    # ----------------------------------------------------------
    # 嵌套配置
    # ----------------------------------------------------------
    db: DatabaseConfig
    redis: RedisConfig = RedisConfig()  # 可选嵌套，有默认值

    # ----------------------------------------------------------
    # 计算属性（供 SQLAlchemy 等使用）
    # ----------------------------------------------------------
    @computed_field
    @property
    def database_url(self) -> str:
        return self.db.url

    # ----------------------------------------------------------
    # 自定义验证器
    # ----------------------------------------------------------
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level 必须是 {allowed} 之一")
        return upper

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """支持逗号分隔的字符串"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


# ============================================================
# 全局单例
# ============================================================

@lru_cache
def get_settings() -> Settings:
    """全局单例，避免重复解析"""
    return Settings()
```

对应 `.env` 文件：

```env
# 必填
SECRET_KEY=your-secret-key-here

# 可选（覆盖默认值）
DEBUG=true
APP_NAME=MyApp
LOG_LEVEL=debug
PORT=8000
WORKERS=4

# 列表（逗号分隔）
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# 嵌套配置（使用 _ 分隔）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=production_db
DB_USER=app_user
DB_PASSWORD=secret123

REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_DB=0
```

---

## FastAPI 集成

```python
# app/dependencies.py
from typing import Annotated
from fastapi import Depends

from .config import Settings, get_settings

# 类型别名，简化依赖声明
SettingsDep = Annotated[Settings, Depends(get_settings)]
```

```python
# app/routers/health.py
from fastapi import APIRouter

from ..dependencies import SettingsDep

router = APIRouter()


@router.get("/health")
def health_check(settings: SettingsDep):
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "debug": settings.debug,
    }
```

### 测试时覆盖配置

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def get_settings_override() -> Settings:
    return Settings(
        secret_key="test-secret-key",
        db={"host": "localhost", "port": 5432, "name": "test_db",
            "user": "test", "password": "test"},
        debug=True,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = get_settings_override
    yield TestClient(app)
    app.dependency_overrides.clear()
```

---

## 配置源优先级

从高到低：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | 构造函数参数 | `Settings(debug=True)` |
| 2 | 环境变量 | `export DEBUG=true` |
| 3 | .env 文件 | `env_file=".env"` |
| 4 | 字段默认值 | `debug: bool = False` |

---

## SettingsConfigDict 常用选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `env_file` | `str \| tuple` | `None` | .env 文件路径 |
| `env_file_encoding` | `str` | `None` | 文件编码 |
| `env_prefix` | `str` | `""` | 环境变量前缀 |
| `env_nested_delimiter` | `str` | `None` | 嵌套配置分隔符 |
| `env_nested_max_split` | `int` | `None` | 分隔符最大分割次数 |
| `case_sensitive` | `bool` | `False` | 是否区分大小写 |
| `extra` | `str` | `"forbid"` | 额外字段处理 |
| `validate_default` | `bool` | `True` | 是否验证默认值 |

---

## 常见问题

### Q: 为什么用 `@lru_cache`？

避免每次调用 `get_settings()` 都重新解析环境变量和 .env 文件。配置在应用生命周期内不变，缓存提升性能。

### Q: `extra="ignore"` vs `extra="forbid"`？

- `ignore`：忽略 .env 中未定义的变量（推荐）
- `forbid`：遇到未定义变量抛出错误

### Q: 嵌套模型用 BaseModel 还是 BaseSettings？

嵌套模型用 `BaseModel`，只有顶层配置类用 `BaseSettings`。嵌套的 BaseSettings 会导致重复读取环境变量。

### Q: SecretStr 如何获取实际值？

```python
settings = get_settings()
actual_key = settings.secret_key.get_secret_value()

# 安全：打印时自动隐藏
print(settings.secret_key)  # 输出: **********
```
