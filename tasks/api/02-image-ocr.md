# API 服务 — 图片上传与 OCR（M4）

**里程碑**：M4  
**依赖**：`api/00-foundation`, `api/01-parts-search`  
**预估**：6–8 人天

## 任务列表

### T1: 图片上传接口 `[x]`

**接口**：`POST /api/v1/images/upload`

- 支持格式：JPG, PNG, HEIC, WebP
- 单张 ≤ 10MB；单次最多 5 张
- 存储至对象存储，返回 `image_id`, `url`
- MIME 类型校验，拒绝可执行文件

**验收**：前台可上传并获取图片 URL。

---

### T2: OCR 文字识别 `[x]`

**接口**：`POST /api/v1/images/{image_id}/ocr`

- 调用 OCR 服务提取图片中全部文字
- 返回原始文本 + 分行结果
- 超时控制 ≤ 10s（PRD §14.1）
- 模糊/无文字时返回明确错误码

**验收**：清晰铭牌/编号照片可提取文字。

---

### T3: 图片类型判断 `[x]`

- 分类：配件实物 / 整机铭牌 / 发动机铭牌 / 包装标签 / 旧件编号 / 爆炸图
- MVP：规则 + 关键词启发（铭牌常见字段）+ 可选 AI 分类
- 返回 `image_type` 及置信度

**验收**：不同类型图片返回合理分类。

---

### T4: 铭牌字段结构化提取 `[x]`

**接口**：`POST /api/v1/images/{image_id}/parse`

- 从 OCR 文本提取：
  - 设备品牌、整机型号、序列号
  - 发动机型号、出厂年份
  - Part Number、OEM 编号
- 使用正则 + AI 辅助解析
- 返回 `extracted_info` JSON

**验收**（PRD §16.2-1,2）：
- 整机铭牌识别设备型号
- 发动机铭牌识别发动机型号
- 配件编号照片提取 Part Number

---

### T5: 图片识别 → 配件匹配 `[x]`

**接口**：`POST /api/v1/images/match`

```json
{
  "image_ids": ["id1", "id2"],
  "user_hint": "可选补充描述"
}
```

- 流程：上传 → OCR → 字段提取 → 调用搜索引擎
- 多个候选时全部返回，附匹配依据
- 无匹配时 `match_status: not_found`，附人工查询建议

**验收**（PRD §8.3, §7.3）：端到端图片匹配流程可用。

---

### T6: 异常场景处理 `[x]`

| 场景 | 响应 |
|------|------|
| 图片模糊 | `code: IMAGE_BLURRY`，提示重传 |
| 无法识别文字 | `code: OCR_EMPTY`，引导手动填写 |
| 仅识别到型号 | 返回设备信息 + 配件系统选择建议 |
| 多个候选 | `match_status: multiple` |

**验收**（PRD §16.2-4,5）：各异常场景有明确引导。

---

### T7: 查询日志记录 `[x]`

- 每次图片匹配写入 `part_query_log`（`query_type: image`）
- 记录 `raw_input`（图片 ID）、`extracted_info`、`ai_result`
- 关联 `ai_match_evidence`

**验收**：后台可查到图片查询记录。
