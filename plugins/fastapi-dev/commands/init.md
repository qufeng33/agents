---
name: init
description: 交互式初始化 FastAPI 项目，支持简单结构和模块化结构
argument-hint: "[project-name]"
allowed-tools: Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(basename:*)
---

# FastAPI 项目初始化

## 当前环境检测

- 当前目录: !`pwd`
- 目录名称: !`basename "$(pwd)"`
- 是否为空目录: !`[ -z "$(ls -A 2>/dev/null)" ] && echo "yes" || echo "no"`
- 是否存在 pyproject.toml: !`test -f pyproject.toml && echo "yes" || echo "no"`
- 是否已有 FastAPI: !`test -f pyproject.toml && grep -q 'fastapi' pyproject.toml 2>/dev/null && echo "yes" || echo "no"`

## 参数

用户提供的项目名称: `$ARGUMENTS`

## 初始化逻辑

根据上述检测结果，按以下逻辑处理：

| 情况 | 条件 | 处理方式 |
|------|------|----------|
| A | 当前目录已是 FastAPI 项目 | 提示已存在，询问是否补充缺失文件 |
| B | 当前目录为空（或仅有 .git） | 在当前目录初始化，`uv init .` |
| C | 当前目录非空但不是 FastAPI 项目 | 询问用户：当前目录 or 创建子目录 |
| D | 用户明确指定了项目名称 | 创建子目录并进入 |

## Step 1: 确认项目配置

使用 AskUserQuestion 工具确认：

1. **项目名称**: `$ARGUMENTS` > 当前目录名
2. **结构类型**:
   - **简单结构**: 小项目、原型、单人开发（`Router → Service → Database`）
   - **模块化结构**: 团队开发、中大型项目（`Router → Service → Repository → Database`）
3. **认证方式**: JWT 认证 / 无认证
4. **Docker 支持**: 是否需要

> 结构选择标准见 **fastapi-development** skill

## Step 2: 初始化项目

1. 根据情况执行 `uv init .` 或 `uv init {project_name}`
2. 安装核心依赖：`fastapi[standard]`, `sqlalchemy`, `asyncpg`, `alembic`, `loguru`, `pydantic-settings`
3. 如需认证：`pyjwt`, `pwdlib[argon2]`
4. 开发依赖：`pytest`, `pytest-asyncio`, `httpx`, `ruff`

## Step 3: 创建项目结构

根据用户选择的结构类型生成目录和文件：

| 结构 | 模板 | 特点 |
|------|------|------|
| 简单 | `assets/simple-api/` | 无 Repository 层，main.py 直接配置 |
| 模块化 | `assets/modular-api/` | 有 Repository 层，create_app 工厂模式 |

> 参考 **fastapi-development** skill 的 `references/fastapi-project-structure.md` 和 `assets/` 模板

## Step 4: 配置工具

在 pyproject.toml 中添加 pytest / ruff 配置。

> 参考 **fastapi-development** skill 的 `references/fastapi-tooling.md`

## Step 5: 生成代码文件

根据选择的结构类型，从 `assets/` 模板生成核心文件：

- `app/main.py` - 应用入口（lifespan 模式）
- `app/config.py` - 配置管理
- `app/core/database.py` - 数据库连接
- `app/core/security.py` - 认证模块（如需要）

> 参考 **fastapi-development** skill 的 `assets/simple-api/` 或 `assets/modular-api/`

## Step 6: 完成设置

1. `git init`（如尚未初始化）
2. `alembic init alembic`
3. 生成 `.env.example` 和 `.gitignore`

提示用户下一步：
- 配置 `.env` 文件
- 修改 `alembic/env.py`
- `alembic revision --autogenerate -m "init"`
- `uv run fastapi dev`

## 后续开发引导

提示用户：

> 项目初始化完成！后续开发中，你可以直接描述需求（如"添加用户注册接口"），**fastapi-pro** agent 会自动介入处理。

**重要**：如果用户继续提出 FastAPI 相关的开发需求，**必须**主动使用 **fastapi-pro** agent 来处理。


