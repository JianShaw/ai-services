from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Conversation, Message, get_db
from app.services.ticket_service import create_ticket as create_ticket_record
from app.services.ticket_service import list_tickets, ticket_to_response

router = APIRouter()


class CreateTicketRequest(BaseModel):
    conversation_id: str
    user_id: str
    type: str
    description: str
    priority: str = "medium"
    assigned_to: Optional[str] = None


class TakeoverRequest(BaseModel):
    conversation_id: str
    agent_id: str


class AgentReplyRequest(BaseModel):
    conversation_id: str
    agent_id: str
    message: str


def format_datetime(value) -> Optional[str]:
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

@router.get("/conversations")
async def get_conversations(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """获取会话列表"""
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if status_filter:
        query = query.where(Conversation.status == status_filter)
    result = await db.execute(query)
    return [conversation_to_response(conversation) for conversation in result.scalars().all()]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """获取会话详情"""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(conversation)


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取会话消息"""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return [message_to_response(message) for message in result.scalars().all()]

@router.post("/takeover")
async def takeover_conversation(request: TakeoverRequest, db: AsyncSession = Depends(get_db)):
    """接管会话"""
    conversation = await db.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.status = "assigned"
    conversation.assigned_agent_id = request.agent_id
    db.add(conversation)
    await db.flush()
    return conversation_to_response(conversation)

@router.post("/reply", status_code=status.HTTP_201_CREATED)
async def send_reply(request: AgentReplyRequest, db: AsyncSession = Depends(get_db)):
    """发送客服回复"""
    conversation = await db.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.assigned_agent_id and conversation.assigned_agent_id != request.agent_id:
        raise HTTPException(status_code=409, detail="Conversation assigned to another agent")

    conversation.status = "assigned"
    conversation.assigned_agent_id = request.agent_id

    message = Message(
        id=f"msg_{uuid4().hex}",
        conversation_id=request.conversation_id,
        sender_type="agent",
        content=request.message,
        meta_data={
            "messageType": "text",
            "agentId": request.agent_id,
        },
    )
    db.add(conversation)
    db.add(message)
    await db.flush()
    return message_to_response(message)

@router.get("/tickets")
async def get_tickets(db: AsyncSession = Depends(get_db)):
    """获取工单列表"""
    tickets = await list_tickets(db)
    return [ticket_to_response(ticket) for ticket in tickets]

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(request: CreateTicketRequest, db: AsyncSession = Depends(get_db)):
    """创建工单"""
    ticket = await create_ticket_record(
        db=db,
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        ticket_type=request.type,
        description=request.description,
        priority=request.priority,
        assigned_to=request.assigned_to,
    )
    return ticket_to_response(ticket)
