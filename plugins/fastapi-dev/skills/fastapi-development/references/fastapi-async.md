# FastAPI 异步处理

## 核心概念

FastAPI 基于 Starlette，原生支持异步。理解何时使用 `async def` vs `def` 是关键。

---

## async def vs def

### I/O 密集型操作：使用 async def

当操作涉及等待外部资源（网络、数据库、文件）时使用。

```python
import httpx

@app.get("/external-api")
async def call_external_api():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

### CPU 密集型操作：避免在路由中直接处理

CPU 密集型任务会阻塞事件循环，应该分发到独立进程。

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)


def cpu_intensive_task(data: str) -> str:
    # 复杂计算...
    return result


@app.post("/process")
async def process_data(data: str):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, cpu_intensive_task, data)
    return {"result": result}
```

### 同步阻塞操作：使用 def

FastAPI 会自动在线程池中运行 `def` 函数，不会阻塞事件循环。

```python
import time

@app.get("/sync-operation")
def sync_operation():
    # 这个会在线程池中执行
    time.sleep(1)  # 阻塞操作
    return {"message": "done"}
```

---

## 混合使用规则

```python
# 可以在 async def 路由中使用 def 依赖
def get_db():  # def
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/items")
async def read_items(db: Session = Depends(get_db)):  # async def
    # FastAPI 正确处理混合
    return db.query(Item).all()


# 也可以在 def 路由中使用 async def 依赖
async def get_current_user():  # async def
    return await fetch_user_from_token()


@app.get("/profile")
def get_profile(user = Depends(get_current_user)):  # def
    return user
```

---

## 异步数据库操作

### 使用 asyncpg + SQLAlchemy 2.0

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

ASYNC_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db"

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

---

## 并发请求

### 并行调用多个异步操作

```python
import asyncio
import httpx


async def fetch_user(user_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()


@app.get("/users/batch")
async def get_multiple_users(user_ids: list[int]):
    # 并行获取所有用户
    tasks = [fetch_user(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    users = []
    errors = []
    for uid, result in zip(user_ids, results):
        if isinstance(result, Exception):
            errors.append({"user_id": uid, "error": str(result)})
        else:
            users.append(result)

    return {"users": users, "errors": errors}
```

---

## 后台任务

后台任务在响应发送后执行，不阻塞请求。

```python
from fastapi import BackgroundTasks


def send_email(email: str, message: str):
    # 同步函数也可以作为后台任务
    # 会在线程池中执行
    ...


async def log_operation(operation: str):
    # 异步后台任务
    ...


@app.post("/send-notification")
async def send_notification(
    email: str,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(send_email, email, "Hello!")
    background_tasks.add_task(log_operation, "notification_sent")
    return {"message": "Notification scheduled"}
```

### 后台任务最佳实践

```python
# 传递 ID 而非对象（0.106.0+ 推荐）
def process_order(order_id: int):
    """后台任务应创建自己的数据库会话"""
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        # 处理订单...
    finally:
        db.close()


@app.post("/orders")
async def create_order(order: OrderCreate, background_tasks: BackgroundTasks, db: DBSession):
    db_order = Order(**order.model_dump())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # 传递 ID，不传递 db_order 或 db session
    background_tasks.add_task(process_order, db_order.id)

    return db_order
```

---

## 生命周期事件

使用 `lifespan` 管理应用启动和关闭逻辑。

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 启动时：初始化资源
    app.state.http_client = httpx.AsyncClient()
    app.state.db_pool = await create_db_pool()

    yield  # 应用运行中

    # 关闭时：清理资源
    await app.state.http_client.aclose()
    await app.state.db_pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/external")
async def call_external(request: Request):
    # 使用共享的 HTTP 客户端
    client = request.app.state.http_client
    response = await client.get("https://api.example.com")
    return response.json()
```

---

## 常见错误

### 1. 在 async def 中使用阻塞调用

```python
# 错误：阻塞整个事件循环
@app.get("/bad")
async def bad_example():
    time.sleep(5)  # 阻塞！
    return {"message": "done"}


# 正确：使用 def 或 asyncio.sleep
@app.get("/good")
async def good_example():
    await asyncio.sleep(5)  # 非阻塞
    return {"message": "done"}


# 或者用 def
@app.get("/also-good")
def also_good():
    time.sleep(5)  # 在线程池中执行
    return {"message": "done"}
```

### 2. 忘记 await

```python
# 错误：返回协程对象而非结果
@app.get("/wrong")
async def wrong():
    return fetch_data()  # 缺少 await


# 正确
@app.get("/correct")
async def correct():
    return await fetch_data()
```
