import axios from 'axios'
import type {
  SendMessageRequest,
  CreateConversationRequest,
  AIResponse,
  Conversation,
  Message
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const chatApi = axios.create({
  baseURL: `${API_BASE_URL}/chat`,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
chatApi.interceptors.request.use(
  (config) => {
    // 可以在这里添加token等
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
chatApi.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export const chatApiEndpoints = {
  // 获取用户会话列表
  getUserConversations: async (userId: string): Promise<Conversation[]> => {
    return chatApi.get('/conversations', { params: { userId } })
  },

  // 发送消息
  sendMessage: async (data: SendMessageRequest): Promise<AIResponse> => {
    return chatApi.post('/messages', data)
  },

  // 创建会话
  createConversation: async (data: CreateConversationRequest): Promise<Conversation> => {
    return chatApi.post('/conversations', data)
  },

  // 获取会话详情
  getConversation: async (conversationId: string): Promise<Conversation> => {
    return chatApi.get(`/conversations/${conversationId}`)
  },

  // 获取会话消息列表
  getMessages: async (conversationId: string): Promise<Message[]> => {
    return chatApi.get(`/conversations/${conversationId}/messages`)
  },

  // 转人工
  transferToHuman: async (conversationId: string, reason: string): Promise<void> => {
    return chatApi.post(`/conversations/${conversationId}/transfer`, { reason })
  },

  // 评价回复
  rateReply: async (messageId: string, rating: 'thumbsUp' | 'thumbsDown'): Promise<void> => {
    return chatApi.post(`/messages/${messageId}/rate`, { rating })
  }
}

export default chatApiEndpoints