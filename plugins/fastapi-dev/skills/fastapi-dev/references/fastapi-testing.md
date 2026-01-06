# FastAPI 测试
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 测试覆盖核心路径与异常路径
- 测试数据可重复、可清理
- 依赖覆盖优先于真实外部服务
- 单测快速、集成测试可控
- 异步测试优先使用 AsyncClient

## 最佳实践
1. `asyncio_mode = "auto"`
2. 事务回滚保证隔离
3. `dependency_overrides` 模拟依赖
4. Fixtures 复用集中在 `conftest.py`
5. Lifespan 事件用 `asgi-lifespan`

## 目录
- `概述`
- `pytest-asyncio 配置`
- `基本测试`
- `Fixtures`
- `数据库测试`
- `依赖覆盖`
- `其他测试场景`
- `测试工具与覆盖率`

---

## 概述

FastAPI 测试推荐使用 pytest + pytest-asyncio + httpx 组合。

```bash
uv add --dev pytest pytest-asyncio pytest-cov httpx asgi-lifespan aiosqlite
```

---

## pytest-asyncio 配置

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

---

## 基本测试

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["data"] == {"status": "ok"}
```

> 同步场景可用 `TestClient`，原则一致。

---

## Fixtures

```python
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as ac:
            yield ac
```

---

## 数据库测试

### SQLite 内存数据库配置

```python
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# SQLite 内存数据库（测试用）
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # 关键：内存数据库需要共享连接
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
```

> **重要**：SQLite 内存数据库必须使用 `StaticPool`，否则每次连接会创建新的数据库实例。

### db_session Fixture

```python
import pytest_asyncio
from app.core.database import Base

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """创建测试数据库会话，每个测试前创建表，测试后清理"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

> 完整的 `conftest.py` 模板见 `assets/tests/conftest.py.template`。

---

## 依赖覆盖

```python
from uuid import uuid4

import pytest_asyncio
from app.dependencies import get_current_user


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    mock_user = User(id=uuid4(), username="tester", hashed_password="x", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield client
    app.dependency_overrides.clear()
```

---

## 其他测试场景

- 参数化测试：适用于输入校验矩阵
- 异常测试：断言错误码与错误响应结构
- 文件上传/WS：按需引入 `httpx-ws`
- Factory Boy：复杂数据生成时使用

---

## 测试工具与覆盖率

- 插件建议：`pytest-asyncio`、`pytest-cov`、`pytest-mock`、`asgi-lifespan`
- 覆盖率配置建议放在 `pyproject.toml`，按团队阈值设置 `fail_under`

