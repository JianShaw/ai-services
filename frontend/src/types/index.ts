// 通用类型定义

export interface Message {
  id: string
  conversationId: string
  senderType: 'user' | 'agent' | 'ai'
  content: string
  messageType: 'text' | 'card' | 'image' | 'action'
  metadata?: Record<string, any>
  timestamp: string
}

export interface Conversation {
  id: string
  userId: string
  channel: string
  status: 'active' | 'transferred' | 'assigned' | 'closed'
  currentIntent: string
  summary?: string
  assignedAgentId?: string
  createdAt: string
  updatedAt: string
  lastMessage?: Message
}

export interface Ticket {
  id: string
  conversationId: string
  userId: string
  type: string
  priority: 'low' | 'medium' | 'high'
  status: 'open' | 'processing' | 'resolved' | 'closed'
  description: string
  assignedTo?: string
  createdAt: string
  updatedAt: string
}

export interface UserInfo {
  id: string
  name: string
  email?: string
  phone?: string
  avatar?: string
}

export interface OrderInfo {
  id: string
  orderNo: string
  status: string
  totalAmount: number
  createdAt: string
  items: OrderItem[]
}

export interface OrderItem {
  id: string
  productName: string
  quantity: number
  price: number
}

export interface KnowledgeDocument {
  id: string
  title: string
  sourceType: string
  category: string
  tenantId: string
  status: 'active' | 'inactive'
  version: string
  chunkCount: number
  createdAt: string
  updatedAt: string
}

export interface KnowledgeChunk {
  id: string
  documentId: string
  content: string
  embeddingId: string | null
  metadata: Record<string, any>
  createdAt: string
}

export interface SearchResult {
  id: string
  document_id: string
  title: string
  content: string
  score: number
  category: string
  metadata: Record<string, any>
}

export interface AIResponse {
  reply: string
  replyType: 'text' | 'card' | 'action'
  cards?: Card[]
  intent?: string
  confidence?: number
  needHuman?: boolean
  riskLevel?: 'low' | 'medium' | 'high'
  traceId?: string
  route?: string
  ticketId?: string
  toolsUsed?: string[]
  sources?: Array<Record<string, any>>
}

export interface Card {
  type: 'order' | 'logistics' | 'ticket' | 'custom'
  title: string
  content: Record<string, any>
}

export interface QuickQuestion {
  id: string
  text: string
  intent?: string
}

export interface StatsData {
  totalConversations: number
  aiResolutionRate: number
  humanTransferRate: number
  avgResponseTime: number
  userSatisfaction: number
  topQuestions: Array<{
    question: string
    count: number
  }>
}

// API 请求/响应类型
export interface SendMessageRequest {
  conversationId?: string
  userId: string
  message: string
  channel: string
}

export interface CreateConversationRequest {
  userId: string
  channel: string
}

export interface TakeoverRequest {
  agentId: string
  conversationId: string
}

export interface AgentReplyRequest {
  conversationId: string
  message: string
  agentId: string
}

export interface CreateTicketRequest {
  conversationId: string
  userId: string
  type: string
  priority: 'low' | 'medium' | 'high'
  description: string
}

export interface HumanTransferPayload {
  conversationId: string
  userId: string
  reason: string
  riskLevel: 'low' | 'medium' | 'high'
  route: string
}

export interface SocketNewMessagePayload {
  id: string
  type: 'ai' | 'agent'
  content: string
  timestamp: string
  metadata: Record<string, any>
}
