import axios from 'axios'
import type { StatsData, KnowledgeDocument, KnowledgeChunk, SearchResult } from '@/types'

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

  // 获取文档详情
  getKnowledgeDocument: async (documentId: string): Promise<KnowledgeDocument & { chunks: KnowledgeChunk[] }> => {
    return adminApi.get(`/knowledge/documents/${documentId}`)
  },

  // 上传知识库文档（JSON 方式）
  uploadKnowledgeDocument: async (data: {
    title: string
    source_type: string
    category: string
    tenant_id: string
    version?: string
    chunks: { content: string; metadata?: Record<string, any> }[]
  }): Promise<KnowledgeDocument> => {
    return adminApi.post('/knowledge/documents', data)
  },

  // 上传知识库文档（文件上传方式）
  uploadKnowledgeFile: async (params: {
    title: string
    category: string
    tenant_id: string
    version?: string
    file: File
  }): Promise<KnowledgeDocument> => {
    const formData = new FormData()
    formData.append('title', params.title)
    formData.append('category', params.category)
    formData.append('tenant_id', params.tenant_id)
    if (params.version) formData.append('version', params.version)
    formData.append('file', params.file)
    return adminApi.post('/knowledge/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 更新文档状态
  updateDocumentStatus: async (documentId: string, status: string): Promise<KnowledgeDocument> => {
    return adminApi.patch(`/knowledge/documents/${documentId}`, { status })
  },

  // 删除知识库文档
  deleteKnowledgeDocument: async (documentId: string): Promise<void> => {
    return adminApi.delete(`/knowledge/documents/${documentId}`)
  },

  // 重新索引文档
  reindexDocument: async (documentId: string): Promise<{ message: string }> => {
    return adminApi.post(`/knowledge/documents/${documentId}/reindex`)
  },

  // 获取文档 chunks
  getDocumentChunks: async (documentId: string): Promise<KnowledgeChunk[]> => {
    return adminApi.get(`/knowledge/documents/${documentId}/chunks`)
  },

  // 检索测试
  searchTest: async (params: {
    query: string
    category?: string
    tenant_id?: string
    top_k?: number
  }): Promise<{ query: string; results: SearchResult[]; total: number }> => {
    return adminApi.post('/knowledge/search-test', params)
  },

  // 获取意图配置
  getIntents: async (): Promise<any[]> => {
    return adminApi.get('/intents')
  },

  // 获取话术配置
  getScripts: async (): Promise<any[]> => {
    return adminApi.get('/scripts')
  },
}

export default adminApiEndpoints
