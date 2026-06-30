# PartsMatch 任务文档

工程机械配件智能匹配系统的开发任务拆分，基于 [README.md](../README.md)（PRD V2.0）按**前后端分离**架构组织。

## 目录结构

```
tasks/
├── README.md                 # 本文件：任务索引
├── 00-architecture.md        # 系统架构与职责划分
├── 01-mvp-roadmap.md         # MVP 路线图与里程碑
├── api/                      # API 服务任务
│   ├── 00-foundation.md      # 项目初始化、数据库、基础设施
│   ├── 01-parts-search.md    # 配件搜索与匹配引擎
│   ├── 02-image-ocr.md       # 图片上传与 OCR 识别
│   ├── 03-excel-batch.md     # Excel 批量匹配
│   ├── 04-cart.md            # 采购清单
│   ├── 05-manual-ticket.md   # 人工查询工单
│   ├── 06-admin-crud.md      # 后台数据管理 API
│   ├── 07-ai-matching.md     # AI 候选推荐与日志
│   └── 08-i18n.md            # 多语言支持
├── frontend/                 # 用户前台任务
│   ├── 00-foundation.md      # 项目初始化、布局、路由
│   ├── 01-home-search.md     # 配件查询首页与文本搜索
│   ├── 02-search-results.md  # 匹配结果页与配件详情
│   ├── 03-image-upload.md    # 图片/铭牌上传识别
│   ├── 04-excel-batch.md     # Excel 批量上传
│   ├── 05-cart.md            # 采购清单
│   ├── 06-manual-inquiry.md  # 人工查询入口
│   └── 07-i18n.md            # 多语言切换
└── admin/                    # 后台管理前台任务
    ├── 00-foundation.md      # 后台框架、权限、布局
    ├── 01-parts-management.md
    ├── 02-machine-management.md
    ├── 03-cross-reference.md
    ├── 04-ticket-management.md
    └── 05-query-logs.md
```

## 系统组成

| 模块 | 说明 | 任务目录 |
|------|------|----------|
| **API 服务** | 统一后端，提供 REST API；负责数据、匹配引擎、OCR、AI、文件存储 | `api/` |
| **用户前台** | 配件查询、搜索、上传、采购清单等用户端页面 | `frontend/` |
| **管理后台** | 配件/设备/替代件/工单/日志等运营管理界面 | `admin/` |

## MVP 范围（V1.0）

对应 PRD §17.1，本期必须交付：

1. 配件查询首页 + 文本搜索
2. Part Number / OEM 精确匹配
3. 配件 & 设备 & 替代件后台管理
4. 图片/铭牌上传 + OCR
5. Excel 批量上传
6. AI 候选推荐（含置信度与匹配依据）
7. 人工查询工单
8. 采购清单
9. 多语言（中/英/越）
10. 查询日志与 AI 匹配证据

V1.1+（RAG、序列号范围、发动机关系等）见 [01-mvp-roadmap.md](./01-mvp-roadmap.md)。

## 建议开发顺序

```
Phase 0: API 基础设施 + 前台/后台脚手架
    ↓
Phase 1: 配件/设备/替代件 CRUD（API + Admin）
    ↓
Phase 2: 文本搜索 + 精确匹配（API + 前台）
    ↓
Phase 3: 采购清单 + 配件详情（API + 前台）
    ↓
Phase 4: 图片 OCR + Excel 批量（API + 前台）
    ↓
Phase 5: AI 候选推荐 + 查询日志（API）
    ↓
Phase 6: 人工工单（API + 前台 + Admin）
    ↓
Phase 7: 多语言收尾
```

## 任务状态标记

各任务文档中使用统一状态：

- `[ ]` 待开始
- `[~]` 进行中
- `[x]` 已完成
- `[-]` 本期不做（V1.1+）