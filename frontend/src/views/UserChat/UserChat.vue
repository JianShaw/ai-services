<template>
  <div class="user-chat-container">
    <div class="chat-header">
      <h2>AI 客服助手</h2>
      <el-button v-if="chatStore.hasConversation" type="primary" @click="handleTransferToHuman">
        转人工
      </el-button>
    </div>

    <div class="chat-content">
      <div v-if="!chatStore.hasConversation" class="welcome-screen">
        <h3>欢迎来到AI客服中心</h3>
        <p>请输入您的问题，我会尽快为您解答</p>

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

        <el-form @submit.prevent="handleStartChat">
          <el-form-item label="您的ID：">
            <el-input v-model="userId" placeholder="请输入用户ID" />
          </el-form-item>
          <el-button type="primary" @click="handleStartChat">开始对话</el-button>
        </el-form>
      </div>

      <div v-else class="chat-area">
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="message in chatStore.messages"
            :key="message.id"
            :class="['message', message.senderType]"
          >
            <div class="message-content">
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
            :disabled="chatStore.isLoading"
          />
          <div class="input-actions">
            <span class="input-hint">Ctrl + Enter 发送</span>
            <el-button
              type="primary"
              :loading="chatStore.isLoading"
              @click="handleSendMessage"
            >
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useChatStore } from '@/store/chat'
import type { QuickQuestion } from '@/types'
import { ElMessage } from 'element-plus'

const chatStore = useChatStore()
const userId = ref(`user_${Date.now()}`)
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement>()

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function handleStartChat() {
  try {
    await chatStore.createConversation(userId.value)
    ElMessage.success('会话已创建')
  } catch (error) {
    ElMessage.error('创建会话失败')
    console.error(error)
  }
}

async function handleSendMessage() {
  if (!inputMessage.value.trim()) {
    return
  }

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
    ElMessage.success('已转接人工客服')
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
</script>

<style scoped>
.user-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
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
  max-width: 800px;
  margin: 0 auto;
}

.welcome-screen h3 {
  color: #333;
  margin-bottom: 0.5rem;
}

.welcome-screen p {
  color: #666;
  margin-bottom: 2rem;
}

.quick-questions {
  width: 100%;
  margin-bottom: 2rem;
}

.quick-questions h4 {
  color: #333;
  margin-bottom: 1rem;
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

.message.agent,
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