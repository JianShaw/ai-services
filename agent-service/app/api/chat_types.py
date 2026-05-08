from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIResponse(BaseModel):
    reply: str
    reply_type: str = "text"
    cards: List[Dict[str, Any]] = []
    intent: Optional[str] = None
    confidence: Optional[float] = None
    need_human: bool = False
