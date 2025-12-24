# FastAPI 编码规范

> 适用版本：Python 3.13+ | FastAPI 0.127.0+ | Pydantic 2.7.0+
>
> 基于 PEP 8、Google Python Style Guide 和 FastAPI 社区最佳实践（2025）

## 命名规范

### 总览

| 类型 | 规范 | 示例 |
|------|------|------|
| 函数/方法 | `snake_case` | `get_user`, `create_order` |
| 变量 | `snake_case` | `user_name`, `total_count` |
| 类 | `PascalCase` | `UserService`, `OrderRepository` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_CONNECTIONS`, `DEFAULT_TIMEOUT` |
| 模块/包 | `lowercase` | `users`, `auth`, `config` |
| 私有成员 | `_prefix` | `_validate`, `_hash_password` |
| 异常类 | `PascalCase` + `Error` | `UserNotFoundError`, `ValidationError` |

---

### 路由函数命名

路由函数名应清晰描述操作和资源：

```python
# GET 列表
@router.get("/")
async def list_users(): ...

# GET 单个
@router.get("/{user_id}")
async def get_user(user_id: int): ...

# POST 创建
@router.post("/")
async def create_user(user: UserCreate): ...

# PUT 完整更新
@router.put("/{user_id}")
async def update_user(user_id: int, user: UserUpdate): ...

# PATCH 部分更新
@router.patch("/{user_id}")
async def patch_user(user_id: int, user: UserPatch): ...

# DELETE 删除
@router.delete("/{user_id}")
async def delete_user(user_id: int): ...
```

**命名模式**：`{动词}_{资源}`

| HTTP 方法 | 动词 | 示例 |
|-----------|------|------|
| GET (列表) | `list_` | `list_users`, `list_orders` |
| GET (单个) | `get_` | `get_user`, `get_order` |
| POST | `create_` | `create_user`, `create_order` |
| PUT | `update_` | `update_user`, `update_order` |
| PATCH | `patch_` | `patch_user`, `patch_order` |
| DELETE | `delete_` | `delete_user`, `delete_order` |

---

### Pydantic 模型命名

```python
# 基础模型
class UserBase(BaseModel):
    email: EmailStr
    username: str


# 创建请求
class UserCreate(UserBase):
    password: str


# 完整更新请求
class UserUpdate(UserBase):
    password: str | None = None


# 部分更新请求（所有字段可选）
class UserPatch(BaseModel):
    email: EmailStr | None = None
    username: str | None = None


# 响应模型
class UserResponse(UserBase):
    id: int
    created_at: datetime


# 列表项（用于列表响应）
class UserListItem(BaseModel):
    id: int
    email: EmailStr
    username: str


# 列表响应
class UserList(BaseModel):
    items: list[UserListItem]
    total: int


# 数据库内部模型（包含敏感字段）
class UserInDB(UserResponse):
    hashed_password: str


# 内部创建模型（自动分配字段）
class UserCreateDB(UserCreate):
    created_by: int  # 自动从认证用户获取
```

**命名模式**：`{Resource}{Action/Purpose}`

| 后缀 | 用途 |
|------|------|
| `Create` | 创建请求体 |
| `Update` | 完整更新请求体 |
| `Patch` | 部分更新请求体 |
| `Response` | API 响应 |
| `ListItem` | 列表中的单项 |
| `List` | 列表响应 |
| `InDB` | 数据库完整模型 |
| `CreateDB` / `UpdateDB` | 内部处理模型（含自动字段） |

---

### 依赖函数命名

依赖函数使用 `get_` 前缀：

```python
# 获取数据库会话
def get_db() -> Generator[Session, None, None]: ...

# 获取当前用户
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User: ...

# 获取配置
def get_settings() -> Settings: ...

# 获取服务实例
def get_user_service(db: DBSession) -> UserService: ...

# 获取并验证资源
async def get_user_or_404(user_id: int, db: DBSession) -> User: ...
```

---

### Service/Repository 类命名

```python
# Service 层：业务逻辑
class UserService:
    async def create(self, user_in: UserCreate) -> User: ...
    async def get(self, user_id: int) -> User: ...
    async def list(self, skip: int, limit: int) -> list[User]: ...
    async def update(self, user_id: int, user_in: UserUpdate) -> User: ...
    async def delete(self, user_id: int) -> None: ...


# Repository 层：数据访问
class UserRepository:
    def find_by_id(self, user_id: int) -> User | None: ...
    def find_by_email(self, email: str) -> User | None: ...
    def find_all(self, skip: int, limit: int) -> list[User]: ...
    def save(self, user: User) -> User: ...
    def delete(self, user: User) -> None: ...
```

---

### 异常类命名

```python
# 基础异常
class AppException(Exception): ...

# 资源相关异常：{Resource}{Problem}Error
class UserNotFoundError(AppException): ...
class UserAlreadyExistsError(AppException): ...
class OrderNotFoundError(AppException): ...

