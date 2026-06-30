# API 服务 — 采购清单（M3）

**里程碑**：M3  
**依赖**：`api/00-foundation`, `api/01-parts-search`  
**预估**：4–5 人天

## 任务列表

### T1: 清单 CRUD `[ ]`

**接口**：
- `GET /api/v1/cart` — 获取当前清单
- `POST /api/v1/cart/items` — 添加配件
- `PUT /api/v1/cart/items/{id}` — 修改数量
- `DELETE /api/v1/cart/items/{id}` — 删除

- 用户标识：`user_id`（登录）或 `X-Session-Id`（匿名）
- 添加时记录：`part_id`, `quantity`, `match_status`, `source`, `need_confirm`

**验收**：可增删改清单项。

---

### T2: 重复配件合并 `[ ]`

- 相同 `part_id` 重复添加时累加 `quantity`，不新建行
- 更新 `updated_at`

**验收**（PRD §8.9-3）：重复加入自动合并数量。

---

### T3: 低置信度标记 `[ ]`

- `confidence < 70%` 或 `match_status != exact` 时设 `need_confirm = 1`
- 发动机/液压/电气/制动类配件强制 `need_confirm`（PRD §10.6）

**验收**（PRD §8.9-4,5）：低置信度与安全类配件有确认标记。

---

### T4: 清单汇总 `[ ]`

**接口**：`GET /api/v1/cart/summary`

- 返回：总件数、合计金额、需人工确认项数量
- 每项含：配件图片、名称、Part Number、OEM、适配设备、单价、小计

**验收**：清单页所需字段完整。

---

### T5: 提交采购意向单 `[ ]`

**接口**：`POST /api/v1/cart/submit`

```json
{
  "contact_name": "",
  "contact_method": "",
  "communication_tool": "whatsapp",
  "note": ""
}
```

- 生成 `inquiry_order` 记录（本期无支付物流）
- 清单项快照保存，防止后续价格变动
- 返回意向单号

**验收**（PRD §8.9-7,8）：可提交采购意向，无支付流程。

---

### T6: 从匹配结果快捷添加 `[ ]`

**接口**：`POST /api/v1/cart/items/from-match`

```json
{
  "part_id": 123,
  "quantity": 1,
  "query_id": 456,
  "match_status": "exact",
  "confidence": 0.95
}
```

- 关联来源查询记录
- 供搜索/图片/批量/人工回填场景复用

**验收**：各匹配场景可一键加入清单。