import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_e2e.db"
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"
os.environ["MODEL_NAME"] = "deepseek-v4-flash"

from app.graph import chat_graph
from app.main import app
from app.models.database import Base, engine
from app.services.order_seed import seed_mock_orders


@pytest.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_health_and_root_endpoints(client):
    root_response = await client.get("/")
    health_response = await client.get("/health")

    assert root_response.status_code == 200
    assert root_response.json() == {
        "service": "AI Customer Service Agent",
        "version": "0.1.0",
        "status": "running",
    }
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_chat_conversation_and_message_flow_persists_history(client):
    conversation_payload = {
        "conversation_id": "conv_e2e_001",
        "user_id": "user_e2e_001",
        "channel": "web",
    }

    create_response = await client.post("/chat/conversations", json=conversation_payload)
    send_response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_e2e_001",
            "user_id": "user_e2e_001",
            "message": "我想查询订单状态",
            "channel": "web",
        },
    )
    detail_response = await client.get("/chat/conversations/conv_e2e_001")
    messages_response = await client.get("/chat/conversations/conv_e2e_001/messages")

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "active"
    assert create_response.json()["userId"] == "user_e2e_001"

    assert send_response.status_code == 200
    body = send_response.json()
    assert body["reply_type"] == "text"
    assert body["intent"] == "order_query"
    assert body["confidence"] >= 0.8
    assert body["need_human"] is False

    assert detail_response.status_code == 200
    conversation = detail_response.json()
    assert conversation["id"] == "conv_e2e_001"
    assert conversation["currentIntent"] == "order_query"

    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 2
    assert messages[0]["senderType"] == "user"
    assert messages[0]["content"] == "我想查询订单状态"
    assert messages[1]["senderType"] == "ai"
    assert messages[1]["metadata"]["intent"] == "order_query"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_intent", "need_human"),
    [
        ("退款什么时候到账", "refund_query", False),
        ("我要转人工客服", "human_request", True),
        ("帮我查一下物流", "logistics_query", False),
        ("你好", "unknown", False),
    ],
)
async def test_chat_intent_routing(client, message, expected_intent, need_human):
    response = await client.post(
        "/chat/messages",
        json={"user_id": "user_e2e_002", "message": message, "channel": "web"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == expected_intent
    assert body["need_human"] is need_human
    assert isinstance(body["reply"], str)
    assert body["reply"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_intent", "need_human", "risk_level"),
    [
        ("我要人工查订单 ORD-20260508-0001", "human_request", True, "medium"),
        ("我要投诉并要求赔偿", "complaint", True, "high"),
        ("退款订单 ORD-20260508-0003", "refund_query", False, "low"),
        ("物流 ORD-20260508-0001", "logistics_query", False, "low"),
    ],
)
async def test_chat_intent_priority_and_risk_routing(
    client, message, expected_intent, need_human, risk_level
):
    response = await client.post(
        "/chat/messages",
        json={"user_id": "user_demo_001", "message": message, "channel": "web"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == expected_intent
    assert body["need_human"] is need_human
    assert body["risk_level"] == risk_level


@pytest.mark.asyncio
async def test_chat_uses_deepseek_reply_when_available(client, monkeypatch):
    async def fake_reply(user_message, intent, conversation_id):
        assert user_message == "你好，我有一个其他问题"
        assert intent == "unknown"
        assert conversation_id == "conv_ai_001"
        return "这是来自 DeepSeek 的测试回复。"

    monkeypatch.setattr(chat_graph.deepseek_client, "reply", fake_reply)

    response = await client.post(
        "/chat/messages",
            json={
                "conversation_id": "conv_ai_001",
                "user_id": "user_ai_001",
                "message": "你好，我有一个其他问题",
                "channel": "web",
            },
        )
    messages_response = await client.get("/chat/conversations/conv_ai_001/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "这是来自 DeepSeek 的测试回复。"
    assert body["intent"] == "unknown"
    assert messages_response.json()[1]["content"] == "这是来自 DeepSeek 的测试回复。"


@pytest.mark.asyncio
async def test_chat_can_lookup_mock_order(client):
    from app.models.database import async_session_maker

    async with async_session_maker() as session:
        await seed_mock_orders(session)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_order_001",
            "user_id": "user_demo_001",
            "message": "ORD-20260508-0001 看下这个订单什么时候发货",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_query"
    assert "ORD-20260508-0001" in body["reply"]
    assert "SF1234567890" in body["reply"]
    assert "运输中" in body["reply"]


@pytest.mark.asyncio
async def test_chat_does_not_expose_other_users_order(client):
    from app.models.database import async_session_maker

    async with async_session_maker() as session:
        await seed_mock_orders(session)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_order_forbidden_001",
            "user_id": "user_demo_001",
            "message": "ORD-20260508-0002 看下这个订单",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "order_query"
    assert "没有查询到订单 ORD-20260508-0002" in body["reply"]
    assert "AI Customer Service Pro Plan" not in body["reply"]


@pytest.mark.asyncio
async def test_chat_uses_specific_logistics_and_refund_tool_replies(client):
    from app.models.database import async_session_maker

    async with async_session_maker() as session:
        await seed_mock_orders(session)

    logistics_response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_logistics_001",
            "user_id": "user_demo_001",
            "message": "物流 ORD-20260508-0001",
            "channel": "web",
        },
    )
    refund_response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_refund_001",
            "user_id": "user_demo_001",
            "message": "退款订单 ORD-20260508-0003",
            "channel": "web",
        },
    )

    assert logistics_response.status_code == 200
    logistics_body = logistics_response.json()
    assert logistics_body["intent"] == "logistics_query"
    assert "物流状态" in logistics_body["reply"]
    assert "SF1234567890" in logistics_body["reply"]

    assert refund_response.status_code == 200
    refund_body = refund_response.json()
    assert refund_body["intent"] == "refund_query"
    assert "退款状态" in refund_body["reply"]
    assert "退款处理中" in refund_body["reply"]


@pytest.mark.asyncio
async def test_agent_ticket_endpoints_persist_tickets(client):
    create_response = await client.post(
        "/agent/tickets",
        json={
            "conversation_id": "conv_ticket_001",
            "user_id": "user_ticket_001",
            "type": "after_sales",
            "priority": "high",
            "description": "商品损坏，需要售后处理",
        },
    )
    list_response = await client.get("/agent/tickets")

    assert create_response.status_code == 201
    ticket = create_response.json()
    assert ticket["conversationId"] == "conv_ticket_001"
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"

    assert list_response.status_code == 200
    tickets = list_response.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == ticket["id"]


@pytest.mark.asyncio
async def test_admin_can_upload_and_list_knowledge_documents(client):
    upload_response = await client.post(
        "/admin/knowledge/documents",
        json={
            "title": "售后政策",
            "source_type": "faq",
            "version": "v1",
            "chunks": [
                {
                    "content": "保修期为一年。用户可以凭订单号申请售后维修。",
                    "metadata": {"category": "after_sales"},
                }
            ],
        },
    )
    list_response = await client.get("/admin/knowledge/documents")

    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["title"] == "售后政策"
    assert document["chunkCount"] == 1

    assert list_response.status_code == 200
    documents = list_response.json()
    assert len(documents) == 1
    assert documents[0]["id"] == document["id"]


@pytest.mark.asyncio
async def test_chat_answers_faq_from_knowledge_base(client):
    await client.post(
        "/admin/knowledge/documents",
        json={
            "title": "售后政策",
            "source_type": "faq",
            "chunks": [
                {
                    "content": "保修期为一年。用户可以凭订单号申请售后维修。",
                    "metadata": {"category": "after_sales"},
                }
            ],
        },
    )

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_faq_001",
            "user_id": "user_faq_001",
            "message": "保修期多久",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "faq"
    assert "保修期为一年" in body["reply"]
    assert body["sources"]
    assert body["sources"][0]["title"] == "售后政策"


@pytest.mark.asyncio
async def test_chat_faq_without_knowledge_does_not_invent_answer(client):
    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_faq_missing_001",
            "user_id": "user_faq_002",
            "message": "会员权益有哪些",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "faq"
    assert "暂时没有在知识库中找到" in body["reply"]
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_chat_response_includes_trace_route_and_tools_metadata(client):
    from app.models.database import async_session_maker

    async with async_session_maker() as session:
        await seed_mock_orders(session)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_trace_001",
            "user_id": "user_demo_001",
            "message": "物流 ORD-20260508-0001",
            "channel": "web",
        },
    )
    messages_response = await client.get("/chat/conversations/conv_trace_001/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"]
    assert body["route"] == "business_tool"
    assert body["tools_used"] == ["get_order_snapshot"]

    ai_message = messages_response.json()[1]
    assert ai_message["metadata"]["traceId"] == body["trace_id"]
    assert ai_message["metadata"]["route"] == "business_tool"
    assert ai_message["metadata"]["toolsUsed"] == ["get_order_snapshot"]


