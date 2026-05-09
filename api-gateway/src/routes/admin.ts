import { Router } from 'express'

const router = Router()

// 管理员路由 - 待实现
router.get('/stats', (_req, res) => {
  res.json({
    totalConversations: 0,
    aiResolutionRate: 0,
    humanTransferRate: 0,
    avgResponseTime: 0,
    userSatisfaction: 0,
    topQuestions: []
  })
})

router.get('/knowledge/documents', (_req, res) => {
  res.json({ message: 'Knowledge documents endpoint - coming soon' })
})

router.post('/knowledge/documents', (_req, res) => {
  res.json({ message: 'Upload knowledge document endpoint - coming soon' })
})

router.get('/intents', (_req, res) => {
  res.json({ message: 'Intents configuration endpoint - coming soon' })
})

router.get('/scripts', (_req, res) => {
  res.json({ message: 'Scripts configuration endpoint - coming soon' })
})

export default router
