"""Quick test: rule vs LLM intent classification."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from app.services.intent_service import classify_by_rules, classify_intent

    test_messages = [
        "我要退款",
        "查物流",
        "钱什么时候退回来",
        "那我还能问你些什么呢",
        "ORD-20260508-0001 订单到哪了",
    ]

    for msg in test_messages:
        print(f"\n--- 输入: {msg!r} ---")

        # 1. Rule layer
        rule = classify_by_rules(msg)
        if rule:
            print(f"  [rule]  intent={rule.intent}  conf={rule.confidence}  slots={rule.slots}")
        else:
            print(f"  [rule]  未命中")

        # 2. Full pipeline (rule → LLM)
        result = await classify_intent(msg)
        print(f"  [full]  intent={result.intent}  conf={result.confidence}  source={result.source}  reason={result.reason}")


if __name__ == "__main__":
    asyncio.run(main())
