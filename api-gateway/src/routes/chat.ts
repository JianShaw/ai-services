import { Router } from 'express'
import { chatService } from '../services/chatService'
import { ValidationError } from '../middleware/errorHandler'

const router = Router()

// 获取用户会话列表
router.get('/conversations', async (req, res, next) => {
  try {
    const { userId } = req.query
    if (!userId) {
      throw new ValidationError('userId is required')
    }
    const conversations = await chatService.getUserConversations(userId as string)
    res.json(conversations)
  } catch (error) {
    next(error)
  }
})

// 发送消息
router.post('/messages', async (req, res, next) => {
  try {
    const { conversationId, userId, message, channel } = req.body

    // 验证请求
    if (!userId || !message) {
      throw new ValidationError('userId and message are required')
    }

    const response = await chatService.sendMessage({
      conversationId,
      userId,
      message,
      channel: channel || 'web'
    })

    res.json(response)
  } catch (error) {
    next(error)
  }
})

// 创建会话
router.post('/conversations', async (req, res, next) => {
  try {
    const { userId, channel } = req.body

    if (!userId) {
      throw new ValidationError('userId is required')
    }

    const conversation = await chatService.createConversation({
      userId,
      channel: channel || 'web'
    })

    res.status(201).json(conversation)
  } catch (error) {
    next(error)
  }
})

// 获取会话详情
router.get('/conversations/:id', async (req, res, next) => {
  try {
    const conversation = await chatService.getConversation(req.params.id)
    res.json(conversation)
  } catch (error) {
    next(error)
  }
})

// 获取会话消息
router.get('/conversations/:id/messages', async (req, res, next) => {
  try {
    const messages = await chatService.getMessages(req.params.id)
    res.json(messages)
  } catch (error) {
    next(error)
  }
})

// 转人工
router.post('/conversations/:id/transfer', async (req, res, next) => {
  try {
    const { reason } = req.body
    await chatService.transferToHuman(req.params.id, reason)
    res.json({ success: true })
  } catch (error) {
    next(error)
  }
})

// 评价回复
router.post('/messages/:id/rate', async (req, res, next) => {
  try {
    const { rating } = req.body
    await chatService.rateMessage(req.params.id, rating)
    res.json({ success: true })
  } catch (error) {
    next(error)
  }
})

export default router