# FastAPI 测试

## 概述

FastAPI 测试推荐使用 pytest + pytest-asyncio + httpx 组合。

```bash
uv add --dev pytest pytest-asyncio httpx asgi-lifespan
```

---

## pytest-asyncio 配置

### pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # 自动识别 async 测试
asyncio_default_fixture_loop_scope = "function"
asyncio_default_test_loop_scope = "function"

# 可选：启用调试
# asyncio_debug = true
```

### 模式说明

| 模式 | 说明 |
|------|------|
| `auto` | 自动将 async def 测试/fixtures 识别为异步 |
| `strict` | 需要显式标记 `@pytest.mark.asyncio` |

---

## 基本测试

### 同步测试（TestClient）

> 本项目响应统一使用 `ApiResponse` 包装，测试断言需要从 `data` 字段取值。

```python
from fastapi.testclient import TestClient
from app.main import app


def test_read_root():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}
```

### 异步测试（AsyncClient）

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_read_root():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}
```

---

## Fixtures

### 异步客户端 Fixture

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post(
        "/users/",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["email"] == "test@example.com"
```

### 处理 Lifespan 事件

默认情况下 `AsyncClient` 不会触发 lifespan 事件。使用 `asgi-lifespan`：

```python
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as ac:
            yield ac
```

---

## 数据库测试

### 测试数据库配置

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.dependencies import get_db
from app.main import app


# 测试数据库
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """每个测试函数使用独立的数据库会话"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """覆盖数据库依赖"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

### 事务回滚模式

```python
@pytest_asyncio.fixture
async def db_session():
    """使用事务回滚隔离测试"""
    async with test_engine.connect() as conn:
        # 开始事务
        trans = await conn.begin()
        session = AsyncSession(bind=conn)

        yield session

        # 回滚所有更改
        await trans.rollback()
        await session.close()
```

---

## 依赖覆盖

### 覆盖认证依赖

```python
from uuid import uuid4

from app.dependencies import get_current_user
from app.models import User


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient):
    """模拟已认证用户"""
    mock_user = User(id=uuid4(), email="test@example.com", is_active=True)

    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_protected_route(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/users/me")
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "test@example.com"
```

### 覆盖外部服务

```python
from unittest.mock import AsyncMock
from app.services.email import EmailService


@pytest_asyncio.fixture
async def client_with_mock_email(client: AsyncClient):
    """模拟邮件服务"""
    mock_email = AsyncMock(spec=EmailService)
    mock_email.send.return_value = True

    app.dependency_overrides[EmailService] = lambda: mock_email
    yield client, mock_email
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_notification(client_with_mock_email):
    client, mock_email = client_with_mock_email
    response = await client.post("/notifications/", json={"message": "Hello"})

    assert response.status_code == 200
    mock_email.send.assert_called_once()
```

---

## 参数化测试

```python
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "email,password,expected_status",
    [
        ("valid@example.com", "password123", 201),
        ("invalid-email", "password123", 422),
        ("valid@example.com", "short", 422),
    ],
)
async def test_create_user_validation(
    client: AsyncClient,
    email: str,
    password: str,
    expected_status: int,
):
    response = await client.post(
        "/users/",
        json={"email": email, "password": password},
    )
    assert response.status_code == expected_status
```

---

## 异常测试

```python
import pytest
from uuid import uuid4
from app.core.error_codes import ErrorCode
from app.core.exceptions import UserNotFoundError


@pytest.mark.asyncio
async def test_get_nonexistent_user(client: AsyncClient):
    user_id = uuid4()
    response = await client.get(f"/users/{user_id}")
    assert response.status_code == 404
    assert response.json()["code"] == ErrorCode.USER_NOT_FOUND


@pytest.mark.asyncio
async def test_service_raises_exception():
    with pytest.raises(UserNotFoundError):
        await user_service.get(uuid4())
```

---

## 文件上传测试

```python
from io import BytesIO


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient):
    file_content = b"test file content"
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

    response = await client.post("/upload/", files=files)

    assert response.status_code == 200
    assert response.json()["filename"] == "test.txt"
```

---

## WebSocket 测试

```python
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport


@pytest.mark.asyncio
async def test_websocket():
    async with aconnect_ws(
        "http://test/ws",
        transport=ASGIWebSocketTransport(app),
    ) as ws:
        await ws.send_text("Hello")
        message = await ws.receive_text()
        assert message == "Echo: Hello"
```

---

## 测试工具函数

### Factory Boy 集成

```python
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.models import User


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "commit"

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    hashed_password = "hashed_password"
    is_active = True


@pytest_asyncio.fixture
async def user(db_session: AsyncSession):
    UserFactory._meta.sqlalchemy_session = db_session
    return UserFactory.create()
```

---

## pytest 插件推荐

| 插件 | 用途 |
|------|------|
| `pytest-asyncio` | 异步测试支持 |
| `pytest-cov` | 代码覆盖率 |
| `pytest-xdist` | 并行测试 |
| `pytest-mock` | Mock 支持 |
| `pytest-httpx` | httpx Mock |
| `asgi-lifespan` | Lifespan 事件 |
| `factory-boy` | 测试数据工厂 |

---

## 代码覆盖率

### 安装

```bash
uv add --dev pytest-cov
```

### pyproject.toml 配置

```toml
[tool.coverage.run]
source = ["app"]
branch = true
omit = [
    "*/tests/*",
    "*/__init__.py",
    "*/migrations/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
fail_under = 80
show_missing = true
skip_covered = true
```

### 运行测试

```bash
# 生成覆盖率报告
uv run pytest --cov=app --cov-report=term-missing

# 生成 HTML 报告
uv run pytest --cov=app --cov-report=html

# CI 中使用（失败阈值）
uv run pytest --cov=app --cov-fail-under=80
```

### pytest.ini_options 集成

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=term-missing"
```

---

## 最佳实践

1. **使用 `asyncio_mode = "auto"`** - 减少样板代码
2. **独立数据库** - 测试使用 SQLite 或独立 PostgreSQL
3. **事务回滚** - 每个测试后回滚保证隔离
4. **依赖覆盖** - 使用 `dependency_overrides` 模拟服务
5. **参数化测试** - 减少重复测试代码
6. **Fixture 复用** - 在 `conftest.py` 中定义共享 fixtures
7. **异步客户端** - 异步测试使用 `AsyncClient`
8. **处理 Lifespan** - 使用 `asgi-lifespan` 触发启动/关闭事件
