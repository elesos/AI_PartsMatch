# API 服务 — 人工查询工单（M7）

**里程碑**：M7  
**依赖**：`api/00-foundation`, `api/04-cart`  
**预估**：5–6 人天

## 任务列表

### T1: 用户提交工单 `[ ]`

**接口**：`POST /api/v1/tickets`

```json
{
  "contact_name": "",
  "country": "",
  "contact_info": "",
  "communication_tool": "whatsapp|wechat|zalo|telegram",
  "machine_type": "",
  "machine_brand": "",
  "machine_model": "",
  "serial_no": "",
  "engine_model": "",
  "part_description": "",
  "quantity": 1,
  "image_ids": [],
  "excel_batch_id": "",
  "note": "",
  "ai_preliminary_result": {}
}
```

- 生成工单号，初始状态 `pending`
- 附件关联图片/Excel
- 联系方式入库完整存储，对外接口脱敏

**验收**（PRD §8.10）：用户可提交含附件的工单。

---

### T2: 工单状态流转 `[ ]`

状态机（PRD §11.9）：

```
pending → processing → need_info → matched → in_cart → closed
```

**接口**（用户端）：
- `GET /api/v1/tickets/{id}` — 查看自己的工单状态
- `POST /api/v1/tickets/{id}/supplement` — 用户补充信息

**接口**（管理端）：
- `PUT /api/v1/admin/tickets/{id}/status`
- `POST /api/v1/admin/tickets/{id}/assign` — 分配处理人

**验收**：状态按规则流转，非法跳转拒绝。

---

### T3: 客服回填配件 `[ ]`

**接口**：`POST /api/v1/admin/tickets/{id}/resolve`

```json
{
  "resolved_part_ids": [123, 456],
  "match_evidence": "人工确认依据",
  "internal_note": "",
  "quantities": { "123": 2 }
}
```

- 更新工单 `final_parts`
- 状态 → `matched`
- 生成知识库候选记录（待审核，不直接入库 — PRD §10.6）

**验收**（PRD §16.4-7）：客服可回填确认配件。

---

### T4: 用户将人工结果加入清单 `[ ]`

**接口**：`POST /api/v1/tickets/{id}/add-to-cart`

- 仅 `matched` 状态可用
- 调用清单服务，来源标记 `manual`

**验收**（PRD §7.4-9）：人工确认结果可加入采购清单。

---

### T5: 工单列表与筛选（管理端）`[ ]`

**接口**：`GET /api/v1/admin/tickets`

- 筛选：状态、处理人、日期范围、设备品牌
- 分页、排序（待处理优先）
- 展示 AI 初步结果、附件预览

**验收**：客服可高效浏览待处理工单。

---

### T6: 联系方式脱敏 `[ ]`

- 对外 API：`138****1234`
- 管理端完整展示（需 `operator` 权限）
- 日志中不打印完整联系方式

**验收**（PRD §14.3-5）：脱敏规则正确。