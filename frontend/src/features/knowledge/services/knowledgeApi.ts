import type { KnowledgeApi, KnowledgeBase, KnowledgeDocument } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiPost, apiUpload } from '@/shared/services/apiClient'
import { idempotentWrite, invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockKnowledge } from '@/shared/services/mockAdapter'

const live: KnowledgeApi = {
  listBases: () => resilientGet<KnowledgeBase[]>('/knowledge/bases', undefined, { dedupe: true }),
  createBase: (name) =>
    idempotentWrite(
      (key) =>
        apiPost<KnowledgeBase>('/knowledge/bases', { name }, {
          headers: { 'Idempotency-Key': key },
        }),
      { method: 'POST', path: '/api/v1/knowledge/bases', body: { name } },
    ).then((base) => {
      invalidateCache('GET:/knowledge/bases:')
      return base
    }),
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
    invalidateCache(`GET:/knowledge/bases/${baseId}/documents:`)
    invalidateCache('GET:/knowledge/bases:')
    return doc
  },
  deleteDocument: (id) =>
    idempotentWrite(
      (key) =>
        apiDelete(`/knowledge/documents/${id}`, { headers: { 'Idempotency-Key': key } }),
      { method: 'DELETE', path: `/api/v1/knowledge/documents/${id}` },
    ).then(() => {
      invalidateCache('GET:/knowledge/bases:')
      invalidateCache('GET:/knowledge/bases/')
    }),
}

export const knowledgeApi: KnowledgeApi = API_MODE === 'mock' ? mockKnowledge : live
