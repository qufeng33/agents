---
name: fastapi-design
description: 启动 FastAPI 功能设计流程，产出设计文档 spec.md
argument-hint: <功能描述> | <task-id>
---

# FastAPI 功能设计

使用 `fastapi-designer` agent 进行功能设计，产出设计文档。

---

## 调用方式

使用 **Task 工具** 调用 `fastapi-designer` agent：

```
Task 工具参数：
- subagent_type: "fastapi-designer"
- prompt: "..."
```

---

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

> 调用 agent 时，如果 `.agent/tips.md` 存在，始终传递经验文档路径。

### 步骤 1：解析输入

判断 `$ARGUMENTS` 的类型：

**情况 A：输入为空**
- 询问用户要设计什么功能

**情况 B：输入是已存在的任务 ID**
- 检查 `.agent/tasks/{输入}/` 目录是否存在
- 如果存在，说明是查看/修改已有任务的设计

**情况 C：输入是功能描述**
- 不是已存在的任务 ID，视为新功能描述

### 步骤 2：根据类型执行

#### 情况 B：已有任务

**使用 Task 工具调用 `fastapi-designer` agent**：
```
Task 工具参数：
- subagent_type: "fastapi-designer"
- prompt: |
    ## 文件
    - 设计文档: .agent/tasks/{task-id}/spec.md
    - 经验文档: .agent/tips.md

    ## 任务
    请先阅读现有设计文档，然后根据用户需求查看或修改设计。
    修改后更新设计文档。
```

#### 情况 A/C：新设计

1. 询问用户是否创建任务目录来保存设计

**如果创建任务：**
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

**如果不创建任务：**

**使用 Task 工具调用 `fastapi-designer` agent**：
```
Task 工具参数：
- subagent_type: "fastapi-designer"
- prompt: |
    ## 任务
    功能描述：{用户的功能描述}

    请进行功能设计，直接输出设计内容。
```

每个 agent 按照其定义的流程执行。
