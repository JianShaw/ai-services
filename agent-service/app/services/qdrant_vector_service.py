from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config.settings import settings
from app.services.embedding_service import get_embeddings

log = logging.getLogger(__name__)


@dataclass
class KnowledgeChunkInput:
    chunk_id: str
    document_id: str
    content: str
    title: str = ""
    category: str = "faq"
    tenant_id: str = "default"
    source_type: str = "txt"
    version: str = ""
    chunk_index: int = 0


@dataclass
class KnowledgeSearchFilter:
    tenant_id: Optional[str] = None
    category: Optional[str] = None
    document_id: Optional[str] = None


@dataclass
class KnowledgeHit:
    chunk_id: str
    document_id: str
    content: str
    score: float
    title: str = ""
    category: str = ""
    metadata: dict = field(default_factory=dict)


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=30,
    )


def _create_collection(client: QdrantClient, collection_name: str) -> None:
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=settings.embedding_dimension,
            distance=models.Distance.COSINE,
        ),
    )


def _get_dense_vector_size(collection_info) -> Optional[int]:
    vectors_config = collection_info.config.params.vectors
    if isinstance(vectors_config, models.VectorParams):
        return vectors_config.size
    if isinstance(vectors_config, dict):
        default_vector = vectors_config.get("")
        if isinstance(default_vector, models.VectorParams):
            return default_vector.size
    return None


def _ensure_collection(client: QdrantClient) -> None:
    collection_name = settings.qdrant_collection_name
    try:
        collection_info = client.get_collection(collection_name)
    except (UnexpectedResponse, Exception):
        log.info("[qdrant] creating collection: %s", collection_name)
        _create_collection(client, collection_name)
        return

    vector_size = _get_dense_vector_size(collection_info)
    if vector_size and vector_size != settings.embedding_dimension:
        log.warning(
            "[qdrant] recreating collection %s: vector size %s != configured embedding dimension %s",
            collection_name,
            vector_size,
            settings.embedding_dimension,
        )
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
        )


def get_vector_store() -> QdrantVectorStore:
    client = _get_qdrant_client()
    _ensure_collection(client)
    embeddings = get_embeddings()
    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
        embedding=embeddings,
        validate_collection_config=False,
    )


async def upsert_chunks(chunks: list[KnowledgeChunkInput]) -> list[str]:
    """将文本块写入 Qdrant：先通过 embedding 模型将原文转为向量，再连同 metadata 一起存入集合。"""
    store = get_vector_store()
    texts = [c.content for c in chunks]
    # metadata 随向量一起存储，后续搜索时可用于 Filter 过滤
    metadatas = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "title": c.title,
            "category": c.category,
            "tenant_id": c.tenant_id,
            "source_type": c.source_type,
            "version": c.version,
            "status": "active",
            "chunk_index": c.chunk_index,
        }
        for c in chunks
    ]
    ids = await store.aadd_texts(texts=texts, metadatas=metadatas)
    log.info("[qdrant] upserted %d chunks, ids=%s", len(ids), ids[:3])
    return ids


async def search_knowledge(
    query: str,
    filters: Optional[KnowledgeSearchFilter] = None,
    top_k: Optional[int] = None,
) -> list[KnowledgeHit]:
    """向量相似度搜索：将 query 转为 embedding，在 Qdrant 中找最近的 top_k 个文本块。

    支持通过 filters 按 tenant_id / category / document_id 做 metadata 预过滤，
    返回结果会剔除低于 knowledge_score_threshold 的低质量命中。
    """
    store = get_vector_store()
    k = top_k or settings.knowledge_top_k

    # 构建 Qdrant Filter：在向量搜索前按 metadata 字段精确匹配过滤
    qdrant_filters = None
    if filters:
        conditions = []
        if filters.tenant_id:
            conditions.append(
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=filters.tenant_id))
            )
        if filters.category:
            conditions.append(
                models.FieldCondition(key="category", match=models.MatchValue(value=filters.category))
            )
        if filters.document_id:
            conditions.append(
                models.FieldCondition(key="document_id", match=models.MatchValue(value=filters.document_id))
            )
        if conditions:
            qdrant_filters = models.Filter(must=conditions)

    # similarity_search_with_score 返回 (Document, score) 元组列表
    docs_with_scores = await store.asimilarity_search_with_score(
        query,
        k=k,
        filter=qdrant_filters,
    )

    hits: list[KnowledgeHit] = []
    for doc, score in docs_with_scores:
        meta = doc.metadata or {}
        hit_score = float(score)
        # 过滤掉低于阈值的结果
        if hit_score < settings.knowledge_score_threshold:
            continue
        hits.append(
            KnowledgeHit(
                chunk_id=meta.get("chunk_id", ""),
                document_id=meta.get("document_id", ""),
                content=doc.page_content,
                score=hit_score,
                title=meta.get("title", ""),
                category=meta.get("category", ""),
                metadata=meta,
            )
        )

    top_summary = ", ".join(
        f"doc={h.document_id[:12]} chunk={h.metadata.get('chunk_index', '?')} score={h.score:.2f}"
        for h in hits[:3]
    )
    log.info("[qdrant] search query='%s' hits=%d top=[%s]", query[:40], len(hits), top_summary)
    return hits


async def delete_document_vectors(document_id: str) -> None:
    """按 document_id 删除 Qdrant 中该文档的所有向量点。"""
    client = _get_qdrant_client()
    collection_name = settings.qdrant_collection_name
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
        log.info("[qdrant] deleted vectors for document_id=%s", document_id)
    except Exception:
        log.exception("[qdrant] failed to delete vectors for document_id=%s", document_id)
