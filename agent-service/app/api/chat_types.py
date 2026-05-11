from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIResponse(BaseModel):
    reply: str
    reply_type: str = "text"
    cards: List[Dict[str, Any]] = []
    intent: Optional[str] = None
    confidence: Optional[float] = None
    need_human: bool = False
    risk_level: str = "low"
    trace_id: Optional[str] = None
    route: Optional[str] = None
    ticket_id: Optional[str] = None
    tools_used: List[str] = []
    sources: List[Dict[str, Any]] = []
    pending_intent: Optional[str] = None
    missing_slots: List[str] = []
    slots: Dict[str, Any] = {}
    message_id: Optional[str] = None
