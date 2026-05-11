from typing import Optional

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.services.intent_service import IntentResult, INTENTS

log = logging.getLogger(__name__)


class AIClientError(RuntimeError):
    pass


# --- LLM intent classification via langchain-openai ---

CLASSIFY_SYSTEM_PROMPT = (
    "你是客服意图分类器。从以下意图列表中选择最合适的一个：\n"
    "- check_order: 查订单状态、订单信息\n"
    "- check_logistics: 查物流、快递、配送状态\n"
    "- refund: 退款、退货、换货\n"
    "- invoice: 要发票、开票\n"
    "- modify_address: 修改收货地址\n"
    "- complaint: 投诉、不满、举报\n"
    "- transfer_human: 明确要求转人工、找真人客服\n"
    "- knowledge_query: 询问工作时间、退货规则、商品材质、企业文化、会员积分、保修售后、发货配送等通用知识问题\n"
    "- unknown: 无法判断意图\n\n"
    "判断 knowledge_query 的标准：用户询问的是通用规则、政策或知识，而非特定订单的实时数据。\n"
    "同时提取消息中明确出现的槽位值（订单号、商品名等），不要猜测。\n"
    "你必须严格按以下JSON格式回复，不要输出其他内容：\n"
    '{{"intent":"意图名","confidence":0.0,"slots":{{"order_id":"","product_name":""}}}}'
)

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CLASSIFY_SYSTEM_PROMPT),
    ("user", "客户消息：{message}"),
])


REPLY_SYSTEM_PROMPT = (
    "你是一名专业的电商客服助手。你的职责是根据用户的问题给出准确、友好的回复。\n\n"
    "规则：\n"
    "- 用简洁自然的中文回复，不要使用机械模板话术\n"
    "- 不要编造订单状态、物流信息、退款进度等数据\n"
    "- 如果缺少关键信息（如订单号），礼貌地请用户提供\n"
    "- 涉及退款、投诉等敏感问题，表达同理心并主动提供解决方案\n"
    "- 回复控制在 3 句话以内，避免冗长\n"
    "- 不要使用表情符号，不要假设用户在测试，始终保持专业客服态度\n"
)

REPLY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", REPLY_SYSTEM_PROMPT),
    (
        "user",
        (
            "当前意图：{intent}\n"
            "对话历史：\n{history}\n"
            "用户消息：{message}"
        ),
    ),
])


def _get_classify_llm():
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.0,
        request_timeout=settings.ai_request_timeout,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _get_reply_llm():
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.7,
        request_timeout=settings.ai_request_timeout,
    )


def _parse_classification(raw: str) -> IntentResult:
    import json
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return IntentResult(intent="unknown", confidence=0.3, source="llm", reason="json_parse_error")

    intent = str(data.get("intent", "unknown"))
    if intent not in INTENTS:
        intent = "unknown"
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    slots = data.get("slots", {})
    if not isinstance(slots, dict):
        slots = {}

    return IntentResult(
        intent=intent,
        confidence=confidence,
        slots={str(k): str(v) for k, v in slots.items()},
        source="llm",
        reason="llm_classification",
    )


def _parse_reply(raw: str) -> str:
    """解析 LLM 回复。优先尝试 JSON 格式兼容旧逻辑，否则直接使用原文。"""
    import json
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            reply = data.get("reply")
            if isinstance(reply, str) and reply.strip():
                return reply.strip()
        except (json.JSONDecodeError, TypeError):
            pass
    if not stripped:
        raise AIClientError("AI returned empty response") from None
    return stripped


def _format_history(history: Optional[list[dict]]) -> str:
    if not history:
        return "(无历史对话)"

    lines = []
    for item in history[-10:]:
        sender = item.get("sender_type") or item.get("sender") or "unknown"
        sender_label = "用户" if sender == "user" else "客服"
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        meta = item.get("meta_data") or {}
        intent = meta.get("intent")
        route = meta.get("route")
        suffix = ""
        if intent:
            suffix += f" [意图:{intent}]"
        if route:
            suffix += f" [路由:{route}]"
        lines.append(f"{sender_label}: {content}{suffix}")
    return "\n".join(lines) if lines else "(无历史对话)"


async def classify_via_llm(message: str) -> IntentResult:
    """通过 LLM 对用户消息进行意图分类。

    当规则匹配未命中时，作为兜底分类手段调用。
    使用 LangChain LCEL 管道语法：CLASSIFY_PROMPT | LLM，
    执行流程为 {"message": ...} → 模板渲染 → LLM 调用 → 返回 AIMessage。
    """
    import logging
    _log = logging.getLogger(__name__)
    if not settings.openai_api_key:
        _log.warning("[llm] no API key configured, skipping LLM classification")
        return IntentResult(
            intent="unknown", confidence=0.3, source="llm", reason="no_api_key",
        )

    # LCEL 管道：输入 dict → ChatPromptTemplate 渲染 → ChatOpenAI 调用 → AIMessage
    chain = CLASSIFY_PROMPT | _get_classify_llm()
    _log.info(f"[llm] calling classify for: {message!r}")
    response = await chain.ainvoke({"message": message})

    raw = response.content if hasattr(response, "content") else str(response)
    _log.info(f"[llm] raw response: {raw!r}")
    return _parse_classification(raw)


async def reply_via_llm(
    user_message: str,
    intent: str,
    conversation_id: Optional[str],
    history: Optional[list[dict]] = None,
) -> str:
    """通过 LLM 生成兜底回复。

    当订单查询无结果或意图无法匹配具体业务时调用。
    LCEL 管道同上：REPLY_PROMPT | LLM。
    """
    if not settings.openai_api_key:
        raise AIClientError("OPENAI_API_KEY is not configured")

    try:
        log.info(
            "[reply_llm_client] CALL model=%s base_url=%s conv=%s intent=%s msg=%r",
            settings.model_name,
            settings.openai_base_url,
            conversation_id or "new",
            intent,
            user_message,
        )
        formatted_history = _format_history(history)
        log.info("[reply_llm_client] HISTORY %r", formatted_history)
        chain = REPLY_PROMPT | _get_reply_llm()
        response = await chain.ainvoke({
            "intent": intent,
            "history": formatted_history,
            "message": user_message,
        })
    except Exception as exc:
        log.exception(
            "[reply_llm_client] CALL_FAILED model=%s base_url=%s conv=%s intent=%s",
            settings.model_name,
            settings.openai_base_url,
            conversation_id or "new",
            intent,
        )
        raise AIClientError(f"{type(exc).__name__}: {exc}") from exc

    raw = response.content if hasattr(response, "content") else str(response)
    log.info("[reply_llm_client] RAW_RESPONSE %r", raw)
    try:
        return _parse_reply(raw)
    except AIClientError:
        log.exception("[reply_llm_client] PARSE_FAILED raw=%r", raw)
        raise
