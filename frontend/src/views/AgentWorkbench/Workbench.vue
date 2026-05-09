<template>
  <div class="workbench-container">
    <div class="workbench-header">
      <h2>客服工作台</h2>
      <div class="header-actions">
        <el-input
          v-model="agentStore.currentAgentId"
          placeholder="客服ID"
          style="width: 180px; margin-right: 12px;"
          size="small"
        />
        <el-badge :value="agentStore.unreadTransferCount" :hidden="agentStore.unreadTransferCount === 0">
          <el-tag :type="socket.isConnected.value ? 'success' : 'danger'">
            {{ socket.isConnected.value ? '已连接' : '未连接' }}
          </el-tag>
        </el-badge>
      </div>
    </div>

    <div class="workbench-body">
      <div class="conversation-list">
        <div class="list-filter">
          <el-radio-group v-model="agentStore.statusFilter" size="small" @change="handleFilterChange">
            <el-radio-button value="transferred">待接管</el-radio-button>
            <el-radio-button value="mine">我接手的</el-radio-button>
            <el-radio-button value="all">全部</el-radio-button>
          </el-radio-group>
        </div>

        <div v-if="agentStore.isLoading" class="list-loading">
          <el-icon class="is-loading"><Loading /></el-icon> 加载中...
        </div>

        <div v-else-if="agentStore.filteredConversations.length === 0" class="list-empty">
          暂无会话
        </div>

        <div
          v-else
          v-for="conv in agentStore.filteredConversations"
          :key="conv.id"
          :class="['conversation-card', { active: conv.id === agentStore.activeConversationId }]"
          @click="handleSelectConversation(conv.id)"
        >
          <div class="card-header">
            <span class="card-user">{{ conv.userId }}</span>
            <span class="card-time">{{ formatTime(conv.updatedAt) }}</span>
          </div>
          <div class="card-body">
            <el-tag
              :type="statusTagType(conv.status)"
              size="small"
            >
              {{ statusLabel(conv.status) }}
            </el-tag>
            <el-tag
              v-if="conv.currentIntent"
              size="small"
              type="info"
              style="margin-left: 4px;"
            >
              {{ conv.currentIntent }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="conversation-detail">
        <div v-if="!agentStore.activeConversation" class="detail-empty">
          <el-empty description="请选择一个会话" />
        </div>

        <template v-else>
          <div class="detail-header">
            <span>{{ agentStore.activeConversation.userId }}</span>
            <el-tag :type="statusTagType(agentStore.activeConversation.status)" size="small">
              {{ statusLabel(agentStore.activeConversation.status) }}
            </el-tag>
          </div>

          <div class="detail-messages" ref="detailMessagesRef">
            <div
              v-for="msg in agentStore.activeConversationMessages"
              :key="msg.id"
              :class="['detail-msg', msg.senderType]"
            >
              <div class="detail-msg-content">
                <div v-if="msg.senderType !== 'user'" class="msg-sender">
                  {{ msg.senderType === 'agent' ? '我' : 'AI' }}
                </div>
                <div>{{ msg.content }}</div>
                <div class="msg-time">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </div>

          <div class="detail-actions">
            <div v-if="!isTakenOver" class="takeover-area">
              <el-button
                type="primary"
                @click="handleTakeover"
                :disabled="!agentStore.currentAgentId"
              >
                接管会话
              </el-button>
            </div>

            <div v-else class="reply-area">
              <el-input
                v-model="replyContent"
                type="textarea"
                :rows="2"
                placeholder="输入回复内容..."
                @keydown.enter.ctrl="handleSendReply"
              />
              <div class="reply-actions">
                <span class="input-hint">Ctrl + Enter 发送</span>
                <el-button type="primary" :disabled="!replyContent.trim()" @click="handleSendReply">
                  发送
                </el-button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useAgentStore } from '@/store/agent'
import { useSocket } from '@/composables/useSocket'
import { ElNotification } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

const agentStore = useAgentStore()
const socket = useSocket()
const replyContent = ref('')
const detailMessagesRef = ref<HTMLElement>()
const cleanups: (() => void)[] = []

const isTakenOver = computed(() =>
  agentStore.activeConversation?.assignedAgentId === agentStore.currentAgentId
)