# 操作相关异常：{Operation}Error
class ValidationError(AppException): ...
class AuthenticationError(AppException): ...
class AuthorizationError(AppException): ...
class RateLimitError(AppException): ...
```

---

### 文件/模块命名

```
app/
├── main.py              # 应用入口
├── config.py            # 配置
├── dependencies.py      # 共享依赖
├── exceptions.py        # 全局异常
│
├── modules/
│   └── users/
│       ├── router.py        # 路由
│       ├── schemas.py       # Pydantic 模型
│       ├── models.py        # ORM 模型
│       ├── service.py       # 业务逻辑
│       ├── repository.py    # 数据访问（可选）
│       ├── dependencies.py  # 模块依赖
│       ├── exceptions.py    # 模块异常
│       └── constants.py     # 模块常量
```

---

## 类型注解规范

### Python 3.13+ 现代类型语法

```python
# 内置泛型类型（3.9+）
items: list[str]           # 不用 List[str]
mapping: dict[str, int]    # 不用 Dict[str, int]

# Union 类型（3.10+）
optional: str | None       # 不用 Optional[str]
mixed: int | str | None    # 不用 Union[int, str, None]

# 类型别名（3.12+，推荐）
type UserID = int
type UserMapping = dict[str, User]

# Annotated 元数据
from typing import Annotated
from fastapi import Depends, Query

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PageSize = Annotated[int, Query(ge=1, le=100)]
```

### Python 3.13 新增特性

```python
from typing import TypeIs, ReadOnly, TypedDict

# TypeIs：更精确的类型收窄（替代 TypeGuard）
def is_string(val: object) -> TypeIs[str]:
    return isinstance(val, str)

def process(val: str | int) -> None:
    if is_string(val):
        print(val.upper())  # val 被收窄为 str
    else:
        print(val + 1)      # val 被收窄为 int

# ReadOnly：TypedDict 只读字段
class Config(TypedDict):
    name: ReadOnly[str]     # 只读
    version: int            # 可修改

# 类型变量默认值
from typing import TypeVar
T = TypeVar("T", default=str)  # 默认为 str

# ClassVar 和 Final 可嵌套
from typing import ClassVar, Final

class Settings:
    MAX_CONN: Final[ClassVar[int]] = 100
```

### Python 3.14 新增特性

```python
# 延迟注解求值（PEP 649）
# 注解不再立即求值，提升启动性能，解决前向引用问题
class User:
    manager: "User"  # 不再需要引号（3.14+）

# Union 类型统一
# int | str 和 Union[int, str] 现在是同一类型
from typing import Union, get_origin
assert get_origin(int | str) is Union  # True

# TypeAliasType 解包
type Alias = tuple[int, str]
type Unpacked = tuple[bool, *Alias]  # tuple[bool, int, str]
```

### 已废弃特性（避免使用）

```python
# ❌ AnyStr（3.13 废弃，3.18 移除）
from typing import AnyStr  # 不要使用

# ✅ 使用泛型类型参数
def greet[T: (str, bytes)](data: T) -> T:
    return data

# ❌ TypeAlias（3.12 废弃）
from typing import TypeAlias
Vector: TypeAlias = list[float]  # 不要使用

# ✅ 使用 type 语句
type Vector = list[float]

# ❌ typing 模块的泛型（3.9 废弃）
from typing import List, Dict, Optional  # 不要使用

# ✅ 使用内置类型
items: list[str]
data: dict[str, int]
name: str | None
```

### 类型注解格式

```python
# 变量注解：冒号后有空格
user_id: int
name: str | None = None

# 函数注解：箭头两边有空格
def get_user(user_id: int) -> User: ...

# 带默认值：等号两边有空格
def search(query: str = "", limit: int = 10) -> list[Item]: ...

# Annotated 使用
async def list_items(
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Item]: ...
```

### 类型注解最佳实践

```python
# 参数：优先使用抽象类型
from collections.abc import Sequence, Mapping, Iterable

def process_items(items: Sequence[Item]) -> None: ...  # 接受 list, tuple 等
def get_config(data: Mapping[str, str]) -> None: ...   # 接受 dict 等

# 返回值：使用具体类型
def list_users() -> list[User]: ...  # 明确返回 list

# 避免 Any，使用 object
def accept_anything(value: object) -> None: ...  # 不用 Any

# 显式 None（必须！）
name: str | None = None  # ✅ 正确
name: str = None         # ❌ 类型错误！

# 使用 TypeIs 替代 TypeGuard（3.13+）
from typing import TypeIs  # 更精确的类型收窄
```

---

## 导入规范

### 导入顺序

```python
# 1. __future__ 导入
from __future__ import annotations

# 2. 标准库
import os
import sys
from datetime import datetime
from typing import Annotated

# 3. 第三方库
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 4. 本地模块
from app.config import get_settings
from app.core.database import get_db
from app.modules.users.schemas import UserCreate, UserResponse
from app.modules.users.service import UserService
```

### 导入规则

```python
# 每个导入单独一行
import os
import sys

# 从同一模块导入多个可以合并
from fastapi import APIRouter, Depends, HTTPException, status

# 使用绝对导入，避免相对导入
from app.modules.users import service  # 推荐
from . import service                   # 避免

