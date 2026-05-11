# RAG 可观测性与质量优化计划

**目标：** 在知识库 RAG 链路已经跑通的基础上，优化日志安全性、检索可观测性、会话链路追踪准确性，以及 PDF 抽取文本质量。

**架构：** 保持当前 `LangGraph -> knowledge_service -> Qdrant -> LLM` 流程不变。只在日志边界、检索结果元数据、knowledge 节点参数传递、上传文本清洗这几个位置做小范围改动，不改变现有聊天接口行为。

**技术栈：** FastAPI、LangGraph、LangChain Qdrant、Qdrant、SQLite、Vue 管理后台、TypeScript API client。

---

## 当前发现

从成功测试日志可以看出：

- RAG 主链路已经正常：意图识别命中 `knowledge_query`，路由进入 knowledge 节点，Qdrant 返回检索结果，LLM 基于知识库内容生成回答。
- 当前日志会打印完整聊天历史、完整 RAG prompt、完整知识库上下文。开发早期方便排查，但后续会带来隐私泄露、知识库内容暴露、日志体积过大等问题。
- knowledge 路径调用 `reply_via_llm()` 时传入了 `conversation_id=None`，所以 LLM 日志显示 `conv=new`，即使真实请求里已经有会话 id。
- Qdrant 日志目前只显示命中数量，不显示 `document_id`、`chunk_index`、`score`，后续知识库变大后不方便判断检索质量。
- PDF 抽取文本里存在中文硬换行，例如 `系\n统`。当前 demo 能正常回答，但长期会影响 embedding 质量和文本可读性。

---

## 任务 1：降低日志敏感信息暴露

**涉及文件：**

- 修改：`agent-service/app/api/chat.py`
- 修改：`agent-service/app/graph/chat_graph.py`
- 修改：`agent-service/app/services/ai_client.py`
- 手工测试：`POST /chat/messages`

**步骤：**

1. 将完整 `history=[...]` 日志替换为消息数量和简短预览。

   建议增加辅助函数：

   ```python
   def _preview_text(value: str, limit: int = 80) -> str:
       compact = " ".join((value or "").split())
       return compact[:limit] + ("..." if len(compact) > limit else "")
   ```

2. 聊天请求日志只保留以下字段：

   ```text
   user_id
   conversation_id
   message_preview
   history_count
   pending_intent
   missing_slots
   ```

3. LLM 调用日志默认不要打印完整 prompt。

   保留：

   ```text
   model
   base_url
   conversation_id
   intent
   message_preview
   message_length
   history_count
   ```

4. 如需保留调试信息，只在 `settings.debug` 下打印短预览，例如限制 500 字符。

5. 手工验证：

   ```powershell
   cd D:\workspace\ai-services\agent-service
   uv run uvicorn app.main:app --reload
   ```

   提问：

   ```text
   客服工作时间是什么时候？
   ```

   期望结果：

   - 日志中不再出现完整知识库正文。
   - 日志中不再出现完整 conversation history 数组。
   - 前端回答保持正确。

6. 建议提交：

   ```bash
   git add agent-service/app/api/chat.py agent-service/app/graph/chat_graph.py agent-service/app/services/ai_client.py
   git commit -m "chore: reduce sensitive RAG logs"
   ```

---

## 任务 2：增强检索可观测性

**涉及文件：**

- 修改：`agent-service/app/services/qdrant_vector_service.py`
- 修改：`agent-service/app/services/knowledge_service.py`
- 可选修改：`agent-service/app/api/admin.py`

**步骤：**

1. 调整 Qdrant 检索逻辑，确保可以拿到相似度分数。如果当前 retriever 路径不能稳定暴露 score，就改用 Qdrant 或 LangChain 支持返回 score 的检索 API。

   目标日志格式：

   ```text
   [qdrant] search query='客服工作时间是什么时候？' hits=3 top=[doc=doc_x chunk=0 score=0.82, doc=doc_x chunk=1 score=0.54]
   ```

