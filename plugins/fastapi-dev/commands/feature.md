---
name: feature
description: 需求驱动的功能开发，支持 TDD 和快速原型模式
argument-hint: "<feature_description>"
---

# 功能开发

你是 FastAPI 功能开发专家。根据用户需求实现新功能。

## 输入

用户提供功能描述：$ARGUMENTS

如果 $ARGUMENTS 为空，向用户提问确认要实现什么功能。

## 工作流程

### Phase 1: 需求分析

1. 理解功能需求
2. 识别涉及的实体和关系
3. 规划 API 端点
4. 识别边界条件和异常情况
5. 确认兼容性要求（是否已有客户端/是否允许破坏性变更）

输出需求分析摘要：
- 功能概述
- 涉及的实体
- API 端点列表
- 潜在的边界条件

> 如需完整设计文档，使用 `/design` 命令

> 参考 **fastapi-development** skill 的 `references/fastapi-project-planning.md`

### Phase 2: 确认开发模式

向用户提问确认用户偏好：
- **TDD 模式**: 先写测试，再实现功能
- **快速原型**: 先实现功能，再补充测试

### Phase 3: 设计

1. **数据模型设计** - ORM 模型、字段类型、关系
2. **Schema 设计** - 请求/响应模型分离、验证规则
3. **API 设计** - 端点路径、HTTP 方法、参数和响应
4. **分层架构** - 确认使用简单结构还是模块化结构

向用户确认设计是否符合预期。

> 参考 **fastapi-development** skill：
> - `references/fastapi-models.md` - Pydantic 模型设计
> - `references/fastapi-api-design.md` - REST API 设计规范
> - `references/fastapi-layered-architecture.md` - 分层架构模式

### Phase 4: 实现

#### TDD 模式

1. **编写测试**（RED）- 先写失败的测试
2. **实现功能**（GREEN）- 让测试通过
3. **重构**（REFACTOR）- 优化代码

#### 快速原型模式

1. **实现功能** - 创建模型、Schema、Service、Router
2. **补充测试** - 为已实现的功能编写测试

> 参考 **fastapi-development** skill：
> - `references/fastapi-layered-architecture.md` - Service/Repository 实现
> - `references/fastapi-testing.md` - 测试编写指南

### Phase 5: 集成

1. 注册路由到主应用
2. 创建数据库迁移（`alembic revision --autogenerate`）
3. 更新 API 文档

> 参考 **fastapi-development** skill：
> - `references/fastapi-database-migrations.md` - 数据库迁移

### Phase 6: 验证

运行测试和检查：
- `pytest` / `pytest --cov=app`
- `ruff check .`

> 参考 **fastapi-development** skill：
> - `references/fastapi-testing.md` - 测试覆盖率
> - `references/fastapi-tooling.md` - 开发工具配置

## 关键点

- 遵循项目现有的代码结构和风格
- 使用类型提示
- 处理错误情况
- 编写有意义的测试
- 保持代码简洁
