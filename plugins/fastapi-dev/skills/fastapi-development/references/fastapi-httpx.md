# FastAPI HTTP 客户端（httpx）

## 概述

httpx 是 FastAPI 推荐的 HTTP 客户端库，支持同步和异步请求，是 `requests` 的现代替代品。

```bash
uv add httpx
# HTTP/2 支持
uv add "httpx[http2]"
```

---

## 基本用法

### 生命周期管理 + 依赖注入（推荐）

在 `core/http.py` 中统一管理 HTTP 客户端：

```python
# core/http.py
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request


async def init_http_client(app: FastAPI) -> None:
    """初始化 HTTP 客户端"""
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    timeout = httpx.Timeout(10.0, connect=5.0)
    app.state.http_client = httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        http2=True,
    )


async def close_http_client(app: FastAPI) -> None:
    """关闭 HTTP 客户端"""
    await app.state.http_client.aclose()


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """依赖注入：获取 HTTP 客户端"""
    return request.app.state.http_client


HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
```

在 lifespan 中初始化（完整启动流程详见 [应用启动与初始化](./fastapi-startup.md)）：

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_http_client(app)
    yield
    await close_http_client(app)
```

### 在路由中使用

```python
from fastapi import APIRouter

from app.core.http import HttpClient

router = APIRouter()


@router.get("/users/{user_id}")
async def get_user(user_id: int, client: HttpClient):
    response = await client.get(f"https://api.example.com/users/{user_id}")
    response.raise_for_status()
    return response.json()
```

**优势**：
- 测试时可用 `app.dependency_overrides[get_http_client] = mock_client` 轻松替换
- 类型安全，IDE 自动补全
- 连接池在整个应用生命周期内复用

---

## 连接池配置

```python
import httpx

# 默认值：max_connections=100, max_keepalive_connections=20
limits = httpx.Limits(
    max_connections=100,           # 最大连接数
    max_keepalive_connections=20,  # 保持活跃的连接数
)

client = httpx.AsyncClient(limits=limits)
```

### 监控连接池耗尽

```python
import httpx

try:
    limits = httpx.Limits(max_connections=5)
    timeout = httpx.Timeout(pool=2.0)  # 连接池等待超时

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        # 并发请求可能耗尽连接池
        responses = await asyncio.gather(*[
            client.get("https://httpbin.org/delay/5")
            for _ in range(10)
        ])
except httpx.PoolTimeout:
    print("连接池耗尽！")
```

---

## 超时配置

```python
import httpx

# 单一超时（所有操作）
timeout = httpx.Timeout(10.0)

# 细粒度超时
timeout = httpx.Timeout(
    connect=5.0,   # 建立连接超时
    read=10.0,     # 读取响应超时
    write=5.0,     # 发送请求超时
    pool=5.0,      # 获取连接池连接超时
)

client = httpx.AsyncClient(timeout=timeout)

# 单个请求覆盖
response = await client.get(
    "https://slow-api.example.com/data",
    timeout=60.0,  # 此请求 60 秒超时
)
```

### 超时异常处理

```python
import httpx

try:
    response = await client.get("https://slow-api.example.com/data")
except httpx.ConnectTimeout:
    # 连接建立超时
    pass
except httpx.ReadTimeout:
    # 读取响应超时
    pass
except httpx.WriteTimeout:
    # 发送请求超时
    pass
except httpx.PoolTimeout:
    # 连接池获取超时
    pass
except httpx.TimeoutException:
    # 通用超时
    pass
```

---

## 并发请求

```python
import asyncio
import httpx


@router.get("/aggregate")
async def aggregate_data(client: HttpClient):
    # 并行请求多个 API
    tasks = [
        client.get("https://api1.example.com/data"),
        client.get("https://api2.example.com/data"),
        client.get("https://api3.example.com/data"),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    data = {}
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            data[f"api{i+1}"] = {"error": str(result)}
        else:
            data[f"api{i+1}"] = result.json()

    return data
```

---

## 重试机制（Tenacity）

```python
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
)
async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


@router.get("/reliable-fetch")
async def reliable_fetch(client: HttpClient):
    return await fetch_with_retry(client, "https://api.example.com/data")
```

---

## 请求/响应钩子

```python
import httpx
import logging

logger = logging.getLogger(__name__)


async def log_request(request: httpx.Request):
    logger.info(f"Request: {request.method} {request.url}")


async def log_response(response: httpx.Response):
    logger.info(f"Response: {response.status_code} {response.url}")


client = httpx.AsyncClient(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    }
)
```

---

## 认证与 Headers

```python
import httpx

# Bearer Token
client = httpx.AsyncClient(
    headers={"Authorization": "Bearer your-token"},
)

# Basic Auth
client = httpx.AsyncClient(
    auth=("username", "password"),
)

# 自定义 Auth 类
class BearerAuth(httpx.Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


client = httpx.AsyncClient(auth=BearerAuth("your-token"))
```

---

## 代理配置

```python
import httpx

# HTTP 代理
client = httpx.AsyncClient(
    proxy="http://localhost:8080",
)

# 分协议代理
client = httpx.AsyncClient(
    proxies={
        "http://": "http://localhost:8080",
        "https://": "http://localhost:8080",
    }
)
```

---

## 最佳实践

1. **共享客户端** - 使用 `init_http_client()` 初始化，避免每次请求新建
2. **配置超时** - 始终设置合理的超时，避免无限等待
3. **连接池** - 根据并发量调整 `max_connections`
4. **错误处理** - 捕获特定异常类型，提供友好错误信息
5. **重试策略** - 对网络错误使用指数退避重试
6. **HTTP/2** - 对同一主机的多请求启用 HTTP/2
7. **关闭客户端** - 确保在 lifespan 中调用 `close_http_client()`

---

## 测试中使用

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
```

---

## 常见问题

### 避免阻塞事件循环

```python
# ❌ 错误：在 async 函数中使用同步 requests
import requests
async def bad_example():
    response = requests.get("https://api.example.com")  # 阻塞！

# ✅ 正确：使用 httpx.AsyncClient
import httpx
async def good_example(client: httpx.AsyncClient):
    response = await client.get("https://api.example.com")
```

### 避免在热循环中创建客户端

```python
# ❌ 错误：每次请求创建新客户端
async def bad_example():
    for url in urls:
        async with httpx.AsyncClient() as client:  # 浪费连接池！
            await client.get(url)

# ✅ 正确：复用客户端
async def good_example():
    async with httpx.AsyncClient() as client:
        for url in urls:
            await client.get(url)
```
