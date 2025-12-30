# FastAPI 代码重构

## 设计原则
- 先保证测试稳定，再改结构
- 小步重构，可随时回滚
- 不改变外部行为与接口
- 每次改动后立即验证
- 重构是为可读与可维护

## 最佳实践
1. 测试全绿才开始重构
2. 每次只做一个小改动
3. 保持 API/错误格式不变
4. 修改后运行关键测试
5. 卡住就回退

## 目录
- `代码坏味道识别`
- `常见重构模式`

---

## 代码坏味道识别

| 代码坏味道 | 描述 | 重构方法 |
|------------|------|----------|
| 长方法 | > 20 行 | Extract Method |
| 重复代码 | 相似代码多处 | Extract Method/Class |
| 过大的类 | 职责过多 | Extract Class |
| 深层嵌套 | > 4 层 | Early Return |
| 魔法数字 | 硬编码常量 | Extract Constant |

---

## 常见重构模式

### Extract Method

```python
# Before
async def create_user(data: UserCreate) -> User:
    if not re.match(r"...", data.username):
        raise ValidationError("Invalid username")
    existing = await repo.get_by_username(data.username, include_deleted=True)
    if existing:
        raise ConflictError("Username exists")
    return await repo.save(User(...))

# After
async def create_user(data: UserCreate) -> User:
    await validate_username(data.username)
    await ensure_username_unique(data.username)
    return await save_new_user(data)
```

> 适合把校验/构建/持久化拆成清晰职责。

### Early Return

```python
# Before
async def get_user(user_id: UUID) -> User | None:
    user = await repo.get(user_id)
    if user and user.is_active:
        return user
    return None

# After
async def get_user(user_id: UUID) -> User | None:
    user = await repo.get(user_id)
    if not user or not user.is_active:
        return None
    return user
```

### Extract Constant

```python
# Before
if len(password) < 8:
    raise ValidationError("Password too short")

# After
MIN_PASSWORD_LENGTH = 8
if len(password) < MIN_PASSWORD_LENGTH:
    raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
```

### Extract Class

```python
# Before
class UserService:
    async def create(self, data): ...
    async def hash_password(self, password): ...
    async def send_welcome(self, user): ...

# After
class UserService:
    def __init__(self, password_service: PasswordService, notification_service: NotificationService):
        self.password_service = password_service
        self.notification_service = notification_service
```

> 当单个类承担多个职责时拆分为协作类。

