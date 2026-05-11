import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat_types import AIResponse
from app.graph.chat_graph import run_chat_graph
from app.models.database import Conversation, Message, get_db

router = APIRouter()
log = logging.getLogger(__name__)


def _preview(value: str, limit: int = 80) -> str:
    compact = " ".join((value or "").split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


class SendMessageRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: str
    message: str
    channel: str = "web"


class CreateConversationRequest(BaseModel):
    conversation_id: str
    user_id: str
    channel: str = "web"


class TransferRequest(BaseModel):
    reason: Optional[str] = None


class RateMessageRequest(BaseModel):
    rating: str


def now_utc() -> datetime:
    return datetime.utcnow()


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def conversation_to_response(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "userId": conversation.user_id,
        "channel": conversation.channel,
        "status": conversation.status,
        "currentIntent": conversation.current_intent or "",
        "summary": conversation.summary,
        "assignedAgentId": conversation.assigned_agent_id,
        "createdAt": format_datetime(conversation.created_at),
        "updatedAt": format_datetime(conversation.updated_at),
    }


def message_to_response(message: Message) -> dict:
    metadata = message.meta_data or {}
    return {
        "id": message.id,
        "conversationId": message.conversation_id,
        "senderType": message.sender_type,
        "content": message.content,
        "messageType": metadata.get("messageType", "text"),
        "metadata": metadata,
        "timestamp": format_datetime(message.created_at),
    }


async def process_message_with_agent(
    user_id: str,
    message: str,
    conversation_id: Optional[str],
    channel: str,
    conversation_context: Optional[dict] = None,
) -> AIResponse:
    return await run_chat_graph(
        user_id=user_id,
        message=message,
        conversation_id=conversation_id,
        channel=channel,
        conversation_context=conversation_context,
    )


@router.post("/messages", response_model=AIResponse)
async def send_message(request: SendMessageRequest, db: AsyncSession = Depends(get_db)):
    """接收用户消息的核心接口，执行完整的对话处理流程。"""
    log.info("[POST /messages] user=%s conv=%s msg_preview=%s",
             request.user_id, request.conversation_id, _preview(request.message))
    try:
        # ── 第一阶段：会话准备 ──
        # 如果没有传 conversation_id 则自动生成，首次访问时自动创建会话
        conversation_id = request.conversation_id or f"conv_{uuid4().hex}"
        conversation = await db.get(Conversation, conversation_id)
        current_time = now_utc()

        if conversation is None:
            conversation = Conversation(
                id=conversation_id,
                user_id=request.user_id,
                channel=request.channel,
                status="active",
                created_at=current_time,
                updated_at=current_time,
            )
            db.add(conversation)

        # 持久化用户消息到数据库
        history_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(10)
        )
        history_messages = list(reversed(history_result.scalars().all()))
        history = [
            {
                "sender_type": message.sender_type,
                "content": message.content,
                "created_at": format_datetime(message.created_at),
            }
            for message in history_messages
        ]
        log.info("[POST /messages] history_count=%d", len(history))

        user_message = Message(
            id=f"msg_{uuid4().hex}",
            conversation_id=conversation_id,
            sender_type="user",
            content=request.message,
            meta_data={
                "messageType": "text",
                "channel": request.channel,
            },
            created_at=current_time,
        )
        db.add(user_message)

        # ── 第二阶段：构建上下文 & 调用 Graph ──
        # 从数据库恢复上一次未完成的槽位填充状态，传入 graph 以支持多轮追问
        conv_context = {
            "pending_intent": conversation.pending_intent,
            "missing_slots": conversation.missing_slots or [],
            "slots": (conversation.context_data or {}).get("slots", {}),
            "history": history,
        }

        log.info(f"[POST /messages] conv_context: pending_intent={conv_context.get('pending_intent')} missing_slots={conv_context.get('missing_slots')}")

        # 执行 chat graph：slot_fill → classify → check_slots → lookup_order → generate_reply
        response = await process_message_with_agent(
            user_id=request.user_id,
            message=request.message,
            conversation_id=conversation_id,
            channel=request.channel,
            conversation_context=conv_context,
        )

        # ── 第三阶段：持久化 AI 回复 ──
        # 将 AI 的回复及完整元数据（意图、置信度、路由、trace 等）写入消息表
        ai_message = Message(
            id=f"msg_{uuid4().hex}",
            conversation_id=conversation_id,
            sender_type="ai",
            content=response.reply,
            meta_data={
                "messageType": response.reply_type,
                "intent": response.intent,
                "confidence": response.confidence,
                "needHuman": response.need_human,
                "riskLevel": response.risk_level,
                "traceId": response.trace_id,
                "route": response.route,
                "ticketId": response.ticket_id,
                "toolsUsed": response.tools_used,
                "sources": response.sources,
                "cards": response.cards,
            },
            created_at=now_utc(),
        )
        db.add(ai_message)

        # ── 第四阶段：更新会话状态 ──
        conversation.current_intent = response.intent
        # 需要转人工时，将状态标记为 transferred
        conversation.status = "transferred" if response.need_human else conversation.status

        if response.pending_intent:
            # 槽位未填完：保存 pending_intent + 缺失槽位 + 已填槽位，下轮继续追问
            conversation.pending_intent = response.pending_intent
            conversation.missing_slots = response.missing_slots
            conversation.context_data = {"slots": response.slots}
        else:
            # 槽位已填完或无需填槽：清空补槽状态
            conversation.pending_intent = None
            conversation.missing_slots = None
            conversation.context_data = None
        conversation.updated_at = now_utc()

        response.message_id = ai_message.id
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    user_id: Optional[str] = Query(default=None, alias="userId"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if user_id:
        query = query.where(Conversation.user_id == user_id)
    log.info(f"[GET /conversations] userId={user_id}")
    result = await db.execute(query)
    rows = [conversation_to_response(c) for c in result.scalars().all()]
    log.info(f"[GET /conversations] returned {len(rows)} conversations")
    return rows


@router.post("/conversations")
async def create_conversation(request: CreateConversationRequest, db: AsyncSession = Depends(get_db)):
    log.info(f"[POST /conversations] conv={request.conversation_id} user={request.user_id}")
    existing = await db.get(Conversation, request.conversation_id)
    if existing:
        log.info(f"[POST /conversations] already exists, returning existing")
        return conversation_to_response(existing)

    current_time = now_utc()
    conversation = Conversation(
        id=request.conversation_id,
        user_id=request.user_id,
        channel=request.channel,
        status="active",
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(conversation)
    await db.flush()
    return conversation_to_response(conversation)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    log.info(f"[GET /conversations/{{id}}] conv={conversation_id}")
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(conversation)


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    log.info(f"[GET /conversations/{{id}}/messages] conv={conversation_id}")
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = [message_to_response(message) for message in result.scalars().all()]
    log.info(f"[GET /conversations/{{id}}/messages] returned {len(messages)} messages")
    return messages


@router.post("/conversations/{conversation_id}/transfer")
async def transfer_to_human(
    conversation_id: str,
    request: Optional[TransferRequest] = None,
    reason: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    log.info(f"[POST /conversations/{{id}}/transfer] conv={conversation_id}")
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    transfer_reason = reason or (request.reason if request else None)
    log.info(f"[POST /conversations/{{id}}/transfer] reason={transfer_reason}")
    conversation.status = "transferred"
    conversation.updated_at = now_utc()

    db.add(
            Message(
                id=f"msg_{uuid4().hex}",
                conversation_id=conversation_id,
                sender_type="agent",
                content="Conversation transferred to human agent.",
            meta_data={
                "messageType": "text",
                "event": "human_transfer",
                "reason": transfer_reason,
            },
            created_at=now_utc(),
        )
    )
    return {"success": True}


@router.post("/messages/{message_id}/rate")
async def rate_message(
    message_id: str,
    request: Optional[RateMessageRequest] = None,
    rating: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    log.info(f"[POST /messages/{{id}}/rate] msg={message_id}")
    message = await db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    final_rating = rating or (request.rating if request else None)
    if not final_rating:
        raise HTTPException(status_code=422, detail="rating is required")

    metadata = dict(message.meta_data or {})
    metadata["rating"] = final_rating
    message.meta_data = metadata
    return {"success": True}
