# 知识库存储模型说明

## 定位

知识库目前同时使用 SQLite 和 Qdrant：

- SQLite 存“可管理的原始知识和元信息”
- Qdrant 存“可检索的向量索引和检索元信息”

一句话：

```text
SQLite 是知识库事实源，Qdrant 是为了语义检索生成的索引副本。
```

Qdrant 中的 metadata 应该从 SQLite 的 document 和 chunk metadata 同步生成，不能成为另一套独立事实。

---

## SQLite 存储结构

### `knowledge_documents`

一篇 Markdown、PDF、TXT 文档对应一条 document 记录。

当前核心字段：

```text
id
title
source_type
category
tenant_id
status
version
created_at
updated_at
```

字段含义：

```text
id           文档 id
title        文档标题
source_type  pdf / markdown / txt / faq 等来源类型
category     文档默认分类
tenant_id    租户 id
status       indexing / active / index_failed / disabled 等状态
version      文档版本
created_at   创建时间
updated_at   更新时间
```

未来可扩展字段：

```text
effective_from
effective_to
priority
```

### `knowledge_chunks`

一篇文档会被拆成多个 chunk，每个 chunk 对应一条记录。

当前核心字段：

```text
id
document_id
content
embedding_id
meta_data
created_at
```

字段含义：

```text
id            chunk id
document_id   所属文档 id
content       chunk 原文
embedding_id  Qdrant point id
meta_data     chunk 级 JSON 元信息
created_at    创建时间
```

未来 chunk 级分类的 `meta_data` 应该包含：

```json
{
  "chunk_index": 2,
  "section_title": "退款到账说明",
  "category": "refund_policy",
  "source_heading_level": 2
}
```

示例：

```text
knowledge_documents
doc_001 | 电商客服知识库 | markdown | faq | default | active | 2026-05-11
```

```text
knowledge_chunks
chunk_001 | doc_001 | 工作时间正文... | point_001 | {"chunk_index":0,"section_title":"工作时间","category":"working_hours"}
chunk_002 | doc_001 | 七天无理由正文... | point_002 | {"chunk_index":1,"section_title":"七天无理由退货","category":"return_policy"}
chunk_003 | doc_001 | 退款到账正文... | point_003 | {"chunk_index":2,"section_title":"退款到账说明","category":"refund_policy"}
```

---

## Qdrant 存储结构

Qdrant 不是传统表结构，而是 collection + points。

当前 collection：

```text
knowledge_chunks
vector size = 1024
distance = Cosine
```

每个 chunk 对应一个 Qdrant point。

示例 point：

```json
{
  "id": "point_001",
  "vector": [0.012, -0.034],
  "payload": {
    "page_content": "工作时间正文...",
    "metadata": {
      "chunk_id": "chunk_001",
      "document_id": "doc_001",
      "title": "电商客服知识库",
      "category": "working_hours",
      "tenant_id": "default",
      "source_type": "markdown",
      "version": "2026-05-11",
      "status": "active",
      "chunk_index": 0,
      "section_title": "工作时间"
    }
  }
}
```

另一个 point：

```json
{
  "id": "point_002",
  "vector": [0.045, 0.018],
  "payload": {
    "page_content": "七天无理由正文...",
    "metadata": {
      "chunk_id": "chunk_002",
      "document_id": "doc_001",
      "title": "电商客服知识库",
      "category": "return_policy",
      "tenant_id": "default",
      "source_type": "markdown",
      "version": "2026-05-11",
      "status": "active",
      "chunk_index": 1,
      "section_title": "七天无理由退货"
    }
  }
}
```

---

## 两边职责

SQLite 负责：

```text
后台展示
文档管理
chunk 原文查看
状态管理
重新索引
删除文档
版本治理
```

Qdrant 负责：

```text
语义检索
按 tenant/category/status 过滤
返回最相关 chunk
给 LLM 提供上下文
```

---

## 关键对应关系

以下字段必须保持一致：

```text
SQLite knowledge_chunks.id
= Qdrant metadata.chunk_id

SQLite knowledge_documents.id
= Qdrant metadata.document_id

SQLite knowledge_chunks.meta_data.category
= Qdrant metadata.category

SQLite knowledge_documents.status
= Qdrant metadata.status
```

如果未来增加版本治理，也需要保持：

```text
SQLite knowledge_documents.version
= Qdrant metadata.version

SQLite knowledge_documents.effective_from
= Qdrant metadata.effective_from_ts

SQLite knowledge_documents.effective_to
= Qdrant metadata.effective_to_ts

SQLite knowledge_documents.priority
= Qdrant metadata.priority
```

---

## 设计原则

1. SQLite 是事实源。
2. Qdrant 是索引副本。
3. 重建索引时，应从 SQLite 重新生成 Qdrant point。
4. 后台展示和运营判断应优先依赖 SQLite。
5. 检索过滤依赖 Qdrant metadata，但这些 metadata 必须由 SQLite 同步而来。
6. 不能只在 Qdrant 中维护业务字段，否则重建索引会丢失。
7. 不能只在 SQLite 中维护检索字段，否则 Qdrant 无法按业务条件过滤。

