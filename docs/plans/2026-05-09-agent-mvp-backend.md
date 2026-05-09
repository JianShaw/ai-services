# Agent MVP Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the demo customer-service chatbot into a testable MVP backend that matches the PRD's P0 path: intent routing, knowledge answers, order tools, human handoff, tickets, and conversation logs.

**Architecture:** Keep the existing Vue -> API Gateway -> FastAPI Agent Service shape. Implement the first real business layer in `agent-service`: deterministic safety/risk rules, LLM-assisted intent classification fallback, conditional LangGraph routes, SQLite-backed MVP knowledge retrieval, order/logistics/refund tools, ticket creation, and response metadata for traceability.

**Tech Stack:** FastAPI, LangGraph, SQLAlchemy async, SQLite for MVP business data, pytest/httpx for verification, Node/Express gateway pass-through.

---

## Scope

This plan intentionally implements the PRD's MVP backend spine first. It does not attempt full Qdrant RAG, full admin UI, full multi-channel access, scheduling, quality inspection, or production auth. Those remain P1/P2.

## Target Behavior

- User messages are saved.
- The Agent classifies intent into `faq`, `order_query`, `logistics_query`, `refund_query`, `after_sales`, `complaint`, `human_request`, or `unknown`.
- Explicit human requests and high-risk messages transfer to human.
- Order/logistics/refund questions call business data, not model guessing.
- FAQ questions retrieve knowledge chunks and only answer from retrieved content.
- After-sales questions can create tickets when enough information exists, otherwise ask for missing details.
- Every AI response records intent, confidence, need-human flag, trace id, route, tools used, risk level, and sources.

## Task 1: Planning And Baseline

**Files:**
- Create: `docs/plans/2026-05-09-agent-mvp-backend.md`
- Inspect: `agent-service/tests/e2e/test_agent_service_api.py`
- Inspect: `agent-service/app/graph/chat_graph.py`

**Steps:**
1. Save this implementation plan.
2. Run the current backend test suite.
3. Record baseline failures before feature work.

**Verification:**
- `python -m pytest tests -q` from `agent-service`.

## Task 2: Intent And Risk Foundation

**Files:**
- Create: `agent-service/app/services/intent_service.py`
- Modify: `agent-service/app/graph/chat_graph.py`
- Test: `agent-service/tests/e2e/test_agent_service_api.py`

**Steps:**
1. Add tests for priority routing:
   - "我要人工查订单" -> `human_request`, `need_human=True`.
   - "我要投诉并要求赔偿" -> `complaint`, `need_human=True`, high risk.
   - "退款订单 ORD-20260508-0001" -> `refund_query`, not generic order.
   - "物流 ORD-20260508-0001" -> `logistics_query`.
2. Implement an `IntentResult` dataclass with `intent`, `confidence`, `need_human`, `risk_level`, `reason`, and `order_no`.
3. Move keyword and order-number parsing out of `chat_graph.py`.
4. Add rule priority: human/risk first, refund/logistics second, order third, after-sales/faq/unknown after that.
5. Preserve deterministic date query support as `faq`.

**Verification:**
- `python -m pytest tests/e2e/test_agent_service_api.py -q`.

## Task 3: Business Tools

**Files:**
- Modify: `agent-service/app/services/order_service.py`
- Create: `agent-service/app/services/ticket_service.py`
- Modify: `agent-service/app/models/database.py`
- Modify: `agent-service/app/api/agent.py`
- Test: `agent-service/tests/e2e/test_agent_service_api.py`

**Steps:**
1. Require `user_id` when reading order snapshots.
2. Return not-found when order does not belong to the user.
3. Add logistics and refund formatting helpers from order data.
4. Add `create_ticket` service for after-sales and unresolved issues.
5. Replace placeholder ticket endpoints with DB-backed endpoints.

**Verification:**
- Tests prove user A cannot fetch user B's order.
- Tests prove logistics/refund responses use tool data.
- Tests prove ticket creation persists and appears in `/agent/tickets`.

## Task 4: MVP Knowledge Retrieval

**Files:**
- Modify: `agent-service/app/models/database.py`
- Create: `agent-service/app/services/knowledge_service.py`
- Modify: `agent-service/app/api/admin.py`
- Test: `agent-service/tests/e2e/test_agent_service_api.py`

