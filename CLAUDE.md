# FastAPI Development Plugin

> Claude Code Plugin，用于团队 FastAPI 开发的全流程支持。

## 项目信息

- **位置**: `/Users/nightx/projects/nightx-agents`
- **参考项目**: `/Users/nightx/projects/agents`（wshobson/agents 插件市场）
- **状态**: v1.0 完成

---

## 设计决策记录

### 1. 单一 Agent vs 多 Agent

**决策**: 使用单一 Agent (`fastapi-pro`)

**理由**:
- FastAPI 开发各方面紧密关联，不需要"专家会诊"
- 通过 Commands 区分工作流，Agent 负责执行
- 维护成本低，上下文连续

### 2. Agent vs Skill 职责划分

**决策**: Agent 定义"谁"，Skill 定义"知识"

| 维度 | Agent | Skill |
|------|-------|-------|
| 内容 | 核心原则、行为特征、开发流程 | 详细规范、代码模板、参考资料 |
| 加载 | 每次对话都加载 | 按需触发加载 |
| 变化 | 相对稳定 | 可持续扩展 |
| 大小 | ~185 行 | 300-400 行/skill |

**判断标准**: "每次都需要" → Agent，"特定场景才需要" → Skill

### 3. Skills 设计

**决策**: 2 个专业 Skill，按职责分离

| Skill | 职责 | 触发场景 |
|-------|------|----------|
| `fastapi-architecture` | 需求分析、技术选型、数据库设计 | 设计阶段 |
| `fastapi-development` | 编写代码、测试、最佳实践 | 实现阶段 |

**理由**:
- 架构设计 = "做什么、为什么"（输出设计文档）
- 开发实现 = "怎么做"（输出代码）

### 4. 项目结构模板

**决策**: 支持两种结构

```
简单结构 (simple):           模块化结构 (modular):
app/                         app/
├── main.py                  ├── main.py
├── config.py                ├── config.py
├── routers/                 ├── api/v1/router.py
├── schemas/                 ├── modules/
├── services/                │   └── {domain}/
├── models/                  │       ├── router.py
└── core/                    │       ├── schemas.py
                             │       ├── models.py
                             │       ├── service.py
                             │       ├── repository.py     # optional
                             │       ├── dependencies.py
                             │       ├── exceptions.py
                             │       └── constants.py
                             └── core/
                                 ├── config.py
                                 ├── database.py
                                 ├── exceptions.py
                                 └── dependencies.py
```

---

## 当前 Plugin 结构

```
nightx-agents/
├── plugin.json                     # Plugin 配置
├── CLAUDE.md                       # 本文件
├── agents/
│   └── fastapi-pro.md             # FastAPI 专家 (Opus, ~185 行)
├── commands/
│   ├── fastapi-init.md            # /fastapi-init - 交互式初始化
│   ├── fastapi-feature.md         # /fastapi-feature - 功能开发
│   ├── fastapi-review.md          # /fastapi-review - 代码审查
│   ├── fastapi-test.md            # /fastapi-test - 测试生成
│   └── fastapi-refactor.md        # /fastapi-refactor - 代码重构
└── skills/
    ├── fastapi-architecture/       # 架构设计 Skill
    │   └── SKILL.md
    └── fastapi-development/        # 开发实现 Skill
        └── SKILL.md
```

---

## 组件说明

### Agent: fastapi-pro

**定位**: 核心原则 + 能力概览 + 行为特征

**包含内容**:
- Core Principles: KISS, SOLID/DRY, No over-engineering, Type safety, RORO
- Capabilities: 7 个分类（Core, Data, API, Security, Testing, Observability, Deployment）
- Technology Stack: 技术栈表格（含可选技术）
- Behavioral Guidelines: Async 使用、Code Style、Error Handling、REST、12-Factor
- Project Structure: 两种项目结构模板
- Quality Standards: 质量指标
- Development Process: 新功能开发、代码审查流程
- Edge Cases: 边界情况处理
- Example Interactions: 8 个示例用户查询

### Commands

| 命令 | 用途 | 特点 |
|------|------|------|
| `/fastapi-init` | 初始化项目 | 交互式询问需求 |
| `/fastapi-feature` | 开发新功能 | 支持 TDD 和快速原型 |
| `/fastapi-review` | 代码审查 | 规范+架构+性能 |
| `/fastapi-test` | 生成测试 | 覆盖率 >= 80% |
| `/fastapi-refactor` | 重构代码 | 保持测试绿色 |

### Skills

#### fastapi-architecture

**内容**:
- 需求分析流程
- 技术选型决策（何时用 Redis/Celery/MQ）
- 数据库设计（含命名约定、SQL 优先原则、Migration 规范）
- API 设计规范
- 设计文档模板

**触发**: 设计、架构、需求、技术选型、数据库设计

#### fastapi-development

**内容**:
- Pydantic 规范（内置验证、全局 Base Model、Settings 拆分）
- Dependencies 规范（业务校验、依赖缓存、优先 async）
- Observability 规范（Structured Logging、Health Checks、Request ID）
- Documentation 规范（生产隐藏文档、完整元数据）
- Testing 规范（async 测试、测试原则）
- 代码规范（Ruff 配置）
- Router/Service/Model/Schema 模板
- SQLAlchemy 2.0 异步模式
- 错误处理

**触发**: 实现、编写、代码、router、service、测试

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI 0.120+, Pydantic v2 |
| 数据库 | PostgreSQL, SQLAlchemy 2.0 (async), Alembic |
| 测试 | pytest, pytest-asyncio, httpx |
| 工具 | uv, ruff, ty |
| 认证 | JWT (python-jose), OAuth2 |
| 可选 | Redis, arq/Celery, S3/MinIO, loguru |

---

## 推荐工作流

### 新功能开发

```
1. 用户: /fastapi-feature "用户订单功能"

2. 架构设计阶段 (fastapi-architecture)
   ├─ 分析需求
   ├─ 技术选型（是否需要 Redis/Celery）
   ├─ 设计数据库表
   └─ 规划 API
   → 输出: 设计文档

3. 用户确认设计

4. 开发实现阶段 (fastapi-development)
   ├─ 实现 Model
   ├─ 实现 Schema
   ├─ 实现 Service
   ├─ 实现 Router
   └─ 编写测试
   → 输出: 代码
```

---

## 参考来源

本 Plugin 的规范整合自：
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [wshobson/agents](https://github.com/wshobson/agents) python-development plugin
- Cursor Rules FastAPI 最佳实践

---

## 快速恢复上下文

如果需要继续开发这个 Plugin：

1. 阅读本文件了解设计决策
2. 查看 `agents/fastapi-pro.md` 了解 Agent 定义
3. 查看 `skills/*/SKILL.md` 了解详细规范
4. 查看 `commands/*.md` 了解命令定义
