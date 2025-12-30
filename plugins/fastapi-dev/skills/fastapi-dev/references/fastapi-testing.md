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
uv add --dev pytest pytest-asyncio httpx asgi-lifespan
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

### 事务回滚模式

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# 使用内存数据库进行测试
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)

@pytest_asyncio.fixture
async def db_session():
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn)
        yield session
        await trans.rollback()
        await session.close()
```

> 测试数据库引擎创建与依赖覆盖可放在 `conftest.py`。

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

