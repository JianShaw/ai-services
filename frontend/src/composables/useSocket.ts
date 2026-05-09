import { ref, computed, type Ref } from 'vue'
import { io, Socket } from 'socket.io-client'
import type { HumanTransferPayload, SocketNewMessagePayload, Conversation } from '@/types'

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || '/'

let socket: Socket | null = null
const isConnected: Ref<boolean> = ref(false)

export function useSocket() {
  function connect(): Socket {
    if (socket?.connected) return socket
    socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
    })
    socket.on('connect', () => { isConnected.value = true })
    socket.on('disconnect', () => { isConnected.value = false })
    return socket
  }

  function disconnect() {
    if (socket) {
      socket.disconnect()
      socket = null
      isConnected.value = false
    }
  }

  function joinConversation(conversationId: string) {
    socket?.emit('join-conversation', conversationId)
  }

  function leaveConversation(conversationId: string) {
    socket?.emit('leave-conversation', conversationId)
  }

  function onHumanTransferRequest(cb: (data: HumanTransferPayload) => void) {
    socket?.on('human-transfer-request', cb)
    return () => socket?.off('human-transfer-request', cb)
  }

  function onConversationAssigned(cb: (data: Conversation) => void) {
    socket?.on('conversation-assigned', cb)
    return () => socket?.off('conversation-assigned', cb)
  }

  function onNewMessage(cb: (data: SocketNewMessagePayload) => void) {
    socket?.on('new-message', cb)
    return () => socket?.off('new-message', cb)
  }

  function onAgentReplySent(cb: (data: any) => void) {
    socket?.on('agent-reply-sent', cb)
    return () => socket?.off('agent-reply-sent', cb)
  }

  return {
    socket: computed(() => socket),
    isConnected,
    connect,
    disconnect,
    joinConversation,
    leaveConversation,
    onHumanTransferRequest,
    onConversationAssigned,
    onNewMessage,
    onAgentReplySent,
  }
}
