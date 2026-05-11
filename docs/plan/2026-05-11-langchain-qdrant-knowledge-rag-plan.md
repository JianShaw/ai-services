# 企业 AI 客服知识库 RAG 方案计划

创建日期：2026-05-11  
适用范围：`agent-service`、`frontend` 管理后台、Qdrant 知识库检索链路  
核心选择：使用 `langchain-qdrant` 作为 Qdrant 接入层

## 1. 背景与目标

当前项目已经具备 AI 客服 Agent 的基础链路：

- `chat_graph.py` 已有 LangGraph 对话编排。
- `knowledge_service.py` 已有知识库文档和 chunk 的本地数据库逻辑。
- `settings.py` 已预留 Qdrant 配置：`qdrant_url`、`qdrant_api_key`、`qdrant_collection_name`、`embedding_model`、`embedding_dimension`。
- `database.py` 已有 `KnowledgeDocument` 和 `KnowledgeChunk` 表。

但当前知识库检索仍是本地 SQL chunk 的关键词打分，`knowledge_node` 也没有进入默认路由。对于工作时间、退货原则、商品内容、企业文化、电商 FAQ 等问题，应该走 Qdrant 向量检索，再由 LLM 基于检索结果生成客服回复。

本计划目标：

1. 使用 `langchain-qdrant` 接入 Qdrant。
2. 将通用知识类问题接入 LangGraph 知识库节点。
3. 建立后台知识库上传、维护、版本管理页面。
4. 支持管理员上传 PDF/Markdown/TXT 文档，自动切片、向量化、入库。
5. 回复中返回知识来源，便于客服质检和知识库维护。

## 2. 知识边界

需要进入 Qdrant 的内容：

- 工作时间、客服在线时间、节假日安排。
- 退货、退款、换货原则。
- 商品介绍、规格、材质、使用方法、保养建议。
- 发货规则、配送范围、物流时效说明。
- 发票规则。
- 保修和售后规则。
- 企业文化、品牌介绍、服务承诺。
- 会员、积分、优惠券等常见规则。
- 其他电商通用 FAQ。

不建议进入 Qdrant 的内容：

- 某个用户的订单状态。
- 某个包裹的实时物流节点。
- 某笔退款的实时进度。
- 用户隐私、地址、联系方式、支付信息。

这些实时私有数据继续走业务工具，例如 `get_order_snapshot`、物流接口、退款接口。

## 3. 技术方案

### 3.1 依赖

在 `agent-service/pyproject.toml` 增加：

```toml
"langchain-qdrant>=0.2.0",
```

继续使用现有 `langchain-openai` 生成 embedding。由于当前项目已使用兼容 OpenAI 协议的模型服务，embedding 也建议通过同一套 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 配置接入。

### 3.2 配置

保留并扩展现有配置：

```python
qdrant_url: str = "http://localhost:6333"
qdrant_api_key: Optional[str] = None
qdrant_collection_name: str = "knowledge_chunks"
embedding_model: str = "text-embedding-ada-002"
embedding_dimension: int = 1536
knowledge_score_threshold: float = 0.35
knowledge_top_k: int = 5
```

### 3.3 Qdrant Collection 设计

Collection：`knowledge_chunks`

Point payload：

```json
{
  "chunk_id": "chunk_xxx",
  "document_id": "doc_xxx",
  "title": "七天无理由退货规则",
  "category": "return_policy",
  "tenant_id": "default",
  "source_type": "pdf",
  "version": "2026-05-11",
  "status": "active",
  "chunk_index": 0,
  "updated_at": "2026-05-11T10:00:00"
}
```

建议 category 枚举：

```text
working_hours
return_policy
refund_policy
exchange_policy
product_info
shipping_policy
invoice_policy
warranty_policy
company_culture
membership_policy
faq
```

### 3.4 数据库职责

本地数据库继续保存：

- `KnowledgeDocument`：文档元信息、状态、版本、来源。
- `KnowledgeChunk`：chunk 原文、metadata、Qdrant point id。

Qdrant 保存：

- chunk embedding。
- 检索 payload。

这样便于后台管理、删除、禁用、重新向量化，也方便在 Qdrant 重建 collection 时从数据库恢复。

## 4. 后端改造计划

### 4.1 新增 `embedding_service.py`

职责：

- 初始化 `OpenAIEmbeddings`。
- 提供 `get_embeddings()`，供 `langchain-qdrant` 使用。
- 统一 embedding 模型、base_url、api_key 配置。

### 4.2 新增 `qdrant_vector_service.py`

职责：

- 初始化 `QdrantVectorStore`。
- 创建或复用 collection。
- 写入 chunk。
- 按 query 检索 top-k chunk。
- 支持按 payload 过滤：`tenant_id`、`status`、`category`、`document_id`。

建议核心函数：

```python
def get_vector_store() -> QdrantVectorStore
async def upsert_chunks(chunks: list[KnowledgeChunkInput]) -> list[str]
async def search_knowledge(query: str, filters: KnowledgeSearchFilter) -> list[KnowledgeHit]
async def delete_document_vectors(document_id: str) -> None
```

### 4.3 改造 `knowledge_service.py`

当前 `retrieve_knowledge()` 使用关键词打分，需要改为：

1. 调用 `qdrant_vector_service.search_knowledge()`。
2. 对低分结果做阈值过滤。
3. 返回标准化 sources。
4. `answer_from_knowledge()` 改为“检索 + LLM 基于 context 生成答案”。

