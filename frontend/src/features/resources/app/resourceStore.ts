import { create } from 'zustand'
import type { ResourceItem } from '@/shared/services/types'
import { validateUploadFile } from '@/shared/lib/constants'
import { resourceApi } from '../services/resourceApi'

interface UploadTask {
  id: string
  name: string
  percent: number
  error?: string
}

interface ResourceState {
  resources: ResourceItem[]
  uploads: Record<string, UploadTask>
  load: () => Promise<void>
  upload: (file: File) => Promise<void>
  remove: (id: string) => Promise<void>
}

export const useResourceStore = create<ResourceState>()((set, get) => ({
  resources: [],
  uploads: {},

  load: async () => {
    const resources = await resourceApi.list()
    set({ resources })
  },

  upload: async (file) => {
    const taskId = crypto.randomUUID()
    const v = validateUploadFile(file)
    if (!v.ok) {
      set((st) => ({
        uploads: {
          ...st.uploads,
          [taskId]: { id: taskId, name: file.name, percent: 0, error: v.error },
        },
      }))
      return
    }
    set((st) => ({
      uploads: { ...st.uploads, [taskId]: { id: taskId, name: file.name, percent: 0 } },
    }))
    try {
      await resourceApi.upload(file, (percent) =>
        set((st) => ({
          uploads: { ...st.uploads, [taskId]: { id: taskId, name: file.name, percent } },
        })),
      )
      set((st) => {
        const uploads = { ...st.uploads }
        delete uploads[taskId]
        return { uploads }
      })
      await get().load()
    } catch (e) {
      set((st) => ({
        uploads: {
          ...st.uploads,
          [taskId]: {
            id: taskId,
            name: file.name,
            percent: 0,
            error: e instanceof Error ? e.message : 'failed',
          },
        },
      }))
    }
  },

  remove: async (id) => {
    await resourceApi.delete(id)
    set((st) => ({ resources: st.resources.filter((r) => r.id !== id) }))
  },
}))
