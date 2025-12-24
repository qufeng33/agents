# Claude Code Plugins Monorepo

> 多 Plugin 项目仓库，用于团队开发的 Claude Code 插件集合。

## 项目结构

```
agents/
├── CLAUDE.md                           # 本文件
├── plugins/                            # 所有 plugins
│   └── fastapi-dev/                    # FastAPI 开发 Plugin
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── agents/
│       │   └── fastapi-pro.md
│       ├── commands/
│       │   ├── init.md                 # /fastapi-dev:init
│       │   ├── feature.md              # /fastapi-dev:feature
│       │   ├── review.md               # /fastapi-dev:review
│       │   ├── test.md                 # /fastapi-dev:test
│       │   └── refactor.md             # /fastapi-dev:refactor
│       └── skills/
│           ├── fastapi-architecture/
│           │   └── SKILL.md
│           └── fastapi-development/
│               ├── SKILL.md
│               └── references/         # 详细参考文档
│                   ├── fastapi-project-structure.md
│                   ├── fastapi-database.md
│                   ├── fastapi-async.md
│                   └── ...
└── shared/                             # 跨 plugin 共享资源（可选）
```

---

## Plugins

### fastapi-dev

FastAPI 开发全流程支持。

**Commands:**
| 命令 | 用途 |
|------|------|
| `/fastapi-dev:init` | 交互式项目初始化 |
| `/fastapi-dev:feature` | 功能开发 (TDD/快速原型) |
| `/fastapi-dev:review` | 代码审查 |
| `/fastapi-dev:test` | 测试生成 |
| `/fastapi-dev:refactor` | 代码重构 |

**Skills:**
- `fastapi-architecture` - 架构设计、需求分析、技术选型
- `fastapi-development` - 代码实现最佳实践

**Agent:**
- `fastapi-pro` - FastAPI 专家 (Opus)

---

## 开发规范

### 添加新 Plugin

```bash
mkdir -p plugins/{plugin-name}/.claude-plugin
mkdir -p plugins/{plugin-name}/{agents,commands,skills}
```

### Plugin 结构规范

```
{plugin-name}/
├── .claude-plugin/
│   └── plugin.json          # 必须：manifest 文件
├── agents/                  # 可选：Agent 定义
├── commands/                # 可选：Slash commands
├── skills/                  # 可选：Skills
│   └── {skill-name}/
│       └── SKILL.md
└── hooks/                   # 可选：Event hooks
    └── hooks.json
```

### 命名规范

- Plugin name: kebab-case (`fastapi-dev`, `code-review`)
- Command: 短名称，通过 `plugin:command` 格式调用
- Skill: 按功能命名的目录，包含 `SKILL.md`

---

## 技术栈 (fastapi-dev)

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI >=0.120.0, Pydantic v2 |
| 数据库 | PostgreSQL, SQLAlchemy 2.0 (async), Alembic |
| 测试 | pytest, pytest-asyncio, httpx |
| 工具 | uv, ruff, ty |

---

## 待改进项

1. **fastapi-architecture Skill**
   - 统一使用祈使句式
   - 添加设计文档模板

2. **fastapi-development Skill**
   - ~~添加 `references/` 目录~~ ✅ 已完成
   - 拆分代码模板到 `assets/`（simple-api/、modular-api/）
