# PartsMatch API

FastAPI 服务提供统一响应、PostgreSQL 持久化、Redis 缓存、MinIO 文件存储和管理员 JWT 认证。

## Docker 本地启动

```bash
cd api
docker compose up --build -d
docker compose ps
curl http://localhost:8880/health
curl http://localhost:8880/api/v1/health/dependencies
```

端口分配：API `8880`、MinIO API `8890`、MinIO Console `8891`；PostgreSQL 和 Redis 仅在 Compose 内部网络开放。Swagger 位于 `http://localhost:8880/docs`。本地初始管理员为 `admin` / `admin-local-only`，首次登录后应立即修改。

## 配置策略

项目不加载 dotenv 文件。可在线调整的业务参数全部通过受保护的 `sys_configs` 管理接口持久化，并在读取时即时生效：

```http
GET /api/v1/admin/configs
PUT /api/v1/admin/configs/{key}
Authorization: Bearer <admin-token>
```

数据库、Redis、对象存储凭据和 JWT 签名密钥属于应用启动前必须具备的引导参数。本地 Compose 显式传入仅供开发的值；生产部署应将同名小写文件挂载到 `/run/secrets/`（例如 `/run/secrets/database_url` 和 `/run/secrets/jwt_secret`），代码会优先读取 Docker secrets。业务密钥（OCR、AI、通知等）应写入 `sys_configs` 并标记 `is_secret=true`，列表接口会隐藏其值。

## 原生开发与测试

```bash
cd api
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload --port 8880
```

SQLite 是无外部依赖时的安全代码默认值；完整开发和生产环境使用 PostgreSQL。修改模型后应生成并审查 Alembic 迁移。

## 图片 OCR

图片接口要求每个请求携带稳定的 `X-Session-ID`，上传的图片只能由同一会话读取、解析和匹配。默认 `ocr.provider=local_tesseract`，Docker 镜像包含 Tesseract 英文语言包；可通过 `sys_configs` 调整 `ocr.language`、模糊阈值及不超过 10 秒的超时。HEIC 由 `pillow-heif` 解码后交给 Tesseract。若改用 `ocr.provider=http`，endpoint、API key 和 timeout 同样只存于 `sys_configs`。`mock` provider 仅用于自动化测试，不应在生产启用。
