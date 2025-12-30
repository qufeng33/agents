# FastAPI HTTP 客户端（httpx）
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 共享客户端，避免重复创建
- 超时必须显式配置
- 并发请求要可控
- 错误处理清晰可追踪
- 生命周期由应用统一管理

## 最佳实践
1. 客户端在 lifespan 初始化与关闭
2. 超时与连接池根据负载配置
3. 并发请求使用 `asyncio.gather`
4. 网络错误可用重试策略
5. 禁止在 async 中使用 requests

## 目录
- `概述`
- `生命周期管理 + 依赖注入`
- `连接池与超时`
- `并发请求`
- `认证与代理`
- `常见问题`
- `相关文档`

---

## 概述

httpx 是 FastAPI 推荐的 HTTP 客户端库，支持同步和异步请求。

```bash
uv add httpx
# HTTP/2 支持
uv add "httpx[http2]"
```

---

## 生命周期管理 + 依赖注入

```python
# core/http.py
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request


async def init_http_client(app: FastAPI) -> None:
    app.state.http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        timeout=httpx.Timeout(10.0, connect=5.0),
        http2=True,
    )


async def close_http_client(app: FastAPI) -> None:
    await app.state.http_client.aclose()


async def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
```

> 在 lifespan 中调用 `init_http_client/close_http_client`，详见 [应用生命周期](./fastapi-app-lifecycle.md)。

---

## 连接池与超时

```python
import httpx

client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=httpx.Timeout(10.0, connect=5.0, read=10.0),
)
```

> 异常处理可按需捕获 `httpx.TimeoutException` 或网络错误。

---

## 并发请求

```python
import asyncio


@router.get("/aggregate")
async def aggregate_data(client: HttpClient):
    tasks = [
        client.get("https://api1.example.com/data"),
        client.get("https://api2.example.com/data"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        "api1": results[0].json() if not isinstance(results[0], Exception) else None,
        "api2": results[1].json() if not isinstance(results[1], Exception) else None,
    }
```

> 并发量应受限于连接池与下游承载能力。

---

## 认证与代理

- Bearer Token/Basic Auth 可在 `AsyncClient(headers/auth=...)` 配置
- 代理可使用 `proxy` 或 `proxies` 参数

---

## 常见问题

### 避免阻塞事件循环

```python
# ❌ 错误：在 async 函数中使用同步 requests
import requests
async def bad_example():
    response = requests.get("https://api.example.com")

# ✅ 正确：使用 httpx.AsyncClient
import httpx
async def good_example(client: httpx.AsyncClient):
    response = await client.get("https://api.example.com")
```

---

## 相关文档

- [应用生命周期](./fastapi-app-lifecycle.md)
- [性能优化](./fastapi-performance.md)
- [测试](./fastapi-testing.md)
