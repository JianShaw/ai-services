from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Order, OrderItem


MOCK_ORDERS = [
    {
        "id": "order_mock_001",
        "order_no": "ORD-20260508-0001",
        "user_id": "123456",
        "status": "shipped",
        "payment_status": "paid",
        "logistics_status": "in_transit",
        "tracking_no": "SF1234567890",
        "carrier": "顺丰速运",
        "refund_status": "none",
        "total_amount": 299.0,
        "currency": "CNY",
        "shipping_address": "北京市朝阳区建国路88号",
        "created_at": datetime.utcnow() - timedelta(days=2),
        "items": [
            {
                "id": "order_item_mock_001",
                "product_name": "无线蓝牙耳机",
                "sku": "SKU-BT-001",
                "quantity": 1,
                "unit_price": 299.0,
            }
        ],
    },
    {
        "id": "order_mock_002",
        "order_no": "ORD-20260507-0002",
        "user_id": "123456",
        "status": "paid",
        "payment_status": "paid",
        "logistics_status": "pending",
        "tracking_no": None,
        "carrier": None,
        "refund_status": "none",
        "total_amount": 1580.0,
        "currency": "CNY",
        "shipping_address": "上海市浦东新区陆家嘴环路1000号",
        "created_at": datetime.utcnow() - timedelta(hours=6),
        "items": [
            {
                "id": "order_item_mock_002a",
                "product_name": "智能手表 Pro",
                "sku": "SKU-SW-002",
                "quantity": 1,
                "unit_price": 1299.0,
            },
            {
                "id": "order_item_mock_002b",
                "product_name": "钢化膜（两片装）",
                "sku": "SKU-FL-002",
                "quantity": 1,
                "unit_price": 39.0,
            },
            {
                "id": "order_item_mock_002c",
                "product_name": "硅胶表带 黑色",
                "sku": "SKU-SB-002",
                "quantity": 1,
                "unit_price": 242.0,
            },
        ],
    },
    {
        "id": "order_mock_003",
        "order_no": "ORD-20260505-0003",
        "user_id": "123456",
        "status": "shipped",
        "payment_status": "paid",
        "logistics_status": "delivered",
        "tracking_no": "JD9876543210",
        "carrier": "京东物流",
        "refund_status": "processing",
        "total_amount": 89.9,
        "currency": "CNY",
        "shipping_address": "广州市天河区天河路385号",
        "created_at": datetime.utcnow() - timedelta(days=7),
        "items": [
            {
                "id": "order_item_mock_003",
                "product_name": "保温杯 500ml",
                "sku": "SKU-CP-003",
                "quantity": 1,
                "unit_price": 89.9,
            }
        ],
    },
    {
        "id": "order_mock_004",
        "order_no": "ORD-20260501-0004",
        "user_id": "123456",
        "status": "paid",
        "payment_status": "paid",
        "logistics_status": "in_transit",
        "tracking_no": "YT6688992211",
        "carrier": "圆通速递",
        "refund_status": "completed",
        "total_amount": 4599.0,
        "currency": "CNY",
        "shipping_address": "深圳市南山区科技园南路1号",
        "created_at": datetime.utcnow() - timedelta(days=8),
        "items": [
            {
                "id": "order_item_mock_004",
                "product_name": "笔记本电脑 14寸",
                "sku": "SKU-NB-004",
                "quantity": 1,
                "unit_price": 4599.0,
            }
        ],
    },
    {
        "id": "order_mock_005",
        "order_no": "ORD-20260428-0005",
        "user_id": "123456",
        "status": "shipped",
        "payment_status": "paid",
        "logistics_status": "delivered",
        "tracking_no": "ZT1122334455",
        "carrier": "中通快递",
        "refund_status": "none",
        "total_amount": 45.0,
        "currency": "CNY",
        "shipping_address": "成都市武侯区天府大道999号",
        "created_at": datetime.utcnow() - timedelta(days=11),
        "items": [
            {
                "id": "order_item_mock_005a",
                "product_name": "手机壳 透明",
                "sku": "SKU-CA-005",
                "quantity": 2,
                "unit_price": 15.0,
            },
            {
                "id": "order_item_mock_005b",
                "product_name": "数据线 Type-C",
                "sku": "SKU-CB-005",
                "quantity": 1,
                "unit_price": 15.0,
            },
        ],
    },
]


async def seed_mock_orders(session: AsyncSession) -> list[str]:
    seeded_order_numbers: list[str] = []

    for source_order in MOCK_ORDERS:
        order_data = {key: value for key, value in source_order.items() if key != "items"}
        item_data = source_order["items"]

        order = await session.get(Order, order_data["id"])
        if order is None:
            order = Order(**order_data)
            session.add(order)
        else:
            for key, value in order_data.items():
                setattr(order, key, value)

        seeded_order_numbers.append(order_data["order_no"])

        existing_items = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order_data["id"])
        )
        for existing_item in existing_items.scalars().all():
            await session.delete(existing_item)

        for item in item_data:
            session.add(OrderItem(order_id=order_data["id"], **item))

    await session.commit()
    return seeded_order_numbers
