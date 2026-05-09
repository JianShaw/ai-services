# Agent MVP 后端实施计划

> **执行说明：** 本计划用于按任务逐步实施。每个任务完成后都需要先运行对应验证，再进入下一步。

**目标：** 将当前演示性质的客服聊天机器人，推进为一个可测试、可验收的 MVP 后端，覆盖 PRD P0 主链路：意图路由、知识库问答、订单工具、转人工、工单和会话日志。

**架构：** 保持现有 `Vue -> API Gateway -> FastAPI Agent Service` 架构不变。第一阶段主要在 `agent-service` 中补齐真实业务层：确定性的安全/风险规则、意图识别、LangGraph 条件路由、基于 SQLite 的 MVP 知识检索、订单/物流/退款工具、工单创建，以及用于追踪的响应元数据。

**技术栈：** FastAPI、LangGraph、SQLAlchemy async、SQLite MVP 业务数据、pytest/httpx 验证、Node/Express API Gateway 透传。

---

## 范围

本计划优先实现 PRD 中 MVP 后端主链路，不一次性实现完整 Qdrant RAG、完整管理后台 UI、全渠道接入、排班、质检或生产级权限认证。这些内容保留到 P1/P2。

## 目标行为

- 用户消息会被保存。
- Agent 能将意图识别为 `faq`、`order_query`、`logistics_query`、`refund_query`、`after_sales`、`complaint`、`human_request` 或 `unknown`。
- 用户明确要求人工、或消息命中高风险场景时，进入转人工。
- 订单、物流、退款问题调用业务数据，不允许模型猜测。
- FAQ 问题先检索知识片段，只能基于检索结果回答。
- 售后问题在信息足够时可创建工单，否则追问缺失信息。
- 每次 AI 回复都记录 intent、confidence、need-human、trace id、route、tools used、risk level 和 sources。

## 任务 1：计划与基线

**文件：**
- 创建：`docs/plans/2026-05-09-agent-mvp-backend.md`
- 检查：`agent-service/tests/e2e/test_agent_service_api.py`
- 检查：`agent-service/app/graph/chat_graph.py`

**步骤：**
1. 保存实施计划。
2. 运行当前后端测试套件。
3. 在正式功能开发前记录基线失败情况。

**验证：**
- 在 `agent-service` 目录运行：`python -m pytest tests -q`

## 任务 2：意图与风险识别基础

**文件：**
- 创建：`agent-service/app/services/intent_service.py`
- 修改：`agent-service/app/graph/chat_graph.py`
- 测试：`agent-service/tests/e2e/test_agent_service_api.py`

**步骤：**
1. 为优先级路由增加测试：
   - “我要人工查订单” -> `human_request`，`need_human=True`
   - “我要投诉并要求赔偿” -> `complaint`，`need_human=True`，高风险
   - “退款订单 ORD-20260508-0001” -> `refund_query`，不能被识别成普通订单
   - “物流 ORD-20260508-0001” -> `logistics_query`
2. 实现 `IntentResult` 数据结构，包含 `intent`、`confidence`、`need_human`、`risk_level`、`reason` 和 `order_no`。
3. 将关键词和订单号解析逻辑从 `chat_graph.py` 中抽离出去。
4. 建立规则优先级：人工/风险优先，其次退款/物流，再其次订单，最后售后/FAQ/未知。
5. 保留确定性的日期类查询能力。

**验证：**
- `python -m pytest tests/e2e/test_agent_service_api.py -q`

## 任务 3：业务工具

**文件：**
- 修改：`agent-service/app/services/order_service.py`
- 创建：`agent-service/app/services/ticket_service.py`
- 修改：`agent-service/app/models/database.py`
- 修改：`agent-service/app/api/agent.py`
- 测试：`agent-service/tests/e2e/test_agent_service_api.py`

**步骤：**
1. 查询订单快照时必须带 `user_id`。
2. 如果订单不属于当前用户，返回未查到，避免越权泄露。
3. 基于订单数据增加物流、退款回复格式化工具。
4. 增加 `create_ticket` 服务，用于售后和未解决问题。
5. 将占位工单接口替换为数据库持久化接口。

**验证：**
- 测试证明用户 A 不能查询用户 B 的订单。
- 测试证明物流/退款回复来自业务工具数据。
- 测试证明工单能创建并出现在 `/agent/tickets`。

## 任务 4：MVP 知识库检索

**文件：**
- 修改：`agent-service/app/models/database.py`
- 创建：`agent-service/app/services/knowledge_service.py`
- 修改：`agent-service/app/api/admin.py`
- 测试：`agent-service/tests/e2e/test_agent_service_api.py`

