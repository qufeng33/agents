# FastAPI 配置管理
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

> pydantic-settings 最佳实践

## 设计原则
- 配置集中管理，应用内只读取一次
- 敏感信息必须使用 `SecretStr`
- 必填字段不设默认值，启动时强校验
- 类型与约束用 `Field` 明确表达
- 嵌套配置用 `BaseModel`，顶层用 `BaseSettings`

## 最佳实践
1. 使用 `.env` 管理开发环境配置
2. `@lru_cache` 保证全局单例
3. 使用 `SettingsConfigDict` 代替旧 `Config`
4. 可变默认值使用 `default_factory`
5. 配置源优先级明确、可预期

## 目录
- `最小示例`
- `FastAPI 集成`
- `配置源优先级`
- `SettingsConfigDict 常用选项`
- `常见问题`

---

## 最小示例

```python
# app/config.py
from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = "mydb"
    user: str = "postgres"
    password: SecretStr

    @computed_field
    @property
    def url(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        extra="ignore",
    )

    secret_key: SecretStr
    debug: bool = False
    log_level: str = "INFO"

    db: DatabaseConfig

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level 必须是 {allowed} 之一")
        return upper


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
```

> 其他配置字段（如 CORS、Redis、workers）可按需要添加，避免一次性堆入所有项。

对应 `.env` 文件：

```env
SECRET_KEY=your-secret-key-here
DEBUG=true
LOG_LEVEL=debug
DB_HOST=localhost
DB_PORT=5432
DB_NAME=production_db
DB_USER=postgres
DB_PASSWORD=secret123
```

> 使用 `DB_` 前缀配合 `env_nested_delimiter="_"` 生成嵌套配置。

---

## FastAPI 集成

通过依赖注入统一获取配置。建议将此依赖定义在 `app/dependencies.py` 中以避免循环导入。

```python
# app/dependencies.py
from typing import Annotated
from fastapi import Depends
from app.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

> 测试时可用 `dependency_overrides` 覆盖 `get_settings()`。

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

| 选项 | 说明 |
|------|------|
| `env_file` | .env 文件路径 |
| `env_file_encoding` | 文件编码 |
| `env_prefix` | 环境变量前缀 |
| `env_nested_delimiter` | 嵌套配置分隔符 |
| `env_nested_max_split` | 分隔符最大分割次数 |
| `extra` | 额外字段处理策略 |

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
