# FastAPI 部署

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
    --access-logfile - \
    --error-logfile -
```

Worker 数量建议：`(2 x CPU核心数) + 1`

---

## Docker 部署

### Dockerfile（uv）

```dockerfile
FROM python:3.13-slim

# 复制 uv 二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 启用字节码编译（提升启动速度）
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# 先复制依赖文件（利用 Docker 缓存）
COPY pyproject.toml uv.lock ./

# 安装依赖（不安装项目本身）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# 复制应用代码
COPY ./app ./app

# 安装项目
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# 创建非 root 用户
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

### 多阶段构建（更小镜像）

```dockerfile
# 构建阶段
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# 运行阶段
FROM python:3.13-slim

WORKDIR /app

# 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制应用代码
COPY --from=builder /app/app ./app

# 设置 PATH
ENV PATH="/app/.venv/bin:$PATH"

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

### .dockerignore

```
.git
.venv
__pycache__
*.pyc
.env
.pytest_cache
.ruff_cache
tests/
*.md
```

### docker-compose.yml

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mydb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d mydb"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## Kubernetes 部署

### deployment.yaml

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
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
```

### service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
spec:
  selector:
    app: fastapi-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

### HPA（自动扩缩容）

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## Nginx 反向代理

```nginx
upstream fastapi {
    server 127.0.0.1:8000;
    keepalive 32;
}

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

    # SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://fastapi;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 健康检查端点
    location /health {
        proxy_pass http://fastapi/health;
        access_log off;
    }
}
```

---

## 健康检查端点

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncDBSession):
    """就绪检查：验证依赖服务"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "database": str(e)},
        )


@router.get("/health/live")
async def liveness():
    """存活检查：应用是否运行"""
    return {"status": "alive"}
```

---

## 环境配置

### 开发环境

```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    debug: bool = False
    database_url: str
    secret_key: str


# .env（开发）
DEBUG=true
DATABASE_URL=postgresql://user:pass@localhost:5432/dev_db
SECRET_KEY=dev-secret-key
```

### 生产环境

```bash
# 环境变量（不使用 .env 文件）
export DEBUG=false
export DATABASE_URL=postgresql://user:pass@db-host:5432/prod_db
export SECRET_KEY=super-secure-production-key
```

### 禁用 OpenAPI 文档

```python
settings = get_settings()

app = FastAPI(
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)
```

---

## 日志配置

生产环境日志要点：

- **JSON 格式** - 便于日志聚合工具（ELK、Loki）分析
- **异步队列** - `enqueue=True` 防止 I/O 阻塞
- **文件轮转** - 按大小/时间轮转，防止磁盘占满
- **禁用 access log** - 使用自定义日志中间件

> 完整的 Loguru 配置、两阶段初始化、InterceptHandler 详见 [日志](./fastapi-logging.md)

---

## 最佳实践

1. **使用 uv** - 极速依赖安装，Docker 构建更快
2. **Gunicorn + Uvicorn** - 生产环境标准配置
3. **非 root 用户** - Docker 容器安全
4. **健康检查** - 就绪和存活分离
5. **资源限制** - Kubernetes 设置 requests/limits
6. **自动扩缩容** - HPA 基于 CPU/内存
7. **HTTPS** - Nginx/负载均衡器终止 SSL
8. **环境变量** - 生产环境不使用 .env 文件
9. **禁用文档** - 生产环境关闭 OpenAPI
10. **结构化日志** - JSON 格式便于分析
11. **优雅关闭** - 处理 SIGTERM 信号
