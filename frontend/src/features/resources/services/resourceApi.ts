import type { ResourceApi, ResourceItem } from '@/shared/services/types'
import { API_MODE } from '@/shared/lib/constants'
import { apiDelete, apiGet, apiUpload } from '@/shared/services/apiClient'
import { mockResources } from '@/shared/services/mockAdapter'

const live: ResourceApi = {
  list: () => apiGet<ResourceItem[]>('/resources'),
  upload: (file, onProgress) => apiUpload<ResourceItem>('/resources', file, onProgress),
  delete: (id) => apiDelete(`/resources/${id}`),
}

export const resourceApi: ResourceApi = API_MODE === 'mock' ? mockResources : live
