from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.chat_types import AIResponse
from app.graph.chat_graph import run_chat_graph

router = APIRouter()


class SendMessageRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: str
    message: str
    channel: str = "web"


class CreateConversationRequest(BaseModel):
    conversation_id: str
    user_id: str
    channel: str = "web"


async def process_message_with_agent(
    user_id: str,
    message: str,
    conversation_id: Optional[str],
    channel: str,
) -> AIResponse:
    return await run_chat_graph(
        user_id=user_id,
        message=message,
        conversation_id=conversation_id,
        channel=channel,
    )


@router.post("/messages", response_model=AIResponse)
async def send_message(request: SendMessageRequest):
    try:
        response = await process_message_with_agent(
            user_id=request.user_id,
            message=request.message,
            conversation_id=request.conversation_id,
            channel=request.channel,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations")
async def create_conversation(request: CreateConversationRequest):
    return {
        "id": request.conversation_id,
        "user_id": request.user_id,
        "channel": request.channel,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    return {
        "id": conversation_id,
        "user_id": "user_001",
        "channel": "web",
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    return []


@router.post("/conversations/{conversation_id}/transfer")
async def transfer_to_human(conversation_id: str, reason: str):
    return {"success": True}


@router.post("/messages/{message_id}/rate")
async def rate_message(message_id: str, rating: str):
    return {"success": True}
