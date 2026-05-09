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
) -> tuple[KnowledgeDocument, int]:
    now = datetime.utcnow()
    document = KnowledgeDocument(
        id=f"doc_{uuid4().hex}",
        title=title,
        source_type=source_type,
        status="active",
        version=version,
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    await db.flush()

    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunk(
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
        )

    await db.flush()
    return document, len(chunks)


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


async def retrieve_knowledge(query: str, limit: int = 3) -> list[dict[str, Any]]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == "active")
        )
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


async def answer_from_knowledge(query: str) -> tuple[str, list[dict[str, Any]]]:
    sources = await retrieve_knowledge(query)
    if not sources:
        return (
            "暂时没有在知识库中找到可以确认的答案。为了避免误导您，我可以帮您转人工客服继续确认。",
            [],
        )

    answer_body = "\n".join(f"- {source['content']}" for source in sources)
    return f"根据知识库查询到以下信息：\n{answer_body}", sources
