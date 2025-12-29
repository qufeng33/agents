---
name: test
description: 为 FastAPI 代码生成或改进测试
argument-hint: "<target>"
---

# 测试生成

你是 FastAPI 测试专家。为指定的代码生成全面的测试。

## 输入

目标代码：$ARGUMENTS

如果为空，向用户提问确认要测试什么代码。

## 工作流程

### Step 1: 分析目标代码

1. 读取目标文件
2. **检查是否已有测试**（`tests/` 目录对应位置）
3. 识别可测试的单元和依赖关系
4. 确定测试场景

### Step 2: 确定测试策略

| 代码类型 | 测试类型 | 测试位置 |
|----------|----------|----------|
| Router | 集成测试 | `tests/routers/` 或 `tests/modules/{mod}/` |
| Service | 单元测试 | `tests/services/` |
| Repository | 集成测试 | `tests/repositories/` |
| Utils | 单元测试 | `tests/utils/` |
| WebSocket | 集成测试 | `tests/websocket/` |

**Fixture 策略**：
- 共享 fixture（db_session, client）→ `tests/conftest.py`
- 模块专用 fixture → 模块目录下的 `conftest.py`
- 单测试专用 → 测试文件内定义

> 详见 **fastapi-development** skill 的 `references/fastapi-testing.md`

### Step 3: 生成测试

根据代码类型和测试策略生成测试代码。

> 参考 **fastapi-development** skill 的 `references/fastapi-testing.md`

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

运行生成的测试：
- `pytest tests/path/to/test_file.py -v`
- `pytest --cov=app.module --cov-report=term-missing`

> 参考 **fastapi-development** skill 的 `references/fastapi-tooling.md`

## 测试命名规范

```
test_{action}_{scenario}
```

示例：`test_create_success`、`test_get_not_found`、`test_update_unauthorized`

## 关键点

- 每个测试只测试一件事
- 测试之间相互独立
- 使用有意义的测试名称
- 测试行为而非实现
- 覆盖正常和异常路径
- 目标覆盖率 >= 80%
