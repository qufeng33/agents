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
2. **结构类型**（选择标准见 **fastapi-development** SKILL.md）:
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

# 如果需要认证（详见 references/fastapi-security.md）
uv add pyjwt "pwdlib[argon2]"

# 开发依赖
uv add --dev pytest pytest-asyncio httpx ruff ty
```

## Step 3: 创建项目结构

根据用户选择的结构类型创建目录和文件：

**两种结构都遵循 Router → Service → Repository 分层模式**

- 目录布局：见 **fastapi-development** SKILL.md 的「项目结构」章节
- 详细说明：见 `references/fastapi-project-structure.md`

## Step 4: 配置工具

在 pyproject.toml 中添加工具配置：

- pytest / ruff / ty 配置：见 `references/fastapi-tooling.md`

## Step 5: 生成代码文件

生成核心文件，遵循 **fastapi-development** 的核心原则：

| 文件 | 说明 | 参考 |
|------|------|------|
| `app/main.py` | 应用入口（lifespan 模式） | SKILL.md |
| `app/config.py` | 配置管理（pydantic-settings） | SKILL.md |
| `app/core/database.py` | 数据库连接 | `references/fastapi-database.md` |
| `app/core/security.py` | 认证模块（如需要） | `references/fastapi-security.md` |

## Step 6: 完成设置

```bash
git init  # 如果尚未初始化
alembic init alembic
```

提示用户下一步：
- 配置 `.env` 文件
- 修改 `alembic/env.py` 配置
- `alembic revision --autogenerate -m "init"`
- `alembic upgrade head`
- `uv run fastapi dev`

## 关键点

- 智能检测当前目录状态，避免创建不必要的嵌套目录
- 两种结构都使用 Router → Service → Repository 分层
- 使用 AskUserQuestion 交互式确认配置
- 生成的代码应该可以直接运行
- 包含必要的配置文件（.gitignore, .env.example）

## 后续开发引导

初始化完成后，提示用户：

> 项目初始化完成！后续开发中，你可以直接描述需求（如"添加用户注册接口"、"实现 JWT 认证"），**fastapi-pro** agent 会自动介入处理复杂的 FastAPI 开发任务。

如果用户继续提出 FastAPI 相关的开发需求，应主动使用 **fastapi-pro** agent 来处理。
