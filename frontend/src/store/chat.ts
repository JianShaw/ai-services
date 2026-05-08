import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, Message, QuickQuestion } from '@/types'
import { chatApiEndpoints } from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  // 状态
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const quickQuestions = ref<QuickQuestion[]>([
    { id: '1', text: '我的订单什么时候发货？', intent: 'order_query' },
    { id: '2', text: '如何申请退款？', intent: 'faq' },
    { id: '3', text: '你们的工作时间是什么时候？', intent: 'faq' },
    { id: '4', text: '转人工客服', intent: 'human_request' }
  ])

  // 计算属性
  const hasConversation = computed(() => !!currentConversation.value)
  const conversationId = computed(() => currentConversation.value?.id || '')

  // 方法
  async function createConversation(userId: string) {
    try {
      isLoading.value = true
      const conversation = await chatApiEndpoints.createConversation({
        userId,
        channel: 'web'
      })
      currentConversation.value = conversation
      return conversation
    } catch (error) {
      console.error('Failed to create conversation:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function loadConversation(conversationId: string) {
    try {
      isLoading.value = true
      const [conversation, conversationMessages] = await Promise.all([
        chatApiEndpoints.getConversation(conversationId),
        chatApiEndpoints.getMessages(conversationId)
      ])
      currentConversation.value = conversation
      messages.value = conversationMessages
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

      // 添加用户消息
      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        conversationId: currentConversation.value.id,
        senderType: 'user',
        content,
        messageType: 'text',
        timestamp: new Date().toISOString()
      }
      messages.value.push(userMessage)

      // 发送消息并获取AI回复
      const response = await chatApiEndpoints.sendMessage({
        conversationId: currentConversation.value.id,
        userId: currentConversation.value.userId,
        message: content,
        channel: 'web'
      })

      // 添加AI回复
      const aiMessage: Message = {
        id: `msg_${Date.now() + 1}`,
        conversationId: currentConversation.value.id,
        senderType: 'ai',
        content: response.reply,
        messageType: response.replyType,
        metadata: {
          intent: response.intent,
          confidence: response.confidence,
          needHuman: response.needHuman
        },
        timestamp: new Date().toISOString()
      }
      messages.value.push(aiMessage)

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
    } catch (error) {
      console.error('Failed to transfer to human:', error)
      throw error
    }
  }

  async function rateMessage(messageId: string, rating: 'thumbsUp' | 'thumbsDown') {
    try {
      await chatApiEndpoints.rateReply(messageId, rating)
      // 更新本地消息状态
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
  }

  return {
    // 状态
    currentConversation,
    messages,
    isLoading,
    quickQuestions,

    // 计算属性
    hasConversation,
    conversationId,

    // 方法
    createConversation,
    loadConversation,
    sendMessage,
    transferToHuman,
    rateMessage,
    clearConversation
  }
})