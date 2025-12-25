---
name: test
description: 为 FastAPI 代码生成或改进测试
argument-hint: "<target>"
---

# 测试生成

你是 FastAPI 测试专家。为指定的代码生成全面的测试。

## 输入

目标代码：$ARGUMENTS

如果为空，使用 AskUserQuestion 询问用户要测试什么代码。

## 工作流程

### Step 1: 分析目标代码

1. 读取目标文件
2. 识别可测试的单元
3. 分析依赖关系
4. 识别测试场景

### Step 2: 确定测试类型

根据代码类型选择测试策略：

| 代码类型 | 测试类型 | 关键点 |
|----------|----------|--------|
| Router | 集成测试 | 使用 AsyncClient |
| Service | 单元测试 | Mock 依赖 |
| Repository | 集成测试 | 使用测试数据库 |
| Utils | 单元测试 | 纯函数测试 |

### Step 3: 生成测试

#### Router 测试

```python
# tests/integration/api/test_{router}.py
import pytest
from httpx import AsyncClient

class Test{Entity}API:
    """API 端点测试"""

    async def test_create_success(self, client: AsyncClient):
        """成功创建"""
        response = await client.post("/{entities}/", json={
            "field1": "value1",
            "field2": "value2",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["field1"] == "value1"
        assert "id" in data

    async def test_create_validation_error(self, client: AsyncClient):
        """验证失败"""
        response = await client.post("/{entities}/", json={
            "field1": "",  # 无效值
        })

        assert response.status_code == 422

    async def test_get_success(self, client: AsyncClient, {entity}_factory):
        """成功获取"""
        {entity} = await {entity}_factory()

        response = await client.get(f"/{entities}/{{entity}.id}")

        assert response.status_code == 200
        assert response.json()["id"] == {entity}.id

    async def test_get_not_found(self, client: AsyncClient):
        """不存在"""
        response = await client.get("/{entities}/99999")

        assert response.status_code == 404

    async def test_list_pagination(self, client: AsyncClient, {entity}_factory):
        """分页测试"""
        for _ in range(5):
            await {entity}_factory()

        response = await client.get("/{entities}/?skip=0&limit=2")

        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_update_success(self, client: AsyncClient, {entity}_factory):
        """成功更新"""
        {entity} = await {entity}_factory()

        response = await client.put(f"/{entities}/{{entity}.id}", json={
            "field1": "updated",
        })

        assert response.status_code == 200
        assert response.json()["field1"] == "updated"

    async def test_delete_success(self, client: AsyncClient, {entity}_factory):
        """成功删除"""
        {entity} = await {entity}_factory()

        response = await client.delete(f"/{entities}/{{entity}.id}")

        assert response.status_code == 204

        # 验证已删除
        get_response = await client.get(f"/{entities}/{{entity}.id}")
        assert get_response.status_code == 404
```

#### Service 测试

```python
# tests/unit/services/test_{service}.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.{entity} import {Entity}Service
from app.schemas.{entity} import {Entity}Create

class Test{Entity}Service:
    """Service 单元测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        return {Entity}Service(mock_session)

    async def test_create(self, service, mock_session):
        """测试创建"""
        data = {Entity}Create(field1="value1")

        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await service.create(data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_get_found(self, service, mock_session):
        """测试获取存在的记录"""
        mock_{entity} = MagicMock()
        mock_{entity}.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_{entity}
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.get(1)

        assert result.id == 1

    async def test_get_not_found(self, service, mock_session):
        """测试获取不存在的记录"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.get(1)

        assert result is None
```

#### Fixture 工厂

```python
# tests/conftest.py
import pytest
from app.models.{entity} import {Entity}

@pytest.fixture
def {entity}_factory(db_session):
    """工厂 fixture"""
    async def create(
        field1: str = "default",
        field2: str = "default",
    ) -> {Entity}:
        {entity} = {Entity}(field1=field1, field2=field2)
        db_session.add({entity})
        await db_session.flush()
        await db_session.refresh({entity})
        return {entity}

    return create
```

### Step 4: 测试场景清单

确保覆盖以下场景：

| 场景类型 | 示例 |
|----------|------|
| Happy Path | 正常创建、获取、更新、删除 |
| Validation | 无效输入、缺少必填字段 |
| Not Found | 访问不存在的资源 |
| Authorization | 未认证、无权限 |
| Edge Cases | 空列表、边界值 |
| Error Handling | 异常处理 |

### Step 5: 验证测试

运行生成的测试并检查：

```bash
# 运行测试
pytest tests/path/to/test_file.py -v

# 检查覆盖率
pytest tests/path/to/test_file.py --cov=app.path.to.module --cov-report=term-missing
```

## 测试命名规范

```
test_{action}_{scenario}
```

示例：
- `test_create_success`
- `test_create_validation_error`
- `test_get_not_found`
- `test_list_empty`
- `test_update_unauthorized`

## 关键点

- 每个测试只测试一件事
- 测试之间相互独立
- 使用有意义的测试名称
- 测试行为而非实现
- 覆盖正常和异常路径
- 目标覆盖率 >= 80%
