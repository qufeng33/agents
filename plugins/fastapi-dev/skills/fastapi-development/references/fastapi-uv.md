# uv 包管理

## 概述

uv 是 Astral 开发的极速 Python 包和项目管理器（Rust 编写），可替代 pip、pip-tools、pipx、poetry 等工具，速度提升 10-100 倍。

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pipx
pipx install uv

# 或 Homebrew (macOS)
brew install uv
```

---

## 项目初始化

```bash
# 创建新项目
uv init my-fastapi-project
cd my-fastapi-project

# 或在现有目录初始化
uv init

# 指定 Python 版本
uv init --python 3.13
```

### 生成的 pyproject.toml

```toml
[project]
name = "my-fastapi-project"
version = "0.1.0"
description = "My FastAPI project"
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 依赖管理

### 添加依赖

```bash
# 添加生产依赖
uv add fastapi
uv add "fastapi[standard]"  # 带 extras

# 添加多个依赖
uv add sqlalchemy alembic asyncpg

# 指定版本
uv add "pydantic>=2.7.0"
uv add "httpx==0.27.0"

# 添加开发依赖
uv add --dev pytest pytest-asyncio ruff

# 添加可选依赖组
uv add --group test pytest pytest-cov
uv add --group lint ruff

# 全局安装类型检查器（推荐）
uv tool install ty
```

### 移除依赖

```bash
uv remove requests
uv remove --dev pytest
```

### 从 requirements.txt 迁移

```bash
uv add -r requirements.txt
uv add --dev -r requirements-dev.txt
```

---

## pyproject.toml 配置

### FastAPI 项目示例

```toml
[project]
name = "my-fastapi-app"
version = "0.1.0"
description = "FastAPI application"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "fastapi[standard]>=0.127.0",
    "sqlalchemy>=2.0",
    "asyncpg>=0.30.0",
    "pydantic-settings>=2.7.0",
    "httpx>=0.27.0",
    "loguru>=0.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0",
    "ruff>=0.8.0",
]

[dependency-groups]
test = ["pytest>=8.0", "pytest-asyncio>=0.24.0", "pytest-cov>=6.0"]
lint = ["ruff>=0.8.0"]

# 注：类型检查使用 ty（uv tool install ty），无需添加为项目依赖

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]
```

---

## 环境与运行

### 同步环境

```bash
# 同步所有依赖（创建/更新 .venv）
uv sync

# 同步并锁定（CI 环境推荐）
uv sync --locked

# 只安装生产依赖
uv sync --no-dev

# 包含可选依赖组
uv sync --group test --group lint
```

### 运行命令

```bash
# 运行 Python 脚本
uv run python main.py

# 运行 FastAPI 开发服务器
uv run fastapi dev

# 运行测试
uv run pytest

# 运行 Ruff
uv run ruff check .

# 直接运行模块
uv run -m uvicorn app.main:app --reload
```

### 锁文件

```bash
# 生成/更新锁文件
uv lock

# 检查锁文件是否最新
uv lock --check

# 升级所有依赖
uv lock --upgrade

# 升级特定依赖
uv lock --upgrade-package fastapi
```

---

## Docker 集成

### 基础 Dockerfile

```dockerfile
FROM python:3.13-slim

# 复制 uv 二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 设置工作目录
WORKDIR /app

# 启用字节码编译（提升启动速度）
ENV UV_COMPILE_BYTECODE=1
# 复制模式（避免跨文件系统警告）
ENV UV_LINK_MODE=copy

# 先复制依赖文件（利用 Docker 缓存）
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --locked --no-dev --no-install-project

# 复制项目代码
COPY . .

# 安装项目
RUN uv sync --locked --no-dev

# 创建非 root 用户
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

# 使用 uv run 启动
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 多阶段构建（更小镜像）

```dockerfile
# 构建阶段
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

# 运行阶段
FROM python:3.13-slim

WORKDIR /app

# 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制应用代码
COPY --from=builder /app .

# 设置 PATH
ENV PATH="/app/.venv/bin:$PATH"

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 使用缓存加速构建

```dockerfile
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./

# 使用缓存挂载加速
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## GitHub Actions

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --locked

      - name: Run linting
        run: uv run ruff check .

      - name: Run type checking
        run: uvx ty check

      - name: Run tests
        run: uv run pytest --cov
```

---

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `uv init` | 初始化项目 |
| `uv add <pkg>` | 添加依赖 |
| `uv add --dev <pkg>` | 添加开发依赖 |
| `uv remove <pkg>` | 移除依赖 |
| `uv sync` | 同步环境 |
| `uv sync --locked` | 严格按锁文件同步 |
| `uv lock` | 生成/更新锁文件 |
| `uv lock --upgrade` | 升级所有依赖 |
| `uv run <cmd>` | 在项目环境中运行命令 |
| `uv python install 3.13` | 安装 Python 版本 |
| `uv python list` | 列出可用 Python 版本 |
| `uv tool install <tool>` | 全局安装工具 |
| `uv pip install <pkg>` | pip 兼容模式 |

---

## 最佳实践

1. **提交 uv.lock** - 锁文件应加入版本控制
2. **CI 使用 --locked** - 确保环境一致性
3. **分离依赖组** - 使用 `--group` 管理 test/lint 等
4. **Docker 缓存** - 先复制依赖文件，再复制代码
5. **字节码编译** - 生产环境设置 `UV_COMPILE_BYTECODE=1`
6. **固定 uv 版本** - Docker 中使用版本标签如 `uv:0.9.2`

---

## 从其他工具迁移

### 从 pip + requirements.txt

```bash
uv init
uv add -r requirements.txt
uv add --dev -r requirements-dev.txt
rm requirements*.txt
```

### 从 Poetry

```bash
# uv 可以直接读取 poetry 的 pyproject.toml
uv sync
```

### 从 pipenv

```bash
uv add -r <(pipenv requirements)
uv add --dev -r <(pipenv requirements --dev)
```