function formatTime(timestamp: string): string {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
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

async function handleSelectConversation(conversationId: string) {
  const prevId = agentStore.activeConversationId
  if (prevId && prevId !== conversationId) {
    socket.leaveConversation(prevId)
  }
  await agentStore.selectConversation(conversationId)
  socket.joinConversation(conversationId)
  nextTick(scrollDetailToBottom)
}

async function handleTakeover() {
  if (!agentStore.activeConversationId) return
  try {
    await agentStore.takeoverConversation(agentStore.activeConversationId)
    ElNotification({ title: '已接管', type: 'success', duration: 2000 })
  } catch {
    ElNotification({ title: '接管失败', type: 'error', duration: 2000 })
  }
}

async function handleSendReply() {
  if (!replyContent.value.trim() || !agentStore.activeConversationId) return
  try {
    await agentStore.sendReply(agentStore.activeConversationId, replyContent.value)
    replyContent.value = ''
    nextTick(scrollDetailToBottom)
  } catch {
    ElNotification({ title: '发送失败', type: 'error', duration: 2000 })
  }
}

function handleFilterChange() {
  agentStore.clearSelection()
}

function scrollDetailToBottom() {
  if (detailMessagesRef.value) {
    detailMessagesRef.value.scrollTop = detailMessagesRef.value.scrollHeight
  }
}

watch(() => agentStore.activeConversationMessages.length, () => {
  nextTick(scrollDetailToBottom)
})

onMounted(async () => {
  socket.connect()
  await agentStore.fetchConversations()

  cleanups.push(
    socket.onHumanTransferRequest((data) => {
      ElNotification({
        title: '新的转接请求',
        message: `用户 ${data.userId}，风险等级：${data.riskLevel}`,
        type: 'warning',
        duration: 5000,
      })
      agentStore.fetchConversations()
    })
  )

  cleanups.push(
    socket.onNewMessage((data) => {
      if (data.type !== 'agent') {
        agentStore.addMessageToActive({
          id: data.id,
          conversationId: agentStore.activeConversationId || '',
          senderType: data.type as 'user' | 'ai',
          content: data.content,
          messageType: 'text',
          metadata: data.metadata,
          timestamp: data.timestamp,
        })
      }
    })
  )

  cleanups.push(
    socket.onConversationAssigned((data) => {
      agentStore.updateConversation(data)
    })
  )
})

onUnmounted(() => {
  if (agentStore.activeConversationId) {
    socket.leaveConversation(agentStore.activeConversationId)
  }
  cleanups.forEach(fn => fn())
})
</script>

<style scoped>
.workbench-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.workbench-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
}

.workbench-header h2 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.header-actions {
  display: flex;
  align-items: center;
}

.workbench-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.conversation-list {
  width: 320px;
  border-right: 1px solid #e0e0e0;
  background-color: white;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-filter {
  padding: 0.75rem;
  border-bottom: 1px solid #eee;
}

.list-loading,
.list-empty {
  padding: 2rem;
  text-align: center;
  color: #999;
}

.conversation-card {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.conversation-card:hover {
  background-color: #f5f7fa;
}

.conversation-card.active {
  background-color: #ecf5ff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.card-user {
  font-weight: 500;
  font-size: 0.875rem;
  color: #333;
}

.card-time {
  font-size: 0.75rem;
  color: #999;
}

.card-body {
  display: flex;
  align-items: center;
}

.conversation-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #f5f5f5;
}

.detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
  font-weight: 500;
}

.detail-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.detail-msg {
  margin-bottom: 0.75rem;
  display: flex;
}

.detail-msg.user {
  justify-content: flex-end;
}

.detail-msg.ai,
.detail-msg.agent {
  justify-content: flex-start;
}

.detail-msg-content {
  max-width: 70%;
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
  font-size: 0.875rem;
  line-height: 1.5;
}

.detail-msg.user .detail-msg-content {
  background-color: #409eff;
  color: white;
}

.detail-msg.ai .detail-msg-content {
  background-color: white;
  color: #333;
}

.detail-msg.agent .detail-msg-content {
  background-color: #f0f9eb;
  color: #333;
  border: 1px solid #e1f3d8;
}

.msg-sender {
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 0.15rem;
}

.msg-time {
  font-size: 0.7rem;
  color: #999;
  margin-top: 0.2rem;
}

.detail-msg.user .msg-time {
  color: rgba(255, 255, 255, 0.7);
}

.detail-actions {
  padding: 0.75rem 1.5rem;
  background-color: white;
  border-top: 1px solid #e0e0e0;
}

.takeover-area {
  display: flex;
  justify-content: center;
  padding: 0.5rem 0;
}

.reply-area {
  display: flex;
  flex-direction: column;
}

.reply-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
}

.input-hint {
  font-size: 0.8rem;
  color: #999;
}
</style>
