"""配置管理"""

from functools import lru_cache
from urllib.parse import quote

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
    access_token_expire_minutes: int = Field(default=30, ge=1)

    # 数据库（嵌套配置）
    db: DatabaseConfig

    # CORS
    cors_origins: list[str] = []

    @computed_field
    @property
    def database_url(self) -> str:
        """数据库连接 URL（供 SQLAlchemy 使用）"""
        return self.db.url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """全局单例"""
    return Settings()
