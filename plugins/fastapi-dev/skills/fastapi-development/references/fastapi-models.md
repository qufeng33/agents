# FastAPI 数据模型

## Pydantic v2 基础

FastAPI >= 0.120.0 仅支持 Pydantic v2。

---

## 模型定义

### 基础配置

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """所有 schema 的基类"""
    model_config = ConfigDict(
        from_attributes=True,      # 支持 ORM 模型转换
        str_strip_whitespace=True, # 自动去除字符串首尾空白
        validate_default=True,     # 验证默认值
    )
```

### 请求/响应模型分离

```python
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# 创建请求
class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


# 更新请求（所有字段可选）
class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=50)


# 响应模型（排除敏感字段）
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime


# 数据库内部使用
class UserInDB(UserResponse):
    hashed_password: str
```

---

## Field 验证

### 字符串约束

```python
from pydantic import ConfigDict, Field


class Example(BaseModel):
    # 自动去除字符串首尾空白（在 ConfigDict 中配置）
    model_config = ConfigDict(str_strip_whitespace=True)

    # 长度限制
    username: str = Field(min_length=3, max_length=50)

    # 正则模式
    slug: str = Field(pattern=r"^[a-z0-9-]+$")

    # name 会自动 strip（通过 model_config）
    name: str
```

### 数值约束

```python
class Product(BaseModel):
    # 范围限制
    price: float = Field(gt=0, le=10000)

    # 整数范围
    quantity: int = Field(ge=0, lt=1000)

    # 倍数
    discount: float = Field(multiple_of=0.01)
```

### 集合约束

```python
class Order(BaseModel):
    # 列表长度
    items: list[str] = Field(min_length=1, max_length=100)

    # 唯一项（转为 set）
    tags: set[str] = Field(max_length=10)
```

---

## 自定义验证器

### field_validator

```python
from pydantic import BaseModel, field_validator


class User(BaseModel):
    username: str
    email: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("must be alphanumeric")
        return v.lower()

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()
```

### model_validator

```python
from pydantic import BaseModel, model_validator


class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def check_dates(self) -> "DateRange":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class PasswordChange(BaseModel):
    password: str
    password_confirm: str

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordChange":
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self
```

---

## 严格模式

### 禁止额外字段

```python
from pydantic import ConfigDict


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: int


# 这会抛出验证错误
# StrictInput(name="test", value=1, extra_field="oops")
```

### 应用于查询参数

```python
from fastapi import APIRouter, Query

router = APIRouter()


class QueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = 0  # 从 0 开始
    page_size: int = 20


@router.get("/items/")
async def list_items(params: QueryParams = Query()):
    # 额外的查询参数会返回 422 错误
    return {"page": params.page, "page_size": params.page_size}
```

---

## 响应模型

### 过滤敏感数据

```python
@router.post("/users/", response_model=ApiResponse[UserResponse])
async def create_user(user: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    # service 内部完成持久化与密码处理
    created = await service.create(user)
    # UserResponse 排除敏感字段（如 hashed_password）
    return ApiResponse(data=created)
```

### 排除默认值

```python
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float = 10.5


@router.get("/items/{item_id}", response_model=Item, response_model_exclude_unset=True)
async def get_item(item_id: UUID) -> Item:
    return {"name": "Foo", "price": 50.2}
    # 响应只包含 name 和 price，不包含 description 和 tax
```

---

## 嵌套模型

```python
class Address(BaseModel):
    street: str
    city: str
    country: str = "China"


class Company(BaseModel):
    name: str
    address: Address


class UserWithCompany(BaseModel):
    username: str
    company: Company | None = None


# 请求体示例
# {
#     "username": "john",
#     "company": {
#         "name": "Acme",
#         "address": {"street": "123 Main St", "city": "Beijing"}
#     }
# }
```

---

## 自定义类型

```python
from typing import Annotated
from pydantic import AfterValidator


def validate_phone(v: str) -> str:
    # 移除非数字字符
    digits = "".join(filter(str.isdigit, v))
    if len(digits) != 11:
        raise ValueError("Phone number must have 11 digits")
    return digits


PhoneNumber = Annotated[str, AfterValidator(validate_phone)]


class Contact(BaseModel):
    name: str
    phone: PhoneNumber  # 自动验证和格式化
```

---

## 枚举和字面量

```python
from enum import Enum
from typing import Literal


class Status(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class Task(BaseModel):
    title: str
    status: Status = Status.PENDING

    # 或使用 Literal
    priority: Literal["low", "medium", "high"] = "medium"
```

---

## 验证错误处理

FastAPI 自动返回 422 响应，可自定义格式：

```python
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "errors": errors},
    )
```

---

## 最佳实践

1. **分离请求/响应模型** - 永远不要暴露内部字段
2. **使用 ConfigDict** - 统一配置基类
3. **Field 提供默认值** - 明确可选和必填
4. **自定义类型复用** - 创建领域特定类型
5. **严格模式** - 对外部输入使用 `extra="forbid"`
6. **response_model** - 始终指定，确保类型安全

---

## 代码模板

完整可运行示例见 `assets/` 目录：

| 结构 | ORM 模型 | Pydantic Schema |
|------|----------|-----------------|
| 简单结构 | `assets/simple-api/models/` | `assets/simple-api/schemas/` |
| 模块化结构 | `assets/modular-api/modules/user/models.py` | `assets/modular-api/modules/user/schemas.py` |
