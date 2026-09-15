import type { KnowledgeApi, KnowledgeBase, KnowledgeDocument } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiGet, apiPost, apiUpload } from '@/shared/services/apiClient'
import { mockKnowledge } from '@/shared/services/mockAdapter'

const live: KnowledgeApi = {
  listBases: () => apiGet<KnowledgeBase[]>('/knowledge/bases'),
  createBase: (name) => apiPost<KnowledgeBase>('/knowledge/bases', { name }),
  listDocuments: (baseId) => apiGet<KnowledgeDocument[]>(`/knowledge/bases/${baseId}/documents`),
  uploadDocument: (baseId, file, onProgress) =>
    apiUpload<KnowledgeDocument>(`/knowledge/bases/${baseId}/documents`, file, onProgress),
  deleteDocument: (id) => apiDelete(`/knowledge/documents/${id}`),
}

export const knowledgeApi: KnowledgeApi = API_MODE === 'mock' ? mockKnowledge : live
