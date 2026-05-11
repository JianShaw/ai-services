from io import BytesIO
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.services.knowledge_service import (
    create_knowledge_document,
    delete_knowledge_document,
    document_to_response,
    get_document_chunks,
    get_knowledge_document,
    list_knowledge_documents,
    reindex_document,
    retrieve_knowledge,
    update_document_status,
)

router = APIRouter()


class KnowledgeChunkRequest(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentRequest(BaseModel):
    title: str
    source_type: str = "faq"
    category: str = "faq"
    tenant_id: str = "default"
    version: Optional[str] = None
    chunks: list[KnowledgeChunkRequest]


class DocumentStatusRequest(BaseModel):
    status: str


class SearchTestRequest(BaseModel):
    query: str
    category: Optional[str] = None
    tenant_id: Optional[str] = None
    top_k: int = 5


@router.get("/stats")
async def get_stats():
    return {
        "totalConversations": 0,
        "aiResolutionRate": 0,
        "humanTransferRate": 0,
        "avgResponseTime": 0,
        "userSatisfaction": 0,
        "topQuestions": [],
    }


# --- Knowledge Document APIs ---


@router.get("/knowledge/documents")
async def get_knowledge_documents(db: AsyncSession = Depends(get_db)):
    return await list_knowledge_documents(db)


@router.post("/knowledge/documents", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: KnowledgeDocumentRequest,
    db: AsyncSession = Depends(get_db),
):
    """上传知识库文档（JSON 方式）"""
    document, chunk_count = await create_knowledge_document(
        db=db,
        title=request.title,
        source_type=request.source_type,
        version=request.version,
        category=request.category,
        tenant_id=request.tenant_id,
        chunks=[chunk.model_dump() for chunk in request.chunks],
    )
    return document_to_response(document, chunk_count)


@router.post("/knowledge/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    title: str = Form(...),
    category: str = Form("faq"),
    tenant_id: str = Form("default"),
    version: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传知识库文档（文件上传方式，支持 PDF/MD/TXT）"""
    filename = file.filename or "unknown.txt"
    source_type = _detect_source_type(filename)

    content_bytes = await file.read()
    raw_text = _extract_uploaded_text(content_bytes, source_type)

    chunks = _split_text_to_chunks(raw_text)
    if not chunks:
        raise HTTPException(status_code=400, detail="文档内容为空或无法解析")

    document, chunk_count = await create_knowledge_document(
        db=db,
        title=title,
        source_type=source_type,
        version=version,
        category=category,
        tenant_id=tenant_id,
        chunks=chunks,
    )
    return document_to_response(document, chunk_count)


@router.get("/knowledge/documents/{document_id}")
async def get_knowledge_document_detail(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    document = await get_knowledge_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = await get_document_chunks(db, document_id)
    resp = document_to_response(document, len(chunks))
    resp["chunks"] = chunks
    return resp


@router.patch("/knowledge/documents/{document_id}")
async def patch_knowledge_document(
    document_id: str,
    request: DocumentStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    document = await update_document_status(db, document_id, request.status)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document_to_response(document)


@router.delete("/knowledge/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_document_api(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_knowledge_document(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")


@router.post("/knowledge/documents/{document_id}/reindex")
async def reindex_knowledge_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    success = await reindex_document(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "重新索引完成", "document_id": document_id}


@router.get("/knowledge/documents/{document_id}/chunks")
async def get_chunks(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    document = await get_knowledge_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return await get_document_chunks(db, document_id)


@router.post("/knowledge/search-test")
async def search_test(request: SearchTestRequest):
    results = await retrieve_knowledge(
        query=request.query,
        limit=request.top_k,
        category=request.category,
        tenant_id=request.tenant_id,
    )
    return {"query": request.query, "results": results, "total": len(results)}


@router.get("/intents")
async def get_intents():
    return {"message": "Intents configuration endpoint - coming soon"}


@router.get("/scripts")
async def get_scripts():
    return {"message": "Scripts configuration endpoint - coming soon"}


# --- Helpers ---


def _detect_source_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {"pdf": "pdf", "md": "markdown", "markdown": "markdown", "txt": "txt"}.get(ext, "txt")


def _extract_uploaded_text(content_bytes: bytes, source_type: str) -> str:
    if source_type == "pdf":
        return _extract_pdf_text(content_bytes)

    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes.decode("gbk", errors="ignore")


def _extract_pdf_text(content_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return _extract_pdf_text_fallback(content_bytes)

    try:
        reader = PdfReader(BytesIO(content_bytes))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF could not be parsed.") from exc

    return "\n\n".join(text.strip() for text in page_texts if text.strip())


def _extract_pdf_text_fallback(content_bytes: bytes) -> str:
    content = content_bytes.decode("latin-1", errors="ignore")
    text_parts: list[str] = []

    for match in re.finditer(r"<([0-9A-Fa-f\s]+)>\s*Tj", content):
        hex_text = re.sub(r"\s+", "", match.group(1))
        if not hex_text:
            continue

        try:
            raw = bytes.fromhex(hex_text)
        except ValueError:
            continue

        decoded = ""
        for encoding in ("utf-16-be", "utf-8", "gbk"):
            try:
                decoded = raw.decode(encoding).strip()
                break
            except UnicodeDecodeError:
                continue

        if decoded:
            text_parts.append(decoded)

    return "\n".join(text_parts)


def _split_text_to_chunks(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """将文本按段落和字符数切片。"""
    # 按段落分割
    paragraphs = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped:
            paragraphs.append(stripped)

    if not paragraphs:
        return []

    # 合并段落为 chunk
    chunks: list[dict[str, Any]] = []
    current_parts: list[str] = []
    current_len = 0
    section_title = ""

    for para in paragraphs:
        # 检测 Markdown 标题
        if para.startswith("#"):
            if current_parts:
                chunks.append({
                    "content": "\n".join(current_parts),
                    "metadata": {"section_title": section_title} if section_title else {},
                })
                current_parts = []
                current_len = 0
            section_title = para.lstrip("#").strip()
            continue

        if current_len + len(para) > chunk_size and current_parts:
            chunks.append({
                "content": "\n".join(current_parts),
                "metadata": {"section_title": section_title} if section_title else {},
            })
            # overlap: 保留最后一段
            overlap_text = current_parts[-1] if current_parts else ""
            current_parts = [overlap_text, para] if overlap_text else [para]
            current_len = len(overlap_text) + len(para)
        else:
            current_parts.append(para)
            current_len += len(para)

    if current_parts:
        chunks.append({
            "content": "\n".join(current_parts),
            "metadata": {"section_title": section_title} if section_title else {},
        })

    return chunks
