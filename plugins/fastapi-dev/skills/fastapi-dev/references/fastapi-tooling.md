# FastAPI 开发工具
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 工具链最小化，覆盖构建、测试、质量检查即可
- 依赖锁定与可复现优先
- 避免全局安装工具，使用 `uvx` 或 `uv run`
- 配置保持短小，按需扩展
- 规范集中维护，避免多处重复

## 最佳实践
1. `uv` 负责依赖与运行
2. `ruff` 统一格式化与静态检查
3. `ty` 进行类型检查（按需）
4. `uv.lock` 必须提交
5. Docker 构建使用分层缓存

## 目录
- `uv 包管理`
- `Ruff 代码检查`
- `ty 类型检查`
- `pre-commit`
- `pytest 配置`
- `Docker 集成`
- `命名规范速查`
- `类型注解规范`
- `命令速查`

---

## uv 包管理

极速 Python 包管理器（Rust 编写）。

```bash
# 安装
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 常用命令

```bash
# 项目初始化
uv init my-project --python 3.13

# 依赖管理
uv add fastapi sqlalchemy
uv add --dev pytest ruff
uv remove requests

# 环境同步
uv sync
uv sync --locked
uv sync --no-dev

# 运行
uv run fastapi dev
uv run pytest
uv run ruff check .

# 锁文件
uv lock
uv lock --upgrade
```

### uv.lock 版本控制

**uv.lock 应提交到 Git**，原因：
- 确保团队成员和 CI/CD 使用完全相同的依赖版本
- `uv sync --locked` 依赖此文件进行严格版本锁定
- Docker 构建时用于分层缓存

---

## Ruff 代码检查

极速 linter + formatter，替代 flake8、isort、black。

```bash
uv add --dev ruff
ruff check .
ruff check . --fix
ruff format .
```

### 最小配置

```toml
[tool.ruff]
target-version = "py313"
line-length = 100
exclude = [".venv", "alembic"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "ASYNC", "ANN", "S", "RUF"]
ignore = ["ANN101", "ANN102", "RUF001", "RUF002", "RUF003"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```

> 规则可按项目规模扩展，避免一次性启用全部规则导致维护成本过高。

---

## ty 类型检查

```bash
# 无需全局安装
uvx ty check
uvx ty check --watch
```

### 最小配置

```toml
[tool.ty]
python-version = "3.13"

[tool.ty.rules]
unresolved-import = "error"
possibly-unbound = "warn"
```

---

## pre-commit

```bash
uv add --dev pre-commit
uv run pre-commit install
```

### 最小配置

```yaml
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
testpaths = ["tests"]
addopts = "-v --tb=short"
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
items: list[str]
mapping: dict[str, int]
optional: str | None

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
| `uvx ty check` | 类型检查 |