2. 确保 `KnowledgeHit.score` 来自 Qdrant 的真实 score，而不是一直为 `0.0`。

3. 保持 `retrieve_knowledge()` 当前返回结构不变：

   ```python
   {
       "id": hit.chunk_id,
       "document_id": hit.document_id,
       "title": hit.title,
       "content": hit.content,
       "score": hit.score,
       "category": hit.category,
       "metadata": hit.metadata,
   }
   ```

4. `/admin/knowledge/search-test` 继续返回结果中的 score，方便后台验证检索质量。

5. 手工验证：

   调用后台 search test：

   ```json
   {
     "query": "七天无理由退货有什么要求？",
     "top_k": 3
   }
   ```

   期望结果：

   - 返回结果包含非零 score。
   - 日志显示 `document_id`、`chunk_index`、`score`。
   - 排名靠前的结果应包含“七天无理由退货原则”。

6. 建议提交：

   ```bash
   git add agent-service/app/services/qdrant_vector_service.py agent-service/app/services/knowledge_service.py agent-service/app/api/admin.py
   git commit -m "feat: add RAG retrieval diagnostics"
   ```

---

## 任务 3：knowledge 调 LLM 时保留会话 id

**涉及文件：**

- 修改：`agent-service/app/graph/chat_graph.py`
- 修改：`agent-service/app/services/knowledge_service.py`
- 手工测试：`POST /chat/messages`

**步骤：**

1. 将 `answer_from_knowledge()` 函数签名从：

   ```python
   async def answer_from_knowledge(query: str) -> tuple[str, list[dict[str, Any]]]:
   ```

   改为：

   ```python
   async def answer_from_knowledge(
       query: str,
       conversation_id: Optional[str] = None,
       history: Optional[list[dict[str, Any]]] = None,
   ) -> tuple[str, list[dict[str, Any]]]:
   ```

2. 在 `knowledge_node()` 中，从 graph state 里取当前 `conversation_id` 和 `history`，传给 `answer_from_knowledge()`。

3. 在 `answer_from_knowledge()` 内部调用 `reply_via_llm()` 时传入：

   ```python
   conversation_id=conversation_id
   ```

4. history 先保守处理。

   推荐第一阶段只修复 `conversation_id`，仍然传：

   ```python
   history=[]
   ```

   原因：单轮知识库问答更稳定，避免历史闲聊污染 RAG prompt。

5. 手工验证：

   提问：

   ```text
   客服工作时间是什么时候？
   ```

   期望日志从：

   ```text
   conv=new
   ```

   变为：

   ```text
   conv=conv_...
   ```

6. 建议提交：

   ```bash
   git add agent-service/app/graph/chat_graph.py agent-service/app/services/knowledge_service.py
   git commit -m "fix: preserve conversation id for knowledge replies"
   ```

---

## 任务 4：清洗 PDF 抽取文本

**涉及文件：**

- 修改：`agent-service/app/api/admin.py`
- 可选新增测试：`agent-service/tests/test_admin_text_extraction.py`

**步骤：**

1. 在 PDF 正文抽取后、切块前增加文本清洗函数：

   ```python
   def _normalize_extracted_text(text: str) -> str:
       lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
       paragraphs: list[str] = []
       current = ""

       for line in lines:
           if not line:
               if current:
                   paragraphs.append(current)
                   current = ""
               continue

           if current and _should_join_lines(current, line):
               current += line
           else:
               if current:
                   paragraphs.append(current)
               current = line

       if current:
           paragraphs.append(current)

       return "\n".join(paragraphs)
   ```

2. 增加保守的中文断行合并判断：

   ```python
   def _should_join_lines(previous: str, current: str) -> bool:
       if not previous or not current:
           return False
       if previous.endswith(("。", "！", "？", "：", "；", ".", "!", "?", ":")):
           return False
       return _is_cjk(previous[-1]) and _is_cjk(current[0])
   ```