@pytest.mark.asyncio
async def test_after_sales_route_creates_ticket(client):
    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_after_sales_001",
            "user_id": "user_after_sales_001",
            "message": "商品损坏，需要售后处理",
            "channel": "web",
        },
    )
    tickets_response = await client.get("/agent/tickets")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "after_sales"
    assert body["route"] == "ticket"
    assert body["ticket_id"]
    assert "工单" in body["reply"]

    tickets = tickets_response.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == body["ticket_id"]


@pytest.mark.asyncio
async def test_chat_answers_date_query_without_model_call(client):
    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_date_001",
            "user_id": "user_date_001",
            "message": "今天星期几",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "date_query"
    assert "星期" in body["reply"]


@pytest.mark.asyncio
async def test_chat_request_validation(client):
    response = await client.post(
        "/chat/messages",
        json={"user_id": "user_e2e_003", "channel": "web"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_actions_persist_transfer_and_rating(client):
    await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_e2e_001",
            "user_id": "user_e2e_001",
            "message": "我想查询订单状态",
            "channel": "web",
        },
    )
    messages = (await client.get("/chat/conversations/conv_e2e_001/messages")).json()
    ai_message_id = messages[1]["id"]

    transfer_response = await client.post(
        "/chat/conversations/conv_e2e_001/transfer",
        json={"reason": "customer_request"},
    )
    rate_response = await client.post(
        f"/chat/messages/{ai_message_id}/rate",
        json={"rating": "thumbsUp"},
    )

    assert transfer_response.status_code == 200
    assert transfer_response.json() == {"success": True}
    assert rate_response.status_code == 200
    assert rate_response.json() == {"success": True}

    conversation = (await client.get("/chat/conversations/conv_e2e_001")).json()
    persisted_messages = (await client.get("/chat/conversations/conv_e2e_001/messages")).json()

    assert conversation["status"] == "transferred"
    assert persisted_messages[1]["metadata"]["rating"] == "thumbsUp"
    assert persisted_messages[2]["senderType"] == "agent"
    assert persisted_messages[2]["metadata"]["event"] == "human_transfer"


