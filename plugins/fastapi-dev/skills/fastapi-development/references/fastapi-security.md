# FastAPI 安全性

安全相关内容已拆分到专门文档，便于按需查阅。

## 认证

OAuth2 + JWT、API Key、密码策略等。

详见 [认证](./fastapi-authentication.md)

---

## 权限控制

角色权限、OAuth2 Scopes、敏感数据处理等。

详见 [权限控制](./fastapi-permissions.md)

---

## 安全中间件

CORS、HTTPS 重定向、请求限流、安全响应头、Trusted Host 等。

详见 [中间件](./fastapi-middleware.md)

---

## 最佳实践

1. **永远不存储明文密码** - 使用 Argon2（推荐）或 bcrypt
2. **JWT 过期时间要短** - 建议 15-60 分钟
3. **使用 HTTPS** - 生产环境必须
4. **验证所有输入** - Pydantic + 自定义验证
5. **响应模型过滤** - 永远不返回敏感数据
6. **Host Header 验证** - 防止 DNS 重绑定攻击
7. **限流** - 防止暴力破解和 DDoS
8. **安全响应头** - XSS、点击劫持防护
