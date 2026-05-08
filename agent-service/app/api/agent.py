from fastapi import APIRouter

router = APIRouter()

@router.get("/conversations")
async def get_conversations():
    """获取会话列表"""
    return {"message": "Agent conversations endpoint - coming soon"}

@router.post("/takeover")
async def takeover_conversation():
    """接管会话"""
    return {"message": "Agent takeover endpoint - coming soon"}

@router.post("/reply")
async def send_reply():
    """发送客服回复"""
    return {"message": "Agent reply endpoint - coming soon"}

@router.get("/tickets")
async def get_tickets():
    """获取工单列表"""
    return {"message": "Tickets endpoint - coming soon"}

@router.post("/tickets")
async def create_ticket():
    """创建工单"""
    return {"message": "Create ticket endpoint - coming soon"}