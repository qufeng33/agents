---
name: fastapi-init
description: 交互式初始化 FastAPI 项目，支持简单结构和模块化结构
---

# FastAPI 项目初始化

你是 FastAPI 项目初始化专家。请按照以下步骤创建一个生产级的 FastAPI 项目。

## Step 1: 收集需求

使用 AskUserQuestion 工具询问用户以下信息：

1. **项目名称**: 项目的名称（用于目录和包名）
2. **结构类型**:
   - 简单结构 (simple): 适合小型 API、原型
   - 模块化结构 (modular): 适合大型项目、团队协作
3. **认证方式**:
   - JWT 认证
   - 无认证
4. **Docker 支持**: 是否需要 Docker 配置

## Step 2: 创建项目结构

根据用户选择的结构类型创建相应的目录和文件。

### 简单结构

```
{project}/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── health.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── database.py
│       ├── security.py (如果需要认证)
│       └── exceptions.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
└── docker/ (如果需要)
    ├── Dockerfile
    └── docker-compose.yml
```

### 模块化结构

```
{project}/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py
│   ├── modules/
│   │   ├── __init__.py
│   │   └── health/
│   │       ├── __init__.py
│   │       └── router.py
│   └── core/
│       ├── __init__.py
│       ├── database.py
│       ├── deps.py
│       ├── security.py (如果需要认证)
│       └── exceptions.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── modules/
│       └── health/
│           └── test_router.py
└── docker/ (如果需要)
    ├── Dockerfile
    └── docker-compose.yml
```

## Step 3: 生成文件内容

### pyproject.toml

```toml
[project]
name = "{project_name}"
version = "0.1.0"
description = "A FastAPI application"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.28.0",
    "alembic>=1.12.0",
    # 如果需要认证
    # "python-jose[cryptography]>=3.3.0",
    # "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.25.0",
    "ruff>=0.1.0",
    "mypy>=1.6.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "ASYNC"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### app/main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# 根据结构类型添加路由
# 简单结构:
# from app.routers import health
# app.include_router(health.router)

# 模块化结构:
# from app.api.v1.router import router as v1_router
# app.include_router(v1_router, prefix="/api")
```

### app/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "{project_name}"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/{project_name}"

    # 如果需要认证
    # SECRET_KEY: str = "change-me"
    # ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()
```

## Step 4: 初始化项目

创建完所有文件后：

1. 初始化 git 仓库
2. 提示用户下一步操作：
   - `uv sync` 安装依赖
   - 配置 `.env` 文件
   - `alembic upgrade head` 运行迁移
   - `uvicorn app.main:app --reload` 启动服务

## 关键点

- 使用 AskUserQuestion 交互式询问需求
- 根据用户选择生成对应的结构
- 生成的代码应该是可以直接运行的
- 包含必要的配置文件（.gitignore, .env.example 等）
- 包含基础的健康检查端点
