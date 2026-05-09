import { Request, Response, NextFunction } from 'express'
import winston from 'winston'

export function requestLogger(logger: winston.Logger) {
  return (req: Request, res: Response, next: NextFunction) => {
    const start = Date.now()

    res.on('finish', () => {
      const duration = Date.now() - start
      logger.info(`${req.method} ${req.url} ${res.statusCode} ${duration}ms ip=${req.ip || '-'}`)
    })

    next()
  }
}