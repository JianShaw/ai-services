import { Router } from 'express'
import { agentService } from '../services/agentService'
import { ValidationError } from '../middleware/errorHandler'

const router = Router()

router.get('/conversations', async (req, res, next) => {
  try {
    const conversations = await agentService.getConversations(req.query.status as string | undefined)
    res.json(conversations)
  } catch (error) {
    next(error)
  }
})

router.get('/conversations/:id', async (req, res, next) => {
  try {
    const conversation = await agentService.getConversation(req.params.id)
    res.json(conversation)
  } catch (error) {
    next(error)
  }
})

router.get('/conversations/:id/messages', async (req, res, next) => {
  try {
    const messages = await agentService.getConversationMessages(req.params.id)
    res.json(messages)
  } catch (error) {
    next(error)
  }
})

router.post('/takeover', async (req, res, next) => {
  try {
    const { conversationId, agentId } = req.body
    if (!conversationId || !agentId) {
      throw new ValidationError('conversationId and agentId are required')
    }

    const conversation = await agentService.takeoverConversation(conversationId, agentId)
    res.json(conversation)
  } catch (error) {
    next(error)
  }
})

router.post('/reply', async (req, res, next) => {
  try {
    const { conversationId, agentId, message } = req.body
    if (!conversationId || !agentId || !message) {
      throw new ValidationError('conversationId, agentId and message are required')
    }

    const reply = await agentService.sendReply(conversationId, agentId, message)
    res.status(201).json(reply)
  } catch (error) {
    next(error)
  }
})

router.get('/tickets', async (_req, res, next) => {
  try {
    const tickets = await agentService.getTickets()
    res.json(tickets)
  } catch (error) {
    next(error)
  }
})

router.post('/tickets', async (req, res, next) => {
  try {
    const { conversationId, userId, type, description, priority, assignedTo } = req.body
    if (!conversationId || !userId || !type || !description) {
      throw new ValidationError('conversationId, userId, type and description are required')
    }

    const ticket = await agentService.createTicket({
      conversationId,
      userId,
      type,
      description,
      priority,
      assignedTo
    })
    res.status(201).json(ticket)
  } catch (error) {
    next(error)
  }
})

export default router