**Steps:**
1. Add `KnowledgeChunk` table aligned with the PRD.
2. Implement admin document/chunk creation for local MVP JSON payloads.
3. Implement simple lexical retrieval with scoring so tests do not require Qdrant.
4. Generate FAQ answer only from retrieved chunks.
5. Return fallback when no chunks match.

**Verification:**
- Tests upload knowledge and ask a matching FAQ.
- Tests ask unmatched FAQ and confirm no invented answer.

## Task 5: Conditional LangGraph Routing

**Files:**
- Modify: `agent-service/app/graph/chat_graph.py`
- Test: `agent-service/tests/e2e/test_agent_service_api.py`

**Steps:**
1. Expand `ChatState` with `trace_id`, `risk_level`, `route`, `tools_used`, `sources`, `ticket_id`.
2. Replace the linear graph with conditional routes:
   - classify -> human_transfer for human/risk.
   - classify -> business_tool for order/logistics/refund.
   - classify -> knowledge for faq.
   - classify -> ticket for after_sales when needed.
   - classify -> generate_reply for unknown.
3. Keep LLM generation as fallback only, with strong prompt constraints.
4. Return cards for order/ticket where available.

**Verification:**
- Tests assert route metadata and tool usage.
- Existing chat persistence still passes.

## Task 6: Gateway Contract Alignment

**Files:**
- Modify: `api-gateway/src/services/chatService.ts`
- Modify: frontend types only if compile requires it.

**Steps:**
1. Pass through new metadata fields without breaking old consumers.
2. Keep existing `reply`, `replyType`, `cards`, `intent`, `confidence`, `needHuman` fields stable.
3. Add tests/build check for API Gateway.

**Verification:**
- `npm run build` from `api-gateway`.

## Task 7: Final Verification And Docs

**Files:**
- Modify: `README.md` if commands or feature claims need correction.

**Steps:**
1. Run backend tests.
2. Run gateway build.
3. Run frontend build if touched.
4. Summarize implemented PRD coverage and remaining P1/P2 gaps.

**Verification:**
- `python -m pytest tests -q`
- `npm run build` in changed Node projects.

---

## Execution Status

Completed on 2026-05-09:

- Intent and risk routing extracted from `chat_graph.py` into a dedicated service.
- Human-request, complaint/high-risk, refund, logistics, order, FAQ, after-sales, date, and unknown routing are covered by tests.
- Order access is scoped by `user_id` to avoid cross-user data exposure.
- Logistics and refund replies use business data instead of generic order text.
- Ticket creation and listing are persisted through `/agent/tickets`.
- Knowledge documents and chunks can be uploaded/listed through `/admin/knowledge/documents`.
- FAQ answers are generated only from retrieved knowledge chunks; unmatched FAQ questions use a no-answer fallback.
- LangGraph now uses conditional routing instead of a fixed linear path.
- AI responses include trace id, route, risk level, tools used, sources, and ticket id where applicable.
- API Gateway and frontend types pass the new metadata through without breaking the old response shape.

Verification results:

- `agent-service`: `.venv\Scripts\python.exe -m pytest tests -q` -> 26 passed.
- `api-gateway`: `npm run build` -> passed.
- `frontend`: `npx vite build` -> passed.

Known verification caveat:

- `frontend npm run build` invokes `vue-tsc`, which crashes under the current Node 24 runtime with `Search string not found: "/supportedTSExtensions = .*(?=;)/"`. This is a toolchain compatibility issue before normal type diagnostics. A fallback `npx tsc --noEmit -p tsconfig.json` still reports existing Vite/Vue shim issues for `import.meta.env` and `.vue` module declarations, while `npx vite build` succeeds.

Remaining PRD gaps:

- Qdrant/vector embeddings are not implemented yet; MVP knowledge retrieval is lexical SQLite retrieval.
- Real external order/logistics/refund integrations are not connected.
- Full customer-service workbench behavior is still mostly placeholder.
- Admin intent/script configuration is still placeholder.
- Full auth/permission model and sensitive-data masking are not implemented.
- Observability is response metadata only; no OpenTelemetry/Loki trace pipeline yet.
