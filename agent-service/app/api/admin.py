from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.services.knowledge_service import (
    create_knowledge_document,
    document_to_response,
    list_knowledge_documents,
)

router = APIRouter()


class KnowledgeChunkRequest(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentRequest(BaseModel):
    title: str
    source_type: str = "faq"
    version: Optional[str] = None
    chunks: list[KnowledgeChunkRequest]

@router.get("/stats")
async def get_stats():
    """获取统计数据"""
    return {
        "totalConversations": 0,
        "aiResolutionRate": 0,
        "humanTransferRate": 0,
        "avgResponseTime": 0,
        "userSatisfaction": 0,
        "topQuestions": []
    }

@router.get("/knowledge/documents")
async def get_knowledge_documents(db: AsyncSession = Depends(get_db)):
    """获取知识库文档列表"""
    return await list_knowledge_documents(db)

@router.post("/knowledge/documents", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: KnowledgeDocumentRequest,
    db: AsyncSession = Depends(get_db),
):
    """上传知识库文档"""
    document, chunk_count = await create_knowledge_document(
        db=db,
        title=request.title,
        source_type=request.source_type,
        version=request.version,
        chunks=[chunk.model_dump() for chunk in request.chunks],
    )
    return document_to_response(document, chunk_count)

@router.get("/intents")
async def get_intents():
    """获取意图配置"""
    return {"message": "Intents configuration endpoint - coming soon"}

@router.get("/scripts")
async def get_scripts():
    """获取话术配置"""
    return {"message": "Scripts configuration endpoint - coming soon"}
