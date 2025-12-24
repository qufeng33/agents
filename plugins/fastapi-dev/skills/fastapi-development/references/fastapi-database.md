# FastAPI 数据库集成

## SQLAlchemy 2.0 同步

### 基础配置

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # 连接前检查有效性
    pool_recycle=300,         # 5分钟回收连接
    pool_size=5,              # 连接池大小
    max_overflow=10,          # 最大溢出连接数
    echo=settings.debug,      # 调试模式打印 SQL
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
```

### 依赖注入

```python
from typing import Annotated, Generator
from fastapi import Depends
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]
```

---

## SQLAlchemy 2.0 异步

### 异步配置

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 注意：使用异步驱动
# PostgreSQL: postgresql+asyncpg://
# MySQL: mysql+aiomysql://
# SQLite: sqlite+aiosqlite://

async_engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
```

### 异步依赖

```python
from typing import AsyncGenerator


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

### 异步查询

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@app.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncDBSession):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404)
    return user


@app.get("/users/{user_id}/with-posts")
async def get_user_with_posts(user_id: int, db: AsyncDBSession):
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.posts))  # 预加载关联
    )
    return result.scalar_one_or_none()
```

---

## SQLModel（推荐）

SQLModel 整合了 SQLAlchemy 和 Pydantic。

### 模型定义

```python
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    username: str = Field(min_length=3, max_length=50, index=True)
    is_active: bool = True


class User(UserBase, table=True):
    """数据库表模型"""
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 关联
    posts: list["Post"] = Relationship(back_populates="author")


class UserCreate(UserBase):
    """创建请求"""
    password: str = Field(min_length=8)


class UserResponse(UserBase):
    """响应模型"""
    id: int
    created_at: datetime


class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="user.id")

    author: User | None = Relationship(back_populates="posts")
```

### CRUD 操作

```python
from sqlmodel import Session, select


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_in: UserCreate) -> User:
        user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.exec(statement).first()

    def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        statement = select(User).offset(skip).limit(limit)
        return self.db.exec(statement).all()

    def update(self, user: User, user_in: UserUpdate) -> User:
        user_data = user_in.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            setattr(user, key, value)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
```

---

## 事务管理

### 手动事务

```python
@app.post("/transfer")
async def transfer_money(
    from_id: int,
    to_id: int,
    amount: float,
    db: DBSession,
):
    try:
        from_account = db.query(Account).filter(Account.id == from_id).with_for_update().first()
        to_account = db.query(Account).filter(Account.id == to_id).with_for_update().first()

        if from_account.balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        from_account.balance -= amount
        to_account.balance += amount

        db.commit()
        return {"message": "Transfer successful"}
    except Exception:
        db.rollback()
        raise
```

### 嵌套事务（Savepoint）

```python
from sqlalchemy import event


@app.post("/complex-operation")
async def complex_operation(db: DBSession):
    # 创建主记录
    order = Order(...)
    db.add(order)
    db.flush()  # 获取 order.id

    # 嵌套事务
    savepoint = db.begin_nested()
    try:
        # 可能失败的操作
        process_payment(order)
        savepoint.commit()
    except PaymentError:
        savepoint.rollback()
        order.status = "payment_failed"

    db.commit()
    return order
```

---

## 数据库迁移（Alembic）

### 初始化

```bash
alembic init alembic
```

### 配置 `alembic/env.py`

```python
from app.core.database import Base
from app.config import get_settings

settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

### 常用命令

```bash
# 创建迁移
alembic revision --autogenerate -m "add users table"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看历史
alembic history
```

---

## 连接池配置

### PostgreSQL 推荐配置

```python
engine = create_engine(
    database_url,
    pool_size=5,              # 基础连接数
    max_overflow=10,          # 允许溢出连接数
    pool_timeout=30,          # 获取连接超时（秒）
    pool_recycle=1800,        # 连接回收时间（秒）
    pool_pre_ping=True,       # 使用前检查连接
)
```

### SQLite 配置

```python
# SQLite 需要特殊配置支持多线程
engine = create_engine(
    "sqlite:///./app.db",
    connect_args={"check_same_thread": False},
)
```

---

## 同步 Session 在异步 FastAPI 中的处理

当必须使用同步 ORM（如某些第三方库）时，使用 `run_in_threadpool` 避免阻塞事件循环：

```python
from fastapi.concurrency import run_in_threadpool


