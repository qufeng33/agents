---
name: fastapi-test
description: 编写 FastAPI 测试用例（pytest-asyncio）
---

# FastAPI 测试

使用 `fastapi-tester` agent 按照测试规范编写测试用例。

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
- 询问用户要测试什么

**情况 B：输入是已存在的任务 ID**
- 检查 `.agent/tasks/{输入}/` 目录是否存在
- 如果存在，说明是为该任务的功能编写测试

**情况 C：输入是测试描述**
- 不是已存在的任务 ID，视为测试目标描述

### 步骤 2：根据类型执行

#### 情况 B：为任务编写测试

调用 `fastapi-tester` agent，传递指令：
```
## 文件
- 设计文档: .agent/tasks/{task-id}/spec.md
- 经验文档: .agent/tips.md

## 任务
为该任务的功能编写测试用例。
完成后更新设计文档（如有测试相关章节）。
```

#### 情况 A/C：独立测试

调用 `fastapi-tester` agent，传递指令：
```
## 文件
- 经验文档: .agent/tips.md

## 任务
测试目标：{$ARGUMENTS 或用户描述}

请按描述编写测试用例。
完成后询问用户是否将测试关联到某个任务。
```

每个 agent 按照其定义的流程执行。
