<template>
  <div class="admin-container">
    <div class="admin-header">
      <h2>管理后台</h2>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="知识库管理" name="knowledge" />
        <el-tab-pane label="检索测试" name="search" />
      </el-tabs>
    </div>
    <div class="admin-content">
      <!-- 知识库管理 -->
      <div v-if="activeTab === 'knowledge'" class="knowledge-panel">
        <div class="toolbar">
          <el-button type="primary" @click="showUploadDialog = true">上传文档</el-button>
          <el-button @click="loadDocuments">刷新</el-button>
        </div>

        <el-table :data="documents" v-loading="loading" stripe style="width: 100%">
          <el-table-column prop="title" label="标题" min-width="200" />
          <el-table-column prop="category" label="分类" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sourceType" label="类型" width="90" />
          <el-table-column prop="chunkCount" label="分片数" width="80" align="center" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="120" />
          <el-table-column prop="updatedAt" label="更新时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.updatedAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="viewChunks(row)">查看分片</el-button>
              <el-button
                size="small"
                :type="row.status === 'active' ? 'warning' : 'success'"
                @click="toggleStatus(row)"
              >
                {{ row.status === 'active' ? '停用' : '启用' }}
              </el-button>
              <el-button size="small" @click="reindexDoc(row)">重新索引</el-button>
              <el-button size="small" type="danger" @click="deleteDoc(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 检索测试 -->
      <div v-if="activeTab === 'search'" class="search-panel">
        <div class="search-bar">
          <el-input
            v-model="searchQuery"
            placeholder="输入测试问题，如：你们客服几点上班？"
            clearable
            @keyup.enter="doSearch"
            style="max-width: 600px"
          >
            <template #append>
              <el-button @click="doSearch" :loading="searching">检索</el-button>
            </template>
          </el-input>
        </div>
        <div v-if="searchResults.length > 0" class="search-results">
          <p class="result-summary">共 {{ searchTotal }} 条结果</p>
          <div v-for="(item, idx) in searchResults" :key="item.id" class="result-item">
            <div class="result-header">
              <span class="result-index">#{{ idx + 1 }}</span>
              <el-tag size="small">{{ categoryLabel(item.category) }}</el-tag>
              <span class="result-score">相似度: {{ (item.score * 100).toFixed(1) }}%</span>
              <span class="result-title">{{ item.title }}</span>
            </div>
            <div class="result-content">{{ item.content }}</div>
          </div>
        </div>
        <el-empty v-else-if="searchDone" description="未检索到相关内容" />
      </div>

      <!-- 上传对话框 -->
      <el-dialog v-model="showUploadDialog" title="上传知识库文档" width="520px" :close-on-click-modal="false">
        <el-form :model="uploadForm" label-width="80px">
          <el-form-item label="标题" required>
            <el-input v-model="uploadForm.title" placeholder="文档标题" />
          </el-form-item>
          <el-form-item label="分类" required>
            <el-select v-model="uploadForm.category" style="width: 100%">
              <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="版本">
            <el-input v-model="uploadForm.version" placeholder="如 2026-05-11" />
          </el-form-item>
          <el-form-item label="文件" required>
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".pdf,.md,.txt,.markdown"
              :on-change="onFileChange"
              :file-list="fileList"
            >
              <el-button>选择文件</el-button>
              <template #tip>
                <div class="el-upload__tip">支持 PDF / Markdown / TXT 文件</div>
              </template>
            </el-upload>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showUploadDialog = false">取消</el-button>
          <el-button type="primary" @click="doUpload" :loading="uploading">上传</el-button>
        </template>
      </el-dialog>

      <!-- 分片查看对话框 -->
      <el-dialog v-model="showChunksDialog" :title="'分片列表 - ' + chunksDocTitle" width="700px">
        <el-table :data="chunks" v-loading="chunksLoading" max-height="500">
          <el-table-column prop="id" label="ID" width="140" show-overflow-tooltip />
          <el-table-column prop="content" label="内容" min-width="400" show-overflow-tooltip />
          <el-table-column label="Embedding" width="90">
            <template #default="{ row }">
              <el-tag :type="row.embeddingId ? 'success' : 'info'" size="small">
                {{ row.embeddingId ? '已入库' : '未入库' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import adminApiEndpoints from '@/api/admin'
import type { KnowledgeDocument, KnowledgeChunk, SearchResult } from '@/types'

const activeTab = ref('knowledge')
const loading = ref(false)
const documents = ref<KnowledgeDocument[]>([])

const categories = [
  { value: 'working_hours', label: '工作时间' },
  { value: 'return_policy', label: '退货政策' },
  { value: 'refund_policy', label: '退款政策' },
  { value: 'exchange_policy', label: '换货政策' },
  { value: 'product_info', label: '商品信息' },
  { value: 'shipping_policy', label: '发货配送' },
  { value: 'invoice_policy', label: '发票规则' },
  { value: 'warranty_policy', label: '保修售后' },
  { value: 'company_culture', label: '企业文化' },
  { value: 'membership_policy', label: '会员积分' },
  { value: 'faq', label: '通用FAQ' },
]

function categoryLabel(val: string): string {
  return categories.find(c => c.value === val)?.label || val
}

function formatTime(val: string | null): string {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN')
}

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await adminApiEndpoints.getKnowledgeDocuments()
  } catch {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

// --- Upload ---
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadForm = ref({ title: '', category: 'faq', version: '' })
const fileList = ref<UploadFile[]>([])
const selectedFile = ref<File | null>(null)

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
  if (!uploadForm.value.title && file.name) {
    uploadForm.value.title = file.name.replace(/\.[^.]+$/, '')
  }
}

async function doUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.value.title) {
    ElMessage.warning('请填写标题')
    return
  }
  uploading.value = true
  try {
    await adminApiEndpoints.uploadKnowledgeFile({
      title: uploadForm.value.title,
      category: uploadForm.value.category,
      tenant_id: 'default',
      version: uploadForm.value.version || undefined,
      file: selectedFile.value,
    })
    ElMessage.success('上传成功')
    showUploadDialog.value = false
    uploadForm.value = { title: '', category: 'faq', version: '' }
    fileList.value = []
    selectedFile.value = null
    await loadDocuments()
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

// --- Document Actions ---
async function toggleStatus(doc: KnowledgeDocument) {
  const newStatus = doc.status === 'active' ? 'inactive' : 'active'
  try {
    await adminApiEndpoints.updateDocumentStatus(doc.id, newStatus)
    ElMessage.success(newStatus === 'active' ? '已启用' : '已停用')
    await loadDocuments()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function reindexDoc(doc: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm('确认重新索引该文档？将删除旧向量并重新生成。', '重新索引')
    await adminApiEndpoints.reindexDocument(doc.id)
    ElMessage.success('重新索引完成')
    await loadDocuments()
  } catch { /* cancelled */ }
}

async function deleteDoc(doc: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(`确认删除文档「${doc.title}」？此操作将同时删除 Qdrant 中的向量数据。`, '删除确认', { type: 'warning' })
    await adminApiEndpoints.deleteKnowledgeDocument(doc.id)
    ElMessage.success('已删除')
    await loadDocuments()
  } catch { /* cancelled */ }
}

// --- Chunks ---
const showChunksDialog = ref(false)
const chunksLoading = ref(false)
const chunks = ref<KnowledgeChunk[]>([])
const chunksDocTitle = ref('')

async function viewChunks(doc: KnowledgeDocument) {
  chunksDocTitle.value = doc.title
  showChunksDialog.value = true
  chunksLoading.value = true
  try {
    chunks.value = await adminApiEndpoints.getDocumentChunks(doc.id)
  } catch {
    ElMessage.error('加载分片失败')
  } finally {
    chunksLoading.value = false
  }
}

// --- Search Test ---
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchTotal = ref(0)
const searchDone = ref(false)

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  searchDone.value = false
  try {
    const res = await adminApiEndpoints.searchTest({ query: searchQuery.value, top_k: 5 })
    searchResults.value = res.results
    searchTotal.value = res.total
  } catch {
    ElMessage.error('检索失败')
  } finally {
    searching.value = false
    searchDone.value = true
  }
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.admin-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.admin-header {
  padding: 0 2rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
}

.admin-header h2 {
  margin: 0;
  padding: 1rem 0 0.5rem;
}

.admin-content {
  flex: 1;
  padding: 1.5rem 2rem;
  overflow: auto;
}

.toolbar {
  margin-bottom: 1rem;
}

.search-panel {
  max-width: 800px;
}

.search-bar {
  margin-bottom: 1.5rem;
}

.result-summary {
  color: #666;
  font-size: 14px;
  margin-bottom: 1rem;
}

.result-item {
  background: white;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 0.75rem;
  border: 1px solid #ebeef5;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.result-index {
  font-weight: bold;
  color: #409eff;
}

.result-score {
  color: #67c23a;
  font-size: 13px;
}

.result-title {
  color: #999;
  font-size: 13px;
}

.result-content {
  color: #333;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
