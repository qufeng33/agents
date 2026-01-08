---
name: fastapi-review
description: 按照 FastAPI 规范审查代码
---

# FastAPI 代码审查

使用 `fastapi-reviewer` agent 进行代码审查，产出审查报告。

## 任务目录结构
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
- 默认审查 `git diff` 的未提交变更

**情况 B：输入是已存在的任务 ID**
- 检查 `.agent/tasks/{输入}/` 目录是否存在
- 如果存在，说明是审查该任务相关的代码

**情况 C：输入是其他内容**
- 可能是文件路径、目录、commit 范围等
- 交给 agent 理解并处理

### 步骤 2：根据类型执行

#### 情况 B：审查任务相关代码

调用 `fastapi-reviewer` agent，传递指令：
```
## 文件
- 设计文档: .agent/tasks/{task-id}/spec.md
- 审查记录: .agent/tasks/{task-id}/review.md
- 经验文档: .agent/tips.md

## 任务
审查设计文档中「待审核」状态的子任务相关代码。
- 审查结果追加到审查记录文件
- 通过则更新状态为「已完成」，不通过则保持「待审核」
```

#### 情况 A/C：独立审查

调用 `fastapi-reviewer` agent，传递指令：
```
## 文件
- 经验文档: .agent/tips.md

## 任务
审查范围：{$ARGUMENTS 或 "git diff 未提交变更"}

请审查指定范围的代码。
- 如果输入为空，审查 git diff 的未提交变更
- 如果是文件/目录路径，审查对应的代码
- 如果是 commit 范围，审查对应的变更

完成后询问用户是否将审查报告保存到任务目录。
```

每个 agent 按照其定义的流程执行。
