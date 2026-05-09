<template>
  <div class="user-chat-container">
    <!-- 左侧会话列表 -->
    <div class="sidebar" v-if="chatStore.userId">
      <div class="sidebar-header">
        <span class="sidebar-title">历史会话</span>
        <el-button size="small" @click="handleNewChat">新建</el-button>
      </div>
      <div class="sidebar-list">
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          :class="['sidebar-item', { active: conv.id === chatStore.conversationId }]"
          @click="handleSelectConversation(conv.id)"
        >
          <div class="sidebar-item-header">
            <el-tag :type="statusTagType(conv.status)" size="small">{{ statusLabel(conv.status) }}</el-tag>
            <span class="sidebar-item-time">{{ formatDate(conv.updatedAt) }}</span>
          </div>
          <div class="sidebar-item-intent">{{ conv.currentIntent || '新会话' }}</div>
        </div>
        <div v-if="chatStore.conversations.length === 0" class="sidebar-empty">
          暂无会话
        </div>
      </div>
    </div>

    <!-- 右侧主聊天区 -->
    <div class="chat-main">
      <div class="chat-header">
        <h2>AI 客服助手</h2>
        <div class="header-right">
          <el-button
            v-if="chatStore.hasConversation && !chatStore.isTransferred && !chatStore.isAssigned"
            type="primary"
            @click="handleTransferToHuman"
          >
            转人工
          </el-button>
          <el-tag v-if="chatStore.isTransferred && !chatStore.isAssigned" type="warning">
            转接中...
          </el-tag>
          <el-tag v-if="chatStore.isAssigned" type="success">
            人工客服服务中
          </el-tag>
        </div>
      </div>

      <div class="chat-content">
        <!-- 欢迎/登录界面 -->
        <div v-if="!chatStore.hasConversation" class="welcome-screen">
          <template v-if="!chatStore.userId">
            <h3>欢迎来到AI客服中心</h3>
            <p>请输入您的ID开始对话</p>
            <el-form @submit.prevent="handleStartChat" class="welcome-form">
              <el-form-item label="您的ID：">
                <el-input v-model="inputUserId" placeholder="请输入用户ID" />
              </el-form-item>
              <el-button type="primary" @click="handleStartChat">开始对话</el-button>
            </el-form>
          </template>

          <template v-else>
            <h3>AI 客服助手</h3>
            <p>请选择一个历史会话，或开始新对话</p>
            <div class="quick-questions">
              <h4>常见问题：</h4>
              <el-button
                v-for="question in chatStore.quickQuestions"
                :key="question.id"
                class="quick-question-btn"
                @click="handleQuickQuestion(question)"
              >
                {{ question.text }}
              </el-button>
            </div>
            <el-button type="primary" @click="handleNewChat">开始新对话</el-button>
          </template>
        </div>

        <!-- 聊天区域 -->
        <div v-else class="chat-area">
          <div v-if="chatStore.isTransferred && !chatStore.isAssigned" class="transfer-banner waiting">
            正在为您转接人工客服，请稍候...
          </div>
          <div v-if="chatStore.isAssigned" class="transfer-banner assigned">
            人工客服已接入
          </div>

          <div class="messages-container" ref="messagesContainer">
            <div
              v-for="message in chatStore.messages"
              :key="message.id"
              :class="['message', message.senderType]"
            >
              <div class="message-content">
                <div v-if="message.senderType === 'agent'" class="agent-label">人工客服</div>
                <div class="message-text">{{ message.content }}</div>
                <div class="message-time">{{ formatTime(message.timestamp) }}</div>
              </div>
              <div v-if="message.senderType === 'ai'" class="message-actions">
                <el-button
                  size="small"
                  :type="message.metadata?.rating === 'thumbsUp' ? 'primary' : 'default'"
                  @click="handleRateMessage(message.id, 'thumbsUp')"
                >
                  👍
                </el-button>
                <el-button
                  size="small"
                  :type="message.metadata?.rating === 'thumbsDown' ? 'danger' : 'default'"
                  @click="handleRateMessage(message.id, 'thumbsDown')"
                >
                  👎
                </el-button>
              </div>
            </div>
          </div>

          <div class="input-area">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="2"
              placeholder="输入您的问题..."
              @keydown.enter.ctrl="handleSendMessage"
              :disabled="chatStore.isLoading || (chatStore.isTransferred && !chatStore.isAssigned)"
            />
            <div class="input-actions">
              <span class="input-hint">Ctrl + Enter 发送</span>
              <el-button
                type="primary"
                :loading="chatStore.isLoading"
                :disabled="chatStore.isTransferred && !chatStore.isAssigned"
                @click="handleSendMessage"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/store/chat'
import { useSocket } from '@/composables/useSocket'
import type { QuickQuestion } from '@/types'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const socket = useSocket()

const inputUserId = ref('')
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement>()
const cleanups: (() => void)[] = []

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatDate(timestamp: string): string {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()
  return isToday
    ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function statusTagType(status: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    active: '',
    transferred: 'danger',
    assigned: 'success',
    closed: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '进行中',
    transferred: '待接管',
    assigned: '已接管',
    closed: '已关闭',
  }
  return map[status] || status
}

async function handleStartChat() {
  if (!inputUserId.value.trim()) return
  try {
    chatStore.setUserId(inputUserId.value)
    const conversation = await chatStore.createConversation(inputUserId.value)
    router.push(`/chat/${conversation.id}`)
  } catch (error) {
    ElMessage.error('创建会话失败')
    console.error(error)
  }
}

