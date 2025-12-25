# FastAPI 核心模式

## async def vs def 选择

| 场景 | 推荐 | 原因 |
|-----|------|------|
| 无 I/O 的简单逻辑 | `async def` | 避免线程池开销 |
| 异步 I/O（httpx, asyncpg） | `async def` + `await` | 非阻塞 |
| 同步阻塞 I/O | `def` | FastAPI 自动线程池 |
| CPU 密集型 | `ProcessPoolExecutor` | 不阻塞事件循环 |

```python
# I/O 密集型：async def
@app.get("/external")
async def call_api():
    async with httpx.AsyncClient() as client:
        return (await client.get("https://api.example.com")).json()

# 同步阻塞：def（自动线程池）
@app.get("/sync")
def sync_operation():
    time.sleep(1)  # 不会阻塞事件循环
    return {"done": True}

# CPU 密集型：外部进程
executor = ProcessPoolExecutor(max_workers=4)

@app.post("/compute")
async def compute(data: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, heavy_task, data)
```

### 常见错误

```python
# 错误：在 async def 中阻塞
@app.get("/bad")
async def bad():
    time.sleep(5)  # 阻塞事件循环！

# 正确：使用 def 或 asyncio.sleep
@app.get("/good")
async def good():
    await asyncio.sleep(5)
```

---

## 依赖注入

### 基本用法（Annotated 推荐）

```python
from typing import Annotated
from fastapi import Depends, Query

def pagination(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
) -> dict:
    return {"skip": skip, "limit": limit}

Pagination = Annotated[dict, Depends(pagination)]

@app.get("/items/")
async def list_items(params: Pagination):
    return params
```

### 依赖链

```python
async def get_token(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid format")
    return authorization[7:]

async def get_current_user(token: Annotated[str, Depends(get_token)]) -> User:
    user = await decode_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

@app.get("/me")
async def get_me(user: CurrentUser):
    return user
```

### yield 依赖（资源管理）

```python
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


AsyncDBSession = Annotated[AsyncSession, Depends(get_async_db)]
```

> 详细的数据库配置参见 [fastapi-database.md](./fastapi-database.md)

### 类作为依赖

```python
class PermissionChecker:
    def __init__(self, permissions: list[str]):
        self.permissions = permissions

    def __call__(self, user: CurrentUser) -> User:
        for p in self.permissions:
            if p not in user.permissions:
                raise HTTPException(403, f"Missing: {p}")
        return user

require_admin = PermissionChecker(["admin"])

@app.delete("/users/{user_id}")
async def delete_user(admin: Annotated[User, Depends(require_admin)]):
    ...
```

### 依赖缓存

同一请求中相同依赖只执行一次（共享实例）。

```python
# 禁用缓存：每次都创建新实例
@app.get("/items/")
async def items(val: Annotated[str, Depends(get_random, use_cache=False)]):
    ...
```

### 路由级依赖

```python
router = APIRouter(dependencies=[Depends(verify_api_key)])
app = FastAPI(dependencies=[Depends(log_request)])
```

---

## 资源存在性验证

```python
from sqlalchemy import select


async def get_item_or_404(
    item_id: int,
    db: AsyncDBSession,
) -> Item:
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")
    return item


ValidItem = Annotated[Item, Depends(get_item_or_404)]


@app.get("/items/{item_id}")
async def read_item(item: ValidItem):
    return item  # 保证存在
```

---

## 后台任务

```python
from fastapi import BackgroundTasks

def send_email(email: str, msg: str):
    # 同步函数自动在线程池执行
    ...

@app.post("/notify")
async def notify(email: str, bg: BackgroundTasks):
    bg.add_task(send_email, email, "Hello")
    return {"status": "scheduled"}
```

**最佳实践**：传递 ID 而非对象，后台任务自己创建 session。

```python
def process_order(order_id: int):
    db = SessionLocal()
    try:
        order = db.query(Order).get(order_id)
        # 处理...
    finally:
        db.close()

@app.post("/orders")
async def create_order(order: OrderCreate, bg: BackgroundTasks, db: DBSession):
    db_order = Order(**order.model_dump())
    db.add(db_order)
    db.commit()
    bg.add_task(process_order, db_order.id)  # 传 ID，不传对象
    return db_order
```

---

## 生命周期管理（Lifespan）

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    app.state.http_client = httpx.AsyncClient()
    app.state.db_pool = await create_db_pool()

    yield  # 运行中

    # 关闭
    await app.state.http_client.aclose()
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)

@app.get("/external")
async def external(request: Request):
    client = request.app.state.http_client
    return (await client.get("https://api.example.com")).json()
```

### 分离职责模式

参见 [fastapi-httpx.md](./fastapi-httpx.md) 的「生命周期管理 + 依赖注入」章节。

```python
# main.py - lifespan 示例
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    await init_http_client(app)
    yield
    await close_http_client(app)
    await close_database()
```

---

## 并发请求

```python
@app.get("/users/batch")
async def get_users(user_ids: list[int]):
    tasks = [fetch_user(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    users, errors = [], []
    for uid, r in zip(user_ids, results):
        if isinstance(r, Exception):
            errors.append({"id": uid, "error": str(r)})
        else:
            users.append(r)
    return {"users": users, "errors": errors}
```

---

## 异步数据库

参见 [fastapi-database.md](./fastapi-database.md) 的「SQLAlchemy 2.0 异步」章节。

---

## 最佳实践

1. **使用 Annotated 创建类型别名** - 提高可读性和可维护性
2. **单一职责** - 每个依赖只做一件事
3. **利用依赖链** - 组合小依赖构建复杂逻辑
4. **yield 管理资源** - 确保资源正确清理
5. **类型提示** - 始终提供返回类型
6. **优先 async** - 简单逻辑使用 async 依赖，避免线程池开销
7. **后台任务传 ID** - 不传递 ORM 对象或 db session
8. **lifespan 管理资源** - 启动时初始化，关闭时清理
