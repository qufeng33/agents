"""配置管理"""

from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseModel):
    """Redis 配置"""

    host: str = "localhost"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)

    @computed_field
    @property
    def url(self) -> str:
        """构建 Redis 连接 URL"""
        return f"redis://{self.host}:{self.port}/{self.db}"


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        extra="ignore",
    )

    # 必填字段
    secret_key: SecretStr

    # 应用配置
    app_name: str = "My API"
    debug: bool = False
    log_level: str = "INFO"

    # 数据库（嵌套配置）
    db: DatabaseConfig

    # Redis（可选）
    redis: RedisConfig = RedisConfig()

    # CORS（空列表=全放开，生产环境配置具体域名以启用 credentials）
    cors_origins: list[str] = []

    @computed_field
    @property
    def database_url(self) -> str:
        """数据库连接 URL（供 SQLAlchemy 使用）"""
        return self.db.url

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            msg = f"log_level 必须是 {allowed} 之一"
            raise ValueError(msg)
        return upper


@lru_cache
def get_settings() -> Settings:
    """全局单例"""
    return Settings()
