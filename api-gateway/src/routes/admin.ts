import { Router, Request, Response } from 'express'
import axios from 'axios'
import multer from 'multer'

const router = Router()

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || 'http://localhost:8000'

const agentApi = axios.create({
  baseURL: AGENT_SERVICE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
})

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } })

// Stats
router.get('/stats', async (_req: Request, res: Response) => {
  try {
    const response = await agentApi.get('/admin/stats')
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - List
router.get('/knowledge/documents', async (_req: Request, res: Response) => {
  try {
    const response = await agentApi.get('/admin/knowledge/documents')
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Upload JSON
router.post('/knowledge/documents', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.post('/admin/knowledge/documents', req.body)
    res.status(response.status).json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Upload File (multipart)
router.post('/knowledge/documents/upload', upload.single('file'), async (req: Request, res: Response) => {
  try {
    const file = req.file
    if (!file) {
      res.status(400).json({ error: 'No file uploaded' })
      return
    }
    const formData = new FormData()
    formData.append('title', req.body.title || 'Untitled')
    formData.append('category', req.body.category || 'faq')
    formData.append('tenant_id', req.body.tenant_id || 'default')
    if (req.body.version) formData.append('version', req.body.version)
    formData.append('file', new Blob([file.buffer]), file.originalname)

    const response = await agentApi.post('/admin/knowledge/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    res.status(response.status).json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Get Detail
router.get('/knowledge/documents/:documentId', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.get(`/admin/knowledge/documents/${req.params.documentId}`)
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Update Status
router.patch('/knowledge/documents/:documentId', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.patch(`/admin/knowledge/documents/${req.params.documentId}`, req.body)
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Delete
router.delete('/knowledge/documents/:documentId', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.delete(`/admin/knowledge/documents/${req.params.documentId}`)
    res.status(response.status).json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Reindex
router.post('/knowledge/documents/:documentId/reindex', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.post(`/admin/knowledge/documents/${req.params.documentId}/reindex`)
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Knowledge Documents - Chunks
router.get('/knowledge/documents/:documentId/chunks', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.get(`/admin/knowledge/documents/${req.params.documentId}/chunks`)
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Search Test
router.post('/knowledge/search-test', async (req: Request, res: Response) => {
  try {
    const response = await agentApi.post('/admin/knowledge/search-test', req.body)
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Intents
router.get('/intents', async (_req: Request, res: Response) => {
  try {
    const response = await agentApi.get('/admin/intents')
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

// Scripts
router.get('/scripts', async (_req: Request, res: Response) => {
  try {
    const response = await agentApi.get('/admin/scripts')
    res.json(response.data)
  } catch (err: any) {
    const status = err.response?.status || 500
    res.status(status).json({ error: err.message })
  }
})

export default router
