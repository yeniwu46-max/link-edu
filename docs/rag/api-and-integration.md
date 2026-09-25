# RAG API 与 LINK 业务接入

## 1. HTTP API（均需 JWT）

前缀 **`/api/rag`**。公网开启时，**POST/PATCH/DELETE 文档** 需账号 ∈ `RAG_ADMIN_ACCOUNTS`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/status` | 统计、embedding 信息、`can_manage` |
| GET | `/categories` | 知识分类枚举 |
| POST | `/documents` | multipart `file` + 表单项 |
| GET | `/documents` | 分页列表 |
| GET/PATCH/DELETE | `/documents/<id>` | 详情 / 元数据 / 删除 |
| POST | `/documents/<id>/reindex` | 原文件重切+向量化 |
| GET | `/documents/<id>/chunks` | 切片调试 |
| GET | `/chunks/<chunk_id>` | 单切片 + 文档元数据（评课 kb: 互跳） |
| POST | `/retrieve` | **仅检索**（无 LLM 费用） |
| POST | `/query` | 检索 +  grounded 回答 |
| POST | `/evaluate` | 微格评课（可 `generate:false`） |

### `/query` 示例

请求：

```json
{
  "query": "提问后应该留多长候答时间？",
  "top_k": 5,
  "categories": ["rubric", "theory"],
  "generate": true
}
```

响应 `status`：`answered` | `insufficient_evidence` | `retrieval_only` | `generation_failed`。

`citations[]` 含：`document_title`、`category_label`、`section`、`page_start/end`、`similarity`、`quote`。

### `/evaluate` 示例

- 不传 `indicators` → 默认六维（与 `services/llm/deepseek.py` 一致）。
- `generate: false` → 只返回 `knowledge` 池与各指标 `knowledge_refs`，供外部 prompt 拼接。
- `judge: true` → 在规则校验引用片段后，再调用 LLM-as-a-Judge 复核 `theory_status`（额外模型费用）。

## 2. 程序内调用

```python
from rag.service import get_kb

kb = get_kb()
result = kb.retrieve("导入环节如何激发兴趣", top_k=5, categories=["theory", "case"])
answer = kb.query("...", generate=True)

pool, refs = kb.evidence_for_indicators(
    [{"key": "questioning", "label": "提问质量", "description": "..."}],
    scene="新授",
    top_k=3,
    categories=["rubric"],
)
```

课堂报告引用（BM25 + 向量）：

```python
from services.classroom_reports import gather_report_references

sources = gather_report_references()  # 默认查询串见 RAG_REPORT_QUERY
# source id:  legacy JSON id 或  kb:<chunk_id>
```

向量侧单独封装：

```python
from rag.service import report_reference_sources

refs = report_reference_sources("平均分 分数 提问", top_k=5)
```

## 3. 与现有子系统关系

```text
┌─────────────────────┐     ┌──────────────────────────┐
│ classroom_knowledge │     │ backend/rag (向量库)      │
│ JSON + BM25 (≤5)    │     │ MySQL chunks + Top-K      │
└──────────┬──────────┘     └────────────┬─────────────┘
           │                              │
           └──────────┬───────────────────┘
                      ▼
           report_theory_context()
                      │
                      ▼
           chat(..., { references, theory_by_dimension })
                      │
                      ▼
           validate_report(..., theory_by_dimension)  # 错 kb 引用过滤
```

| 子系统 | 当前 RAG 关系 |
| --- | --- |
| **模拟课堂报告** | 六维 `evidence_for_indicators` → `theory_by_dimension` + 合并 `references`；前端 `/ai-review` 支持 kb 原文与课堂事件互跳 |
| **片段训练 / `/api/rag/evaluate`** | 按指标检索 + 引用规则校验；可选 `judge:true` LLM 复核 |
| **资源库 UI** | 知识库页 `/knowledge` 对接 `/api/rag/*` |
| **evals/** | `rag_retrieval_golden.json` + 规则 `no_score_without_events`、`kb_refs_match_dimension` |

## 4. 费用与供应商

| 能力 | 账本 / 服务名 |
| --- | --- |
| Embedding（远程） | `classroom_budget.reserve('rag_embedding', …)` |
| `/query`、`/evaluate` 生成 | `classroom_providers.chat`（DeepSeek / OpenAI Next） |

本机 `127.0.0.1` Embedding 端点不计入 `rag_embedding` 预留。

## 5. 测试

```bash
cd backend
python -m pytest tests/test_rag.py tests/test_rag_golden.py tests/test_rag_judge.py -q
python -m pytest ../evals/tests/test_rules_grounding.py -q
```

配置错误、权限、引用清洗、FAISS 一致性、课堂 merge 均在测试中覆盖。
