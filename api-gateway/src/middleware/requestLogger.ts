import { Request, Response, NextFunction } from 'express'
import winston from 'winston'

export function requestLogger(logger: winston.Logger) {
  return (req: Request, res: Response, next: NextFunction) => {
    const start = Date.now()

    res.on('finish', () => {
      const duration = Date.now() - start
      logger.info({
        method: req.method,
        url: req.url,
        status: res.statusCode,
        duration: `${duration}ms`,
        ip: req.ip
      })
    })

    next()
  }
}