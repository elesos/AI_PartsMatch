# API 服务 — 配件搜索与匹配（M2）

**里程碑**：M2  
**依赖**：`api/00-foundation`, `api/06-admin-crud`（有种子数据）  
**预估**：8–10 人天

## 任务列表

### T1: Part Number 精确匹配 `[ ]`

**接口**：`GET /api/v1/search?type=part_no&q={value}`

- 输入标准化：去空格、大小写统一
- 精确命中 `part.part_no`，返回唯一配件
- 响应含：配件基本信息、图片、适配设备、置信度 100%、匹配原因
- Redis 缓存热门编号

**验收**（PRD §16.1-1）：准确 Part Number 返回唯一结果，响应 ≤ 1s。

---

### T2: OEM 编号匹配 `[ ]`

**接口**：`GET /api/v1/search?type=oem&q={value}`

- 匹配 `part.oem_code`
- 关联 `part_cross_reference` 返回替代件列表
- 区分关系类型：OEM / aftermarket / replacement / compatible
- 标注替代件可靠度

**验收**（PRD §16.1-2）：OEM 查询返回原厂件 + 可替代件。

---

### T3: 设备型号匹配 `[ ]`

**接口**：`GET /api/v1/search?type=machine&q={brand}&model={model}`

- 查询 `machine` 表
- 通过 `machine_part_relation` 获取关联配件
- 按配件系统（发动机/液压/电气等）分组返回
- 无精确配件时返回分类导航

**验收**（PRD §16.1-3）：输入整机型号展示相关配件分类。

---

### T4: 发动机型号匹配 `[ ]`

**接口**：`GET /api/v1/search?type=engine&q={engine_model}`

- MVP：通过 `machine.engine_model` 关联 + 配件分类筛选
- 返回发动机系统常用保养件
- 标注是否需要序列号进一步确认

**验收**（PRD §16.1-4）：发动机型号可推荐相关配件。

---

### T5: 配件名称与别名搜索 `[ ]`

**接口**：`GET /api/v1/search?type=text&q={keyword}&lang={zh|en|vi}`

- 搜索 `part.name_*` + `part_alias.alias`
- 支持模糊匹配（ILIKE / 全文索引）
- 返回候选列表，按相关度排序

**验收**：中文/英文配件名可搜到对应配件。

---

### T6: 综合搜索入口 `[ ]`

**接口**：`POST /api/v1/search`

```json
{
  "query": "用户输入",
  "lang": "zh",
  "context": { "machine_brand": "", "machine_model": "" }
}
```

- 自动识别输入类型：编号 / OEM / 型号 / 自然语言
- 编号类走 T1–T2；型号类走 T3–T4；自然语言走 AI 模块（M6）
- 统一返回结构：

```json
{
  "query_type": "part_no|oem|machine|engine|natural",
  "extracted_info": {},
  "match_status": "exact|high|multiple|insufficient|not_found",
  "candidates": [{ "part": {}, "confidence": 0.95, "reason": "", "evidence": [] }],
  "suggestions": ["补充品牌", "上传铭牌"]
}
```

**验收**（PRD §8.2）：单接口支持多种输入；内容过少时返回补充建议。

---

### T7: 配件详情 `[ ]`

**接口**：`GET /api/v1/parts/{id}`

- 返回完整配件信息（PRD §8.8 全部字段）
- 含替代件列表、适配设备、适配发动机、图片列表
- 响应 ≤ 2s

**验收**：详情页所需字段完整返回。

---

### T8: 分类与导航数据 `[ ]`

**接口**：
- `GET /api/v1/categories` — 一级分类（PRD §9.1）
- `GET /api/v1/machines/hot` — 热门设备型号
- `GET /api/v1/parts/hot` — 热门配件

**验收**：首页分类入口、热门型号可渲染。

---

### T9: 搜索索引优化 `[ ]`

- `part_no`, `oem_code` 建唯一/普通索引
- `part_alias.alias` 建索引
- `machine.brand + model` 联合索引
- 考虑 PostgreSQL `pg_trgm` 模糊搜索

**验收**：文本查询 P95 ≤ 3s（PRD §14.1）。