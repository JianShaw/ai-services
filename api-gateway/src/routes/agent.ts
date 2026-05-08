import { Router } from 'express'

const router = Router()

// 客服路由 - 待实现
router.get('/conversations', (req, res) => {
  res.json({ message: 'Agent conversations endpoint - coming soon' })
})

router.post('/takeover', (req, res) => {
  res.json({ message: 'Agent takeover endpoint - coming soon' })
})

router.post('/reply', (req, res) => {
  res.json({ message: 'Agent reply endpoint - coming soon' })
})

router.get('/tickets', (req, res) => {
  res.json({ message: 'Tickets endpoint - coming soon' })
})

router.post('/tickets', (req, res) => {
  res.json({ message: 'Create ticket endpoint - coming soon' })
})

export default router