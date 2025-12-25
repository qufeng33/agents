---
name: fastapi-init
description: 交互式初始化 FastAPI 项目，支持简单结构和模块化结构
argument-hint: "[project-name]"
allowed-tools: Bash(pwd:*), Bash(ls:*), Bash(test:*), Bash(basename:*)
---

# FastAPI 项目初始化

使用 **fastapi-development** skill 的指南创建生产级 FastAPI 项目。

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

### 情况 A: 当前目录已是 FastAPI 项目
- 提示用户项目已存在
- 询问是否需要补充缺失的文件或结构

### 情况 B: 当前目录为空（或仅有 .git）
- **使用当前目录**作为项目根路径
- 项目名称 = `$ARGUMENTS` 或当前目录名称
- 执行 `uv init .`（在当前目录初始化，不创建子目录）

### 情况 C: 当前目录非空但不是 FastAPI 项目
- 如果 `$ARGUMENTS` 提供了项目名称：创建子目录并初始化
- 如果没有提供：询问用户选择
  - 在当前目录初始化（覆盖风险提示）
  - 创建子目录（需提供名称）

### 情况 D: 用户明确指定了项目名称
- 创建 `{project_name}` 子目录并进入

## Step 1: 确认项目配置

使用 AskUserQuestion 工具确认以下配置：

1. **项目名称**: 根据检测结果预填（`$ARGUMENTS` > 当前目录名）
2. **结构类型**:
   - 简单结构 (simple): 小型 API、原型、单人开发
   - 模块化结构 (modular): 大型项目、团队协作
3. **认证方式**: JWT 认证 / 无认证
4. **Docker 支持**: 是否需要 Dockerfile / compose.yml

## Step 2: 初始化项目

根据情况执行不同的初始化命令：

```bash
# 情况 B: 在当前空目录初始化
uv init .

# 情况 C/D: 创建新子目录
uv init {project_name}
cd {project_name}
```

安装依赖：

```bash
# 核心依赖
uv add "fastapi[standard]" sqlalchemy asyncpg alembic loguru

# 如果需要认证
uv add pyjwt "pwdlib[argon2]"

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
git init  # 如果尚未初始化
alembic init alembic
```

提示用户下一步：
- 配置 `.env` 文件
- `alembic revision --autogenerate -m "init"`
- `alembic upgrade head`
- `uv run uvicorn app.main:app --reload`

## 关键点

- 智能检测当前目录状态，避免创建不必要的嵌套目录
- 使用 AskUserQuestion 交互式确认配置
- 参考 fastapi-development skill 获取详细模板
- 生成的代码应该可以直接运行
- 包含必要的配置文件（.gitignore, .env.example）
