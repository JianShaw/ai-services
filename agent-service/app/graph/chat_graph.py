from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.api.chat_types import AIResponse
from app.services.ai_client import AIClientError, deepseek_client


class ChatState(TypedDict, total=False):
    user_id: str
    message: str
    conversation_id: Optional[str]
    channel: str
    intent: str
    confidence: float
    need_human: bool
    reply: str


def classify_intent(message: str) -> tuple[str, float, bool]:
    message_lower = message.lower()

    if "订单" in message_lower:
        return "order_query", 0.8, False
    if "退款" in message_lower:
        return "refund_query", 0.85, False
    if "转人工" in message_lower or "人工" in message_lower:
        return "human_request", 0.95, True
    if "物流" in message_lower:
        return "logistics_query", 0.8, False
    return "unknown", 0.5, False


def fallback_reply(intent: str) -> str:
    replies = {
        "order_query": "关于您的订单，我可以帮您查询。请提供订单号，我会继续为您确认订单信息。",
        "refund_query": "关于退款问题，我可以帮您处理。请提供订单号，我会为您查询退款进度。",
        "human_request": "正在为您转接人工客服，请稍等。",
        "logistics_query": "我可以帮您查询物流信息。请提供订单号，我会为您确认最新物流状态。",
        "unknown": "感谢您的咨询。请问您想了解订单信息、物流查询，还是退款相关服务？",
    }
    return replies.get(intent, replies["unknown"])


async def classify_node(state: ChatState) -> ChatState:
    intent, confidence, need_human = classify_intent(state["message"])
    return {
        **state,
        "intent": intent,
        "confidence": confidence,
        "need_human": need_human,
    }


async def generate_reply_node(state: ChatState) -> ChatState:
    if state["need_human"]:
        reply = fallback_reply(state["intent"])
    else:
        try:
            reply = await deepseek_client.reply(
                user_message=state["message"],
                intent=state["intent"],
                conversation_id=state.get("conversation_id"),
            )
        except AIClientError:
            reply = fallback_reply(state["intent"])

    return {**state, "reply": reply}


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("classify_intent", classify_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "generate_reply")
    graph.add_edge("generate_reply", END)
    return graph.compile()


chat_graph = build_chat_graph()


async def run_chat_graph(
    user_id: str,
    message: str,
    conversation_id: Optional[str],
    channel: str,
) -> AIResponse:
    result = await chat_graph.ainvoke(
        {
            "user_id": user_id,
            "message": message,
            "conversation_id": conversation_id,
            "channel": channel,
        }
    )

    return AIResponse(
        reply=result["reply"],
        reply_type="text",
        cards=[],
        intent=result["intent"],
        confidence=result["confidence"],
        need_human=result["need_human"],
    )
