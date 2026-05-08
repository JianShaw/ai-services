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
async def test_chat_conversation_and_message_flow(client):
    conversation_payload = {
        "conversation_id": "conv_e2e_001",
        "user_id": "user_e2e_001",
        "channel": "web",
    }

    create_response = await client.post("/chat/conversations", json=conversation_payload)
    detail_response = await client.get("/chat/conversations/conv_e2e_001")
    messages_response = await client.get("/chat/conversations/conv_e2e_001/messages")
    send_response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_e2e_001",
            "user_id": "user_e2e_001",
            "message": "我想查询订单状态",
            "channel": "web",
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "active"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "conv_e2e_001"
    assert messages_response.status_code == 200
    assert messages_response.json() == []
    assert send_response.status_code == 200
    body = send_response.json()
    assert body["reply_type"] == "text"
    assert body["intent"] == "order_query"
    assert body["confidence"] >= 0.8
    assert body["need_human"] is False


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
async def test_chat_uses_deepseek_reply_when_available(client, monkeypatch):
    async def fake_reply(user_message, intent, conversation_id):
        assert user_message == "你好，我想了解售后政策"
        assert intent == "unknown"
        assert conversation_id == "conv_ai_001"
        return "这是来自 DeepSeek 的测试回复。"

    monkeypatch.setattr(chat_graph.deepseek_client, "reply", fake_reply)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": "conv_ai_001",
            "user_id": "user_ai_001",
            "message": "你好，我想了解售后政策",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "这是来自 DeepSeek 的测试回复。"
    assert body["intent"] == "unknown"


@pytest.mark.asyncio
async def test_chat_request_validation(client):
    response = await client.post(
        "/chat/messages",
        json={"user_id": "user_e2e_003", "channel": "web"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_actions(client):
    transfer_response = await client.post(
        "/chat/conversations/conv_e2e_001/transfer",
        params={"reason": "customer_request"},
    )
    rate_response = await client.post(
        "/chat/messages/msg_e2e_001/rate",
        params={"rating": "good"},
    )

    assert transfer_response.status_code == 200
    assert transfer_response.json() == {"success": True}
    assert rate_response.status_code == 200
    assert rate_response.json() == {"success": True}


@pytest.mark.asyncio
async def test_agent_workspace_endpoints(client):
    endpoints = [
        ("GET", "/agent/conversations"),
        ("POST", "/agent/takeover"),
        ("POST", "/agent/reply"),
        ("GET", "/agent/tickets"),
        ("POST", "/agent/tickets"),
    ]

    for method, path in endpoints:
        response = await client.request(method, path)
        assert response.status_code == 200
        assert "message" in response.json()


@pytest.mark.asyncio
async def test_admin_endpoints(client):
    stats_response = await client.get("/admin/stats")
    knowledge_response = await client.get("/admin/knowledge/documents")
    upload_response = await client.post("/admin/knowledge/documents")
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
    for response in [
        knowledge_response,
        upload_response,
        intents_response,
        scripts_response,
    ]:
        assert response.status_code == 200
        assert "message" in response.json()
