import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, Message, QuickQuestion } from '@/types'
import { chatApiEndpoints } from '@/api/chat'

const STORAGE_KEY = 'ai_chat_user_id'

export const useChatStore = defineStore('chat', () => {
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const transferStatus = ref<'none' | 'waiting' | 'assigned'>('none')
  const userId = ref(localStorage.getItem(STORAGE_KEY) || '')
  const conversations = ref<Conversation[]>([])

  const quickQuestions = ref<QuickQuestion[]>([
    { id: '1', text: '我的订单什么时候发货？', intent: 'order_query' },
    { id: '2', text: '如何申请退款？', intent: 'faq' },
    { id: '3', text: '你们的工作时间是什么时候？', intent: 'faq' },
    { id: '4', text: '转人工客服', intent: 'human_request' }
  ])

  const hasConversation = computed(() => !!currentConversation.value)
  const conversationId = computed(() => currentConversation.value?.id || '')
  const isTransferred = computed(() =>
    currentConversation.value?.status === 'transferred' || transferStatus.value === 'waiting'
  )
  const isAssigned = computed(() => transferStatus.value === 'assigned')

  function setUserId(id: string) {
    userId.value = id
    localStorage.setItem(STORAGE_KEY, id)
  }

  async function fetchConversations() {
    if (!userId.value) return
    try {
      conversations.value = await chatApiEndpoints.getUserConversations(userId.value)
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    }
  }

  async function createConversation(uid: string) {
    try {
      isLoading.value = true
      if (uid !== userId.value) setUserId(uid)
      const conversation = await chatApiEndpoints.createConversation({
        userId: uid,
        channel: 'web'
      })
      currentConversation.value = conversation
      await fetchConversations()
      return conversation
    } catch (error) {
      console.error('Failed to create conversation:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function loadConversation(id: string) {
    try {
      isLoading.value = true
      const [conversation, conversationMessages] = await Promise.all([
        chatApiEndpoints.getConversation(id),
        chatApiEndpoints.getMessages(id)
      ])
      currentConversation.value = conversation
      messages.value = conversationMessages
      if (conversation.status === 'assigned' && conversation.assignedAgentId) {
        transferStatus.value = 'assigned'
      } else if (conversation.status === 'transferred') {
        transferStatus.value = 'waiting'
      } else {
        transferStatus.value = 'none'
      }
    } catch (error) {
      console.error('Failed to load conversation:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function sendMessage(content: string) {
    if (!currentConversation.value) {
      throw new Error('No active conversation')
    }

    try {
      isLoading.value = true

      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        conversationId: currentConversation.value.id,
        senderType: 'user',
        content,
        messageType: 'text',
        timestamp: new Date().toISOString()
      }
      messages.value.push(userMessage)

      const response = await chatApiEndpoints.sendMessage({
        conversationId: currentConversation.value.id,
        userId: currentConversation.value.userId,
        message: content,
        channel: 'web'
      })

      const aiMessage: Message = {
        id: `msg_${Date.now() + 1}`,
        conversationId: currentConversation.value.id,
        senderType: 'ai',
        content: response.reply,
        messageType: response.replyType,
        metadata: {
          intent: response.intent,
          confidence: response.confidence,
          needHuman: response.needHuman,
          riskLevel: response.riskLevel,
          traceId: response.traceId,
          route: response.route,
          ticketId: response.ticketId,
          toolsUsed: response.toolsUsed || [],
          sources: response.sources || []
        },
        timestamp: new Date().toISOString()
      }
      messages.value.push(aiMessage)

      if (response.needHuman) {
        transferStatus.value = 'waiting'
        if (currentConversation.value) {
          currentConversation.value.status = 'transferred'
        }
      }

      fetchConversations()
      return response
    } catch (error) {
      console.error('Failed to send message:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function transferToHuman(reason: string) {
    if (!currentConversation.value) {
      throw new Error('No active conversation')
    }

    try {
      await chatApiEndpoints.transferToHuman(currentConversation.value.id, reason)
      if (currentConversation.value) {
        currentConversation.value.status = 'transferred'
      }
      transferStatus.value = 'waiting'
    } catch (error) {
      console.error('Failed to transfer to human:', error)
      throw error
    }
  }

  function markAssigned(agentId: string) {
    transferStatus.value = 'assigned'
    if (currentConversation.value) {
      currentConversation.value.status = 'assigned'
      currentConversation.value.assignedAgentId = agentId
    }
    messages.value.push({
      id: `msg_sys_${Date.now()}`,
      conversationId: currentConversation.value?.id || '',
      senderType: 'agent',
      content: '人工客服已接入，请问有什么可以帮助您的？',
      messageType: 'text',
      timestamp: new Date().toISOString()
    })
  }

  function addAgentMessage(payload: { id: string; content: string; timestamp: string }) {
    if (messages.value.some(m => m.id === payload.id)) return
    messages.value.push({
      id: payload.id,
      conversationId: currentConversation.value?.id || '',
      senderType: 'agent',
      content: payload.content,
      messageType: 'text',
      timestamp: payload.timestamp
    })
  }

  async function rateMessage(messageId: string, rating: 'thumbsUp' | 'thumbsDown') {
    try {
      await chatApiEndpoints.rateReply(messageId, rating)
      const message = messages.value.find(m => m.id === messageId)
      if (message) {
        message.metadata = { ...message.metadata, rating }
      }
    } catch (error) {
      console.error('Failed to rate message:', error)
      throw error
    }
  }

  function clearConversation() {
    currentConversation.value = null
    messages.value = []
    transferStatus.value = 'none'
  }

  return {
    currentConversation,
    messages,
    isLoading,
    transferStatus,
    userId,
    conversations,
    quickQuestions,

    hasConversation,
    conversationId,
    isTransferred,
    isAssigned,

    setUserId,
    fetchConversations,
    createConversation,
    loadConversation,
    sendMessage,
    transferToHuman,
    markAssigned,
    addAgentMessage,
    rateMessage,
    clearConversation
  }
})
