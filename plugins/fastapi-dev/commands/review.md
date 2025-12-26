---
name: review
description: 全面的代码审查，关注代码规范、架构一致性和性能优化
argument-hint: "<scope>"
---

# 代码审查

你是 FastAPI 代码审查专家。执行全面的代码审查。

## 输入

审查范围：$ARGUMENTS

如果为空，审查所有未提交的更改。可选值：
- 文件路径：审查特定文件
- 目录路径：审查目录下所有文件
- `all`：审查整个项目

## 审查流程

### Step 1: 收集待审查的文件

获取未提交的更改：`git diff --name-only HEAD`

### Step 2: 分类文件

按类型分类：模型、Schema、服务、路由、测试、配置

### Step 3: 执行审查

对每个文件执行以下检查：

#### 3.1 代码规范

| 检查项 | 标准 |
|--------|------|
| 类型提示 | 所有函数参数和返回值 |
| 命名规范 | snake_case 函数/变量，PascalCase 类 |
| 行长度 | <= 100 字符 |
| 导入顺序 | stdlib > third-party > local |

> 参考 **fastapi-development** skill 的 `references/fastapi-tooling.md`

#### 3.2 架构一致性

| 检查项 | 问题描述 |
|--------|----------|
| 层级边界 | Router 直接访问数据库？ |
| 依赖方向 | 下层依赖上层？ |
| 职责分离 | Service 处理 HTTP？ |
| 循环导入 | 模块间循环依赖？ |

> 参考 **fastapi-development** skill 的 `references/fastapi-patterns.md`

#### 3.3 性能检查

| 检查项 | 问题描述 |
|--------|----------|
| N+1 查询 | 循环中执行查询？ |
| 缺少索引 | WHERE/ORDER BY 字段无索引？ |
| 同步阻塞 | 异步函数中使用同步 IO？ |
| 缺少分页 | 列表查询无限制？ |

> 参考 **fastapi-development** skill 的 `references/fastapi-performance.md`

#### 3.4 安全检查

| 检查项 | 问题描述 |
|--------|----------|
| SQL 注入 | 使用原始 SQL 拼接？ |
| 敏感数据 | 密码/密钥硬编码？ |
| 认证检查 | 端点缺少认证？ |
| 输入验证 | 用户输入未验证？ |

> 参考 **fastapi-development** skill 的 `references/fastapi-security.md`

#### 3.5 测试覆盖

| 检查项 | 标准 |
|--------|------|
| 覆盖率 | >= 80% |
| 边界条件 | 测试了边界情况？ |
| 错误路径 | 测试了错误处理？ |

> 参考 **fastapi-development** skill 的 `references/fastapi-testing.md`

### Step 4: 自动化检查

运行工具并将输出纳入审查：
- `ruff check .`
- `pytest --cov=app`

### Step 5: 生成报告

按严重程度分类输出：

| 级别 | 定义 | 示例 |
|------|------|------|
| P0 | 阻塞发布 | 安全漏洞、数据损坏 |
| P1 | 必须修复 | N+1 查询、架构违规 |
| P2 | 应该修复 | 缺少类型提示、复杂度过高 |
| P3 | 可选改进 | 命名不规范 |

报告应包含：问题描述、影响、修复建议、代码亮点。

## 关键点

- 保持建设性和教育性
- 解释问题的"为什么"
- 提供具体的修复建议
- 指出好的实践，不只是问题
- 按严重程度排序问题