回复原则：

- 只基于知识库资料回答。
- 知识库无命中时不编造。
- 无法确认时建议转人工。
- 回复控制在 3 句话以内。
- 返回 `sources`，供前端和日志展示。

### 4.4 改造意图识别

在 `intent_service.py` 增加：

```python
"knowledge_query"
```

规则关键词：

```text
工作时间、几点上班、几点下班、客服时间、退货规则、退货原则、
七天无理由、换货、商品材质、商品规格、怎么使用、企业文化、
品牌介绍、会员、优惠券、积分、保修、售后政策
```

LLM 分类 prompt 也需要增加 `knowledge_query`。

### 4.5 改造 LangGraph 路由

目标路由：

```text
slot_fill
  -> classify_intent
    -> complaint / transfer_human: human_transfer
    -> check_order / check_logistics / refund / invoice / modify_address: check_slots -> lookup_order -> generate_reply
    -> knowledge_query: knowledge
    -> unknown: generate_reply 或先尝试 knowledge fallback
```

建议先 MVP：

- 明确 `knowledge_query` 直接进入 `knowledge_node`。
- `unknown` 暂时仍走 LLM fallback。

后续增强：

- `unknown` 先轻量检索 Qdrant，如果 score 高则使用知识库回答，否则再 fallback。

## 5. 管理后台改造计划

当前 frontend 已有 `/admin` 页面，但还不是完整知识库管理页面。需要新增“知识库管理 / 维护”模块。

### 5.1 页面入口

路径建议：

```text
/admin/knowledge
```

也可以在现有 `/admin` 中以 Tab 展示：

```text
概览 | 知识库 | 会话质检 | 系统配置
```

MVP 先做 `知识库` Tab。

### 5.2 页面能力

必须具备：

1. 上传文档：PDF、MD、TXT。
2. 填写文档标题、分类、版本、租户。
3. 查看文档列表：标题、分类、状态、版本、chunk 数、更新时间。
4. 启用/停用文档。
5. 删除文档，并同步删除 Qdrant vectors。
6. 重新向量化文档。
7. 查看 chunk 列表和原文片段。
8. 测试检索：输入问题，展示 top-k 命中、score、来源。

### 5.3 后端 API

建议 API：

```text
GET    /api/knowledge/documents
POST   /api/knowledge/documents
GET    /api/knowledge/documents/{document_id}
PATCH  /api/knowledge/documents/{document_id}
DELETE /api/knowledge/documents/{document_id}
POST   /api/knowledge/documents/{document_id}/reindex
GET    /api/knowledge/documents/{document_id}/chunks
POST   /api/knowledge/search-test
```

上传接口需要支持 `multipart/form-data`：

```text
file
title
category
version
tenant_id
source_type
```

## 6. 文档上传与切片

MVP 支持：

- TXT：直接按段落切片。
- Markdown：按标题和段落切片。
- PDF：先抽文本，再按标题/段落切片。

切片建议：

- chunk size：500-800 中文字符。
- overlap：80-120 中文字符。
- 保留标题路径到 metadata，例如 `section_title`。

每个 chunk 入库流程：

```text
上传文档
  -> 解析文本
  -> 清洗内容
  -> 切片
  -> 保存 KnowledgeDocument
  -> 保存 KnowledgeChunk
  -> langchain-qdrant 写入 Qdrant
  -> 回填 embedding_id / point_id
```

## 7. 可上传种子知识库

已准备一份种子知识库 PDF，建议作为第一批测试知识上传：

```text
docs/plan/ecommerce_customer_service_seed_knowledge_2026-05-11.pdf
```

同时保留 Markdown 原文，便于后续调整内容：

```text
data/knowledge/ecommerce_customer_service_seed_knowledge_2026-05-11.md
```

建议上传参数：

```text
title: 电商客服通用知识库种子文档
category: faq
version: 2026-05-11
tenant_id: default
source_type: pdf
```

## 8. 测试用例

知识库命中问题：

```text
你们客服几点上班？
退货需要满足什么条件？
这个商品怎么保养？
你们公司是什么文化？
发票可以开企业抬头吗？
```

业务工具问题：

```text
帮我查一下订单 ORD-20260508-0001
这个订单物流到哪了？
我的退款到账了吗？
```

边界问题：

```text
我没有订单号能退货吗？
你直接告诉我退款进度。
我要投诉你们。
```

预期：

- 通用规则类问题走 Qdrant。
- 订单实时数据走业务工具。
- 知识库无命中不编造。
- 投诉和高风险问题转人工。

## 9. 实施顺序

1. 增加 `langchain-qdrant` 依赖。
2. 新增 embedding 和 qdrant vector service。
3. 改造知识库导入和检索逻辑。
4. 扩展意图识别和 LangGraph 路由。
5. 增加知识库管理 API。
6. 增加 admin 知识库管理页面。
7. 上传种子 PDF 验证检索。
8. 增加 e2e 测试：知识库问答、无命中、业务工具分流。

## 10. 验收标准

- 管理员可以在 admin 页面上传 PDF 知识库文档。
- 文档上传后能看到 chunk 数、状态和版本。
- Qdrant collection 中能看到对应向量数据。
- 用户询问工作时间、退货原则、商品内容、企业文化时，系统走 `knowledge` 路由。
- AI 回复引用知识库 sources。
- 知识库无命中时不编造，提示转人工或补充说明。
- 订单/物流/退款实时查询仍走业务工具，不被知识库回答覆盖。
