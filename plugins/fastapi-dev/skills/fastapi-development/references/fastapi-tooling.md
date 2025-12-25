# FastAPI 开发工具

## uv 包管理

极速 Python 包管理器（Rust 编写），比 pip 快 10-100 倍。

```bash
# 安装
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 常用命令

```bash
# 项目初始化
uv init my-project --python 3.13

# 依赖管理
uv add fastapi sqlalchemy          # 添加依赖
uv add --dev pytest ruff           # 开发依赖
uv remove requests                 # 移除依赖

# 环境同步
uv sync                            # 同步依赖
uv sync --locked                   # 严格锁定（CI 用）
uv sync --no-dev                   # 只生产依赖

# 运行
uv run fastapi dev                 # 开发服务器
uv run pytest                      # 测试
uv run ruff check .                # Lint

# 锁文件
uv lock                            # 生成
uv lock --upgrade                  # 升级所有
```

### pyproject.toml 示例

```toml
[project]
name = "my-fastapi-app"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi[standard]>=0.127.0",
    "sqlalchemy>=2.0",
    "pydantic-settings>=2.7.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Ruff 代码检查

极速 linter + formatter，替代 flake8、isort、black。

```bash
uv add --dev ruff

ruff check .          # 检查
ruff check . --fix    # 自动修复
ruff format .         # 格式化
```

### 配置

```toml
[tool.ruff]
target-version = "py313"
line-length = 100
exclude = [".venv", "migrations"]

[tool.ruff.lint]
select = [
    "E", "W",     # pycodestyle
    "F",          # Pyflakes
    "I",          # isort
    "B",          # bugbear
    "UP",         # pyupgrade
    "SIM",        # simplify
    "ASYNC",      # async
    "ANN",        # annotations
    "S",          # security
    "RUF",        # Ruff 规则
]
ignore = [
    "ANN101",     # missing self type
    "ANN102",     # missing cls type
    "RUF001",     # 中文环境：字符串中的 Unicode
    "RUF002",     # 中文环境：docstring 中的 Unicode
    "RUF003",     # 中文环境：注释中的 Unicode
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ANN"]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```

---

## ty 类型检查

Astral 的极速类型检查器，比 mypy 快 10-100 倍。

```bash
# 安装（全局工具）
uv tool install ty

# 运行
ty check
ty check --watch     # 监听模式
uvx ty check         # 无需安装
```

### 配置

```toml
[tool.ty]
python-version = "3.13"

[tool.ty.rules]
unresolved-import = "error"
unresolved-attribute = "warn"
possibly-unbound = "warn"

[tool.ty.src]
exclude = ["migrations/**", ".venv/**"]
```

---

## pre-commit

```bash
uv add --dev pre-commit
uv run pre-commit install
```

### 配置

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: ty
        name: ty check
        entry: uvx ty check
        language: system
        types: [python]
        pass_filenames: false
```

---

## pytest 配置

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

---

## Docker 集成

uv 与 Docker 配合使用的要点：

- **复制 uv 二进制** - `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`
- **启用字节码编译** - `UV_COMPILE_BYTECODE=1` 提升启动速度
- **分层缓存** - 先复制 `pyproject.toml` 和 `uv.lock`，再复制代码
- **多阶段构建** - 减小最终镜像体积

> 完整的 Dockerfile、docker-compose、Kubernetes 配置详见 [部署](./fastapi-deployment.md)

---

## 命名规范速查

### 文件/模块

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | `lowercase` | `users`, `auth` |
| 路由文件 | `router.py` 或 `{resource}.py` | `users.py` |
| 服务文件 | `service.py` 或 `{resource}_service.py` | `user_service.py` |

### 代码元素

| 类型 | 规范 | 示例 |
|------|------|------|
| 函数 | `snake_case` | `get_user`, `create_order` |
| 类 | `PascalCase` | `UserService`, `OrderRepository` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_CONNECTIONS` |
| 异常 | `PascalCase` + `Error` | `UserNotFoundError` |

### Pydantic 模型

| 后缀 | 用途 |
|------|------|
| `Create` | 创建请求 |
| `Update` | 完整更新 |
| `Patch` | 部分更新 |
| `Response` | API 响应 |
| `InDB` | 数据库内部 |

### 路由函数

| HTTP 方法 | 命名模式 | 示例 |
|-----------|----------|------|
| GET (列表) | `list_` | `list_users` |
| GET (单个) | `get_` | `get_user` |
| POST | `create_` | `create_user` |
| PUT | `update_` | `update_user` |
| PATCH | `patch_` | `patch_user` |
| DELETE | `delete_` | `delete_user` |

---

## 类型注解规范

### 现代语法（Python 3.10+）

```python
# 内置泛型
items: list[str]           # 不用 List[str]
mapping: dict[str, int]    # 不用 Dict[str, int]

# Union 类型
optional: str | None       # 不用 Optional[str]

# 类型别名（3.12+）
type UserID = int

# Annotated 元数据
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
```

### 参数 vs 返回值

```python
from collections.abc import Sequence

# 参数：使用抽象类型
def process(items: Sequence[Item]) -> None: ...

# 返回值：使用具体类型
def list_users() -> list[User]: ...
```

---

## 命令速查

| 命令 | 说明 |
|------|------|
| `uv init` | 初始化项目 |
| `uv add <pkg>` | 添加依赖 |
| `uv sync` | 同步环境 |
| `uv run <cmd>` | 运行命令 |
| `uv lock` | 更新锁文件 |
| `ruff check .` | 代码检查 |
| `ruff format .` | 格式化 |
| `ty check` | 类型检查 |
