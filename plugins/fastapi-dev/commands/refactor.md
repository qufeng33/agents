---
name: fastapi-refactor
description: 按照 FastAPI 最佳实践重构代码
---

# FastAPI 代码重构

使用 `fastapi-developer` agent 按照开发规范重构代码。

## 任务目录结构
```
.agent/
├── tips.md              # 经验文档（全局共享）
└── tasks/
    └── {feature}-{seq}/
        └── spec.md      # 设计文档 + 任务状态
```

---

用户输入：

$ARGUMENTS

---

## 执行指南

### 步骤 1：解析输入

判断 `$ARGUMENTS` 的类型：

**情况 A：输入为空**
- 询问用户要重构什么

**情况 B：输入是已存在的任务 ID**
- 检查 `.agent/tasks/{输入}/` 目录是否存在
- 如果存在，说明是在该任务上下文中进行重构

**情况 C：输入是重构描述**
- 不是已存在的任务 ID，视为重构目标描述

### 步骤 2：根据类型执行

#### 情况 B：任务上下文中重构

调用 `fastapi-developer` agent，传递指令：
```
## 文件
- 设计文档: .agent/tasks/{task-id}/spec.md
- 经验文档: .agent/tips.md

## 任务
在该任务上下文中进行重构。
完成后更新设计文档相关内容（如需）。
```

#### 情况 A/C：独立重构

调用 `fastapi-developer` agent，传递指令：
```
## 文件
- 经验文档: .agent/tips.md

## 任务
重构目标：{$ARGUMENTS 或用户描述}

请按描述进行重构。
完成后询问用户是否将重构关联到某个任务。
```

每个 agent 按照其定义的流程执行。
