from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.order_service import extract_order_no

RiskLevel = str  # "low" | "medium" | "high"

INTENTS = (
    "check_order",
    "check_logistics",
    "refund",
    "invoice",
    "modify_address",
    "complaint",
    "transfer_human",
    "unknown",
)

INTENT_SLOTS: dict[str, dict[str, tuple[str, bool]]] = {
    "check_order": {"order_id": ("订单号", True)},
    "check_logistics": {"order_id": ("订单号", True)},
    "refund": {"order_id": ("订单号", True), "reason": ("退款原因", False)},
    "invoice": {"order_id": ("订单号", True), "invoice_type": ("发票类型", False)},
    "modify_address": {"order_id": ("订单号", True), "new_address": ("新地址", True)},
    "complaint": {"reason": ("投诉原因", True)},
    "transfer_human": {},
    "unknown": {},
}

SLOT_CLARIFY_QUESTIONS: dict[str, str] = {
    "order_id": "请提供您的订单号（格式：ORD-XXXXXXXX-XXXX）。",
    "new_address": "请提供您要修改的新收货地址。",
    "reason": "请描述一下具体原因。",
    "invoice_type": "请问您需要个人发票还是企业发票？",
}

TRANSFER_KEYWORDS = ("转人工", "人工", "真人", "客服接待", "人工客服")
COMPLAINT_KEYWORDS = ("投诉", "差评", "举报", "监管", "消协")
HIGH_RISK_KEYWORDS = (
    "赔偿", "起诉", "律师", "法律", "隐私", "泄露", "盗刷", "支付异常", "欺诈", "诈骗",
)
REFUND_KEYWORDS = ("退款", "退钱", "返钱", "到账", "退货", "换货")
LOGISTICS_KEYWORDS = ("物流", "快递", "运单", "签收", "配送")
ORDER_KEYWORDS = ("订单", "发货", "下单", "付款", "支付", "订单状态")
INVOICE_KEYWORDS = ("发票", "开票", "发票抬头")
MODIFY_ADDRESS_KEYWORDS = ("修改地址", "改地址", "换地址", "地址改一下")
DATE_KEYWORDS = ("星期几", "周几", "今天几号")


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    slots: dict[str, str] = field(default_factory=dict)
    risk_level: RiskLevel = "low"
    source: str = "rule"
    reason: str = ""


def _contains_any(message: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in message for kw in keywords)


def classify_by_rules(message: str) -> Optional[IntentResult]:
    normalized = message.lower()
    order_no = extract_order_no(message)

    if _contains_any(normalized, TRANSFER_KEYWORDS):
        return IntentResult(
            intent="transfer_human", confidence=0.95,
            slots={"order_id": order_no} if order_no else {},
            risk_level="medium", reason="transfer_keyword",
        )

    if _contains_any(normalized, COMPLAINT_KEYWORDS) or _contains_any(normalized, HIGH_RISK_KEYWORDS):
        return IntentResult(
            intent="complaint", confidence=0.92,
            slots={"order_id": order_no} if order_no else {},
            risk_level="high", reason="complaint_or_high_risk",
        )

    if _contains_any(normalized, REFUND_KEYWORDS):
        slots = {}
        if order_no:
            slots["order_id"] = order_no
        return IntentResult(
            intent="refund", confidence=0.88 if order_no else 0.85,
            slots=slots, reason="refund_keyword",
        )

    if _contains_any(normalized, LOGISTICS_KEYWORDS):
        slots = {}
        if order_no:
            slots["order_id"] = order_no
        return IntentResult(
            intent="check_logistics", confidence=0.86 if order_no else 0.80,
            slots=slots, reason="logistics_keyword",
        )

    if _contains_any(normalized, INVOICE_KEYWORDS):
        slots = {}
        if order_no:
            slots["order_id"] = order_no
        return IntentResult(
            intent="invoice", confidence=0.85 if order_no else 0.75,
            slots=slots, reason="invoice_keyword",
        )

    if _contains_any(normalized, MODIFY_ADDRESS_KEYWORDS):
        slots = {}
        if order_no:
            slots["order_id"] = order_no
        return IntentResult(
            intent="modify_address", confidence=0.85 if order_no else 0.75,
            slots=slots, reason="modify_address_keyword",
        )

    if order_no or _contains_any(normalized, ORDER_KEYWORDS):
        return IntentResult(
            intent="check_order", confidence=0.90 if order_no else 0.80,
            slots={"order_id": order_no} if order_no else {},
            reason="order_keyword_or_number",
        )

    return None


