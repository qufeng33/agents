---
name: fastapi-architecture
description: |
  FastAPI 架构设计知识库：需求分析、技术选型、数据库设计、API 规划。
  This skill should be used when designing FastAPI application architecture, analyzing requirements, making technology decisions, or planning database schemas.
  Triggers: "设计", "架构", "需求", "技术选型", "数据库设计", "表设计", "design", "architecture", "tech stack", "database schema", "API design"
---

# FastAPI 架构设计指南

专注于**设计和规划**，输出设计文档而非代码。

---

## 1. 需求分析流程

### Step 1: 理解业务需求

```
用户需求 → 核心问题是什么？
         → 要解决什么业务场景？
         → 有哪些约束条件？
```

**关键问题清单**：
- 功能的核心价值是什么？
- 谁是使用者？
- 预期的数据量级？
- 性能要求？（响应时间、并发量）
- 是否需要实时性？

### Step 2: 拆分需求

将大需求拆分为可实现的小单元：

```
大需求: 用户订单系统
  ├─ 用户管理
  │   ├─ 用户注册
  │   ├─ 用户登录
  │   └─ 用户信息修改
  ├─ 商品管理
  │   ├─ 商品列表
  │   └─ 商品详情
  └─ 订单管理
      ├─ 创建订单
      ├─ 订单列表
      └─ 订单状态变更
```

### Step 3: 确定优先级

| 优先级 | 标准 | 示例 |
|--------|------|------|
| P0 | 核心功能，必须有 | 用户登录、创建订单 |
| P1 | 重要功能，应该有 | 订单状态通知 |
| P2 | 增强功能，可以有 | 订单数据分析 |

---

## 2. 技术选型决策

### 核心技术栈（默认）

| 组件 | 选择 | 理由 |
|------|------|------|
| 框架 | FastAPI | 异步、类型安全、自动文档 |
| ORM | SQLAlchemy 2.0 | 成熟、异步支持、灵活 |
| 数据库 | PostgreSQL | 功能丰富、可靠 |
| 验证 | Pydantic v2 | 性能好、与 FastAPI 集成 |

### 扩展组件选型

根据需求选择是否引入：

#### 缓存 (Redis)

**需要引入的场景**：
- 高频读取的数据（如配置、热点数据）
- Session 存储
- 分布式锁
- 消息队列（简单场景）

**不需要的场景**：
- 简单 CRUD 应用
- 数据量小、并发低
- 实时性要求不高

#### 异步任务 (Celery)

**需要引入的场景**：
- 耗时操作（发邮件、生成报表）
- 定时任务
- 需要重试机制的任务

**不需要的场景**：
- 所有操作都能在请求内完成
- FastAPI BackgroundTasks 能满足

**轻量替代**：
- 简单后台任务：FastAPI BackgroundTasks
- 定时任务：APScheduler

#### 消息队列 (RabbitMQ/Kafka)

**需要引入的场景**：
- 微服务间通信
- 事件驱动架构
- 高吞吐量消息处理

**不需要的场景**：
- 单体应用
- Redis Pub/Sub 能满足

#### 搜索引擎 (Elasticsearch)

**需要引入的场景**：
- 全文搜索
- 复杂查询和聚合
- 日志分析

**不需要的场景**：
- PostgreSQL 全文搜索能满足
- 简单的 LIKE 查询

---

## 3. 数据库设计

### 设计原则

1. **先理解业务实体和关系**
2. **从核心实体开始设计**
3. **考虑查询模式决定索引**
4. **预留扩展字段**

### 实体识别

```
业务需求 → 识别名词 → 筛选核心实体
```

示例：
```
"用户可以创建订单购买商品"

名词：用户、订单、商品
核心实体：User, Order, Product
关系：User 1:N Order, Order N:M Product
```

### 命名约定

