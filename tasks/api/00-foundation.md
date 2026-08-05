# API 服务 — 基础设施（M0）

**里程碑**：M0  
**依赖**：无  
**预估**：3–5 人天

## 任务列表

### T1: 项目初始化 `[x]`

- 创建 API 服务项目（推荐 FastAPI / NestJS）
- 目录结构：`routers/`, `services/`, `models/`, `schemas/`, `core/`
- 配置管理：动态业务配置存入 `sys_configs`；引导配置使用容器参数或 Docker secrets
- 统一响应格式：`{ "code": 0, "message": "ok", "data": {} }`
- 全局异常处理与请求日志中间件

**验收**：`GET /health` 返回 200；`GET /api/v1/health` 返回服务版本号。

---

### T2: 数据库连接与迁移 `[x]`

- 接入 PostgreSQL（或 MySQL）
- 集成 ORM（SQLAlchemy / Prisma / TypeORM）
- 配置 Alembic / Prisma Migrate 迁移工具
- 创建 MVP 核心表（见 `00-architecture.md` §7）：
  - `part`, `part_image`, `machine`, `machine_part_relation`
  - `part_cross_reference`, `part_alias`
  - `cart_item`, `manual_ticket`
  - `part_query_log`, `ai_match_evidence`

**验收**：`alembic upgrade head` 成功；所有表可查询。

---

### T3: Redis 缓存接入 `[x]`

- 连接 Redis
- 封装缓存工具类（get/set/delete，TTL 支持）
- 为 Part Number / OEM 索引预留 key 规范：`part:no:{part_no}`

**验收**：健康检查接口可验证 Redis 连通性。

---

### T4: 对象存储接入 `[x]`

- 接入 MinIO / S3 兼容存储
- 封装上传服务：支持图片（jpg/png/webp/heic）、Excel（xlsx/xls）
- 文件大小限制：图片 ≤ 10MB，Excel ≤ 5MB
- 返回 `file_id`, `url`, `mime_type`, `size`

**验收**：测试上传图片与 Excel 文件，可通过 URL 访问。

---

### T5: 认证与权限骨架 `[x]`

- 后台管理员 JWT 登录（`/api/v1/admin/auth/login`）
- 角色：`admin`, `operator`（客服）
- 中间件：保护 `/api/v1/admin/*` 路由
- 用户端：匿名 `session_id`（Header `X-Session-Id`）用于采购清单

**验收**：未登录访问 admin 接口返回 401；登录后返回 token。

---

### T6: Docker Compose 开发环境 `[x]`

```yaml
services:
  api, db, redis, minio
```

- 一键 `docker compose up` 启动全套环境
- README 补充本地开发说明

**验收**：新成员按文档 15 分钟内可启动 API + 依赖服务。

---

### T7: API 文档 `[x]`

- 集成 OpenAPI / Swagger UI（`/docs`）
- 为已实现的接口补充 request/response schema

**验收**：Swagger 可浏览并试调 `/health` 接口。