@pytest.mark.asyncio
async def test_missing_conversation_returns_404(client):
    response = await client.get("/chat/conversations/missing/messages")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_workspace_endpoints(client):
    await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_agent_001",
            "user_id": "user_agent_001",
            "message": "我要转人工客服",
            "channel": "web",
        },
    )

    list_response = await client.get("/agent/conversations", params={"status": "transferred"})
    detail_response = await client.get("/agent/conversations/conv_agent_001")
    messages_response = await client.get("/agent/conversations/conv_agent_001/messages")

    takeover_response = await client.post(
        "/agent/takeover",
        json={"conversation_id": "conv_agent_001", "agent_id": "agent_001"},
    )
    reply_response = await client.post(
        "/agent/reply",
        json={
            "conversation_id": "conv_agent_001",
            "agent_id": "agent_001",
            "message": "您好，我是人工客服，已经接入。",
        },
    )
    final_messages_response = await client.get("/agent/conversations/conv_agent_001/messages")

    assert list_response.status_code == 200
    transferred = list_response.json()
    assert len(transferred) == 1
    assert transferred[0]["id"] == "conv_agent_001"
    assert transferred[0]["status"] == "transferred"

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "conv_agent_001"

    assert messages_response.status_code == 200
    assert len(messages_response.json()) == 2

    assert takeover_response.status_code == 200
    taken = takeover_response.json()
    assert taken["status"] == "assigned"
    assert taken["assignedAgentId"] == "agent_001"

    assert reply_response.status_code == 201
    reply = reply_response.json()
    assert reply["senderType"] == "agent"
    assert reply["content"] == "您好，我是人工客服，已经接入。"

    final_messages = final_messages_response.json()
    assert len(final_messages) == 3
    assert final_messages[-1]["senderType"] == "agent"


@pytest.mark.asyncio
async def test_admin_endpoints(client):
    stats_response = await client.get("/admin/stats")
    knowledge_response = await client.get("/admin/knowledge/documents")
    intents_response = await client.get("/admin/intents")
    scripts_response = await client.get("/admin/scripts")

    assert stats_response.status_code == 200
    assert stats_response.json() == {
        "totalConversations": 0,
        "aiResolutionRate": 0,
        "humanTransferRate": 0,
        "avgResponseTime": 0,
        "userSatisfaction": 0,
        "topQuestions": [],
    }
    assert knowledge_response.status_code == 200
    assert knowledge_response.json() == []
    for response in [intents_response, scripts_response]:
        assert response.status_code == 200
        assert "message" in response.json()