**步骤：**
1. 增加与 PRD 对齐的 `KnowledgeChunk` 表。
2. 实现 admin 文档/片段创建接口，MVP 阶段使用 JSON payload。
3. 实现简单词面检索和评分，保证测试不依赖 Qdrant。
4. FAQ 只能基于检索到的片段生成答案。
5. 无命中时返回兜底话术，不能编造答案。

**验证：**
- 测试能上传知识并询问命中的 FAQ。
- 测试未命中 FAQ 时确认不会编造答案。

## 任务 5：LangGraph 条件路由

**文件：**
- 修改：`agent-service/app/graph/chat_graph.py`
- 测试：`agent-service/tests/e2e/test_agent_service_api.py`

**步骤：**
1. 扩展 `ChatState`，增加 `trace_id`、`risk_level`、`route`、`tools_used`、`sources`、`ticket_id`。
2. 将线性图替换为条件路由：
   - classify -> human_transfer：人工请求/风险场景
   - classify -> business_tool：订单/物流/退款
   - classify -> knowledge：FAQ
   - classify -> ticket：售后问题
   - classify -> generate_reply：未知问题
3. LLM 只作为兜底生成使用，并保留强约束 prompt。
4. 在可用时返回订单/工单卡片。

**验证：**
- 测试断言 route 元数据和 tool usage。
- 现有聊天持久化测试仍然通过。

## 任务 6：API Gateway 与前端契约对齐

**文件：**
- 修改：`api-gateway/src/services/chatService.ts`
- 如编译需要，修改前端类型。

**步骤：**
1. 透传新的元数据字段，同时不破坏旧消费者。
2. 保持现有 `reply`、`replyType`、`cards`、`intent`、`confidence`、`needHuman` 字段稳定。
3. 增加 API Gateway 构建检查。

**验证：**
- 在 `api-gateway` 目录运行：`npm run build`

## 任务 7：最终验证与文档

**文件：**
- 如命令或功能声明需要修正，修改 `README.md`。

**步骤：**
1. 运行后端测试。
2. 运行 API Gateway 构建。
3. 如触碰前端，运行前端构建。
4. 总结已覆盖的 PRD 范围和剩余 P1/P2 缺口。

**验证：**
- `python -m pytest tests -q`
- 在变更过的 Node 项目中运行 `npm run build`

---

## 执行状态

已于 2026-05-09 完成：

- 意图与风险路由已从 `chat_graph.py` 抽离为独立服务。
- 人工请求、投诉/高风险、退款、物流、订单、FAQ、售后、日期、未知意图均已有测试覆盖。
- 订单访问已按 `user_id` 限定，避免跨用户数据泄露。
- 物流和退款回复使用业务数据，不再复用普通订单话术。
- 工单创建和列表已通过 `/agent/tickets` 持久化。
- 知识文档和知识片段可通过 `/admin/knowledge/documents` 上传和列表查询。
- FAQ 只基于检索到的知识片段回答；未命中时返回无答案兜底。
- LangGraph 已从固定线性流程改为条件路由。
- AI 响应会返回 trace id、route、risk level、tools used、sources，以及可用时的 ticket id。
- API Gateway 和前端类型已透传新增元数据，同时保持旧响应结构兼容。

验证结果：

- `agent-service`：`.venv\Scripts\python.exe -m pytest tests -q` -> 26 passed
- `api-gateway`：`npm run build` -> passed
- `frontend`：`npx vite build` -> passed

已知验证注意事项：

- `frontend npm run build` 会调用 `vue-tsc`，当前 Node 24 环境下会因工具链兼容问题崩溃，错误为 `Search string not found: "/supportedTSExtensions = .*(?=;)/"`。这发生在正常类型诊断之前，属于工具链兼容问题。
- 作为替代验证，`npx vite build` 已通过。
- `npx tsc --noEmit -p tsconfig.json` 仍会报告项目既有的 Vite/Vue 类型声明问题，例如 `import.meta.env` 和 `.vue` module declaration。

剩余 PRD 缺口：

- 尚未实现 Qdrant / 向量 embedding；当前 MVP 知识检索是 SQLite 词面检索。
- 尚未接入真实外部订单、物流、退款系统。
- 完整客服工作台能力仍大多是占位。
- 管理后台的意图配置、话术配置仍是占位。
- 尚未实现完整权限模型和敏感数据脱敏。
- 可观测性目前只是响应元数据，尚未接入 OpenTelemetry / Loki 调用链路。
