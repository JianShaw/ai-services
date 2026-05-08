import axios from 'axios'
import { NotFoundError, ValidationError } from '../middleware/errorHandler'
import { io } from '../index'

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000'

const agentApi = axios.create({
  baseURL: AGENT_SERVICE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 30000 // 30秒超时
})

interface SendMessageParams {
  conversationId?: string
  userId: string
  message: string
  channel: string
}

interface CreateConversationParams {
  userId: string
  channel: string
}

// 生成唯一ID
function generateId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

export const chatService = {
  // 发送消息到AI服务
  async sendMessage(params: SendMessageParams) {
    try {
      const response = await agentApi.post('/chat/messages', {
        conversation_id: params.conversationId,
        user_id: params.userId,
        message: params.message,
        channel: params.channel
      })

      const result = response.data

      // 通过WebSocket推送消息到客户端
      if (params.conversationId) {
        io.to(`conversation:${params.conversationId}`).emit('new-message', {
          type: 'ai',
          content: result.reply,
          metadata: {
            intent: result.intent,
            confidence: result.confidence,
            needHuman: result.needHuman
          }
        })
      }

      return {
        reply: result.reply,
        replyType: result.reply_type || 'text',
        cards: result.cards || [],
        intent: result.intent,
        confidence: result.confidence,
        needHuman: result.need_human
      }
    } catch (error) {
      console.error('Failed to send message to agent service:', error)
      throw new Error('Failed to process message')
    }
  },

  // 创建会话
  async createConversation(params: CreateConversationParams) {
    try {
      const conversationId = generateId('conv')

      const response = await agentApi.post('/chat/conversations', {
        conversation_id: conversationId,
        user_id: params.userId,
        channel: params.channel
      })

      return {
        id: conversationId,
        userId: params.userId,
        channel: params.channel,
        status: 'active',
        currentIntent: '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    } catch (error) {
      console.error('Failed to create conversation:', error)
      throw new Error('Failed to create conversation')
    }
  },

  // 获取会话详情
  async getConversation(conversationId: string) {
    try {
      const response = await agentApi.get(`/chat/conversations/${conversationId}`)
      return response.data
    } catch (error) {
      throw new NotFoundError('Conversation not found')
    }
  },

  // 获取会话消息
  async getMessages(conversationId: string) {
    try {
      const response = await agentApi.get(`/chat/conversations/${conversationId}/messages`)
      return response.data
    } catch (error) {
      throw new NotFoundError('Messages not found')
    }
  },

  // 转人工
  async transferToHuman(conversationId: string, reason: string) {
    try {
      await agentApi.post(`/chat/conversations/${conversationId}/transfer`, {
        reason
      })

      // 通知客服有新会话需要接管
      io.emit('human-transfer-request', {
        conversationId,
        reason
      })

      return { success: true }
    } catch (error) {
      throw new Error('Failed to transfer to human')
    }
  },

  // 评价消息
  async rateMessage(messageId: string, rating: 'thumbsUp' | 'thumbsDown') {
    try {
      await agentApi.post(`/chat/messages/${messageId}/rate`, {
        rating
      })
      return { success: true }
    } catch (error) {
      throw new Error('Failed to rate message')
    }
  }
}