import express from 'express'
import cors from 'cors'
import { createServer } from 'http'
import { Server as SocketIOServer } from 'socket.io'
import dotenv from 'dotenv'
import winston from 'winston'

import chatRoutes from './routes/chat'
import agentRoutes from './routes/agent'
import adminRoutes from './routes/admin'
import { errorHandler } from './middleware/errorHandler'
import { requestLogger } from './middleware/requestLogger'

// 加载环境变量
dotenv.config()

const app = express()
const httpServer = createServer(app)
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: process.env.FRONTEND_URL || 'http://localhost:5173',
    methods: ['GET', 'POST']
  }
})

// 配置日志
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      )
    }),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
})

// 中间件
app.use(cors())
app.use(express.json())
app.use(express.urlencoded({ extended: true }))
app.use(requestLogger(logger))

// 健康检查
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

// API 路由
app.use('/api/chat', chatRoutes)
app.use('/api/agent', agentRoutes)
app.use('/api/admin', adminRoutes)

// WebSocket 连接
io.on('connection', (socket) => {
  logger.info(`Client connected: ${socket.id}`)

  socket.on('join-conversation', (conversationId: string) => {
    socket.join(`conversation:${conversationId}`)
    logger.info(`Socket ${socket.id} joined conversation: ${conversationId}`)
  })

  socket.on('leave-conversation', (conversationId: string) => {
    socket.leave(`conversation:${conversationId}`)
    logger.info(`Socket ${socket.id} left conversation: ${conversationId}`)
  })

  socket.on('disconnect', () => {
    logger.info(`Client disconnected: ${socket.id}`)
  })
})

// 错误处理
app.use(errorHandler)

// 导出 io 实例供其他模块使用
export { io, logger }

// 启动服务器
const PORT = process.env.PORT || 3000

httpServer.listen(PORT, () => {
  logger.info(`API Gateway is running on port ${PORT}`)
  logger.info(`WebSocket server is ready`)
})

// 优雅关闭
process.on('SIGTERM', () => {
  logger.info('SIGTERM signal received: closing HTTP server')
  httpServer.close(() => {
    logger.info('HTTP server closed')
    process.exit(0)
  })
})
