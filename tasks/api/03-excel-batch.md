# API 服务 — Excel 批量匹配（M5）

**里程碑**：M5  
**依赖**：`api/01-parts-search`, `api/04-cart`, `api/05-manual-ticket`  
**预估**：5–6 人天

## 任务列表

### T1: Excel 模板下载 `[ ]`

**接口**：`GET /api/v1/batch/template`

- 生成标准 xlsx 模板，字段（PRD §8.6）：
  - 设备类型、设备品牌、整机型号、设备序列号
  - 发动机型号、配件名称、Part Number、OEM 编号
  - 替代编号、配件系统、所需数量（必填）、备注
- 含表头说明行与示例数据行

**验收**（PRD §16.3-1）：用户可下载可用模板。

---

### T2: Excel 上传与解析 `[ ]`

**接口**：`POST /api/v1/batch/upload`

- 支持 xlsx、xls
- 单次最多 500 行
- 校验规则：
  - 每行至少一个有效识别字段
  - 数量为正整数（必填）
  - 空行自动忽略
- 返回 `batch_id`、总行数、校验错误列表

**验收**（PRD §16.3-2）：合法 Excel 解析成功；非法行返回明确错误。

---

### T3: 逐行匹配 `[ ]`

**接口**：`POST /api/v1/batch/{batch_id}/match`

- 对每行调用搜索引擎（优先 Part Number → OEM → 型号 → 名称）
- 每行返回：
  - `row_index`, `raw_content`
  - `match_status`: exact / multiple / insufficient / not_found / need_manual
  - `candidates`, `confidence`, `match_reason`
  - `suggested_action`: confirm / select / supplement / manual
- 100 行以内 ≤ 30s（PRD §14.1）
- 异步任务：超过 50 行走后台 job + 轮询状态

**验收**（PRD §16.3-3）：逐行返回匹配状态与推荐配件。

---

### T4: 重复行检测 `[ ]`

- 相同 Part Number + 数量行提示合并
- 返回 `duplicate_rows` 列表供用户确认

**验收**：重复配件有合并提示。

---

### T5: 批量加入采购清单 `[ ]`

**接口**：`POST /api/v1/batch/{batch_id}/add-to-cart`

```json
{
  "selections": [
    { "row_index": 1, "part_id": 123, "quantity": 2 }
  ]
}
```

- 仅 `exact` 或用户已确认的行可加入
- 复用清单合并逻辑

**验收**（PRD §16.3-4）：批量确认后可加入采购清单。

---

### T6: 未匹配项转人工 `[ ]`

**接口**：`POST /api/v1/batch/{batch_id}/create-tickets`

- 对 `not_found` / `need_manual` 行一键生成人工工单
- 工单附带 Excel 原始行内容与 batch 文件引用

**验收**（PRD §16.3-5）：未匹配项可批量提交人工查询。