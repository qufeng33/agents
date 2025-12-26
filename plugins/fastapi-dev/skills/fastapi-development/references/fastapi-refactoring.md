# FastAPI 代码重构

## 重构原则

### 安全第一

1. **确保测试通过** - 重构前必须所有测试绿色
2. **小步前进** - 每次只做一个小改动
3. **持续验证** - 每步改动后运行测试
4. **可回滚** - 保持 git 状态干净，随时可回滚

### 不改变行为

重构只改变代码结构，不改变外部行为：
- 保持 API 接口不变
- 保持返回值格式不变
- 保持错误处理方式不变

---

## 代码坏味道识别

| 代码坏味道 | 描述 | 重构方法 |
|------------|------|----------|
| 长方法 | > 20 行 | Extract Method |
| 长参数列表 | > 5 个参数 | Introduce Parameter Object |
| 重复代码 | 相似代码多处 | Extract Method/Class |
| 过大的类 | 职责过多 | Extract Class |
| 深层嵌套 | > 4 层 | Early Return, Extract Method |
| 魔法数字 | 硬编码常量 | Extract Constant |
| 复杂条件 | 难以理解的条件 | Extract Method |

---

## 常见重构模式

### Extract Method

将复杂逻辑拆分为独立方法，提高可读性和复用性。

```python
# Before
async def create_user(data: UserCreate) -> User:
    # 验证邮箱格式
    if not re.match(r"...", data.email):
        raise ValidationError("Invalid email")
    # 检查邮箱唯一性
    existing = await repo.get_by_email(data.email)
    if existing:
        raise ConflictError("Email exists")
    # 创建用户
    user = User(...)
    return await repo.save(user)

# After
async def create_user(data: UserCreate) -> User:
    await validate_email(data.email)
    await ensure_email_unique(data.email)
    return await save_new_user(data)


async def validate_email(email: str) -> None:
    if not re.match(r"...", email):
        raise ValidationError("Invalid email")


async def ensure_email_unique(email: str) -> None:
    existing = await repo.get_by_email(email)
    if existing:
        raise ConflictError("Email exists")
```

### Early Return

减少嵌套层级，提高代码可读性。

```python
# Before
async def get_user(user_id: int) -> User | None:
    if user_id > 0:
        user = await repo.get(user_id)
        if user:
            if user.is_active:
                return user
    return None

# After
async def get_user(user_id: int) -> User | None:
    if user_id <= 0:
        return None

    user = await repo.get(user_id)
    if not user:
        return None

    if not user.is_active:
        return None

    return user
```

### Extract Constant

消除魔法数字，提高可维护性。

```python
# Before
if len(password) < 8:
    raise ValidationError("Password too short")

# After
MIN_PASSWORD_LENGTH = 8

if len(password) < MIN_PASSWORD_LENGTH:
    raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
```

### Introduce Parameter Object

减少参数数量，提高可读性。

```python
# Before
async def create_order(
    user_id: int,
    product_id: int,
    quantity: int,
    address: str,
    city: str,
    zip_code: str,
) -> Order:
    ...

# After
@dataclass
class ShippingAddress:
    address: str
    city: str
    zip_code: str


@dataclass
class CreateOrderParams:
    user_id: int
    product_id: int
    quantity: int
    shipping_address: ShippingAddress


async def create_order(params: CreateOrderParams) -> Order:
    ...
```

### Extract Class

拆分职责过重的类。

```python
# Before: Service 做了太多事
class UserService:
    async def create(self, data): ...
    async def validate_password(self, password): ...
    async def hash_password(self, password): ...
    async def send_welcome_email(self, user): ...
    async def send_reset_email(self, user): ...

# After: 拆分职责
class UserService:
    def __init__(self, password_service: PasswordService, email_service: EmailService):
        self.password_service = password_service
        self.email_service = email_service

    async def create(self, data: UserCreate) -> User:
        hashed = await self.password_service.hash(data.password)
        user = User(hashed_password=hashed)
        await self.email_service.send_welcome(user)
        return user


class PasswordService:
    async def validate(self, password: str) -> None: ...
    async def hash(self, password: str) -> str: ...


class EmailService:
    async def send_welcome(self, user: User) -> None: ...
    async def send_reset(self, user: User) -> None: ...
```

---

## 最佳实践

1. **永远不要在测试红色时重构**
2. **每步改动尽可能小**
3. **改动后立即验证**
4. **保持代码行为不变**
5. **如果卡住，回滚并重新思考**
6. **重构是为了让代码更清晰，不是为了重构而重构**
