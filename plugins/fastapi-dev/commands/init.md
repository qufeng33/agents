---
name: init
description: 初始化 FastAPI 项目结构
---

# 初始化 FastAPI 项目

根据开发规范初始化项目结构。

## 项目结构类型

- **简单结构** - 适合小项目/原型/单人开发
- **模块化结构** - 适合团队开发/中大型项目

---

用户输入：

$ARGUMENTS

---

## 执行指南

### 步骤 1：解析输入

- 如果输入为空，询问项目名称和结构类型
- 如果输入包含项目信息，解析项目名称

### 步骤 2：初始化

1. 加载 `fastapi-dev` skill 获取模板路径（`assets/simple-api/` 或 `assets/modular-api/`）
2. 确认项目类型（简单/模块化）
3. 确认项目路径
4. 创建项目目录结构：
   ```
   {project}/
   ├── app/           # 从 assets/{simple|modular}-api/ 复制
   ├── tests/         # 从 assets/tests/ 复制
   ├── pyproject.toml # 从 assets/pyproject.toml.template 生成
   ├── README.md      # 从 assets/README.md.template 生成
   ├── .env.example   # 从 assets/.env.example 生成
   └── .gitignore     # 从 assets/.gitignore.template 生成
   ```
5. 处理模板文件：
   - 替换 `{{PROJECT_NAME}}` 为实际项目名
   - 将 `.template` 后缀的文件去掉后缀（如 `conftest.py.template` → `conftest.py`）

### 步骤 3：验证

1. 进入项目目录：`cd {project}`
2. 复制配置：`cp .env.example .env`
3. 安装依赖：`uv sync`
4. 启动应用：`uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. 确认启动成功（显示 "Uvicorn running on..."）
6. 关闭应用，输出项目结构和下一步说明

> 如果启动失败，修复问题后重新验证，直到成功为止。

（不涉及任务追踪系统）