# 跨模块导入使用别名
from app.modules.auth import constants as auth_constants
from app.modules.auth import service as auth_service
from app.modules.users import schemas as user_schemas

# 避免通配符导入
from module import *  # 禁止
```

---

## 文档字符串规范

### 模块文档

```python
"""用户管理模块。

提供用户的 CRUD 操作和认证功能。

Example:
    from app.modules.users import service

    user = await service.create_user(user_data)
"""
```

### 函数/方法文档

```python
async def create_user(user_in: UserCreate, db: Session) -> User:
    """创建新用户。

    验证邮箱唯一性后创建用户，密码会自动哈希处理。

    Args:
        user_in: 用户创建数据。
        db: 数据库会话。

    Returns:
        创建的用户对象。

    Raises:
        UserAlreadyExistsError: 邮箱已被注册。
        ValidationError: 输入数据验证失败。
    """
```

### 类文档

```python
class UserService:
    """用户业务逻辑服务。

    处理用户相关的业务逻辑，包括创建、查询、更新和删除操作。

    Attributes:
        db: 数据库会话。
        password_hasher: 密码哈希器。
    """

    def __init__(self, db: Session) -> None:
        """初始化用户服务。

        Args:
            db: 数据库会话。
        """
        self.db = db
```

---

## 代码质量工具

### Ruff（推荐）

Ruff 是一个极速的 Python linter 和 formatter，可以替代 flake8、isort、black 等工具。

```bash
uv add --dev ruff
```

#### 完整配置

```toml
# pyproject.toml
[tool.ruff]
target-version = "py313"  # Python 3.13
line-length = 100
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "migrations",
    "*.pyi",
]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade (现代化语法)
    "SIM",    # flake8-simplify
    "ANN",    # flake8-annotations
    "ASYNC",  # flake8-async
    "FA",     # flake8-future-annotations
    "S",      # flake8-bandit (安全)
    "T20",    # flake8-print
    "PT",     # flake8-pytest-style
    "RUF",    # Ruff 专有规则
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "ANN101", # missing self type
    "ANN102", # missing cls type
    "S101",   # assert usage (测试中使用)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ANN"]  # 测试文件允许 assert 和省略类型注解
"migrations/**/*.py" = ["ALL"]     # 迁移文件忽略所有

[tool.ruff.lint.isort]
known-first-party = ["app"]
force-single-line = false
combine-as-imports = true

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", "fastapi.Path"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
docstring-code-format = true
```

#### 常用命令

```bash
# 检查
ruff check .

# 自动修复
ruff check . --fix

# 格式化
ruff format .

# 检查并格式化
ruff check . --fix && ruff format .
```

### pre-commit 配置

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
        name: ty type check
        entry: uvx ty check
        language: system
        types: [python]
        pass_filenames: false
```

安装 pre-commit hooks：

```bash
uv add --dev pre-commit
uv run pre-commit install
```

### 类型检查（ty）

[ty](https://docs.astral.sh/ty/) 是 Astral（Ruff/uv 团队）推出的新一代类型检查器，用 Rust 编写，比 mypy 快 10-100 倍。

```bash
# 快速运行（无需安装）
uvx ty check

# 安装为工具
uv tool install ty

# 检查当前目录
ty check

# 监听模式
ty check --watch
```

```toml
# pyproject.toml
[tool.ty]
python-version = "3.13"

[tool.ty.rules]
# 规则级别：ignore / warn / error
unresolved-import = "error"
unresolved-attribute = "warn"
possibly-unbound = "warn"
division-by-zero = "error"
deprecated = "warn"

[tool.ty.src]
exclude = ["build/**", "migrations/**", ".venv/**"]
```

**ty 特点**：
- 极速：比 mypy/Pyright 快 10-100 倍
- 增量分析：编辑时只重新计算必要部分
- 内置 LSP：支持代码导航、补全、自动导入
- 无插件：直接内置 Pydantic 等流行库支持
- 当前状态：Beta（2026 年稳定版）

---

## 避免的命名

```python
# 避免单字符变量（除了常见迭代器）
l = [1, 2, 3]       # 错误：易与 1 混淆
O = "value"         # 错误：易与 0 混淆
I = 42              # 错误：易与 l 或 1 混淆

# 正确的迭代器例外
for i in range(10): ...
for i, item in enumerate(items): ...
except ValueError as e: ...
with open("file.txt") as f: ...

# 避免在变量名中包含类型
users_list = []     # 冗余
user_dict = {}      # 冗余

# 推荐
users = []
user_mapping = {}

# 避免缩写（除非广泛认可）
usr = get_user()    # 错误
config = get_cfg()  # 错误

# 推荐
user = get_user()
config = get_config()

# 广泛认可的缩写可以使用
db = get_database()
id = user.id
url = "https://..."
```

---

## 参考资料

- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Pydantic Schema Naming Guide](https://jd-solanki.github.io/blog/the-ultimate-guide-to-naming-conventions-for-pydantic-schemas-in-fastapi)
- [Python Typing Best Practices](https://typing.python.org/en/latest/reference/best_practices.html)
