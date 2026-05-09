from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Ticket


def ticket_to_response(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "conversationId": ticket.conversation_id,
        "userId": ticket.user_id,
        "type": ticket.type,
        "priority": ticket.priority,
        "status": ticket.status,
        "description": ticket.description,
        "assignedTo": ticket.assigned_to,
        "createdAt": ticket.created_at.isoformat() if ticket.created_at else None,
        "updatedAt": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


async def create_ticket(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
    ticket_type: str,
    description: str,
    priority: str = "medium",
    assigned_to: Optional[str] = None,
) -> Ticket:
    now = datetime.utcnow()
    ticket = Ticket(
        id=f"ticket_{uuid4().hex}",
        conversation_id=conversation_id,
        user_id=user_id,
        type=ticket_type,
        priority=priority,
        status="open",
        description=description,
        assigned_to=assigned_to,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()
    return ticket


async def list_tickets(db: AsyncSession) -> list[Ticket]:
    result = await db.execute(select(Ticket).order_by(Ticket.created_at.desc()))
    return list(result.scalars().all())
