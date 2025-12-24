---
name: fastapi-feature
description: 需求驱动的功能开发，支持 TDD 和快速原型模式
allowed_args: feature_description
---

# 功能开发

你是 FastAPI 功能开发专家。根据用户需求实现新功能。

## 输入

用户提供功能描述：$ARGUMENTS

如果 $ARGUMENTS 为空，使用 AskUserQuestion 询问用户要实现什么功能。

## 工作流程

### Phase 1: 需求分析

1. 理解功能需求
2. 识别涉及的实体和关系
3. 规划 API 端点
4. 识别边界条件和异常情况

输出需求分析摘要，包括：
- 功能概述
- 涉及的实体
- API 端点列表
- 潜在的边界条件

### Phase 2: 确认开发模式

使用 AskUserQuestion 询问用户偏好的开发模式：
- **TDD 模式**: 先写测试，再实现功能
- **快速原型**: 先实现功能，再补充测试

### Phase 3: 设计

1. **数据模型设计**
   - SQLAlchemy 模型定义
   - 字段类型和约束
   - 关系设计

2. **Schema 设计**
   - 请求 Schema (Create, Update)
   - 响应 Schema
   - 验证规则

3. **API 设计**
   - 端点路径
   - HTTP 方法
   - 参数和响应

向用户确认设计是否符合预期。

### Phase 4: 实现

#### TDD 模式

1. **编写测试** (RED)
   ```python
   # tests/test_{feature}.py
   async def test_create_success(client):
       response = await client.post("/...", json={...})
       assert response.status_code == 201

   async def test_create_validation_error(client):
       response = await client.post("/...", json={...})
       assert response.status_code == 422
   ```

2. **实现功能** (GREEN)
   - 创建模型
   - 创建 Schema
   - 实现 Service
   - 实现 Router

3. **重构** (REFACTOR)
   - 检查代码质量
   - 优化实现

#### 快速原型模式

1. **实现功能**
   - 创建模型
   - 创建 Schema
   - 实现 Service
   - 实现 Router

2. **补充测试**
   - 为已实现的功能编写测试
   - 确保测试通过

### Phase 5: 集成

1. 注册路由到主应用
2. 创建数据库迁移
3. 更新 API 文档

### Phase 6: 验证

1. 运行所有测试
2. 检查测试覆盖率
3. 运行 lint 和类型检查

```bash
pytest
pytest --cov=app
ruff check .
mypy app
```

## 代码模板

### 模型

```python
# app/models/{entity}.py
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, TimestampMixin

class {Entity}(TimestampMixin, Base):
    __tablename__ = "{entities}"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # ... 其他字段
```

### Schema

```python
# app/schemas/{entity}.py
from pydantic import BaseModel, ConfigDict

class {Entity}Base(BaseModel):
    name: str

class {Entity}Create({Entity}Base):
    pass

class {Entity}Update(BaseModel):
    name: str | None = None

class {Entity}Response({Entity}Base):
    model_config = ConfigDict(from_attributes=True)
    id: int
```

### Service

```python
# app/services/{entity}.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.{entity} import {Entity}
from app.schemas.{entity} import {Entity}Create, {Entity}Update

class {Entity}Service:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: {Entity}Create) -> {Entity}:
        entity = {Entity}(**data.model_dump())
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get(self, id: int) -> {Entity} | None:
        result = await self.session.execute(
            select({Entity}).where({Entity}.id == id)
        )
        return result.scalar_one_or_none()
```

### Router

```python
# app/routers/{entity}.py (简单结构)
# app/modules/{entity}/router.py (模块化结构)
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from app.services.{entity} import {Entity}Service
from app.schemas.{entity} import {Entity}Create, {Entity}Response
from app.core.deps import get_{entity}_service

router = APIRouter(prefix="/{entities}", tags=["{entities}"])

@router.post("/", response_model={Entity}Response, status_code=status.HTTP_201_CREATED)
async def create_{entity}(
    data: {Entity}Create,
    service: Annotated[{Entity}Service, Depends(get_{entity}_service)],
) -> {Entity}Response:
    return await service.create(data)
```

## 关键点

- 遵循项目现有的代码结构和风格
- 使用类型提示
- 处理错误情况
- 编写有意义的测试
- 保持代码简洁
