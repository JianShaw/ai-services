import axios from 'axios'
import type { StatsData, KnowledgeDocument } from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const adminApi = axios.create({
  baseURL: `${API_BASE_URL}/admin`,
  headers: {
    'Content-Type': 'application/json'
  }
})

adminApi.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('Admin API Error:', error)
    return Promise.reject(error)
  }
)

export const adminApiEndpoints = {
  // 获取统计数据
  getStats: async (): Promise<StatsData> => {
    return adminApi.get('/stats')
  },

  // 获取知识库文档列表
  getKnowledgeDocuments: async (): Promise<KnowledgeDocument[]> => {
    return adminApi.get('/knowledge/documents')
  },

  // 上传知识库文档
  uploadKnowledgeDocument: async (file: File): Promise<KnowledgeDocument> => {
    const formData = new FormData()
    formData.append('file', file)
    return adminApi.post('/knowledge/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 删除知识库文档
  deleteKnowledgeDocument: async (documentId: string): Promise<void> => {
    return adminApi.delete(`/knowledge/documents/${documentId}`)
  },

  // 获取意图配置
  getIntents: async (): Promise<any[]> => {
    return adminApi.get('/intents')
  },

  // 更新意图配置
  updateIntent: async (intentId: string, config: any): Promise<void> => {
    return adminApi.put(`/intents/${intentId}`, config)
  },

  // 获取话术配置
  getScripts: async (): Promise<any[]> => {
    return adminApi.get('/scripts')
  },

  // 更新话术配置
  updateScript: async (scriptId: string, content: string): Promise<void> => {
    return adminApi.put(`/scripts/${scriptId}`, { content })
  }
}

export default adminApiEndpoints