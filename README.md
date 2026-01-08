# Claude Code Plugins Monorepo

个人 Claude Code Plugins 仓库，用于管理和维护自定义的开发工作流插件。

## 安装

```bash
# 添加 marketplace
/plugin marketplace add github:qufeng33/agents

# 安装插件
/plugin install fastapi-dev
```

或直接安装：
```bash
/plugin install github:qufeng33/agents/fastapi-dev
```

## 设计理念

- **个人工作流** - 基于个人开发习惯定制，不追求通用性
- **经验沉淀** - 将最佳实践和常用模式固化为可复用的 skill 和 command
- **持续迭代** - 根据实际使用体验不断优化改进

## 项目结构

```
agents/
├── .claude-plugin/
│   └── marketplace.json        # Marketplace 配置
├── plugins/                    # 所有 plugins
│   └── fastapi-dev/            # FastAPI 开发插件
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── agents/             # Agent 定义
│       ├── commands/           # Slash commands
│       ├── hooks/              # 自动化钩子
│       └── skills/             # Skills + references + assets
└── README.md
```

## 插件列表

### fastapi-dev

FastAPI 全流程开发支持。

| 类型 | 内容 |
|------|------|
| Commands | `init`, `design`, `feature`, `review`, `test`, `refactor` |
| Agents | `fastapi-designer`, `fastapi-developer`, `fastapi-tester`, `fastapi-reviewer` |
| Skill | `fastapi-dev`（含 20+ 参考文档） |
| Hooks | Python 文件自动格式化（ruff） |

技术栈：FastAPI ≥0.122.0 / Python ≥3.13 / Pydantic ≥2.10 / SQLAlchemy 2.0 (async) / pytest-asyncio / uv + ruff

## 开发规范

### 添加新 Plugin

```bash
mkdir -p plugins/{plugin-name}/.claude-plugin
mkdir -p plugins/{plugin-name}/{agents,commands,skills}
# 创建 plugin.json
```

然后更新 `.claude-plugin/marketplace.json`：

```json
{
  "plugins": [
    { "name": "fastapi-dev", "path": "plugins/fastapi-dev", "description": "..." },
    { "name": "new-plugin", "path": "plugins/new-plugin", "description": "..." }
  ]
}
```

### 目录规范

```
{plugin-name}/
├── .claude-plugin/
│   └── plugin.json          # 必须
├── agents/                  # Agent 定义
├── commands/                # Slash commands
├── skills/                  # Skills
│   └── {skill-name}/
│       ├── SKILL.md         # 必须
│       ├── references/      # 参考文档
│       └── assets/          # 代码模板
└── README.md
```

### 命名规范

- Plugin: kebab-case (`fastapi-dev`)
- Command: 短名称，通过 `/plugin:command` 调用
- Skill: 功能命名，目录包含 `SKILL.md`
