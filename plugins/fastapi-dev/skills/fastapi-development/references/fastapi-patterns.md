# FastAPI 核心模式

核心模式内容已拆分到专门文档，便于按需查阅。

## 分层架构

Router/Service/Repository 三层架构、职责划分、代码示例。

详见 [分层架构](./fastapi-layered-architecture.md)

---

## 依赖注入

Annotated 用法、依赖链、yield 依赖、类依赖、资源存在性验证。

详见 [依赖注入](./fastapi-dependency-injection.md)

---

## 异步与性能

async def vs def 选择、并发请求、CPU 密集型任务处理。

详见 [性能优化](./fastapi-performance.md)

---

## 后台任务

BackgroundTasks、ARQ、Celery、APScheduler 选型与集成。

详见 [后台任务](./fastapi-tasks.md)

---

## 生命周期管理

lifespan、init/setup/close 模式、资源初始化与清理。

详见 [应用生命周期](./fastapi-app-lifecycle.md)

---

## 最佳实践

1. **使用 Annotated 创建类型别名** - 提高可读性和可维护性
2. **单一职责** - 每个依赖只做一件事
3. **利用依赖链** - 组合小依赖构建复杂逻辑
4. **yield 管理资源** - 确保资源正确清理
5. **类型提示** - 始终提供返回类型
6. **优先 async** - 简单逻辑使用 async 依赖，避免线程池开销
7. **lifespan 管理资源** - 启动时初始化，关闭时清理

---

## 代码模板

完整可运行示例见 `assets/` 目录：

| 结构 | 模板目录 | 特点 |
|------|----------|------|
| 简单结构 | `assets/simple-api/services/` | Service 直接操作 AsyncSession |
| 模块化结构 | `assets/modular-api/modules/user/` | 完整三层架构（含 Repository）|
