import logging
from typing import Any, Optional, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.api.chat_types import AIResponse
from app.config.settings import settings
from app.models.database import async_session_maker
from app.services.ai_client import AIClientError, deepseek_client
from app.services.intent_service import (
    INTENT_SLOTS,
    IntentResult,
    build_clarify_question,
    classify_intent,
)
from app.services.knowledge_service import answer_from_knowledge
from app.services.order_service import (
    format_logistics_reply,
    format_order_reply,
    format_refund_reply,
    get_order_snapshot,
)

log = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    """LangGraph 在各节点之间传递的状态对象。

    每个节点只读写自己关心的字段，最后由 run_chat_graph 组装成 AIResponse。
    """
    user_id: str
    message: str
    conversation_id: Optional[str]
    channel: str
    intent: str
    confidence: float
    risk_level: str
    intent_reason: str
    slots: dict[str, str]
    order: Optional[dict[str, Any]]
    sources: list[dict[str, Any]]
    tools_used: list[str]
    trace_id: str
    route: str
    ticket_id: Optional[str]
    reply: str
    pending_intent: Optional[str]
    missing_slots: list[str]
    classification_source: str
    conversation_context: dict[str, Any]


def fallback_reply(intent: str) -> str:
    """当模型不可用、低置信度或需要兜底时，按意图返回固定话术。"""
    replies = {
        "check_order": "关于您的订单，我可以帮您查询。请提供订单号，我会继续为您确认订单信息。",
        "check_logistics": "我可以帮您查询物流信息。请提供订单号，我会为您确认最新物流状态。",
        "refund": "关于退款问题，我可以帮您处理。请提供订单号，我会为您查询退款进度。",
        "invoice": "我可以帮您处理发票问题。请提供订单号。",
        "modify_address": "我可以帮您修改收货地址。请提供订单号和新地址。",
        "transfer_human": "正在为您转接人工客服，请稍等。",
        "complaint": "非常抱歉给您带来不好的体验。这个问题我会为您转接人工客服继续处理，请稍等。",
        "unknown": "感谢您的咨询。请问您想了解订单信息、物流查询、退款，还是其他服务？",
    }
    return replies.get(intent, replies["unknown"])


# ---- Nodes ----


async def slot_fill_node(state: ChatState) -> ChatState:
    """图入口节点：检查当前会话是否处于多轮补槽流程。"""
    ctx = state.get("conversation_context", {})
    pending_intent = ctx.get("pending_intent")
    missing_slots = ctx.get("missing_slots", [])
    existing_slots = ctx.get("slots", {})
    log.info(f"[slot_fill] pending={pending_intent} missing={missing_slots} existing_slots={existing_slots}")

    if pending_intent and missing_slots:
        # 上一轮已经确定了意图，但还缺必填槽位；本轮优先当作槽位补充处理。
        result = await classify_intent(
            message=state["message"],
            pending_intent=pending_intent,
            missing_slots=missing_slots,
            existing_slots=existing_slots,
        )
        return {
            **state,
            "intent": result.intent,
            "confidence": result.confidence,
            "slots": result.slots,
            "pending_intent": pending_intent,
            "missing_slots": _calc_missing(pending_intent, result.slots),
            "classification_source": "slot_fill",
            "risk_level": result.risk_level,
        }

    return {**state, "pending_intent": None, "missing_slots": [], "slots": {}}


def _calc_missing(intent: str, slots: dict[str, str]) -> list[str]:
    """根据意图的槽位定义，找出还没有填充的必填槽位。"""
    schema = INTENT_SLOTS.get(intent, {})
    return [name for name, (_, required) in schema.items() if required and not slots.get(name)]


async def classify_node(state: ChatState) -> ChatState:
    """意图分类节点：对用户消息进行意图识别和槽位抽取，计算缺失的必填槽位。"""
    log.info(f"[classify] msg={state['message']!r}")
    # 调用分类服务，依次走 规则匹配 → LLM 回退
    result = await classify_intent(message=state["message"])
    log.info(f"[classify] result: intent={result.intent} conf={result.confidence} source={result.source} reason={result.reason} slots={result.slots}")
    return {
        **state,
        "trace_id": state.get("trace_id") or f"trace_{uuid4().hex}",
        "intent": result.intent,
        "confidence": result.confidence,
        "risk_level": result.risk_level,
        "intent_reason": result.reason,
        "slots": result.slots,
        "classification_source": result.source,
        # 重置下游节点状态，避免残留旧数据
        "order": None,
        "tools_used": [],
        "sources": [],
        # 根据意图的槽位定义，计算还缺少哪些必填字段
        "missing_slots": _calc_missing(result.intent, result.slots),
    }


