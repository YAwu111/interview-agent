import type { ResourceApi, ResourceItem } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiUpload } from '@/shared/services/apiClient'
import { idempotentWrite, invalidateCache, resilientGet } from '@/shared/services/resilience'
import { mockResources } from '@/shared/services/mockAdapter'

const live: ResourceApi = {
  list: () => resilientGet<ResourceItem[]>('/resources', undefined, { dedupe: true }),
  upload: async (file, onProgress) => {
    const item = await apiUpload<ResourceItem>('/resources', file, onProgress)
    invalidateCache('GET:/resources:')
    return item
  },
  delete: (id) =>
    idempotentWrite(
      (key) => apiDelete(`/resources/${id}`, { headers: { 'Idempotency-Key': key } }),
      { method: 'DELETE', path: `/api/v1/resources/${id}` },
    ).then(() => invalidateCache('GET:/resources:')),
}

export const resourceApi: ResourceApi = API_MODE === 'mock' ? mockResources : live
