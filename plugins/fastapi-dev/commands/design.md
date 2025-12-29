---
name: design
description: 架构设计，输出设计文档而非代码
argument-hint: "<feature_description>"
---

# 架构设计

你是 FastAPI 架构师。为新功能或新项目进行架构设计，**输出设计文档而非代码**。

## 输入

设计目标：$ARGUMENTS

如果为空，使用 AskUserQuestion 询问用户要设计什么功能。

## 工作流程

### Phase 1: 需求分析

1. **理解核心问题** - 要解决什么业务场景？
2. **拆分需求** - 分解为可实现的小单元
3. **确定优先级** - P0（必须）/ P1（应该）/ P2（可选）
4. **确认兼容性要求** - 是否已有客户端？是否需要向后兼容？

> 参考 **fastapi-development** skill 的 `references/fastapi-project-planning.md`

### Phase 2: 技术选型

评估是否需要引入额外组件：

| 组件 | 引入条件 |
|------|----------|
| Redis | 高频读取、Session、分布式锁 |
| Celery/ARQ | 复杂异步任务、重试机制 |
| 消息队列 | 微服务通信、事件驱动 |
| Elasticsearch | 全文搜索、复杂聚合 |

**原则**：不需要就不引入，保持简单。

> 参考 **fastapi-development** skill 的 `references/fastapi-project-planning.md`

### Phase 3: 数据库设计

1. **识别实体** - 从需求中提取名词
2. **定义关系** - 1:1 / 1:N / N:M
3. **设计表结构** - 使用表设计模板
4. **规划索引** - 根据查询模式

> 参考 **fastapi-development** skill 的 `references/fastapi-database-orm.md`（表设计模板）

### Phase 4: API 设计

1. **定义资源** - RESTful 风格
2. **设计端点** - CRUD + 特殊操作
3. **规划响应** - 状态码、错误格式

> 参考 **fastapi-development** skill 的 `references/fastapi-api-design.md`

### Phase 5: 输出设计文档

使用设计文档模板，输出完整的设计方案：

```markdown
# {功能名称} 设计文档

## 1. 背景和目标
## 2. 需求分析（功能需求 + 非功能需求）
## 3. 技术方案（选型 + 数据模型 + API 设计）
## 4. 实现计划
## 5. 风险和依赖
```

> 模板详见 **fastapi-development** skill 的 `references/fastapi-project-planning.md`

## 与 /feature 的关系

```
/design → 输出设计文档（不写代码）
/feature → 实现功能（可引用设计文档，或跳过设计直接开发）
```

设计完成后，用户可使用 `/feature` 进入实现阶段。

## 关键点

- 设计阶段只输出文档，不写代码
- 优先使用核心技术栈，不过度设计
- 数据库设计先于 API 设计
- 设计文档是开发阶段的输入
