from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import KnowledgeChunk, KnowledgeDocument, async_session_maker


def document_to_response(document: KnowledgeDocument, chunk_count: int = 0) -> dict[str, Any]:
    return {
        "id": document.id,
        "title": document.title,
        "sourceType": document.source_type,
        "category": document.category,
        "tenantId": document.tenant_id,
        "status": document.status,
        "version": document.version,
        "chunkCount": chunk_count,
        "createdAt": document.created_at.isoformat() if document.created_at else None,
        "updatedAt": document.updated_at.isoformat() if document.updated_at else None,
    }


async def create_knowledge_document(
    db: AsyncSession,
    title: str,
    source_type: str,
    chunks: list[dict[str, Any]],
    version: Optional[str] = None,
    category: str = "faq",
    tenant_id: str = "default",
) -> tuple[KnowledgeDocument, int]:
    now = datetime.utcnow()
    document = KnowledgeDocument(
        id=f"doc_{uuid4().hex}",
        title=title,
        source_type=source_type,
        category=category,
        tenant_id=tenant_id,
        status="indexing",
        version=version,
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    await db.flush()

    chunk_records: list[KnowledgeChunk] = []
    for index, chunk in enumerate(chunks):
        record = KnowledgeChunk(
            id=f"chunk_{uuid4().hex}",
            document_id=document.id,
            content=chunk["content"],
            embedding_id=None,
            meta_data={
                **(chunk.get("metadata") or {}),
                "chunk_index": index,
            },
            created_at=now,
        )
        db.add(record)
        chunk_records.append(record)

    await db.flush()

    # 写入 Qdrant 向量
    point_ids = await _upsert_chunks_to_qdrant(document, chunk_records)
    document.status = "active" if len(point_ids) == len(chunk_records) else "index_failed"
    document.updated_at = datetime.utcnow()
    await db.flush()

    return document, len(chunks)


async def _upsert_chunks_to_qdrant(
    document: KnowledgeDocument,
    chunks: list[KnowledgeChunk],
) -> list[str]:
    from app.services.qdrant_vector_service import KnowledgeChunkInput, upsert_chunks

    inputs = [
        KnowledgeChunkInput(
            chunk_id=c.id,
            document_id=document.id,
            content=c.content,
            title=document.title,
            category=document.category or "faq",
            tenant_id=document.tenant_id or "default",
            source_type=document.source_type,
            version=document.version or "",
            chunk_index=(c.meta_data or {}).get("chunk_index", 0),
        )
        for c in chunks
    ]
    try:
        point_ids = await upsert_chunks(inputs)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("[knowledge] failed to upsert chunks to Qdrant")
        return []

    # 回填 embedding_id (point_id)
    for chunk, point_id in zip(chunks, point_ids):
        chunk.embedding_id = point_id

    return point_ids


async def list_knowledge_documents(db: AsyncSession) -> list[dict[str, Any]]:
    documents_result = await db.execute(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    )
    documents = list(documents_result.scalars().all())

    responses: list[dict[str, Any]] = []
    for document in documents:
        chunks_result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
        )
        responses.append(document_to_response(document, len(chunks_result.scalars().all())))
    return responses


async def get_knowledge_document(db: AsyncSession, document_id: str) -> Optional[KnowledgeDocument]:
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    )
    return result.scalar_one_or_none()


async def update_document_status(
    db: AsyncSession,
    document_id: str,
    status: str,
) -> Optional[KnowledgeDocument]:
    document = await get_knowledge_document(db, document_id)
    if not document:
        return None
    document.status = status
    document.updated_at = datetime.utcnow()
    await db.flush()

    # 同步更新 Qdrant payload 中的 status
    if status == "active":
        try:
            from app.services.qdrant_vector_service import delete_document_vectors
            await delete_document_vectors(document_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("[knowledge] failed to delete Qdrant vectors before reindex")
        chunks_result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )
        chunks = list(chunks_result.scalars().all())
        point_ids = await _upsert_chunks_to_qdrant(document, chunks)
        if len(point_ids) != len(chunks):
            document.status = "index_failed"
            document.updated_at = datetime.utcnow()
            await db.flush()
    else:
        try:
            from app.services.qdrant_vector_service import delete_document_vectors
            await delete_document_vectors(document_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("[knowledge] failed to delete Qdrant vectors")

    return document


async def delete_knowledge_document(db: AsyncSession, document_id: str) -> bool:
    document = await get_knowledge_document(db, document_id)
    if not document:
        return False
    # 删除 chunks
    chunks_result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
    )
    for chunk in chunks_result.scalars().all():
        await db.delete(chunk)

    await db.delete(document)
    await db.flush()

    # 删除 Qdrant 向量
    try:
        from app.services.qdrant_vector_service import delete_document_vectors
        await delete_document_vectors(document_id)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("[knowledge] failed to delete Qdrant vectors")

    return True


