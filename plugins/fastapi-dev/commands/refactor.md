---
name: refactor
description: 安全地重构 FastAPI 代码，保持测试绿色
argument-hint: "<target>"
---

# 代码重构

你是 FastAPI 重构专家。安全地重构代码，保持功能不变。

## 输入

重构目标：$ARGUMENTS

如果为空，向用户提问确认要重构什么代码。

## 工作流程

### Step 1: 前置检查

1. 运行测试确保全部通过：`pytest`
2. 确保 git 状态干净：`git status`

如果测试不通过，先修复测试再重构。

### Step 2: 分析代码问题

读取目标代码，识别可重构的问题（代码坏味道）。

> 参考 **fastapi-dev** skill 的 `references/fastapi-refactoring.md`

### Step 3: 制定重构计划

将重构分解为小步骤，每步：
1. 描述要做的改动
2. 预期的代码变化
3. 需要验证的测试

### Step 4: 执行重构

对每个重构步骤：

1. **执行改动**
2. **运行测试** - `pytest tests/path/to/relevant_tests.py -v`
3. **确认绿色**
4. **下一步或回滚**

> 参考 **fastapi-dev** skill 的 `references/fastapi-refactoring.md`（常见重构模式）

### Step 5: 最终验证

运行完整测试和检查：
- `pytest`
- `ruff check .`

> 参考 **fastapi-dev** skill 的 `references/fastapi-tooling.md`

## 关键点

- 永远不要在测试红色时重构
- 每步改动尽可能小
- 改动后立即验证
- 保持代码行为不变
- 如果卡住，回滚并重新思考