def route_after_classify(state: ChatState) -> str:
    """分类后路由：高风险转人工，低置信度澄清，其余检查槽位。"""
    intent = state["intent"]
    confidence = state.get("confidence", 0)
    if intent in {"transfer_human", "complaint"}:
        log.info(f"[route] → human_transfer (intent={intent})")
        return "human_transfer"
    if confidence < 0.4:
        log.info(f"[route] → human_transfer (conf={confidence} < 0.4)")
        return "human_transfer"
    if confidence < settings.default_confidence_threshold:
        log.info(f"[route] → clarify (conf={confidence} < {settings.default_confidence_threshold})")
        return "clarify"
    log.info(f"[route] → check_slots (conf={confidence})")
    return "check_slots"


async def check_slots_node(state: ChatState) -> ChatState:
    """检查业务必填参数是否齐全；不齐则生成追问并记录 pending_intent。"""
    missing = state.get("missing_slots", [])
    log.info(f"[check_slots] intent={state['intent']} missing={missing}")
    if missing:
        question = build_clarify_question(state["intent"], missing)
        return {
            **state,
            "reply": question,
            "route": "clarify",
            "pending_intent": state["intent"],
        }
    return {**state, "pending_intent": None}


def route_after_slots(state: ChatState) -> str:
    """槽位检查后的路由：继续追问、调用业务工具或直接生成回复。"""
    if state.get("pending_intent") and state.get("missing_slots"):
        return "clarify"
    intent = state["intent"]
    if intent in {"check_order", "check_logistics", "refund", "invoice", "modify_address"}:
        return "business_tool"
    return "generate"


async def clarify_node(state: ChatState) -> ChatState:
    """澄清节点：保留前面生成好的追问回复，标记当前路由。"""
    return {
        **state,
        "route": "clarify",
        "tools_used": [],
    }


async def human_transfer_node(state: ChatState) -> ChatState:
    """转人工节点：生成固定转人工回复，并记录使用了转人工工具。"""
    return {
        **state,
        "route": "human_transfer",
        "tools_used": ["transfer_to_human"],
        "reply": fallback_reply(state["intent"]),
    }


async def lookup_order_node(state: ChatState) -> ChatState:
    """订单查询节点：根据 slots.order_id 查询订单快照，供后续回复格式化使用。"""
    order_id = (state.get("slots") or {}).get("order_id")
    if not order_id:
        return {**state, "order": None, "route": "business_tool", "tools_used": []}
    order = await get_order_snapshot(order_id, state["user_id"])
    return {
        **state,
        "order": order,
        "route": "business_tool",
        "tools_used": ["get_order_snapshot"],
    }


async def knowledge_node(state: ChatState) -> ChatState:
    """知识库节点：从知识库检索答案，目前图里未作为默认路由使用。"""
    reply, sources = await answer_from_knowledge(state["message"])
    return {
        **state,
        "route": "knowledge",
        "tools_used": ["retrieve_knowledge"],
        "reply": reply,
        "sources": sources,
    }


async def ticket_node(state: ChatState) -> ChatState:
    """工单节点：创建售后工单，目前图里未作为默认路由使用。"""
    async with async_session_maker() as session:
        from app.services.ticket_service import create_ticket as create_ticket_record

        ticket = await create_ticket_record(
            db=session,
            conversation_id=state.get("conversation_id") or f"conv_{state['trace_id']}",
            user_id=state["user_id"],
            ticket_type="after_sales",
            priority="medium",
            description=state["message"],
        )
        await session.commit()

    return {
        **state,
        "route": "ticket",
        "tools_used": ["create_ticket"],
        "ticket_id": ticket.id,
        "reply": f"已为您创建售后工单 {ticket.id}，客服会继续跟进处理。",
    }


