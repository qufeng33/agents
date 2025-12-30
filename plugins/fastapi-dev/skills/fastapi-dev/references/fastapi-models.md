# FastAPI 数据模型
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 请求/响应/内部模型严格分离
- 配置集中在基类，避免散落
- 外部输入默认严格校验
- 领域类型复用，减少重复验证
- 错误处理交给统一异常处理器

## 最佳实践
1. 使用 `ConfigDict` 统一配置基类
2. 请求模型与响应模型分离
3. 对外输入使用 `extra="forbid"`
4. 自定义类型集中复用
5. 始终显式声明 `response_model`

## 目录
- `Pydantic v2 基础`
- `模型定义`
- `Field 验证`
- `自定义验证器`
- `严格模式`
- `嵌套模型`
- `自定义类型`
- `枚举和字面量`
- `验证错误处理`
- `代码模板`

---

## Pydantic v2 基础

FastAPI >= 0.122.0 仅支持 Pydantic v2。

---

## 模型定义

### 基础配置

```python
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
```

### 请求/响应模型分离

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# 创建请求
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


# 更新请求（所有字段可选）
class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)


# 响应模型（排除敏感字段）
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    is_active: bool
    created_at: datetime
    # 注意：不包含 password、hashed_password
```

> 内部模型（如 `UserInDB`）只在数据库层使用，不对外暴露。
> 响应模型必须排除敏感字段（密码、token 等）。

---

## Field 验证

```python
from pydantic import BaseModel, Field


class Example(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    price: float = Field(gt=0, le=10000)
```

> 正则、集合长度、倍数等约束按需求补充。

---

## 自定义验证器

### field_validator

```python
from pydantic import BaseModel, field_validator


class User(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("must be alphanumeric")
        return v.lower()
```

> **提示**：在验证器中抛出 `ValueError` 会被 FastAPI 自动捕获并转换为 422 响应，包含友好的错误信息。无需额外处理，直接抛出即可。

### model_validator

```python
from datetime import datetime
from pydantic import BaseModel, model_validator


class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def check_dates(self) -> "DateRange":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

---

## 严格模式

```python
from pydantic import BaseModel, ConfigDict


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: int
```

> 对外部输入建议默认 `extra="forbid"`，避免隐式字段穿透。

---

## 嵌套模型

```python
from pydantic import BaseModel


class Address(BaseModel):
    street: str
    city: str


class Company(BaseModel):
    name: str
    address: Address
```

> 复杂请求体可拆成嵌套结构，避免扁平模型过长。

---

## 自定义类型

```python
from typing import Annotated
from pydantic import AfterValidator


def validate_phone(v: str) -> str:
    digits = "".join(filter(str.isdigit, v))
    if len(digits) != 11:
        raise ValueError("Phone number must have 11 digits")
    return digits


PhoneNumber = Annotated[str, AfterValidator(validate_phone)]
```

> 领域特定校验（如手机号、地区码）建议封装为类型别名复用。

---

## 枚举和字面量

```python
from enum import Enum
from typing import Literal


class Status(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"


class Task(BaseModel):
    status: Status = Status.PENDING
    priority: Literal["low", "medium", "high"] = "medium"
```

---

## 验证错误处理

FastAPI 自动返回 422 响应，可在统一异常处理中转换格式。

> 自定义验证错误响应详见 [错误处理](./fastapi-errors.md)

---

## 代码模板

完整可运行示例见 `assets/` 目录：

- `assets/simple-api/models/` / `assets/simple-api/schemas/`
- `assets/modular-api/modules/user/models.py` / `assets/modular-api/modules/user/schemas.py`