async def get_document_chunks(
    db: AsyncSession,
    document_id: str,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document_id)
        .order_by(KnowledgeChunk.created_at)
    )
    chunks = result.scalars().all()
    return [
        {
            "id": c.id,
            "documentId": c.document_id,
            "content": c.content,
            "embeddingId": c.embedding_id,
            "metadata": c.meta_data or {},
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chunks
    ]


async def retrieve_knowledge(
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    try:
        from app.services.qdrant_vector_service import KnowledgeSearchFilter, search_knowledge

        filters = KnowledgeSearchFilter(
            tenant_id=tenant_id or "default",
            category=category,
            status="active",
        )
        hits = await search_knowledge(query, filters=filters, top_k=limit)
        return [
            {
                "id": hit.chunk_id,
                "document_id": hit.document_id,
                "title": hit.title,
                "content": hit.content,
                "score": hit.score,
                "category": hit.category,
                "metadata": hit.metadata,
            }
            for hit in hits
        ]
    except Exception:
        import logging
        logging.getLogger(__name__).exception("[knowledge] Qdrant search failed, falling back to local")
        return await _retrieve_knowledge_local(
            query,
            limit,
            category=category,
            tenant_id=tenant_id or "default",
        )


async def _retrieve_knowledge_local(
    query: str,
    limit: int = 3,
    category: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """本地 SQL 关键词打分兜底。"""
    async with async_session_maker() as session:
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == "active")
        )
        if tenant_id:
            stmt = stmt.where(KnowledgeDocument.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(KnowledgeDocument.category == category)
        result = await session.execute(stmt)
        scored: list[tuple[int, KnowledgeChunk, KnowledgeDocument]] = []
        for chunk, document in result.all():
            score = _score(query, chunk.content)
            if score > 0:
                scored.append((score, chunk, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": chunk.id,
            "document_id": document.id,
            "title": document.title,
            "content": chunk.content,
            "score": score,
            "metadata": chunk.meta_data or {},
        }
        for score, chunk, document in scored[:limit]
    ]


def _query_terms(query: str) -> set[str]:
    compact = "".join(query.lower().split())
    terms = {compact[index : index + 2] for index in range(max(len(compact) - 1, 0))}
    terms.update(token for token in compact.replace("，", " ").replace("。", " ").split() if token)
    return {term for term in terms if term}


def _score(query: str, content: str) -> int:
    query_terms = _query_terms(query)
    normalized_content = content.lower()
    score = sum(1 for term in query_terms if term in normalized_content)

    for keyword in ("保修", "发票", "会员", "退款", "物流", "售后", "政策"):
        if keyword in query and keyword in content:
            score += 3

    return score


async def answer_from_knowledge(
    query: str,
    conversation_id: Optional[str] = None,
) -> tuple[str, list[dict[str, Any]]]:
    sources = await retrieve_knowledge(query)
    if not sources:
        return (
            "暂时没有在知识库中找到可以确认的答案。为了避免误导您，我可以帮您转人工客服继续确认。",
            [],
        )

    # 使用 LLM 基于 context 生成答案
    try:
        from app.services.ai_client import reply_via_llm

        context = "\n\n".join(
            f"【来源：{s.get('title', '未知')}】\n{s['content']}"
            for s in sources
        )
        prompt = (
            f"请根据以下知识库资料回答用户问题。要求：\n"
            f"1. 只基于提供的资料回答，不要编造\n"
            f"2. 回复控制在 3 句话以内\n"
            f'3. 如果资料中没有相关信息，请说"知识库中暂无相关信息，建议转人工客服确认"\n\n'
            f"知识库资料：\n{context}\n\n"
            f"用户问题：{query}"
        )
        reply = await reply_via_llm(
            user_message=prompt,
            intent="knowledge_query",
            conversation_id=conversation_id,
            history=[],
        )
        return reply, sources
    except Exception:
        import logging
        logging.getLogger(__name__).exception("[knowledge] LLM answer generation failed, using raw context")
        answer_body = "\n".join(f"- {source['content']}" for source in sources)
        return f"根据知识库查询到以下信息：\n{answer_body}", sources


async def reindex_document(db: AsyncSession, document_id: str) -> bool:
    """重新向量化文档：删除旧向量，重新写入。"""
    document = await get_knowledge_document(db, document_id)
    if not document:
        return False
    document.status = "indexing"
    document.updated_at = datetime.utcnow()
    await db.flush()

    # 删除旧向量
    try:
        from app.services.qdrant_vector_service import delete_document_vectors
        await delete_document_vectors(document_id)
    except Exception:
        pass

    # 获取所有 chunks
    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
    )
    chunks = list(result.scalars().all())
    if not chunks:
        document.status = "active"
        document.updated_at = datetime.utcnow()
        await db.flush()
        return True

    # 重新写入
    point_ids = await _upsert_chunks_to_qdrant(document, chunks)
    document.status = "active" if len(point_ids) == len(chunks) else "index_failed"
    document.updated_at = datetime.utcnow()
    await db.flush()
    return True
