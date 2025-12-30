# FastAPI API 设计原则
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- URL 表达资源而非动作
- 接口语义清晰且幂等性正确
- 请求/响应模型严格分离
- 错误响应格式统一
- 版本策略明确、可演进

## 最佳实践
1. URL 使用名词复数
2. 使用正确 HTTP 方法与状态码
3. 列表接口必须分页
4. 过滤/搜索参数要可预测
5. 统一错误码与响应结构

## 目录
- `RESTful 设计规范`
- `状态码规范`
- `分页设计`
- `过滤与搜索`
- `错误响应格式`
- `请求/响应模型分离`
- `API 版本管理`
- `路由注册`
- `相关文档`

---

## RESTful 设计规范

### URL 设计

```python
GET    /api/users           # 列表
POST   /api/users           # 创建
GET    /api/users/{id}      # 单个
PUT    /api/users/{id}      # 完整替换
PATCH  /api/users/{id}      # 部分更新
DELETE /api/users/{id}      # 删除

# 嵌套资源（表示从属关系，最多 2 层）
GET    /api/users/{id}/orders  # 获取用户的订单
POST   /api/users/{id}/orders  # 为用户创建订单
```

反例（避免动词）：

```python
POST /api/createUser       # ❌ 动词
GET  /api/getUserById      # ❌ 动词
POST /api/users/create     # ❌ 动词
```

### HTTP 方法语义

| 方法 | 语义 | 幂等性 | 安全性 |
|------|------|--------|--------|
| GET | 获取资源 | ✓ | ✓ |
| POST | 创建资源 | ✗ | ✗ |
| PUT | 完整替换 | ✓ | ✗ |
| PATCH | 部分更新 | ✓ | ✗ |
| DELETE | 删除资源 | ✓ | ✗ |

---

## 状态码规范

### 成功响应

```python
@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(...):
    return ApiResponse(data=user)  # 200

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(...):
    return ApiResponse(data=user)  # 201
```

### 错误响应

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 400 | Bad Request | 请求格式错误、参数无效 |
| 401 | Unauthorized | 未认证（缺少/无效 token） |
| 403 | Forbidden | 已认证但无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突 |
| 422 | Unprocessable Entity | 验证失败 |
| 500 | Internal Server Error | 服务器内部错误 |

---

## 分页设计

### 分页参数约定

| 参数 | 说明 | 默认值 | 约束 |
|------|------|--------|------|
| `page` | 页码（从 0 开始） | 0 | `ge=0` |
| `page_size` | 每页数量 | 20 | `ge=1, le=100` |

### 响应模型

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiPagedResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: list[T]
    total: int
    page: int
    page_size: int
```

> Repository 分页实现与过滤条件组合见 [数据库模式](./fastapi-database-patterns.md)。

---

## 过滤与搜索

建议使用明确的查询参数：
- `status`、`is_active` 等枚举/布尔值
- `created_after/created_before` 时间范围
- `search` 字符串模糊匹配

> 过滤条件在 Repository 层构建 SQL，避免在 Python 侧过滤。

---

## 错误响应格式

统一错误响应结构：`code` + `message` + `data` + `detail`。

```json
{
  "code": 40001,
  "message": "Validation failed",
  "data": null,
  "detail": {
    "errors": [
      {"field": "username", "message": "Invalid format", "type": "value_error"}
    ]
  }
}
```

> 错误码体系与异常处理详见 [错误处理](./fastapi-errors.md)。

---

## 请求/响应模型分离

创建/更新输入与输出响应模型必须分离，避免暴露内部字段。

> Pydantic 模型规范详见 [数据模型](./fastapi-models.md)。

---

## API 版本管理

推荐 URL 版本：

```python
# app/api/v1/router.py
api_router = APIRouter()

# main.py
app.include_router(api_router, prefix="/api/v1")
```

> 是否共存多个版本由业务兼容性决定，需要兼容则保留旧版本并增加新版本。

---

## 路由注册

```python
# app/core/routers.py
from fastapi import FastAPI
from app.api.v1.router import api_router as v1_router


def setup_routers(app: FastAPI) -> None:
    app.include_router(v1_router, prefix="/api/v1")
```

> 在 main.py 中调用详见 [应用生命周期](./fastapi-app-lifecycle.md)。

---

## 相关文档

- [错误处理](./fastapi-errors.md)
- [数据模型](./fastapi-models.md)
- [数据库模式](./fastapi-database-patterns.md)
- [项目结构](./fastapi-project-structure.md)
- [应用生命周期](./fastapi-app-lifecycle.md)