3. 增加 `_is_cjk()`：

   ```python
   def _is_cjk(char: str) -> bool:
       return "\u4e00" <= char <= "\u9fff"
   ```

4. 在 `_extract_uploaded_text()` 中对 PDF 抽取结果调用清洗：

   ```python
   raw_text = _extract_pdf_text(content_bytes)
   return _normalize_extracted_text(raw_text)
   ```

5. 用种子 PDF 测试。

   旧文本可能是：

   ```text
   系
   统会先记录问题
   ```

   清洗后期望为：

   ```text
   系统会先记录问题
   ```

6. 重新上传种子 PDF，确认 Qdrant 中仍然是 3 个可读中文 chunk。

7. 建议提交：

   ```bash
   git add agent-service/app/api/admin.py
   git commit -m "fix: normalize extracted PDF knowledge text"
   ```

---

## 任务 5：补充 RAG 冒烟测试清单

**涉及文件：**

- 修改：`docs/plan/2026-05-11-rag-observability-and-quality-plan.md`
- 可选新增：`docs/plan/rag-smoke-test-checklist.md`

**步骤：**

1. 记录每次改完 RAG 后都应该手工验证的问题：

   ```text
   客服工作时间是什么时候？
   七天无理由退货有什么要求？
   退款一般多久到账？
   用户问优惠券为什么不能用，客服应该怎么处理？
   如果知识库里没有答案，客服应该怎么回复？
   ```

2. 记录后端期望信号：

   ```text
   intent=knowledge_query
   route=knowledge
   qdrant hits > 0
   source document title is ecommerce_customer_service_seed_knowledge_2026-05-11
   answer is grounded in retrieved text
   ```

3. 建议提交：

   ```bash
   git add docs/plan/2026-05-11-rag-observability-and-quality-plan.md
   git commit -m "docs: add RAG smoke test checklist"
   ```

---

## 建议实施顺序

1. 任务 1：降低日志敏感信息暴露。
2. 任务 3：knowledge 调 LLM 时保留会话 id。
3. 任务 2：增强检索可观测性和 score 记录。
4. 任务 4：清洗 PDF 抽取文本。
5. 任务 5：维护 RAG 冒烟测试清单。

这个顺序风险较低：先让日志更安全，再修复链路追踪，再增强检索诊断，最后打磨文本质量。

---

## RAG 冒烟测试清单

每次修改 RAG 链路后，应手工验证以下问题：

### 测试问题

| # | 问题 | 期望意图 | 期望来源文档 |
|---|------|----------|-------------|
| 1 | 客服工作时间是什么时候？ | knowledge_query | ecommerce_customer_service_seed_knowledge |
| 2 | 七天无理由退货有什么要求？ | knowledge_query | ecommerce_customer_service_seed_knowledge |
| 3 | 退款一般多久到账？ | knowledge_query | ecommerce_customer_service_seed_knowledge |
| 4 | 用户问优惠券为什么不能用，客服应该怎么处理？ | knowledge_query | ecommerce_customer_service_seed_knowledge |
| 5 | 如果知识库里没有答案，客服应该怎么回复？ | unknown / knowledge_query | 无命中 → LLM 兜底 |

### 后端期望信号

```text
intent=knowledge_query
route=knowledge
qdrant hits > 0（问题 1-4）
source document title 包含 ecommerce_customer_service_seed_knowledge
answer 基于 retrieved text 生成，未编造
日志中不包含完整知识库正文或完整对话历史
conv=conv_...（非 conv=new）
qdrant 日志显示 score > 0（非 0.0）
```

### 验证步骤

1. `POST /chat/messages` 发送测试问题
2. 检查日志：`[classify]` 节点输出 intent=knowledge_query
3. 检查日志：`[route]` 输出 → knowledge
4. 检查日志：`[qdrant]` 显示 hits 数量和 score
5. 检查日志：`[reply_llm_client]` 显示 conv=conv_...（非 new）
6. 检查日志：无完整 prompt 或 history 泄露
7. 验证前端回复内容正确
