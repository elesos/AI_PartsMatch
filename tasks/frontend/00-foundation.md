# 用户前台 — 基础设施（M0）

**里程碑**：M0  
**依赖**：`api/00-foundation`  
**预估**：3–4 人天

## 任务列表

### T1: 项目初始化 `[x]`

- 创建前台项目（推荐 Next.js / Nuxt / Vite + React/Vue）
- 目录：`pages/`, `components/`, `services/`, `stores/`, `i18n/`, `styles/`
- 环境变量：`NEXT_PUBLIC_API_BASE_URL`
- 移动端优先响应式布局

**验收**：`npm run dev` 可启动，显示占位首页。

---

### T2: API Client 封装 `[x]`

- 基于 fetch/axios 封装 `apiClient`
- 统一处理 `{ code, message, data }` 响应
- 自动附加 `X-Session-Id`（localStorage 生成 UUID）
- 错误 toast 提示
- 请求/响应 TypeScript 类型（或 JSDoc）

**验收**：可调用 `GET /health` 并展示结果。

---

### T3: 全局布局 `[x]`

- 顶部导航：Logo、系统名称、语言切换占位、采购清单入口
- 底部：人工客服入口、版权信息
- 主内容区路由出口
- 加载态、空状态、错误状态通用组件

**验收**：布局在各页面一致，移动端可用。

---

### T4: 路由规划 `[x]`

| 路由 | 页面 |
|------|------|
| `/` | 配件查询首页 |
| `/search` | 搜索结果 |
| `/parts/:id` | 配件详情 |
| `/upload` | 图片上传 |
| `/upload/result` | 识别结果 |
| `/batch` | Excel 批量 |
| `/batch/result` | 批量结果 |
| `/cart` | 采购清单 |
| `/inquiry` | 人工查询 |
| `/inquiry/success` | 提交成功 |

**验收**：路由可导航，404 页面友好。

---

### T5: 设计规范 `[x]`

- 色彩、字体、间距与工程机械行业风格一致（专业、可信）
- 复用组件：Button, Input, Card, Badge, Modal, Upload
- 置信度颜色：绿(≥90%)、黄(70–89%)、橙(40–69%)、红(<40%)

**验收**：组件库可复用，视觉风格统一。
