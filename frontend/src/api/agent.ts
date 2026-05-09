import axios from 'axios'
import type {
  Conversation,
  Message,
  Ticket,
  TakeoverRequest,
  AgentReplyRequest,
  CreateTicketRequest
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const agentApi = axios.create({
  baseURL: `${API_BASE_URL}/agent`,
  headers: {
    'Content-Type': 'application/json'
  }
})

agentApi.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('Agent API Error:', error)
    return Promise.reject(error)
  }
)

export const agentApiEndpoints = {
  // 获取会话列表
  getConversations: async (params?: {
    status?: string
    page?: number
    pageSize?: number
  }): Promise<Conversation[]> => {
    return agentApi.get('/conversations', { params })
  },

  // 获取会话详情
  getConversation: async (conversationId: string): Promise<Conversation> => {
    return agentApi.get(`/conversations/${conversationId}`)
  },

  // 接管会话
  takeoverConversation: async (data: TakeoverRequest): Promise<Conversation> => {
    return agentApi.post('/takeover', data)
  },

  // 客服回复
  sendReply: async (data: AgentReplyRequest): Promise<Message> => {
    return agentApi.post('/reply', data)
  },

  // 获取工单列表
  getTickets: async (params?: {
    status?: string
    page?: number
    pageSize?: number
  }): Promise<Ticket[]> => {
    return agentApi.get('/tickets', { params })
  },

  // 创建工单
  createTicket: async (data: CreateTicketRequest): Promise<Ticket> => {
    return agentApi.post('/tickets', data)
  },

  // 更新工单状态
  updateTicketStatus: async (
    ticketId: string,
    status: string
  ): Promise<void> => {
    return agentApi.patch(`/tickets/${ticketId}`, { status })
  },

  // 获取会话消息
  getConversationMessages: async (conversationId: string): Promise<Message[]> => {
    return agentApi.get(`/conversations/${conversationId}/messages`)
  }
}

export default agentApiEndpoints
