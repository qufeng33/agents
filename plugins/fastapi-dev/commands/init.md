---
name: fastapi-init
description: 交互式初始化 FastAPI 项目，支持简单结构和模块化结构
argument-hint: "[project-name]"
---

# FastAPI 项目初始化

使用 **fastapi-development** skill 的指南创建生产级 FastAPI 项目。

## Step 1: 收集需求

使用 AskUserQuestion 工具询问用户：

1. **项目名称**: 用于目录和包名
2. **结构类型**:
   - 简单结构 (simple): 小型 API、原型、单人开发
   - 模块化结构 (modular): 大型项目、团队协作
3. **认证方式**: JWT 认证 / 无认证
4. **Docker 支持**: 是否需要 Dockerfile / compose.yml

## Step 2: 初始化项目

```bash
uv init {project_name}
cd {project_name}

# 核心依赖
uv add "fastapi[standard]" sqlalchemy asyncpg alembic loguru

# 如果需要认证
uv add "python-jose[cryptography]" "passlib[bcrypt]"

# 开发依赖
uv add --dev pytest pytest-asyncio httpx ruff ty
```

## Step 3: 创建项目结构

根据用户选择的结构类型，参考 **fastapi-development** skill 中的项目结构创建目录和文件：

- 简单结构：按层组织 (routers/, schemas/, services/, models/, core/)
- 模块化结构：按领域组织 (modules/{domain}/ 包含完整 7 文件)

详见 skill 的 `references/fastapi-project-structure.md`

## Step 4: 配置工具

在 pyproject.toml 中添加工具配置，参考 **fastapi-development** skill：

- pytest: asyncio_mode, testpaths
- ruff: select 规则, ignore 规则（含中文环境优化）

详见 skill 的 `references/fastapi-coding-conventions.md`

## Step 5: 生成代码文件

使用 **fastapi-development** skill 中的模板生成：

- `app/main.py` - 应用入口（lifespan 模式）
- `app/config.py` - 配置管理（pydantic-settings）
- `app/core/database.py` - 数据库连接
- 其他必要文件

## Step 6: 完成设置

```bash
git init
alembic init alembic
```

提示用户下一步：
- 配置 `.env` 文件
- `alembic revision --autogenerate -m "init"`
- `alembic upgrade head`
- `uv run uvicorn app.main:app --reload`

## 关键点

- 使用 AskUserQuestion 交互式询问需求
- 参考 fastapi-development skill 获取详细模板
- 生成的代码应该可以直接运行
- 包含必要的配置文件（.gitignore, .env.example）
