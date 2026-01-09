---
name: fastapi-feature
description: 完整的 FastAPI 功能开发流程：设计 → 实现 → 审查
argument-hint: <功能描述> | <task-id>
---

# FastAPI 完整功能开发

完整的功能开发流程，支持大功能拆分为多个子任务逐个处理。

---

## 本插件的自定义 Agent

本命令使用 `fastapi-dev` 插件定义的自定义 agent：

| Agent 名称 | 用途 |
|-----------|------|
| `fastapi-designer` | 需求分析、API 设计、产出 spec.md |
| `fastapi-developer` | 代码实现、遵循分层架构 |
| `fastapi-reviewer` | 代码审查（支持 focus 参数） |

### 调用方式

使用 **Task 工具** 调用，格式如下：

```
Task 工具参数：
- subagent_type: "fastapi-designer"  ← 指定 agent 名称
- prompt: "..."                       ← 传递给 agent 的指令
```

---

## 流程概述

### 阶段 1：设计
使用 Task 工具调用 `fastapi-designer` agent 产出设计文档。

### 阶段 2：确认
展示设计文档给用户，确认后进入实现阶段。

### 阶段 3：实现与审查（循环）
```
循环执行直到所有任务完成：

1. 读取任务目录下的 spec.md 任务清单
2. 找到第一个「待开始」或「待审核」的任务
3. 如果是「待开始」：用 Task 工具调用 fastapi-developer 实现
4. 如果是「待审核」：启动并行审查
   - 同时用 Task 工具调用 3 个 fastapi-reviewer（正确性/架构/安全）
   - 合并审查结果
   - 全部通过 → 标记为「已完成」
   - 有问题 → fastapi-developer 修复 → 重新审查
5. 检查是否还有未完成任务
   - 有 → 继续循环
   - 无 → 流程结束
```

### 任务状态流转
```
待开始 → 进行中 → 待审核 → 已完成
            ↑         │
            └─────────┘
           (审核不通过)
```

### 任务目录结构
```
.agent/
├── tips.md              # 经验文档（全局共享）
└── tasks/
    └── {feature}-{seq}/
        ├── spec.md      # 设计文档 + 任务状态
        └── review.md    # 审查记录（累积追加）
```

---

用户输入：

$ARGUMENTS

---

## 执行指南

### 步骤 1：解析输入

判断 `$ARGUMENTS` 的类型：

**情况 A：输入为空**
- 询问用户要开发什么功能

**情况 B：输入是已存在的任务 ID**
- 检查 `.agent/tasks/{输入}/` 目录是否存在
- 如果存在，说明是继续执行已有任务

**情况 C：输入是功能描述**
- 不是已存在的任务 ID，视为新功能描述

### 步骤 2：根据类型执行

#### 情况 A/C：新任务

1. 询问用户功能名称（用于生成 task-id，如 `user-auth`）
2. 扫描 `.agent/tasks/` 目录，生成 task-id：
   - 查找匹配 `{功能名}-*` 的目录
   - 取最大序号 + 1（无则为 001）
   - 格式：`{功能名}-{seq}`，如 `user-auth-001`
3. 创建任务目录：`.agent/tasks/{task-id}/`
4. **使用 Task 工具调用 `fastapi-designer` agent**：
   ```
   Task 工具参数：
   - subagent_type: "fastapi-designer"
   - prompt: |
       ## 文件
       - 设计文档: .agent/tasks/{task-id}/spec.md
       - 经验文档: .agent/tips.md

       ## 任务
       功能描述：{用户的功能描述}

       请完成设计流程，将设计文档写入指定文件。
   ```
5. 用户确认设计后，进入实现循环

#### 情况 B：继续已有任务

1. 读取任务状态：`.agent/tasks/{task-id}/spec.md`
2. 进入实现循环

### 步骤 3：实现与审查循环

```
循环执行：
1. 读取 .agent/tasks/{task-id}/spec.md 中的任务清单
2. 找到第一个「待开始」或「待审核」的子任务
3. 根据状态调用对应 agent：

   如果是「待开始」：
   **使用 Task 工具调用 `fastapi-developer` agent**：
   ---
   Task 工具参数：
   - subagent_type: "fastapi-developer"
   - prompt: |
       ## 文件
       - 设计文档: .agent/tasks/{task-id}/spec.md
       - 经验文档: .agent/tips.md

       ## 任务
       实现设计文档中第一个「待开始」的子任务。
       完成后更新状态为「待审核」。
   ---

   如果是「待审核」：
   ⚡ 启动并行审查（见下方详细说明）

4. 检查是否还有未完成的子任务
   - 有 → 继续循环
   - 无 → 任务完成，结束流程
```

### 并行审查流程

当子任务状态为「待审核」时，**在同一条消息中发起 3 个 Task 工具调用**：

```
Task 工具调用 1：
- subagent_type: "fastapi-reviewer"
- prompt: |
    审查范围：{变更的文件列表}
    focus: 正确性

Task 工具调用 2：
- subagent_type: "fastapi-reviewer"
- prompt: |
    审查范围：{变更的文件列表}
    focus: 架构

Task 工具调用 3：
- subagent_type: "fastapi-reviewer"
- prompt: |
    审查范围：{变更的文件列表}
    focus: 安全
```

### 合并审查结果

收集 3 个审查结果，合并为统一报告追加到 `.agent/tasks/{task-id}/review.md`：

```markdown
# 并行审查报告 #{n}

## 正确性
[Task 1 结果]

## 架构
[Task 2 结果]

## 安全
[Task 3 结果]

## 结论
- 全部通过 → 更新状态为「已完成」
- 有问题 → 列出待修复项，调用 fastapi-developer 修复后重新审查（最多重试 3 次，超过后询问用户如何处理）
```

每个 agent 按照其定义的流程执行。
