import type { KnowledgeApi, KnowledgeBase, KnowledgeDocument } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiPost, apiUpload } from '@/shared/services/apiClient'
import { invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockKnowledge } from '@/shared/services/mockAdapter'

const live: KnowledgeApi = {
  listBases: () => resilientGet<KnowledgeBase[]>('/knowledge/bases', undefined, { dedupe: true }),
  createBase: async (name) => {
    const base = await apiPost<KnowledgeBase>('/knowledge/bases', { name })
    invalidateCache('GET:/knowledge/bases')
    return base
  },
  listDocuments: (baseId) =>
    resilientGet<KnowledgeDocument[]>(`/knowledge/bases/${baseId}/documents`, undefined, {
      dedupe: true,
    }),
  uploadDocument: async (baseId, file, onProgress) => {
    const doc = await apiUpload<KnowledgeDocument>(
      `/knowledge/bases/${baseId}/documents`,
      file,
      onProgress,
    )
    invalidateCache(`GET:/knowledge/bases/${baseId}/documents`)
    return doc
  },
  deleteDocument: async (id) => {
    await apiDelete(`/knowledge/documents/${id}`)
    invalidateCache('GET:/knowledge')
  },
}

export const knowledgeApi: KnowledgeApi = API_MODE === 'mock' ? mockKnowledge : live
