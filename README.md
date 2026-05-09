# 企业级 AI 客服系统

一个基于 LangGraph 的企业级 AI 客服 Agent 系统，支持多轮对话、意图识别、知识库问答、工具调用、人工协同等功能。

## 技术架构

### 技术栈
- **前端**: Vue 3 + TypeScript + Vite + Element Plus
- **API Gateway**: Node.js + Express + TypeScript
- **AI Agent Service**: Python + FastAPI + LangGraph
- **数据库**: SQLite (业务数据)
- **向量数据库**: Qdrant (知识库检索)
- **缓存**: Redis (会话状态)

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端层 (Vue 3)                        │
│  用户聊天页 │ 客服工作台 │ 管理后台                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              API Gateway (Node.js + Express)                │
│  路由控制 │ 身份验证 │ 业务逻辑                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            AI Agent Service (Python + FastAPI)              │
│  LangGraph │ 意图识别 │ RAG检索 │ 工具调用                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              SQLite │ Qdrant │ Redis                        │
└─────────────────────────────────────────────────────────────┘
```

## 功能特性

### MVP 核心功能
- ✅ 多轮对话与会话管理
- ✅ 意图识别与智能路由
- ✅ 知识库问答 (RAG)
- ✅ 订单查询工具
- ✅ 转人工机制
- ✅ 工单系统
- ✅ 客服工作台
- ✅ 管理后台

### 转人工流程

用户可通过手动点击"转人工"按钮或发送含"转人工/投诉/退款"等关键词的消息触发转人工。完整流程如下：

```
用户发送消息 → 意图识别 → 判定 need_human=true
     ↓
ChatGraph 路由到 human_transfer_node → 返回"正在转接"回复
     ↓
API Gateway 通过 Socket.IO 广播 human-transfer-request 事件
     ↓
客服工作台收到通知 → 会话列表出现待接管会话
     ↓
客服点击"接管" → 会话状态变为 assigned → 用户端显示"人工客服已接入"
     ↓
客服通过工作台回复 → Socket.IO 实时推送至用户端
```

关键设计：
- **意图识别**：基于关键词规则，区分普通请求、投诉、高风险等场景，输出风险等级（low/medium/high）
- **条件路由**：LangGraph 根据意图自动分流到转人工/订单查询/知识库检索/工单创建/LLM 兜底等分支
- **实时通信**：Socket.IO 实现双向消息推送，用户端与客服端共享同一连接，通过 conversation room 隔离消息
- **状态流转**：`active` → `transferred`（等待接管）→ `assigned`（客服已接入）→ `closed`

## 快速开始

### 环境要求
- Node.js 18+
- Python 3.10+
- Docker & Docker Compose
- Redis

### 本地开发

1. **克隆项目**
```bash
git clone <repository-url>
cd ai-services
```

2. **启动基础设施**
```bash
docker-compose up -d qdrant redis
```

3. **安装依赖**

前端:
```bash
cd frontend
npm install
npm run dev
```

API Gateway:
```bash
cd api-gateway
npm install
npm run dev
```

Agent Service:
```bash
cd agent-service
uv sync --dev
uv run uvicorn app.main:app --reload --port 8000
```

4. **访问应用**
- 用户聊天页: http://localhost:5173
- 客服工作台: http://localhost:5173/workbench
- 管理后台: http://localhost:5173/admin

### 一键启动三端

在项目根目录运行：

```bash
start-dev.cmd
```

脚本会优先使用 Windows Terminal，在一个窗口里打开 3 个 PowerShell 标签页；如果没有安装 Windows Terminal，会自动退回为 3 个独立 PowerShell 窗口。

如果依赖已经安装好，可以跳过依赖检查：

```bash
start-dev.cmd -SkipInstall
```

后端 AI 模型使用 DeepSeek 的 OpenAI-compatible API。本地开发时在 `agent-service/.env` 设置：

```bash
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash
```

Qdrant 和 Redis 由 Docker Compose 启动：

```bash
cd docker
docker compose up -d qdrant redis
```

后端需要 mock 订单数据时运行：

```bash
cd agent-service
uv run python scripts/seed_orders.py
```

## 项目结构

```
ai-services/
├── frontend/              # Vue 3 前端
├── api-gateway/           # Node.js API 网关
├── agent-service/         # Python AI 服务
├── data/                  # 数据存储
│   ├── database.db       # SQLite 数据库
│   ├── qdrant/           # Qdrant 数据
│   └── knowledge/        # 知识库文档
├── docker/               # Docker 配置
└── README.md
```

## 开发指南

### API 接口文档

详见各服务的 API 文档：
- API Gateway: http://localhost:3000/api-docs
- Agent Service: http://localhost:8000/docs

### 数据库初始化

```bash
# 在 agent-service 目录下
uv run python init_db.py
```

### 知识库管理

1. 将知识库文档放入 `data/knowledge/` 目录
2. 在管理后台上传文档
3. 系统会自动解析、切片、向量化

## 部署

### Docker 部署

```bash
docker-compose up -d
```

### 手动部署

详见各服务的部署文档。

## 性能指标

- AI 首次响应: < 3 秒
- 工具查询: < 2 秒
- RAG 检索: < 1 秒
- 并发支持: 100+

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

- 项目主页: [GitHub Repository]
- 问题反馈: [Issues]
- 文档: [Wiki]
