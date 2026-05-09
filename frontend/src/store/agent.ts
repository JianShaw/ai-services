import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Conversation, Message } from '@/types'
import { agentApiEndpoints } from '@/api/agent'

export const useAgentStore = defineStore('agent', () => {
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref<string | null>(null)
  const activeConversationMessages = ref<Message[]>([])
  const currentAgentId = ref(`agent_${Date.now()}`)
  const isLoading = ref(false)
  const statusFilter = ref<string>('transferred')

  const activeConversation = computed(() =>
    conversations.value.find(c => c.id === activeConversationId.value) || null
  )

  const filteredConversations = computed(() => {
    if (statusFilter.value === 'all') return conversations.value
    if (statusFilter.value === 'mine') {
      return conversations.value.filter(c => c.assignedAgentId === currentAgentId.value)
    }
    return conversations.value.filter(c => c.status === statusFilter.value)
  })

  const unreadTransferCount = computed(() =>
    conversations.value.filter(c => c.status === 'transferred').length
  )

  async function fetchConversations() {
    try {
      isLoading.value = true
      conversations.value = await agentApiEndpoints.getConversations()
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function selectConversation(conversationId: string) {
    activeConversationId.value = conversationId
    try {
      activeConversationMessages.value = await agentApiEndpoints.getConversationMessages(conversationId)
    } catch (error) {
      console.error('Failed to fetch messages:', error)
      activeConversationMessages.value = []
    }
  }

  async function takeoverConversation(conversationId: string) {
    try {
      const updated = await agentApiEndpoints.takeoverConversation({
        conversationId,
        agentId: currentAgentId.value
      })
      const idx = conversations.value.findIndex(c => c.id === conversationId)
      if (idx !== -1) conversations.value[idx] = updated
      else await fetchConversations()
    } catch (error) {
      console.error('Failed to takeover conversation:', error)
      throw error
    }
  }

  async function sendReply(conversationId: string, content: string) {
    try {
      const message = await agentApiEndpoints.sendReply({
        conversationId,
        agentId: currentAgentId.value,
        message: content
      })
      if (!activeConversationMessages.value.some(m => m.id === message.id)) {
        activeConversationMessages.value.push(message)
      }
      return message
    } catch (error) {
      console.error('Failed to send reply:', error)
      throw error
    }
  }

  function updateConversation(conversation: Conversation) {
    const idx = conversations.value.findIndex(c => c.id === conversation.id)
    if (idx !== -1) conversations.value[idx] = conversation
  }

  function addMessageToActive(message: Message) {
    if (message.conversationId !== activeConversationId.value) return
    if (activeConversationMessages.value.some(m => m.id === message.id)) return
    activeConversationMessages.value.push(message)
  }

  function clearSelection() {
    activeConversationId.value = null
    activeConversationMessages.value = []
  }

  return {
    conversations,
    activeConversationId,
    activeConversationMessages,
    currentAgentId,
    isLoading,
    statusFilter,

    activeConversation,
    filteredConversations,
    unreadTransferCount,

    fetchConversations,
    selectConversation,
    takeoverConversation,
    sendReply,
    updateConversation,
    addMessageToActive,
    clearSelection
  }
})
