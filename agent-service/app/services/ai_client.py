from typing import Optional

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.services.intent_service import IntentResult, INTENTS


class AIClientError(RuntimeError):
    pass


class DeepSeekChatClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model_name = model_name or settings.model_name
        self.timeout = timeout or settings.ai_request_timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def reply(self, user_message: str, intent: str, conversation_id: Optional[str]) -> str:
        if not self.is_configured:
            raise AIClientError("OPENAI_API_KEY is not configured")

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an enterprise customer service AI assistant. "
                        "Reply in concise, helpful Chinese. Ask for missing order "
                        "numbers when needed. Do not invent order status, logistics, "
                        "refund progress, or account data."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Conversation ID: {conversation_id or 'new'}\n"
                        f"Detected intent: {intent}\n"
                        f"Customer message: {user_message}"
                    ),
                },
            ],
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIClientError(str(exc)) from exc

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("AI response did not include a chat message") from exc

        return content.strip()


deepseek_client = DeepSeekChatClient()


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
    "- unknown: 无法判断意图\n\n"
    "同时提取消息中明确出现的槽位值（订单号、商品名等），不要猜测。\n"
    "你必须严格按以下JSON格式回复，不要输出其他内容：\n"
    '{{"intent":"意图名","confidence":0.0,"slots":{{"order_id":"","product_name":""}}}}'
)

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CLASSIFY_SYSTEM_PROMPT),
    ("user", "客户消息：{message}"),
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


async def classify_via_llm(message: str) -> IntentResult:
    import logging
    _log = logging.getLogger(__name__)
    if not settings.openai_api_key:
        _log.warning("[llm] no API key configured, skipping LLM classification")
        return IntentResult(
            intent="unknown", confidence=0.3, source="llm", reason="no_api_key",
        )

    chain = CLASSIFY_PROMPT | _get_classify_llm()
    _log.info(f"[llm] calling classify for: {message!r}")
    response = await chain.ainvoke({"message": message})

    raw = response.content if hasattr(response, "content") else str(response)
    _log.info(f"[llm] raw response: {raw!r}")
    return _parse_classification(raw)