async def generate_reply_node(state: ChatState) -> ChatState:
    """最终回复节点：优先使用订单数据格式化回复，否则调用大模型或固定兜底话术。"""
    intent = state["intent"]
    slots = state.get("slots", {})
    order = state.get("order")
    order_id = slots.get("order_id")

    if order and intent == "check_logistics":
        reply = format_logistics_reply(order)
    elif order and intent == "refund":
        reply = format_refund_reply(order)
    elif order and intent in {"check_order", "invoice", "modify_address"}:
        reply = format_order_reply(order)
        if intent == "invoice":
            reply += "\n如需开具发票，请联系人工客服或前往订单详情页操作。"
        elif intent == "modify_address":
            reply += "\n如需修改地址，请联系人工客服协助处理。"
    elif order_id:
        reply = f"没有查询到订单 {order_id}。请确认订单号是否正确，或联系人工客服继续处理。"
    else:
        try:
            reply = await deepseek_client.reply(
                user_message=state["message"],
                intent=intent,
                conversation_id=state.get("conversation_id"),
            )
        except AIClientError:
            reply = fallback_reply(intent)

    return {**state, "reply": reply, "route": state.get("route") or "generate"}


# ---- Graph ----


def build_chat_graph():
    """构建客服对话状态图。

    主路径：
    slot_fill -> classify_intent -> check_slots -> lookup_order/generate_reply
    其中澄清和转人工会提前结束。
    """
    graph = StateGraph(ChatState)

    graph.add_node("slot_fill", slot_fill_node)
    graph.add_node("classify_intent", classify_node)
    graph.add_node("check_slots", check_slots_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("human_transfer", human_transfer_node)
    graph.add_node("lookup_order", lookup_order_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("ticket", ticket_node)
    graph.add_node("generate_reply", generate_reply_node)

    graph.set_entry_point("slot_fill")

    graph.add_conditional_edges(
        "slot_fill",
        # 有 pending_intent 说明上一轮在等用户补参数，本轮跳过重新分类。
        lambda state: "skip_classify" if state.get("pending_intent") else "do_classify",
        {
            "skip_classify": "check_slots",
            "do_classify": "classify_intent",
        },
    )

    graph.add_conditional_edges(
        "classify_intent",
        # 根据意图风险和置信度决定转人工、澄清还是进入槽位检查。
        route_after_classify,
        {
            "human_transfer": "human_transfer",
            "clarify": "clarify",
            "check_slots": "check_slots",
        },
    )

    graph.add_conditional_edges(
        "check_slots",
        # 槽位齐全的业务意图进入订单工具，否则继续澄清或直接生成回复。
        route_after_slots,
        {
            "clarify": "clarify",
            "business_tool": "lookup_order",
            "generate": "generate_reply",
        },
    )

    graph.add_edge("clarify", END)
    graph.add_edge("human_transfer", END)
    graph.add_edge("lookup_order", "generate_reply")
    graph.add_edge("knowledge", END)
    graph.add_edge("ticket", END)
    graph.add_edge("generate_reply", END)

    return graph.compile()


chat_graph = build_chat_graph()


def _need_human(intent: str) -> bool:
    """API 响应中的 need_human 标记。"""
    return intent in {"transfer_human", "complaint"}


async def run_chat_graph(
    user_id: str,
    message: str,
    conversation_id: Optional[str],
    channel: str,
    conversation_context: Optional[dict] = None,
) -> AIResponse:
    """外部调用入口：运行 LangGraph，并把最终 state 转换成 API 响应模型。"""
    log.info(f"[graph] START user={user_id} msg={message!r} conv={conversation_id}")
    initial_state: dict[str, Any] = {
        "user_id": user_id,
        "message": message,
        "conversation_id": conversation_id,
        "channel": channel,
        "conversation_context": conversation_context or {},
    }

    result = await chat_graph.ainvoke(initial_state)

    log.info(f"[graph] END intent={result.get('intent')} conf={result.get('confidence')} route={result.get('route')} reply={result.get('reply', '')[:60]}")

    pending = result.get("pending_intent")
    missing = result.get("missing_slots", [])

    # 只有仍然缺槽位时，才把 pending 状态返回给 API 层保存到会话中。
    return AIResponse(
        reply=result["reply"],
        reply_type="text",
        cards=[],
        intent=result["intent"],
        confidence=result["confidence"],
        need_human=_need_human(result["intent"]),
        risk_level=result.get("risk_level", "low"),
        trace_id=result.get("trace_id"),
        route=result.get("route"),
        ticket_id=result.get("ticket_id"),
        tools_used=result.get("tools_used", []),
        sources=result.get("sources", []),
        pending_intent=pending if missing else None,
        missing_slots=missing if pending else [],
        slots=result.get("slots", {}),
    )
