import re
from typing import Any, Optional

from sqlalchemy import select

from app.models.database import Order, OrderItem, async_session_maker


ORDER_NO_PATTERN = re.compile(r"\bORD-\d{8}-\d{4}\b", re.IGNORECASE)


def extract_order_no(message: str) -> Optional[str]:
    match = ORDER_NO_PATTERN.search(message)
    return match.group(0).upper() if match else None


async def get_order_snapshot(order_no: str, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    async with async_session_maker() as session:
        query = select(Order).where(Order.order_no == order_no)
        if user_id:
            query = query.where(Order.user_id == user_id)

        order_result = await session.execute(
            query
        )
        order = order_result.scalar_one_or_none()
        if order is None:
            return None

        item_result = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id.asc())
        )
        items = item_result.scalars().all()

        return {
            "order_no": order.order_no,
            "user_id": order.user_id,
            "status": order.status,
            "payment_status": order.payment_status,
            "logistics_status": order.logistics_status,
            "tracking_no": order.tracking_no,
            "carrier": order.carrier,
            "refund_status": order.refund_status,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "shipping_address": order.shipping_address,
            "items": [
                {
                    "product_name": item.product_name,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in items
            ],
        }


def format_order_reply(order: dict[str, Any]) -> str:
    logistics_map = {
        "pending": "待发货",
        "in_transit": "运输中",
        "delivered": "已签收",
    }
    status_map = {
        "paid": "已付款",
        "shipped": "已发货",
        "refunding": "退款处理中",
    }
    refund_map = {
        "none": "无退款",
        "processing": "退款处理中",
        "completed": "退款已完成",
    }

    item_text = "、".join(
        f"{item['product_name']} x{item['quantity']}" for item in order["items"]
    )
    carrier_text = order["carrier"] or "暂无承运商"
    tracking_text = order["tracking_no"] or "暂无运单号"

    return (
        f"查到了，订单 {order['order_no']} 当前状态是"
        f"{status_map.get(order['status'], order['status'])}，物流状态是"
        f"{logistics_map.get(order['logistics_status'], order['logistics_status'])}。"
        f"承运商：{carrier_text}；运单号：{tracking_text}。"
        f"退款状态：{refund_map.get(order['refund_status'], order['refund_status'])}。"
        f"商品：{item_text}；订单金额：{order['total_amount']:.2f} {order['currency']}。"
    )


def format_logistics_reply(order: dict[str, Any]) -> str:
    logistics_map = {
        "pending": "待发货",
        "in_transit": "运输中",
        "delivered": "已签收",
    }
    carrier_text = order["carrier"] or "暂无承运商"
    tracking_text = order["tracking_no"] or "暂无运单号"

    return (
        f"订单 {order['order_no']} 的物流状态是"
        f"{logistics_map.get(order['logistics_status'], order['logistics_status'])}。"
        f"承运商：{carrier_text}；运单号：{tracking_text}。"
    )


def format_refund_reply(order: dict[str, Any]) -> str:
    refund_map = {
        "none": "无退款",
        "processing": "退款处理中",
        "completed": "退款已完成",
    }

    return (
        f"订单 {order['order_no']} 的退款状态是"
        f"{refund_map.get(order['refund_status'], order['refund_status'])}。"
        "如果状态长时间没有变化，我可以继续帮您转人工核实。"
    )