| 元素 | 规范 | 示例 |
|------|------|------|
| 表名 | snake_case，单数，模块前缀 | `user`, `order_item` |
| 字段 | snake_case | `created_at`, `user_id` |
| 时间字段 | `_at` 后缀（datetime）, `_date` 后缀（date） | `created_at`, `birth_date` |
| 布尔字段 | `is_` 或 `has_` 前缀 | `is_active`, `has_verified` |
| 外键 | `{table}_id` | `user_id`, `order_id` |
| 索引 | `ix_{table}_{columns}` | `ix_user_email` |
| 唯一约束 | `uq_{table}_{columns}` | `uq_user_email` |

### 表设计模板

```
表名: {entities}
描述: {功能描述}

字段:
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGINT | PK, AUTO | 主键 |
| ... | ... | ... | ... |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

索引:
| 索引名 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| ix_{table}_{field} | field | BTREE | 用于 xxx 查询 |

关系:
- belongs_to: {parent_table}
- has_many: {child_table}
```

### SQL 优先原则

- 复杂 join、聚合、JSON 构建在 SQL 中完成，不在 Python
- 数据库处理数据比应用层更高效

### Migration 规范

- 文件名：`{date}_{description}.py`（如 `2024-01-15_add_user_email_idx.py`）
- 必须可逆（提供 downgrade）
- 静态内容，避免运行时依赖

### 常见设计模式

#### 软删除

```
deleted_at: TIMESTAMP NULL  -- NULL 表示未删除
```

#### 状态机

```
status: VARCHAR(20)  -- 使用字符串而非数字，更可读
-- 示例：draft, pending, approved, rejected
```

#### 多对多关系

```
表: order_products (关联表)
| order_id | product_id | quantity | price |
```

---

## 4. API 设计

### RESTful 设计原则

| 操作 | HTTP 方法 | 路径示例 |
|------|-----------|----------|
| 列表 | GET | /users |
| 详情 | GET | /users/{id} |
| 创建 | POST | /users |
| 全量更新 | PUT | /users/{id} |
| 部分更新 | PATCH | /users/{id} |
| 删除 | DELETE | /users/{id} |

### API 设计模板

```
API: {功能名称}
路径: {METHOD} /api/v1/{resource}

描述: {功能描述}

请求参数:
| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| id | path | int | Y | 资源 ID |
| name | body | string | Y | 名称 |

响应:
| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| 200 | 成功 | {...} |
| 404 | 不存在 | {"error": {...}} |
```

---

## 5. 项目结构选择

### 简单结构

适用于：小型项目、原型、个人项目

```
app/
├── main.py
├── config.py
├── routers/
├── schemas/
├── services/
├── models/
└── core/
```

### 模块化结构

适用于：中大型项目、团队协作

```
app/
├── main.py
├── config.py
├── api/v1/router.py
├── modules/
│   └── {domain}/
│       ├── router.py
│       ├── schemas.py
│       ├── service.py
│       └── models.py
└── core/
```

**选择依据**：
- 预期 3+ 个业务模块 → 模块化结构
- 团队 2+ 人协作 → 模块化结构
- 快速原型验证 → 简单结构

---

## 6. 设计文档模板

```markdown
# {功能名称} 设计文档

## 1. 背景和目标
{为什么要做这个功能？解决什么问题？}

## 2. 需求分析
### 2.1 功能需求
- [ ] 需求点 1
- [ ] 需求点 2

### 2.2 非功能需求
- 性能：{要求}
- 安全：{要求}

## 3. 技术方案
### 3.1 技术选型
| 组件 | 选择 | 理由 |
|------|------|------|

### 3.2 数据模型
{表设计}

### 3.3 API 设计
{接口列表}

## 4. 实现计划
| 阶段 | 内容 | 产出 |
|------|------|------|
| 1 | ... | ... |

## 5. 风险和依赖
- 风险：{可能的问题}
- 依赖：{外部依赖}
```

---

## 输出物

架构设计完成后，应输出：

1. **设计文档**（使用上述模板）
2. **数据库 ER 图**（可选）
3. **API 列表**
4. **技术选型决策记录**

这些文档将作为开发阶段的输入。
