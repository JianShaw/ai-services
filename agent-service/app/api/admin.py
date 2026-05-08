from fastapi import APIRouter

router = APIRouter()

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
async def get_knowledge_documents():
    """获取知识库文档列表"""
    return {"message": "Knowledge documents endpoint - coming soon"}

@router.post("/knowledge/documents")
async def upload_knowledge_document():
    """上传知识库文档"""
    return {"message": "Upload knowledge document endpoint - coming soon"}

@router.get("/intents")
async def get_intents():
    """获取意图配置"""
    return {"message": "Intents configuration endpoint - coming soon"}

@router.get("/scripts")
async def get_scripts():
    """获取话术配置"""
    return {"message": "Scripts configuration endpoint - coming soon"}