async function handleNewChat() {
  if (!chatStore.userId) return
  try {
    chatStore.clearConversation()
    const conversation = await chatStore.createConversation(chatStore.userId)
    router.push(`/chat/${conversation.id}`)
  } catch (error) {
    ElMessage.error('创建会话失败')
    console.error(error)
  }
}

async function handleSelectConversation(id: string) {
  router.push(`/chat/${id}`)
}

async function handleSendMessage() {
  if (!inputMessage.value.trim()) return
  try {
    await chatStore.sendMessage(inputMessage.value)
    inputMessage.value = ''
    await nextTick()
    scrollToBottom()
  } catch (error) {
    ElMessage.error('发送消息失败')
    console.error(error)
  }
}

function handleQuickQuestion(question: QuickQuestion) {
  inputMessage.value = question.text
}

async function handleTransferToHuman() {
  try {
    await chatStore.transferToHuman('用户主动要求转人工')
    ElMessage.info('正在转接人工客服...')
  } catch (error) {
    ElMessage.error('转接人工失败')
    console.error(error)
  }
}

async function handleRateMessage(messageId: string, rating: 'thumbsUp' | 'thumbsDown') {
  try {
    await chatStore.rateMessage(messageId, rating)
    ElMessage.success(rating === 'thumbsUp' ? '感谢您的评价！' : '感谢您的反馈，我们会继续改进')
  } catch (error) {
    ElMessage.error('评价失败')
    console.error(error)
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

watch(() => chatStore.messages.length, () => {
  nextTick(scrollToBottom)
})

// URL 驱动：路由参数变化时加载对应会话
watch(() => route.params.id, async (id) => {
  if (id && typeof id === 'string') {
    await chatStore.loadConversation(id)
    socket.joinConversation(id)
    nextTick(scrollToBottom)
  }
}, { immediate: false })

onMounted(async () => {
  socket.connect()

  cleanups.push(
    socket.onNewMessage((data) => {
      if (data.type === 'agent') {
        chatStore.addAgentMessage(data)
        nextTick(scrollToBottom)
      }
    })
  )

  cleanups.push(
    socket.onConversationAssigned((data) => {
      chatStore.markAssigned(data.assignedAgentId || 'agent')
      nextTick(scrollToBottom)
    })
  )

  // 有 userId 就加载会话列表
  if (chatStore.userId) {
    await chatStore.fetchConversations()
  }

  // URL 带 id 则加载该会话
  const id = route.params.id as string | undefined
  if (id) {
    await chatStore.loadConversation(id)
    socket.joinConversation(id)
    nextTick(scrollToBottom)
  }
})

onUnmounted(() => {
  if (chatStore.conversationId) {
    socket.leaveConversation(chatStore.conversationId)
  }
  cleanups.forEach(fn => fn())
})
</script>

<style scoped>
.user-chat-container {
  display: flex;
  height: 100vh;
  background-color: #f5f5f5;
}

/* ---- 侧边栏 ---- */
.sidebar {
  width: 260px;
  background-color: white;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #eee;
}

.sidebar-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: #333;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
}

.sidebar-item {
  padding: 0.6rem 1rem;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.sidebar-item:hover {
  background-color: #f5f7fa;
}

.sidebar-item.active {
  background-color: #ecf5ff;
}

.sidebar-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.2rem;
}

.sidebar-item-time {
  font-size: 0.7rem;
  color: #999;
}

.sidebar-item-intent {
  font-size: 0.8rem;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-empty {
  padding: 2rem 1rem;
  text-align: center;
  color: #999;
  font-size: 0.85rem;
}

/* ---- 主聊天区 ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
}

.chat-header h2 {
  margin: 0;
  color: #333;
}

.chat-content {
  flex: 1;
  overflow: hidden;
}

.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  max-width: 600px;
  margin: 0 auto;
}

.welcome-screen h3 {
  color: #333;
  margin-bottom: 0.5rem;
}

.welcome-screen p {
  color: #666;
  margin-bottom: 1.5rem;
}

.welcome-form {
  width: 100%;
  max-width: 360px;
}

.quick-questions {
  width: 100%;
  margin-bottom: 1.5rem;
}

.quick-questions h4 {
  color: #333;
  margin-bottom: 0.75rem;
}

.quick-question-btn {
  margin: 0.25rem;
  display: block;
  width: 100%;
}

.chat-area {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.transfer-banner {
  padding: 0.5rem 1rem;
  text-align: center;
  font-size: 0.875rem;
}

.transfer-banner.waiting {
  background-color: #fdf6ec;
  color: #e6a23c;
  border-bottom: 1px solid #faecd8;
}

.transfer-banner.assigned {
  background-color: #f0f9eb;
  color: #67c23a;
  border-bottom: 1px solid #e1f3d8;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.message {
  display: flex;
  margin-bottom: 1rem;
  max-width: 70%;
}

.message.user {
  margin-left: auto;
}

.message.agent {
  margin-right: auto;
}

.message.ai {
  margin-right: auto;
}

.message-content {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background-color: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message.user .message-content {
  background-color: #409eff;
  color: white;
}

.message.agent .message-content {
  border-left: 3px solid #67c23a;
}

.agent-label {
  font-size: 0.75rem;
  color: #67c23a;
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.message-time {
  font-size: 0.75rem;
  color: #999;
  margin-top: 0.25rem;
}

.message.user .message-time {
  color: rgba(255, 255, 255, 0.8);
}

.message-actions {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.input-area {
  padding: 1rem;
  background-color: white;
  border-top: 1px solid #e0e0e0;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
}

.input-hint {
  font-size: 0.875rem;
  color: #999;
}
</style>
