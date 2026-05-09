import axios from 'axios'
import { io } from '../index'

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000'

const agentApi = axios.create({
  baseURL: AGENT_SERVICE_URL,
  headers: {
    'Content-Type': 'application/json'
  },
  timeout: 30000
})

export const agentService = {
  async getConversations(status?: string) {
    const response = await agentApi.get('/agent/conversations', {
      params: status ? { status } : undefined
    })
    return response.data
  },

  async getConversation(conversationId: string) {
    const response = await agentApi.get(`/agent/conversations/${conversationId}`)
    return response.data
  },

  async getConversationMessages(conversationId: string) {
    const response = await agentApi.get(`/agent/conversations/${conversationId}/messages`)
    return response.data
  },

  async takeoverConversation(conversationId: string, agentId: string) {
    const response = await agentApi.post('/agent/takeover', {
      conversation_id: conversationId,
      agent_id: agentId
    })

    io.emit('conversation-assigned', response.data)
    return response.data
  },

  async sendReply(conversationId: string, agentId: string, message: string) {
    const response = await agentApi.post('/agent/reply', {
      conversation_id: conversationId,
      agent_id: agentId,
      message
    })

    const result = response.data
    io.to(`conversation:${conversationId}`).emit('new-message', {
      id: result.id,
      type: 'agent',
      content: result.content,
      timestamp: result.timestamp,
      metadata: result.metadata || {}
    })
    io.emit('agent-reply-sent', result)

    return result
  },

  async getTickets() {
    const response = await agentApi.get('/agent/tickets')
    return response.data
  },

  async createTicket(payload: {
    conversationId: string
    userId: string
    type: string
    description: string
    priority?: string
    assignedTo?: string
  }) {
    const response = await agentApi.post('/agent/tickets', {
      conversation_id: payload.conversationId,
      user_id: payload.userId,
      type: payload.type,
      description: payload.description,
      priority: payload.priority || 'medium',
      assigned_to: payload.assignedTo
    })
    return response.data
  }
}