def sync_db_operation(db: Session, user_id: int) -> User:
    """同步数据库操作"""
    return db.query(User).filter(User.id == user_id).first()


@app.get("/users/{user_id}")
async def get_user(user_id: int, db: DBSession):
    # 在线程池中运行同步操作
    user = await run_in_threadpool(sync_db_operation, db, user_id)
    if not user:
        raise HTTPException(status_code=404)
    return user
```

---

## 异步 CRUD 服务模式

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


class AsyncCRUDService[T]:
    """通用异步 CRUD 服务"""

    def __init__(self, model: type[T]):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> T | None:
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: dict) -> T:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: T,
        obj_in: dict,
    ) -> T:
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> None:
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()

    async def count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()


# 使用
user_service = AsyncCRUDService(User)
```

---

## 数据库生命周期管理

在 `core/database.py` 中统一管理数据库连接：

```python
# core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_database() -> None:
    """初始化数据库（创建表，仅开发环境）"""
    if settings.debug:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """关闭数据库连接池"""
    await async_engine.dispose()
```

在 `main.py` 中调用：

```python
# main.py
from app.core.database import init_database, close_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_database()
    yield
    await close_database()
```

---

## SQL 优先处理数据聚合

数据库处理数据比 CPython 更快更干净。复杂聚合应在 SQL 层完成，而非 Python 侧。

```python
# ❌ 错误：Python 侧聚合 - 慢且占用内存
@router.get("/posts/stats")
async def get_stats(db: AsyncDBSession):
    result = await db.execute(select(Post))
    all_posts = result.scalars().all()

    # 在 Python 中聚合 - 加载全部数据到内存
    total = len(all_posts)
    published = sum(1 for p in all_posts if p.is_published)
    avg_views = sum(p.views for p in all_posts) / total if total else 0

    return {"total": total, "published": published, "avg_views": avg_views}


# ✅ 正确：SQL 聚合 - 快速且高效
from sqlalchemy import func, case

@router.get("/posts/stats")
async def get_stats(db: AsyncDBSession):
    result = await db.execute(
        select(
            func.count(Post.id).label("total"),
            func.count(case((Post.is_published == True, 1))).label("published"),
            func.coalesce(func.avg(Post.views), 0).label("avg_views"),
        )
    )
    row = result.one()
    return {"total": row.total, "published": row.published, "avg_views": float(row.avg_views)}
```

**适用 SQL 聚合的场景**：
- 聚合计算（COUNT, SUM, AVG, MAX, MIN）
- 分组统计（GROUP BY）
- 复杂筛选和排序
- 分页（LIMIT/OFFSET）
- 窗口函数（ROW_NUMBER, RANK）

**不适用场景**：
- 需要复杂业务逻辑转换
- 需要调用外部服务
- 数据量小且需要多次使用

---

## 最佳实践

1. **使用依赖注入管理 Session** - 确保自动关闭
2. **异步场景用异步驱动** - asyncpg, aiomysql, aiosqlite
3. **配置连接池** - 避免连接泄漏
4. **使用 Alembic 管理迁移** - 版本化数据库变更
5. **索引常用查询字段** - 提升查询性能
6. **预加载关联** - 避免 N+1 查询（`selectinload`, `joinedload`）
7. **SQLModel 简化开发** - 减少重复代码
8. **expire_on_commit=False** - 异步 Session 必须设置
9. **run_in_threadpool** - 同步代码在异步上下文中执行
10. **dispose 连接池** - 在 lifespan 关闭时释放
11. **SQL 优先聚合** - 聚合计算在数据库层完成，避免加载全部数据