def extract_slots_from_message(message: str, slot_names: list[str]) -> dict[str, str]:
    filled: dict[str, str] = {}
    if "order_id" in slot_names:
        order_id = extract_order_no(message)
        if order_id:
            filled["order_id"] = order_id
    return filled


async def classify_intent(
    message: str,
    pending_intent: Optional[str] = None,
    missing_slots: Optional[list[str]] = None,
    existing_slots: Optional[dict[str, str]] = None,
) -> IntentResult:
    """识别用户消息的客服意图，并尽量抽取业务槽位。

    message: 当前用户输入。
    pending_intent: 上一轮已经识别出的意图；存在时表示当前处于多轮补槽流程。
    missing_slots: 上一轮还缺少的必填槽位，例如 order_id、new_address。
    existing_slots: 已经收集到的槽位，本轮会在此基础上合并新增槽位。
    """

    # 1. 多轮补槽：上一轮已经确定意图时，本轮只尝试补齐缺失参数，不重新判断意图。
    if pending_intent and missing_slots:
        # 先用结构化规则抽槽位。目前主要支持从文本里抽订单号。
        filled = extract_slots_from_message(message, missing_slots)
        merged = {**(existing_slots or {}), **filled}

        # 如果没有抽到结构化槽位，就把用户原文作为第一个缺失槽位的值。
        # 这适合地址、原因等自由文本；订单号等强格式字段后续仍建议再做校验。
        if not filled and missing_slots:
            first_missing = missing_slots[0]
            merged[first_missing] = message.strip()

        # 计算补槽后是否仍有必填项缺失。当前返回值里不直接使用，
        # 调用方 chat_graph._calc_missing 会再次计算并决定是否继续追问。
        slot_schema = INTENT_SLOTS.get(pending_intent, {})
        still_missing = [
            name for name, (_, required) in slot_schema.items()
            if required and not merged.get(name)
        ]

        # 补槽场景下沿用上一轮意图，并标记来源为 slot_fill，方便日志和链路追踪。
        return IntentResult(
            intent=pending_intent,
            confidence=0.9,
            slots=merged,
            source="slot_fill",
            reason="multi_turn_slot_fill",
        )

    # 2. 规则识别快速路径：优先用关键词和订单号判断，成本低、延迟小。
    rule_result = classify_by_rules(message)
    if rule_result is not None:
        return rule_result

    # 3. LLM 兜底：规则没有命中时，再调用模型做开放式意图分类。
    import logging
    _log = logging.getLogger(__name__)
    _log.info(f"[intent] rule miss, invoking LLM for: {message!r}")
    try:
        from app.services.ai_client import classify_via_llm
        llm_result = await classify_via_llm(message)
        _log.info(f"[intent] LLM result: intent={llm_result.intent}, conf={llm_result.confidence}, source={llm_result.source}, reason={llm_result.reason}")
        # 防御模型返回未定义 intent，避免后续路由遇到未知枚举值。
        if llm_result.intent not in INTENTS:
            llm_result = IntentResult(
                intent="unknown", confidence=0.3, source="llm", reason="invalid_intent_fallback",
            )
        return llm_result
    except Exception as e:
        # 模型调用失败时降级为 unknown，让后续流程走低置信度/转人工等兜底分支。
        import logging
        logging.getLogger(__name__).warning(f"LLM classification failed: {e}")
        return IntentResult(
            intent="unknown", confidence=0.3, source="llm", reason=f"llm_error: {e}",
        )


def build_clarify_question(intent: str, missing_slots: list[str]) -> str:
    questions = [
        f"- {SLOT_CLARIFY_QUESTIONS.get(name, f'请提供{name}')}"
        for name in missing_slots
    ]
    return "我需要一些信息来帮您处理：\n" + "\n".join(questions)
