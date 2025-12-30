# FastAPI 部署

## 设计原则
- 生产环境可复现
- 进程模型与负载匹配
- 健康检查可用
- 配置与密钥分离
- 日志结构化且可追踪

## 最佳实践
1. Gunicorn + Uvicorn Workers
2. Docker 使用非 root 用户
3. 健康检查分离就绪/存活
4. 生产环境禁用文档
5. 结构化日志输出

## 目录
- `生产服务器`
- `Docker 部署`
- `Kubernetes 部署`
- `Nginx 反向代理`
- `健康检查与环境配置`
- `日志配置`

---

## 生产服务器

### Uvicorn（单进程）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Gunicorn + Uvicorn Workers（推荐）

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5 \
  --no-access-log
```

> Worker 数量建议：`(2 x CPU 核心数) + 1`。

---

## Docker 部署

### Dockerfile（uv）

```dockerfile
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY ./app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

> 多阶段构建与 docker-compose 可按需扩展。

---

## Kubernetes 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-app
  template:
    metadata:
      labels:
        app: fastapi-app
    spec:
      containers:
        - name: api
          image: myregistry/fastapi-app:latest
          ports:
            - containerPort: 8000
          env:
            - name: DB_HOST
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: db-host
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
```

> Service/HPA/资源限制按需配置。

---

## Nginx 反向代理

```nginx
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/ssl/certs/api.example.com.crt;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 健康检查与环境配置

- 健康检查端点建议 `/health`
- 生产环境使用环境变量而非 `.env`
- 生产环境关闭 `docs/redoc/openapi`

---

## 日志配置

生产日志建议：
- JSON 格式
- 异步队列
- 禁用 access log

> 详见 [日志](./fastapi-logging.md)。
